// Offline service for managing connectivity and offline actions

import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';
import '../models/models.dart';
import '../models/offline_action.dart';
import 'cache_service.dart';

/// Service for managing offline functionality
class OfflineService {
  static OfflineService? _instance;

  final Connectivity _connectivity = Connectivity();
  final CacheService _cache = CacheService.instance;

  SharedPreferences? _prefs;
  bool _initialized = false;
  bool _isOnline = true;

  // Queue storage key
  static const String _queueKey = 'offline_action_queue';

  // Connectivity stream
  StreamSubscription<List<ConnectivityResult>>? _connectivitySubscription;
  final StreamController<bool> _onlineStatusController = StreamController<bool>.broadcast();

  // Action queue
  List<OfflineAction> _actionQueue = [];
  bool _isProcessingQueue = false;

  // Callbacks
  Function(OfflineAction action)? onActionProcessed;
  Function(OfflineAction action, String error)? onActionFailed;

  OfflineService._();

  static OfflineService get instance {
    _instance ??= OfflineService._();
    return _instance!;
  }

  /// Initialize the offline service
  Future<void> initialize() async {
    if (_initialized) return;

    _prefs = await SharedPreferences.getInstance();
    await _cache.initialize();

    // Load persisted queue
    await _loadQueue();

    // Check initial connectivity
    final results = await _connectivity.checkConnectivity();
    _updateOnlineStatus(results);

    // Listen for connectivity changes
    _connectivitySubscription = _connectivity.onConnectivityChanged.listen(_updateOnlineStatus);

    _initialized = true;
    debugPrint('OfflineService: Initialized, online: $_isOnline');
  }

  /// Ensure service is initialized
  Future<void> _ensureInitialized() async {
    if (!_initialized) {
      await initialize();
    }
  }

  /// Get online status
  bool get isOnline => _isOnline;

  /// Stream of online status changes
  Stream<bool> get onlineStatusStream => _onlineStatusController.stream;

  /// Get queued action count
  int get queuedActionCount => _actionQueue.length;

  /// Get all queued actions
  List<OfflineAction> get queuedActions => List.unmodifiable(_actionQueue);

  /// Update online status based on connectivity result
  void _updateOnlineStatus(List<ConnectivityResult> results) {
    final wasOnline = _isOnline;
    _isOnline = results.isNotEmpty && !results.contains(ConnectivityResult.none);

    if (_isOnline != wasOnline) {
      _onlineStatusController.add(_isOnline);
      debugPrint('OfflineService: Connectivity changed, online: $_isOnline');

      // Process queue when coming back online
      if (_isOnline) {
        processQueue();
      }
    }
  }

  /// Check if device is currently online
  Future<bool> checkOnlineStatus() async {
    await _ensureInitialized();
    final results = await _connectivity.checkConnectivity();
    _updateOnlineStatus(results);
    return _isOnline;
  }

  // ========================================================================
  // CACHE METHODS (delegating to CacheService)
  // ========================================================================

  /// Cache feed posts
  Future<bool> cacheFeed(List<Post> posts, {String? communityId}) async {
    await _ensureInitialized();
    final jsonPosts = posts.map((p) => _postToJson(p)).toList();
    return await _cache.cacheFeed(jsonPosts, communityId: communityId);
  }

  /// Get cached feed posts
  Future<List<Post>> getCachedFeed({String? communityId}) async {
    await _ensureInitialized();
    final jsonPosts = await _cache.getCachedFeed(communityId: communityId, ignoreExpiry: !_isOnline);
    if (jsonPosts == null) return [];
    return jsonPosts.map((json) => Post.fromJson(json)).toList();
  }

  /// Cache conversations
  Future<bool> cacheConversations(String userId, List<Conversation> conversations) async {
    await _ensureInitialized();
    final jsonConversations = conversations.map((c) => _conversationToJson(c)).toList();
    return await _cache.cacheConversations(userId, jsonConversations);
  }

  /// Get cached conversations
  Future<List<Conversation>> getCachedConversations(String userId) async {
    await _ensureInitialized();
    final jsonConversations = await _cache.getCachedConversations(userId, ignoreExpiry: !_isOnline);
    if (jsonConversations == null) return [];
    return jsonConversations.map((json) => Conversation.fromJson(json)).toList();
  }

  /// Cache communities
  Future<bool> cacheCommunities(List<Community> communities) async {
    await _ensureInitialized();
    final jsonCommunities = communities.map((c) => _communityToJson(c)).toList();
    return await _cache.cacheCommunities(jsonCommunities);
  }

  /// Get cached communities
  Future<List<Community>> getCachedCommunities() async {
    await _ensureInitialized();
    final jsonCommunities = await _cache.getCachedCommunities(ignoreExpiry: !_isOnline);
    if (jsonCommunities == null) return [];
    return jsonCommunities.map((json) => Community.fromJson(json)).toList();
  }

  /// Cache chat messages
  Future<bool> cacheChatMessages(String communityId, List<ChatMessage> messages) async {
    await _ensureInitialized();
    final jsonMessages = messages.map((m) => _chatMessageToJson(m)).toList();
    return await _cache.cacheChatMessages(communityId, jsonMessages);
  }

  /// Get cached chat messages
  Future<List<ChatMessage>> getCachedChatMessages(String communityId) async {
    await _ensureInitialized();
    final jsonMessages = await _cache.getCachedChatMessages(communityId, ignoreExpiry: !_isOnline);
    if (jsonMessages == null) return [];
    return jsonMessages.map((json) => ChatMessage.fromJson(json)).toList();
  }

  /// Cache direct messages
  Future<bool> cacheDirectMessages(String conversationId, String userId, List<DirectMessage> messages) async {
    await _ensureInitialized();
    final jsonMessages = messages.map((m) => _directMessageToJson(m)).toList();
    return await _cache.cacheDirectMessages(conversationId, jsonMessages);
  }

  /// Get cached direct messages
  Future<List<DirectMessage>> getCachedDirectMessages(String conversationId, String userId) async {
    await _ensureInitialized();
    final jsonMessages = await _cache.getCachedDirectMessages(conversationId, ignoreExpiry: !_isOnline);
    if (jsonMessages == null) return [];
    return jsonMessages.map((json) => DirectMessage.fromJson(json, userId)).toList();
  }

  // ========================================================================
  // ACTION QUEUE METHODS
  // ========================================================================

  /// Queue an action for processing when online
  Future<String> queueAction(ActionType type, Map<String, dynamic> payload) async {
    await _ensureInitialized();

    final action = OfflineAction(
      id: const Uuid().v4(),
      type: type,
      payload: payload,
    );

    _actionQueue.add(action);
    await _saveQueue();

    debugPrint('OfflineService: Queued action ${action.id} (${type.value})');

    // Try to process immediately if online
    if (_isOnline) {
      processQueue();
    }

    return action.id;
  }

  /// Process queued actions
  Future<void> processQueue() async {
    if (_isProcessingQueue || _actionQueue.isEmpty || !_isOnline) return;

    _isProcessingQueue = true;
    debugPrint('OfflineService: Processing ${_actionQueue.length} queued actions');

    final actionsToProcess = List<OfflineAction>.from(_actionQueue);

    for (final action in actionsToProcess) {
      try {
        await _processAction(action);
        _actionQueue.removeWhere((a) => a.id == action.id);
        onActionProcessed?.call(action);
        debugPrint('OfflineService: Processed action ${action.id}');
      } catch (e) {
        action.incrementRetry();
        action.errorMessage = e.toString();

        if (action.hasExceededRetries) {
          _actionQueue.removeWhere((a) => a.id == action.id);
          onActionFailed?.call(action, 'Max retries exceeded: ${action.errorMessage}');
          debugPrint('OfflineService: Action ${action.id} failed permanently');
        } else {
          debugPrint('OfflineService: Action ${action.id} failed, will retry');
        }
      }
    }

    await _saveQueue();
    _isProcessingQueue = false;
  }

  /// Process a single action
  Future<void> _processAction(OfflineAction action) async {
    // This method should be overridden or actions should be processed externally
    // Here we just mark it as processed
    // In practice, you would call the appropriate API methods

    switch (action.type) {
      case ActionType.sendMessage:
      case ActionType.createPost:
      case ActionType.likePost:
      case ActionType.unlikePost:
      case ActionType.sendDm:
      case ActionType.createComment:
        // Actions will be processed by the AppState/ApiService
        // This is just a placeholder
        break;
    }
  }

  /// Remove a specific action from the queue
  Future<bool> removeAction(String actionId) async {
    await _ensureInitialized();
    final initialLength = _actionQueue.length;
    _actionQueue.removeWhere((a) => a.id == actionId);

    if (_actionQueue.length != initialLength) {
      await _saveQueue();
      return true;
    }
    return false;
  }

  /// Clear all queued actions
  Future<void> clearQueue() async {
    await _ensureInitialized();
    _actionQueue.clear();
    await _saveQueue();
  }

  /// Save queue to persistent storage
  Future<void> _saveQueue() async {
    final jsonList = _actionQueue.map((a) => a.toJson()).toList();
    await _prefs!.setString(_queueKey, jsonEncode(jsonList));
  }

  /// Load queue from persistent storage
  Future<void> _loadQueue() async {
    final jsonStr = _prefs!.getString(_queueKey);
    if (jsonStr == null) {
      _actionQueue = [];
      return;
    }

    try {
      final List<dynamic> jsonList = jsonDecode(jsonStr);
      _actionQueue = jsonList
          .map((json) => OfflineAction.fromJson(json as Map<String, dynamic>))
          .toList();
      debugPrint('OfflineService: Loaded ${_actionQueue.length} queued actions');
    } catch (e) {
      debugPrint('OfflineService: Failed to load queue: $e');
      _actionQueue = [];
    }
  }

  // ========================================================================
  // JSON SERIALIZATION HELPERS
  // ========================================================================

  Map<String, dynamic> _postToJson(Post post) {
    return {
      'id': post.id,
      'author': {
        'id': post.author.id,
        'display_name': post.author.displayName,
        'handle': post.author.handle,
        'avatar_seed': post.author.avatarSeed,
        'is_ai_labeled': post.author.isAiLabeled,
        'ai_label_text': post.author.aiLabelText,
      },
      'community_id': post.communityId,
      'community_name': post.communityName,
      'content': post.content,
      'image_url': post.imageUrl,
      'like_count': post.likeCount,
      'comment_count': post.commentCount,
      'created_at': post.createdAt.toIso8601String(),
      'is_liked_by_user': post.isLikedByUser,
      'recent_comments': post.recentComments.map((c) => _commentToJson(c)).toList(),
    };
  }

  Map<String, dynamic> _commentToJson(Comment comment) {
    return {
      'id': comment.id,
      'author': {
        'id': comment.author.id,
        'display_name': comment.author.displayName,
        'handle': comment.author.handle,
        'avatar_seed': comment.author.avatarSeed,
        'is_ai_labeled': comment.author.isAiLabeled,
        'ai_label_text': comment.author.aiLabelText,
      },
      'content': comment.content,
      'like_count': comment.likeCount,
      'created_at': comment.createdAt.toIso8601String(),
      'reply_count': comment.replyCount,
    };
  }

  Map<String, dynamic> _conversationToJson(Conversation conversation) {
    return {
      'conversation_id': conversation.conversationId,
      'other_user': {
        'id': conversation.otherUser.id,
        'display_name': conversation.otherUser.displayName,
        'handle': conversation.otherUser.handle,
        'avatar_seed': conversation.otherUser.avatarSeed,
        'is_ai_labeled': conversation.otherUser.isAiLabeled,
        'ai_label_text': conversation.otherUser.aiLabelText,
      },
      'last_message': conversation.lastMessage,
      'last_message_time': conversation.lastMessageTime.toIso8601String(),
      'unread_count': conversation.unreadCount,
    };
  }

  Map<String, dynamic> _communityToJson(Community community) {
    return {
      'id': community.id,
      'name': community.name,
      'description': community.description,
      'theme': community.theme,
      'tone': community.tone,
      'bot_count': community.botCount,
      'activity_level': community.activityLevel,
    };
  }

  Map<String, dynamic> _chatMessageToJson(ChatMessage message) {
    return {
      'id': message.id,
      'community_id': message.communityId,
      'author': {
        'id': message.author.id,
        'display_name': message.author.displayName,
        'handle': message.author.handle,
        'avatar_seed': message.author.avatarSeed,
        'is_ai_labeled': message.author.isAiLabeled,
        'ai_label_text': message.author.aiLabelText,
      },
      'content': message.content,
      'reply_to_id': message.replyToId,
      'reply_to_content': message.replyToContent,
      'created_at': message.createdAt.toIso8601String(),
      'is_bot': !message.isFromUser,
    };
  }

  Map<String, dynamic> _directMessageToJson(DirectMessage message) {
    return {
      'id': message.id,
      'conversation_id': message.conversationId,
      'sender': {
        'id': message.sender.id,
        'display_name': message.sender.displayName,
        'handle': message.sender.handle,
        'avatar_seed': message.sender.avatarSeed,
        'is_ai_labeled': message.sender.isAiLabeled,
        'ai_label_text': message.sender.aiLabelText,
      },
      'receiver_id': message.receiverId,
      'content': message.content,
      'created_at': message.createdAt.toIso8601String(),
      'is_read': message.isRead,
    };
  }

  /// Dispose resources
  void dispose() {
    _connectivitySubscription?.cancel();
    _onlineStatusController.close();
  }
}
