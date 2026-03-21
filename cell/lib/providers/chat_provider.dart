import 'package:flutter/foundation.dart';
import '../models/models.dart';
import '../models/offline_action.dart';
import '../services/api_service.dart';
import '../services/offline_service.dart';
import '../services/websocket_service.dart';

class ChatProvider extends ChangeNotifier {
  final ApiService _api = ApiService();
  final OfflineService _offlineService = OfflineService.instance;

  // Community chat state
  List<ChatMessage> _chatMessages = [];
  bool _isLoadingChat = false;

  // DM state
  List<Conversation> _conversations = [];
  List<DirectMessage> _directMessages = [];
  String? _selectedConversationId;
  BotProfile? _selectedBot;
  bool _isTyping = false;

  // Community typing state - maps user_id to user_name for currently typing users
  final Map<String, String> _communityTypingUsers = {};

  // Current user ID and online status
  String? _currentUserId;
  bool _isOnline = true;

  // WebSocket service reference (set from AppState)
  WebSocketService? _ws;

  // Selected community for chat
  String? _selectedCommunityId;

  // Getters
  List<ChatMessage> get chatMessages => _chatMessages;
  bool get isLoadingChat => _isLoadingChat;

  List<Conversation> get conversations => _conversations;
  List<DirectMessage> get directMessages => _directMessages;
  BotProfile? get selectedBot => _selectedBot;
  bool get isTyping => _isTyping;
  Map<String, String> get communityTypingUsers => Map.unmodifiable(_communityTypingUsers);

  // Setters
  void setCurrentUserId(String? userId) {
    _currentUserId = userId;
  }

  void setOnlineStatus(bool isOnline) {
    _isOnline = isOnline;
  }

  void setWebSocketService(WebSocketService ws) {
    _ws = ws;
  }

  void setSelectedCommunityId(String? communityId) {
    _selectedCommunityId = communityId;
    _chatMessages = [];
    notifyListeners();
  }

  // Add chat message (for WebSocket updates)
  void addChatMessage(ChatMessage message) {
    if (_selectedCommunityId != null && message.communityId == _selectedCommunityId) {
      _chatMessages.add(message);
      notifyListeners();
    }
  }

  // Add direct message (for WebSocket updates)
  void addDirectMessage(DirectMessage message) {
    if (_selectedConversationId == message.conversationId) {
      _directMessages.add(message);
      notifyListeners();
    }
    // Refresh conversations list
    loadConversations();
  }

  // Update typing indicator (for WebSocket updates)
  void updateTypingIndicator(String botId) {
    _isTyping = botId.isNotEmpty && _selectedBot?.id == botId;
    notifyListeners();
  }

  // Update community typing users (for WebSocket updates)
  void updateCommunityTyping(String communityId, String userId, String userName, bool isTyping) {
    if (communityId != _selectedCommunityId) return;

    if (isTyping) {
      _communityTypingUsers[userId] = userName;
    } else {
      _communityTypingUsers.remove(userId);
    }
    notifyListeners();
  }

  // Clear community typing users when switching communities
  void clearCommunityTyping() {
    _communityTypingUsers.clear();
    notifyListeners();
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
      debugPrint('Failed to load chat: $e');
    } finally {
      _isLoadingChat = false;
      notifyListeners();
    }
  }

  Future<void> sendChatMessage(String content, {String? replyToId}) async {
    if (_currentUserId == null || _selectedCommunityId == null || _ws == null) return;

    if (!_isOnline) {
      // Queue message for later
      await _offlineService.queueAction(
        ActionType.sendMessage,
        {
          'community_id': _selectedCommunityId!,
          'user_id': _currentUserId!,
          'content': content,
          'reply_to_id': replyToId,
        },
      );
      notifyListeners();
      return;
    }

    try {
      // Send via WebSocket for real-time
      _ws!.sendChatMessage(
        _selectedCommunityId!,
        _currentUserId!,
        content,
        replyToId: replyToId,
      );
    } catch (e) {
      debugPrint('Failed to send message: $e');
      notifyListeners();
    }
  }

  // Load cached chat messages for offline mode
  Future<void> loadCachedChatMessages(String communityId) async {
    _chatMessages = await _offlineService.getCachedChatMessages(communityId);
    notifyListeners();
  }

  // ========================================================================
  // DIRECT MESSAGE METHODS
  // ========================================================================

  Future<void> loadConversations() async {
    if (_currentUserId == null) return;

    try {
      _conversations = await _api.getConversations(_currentUserId!);
      notifyListeners();
    } catch (e) {
      debugPrint('Failed to load conversations: $e');
      notifyListeners();
    }
  }

  Future<void> selectBot(BotProfile bot) async {
    _selectedBot = bot;
    _directMessages = [];
    _selectedConversationId = null;
    notifyListeners();

    if (_currentUserId == null) return;

    // Generate conversation ID
    final ids = [_currentUserId!, bot.id]..sort();
    _selectedConversationId = '${ids[0]}_${ids[1]}';

    // Load existing messages
    try {
      _directMessages = await _api.getDirectMessages(
        _selectedConversationId!,
        _currentUserId!,
      );
      notifyListeners();
    } catch (e) {
      // No existing conversation, that's ok
    }
  }

  Future<void> sendDirectMessage(String content) async {
    if (_currentUserId == null || _selectedBot == null || _ws == null) return;

    try {
      // Send user message
      final message = await _api.sendDirectMessage(
        _currentUserId!,
        _selectedBot!.id,
        content,
      );
      _directMessages.add(message);

      // Invalidate DM cache since we have new data
      if (_selectedConversationId != null) {
        await _offlineService.invalidateDMCache(_selectedConversationId!);
      }
      // Also invalidate conversations list cache
      await _offlineService.invalidateConversationsCache(_currentUserId!);

      notifyListeners();

      // Request bot response via WebSocket
      _ws!.sendDm(_selectedBot!.id, _currentUserId!, content);
    } on OfflineException {
      // Queue DM for later
      await _offlineService.queueAction(
        ActionType.sendDm,
        {
          'user_id': _currentUserId!,
          'bot_id': _selectedBot!.id,
          'content': content,
        },
      );
      notifyListeners();
    } catch (e) {
      debugPrint('Failed to send message: $e');
      notifyListeners();
    }
  }

  Future<List<BotProfile>> loadBots({String? communityId, int limit = 50, int offset = 0}) async {
    try {
      return await _api.getBots(communityId: communityId, limit: limit, offset: offset);
    } catch (e) {
      debugPrint('Failed to load bots: $e');
      return [];
    }
  }
}
