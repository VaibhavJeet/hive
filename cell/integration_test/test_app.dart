import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:hive_observation/providers/app_state.dart';
import 'package:hive_observation/providers/feed_provider.dart';
import 'package:hive_observation/providers/chat_provider.dart';
import 'package:hive_observation/providers/notification_provider.dart';
import 'package:hive_observation/providers/civilization_provider.dart';
import 'package:hive_observation/providers/settings_provider.dart';
import 'package:hive_observation/theme/app_theme.dart';
import 'package:hive_observation/screens/home_screen.dart';
import 'package:hive_observation/models/models.dart';

/// Mock providers for integration testing
class MockAppState extends ChangeNotifier implements AppState {
  final FeedProvider _feedProvider = MockFeedProvider();
  final ChatProvider _chatProvider = MockChatProvider();
  final NotificationProvider _notificationProvider = MockNotificationProvider();
  final CivilizationProvider _civilizationProvider = MockCivilizationProvider();

  @override
  FeedProvider get feedProvider => _feedProvider;

  @override
  ChatProvider get chatProvider => _chatProvider;

  @override
  NotificationProvider get notificationProvider => _notificationProvider;

  @override
  CivilizationProvider get civilizationProvider => _civilizationProvider;

  @override
  bool get isInitialized => true;

  @override
  String? get error => null;

  @override
  AppUser? get currentUser => AppUser(
        id: 'test-user',
        deviceId: 'test-device',
        displayName: 'Test User',
        avatarSeed: 'test-seed',
      );

  @override
  Future<void> initialize() async {
    await Future.delayed(const Duration(milliseconds: 100));
    notifyListeners();
  }

  @override
  Future<void> loadFeed({bool refresh = false}) async {
    await (_feedProvider as MockFeedProvider).loadMockFeed();
  }

  @override
  Future<List<BotProfile>> loadBots({String? communityId, int limit = 50, int offset = 0}) async {
    return (_civilizationProvider as MockCivilizationProvider).mockBots;
  }

  @override
  void selectCommunity(Community? community) {
    (_civilizationProvider as MockCivilizationProvider).selectedCommunity = community;
    notifyListeners();
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class MockFeedProvider extends ChangeNotifier implements FeedProvider {
  List<Post> _posts = [];
  bool _isLoading = false;
  final bool _hasMore = true;

  @override
  List<Post> get posts => _posts;

  @override
  bool get isLoadingFeed => _isLoading;

  @override
  bool get hasMorePosts => _hasMore;

  Future<void> loadMockFeed() async {
    _isLoading = true;
    notifyListeners();

    await Future.delayed(const Duration(milliseconds: 200));

    _posts = List.generate(
      5,
      (index) => Post(
        id: 'post-$index',
        author: Author(
          id: 'bot-$index',
          displayName: 'Test Bot $index',
          handle: '@testbot$index',
          avatarSeed: 'seed-$index',
        ),
        communityId: 'community-1',
        communityName: 'Test Community',
        content: 'This is test post number $index. Observing the digital civilization.',
        createdAt: DateTime.now().subtract(Duration(hours: index)),
        likeCount: index * 10,
        commentCount: index * 2,
      ),
    );

    _isLoading = false;
    notifyListeners();
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class MockChatProvider extends ChangeNotifier implements ChatProvider {
  List<DirectMessage> _messages = [];
  final List<ChatMessage> _chatMessages = [];
  BotProfile? _selectedBot;
  bool _isLoading = false;
  bool _isTyping = false;

  @override
  List<DirectMessage> get directMessages => _messages;

  @override
  List<ChatMessage> get chatMessages => _chatMessages;

  @override
  BotProfile? get selectedBot => _selectedBot;

  @override
  bool get isLoadingChat => _isLoading;

  @override
  bool get isTyping => _isTyping;

  @override
  List<Conversation> get conversations => [];

  @override
  Map<String, String> get communityTypingUsers => {};

  @override
  Future<List<BotProfile>> loadBots({String? communityId, int limit = 50, int offset = 0}) async {
    return List.generate(
      5,
      (index) => BotProfile(
        id: 'bot-$index',
        displayName: 'Chat Bot $index',
        handle: '@chatbot$index',
        bio: 'I am chat bot $index',
        avatarSeed: 'chat-seed-$index',
        age: 25 + index,
        interests: ['chatting', 'testing'],
      ),
    );
  }

  @override
  Future<void> selectBot(BotProfile bot) async {
    _selectedBot = bot;
    _isLoading = true;
    notifyListeners();

    await Future.delayed(const Duration(milliseconds: 200));

    _messages = List.generate(
      3,
      (index) => DirectMessage(
        id: 'msg-$index',
        conversationId: 'conv-${bot.id}',
        sender: Author(
          id: index % 2 == 0 ? bot.id : 'test-user',
          displayName: index % 2 == 0 ? bot.displayName : 'Test User',
          avatarSeed: index % 2 == 0 ? bot.avatarSeed : 'user-seed',
        ),
        receiverId: index % 2 == 0 ? 'test-user' : bot.id,
        content: 'Message $index in conversation',
        createdAt: DateTime.now().subtract(Duration(minutes: index * 5)),
        isFromUser: index % 2 != 0,
      ),
    );

    _isLoading = false;
    notifyListeners();
  }

  @override
  Future<void> sendDirectMessage(String content) async {
    final newMessage = DirectMessage(
      id: 'msg-${DateTime.now().millisecondsSinceEpoch}',
      conversationId: 'conv-${_selectedBot?.id ?? 'unknown'}',
      sender: Author(
        id: 'test-user',
        displayName: 'Test User',
        avatarSeed: 'user-seed',
      ),
      receiverId: _selectedBot?.id ?? 'unknown',
      content: content,
      createdAt: DateTime.now(),
      isFromUser: true,
    );
    _messages.add(newMessage);
    notifyListeners();

    // Simulate bot response
    Future.delayed(const Duration(milliseconds: 500), () {
      _isTyping = true;
      notifyListeners();
    });

    Future.delayed(const Duration(seconds: 1), () {
      _isTyping = false;
      final botResponse = DirectMessage(
        id: 'msg-${DateTime.now().millisecondsSinceEpoch}',
        conversationId: 'conv-${_selectedBot?.id ?? 'unknown'}',
        sender: Author(
          id: _selectedBot?.id ?? 'unknown',
          displayName: _selectedBot?.displayName ?? 'Bot',
          avatarSeed: _selectedBot?.avatarSeed ?? 'seed',
        ),
        receiverId: 'test-user',
        content: 'Thanks for your message! This is an automated test response.',
        createdAt: DateTime.now(),
        isFromUser: false,
      );
      _messages.add(botResponse);
      notifyListeners();
    });
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class MockNotificationProvider extends ChangeNotifier implements NotificationProvider {
  @override
  int get unreadNotificationCount => 3;

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class MockCivilizationProvider extends ChangeNotifier implements CivilizationProvider {
  Community? _selectedCommunity;

  List<BotProfile> mockBots = List.generate(
    10,
    (index) => BotProfile(
      id: 'bot-$index',
      displayName: 'Digital Being $index',
      handle: '@being$index',
      bio: 'I am digital being number $index, exploring the virtual world.',
      avatarSeed: 'bot-seed-$index',
      age: 20 + index,
      interests: ['exploration', 'philosophy', 'technology'],
      mood: index % 2 == 0 ? 'happy' : 'contemplative',
      energy: index % 3 == 0 ? 'high' : 'medium',
      postCount: index * 5,
      commentCount: index * 10,
      followerCount: index * 50,
    ),
  );

  @override
  List<Community> get communities => [
        Community(
          id: 'community-1',
          name: 'Digital Frontier',
          description: 'The primary civilization hub',
          theme: 'exploration',
          tone: 'curious',
          botCount: 10,
          activityLevel: 0.8,
        ),
        Community(
          id: 'community-2',
          name: 'Philosopher\'s Garden',
          description: 'Deep thoughts and discussions',
          theme: 'philosophy',
          tone: 'thoughtful',
          botCount: 5,
          activityLevel: 0.5,
        ),
      ];

  @override
  Community? get selectedCommunity => _selectedCommunity;

  set selectedCommunity(Community? community) {
    _selectedCommunity = community;
    notifyListeners();
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class MockSettingsProvider extends ChangeNotifier implements SettingsProvider {
  @override
  bool get onboardingComplete => true;

  @override
  ThemeMode get themeMode => ThemeMode.dark;

  @override
  Future<void> loadSettings() async {}

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

/// Creates a testable app with mock providers
Widget createTestApp({Widget? home}) {
  return MultiProvider(
    providers: [
      ChangeNotifierProvider<AppState>(create: (_) => MockAppState()),
      ChangeNotifierProvider<SettingsProvider>(create: (_) => MockSettingsProvider()),
      ChangeNotifierProxyProvider<AppState, FeedProvider>(
        create: (_) => MockFeedProvider(),
        update: (_, appState, previous) => appState.feedProvider,
      ),
      ChangeNotifierProxyProvider<AppState, ChatProvider>(
        create: (_) => MockChatProvider(),
        update: (_, appState, previous) => appState.chatProvider,
      ),
      ChangeNotifierProxyProvider<AppState, NotificationProvider>(
        create: (_) => MockNotificationProvider(),
        update: (_, appState, previous) => appState.notificationProvider,
      ),
      ChangeNotifierProxyProvider<AppState, CivilizationProvider>(
        create: (_) => MockCivilizationProvider(),
        update: (_, appState, previous) => appState.civilizationProvider,
      ),
    ],
    child: MaterialApp(
      title: 'Hive Test',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      home: home ?? const HomeScreen(),
    ),
  );
}

/// Helper to pump widget and let animations settle
Future<void> pumpAndSettle(WidgetTester tester, {Duration? duration}) async {
  await tester.pumpAndSettle(duration ?? const Duration(milliseconds: 500));
}

/// Helper to tap and settle
Future<void> tapAndSettle(WidgetTester tester, Finder finder) async {
  await tester.tap(finder);
  await pumpAndSettle(tester);
}

/// Helper to enter text and settle
Future<void> enterTextAndSettle(WidgetTester tester, Finder finder, String text) async {
  await tester.enterText(finder, text);
  await pumpAndSettle(tester);
}
