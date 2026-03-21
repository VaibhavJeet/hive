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

  // Queue storage keys
  static const String _queueKey = 'offline_action_queue';
  static const String _deadLetterQueueKey = 'offline_dead_letter_queue';

  // Retry configuration
  static const int _maxRetryAttempts = 3;
  static const Duration _baseRetryDelay = Duration(seconds: 1);
  static const double _backoffMultiplier = 2.0;

  // Connectivity stream
  StreamSubscription<List<ConnectivityResult>>? _connectivitySubscription;
  final StreamController<bool> _onlineStatusController = StreamController<bool>.broadcast();

  // Action queue
  List<OfflineAction> _actionQueue = [];
  List<OfflineAction> _deadLetterQueue = [];
  bool _isProcessingQueue = false;

  // Callbacks
  Function(OfflineAction action)? onActionProcessed;
  Function(OfflineAction action, String error)? onActionFailed;
  Function(OfflineAction action)? onActionMovedToDeadLetter;

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

    // Load persisted queues
    await _loadQueue();
    await _loadDeadLetterQueue();

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

  /// Get dead letter queue count
  int get deadLetterQueueCount => _deadLetterQueue.length;

  /// Get all dead letter queue actions
  List<OfflineAction> get deadLetterQueueActions => List.unmodifiable(_deadLetterQueue);

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
  // CACHE INVALIDATION METHODS
  // ========================================================================

  /// Invalidate feed cache (call after creating/deleting posts)
  Future<int> invalidateFeedCache({String? communityId}) async {
    await _ensureInitialized();
    if (communityId != null) {
      await _cache.removeCachedData('feed_$communityId');
      return 1;
    }
    return await _cache.invalidateAllFeeds();
  }

  /// Invalidate chat cache for a community
  Future<bool> invalidateChatCache(String communityId) async {
    await _ensureInitialized();
    return await _cache.removeCachedData('chat_$communityId');
  }

  /// Invalidate DM cache for a conversation
  Future<bool> invalidateDMCache(String conversationId) async {
    await _ensureInitialized();
    return await _cache.removeCachedData('dm_$conversationId');
  }

  /// Invalidate conversations cache for a user
  Future<bool> invalidateConversationsCache(String userId) async {
    await _ensureInitialized();
    return await _cache.removeCachedData('conversations_$userId');
  }

  /// Invalidate communities cache
  Future<bool> invalidateCommunitiesCache() async {
    await _ensureInitialized();
    return await _cache.removeCachedData('communities');
  }

  /// Clear all expired cache entries
  Future<int> clearExpiredCache() async {
    await _ensureInitialized();
    return await _cache.clearExpiredCache();
  }

  /// Get remaining TTL for a cached item
  Future<Duration?> getCacheRemainingTtl(String key) async {
    await _ensureInitialized();
    return await _cache.getRemainingTtl(key);
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

  /// Calculate exponential backoff delay for retry attempts
  Duration _calculateBackoffDelay(int retryCount) {
    // Exponential backoff: baseDelay * (multiplier ^ retryCount)
    // e.g., 1s, 2s, 4s for retries 0, 1, 2
    final delayMs = _baseRetryDelay.inMilliseconds *
        (1 << retryCount); // Using bit shift for power of 2 (equivalent to multiplier of 2)
    return Duration(milliseconds: delayMs);
  }

  /// Process queued actions with exponential backoff retry logic
  Future<void> processQueue() async {
    if (_isProcessingQueue || _actionQueue.isEmpty || !_isOnline) return;

    _isProcessingQueue = true;
    debugPrint('OfflineService: Processing ${_actionQueue.length} queued actions');

    final actionsToProcess = List<OfflineAction>.from(_actionQueue);

    for (final action in actionsToProcess) {
      // Check if we're still online before processing each action
      if (!_isOnline) {
        debugPrint('OfflineService: Went offline during processing, stopping');
        break;
      }

      final success = await _processActionWithRetry(action);

      if (success) {
        _actionQueue.removeWhere((a) => a.id == action.id);
        onActionProcessed?.call(action);
        debugPrint('OfflineService: Processed action ${action.id}');
      } else if (action.retryCount >= _maxRetryAttempts) {
        // Move to dead letter queue after max retries exceeded
        await _moveToDeadLetterQueue(action);
      }
      // If not successful and retries not exceeded, action stays in queue for next processing cycle
    }

    await _saveQueue();
    _isProcessingQueue = false;
  }

  /// Process a single action with retry logic and exponential backoff
  Future<bool> _processActionWithRetry(OfflineAction action) async {
    while (action.retryCount < _maxRetryAttempts) {
      try {
        await _processAction(action);
        return true; // Success
      } catch (e) {
        action.incrementRetry();
        action.errorMessage = e.toString();

        debugPrint(
          'OfflineService: Action ${action.id} failed (attempt ${action.retryCount}/$_maxRetryAttempts): $e',
        );

        if (action.retryCount >= _maxRetryAttempts) {
          // Max retries exceeded
          onActionFailed?.call(action, 'Max retries exceeded: ${action.errorMessage}');
          debugPrint('OfflineService: Action ${action.id} failed permanently after $_maxRetryAttempts attempts');
          return false;
        }

        // Check if still online before waiting for retry
        if (!_isOnline) {
          debugPrint('OfflineService: Went offline, will retry action ${action.id} later');
          return false;
        }

        // Apply exponential backoff delay before next retry
        final delay = _calculateBackoffDelay(action.retryCount - 1);
        debugPrint('OfflineService: Waiting ${delay.inMilliseconds}ms before retry ${action.retryCount}');
        await Future.delayed(delay);

        // Check connectivity again after delay
        if (!_isOnline) {
          debugPrint('OfflineService: Went offline during backoff, will retry action ${action.id} later');
          return false;
        }
      }
    }
    return false;
  }

  /// Move a failed action to the dead letter queue
  Future<void> _moveToDeadLetterQueue(OfflineAction action) async {
    _actionQueue.removeWhere((a) => a.id == action.id);
    _deadLetterQueue.add(action);
    await _saveDeadLetterQueue();
    onActionMovedToDeadLetter?.call(action);
    debugPrint('OfflineService: Moved action ${action.id} to dead letter queue');
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

  /// Save dead letter queue to persistent storage
  Future<void> _saveDeadLetterQueue() async {
    final jsonList = _deadLetterQueue.map((a) => a.toJson()).toList();
    await _prefs!.setString(_deadLetterQueueKey, jsonEncode(jsonList));
  }

  /// Load dead letter queue from persistent storage
  Future<void> _loadDeadLetterQueue() async {
    final jsonStr = _prefs!.getString(_deadLetterQueueKey);
    if (jsonStr == null) {
      _deadLetterQueue = [];
      return;
    }

    try {
      final List<dynamic> jsonList = jsonDecode(jsonStr);
      _deadLetterQueue = jsonList
          .map((json) => OfflineAction.fromJson(json as Map<String, dynamic>))
          .toList();
      debugPrint('OfflineService: Loaded ${_deadLetterQueue.length} dead letter queue actions');
    } catch (e) {
      debugPrint('OfflineService: Failed to load dead letter queue: $e');
      _deadLetterQueue = [];
    }
  }

  /// Retry an action from the dead letter queue
  Future<bool> retryDeadLetterAction(String actionId) async {
    await _ensureInitialized();
    final actionIndex = _deadLetterQueue.indexWhere((a) => a.id == actionId);
    if (actionIndex == -1) return false;

    final action = _deadLetterQueue[actionIndex];
    // Reset retry count to allow fresh retries
    action.retryCount = 0;
    action.errorMessage = null;

    // Move back to main queue
    _deadLetterQueue.removeAt(actionIndex);
    _actionQueue.add(action);

    await _saveQueue();
    await _saveDeadLetterQueue();

    debugPrint('OfflineService: Moved action ${action.id} from dead letter queue back to main queue');

    // Try to process immediately if online
    if (_isOnline) {
      processQueue();
    }

    return true;
  }

  /// Remove an action from the dead letter queue permanently
  Future<bool> removeDeadLetterAction(String actionId) async {
    await _ensureInitialized();
    final initialLength = _deadLetterQueue.length;
    _deadLetterQueue.removeWhere((a) => a.id == actionId);

    if (_deadLetterQueue.length != initialLength) {
      await _saveDeadLetterQueue();
      return true;
    }
    return false;
  }

  /// Clear all actions from the dead letter queue
  Future<void> clearDeadLetterQueue() async {
    await _ensureInitialized();
    _deadLetterQueue.clear();
    await _saveDeadLetterQueue();
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
