import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';
import '../models/models.dart';
import '../models/notification_model.dart';
import '../models/offline_action.dart';
import '../services/api_service.dart';
import '../services/cache_service.dart';
import '../services/notification_service.dart';
import '../services/offline_service.dart';
import '../services/websocket_service.dart';

class AppState extends ChangeNotifier {
  final ApiService _api = ApiService();
  final NotificationService _notificationService = NotificationService();
  final OfflineService _offlineService = OfflineService.instance;
  final CacheService _cacheService = CacheService.instance;
  late WebSocketService _ws;
  StreamSubscription<bool>? _connectivitySubscription;

  // User state
  AppUser? _currentUser;
  bool _isInitialized = false;
  bool _isLoading = false;
  String? _error;

  // Connectivity state
  bool _isOnline = true;
  int _queuedActionsCount = 0;

  // Feed state
  List<Post> _posts = [];
  bool _isLoadingFeed = false;
  bool _hasMorePosts = true;

  // Communities
  List<Community> _communities = [];
  Community? _selectedCommunity;

  // Chat state
  List<ChatMessage> _chatMessages = [];
  bool _isLoadingChat = false;

  // DM state
  List<Conversation> _conversations = [];
  List<DirectMessage> _directMessages = [];
  String? _selectedConversationId;
  BotProfile? _selectedBot;
  bool _isTyping = false;

  // Notification state
  List<NotificationModel> _notifications = [];
  int _unreadNotificationCount = 0;

  // Getters
  AppUser? get currentUser => _currentUser;
  bool get isInitialized => _isInitialized;
  bool get isLoading => _isLoading;
  String? get error => _error;

  List<Post> get posts => _posts;
  bool get isLoadingFeed => _isLoadingFeed;
  bool get hasMorePosts => _hasMorePosts;

  List<Community> get communities => _communities;
  Community? get selectedCommunity => _selectedCommunity;

  List<ChatMessage> get chatMessages => _chatMessages;
  bool get isLoadingChat => _isLoadingChat;

  List<Conversation> get conversations => _conversations;
  List<DirectMessage> get directMessages => _directMessages;
  BotProfile? get selectedBot => _selectedBot;
  bool get isTyping => _isTyping;

  List<NotificationModel> get notifications => _notifications;
  int get unreadNotificationCount => _unreadNotificationCount;

  // Connectivity getters
  bool get isOnline => _isOnline;
  int get queuedActionsCount => _queuedActionsCount;

  WebSocketService get websocket => _ws;

  // Initialize app
  Future<void> initialize() async {
    if (_isInitialized) return;

    _isLoading = true;
    notifyListeners();

    try {
      // Initialize offline service and cache
      await _offlineService.initialize();
      await _cacheService.initialize();

      // Check initial connectivity
      _isOnline = await _offlineService.checkOnlineStatus();
      _queuedActionsCount = _offlineService.queuedActionCount;

      // Listen for connectivity changes
      _connectivitySubscription = _offlineService.onlineStatusStream.listen(_onConnectivityChanged);

      // Get or create device ID
      final prefs = await SharedPreferences.getInstance();
      String? deviceId = prefs.getString('device_id');
      if (deviceId == null) {
        deviceId = const Uuid().v4();
        await prefs.setString('device_id', deviceId);
      }

      // Check API health
      final isHealthy = await _api.healthCheck();
      if (!isHealthy) {
        // Try to use cached data if offline
        if (!_isOnline) {
          debugPrint('AppState: Offline mode - loading cached data');
          await _loadCachedData();
          _isInitialized = true;
          _error = null;
        } else {
          _error = 'Cannot connect to server. Make sure the API is running.';
        }
        _isLoading = false;
        notifyListeners();
        return;
      }

      // Register/get user
      String displayName = prefs.getString('display_name') ?? 'User';
      _currentUser = await _api.registerUser(deviceId, displayName);

      // Initialize WebSocket
      _ws = WebSocketService(clientId: _currentUser!.id);
      await _ws.connect();
      _setupWebSocketListeners();

      // Load initial data
      await Future.wait([
        loadCommunities(),
        loadFeed(),
      ]);

      // Auto-select first community for chat
      if (_communities.isNotEmpty) {
        selectCommunity(_communities.first);
      }

      _isInitialized = true;
      _error = null;
    } catch (e) {
      _error = 'Initialization failed: $e';
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Handle connectivity changes
  void _onConnectivityChanged(bool isOnline) {
    final wasOffline = !_isOnline;
    _isOnline = isOnline;
    _queuedActionsCount = _offlineService.queuedActionCount;

    debugPrint('AppState: Connectivity changed - online: $isOnline');

    // If coming back online, process queued actions and refresh data
    if (isOnline && wasOffline) {
      _offlineService.processQueue();
      // Refresh data in background
      loadFeed(refresh: true);
      loadCommunities();
      if (_currentUser != null) {
        loadConversations();
      }
    }

    notifyListeners();
  }

  /// Load cached data for offline mode
  Future<void> _loadCachedData() async {
    _communities = await _offlineService.getCachedCommunities();
    _posts = await _offlineService.getCachedFeed();

    if (_communities.isNotEmpty) {
      _selectedCommunity = _communities.first;
      _chatMessages = await _offlineService.getCachedChatMessages(_selectedCommunity!.id);
    }

    debugPrint('AppState: Loaded cached data - ${_posts.length} posts, ${_communities.length} communities');
  }

  void _setupWebSocketListeners() {
    // New posts
    _ws.onNewPost.listen((post) {
      _posts.insert(0, post);
      notifyListeners();
    });

    // Post likes
    _ws.onPostLiked.listen((data) {
      final postId = data['post_id'] as String;
      final index = _posts.indexWhere((p) => p.id == postId);
      if (index != -1) {
        _posts[index].likeCount = data['like_count'] as int;
        notifyListeners();
      }
    });

    // New comments
    _ws.onNewComment.listen((comment) {
      // Update comment count on the post
      // The comment will be loaded when viewing post details
      notifyListeners();
    });

    // New chat messages
    _ws.onNewChatMessage.listen((message) {
      if (_selectedCommunity != null && message.communityId == _selectedCommunity!.id) {
        _chatMessages.add(message);
        notifyListeners();
      }
    });

    // New DMs
    _ws.onNewDm.listen((message) {
      if (_selectedConversationId == message.conversationId) {
        _directMessages.add(message);
        notifyListeners();
      }
      // Update conversations list
      loadConversations();
    });

    // Typing indicator
    _ws.onTyping.listen((botId) {
      _isTyping = botId.isNotEmpty && _selectedBot?.id == botId;
      notifyListeners();
    });
  }

  // ========================================================================
  // FEED METHODS
  // ========================================================================

  Future<void> loadFeed({bool refresh = false}) async {
    if (_isLoadingFeed) return;

    _isLoadingFeed = true;
    if (refresh) {
      _posts = [];
      _hasMorePosts = true;
    }
    notifyListeners();

    try {
      final newPosts = await _api.getFeed(
        userId: _currentUser?.id,
        communityId: _selectedCommunity?.id,
        offset: refresh ? 0 : _posts.length,
      );

      if (refresh) {
        _posts = newPosts;
      } else {
        _posts.addAll(newPosts);
      }
      _hasMorePosts = newPosts.length >= 20;
    } catch (e) {
      _error = 'Failed to load feed: $e';
    } finally {
      _isLoadingFeed = false;
      notifyListeners();
    }
  }

  Future<void> likePost(Post post, {ReactionType reactionType = ReactionType.like}) async {
    if (_currentUser == null) return;

    // Optimistic update
    final wasLiked = post.isLikedByUser;
    final previousReactionType = post.userReactionType;

    if (wasLiked && post.userReactionType == reactionType) {
      // Remove reaction (toggle off)
      post.isLikedByUser = false;
      post.userReactionType = null;
      post.likeCount -= 1;
      // Update reaction counts
      final currentCount = post.reactionCounts.counts[reactionType] ?? 0;
      if (currentCount > 0) {
        post.reactionCounts.counts[reactionType] = currentCount - 1;
      }
    } else {
      // Add or change reaction
      if (wasLiked && previousReactionType != null) {
        // Changing reaction type - decrement old, increment new
        final oldCount = post.reactionCounts.counts[previousReactionType] ?? 0;
        if (oldCount > 0) {
          post.reactionCounts.counts[previousReactionType] = oldCount - 1;
        }
      } else if (!wasLiked) {
        // New reaction
        post.likeCount += 1;
      }
      post.isLikedByUser = true;
      post.userReactionType = reactionType;
      post.reactionCounts.counts[reactionType] =
          (post.reactionCounts.counts[reactionType] ?? 0) + 1;
    }
    notifyListeners();

    try {
      if (!post.isLikedByUser) {
        await _api.unlikePost(post.id, _currentUser!.id);
      } else {
        await _api.likePost(post.id, _currentUser!.id, reactionType: reactionType.name);
      }
    } on OfflineException {
      // Queue for later when back online
      await _offlineService.queueAction(
        !post.isLikedByUser ? ActionType.unlikePost : ActionType.likePost,
        {
          'post_id': post.id,
          'user_id': _currentUser!.id,
          'reaction_type': reactionType.name,
        },
      );
      _queuedActionsCount = _offlineService.queuedActionCount;
      notifyListeners();
    } catch (e) {
      // Revert optimistic update on error
      post.isLikedByUser = wasLiked;
      post.userReactionType = previousReactionType;
      if (wasLiked && previousReactionType == reactionType) {
        post.likeCount += 1;
      } else if (!wasLiked) {
        post.likeCount -= 1;
      }
      _error = 'Failed to react to post: $e';
      notifyListeners();
    }
  }

  Future<void> commentOnPost(Post post, String content) async {
    if (_currentUser == null) return;

    try {
      final comment = await _api.createComment(post.id, _currentUser!.id, content);
      post.recentComments.insert(0, comment);
      post.commentCount++;
      notifyListeners();
    } on OfflineException {
      // Queue comment for later
      await _offlineService.queueAction(
        ActionType.createComment,
        {'post_id': post.id, 'user_id': _currentUser!.id, 'content': content},
      );
      _queuedActionsCount = _offlineService.queuedActionCount;
      _error = 'Comment will be posted when back online';
      notifyListeners();
    } catch (e) {
      _error = 'Failed to comment: $e';
      notifyListeners();
    }
  }

  // ========================================================================
  // COMMUNITY METHODS
  // ========================================================================

  Future<void> loadCommunities() async {
    try {
      _communities = await _api.getCommunities();
      notifyListeners();
    } catch (e) {
      _error = 'Failed to load communities: $e';
      notifyListeners();
    }
  }

  void selectCommunity(Community? community) {
    _selectedCommunity = community;
    _chatMessages = [];
    notifyListeners();

    if (community != null) {
      _ws.subscribeToCommunity(community.id);
      loadCommunityChat(community.id);
    }
    loadFeed(refresh: true);
  }

  // ========================================================================
  // COMMUNITY CHAT METHODS
  // ========================================================================

  Future<void> loadCommunityChat(String communityId) async {
    _isLoadingChat = true;
    notifyListeners();

    try {
      _chatMessages = await _api.getCommunityChat(communityId);
    } catch (e) {
      _error = 'Failed to load chat: $e';
    } finally {
      _isLoadingChat = false;
      notifyListeners();
    }
  }

  Future<void> sendChatMessage(String content, {String? replyToId}) async {
    if (_currentUser == null || _selectedCommunity == null) return;

    if (!_isOnline) {
      // Queue message for later
      await _offlineService.queueAction(
        ActionType.sendMessage,
        {
          'community_id': _selectedCommunity!.id,
          'user_id': _currentUser!.id,
          'content': content,
          'reply_to_id': replyToId,
        },
      );
      _queuedActionsCount = _offlineService.queuedActionCount;
      _error = 'Message will be sent when back online';
      notifyListeners();
      return;
    }

    try {
      // Send via WebSocket for real-time
      _ws.sendChatMessage(
        _selectedCommunity!.id,
        _currentUser!.id,
        content,
        replyToId: replyToId,
      );
    } catch (e) {
      _error = 'Failed to send message: $e';
      notifyListeners();
    }
  }

  // ========================================================================
  // DIRECT MESSAGE METHODS
  // ========================================================================

  Future<void> loadConversations() async {
    if (_currentUser == null) return;

    try {
      _conversations = await _api.getConversations(_currentUser!.id);
      notifyListeners();
    } catch (e) {
      _error = 'Failed to load conversations: $e';
      notifyListeners();
    }
  }

  Future<void> selectBot(BotProfile bot) async {
    _selectedBot = bot;
    _directMessages = [];
    _selectedConversationId = null;
    notifyListeners();

    // Generate conversation ID
    final ids = [_currentUser!.id, bot.id]..sort();
    _selectedConversationId = '${ids[0]}_${ids[1]}';

    // Load existing messages
    try {
      _directMessages = await _api.getDirectMessages(
        _selectedConversationId!,
        _currentUser!.id,
      );
      notifyListeners();
    } catch (e) {
      // No existing conversation, that's ok
    }
  }

  Future<void> sendDirectMessage(String content) async {
    if (_currentUser == null || _selectedBot == null) return;

    try {
      // Send user message
      final message = await _api.sendDirectMessage(
        _currentUser!.id,
        _selectedBot!.id,
        content,
      );
      _directMessages.add(message);
      notifyListeners();

      // Request bot response via WebSocket
      _ws.sendDm(_selectedBot!.id, _currentUser!.id, content);
    } on OfflineException {
      // Queue DM for later
      await _offlineService.queueAction(
        ActionType.sendDm,
        {
          'user_id': _currentUser!.id,
          'bot_id': _selectedBot!.id,
          'content': content,
        },
      );
      _queuedActionsCount = _offlineService.queuedActionCount;
      _error = 'Message will be sent when back online';
      notifyListeners();
    } catch (e) {
      _error = 'Failed to send message: $e';
      notifyListeners();
    }
  }

  Future<List<BotProfile>> loadBots({String? communityId}) async {
    try {
      return await _api.getBots(communityId: communityId);
    } catch (e) {
      _error = 'Failed to load bots: $e';
      notifyListeners();
      return [];
    }
  }

  // ========================================================================
  // POST CREATION METHODS
  // ========================================================================

  Future<Post> createPost({
    required String content,
    required String communityId,
  }) async {
    if (_currentUser == null) {
      throw Exception('User not logged in');
    }

    try {
      final post = await _api.createPost(
        userId: _currentUser!.id,
        communityId: communityId,
        content: content,
      );

      // Add to local posts list
      _posts.insert(0, post);
      notifyListeners();

      return post;
    } catch (e) {
      _error = 'Failed to create post: $e';
      notifyListeners();
      rethrow;
    }
  }

  // ========================================================================
  // NOTIFICATION METHODS
  // ========================================================================

  Future<void> loadNotifications() async {
    if (_currentUser == null) return;

    try {
      _notifications = await _notificationService.getNotifications(_currentUser!.id);
      _unreadNotificationCount = _notifications.where((n) => !n.isRead).length;
      notifyListeners();
    } catch (e) {
      _error = 'Failed to load notifications: $e';
      notifyListeners();
    }
  }

  Future<void> markNotificationRead(String notificationId) async {
    await _notificationService.markAsRead(notificationId);

    final index = _notifications.indexWhere((n) => n.id == notificationId);
    if (index != -1 && !_notifications[index].isRead) {
      _notifications[index] = _notifications[index].copyWith(isRead: true);
      _unreadNotificationCount = _notifications.where((n) => !n.isRead).length;
      notifyListeners();
    }
  }

  Future<void> markAllNotificationsRead() async {
    if (_currentUser == null) return;

    await _notificationService.markAllRead(_currentUser!.id);

    _notifications = _notifications.map((n) => n.copyWith(isRead: true)).toList();
    _unreadNotificationCount = 0;
    notifyListeners();
  }

  Future<void> refreshUnreadCount() async {
    if (_currentUser == null) return;

    _unreadNotificationCount = await _notificationService.getUnreadCount(_currentUser!.id);
    notifyListeners();
  }

  // ========================================================================
  // CLEANUP
  // ========================================================================

  /// Manually check and update connectivity status
  Future<void> checkConnectivity() async {
    _isOnline = await _offlineService.checkOnlineStatus();
    _queuedActionsCount = _offlineService.queuedActionCount;
    notifyListeners();
  }

  /// Get formatted cache size
  Future<String> getCacheSize() async {
    return await _cacheService.getFormattedCacheSize();
  }

  /// Clear all cached data
  Future<void> clearCache() async {
    await _cacheService.clearCache();
    notifyListeners();
  }

  @override
  void dispose() {
    _connectivitySubscription?.cancel();
    _ws.dispose();
    _api.dispose();
    _notificationService.dispose();
    _offlineService.dispose();
    super.dispose();
  }
}
