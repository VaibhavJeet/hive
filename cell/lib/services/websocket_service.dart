import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart' show debugPrint;
import 'package:web_socket_channel/web_socket_channel.dart';
import '../config/config.dart';
import '../models/models.dart';
import 'offline_service.dart';

typedef EventCallback = void Function(Map<String, dynamic> data);

class WebSocketService {
  /// Get the WebSocket URL from environment configuration
  static String get wsUrl => EnvConfig.wsBaseUrl;

  WebSocketChannel? _channel;
  final String clientId;
  bool _isConnected = false;
  Timer? _reconnectTimer;
  Timer? _pingTimer;
  StreamSubscription<bool>? _offlineSubscription;
  final OfflineService _offlineService = OfflineService.instance;

  // Reconnection with exponential backoff
  int _reconnectAttempts = 0;
  static const int _maxReconnectAttempts = 10;
  static const int _baseReconnectDelay = 1; // seconds

  // Connection state stream for UI feedback
  final StreamController<bool> _connectionStateController = StreamController<bool>.broadcast();

  // Event callbacks
  final Map<String, List<EventCallback>> _eventHandlers = {};

  // Stream controllers for different event types
  final StreamController<Post> _newPostController = StreamController<Post>.broadcast();
  final StreamController<Map<String, dynamic>> _postLikedController = StreamController<Map<String, dynamic>>.broadcast();
  final StreamController<Comment> _newCommentController = StreamController<Comment>.broadcast();
  final StreamController<ChatMessage> _newChatMessageController = StreamController<ChatMessage>.broadcast();
  final StreamController<DirectMessage> _newDmController = StreamController<DirectMessage>.broadcast();
  final StreamController<String> _typingController = StreamController<String>.broadcast();
  final StreamController<Map<String, dynamic>> _communityTypingController = StreamController<Map<String, dynamic>>.broadcast();

  // Expose streams
  Stream<Post> get onNewPost => _newPostController.stream;
  Stream<Map<String, dynamic>> get onPostLiked => _postLikedController.stream;
  Stream<Comment> get onNewComment => _newCommentController.stream;
  Stream<ChatMessage> get onNewChatMessage => _newChatMessageController.stream;
  Stream<DirectMessage> get onNewDm => _newDmController.stream;
  Stream<String> get onTyping => _typingController.stream;
  Stream<Map<String, dynamic>> get onCommunityTyping => _communityTypingController.stream;

  bool get isConnected => _isConnected;
  Stream<bool> get connectionState => _connectionStateController.stream;

  WebSocketService({required this.clientId}) {
    // Listen for connectivity changes to auto-reconnect when back online
    _offlineSubscription = _offlineService.onlineStatusStream.listen((isOnline) {
      if (isOnline && !_isConnected) {
        debugPrint('WebSocket: Back online, attempting to reconnect...');
        forceReconnect();
      } else if (!isOnline && _isConnected) {
        debugPrint('WebSocket: Going offline, pausing reconnection attempts');
        _reconnectTimer?.cancel();
      }
    });
  }

  Future<void> connect() async {
    if (_isConnected) return;

    // Don't try to connect if offline
    if (!_offlineService.isOnline) {
      debugPrint('WebSocket: Offline, skipping connection attempt');
      _connectionStateController.add(false);
      return;
    }

    try {
      _channel = WebSocketChannel.connect(Uri.parse('$wsUrl/$clientId'));

      _channel!.stream.listen(
        _handleMessage,
        onError: _handleError,
        onDone: _handleDone,
      );

      _isConnected = true;
      _reconnectAttempts = 0; // Reset on successful connection
      _connectionStateController.add(true);
      _startPingTimer();

      debugPrint('WebSocket connected');
    } catch (e) {
      debugPrint('WebSocket connection error: $e');
      _connectionStateController.add(false);
      _scheduleReconnect();
    }
  }

  void _handleMessage(dynamic message) {
    try {
      final data = jsonDecode(message as String);
      final eventType = data['type'] as String?;

      if (eventType == null) return;

      // Handle pong
      if (eventType == 'pong') return;

      // Get event data
      final eventData = data['data'] as Map<String, dynamic>? ?? data;

      // Route to appropriate handler
      switch (eventType) {
        case 'new_post':
          _handleNewPost(eventData);
          break;
        case 'post_liked':
          _handlePostLiked(eventData);
          break;
        case 'new_comment':
          _handleNewComment(eventData);
          break;
        case 'new_chat_message':
          _handleNewChatMessage(eventData);
          break;
        case 'new_dm':
          _handleNewDm(eventData);
          break;
        case 'typing_start':
          _typingController.add(eventData['bot_id'] ?? '');
          break;
        case 'typing_stop':
          _typingController.add('');
          break;
        case 'community_typing_start':
          _communityTypingController.add({
            'community_id': eventData['community_id'] ?? '',
            'user_id': eventData['user_id'] ?? '',
            'user_name': eventData['user_name'] ?? '',
            'is_typing': true,
          });
          break;
        case 'community_typing_stop':
          _communityTypingController.add({
            'community_id': eventData['community_id'] ?? '',
            'user_id': eventData['user_id'] ?? '',
            'user_name': eventData['user_name'] ?? '',
            'is_typing': false,
          });
          break;
        default:
          // Call registered handlers
          _eventHandlers[eventType]?.forEach((handler) => handler(eventData));
      }
    } catch (e) {
      debugPrint('Error handling WebSocket message: $e');
    }
  }

  void _handleNewPost(Map<String, dynamic> data) {
    final post = Post(
      id: data['post_id'] ?? '',
      author: Author(
        id: data['author_id'] ?? '',
        displayName: data['author_name'] ?? 'Unknown',
        handle: data['author_handle'] ?? '',
        avatarSeed: data['avatar_seed'] ?? '',
      ),
      communityId: data['community_id'] ?? '',
      communityName: data['community_name'] ?? '',
      content: data['content'] ?? '',
      createdAt: DateTime.now(),
    );
    _newPostController.add(post);
  }

  void _handlePostLiked(Map<String, dynamic> data) {
    _postLikedController.add({
      'post_id': data['post_id'],
      'liker_id': data['liker_id'],
      'liker_name': data['liker_name'],
      'like_count': data['like_count'],
    });
  }

  void _handleNewComment(Map<String, dynamic> data) {
    final comment = Comment(
      id: data['comment_id'] ?? '',
      author: Author(
        id: data['author_id'] ?? '',
        displayName: data['author_name'] ?? 'Unknown',
        avatarSeed: data['avatar_seed'] ?? '',
      ),
      content: data['content'] ?? '',
      createdAt: DateTime.now(),
    );
    _newCommentController.add(comment);
  }

  void _handleNewChatMessage(Map<String, dynamic> data) {
    final message = ChatMessage(
      id: data['message_id'] ?? '',
      communityId: data['community_id'] ?? '',
      author: Author(
        id: data['author_id'] ?? '',
        displayName: data['author_name'] ?? 'Unknown',
        avatarSeed: data['avatar_seed'] ?? '',
        isAiLabeled: data['is_bot'] ?? true,
      ),
      content: data['content'] ?? '',
      createdAt: DateTime.now(),
      isFromUser: !(data['is_bot'] ?? true),
    );
    _newChatMessageController.add(message);
  }

  void _handleNewDm(Map<String, dynamic> data) {
    final message = DirectMessage(
      id: data['message_id'] ?? '',
      conversationId: data['conversation_id'] ?? '',
      sender: Author(
        id: data['sender_id'] ?? '',
        displayName: data['sender_name'] ?? 'Unknown',
        avatarSeed: data['avatar_seed'] ?? '',
      ),
      receiverId: data['receiver_id'] ?? '',
      content: data['content'] ?? '',
      createdAt: DateTime.now(),
      isFromUser: false,
    );
    _newDmController.add(message);
  }

  void _handleError(dynamic error) {
    debugPrint('WebSocket error: $error');
    _isConnected = false;
    _connectionStateController.add(false);
    _scheduleReconnect();
  }

  void _handleDone() {
    debugPrint('WebSocket connection closed');
    _isConnected = false;
    _connectionStateController.add(false);
    _scheduleReconnect();
  }

  /// Reset reconnection attempts and try to connect immediately
  void forceReconnect() {
    _reconnectAttempts = 0;
    disconnect();
    connect();
  }

  void _scheduleReconnect() {
    _reconnectTimer?.cancel();

    // Don't try to reconnect if offline
    if (!_offlineService.isOnline) {
      debugPrint('WebSocket: Offline, waiting for connectivity to reconnect');
      return;
    }

    // Check if we've exceeded max attempts
    if (_reconnectAttempts >= _maxReconnectAttempts) {
      debugPrint('Max reconnect attempts reached. Giving up.');
      _connectionStateController.add(false);
      return;
    }

    // Exponential backoff: 1s, 2s, 4s, 8s, ... up to 30s max
    final delay = (_baseReconnectDelay * (1 << _reconnectAttempts)).clamp(1, 30);
    _reconnectAttempts++;

    debugPrint('Attempting to reconnect WebSocket in ${delay}s (attempt $_reconnectAttempts/$_maxReconnectAttempts)...');

    _reconnectTimer = Timer(Duration(seconds: delay), () {
      connect();
    });
  }

  void _startPingTimer() {
    _pingTimer?.cancel();
    _pingTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      if (_isConnected) {
        send({'type': 'ping'});
      }
    });
  }

  void send(Map<String, dynamic> data) {
    if (_channel != null && _isConnected) {
      _channel!.sink.add(jsonEncode(data));
    }
  }

  void sendDm(String botId, String userId, String content) {
    send({
      'type': 'dm',
      'bot_id': botId,
      'user_id': userId,
      'content': content,
    });
  }

  void sendChatMessage(String communityId, String userId, String content, {String? replyToId}) {
    send({
      'type': 'chat',
      'community_id': communityId,
      'user_id': userId,
      'content': content,
      'reply_to_id': replyToId,
    });
  }

  /// Send typing start event for DM conversations
  void sendTypingStart(String recipientId) {
    send({
      'type': 'typing_start',
      'recipient_id': recipientId,
    });
  }

  /// Send typing stop event for DM conversations
  void sendTypingStop(String recipientId) {
    send({
      'type': 'typing_stop',
      'recipient_id': recipientId,
    });
  }

  /// Send typing start event for community chat
  void sendCommunityTypingStart(String communityId, String userId) {
    send({
      'type': 'community_typing_start',
      'community_id': communityId,
      'user_id': userId,
    });
  }

  /// Send typing stop event for community chat
  void sendCommunityTypingStop(String communityId, String userId) {
    send({
      'type': 'community_typing_stop',
      'community_id': communityId,
      'user_id': userId,
    });
  }

  void subscribeToCommunity(String communityId) {
    send({
      'type': 'subscribe',
      'community_id': communityId,
    });
  }

  void on(String event, EventCallback callback) {
    _eventHandlers.putIfAbsent(event, () => []).add(callback);
  }

  void off(String event, EventCallback callback) {
    _eventHandlers[event]?.remove(callback);
  }

  void disconnect() {
    _pingTimer?.cancel();
    _reconnectTimer?.cancel();
    _channel?.sink.close();
    _isConnected = false;
  }

  void dispose() {
    disconnect();
    _offlineSubscription?.cancel();
    _newPostController.close();
    _postLikedController.close();
    _newCommentController.close();
    _newChatMessageController.close();
    _newDmController.close();
    _typingController.close();
    _communityTypingController.close();
    _connectionStateController.close();
  }
}
