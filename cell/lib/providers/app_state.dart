import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';
import '../models/models.dart';
import '../models/notification_model.dart';
import '../services/api_service.dart';
import '../services/cache_service.dart' show CacheService, CacheMetadata;
import '../services/offline_service.dart';
import '../services/websocket_service.dart';

// Import feature providers
import 'feed_provider.dart';
import 'chat_provider.dart';
import 'notification_provider.dart';
import 'civilization_provider.dart';

/// AppState acts as a coordinator for feature-specific providers.
/// It handles initialization, connectivity, and WebSocket setup.
/// For backward compatibility, it exposes delegated getters and methods.
class AppState extends ChangeNotifier {
  final ApiService _api = ApiService();
  final OfflineService _offlineService = OfflineService.instance;
  final CacheService _cacheService = CacheService.instance;
  late WebSocketService _ws;
  StreamSubscription<bool>? _connectivitySubscription;

  // Feature providers - exposed for direct access when needed
  final FeedProvider feedProvider = FeedProvider();
  final ChatProvider chatProvider = ChatProvider();
  final NotificationProvider notificationProvider = NotificationProvider();
  final CivilizationProvider civilizationProvider = CivilizationProvider();

  // User state
  AppUser? _currentUser;
  bool _isInitialized = false;
  bool _isLoading = false;
  String? _error;

  // Connectivity state
  bool _isOnline = true;
  int _queuedActionsCount = 0;

  // Getters for user state
  AppUser? get currentUser => _currentUser;
  bool get isInitialized => _isInitialized;
  bool get isLoading => _isLoading;
  String? get error => _error;

  // Connectivity getters
  bool get isOnline => _isOnline;
  int get queuedActionsCount => _queuedActionsCount;

  WebSocketService get websocket => _ws;

  // ========================================================================
  // DELEGATED GETTERS (for backward compatibility)
  // ========================================================================

  // Feed state
  List<Post> get posts => feedProvider.posts;
  bool get isLoadingFeed => feedProvider.isLoadingFeed;
  bool get hasMorePosts => feedProvider.hasMorePosts;

  // Communities
  List<Community> get communities => civilizationProvider.communities;
  Community? get selectedCommunity => civilizationProvider.selectedCommunity;

  // Chat state
  List<ChatMessage> get chatMessages => chatProvider.chatMessages;
  bool get isLoadingChat => chatProvider.isLoadingChat;

  // DM state
  List<Conversation> get conversations => chatProvider.conversations;
  List<DirectMessage> get directMessages => chatProvider.directMessages;
  BotProfile? get selectedBot => chatProvider.selectedBot;
  bool get isTyping => chatProvider.isTyping;
  Map<String, String> get communityTypingUsers => chatProvider.communityTypingUsers;

  // Notification state
  List<NotificationModel> get notifications => notificationProvider.notifications;
  int get unreadNotificationCount => notificationProvider.unreadNotificationCount;

  // ========================================================================
  // INITIALIZATION
  // ========================================================================

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

      // Update feature providers with user ID
      _updateProvidersWithUser();

      // Initialize WebSocket
      _ws = WebSocketService(clientId: _currentUser!.id);
      await _ws.connect();
      _setupWebSocketListeners();

      // Set WebSocket on providers that need it
      chatProvider.setWebSocketService(_ws);
      civilizationProvider.setWebSocketService(_ws);

      // Load initial data
      await Future.wait([
        civilizationProvider.loadCommunities(),
        feedProvider.loadFeed(),
      ]);

      // Auto-select first community for chat
      if (civilizationProvider.communities.isNotEmpty) {
        selectCommunity(civilizationProvider.communities.first);
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

  void _updateProvidersWithUser() {
    feedProvider.setCurrentUserId(_currentUser?.id);
    chatProvider.setCurrentUserId(_currentUser?.id);
    notificationProvider.setCurrentUserId(_currentUser?.id);
  }

  /// Handle connectivity changes
  void _onConnectivityChanged(bool isOnline) {
    final wasOffline = !_isOnline;
    _isOnline = isOnline;
    _queuedActionsCount = _offlineService.queuedActionCount;

    // Update chat provider online status
    chatProvider.setOnlineStatus(isOnline);

    debugPrint('AppState: Connectivity changed - online: $isOnline');

    // If coming back online, process queued actions and refresh data
    if (isOnline && wasOffline) {
      _offlineService.processQueue();
      // Refresh data in background
      feedProvider.loadFeed(refresh: true);
      civilizationProvider.loadCommunities();
      if (_currentUser != null) {
        chatProvider.loadConversations();
      }
    }

    notifyListeners();
  }

  /// Load cached data for offline mode
  Future<void> _loadCachedData() async {
    await civilizationProvider.loadCachedCommunities();
    await feedProvider.loadCachedFeed();

    if (civilizationProvider.selectedCommunity != null) {
      await chatProvider.loadCachedChatMessages(civilizationProvider.selectedCommunity!.id);
    }

    debugPrint('AppState: Loaded cached data - ${feedProvider.posts.length} posts, ${civilizationProvider.communities.length} communities');
  }

  void _setupWebSocketListeners() {
    // New posts
    _ws.onNewPost.listen((post) {
      feedProvider.addPost(post);
      notifyListeners();
    });

    // Post likes
    _ws.onPostLiked.listen((data) {
      final postId = data['post_id'] as String;
      final likeCount = data['like_count'] as int;
      feedProvider.updatePostLikeCount(postId, likeCount);
      notifyListeners();
    });

    // New comments
    _ws.onNewComment.listen((comment) {
      // Update comment count on the post
      // The comment will be loaded when viewing post details
      notifyListeners();
    });

    // New chat messages
    _ws.onNewChatMessage.listen((message) {
      chatProvider.addChatMessage(message);
      notifyListeners();
    });

    // New DMs
    _ws.onNewDm.listen((message) {
      chatProvider.addDirectMessage(message);
      notifyListeners();
    });

    // Typing indicator for DMs
    _ws.onTyping.listen((botId) {
      chatProvider.updateTypingIndicator(botId);
      notifyListeners();
    });

    // Community typing indicator
    _ws.onCommunityTyping.listen((data) {
      chatProvider.updateCommunityTyping(
        data['community_id'] as String,
        data['user_id'] as String,
        data['user_name'] as String,
        data['is_typing'] as bool,
      );
      notifyListeners();
    });
  }

  // ========================================================================
  // DELEGATED FEED METHODS
  // ========================================================================

  Future<void> loadFeed({bool refresh = false}) async {
    await feedProvider.loadFeed(refresh: refresh);
    notifyListeners();
  }

  Future<void> likePost(Post post, {ReactionType reactionType = ReactionType.like}) async {
    await feedProvider.likePost(post, reactionType: reactionType);
    _queuedActionsCount = _offlineService.queuedActionCount;
    notifyListeners();
  }

  Future<void> commentOnPost(Post post, String content) async {
    await feedProvider.commentOnPost(post, content);
    _queuedActionsCount = _offlineService.queuedActionCount;
    notifyListeners();
  }

  Future<Post> createPost({required String content, required String communityId}) async {
    final post = await feedProvider.createPost(content: content, communityId: communityId);
    notifyListeners();
    return post;
  }

  // ========================================================================
  // DELEGATED COMMUNITY METHODS
  // ========================================================================

  Future<void> loadCommunities() async {
    await civilizationProvider.loadCommunities();
    notifyListeners();
  }

  void selectCommunity(Community? community) {
    civilizationProvider.selectCommunity(community);

    // Update feed and chat providers
    feedProvider.setSelectedCommunityId(community?.id);
    chatProvider.setSelectedCommunityId(community?.id);
    chatProvider.clearCommunityTyping();

    if (community != null) {
      chatProvider.loadCommunityChat(community.id);
    }
    feedProvider.loadFeed(refresh: true);
    notifyListeners();
  }

  // ========================================================================
  // DELEGATED CHAT METHODS
  // ========================================================================

  Future<void> loadCommunityChat(String communityId) async {
    await chatProvider.loadCommunityChat(communityId);
    notifyListeners();
  }

  Future<void> sendChatMessage(String content, {String? replyToId}) async {
    await chatProvider.sendChatMessage(content, replyToId: replyToId);
    _queuedActionsCount = _offlineService.queuedActionCount;
    notifyListeners();
  }

  // ========================================================================
  // DELEGATED DM METHODS
  // ========================================================================

  Future<void> loadConversations() async {
    await chatProvider.loadConversations();
    notifyListeners();
  }

  Future<void> selectBot(BotProfile bot) async {
    await chatProvider.selectBot(bot);
    notifyListeners();
  }

  Future<void> sendDirectMessage(String content) async {
    await chatProvider.sendDirectMessage(content);
    _queuedActionsCount = _offlineService.queuedActionCount;
    notifyListeners();
  }

  Future<List<BotProfile>> loadBots({String? communityId, int limit = 50, int offset = 0}) async {
    return chatProvider.loadBots(communityId: communityId, limit: limit, offset: offset);
  }

  // ========================================================================
  // DELEGATED NOTIFICATION METHODS
  // ========================================================================

  Future<void> loadNotifications() async {
    await notificationProvider.loadNotifications();
    notifyListeners();
  }

  Future<void> markNotificationRead(String notificationId) async {
    await notificationProvider.markNotificationRead(notificationId);
    notifyListeners();
  }

  Future<void> markAllNotificationsRead() async {
    await notificationProvider.markAllNotificationsRead();
    notifyListeners();
  }

  Future<void> refreshUnreadCount() async {
    await notificationProvider.refreshUnreadCount();
    notifyListeners();
  }

  // ========================================================================
  // CONNECTIVITY & CACHE METHODS
  // ========================================================================

  /// Manually check and update connectivity status
  Future<void> checkConnectivity() async {
    _isOnline = await _offlineService.checkOnlineStatus();
    _queuedActionsCount = _offlineService.queuedActionCount;
    chatProvider.setOnlineStatus(_isOnline);
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

  /// Clear expired cache entries
  Future<int> clearExpiredCache() async {
    return await _cacheService.clearExpiredCache();
  }

  /// Invalidate feed cache (useful after creating a post)
  Future<void> invalidateFeedCache() async {
    await _cacheService.invalidateAllFeeds();
  }

  /// Invalidate chat cache for a specific community
  Future<void> invalidateChatCache(String communityId) async {
    await _cacheService.removeCachedData('chat_$communityId');
  }

  /// Invalidate DM cache for a specific conversation
  Future<void> invalidateDMCache(String conversationId) async {
    await _cacheService.removeCachedData('dm_$conversationId');
  }

  /// Invalidate all conversation-related caches
  Future<void> invalidateConversationsCache() async {
    await _cacheService.invalidateAllConversations();
  }

  /// Get cache metadata for debugging/display
  Future<List<CacheMetadata>> getCacheMetadata() async {
    return await _cacheService.getAllCacheMetadata();
  }

  // ========================================================================
  // CLEANUP
  // ========================================================================

  @override
  void dispose() {
    _connectivitySubscription?.cancel();
    _ws.dispose();
    _api.dispose();
    notificationProvider.disposeService();
    _offlineService.dispose();
    _cacheService.dispose();
    super.dispose();
  }
}
