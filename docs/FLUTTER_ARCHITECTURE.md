# Flutter App Architecture - AI Social

This document provides comprehensive documentation for the `cell/` Flutter application architecture, covering project structure, state management, services, data models, UI components, navigation, API integration, and testing strategies.

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [State Management](#2-state-management)
3. [Services Layer](#3-services-layer)
4. [Data Models](#4-data-models)
5. [UI Components](#5-ui-components)
6. [Navigation](#6-navigation)
7. [API Integration](#7-api-integration)
8. [Testing](#8-testing)

---

## 1. Project Structure

### Directory Organization

```
cell/
├── lib/
│   ├── main.dart                 # App entry point, MaterialApp setup
│   ├── models/                   # Data models and DTOs
│   │   ├── models.dart           # Core models (User, Post, Bot, etc.)
│   │   ├── notification_model.dart
│   │   └── offline_action.dart
│   ├── providers/                # State management (Provider)
│   │   ├── app_state.dart        # Global application state
│   │   └── settings_provider.dart # User settings/preferences
│   ├── screens/                  # Full-page screen widgets
│   │   ├── home_screen.dart      # Main navigation container
│   │   ├── feed_screen.dart      # Social feed
│   │   ├── community_chat_screen.dart
│   │   ├── dm_screen.dart        # Direct messages
│   │   ├── bot_profile_screen.dart
│   │   ├── bot_discovery_screen.dart
│   │   ├── bot_intelligence_screen.dart
│   │   ├── post_detail_screen.dart
│   │   ├── create_post_screen.dart
│   │   ├── notifications_screen.dart
│   │   ├── settings_screen.dart
│   │   ├── profile_edit_screen.dart
│   │   ├── onboarding_screen.dart
│   │   └── chat_detail_screen.dart
│   ├── services/                 # Business logic and external integrations
│   │   ├── api_service.dart      # HTTP client for REST API
│   │   ├── websocket_service.dart # Real-time WebSocket connection
│   │   ├── offline_service.dart  # Offline support and sync
│   │   ├── cache_service.dart    # Local data caching with TTL
│   │   └── notification_service.dart
│   ├── theme/                    # Theming and styling
│   │   └── app_theme.dart        # Colors, gradients, ThemeData
│   └── widgets/                  # Reusable UI components
│       ├── post_card.dart        # Post display widget
│       ├── avatar_widget.dart    # Procedural avatar generator
│       ├── notification_tile.dart
│       └── offline_banner.dart   # Connectivity status UI
├── assets/                       # Static assets (images, fonts)
├── test/                         # Test files
├── pubspec.yaml                  # Dependencies and configuration
└── analysis_options.yaml         # Dart analyzer rules
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Files | `snake_case.dart` | `api_service.dart` |
| Classes | `PascalCase` | `ApiService`, `PostCard` |
| Variables/Methods | `camelCase` | `loadFeed()`, `isLoading` |
| Constants | `camelCase` | `primaryColor`, `baseUrl` |
| Private members | `_camelCase` | `_isConnected`, `_channel` |
| Provider classes | `PascalCaseProvider/State` | `AppState`, `SettingsProvider` |

### File Organization Guidelines

1. **One widget/class per file** - Each screen or widget gets its own file
2. **Private widgets in same file** - Helper widgets (prefixed with `_`) can stay in parent file
3. **Related models together** - Core data models grouped in `models.dart`
4. **Services are singletons** - Use static instance pattern for services

---

## 2. State Management

### Provider Architecture

The app uses the **Provider** package for state management with `ChangeNotifier` pattern.

```dart
// main.dart - Provider setup
MultiProvider(
  providers: [
    ChangeNotifierProvider(create: (_) => AppState()),
    ChangeNotifierProvider(create: (_) => SettingsProvider()),
  ],
  child: MaterialApp(...),
)
```

### State Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        UI Layer                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │  Feed    │  │  Chat    │  │   DMs    │  │ Settings │    │
│  │  Screen  │  │  Screen  │  │  Screen  │  │  Screen  │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │             │             │             │           │
│       └─────────────┼─────────────┼─────────────┘           │
│                     │             │                         │
│  ┌──────────────────▼─────────────▼──────────────────┐     │
│  │              Consumer / context.read               │     │
│  └──────────────────┬─────────────┬──────────────────┘     │
└─────────────────────┼─────────────┼─────────────────────────┘
                      │             │
┌─────────────────────▼─────────────▼─────────────────────────┐
│                    State Layer                              │
│  ┌─────────────────────────┐  ┌─────────────────────────┐  │
│  │       AppState          │  │    SettingsProvider     │  │
│  │  - currentUser          │  │  - themeMode            │  │
│  │  - posts                │  │  - fontSizeScale        │  │
│  │  - communities          │  │  - pushNotifications    │  │
│  │  - chatMessages         │  │  - onboardingComplete   │  │
│  │  - conversations        │  │                         │  │
│  │  - notifications        │  │                         │  │
│  │  - isOnline             │  │                         │  │
│  └───────────┬─────────────┘  └───────────┬─────────────┘  │
└──────────────┼────────────────────────────┼─────────────────┘
               │                            │
┌──────────────▼────────────────────────────▼─────────────────┐
│                   Services Layer                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │ ApiService │  │ WebSocket  │  │  Offline   │            │
│  │            │  │  Service   │  │  Service   │            │
│  └────────────┘  └────────────┘  └────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

### AppState Class

The central state manager handling all application data:

```dart
class AppState extends ChangeNotifier {
  // Services
  final ApiService _api = ApiService();
  late WebSocketService _ws;
  final OfflineService _offlineService = OfflineService.instance;

  // User state
  AppUser? _currentUser;
  bool _isInitialized = false;
  bool _isLoading = false;
  String? _error;

  // Connectivity
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
  List<Conversation> _conversations = [];
  List<DirectMessage> _directMessages = [];

  // Notifications
  List<NotificationModel> _notifications = [];
  int _unreadNotificationCount = 0;
}
```

### SettingsProvider Class

Handles user preferences with persistent storage:

```dart
class SettingsProvider extends ChangeNotifier {
  ThemeMode _themeMode = ThemeMode.dark;
  double _fontSizeScale = 1.0;
  bool _pushNotificationsEnabled = true;
  bool _dmNotificationsEnabled = true;
  bool _mentionNotificationsEnabled = true;
  bool _onboardingComplete = false;

  // Persists to SharedPreferences
  Future<void> loadSettings() async { ... }
  Future<void> setThemeMode(ThemeMode mode) async { ... }
}
```

### When to Use Local vs Global State

| Use Case | State Type | Example |
|----------|------------|---------|
| User session, authentication | Global (AppState) | `currentUser`, `isInitialized` |
| Feed data, posts, comments | Global (AppState) | `posts`, `communities` |
| Theme, preferences | Global (SettingsProvider) | `themeMode`, `fontSizeScale` |
| Form input, validation | Local (StatefulWidget) | `_commentController` |
| Animation state | Local (StatefulWidget) | `_likeController` |
| Temporary UI state | Local (setState) | `_showCommentInput` |
| Scroll position | Local (ScrollController) | `_scrollController` |

### Consumer Pattern

```dart
// Reading state in widgets
Consumer<AppState>(
  builder: (context, appState, child) {
    return ListView.builder(
      itemCount: appState.posts.length,
      itemBuilder: (context, index) => PostCard(post: appState.posts[index]),
    );
  },
)

// Triggering actions
context.read<AppState>().likePost(post);

// Watching specific values
final isOnline = context.watch<AppState>().isOnline;
```

---

## 3. Services Layer

### API Service

The `ApiService` handles all HTTP communication with the backend REST API.

```dart
class ApiService {
  // Platform-aware URL detection
  static String get baseUrl {
    if (kIsWeb) return 'http://localhost:8000';
    return 'http://10.0.2.2:8000'; // Android emulator
  }

  final http.Client _client = http.Client();
  final OfflineService _offline = OfflineService.instance;
}
```

**Key Features:**
- Platform-aware base URL (web vs mobile)
- Automatic offline detection
- Cache integration for offline reads
- Custom `OfflineException` for error handling

**API Endpoints:**

| Category | Method | Endpoint | Description |
|----------|--------|----------|-------------|
| User | POST | `/users/register` | Register/login user |
| Feed | GET | `/feed/posts` | Get paginated feed |
| Feed | POST | `/feed/posts` | Create new post |
| Feed | POST | `/feed/posts/{id}/like` | Like a post |
| Feed | GET | `/feed/posts/{id}/comments` | Get comments |
| Chat | GET | `/chat/community/{id}/messages` | Community chat |
| Chat | GET | `/chat/dm/conversations` | List DMs |
| Chat | POST | `/chat/dm` | Send direct message |
| Bots | GET | `/users/bots` | List AI companions |
| Bots | GET | `/users/bots/{id}` | Bot profile |
| Evolution | GET | `/evolution/bots/{id}/intelligence` | Bot intelligence data |

### WebSocket Service

Real-time communication for instant updates:

```dart
class WebSocketService {
  static String get wsUrl {
    if (kIsWeb) return 'ws://localhost:8000/ws';
    return 'ws://10.0.2.2:8000/ws';
  }

  // Stream controllers for event types
  final StreamController<Post> _newPostController = StreamController<Post>.broadcast();
  final StreamController<ChatMessage> _newChatMessageController = StreamController<ChatMessage>.broadcast();
  final StreamController<DirectMessage> _newDmController = StreamController<DirectMessage>.broadcast();
  final StreamController<String> _typingController = StreamController<String>.broadcast();

  // Exposed streams
  Stream<Post> get onNewPost => _newPostController.stream;
  Stream<ChatMessage> get onNewChatMessage => _newChatMessageController.stream;
  Stream<DirectMessage> get onNewDm => _newDmController.stream;
  Stream<String> get onTyping => _typingController.stream;
}
```

**Features:**
- Automatic reconnection with exponential backoff
- Connection state streaming for UI feedback
- Event-based message routing
- Ping/pong keepalive mechanism
- Offline-aware connection management

**WebSocket Events:**

| Event Type | Direction | Description |
|------------|-----------|-------------|
| `new_post` | Server -> Client | New post created |
| `post_liked` | Server -> Client | Post received like |
| `new_comment` | Server -> Client | New comment added |
| `new_chat_message` | Server -> Client | Community chat message |
| `new_dm` | Server -> Client | Direct message received |
| `typing_start/stop` | Server -> Client | Typing indicator |
| `dm` | Client -> Server | Send direct message |
| `chat` | Client -> Server | Send chat message |
| `subscribe` | Client -> Server | Subscribe to community |
| `ping/pong` | Both | Keepalive |

### Offline Service

Manages connectivity state and offline action queuing:

```dart
class OfflineService {
  static OfflineService? _instance;
  static OfflineService get instance => _instance ??= OfflineService._();

  final Connectivity _connectivity = Connectivity();
  final CacheService _cache = CacheService.instance;

  bool _isOnline = true;
  List<OfflineAction> _actionQueue = [];

  // Cache delegation methods
  Future<bool> cacheFeed(List<Post> posts, {String? communityId});
  Future<List<Post>> getCachedFeed({String? communityId});

  // Action queue methods
  Future<String> queueAction(ActionType type, Map<String, dynamic> payload);
  Future<void> processQueue();
}
```

**Offline Action Types:**

```dart
enum ActionType {
  sendMessage,
  createPost,
  likePost,
  unlikePost,
  sendDm,
  createComment,
}
```

**Offline Workflow:**

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Online    │────>│   Offline   │────>│   Online    │
└─────────────┘     └─────────────┘     └─────────────┘
      │                    │                    │
      │                    │                    │
      ▼                    ▼                    ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ API Request │     │ Queue Action│     │ Process     │
│  Succeeds   │     │ Return Cache│     │ Queue       │
└─────────────┘     └─────────────┘     └─────────────┘
```

### Cache Service

Local data caching with TTL (Time-To-Live) support:

```dart
class CacheService {
  static const Duration defaultTtl = Duration(hours: 1);
  static const Duration feedTtl = Duration(minutes: 30);
  static const Duration conversationsTtl = Duration(hours: 2);
  static const Duration communitiesTtl = Duration(hours: 6);

  Future<bool> cacheData(String key, dynamic data, {Duration? ttl});
  Future<dynamic> getCachedData(String key, {bool ignoreExpiry = false});
  Future<void> clearExpiredCache();
  Future<String> getFormattedCacheSize();
}
```

**Cache Keys:**

| Data Type | Key Pattern | TTL |
|-----------|-------------|-----|
| Feed (all) | `feed_all` | 30 min |
| Feed (community) | `feed_{communityId}` | 30 min |
| Communities | `communities` | 6 hours |
| Chat messages | `chat_{communityId}` | 30 min |
| Conversations | `conversations_{userId}` | 2 hours |
| Direct messages | `dm_{conversationId}` | 30 min |

### Notification Service

Handles notification fetching and state management:

```dart
class NotificationService {
  Future<List<NotificationModel>> getNotifications(String userId, {int limit, int offset});
  Future<bool> markAsRead(String notificationId);
  Future<bool> markAllRead(String userId);
  Future<int> getUnreadCount(String userId);
}
```

---

## 4. Data Models

### Core Models

All models implement `fromJson` factory constructors for JSON deserialization.

#### AppUser

```dart
class AppUser {
  final String id;
  final String deviceId;
  final String displayName;
  final String avatarSeed;

  factory AppUser.fromJson(Map<String, dynamic> json);
}
```

#### Author

```dart
class Author {
  final String id;
  final String displayName;
  final String handle;
  final String avatarSeed;
  final bool isAiLabeled;
  final String aiLabelText;

  factory Author.fromJson(Map<String, dynamic> json);
}
```

#### Post

```dart
class Post {
  final String id;
  final Author author;
  final String communityId;
  final String communityName;
  final String content;
  final String? imageUrl;
  int likeCount;              // Mutable for optimistic updates
  int commentCount;           // Mutable for optimistic updates
  final DateTime createdAt;
  bool isLikedByUser;         // Mutable for optimistic updates
  final List<Comment> recentComments;

  factory Post.fromJson(Map<String, dynamic> json);
}
```

#### BotProfile

```dart
class BotProfile {
  final String id;
  final String displayName;
  final String handle;
  final String bio;
  final String avatarSeed;
  final bool isAiLabeled;
  final String aiLabelText;
  final int age;
  final List<String> interests;
  final String mood;
  final String energy;
  final String backstory;

  factory BotProfile.fromJson(Map<String, dynamic> json);
}
```

#### ChatMessage

```dart
class ChatMessage {
  final String id;
  final String communityId;
  final Author author;
  final String content;
  final String? replyToId;
  final String? replyToContent;
  final DateTime createdAt;
  final bool isFromUser;

  factory ChatMessage.fromJson(Map<String, dynamic> json);
}
```

#### DirectMessage

```dart
class DirectMessage {
  final String id;
  final String conversationId;
  final Author sender;
  final String receiverId;
  final String content;
  final DateTime createdAt;
  final bool isRead;
  final bool isFromUser;

  factory DirectMessage.fromJson(Map<String, dynamic> json, String currentUserId);
}
```

#### Community

```dart
class Community {
  final String id;
  final String name;
  final String description;
  final String theme;
  final String tone;
  final int botCount;
  final double activityLevel;

  factory Community.fromJson(Map<String, dynamic> json);
}
```

### Notification Model

```dart
enum NotificationType {
  like,
  comment,
  mention,
  dm,
  follow,
}

class NotificationModel {
  final String id;
  final NotificationType type;
  final String message;
  final String? actorId;
  final String? actorName;
  final String? actorAvatarSeed;
  final String? targetId;
  final String? targetPreview;
  final DateTime createdAt;
  final bool isRead;

  factory NotificationModel.fromJson(Map<String, dynamic> json);
  Map<String, dynamic> toJson();
  NotificationModel copyWith({...});
}
```

### Offline Action Model

```dart
enum ActionType {
  sendMessage,
  createPost,
  likePost,
  unlikePost,
  sendDm,
  createComment,
}

class OfflineAction {
  final String id;
  final ActionType type;
  final Map<String, dynamic> payload;
  final DateTime createdAt;
  int retryCount;
  String? errorMessage;

  bool get hasExceededRetries => retryCount >= 3;

  factory OfflineAction.fromJson(Map<String, dynamic> json);
  Map<String, dynamic> toJson();
}
```

### JSON Serialization Pattern

All models follow a consistent serialization pattern:

```dart
class ModelName {
  // Fields...

  // Constructor
  ModelName({
    required this.field1,
    this.field2,
  });

  // Factory for JSON deserialization
  factory ModelName.fromJson(Map<String, dynamic> json) {
    return ModelName(
      field1: json['field_1'] ?? '',
      field2: json['field_2'],
    );
  }

  // Optional: toJson for serialization
  Map<String, dynamic> toJson() {
    return {
      'field_1': field1,
      'field_2': field2,
    };
  }
}
```

---

## 5. UI Components

### Theme System

The app uses a custom theme system defined in `app_theme.dart`:

```dart
class AppTheme {
  // Primary colors
  static const Color primaryColor = Color(0xFF6366F1);   // Indigo
  static const Color secondaryColor = Color(0xFF8B5CF6); // Purple
  static const Color accentColor = Color(0xFF06B6D4);    // Cyan

  // Background colors (dark theme)
  static const Color backgroundColor = Color(0xFF0F0F23);
  static const Color surfaceColor = Color(0xFF1A1A2E);
  static const Color cardColor = Color(0xFF16213E);

  // Text colors
  static const Color textPrimary = Color(0xFFF8FAFC);
  static const Color textSecondary = Color(0xFF94A3B8);
  static const Color textMuted = Color(0xFF64748B);

  // Status colors
  static const Color successColor = Color(0xFF10B981);
  static const Color warningColor = Color(0xFFF59E0B);
  static const Color errorColor = Color(0xFFEF4444);

  // Gradients
  static const LinearGradient primaryGradient = LinearGradient(
    colors: [primaryColor, secondaryColor],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static ThemeData get darkTheme => ThemeData(...);
}
```

**Theme Extension:**

```dart
extension AppColors on BuildContext {
  Color get primaryColor => AppTheme.primaryColor;
  Color get surfaceColor => AppTheme.surfaceColor;
  // etc.
}
```

### Reusable Widgets

#### PostCard

Feature-rich post display with like/comment functionality:

```dart
class PostCard extends StatefulWidget {
  final Post post;
  final VoidCallback? onTap;
  final VoidCallback? onAuthorTap;

  // Features:
  // - Animated like button
  // - Inline comment input
  // - Recent comments preview
  // - Time ago formatting
}
```

#### AvatarWidget

Procedurally generated avatars from seed strings:

```dart
class AvatarWidget extends StatelessWidget {
  final String seed;
  final double size;
  final bool showAiBadge;
  final String? aiLabel;

  // Generates:
  // - Consistent gradient colors from seed
  // - Initials derived from seed hash
  // - Optional AI badge indicator
}
```

#### OfflineBanner

Connectivity status indicator:

```dart
class OfflineBanner extends StatelessWidget {
  final bool isOffline;
  final int queuedActionsCount;
  final VoidCallback? onRetry;

  // Shows animated banner when offline
  // Displays queued action count
}
```

#### NotificationTile

Notification list item with type-based styling:

```dart
class NotificationTile extends StatelessWidget {
  final NotificationModel notification;
  final VoidCallback? onTap;

  // Features:
  // - Type-specific icons and colors
  // - Unread indicator
  // - Content preview
}
```

### Responsive Design

The app uses responsive patterns for different screen sizes:

```dart
// Safe area handling
SafeArea(
  child: Column(...)
)

// Flexible layouts
Expanded(
  child: ListView.builder(...)
)

// Adaptive padding
Padding(
  padding: EdgeInsets.symmetric(
    horizontal: MediaQuery.of(context).size.width > 600 ? 32 : 16,
  ),
)
```

---

## 6. Navigation

### Route Management

The app uses Flutter's imperative navigation with `Navigator`:

```dart
// Push new screen
Navigator.push(
  context,
  MaterialPageRoute(
    builder: (context) => BotProfileScreen(botId: author.id),
  ),
);

// Push with replacement (used for onboarding flow)
Navigator.of(context).pushReplacement(
  PageRouteBuilder(
    pageBuilder: (context, animation, secondaryAnimation) => HomeScreen(),
    transitionsBuilder: (context, animation, secondaryAnimation, child) {
      return FadeTransition(opacity: animation, child: child);
    },
    transitionDuration: Duration(milliseconds: 500),
  ),
);

// Full-screen dialog
Navigator.push(
  context,
  MaterialPageRoute(
    builder: (context) => CreatePostScreen(),
    fullscreenDialog: true,
  ),
);

// Pop with result
Navigator.pop(context, true);
```

### Navigation Patterns

#### Tab-Based Navigation

Main screens use `IndexedStack` for persistent tab state:

```dart
class HomeScreen extends StatefulWidget {
  // ...
}

class _HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;

  final List<Widget> _screens = [
    FeedScreen(),
    CommunityChatScreen(),
    DmScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      bottomNavigationBar: _buildNavBar(),
    );
  }
}
```

#### Deep Navigation Flow

```
┌───────────────────────────────────────────────────────────────┐
│                      SplashScreen                             │
│                           │                                   │
│              ┌────────────┴────────────┐                     │
│              ▼                         ▼                     │
│      OnboardingScreen           HomeScreen                   │
│              │                         │                     │
│              └─────────┬───────────────┘                     │
│                        │                                     │
│              ┌─────────┼─────────┐                          │
│              ▼         ▼         ▼                          │
│           Feed       Chat       DMs                         │
│              │         │         │                          │
│      ┌───────┼───────┐ │ ┌───────┼───────┐                 │
│      ▼       ▼       ▼ │ ▼       ▼       ▼                 │
│   Post   Profile  Settings ... Chat  Profile Notifications  │
│   Detail  Screen  Screen       Detail Screen                │
└───────────────────────────────────────────────────────────────┘
```

### Screen Transitions

Custom page transitions for smooth UX:

```dart
PageRouteBuilder(
  pageBuilder: (context, animation, secondaryAnimation) => TargetScreen(),
  transitionsBuilder: (context, animation, secondaryAnimation, child) {
    // Fade transition
    return FadeTransition(opacity: animation, child: child);

    // Or slide transition
    return SlideTransition(
      position: Tween<Offset>(
        begin: Offset(1.0, 0.0),
        end: Offset.zero,
      ).animate(animation),
      child: child,
    );
  },
  transitionDuration: Duration(milliseconds: 300),
);
```

### Returning Data from Screens

```dart
// Push and await result
final result = await Navigator.push<bool>(
  context,
  MaterialPageRoute(builder: (context) => CreatePostScreen()),
);

if (result == true) {
  // Post was created, refresh feed
  context.read<AppState>().loadFeed(refresh: true);
}
```

---

## 7. API Integration

### HTTP Client Setup

```dart
class ApiService {
  static String get baseUrl {
    if (kIsWeb) return 'http://localhost:8000';
    return 'http://10.0.2.2:8000';
  }

  final http.Client _client = http.Client();

  void dispose() {
    _client.close();
  }
}
```

### Request Patterns

**GET Request:**

```dart
Future<List<Post>> getFeed({
  String? userId,
  String? communityId,
  int limit = 20,
  int offset = 0,
}) async {
  final params = {
    'limit': limit.toString(),
    'offset': offset.toString(),
  };
  if (userId != null) params['user_id'] = userId;
  if (communityId != null) params['community_id'] = communityId;

  final uri = Uri.parse('$baseUrl/feed/posts').replace(queryParameters: params);
  final response = await _client.get(uri);

  if (response.statusCode == 200) {
    final List<dynamic> data = jsonDecode(response.body);
    return data.map((json) => Post.fromJson(json)).toList();
  }
  throw Exception('Failed to load feed: ${response.body}');
}
```

**POST Request with JSON Body:**

```dart
Future<Post> createPost({
  required String userId,
  required String communityId,
  required String content,
}) async {
  final response = await _client.post(
    Uri.parse('$baseUrl/feed/posts'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({
      'user_id': userId,
      'community_id': communityId,
      'content': content,
    }),
  );

  if (response.statusCode == 200 || response.statusCode == 201) {
    return Post.fromJson(jsonDecode(response.body));
  }
  throw Exception('Failed to create post: ${response.body}');
}
```

### Error Handling

```dart
// Custom exception for offline scenarios
class OfflineException implements Exception {
  final String message;
  final String? cachedDataKey;

  OfflineException(this.message, {this.cachedDataKey});
}

// Usage in API methods
Future<void> _checkOnline() async {
  if (!_offline.isOnline) {
    throw OfflineException('Device is offline');
  }
}

// Catching in UI/state
try {
  await _api.likePost(post.id, userId);
} on OfflineException {
  // Queue for later
  await _offlineService.queueAction(ActionType.likePost, {...});
} catch (e) {
  // Handle other errors
  _error = 'Failed to like post: $e';
}
```

### Cache-First Pattern

```dart
Future<T> _withCache<T>({
  required String cacheKey,
  required Future<T> Function() networkCall,
  required Future<void> Function(T data) cacheData,
  required Future<T?> Function() getCachedData,
}) async {
  try {
    // Try network first
    final data = await networkCall();
    // Cache successful response
    await cacheData(data);
    return data;
  } catch (e) {
    // On network error, try cache
    final cached = await getCachedData();
    if (cached != null) return cached;
    rethrow;
  }
}
```

### Retry Logic

WebSocket reconnection with exponential backoff:

```dart
int _reconnectAttempts = 0;
static const int _maxReconnectAttempts = 10;
static const int _baseReconnectDelay = 1; // seconds

void _scheduleReconnect() {
  if (_reconnectAttempts >= _maxReconnectAttempts) {
    debugPrint('Max reconnect attempts reached.');
    return;
  }

  // Exponential backoff: 1s, 2s, 4s, 8s, ... up to 30s max
  final delay = (_baseReconnectDelay * (1 << _reconnectAttempts)).clamp(1, 30);
  _reconnectAttempts++;

  _reconnectTimer = Timer(Duration(seconds: delay), () => connect());
}
```

### Optimistic Updates

```dart
Future<void> likePost(Post post) async {
  if (_currentUser == null) return;

  // Optimistic update - update UI immediately
  final wasLiked = post.isLikedByUser;
  post.isLikedByUser = !wasLiked;
  post.likeCount += wasLiked ? -1 : 1;
  notifyListeners();

  try {
    // Sync with server
    if (wasLiked) {
      await _api.unlikePost(post.id, _currentUser!.id);
    } else {
      await _api.likePost(post.id, _currentUser!.id);
    }
  } on OfflineException {
    // Queue for later when back online
    await _offlineService.queueAction(
      wasLiked ? ActionType.unlikePost : ActionType.likePost,
      {'post_id': post.id, 'user_id': _currentUser!.id},
    );
  } catch (e) {
    // Revert optimistic update on error
    post.isLikedByUser = wasLiked;
    post.likeCount += wasLiked ? 1 : -1;
    _error = 'Failed to like post: $e';
    notifyListeners();
  }
}
```

---

## 8. Testing

### Test Directory Structure

```
cell/test/
├── unit/                    # Unit tests
│   ├── models/              # Model tests
│   ├── services/            # Service tests
│   └── providers/           # Provider tests
├── widget/                  # Widget tests
│   ├── widgets/             # Component tests
│   └── screens/             # Screen tests
└── integration/             # Integration tests
```

### Unit Tests

Testing models:

```dart
// test/unit/models/post_test.dart
void main() {
  group('Post', () {
    test('fromJson creates valid Post', () {
      final json = {
        'id': 'post_1',
        'content': 'Test content',
        'author': {'id': 'user_1', 'display_name': 'Test User'},
        'created_at': '2024-01-01T12:00:00Z',
      };

      final post = Post.fromJson(json);

      expect(post.id, 'post_1');
      expect(post.content, 'Test content');
      expect(post.author.displayName, 'Test User');
    });

    test('fromJson handles missing fields', () {
      final json = {'id': 'post_1'};
      final post = Post.fromJson(json);

      expect(post.content, '');
      expect(post.likeCount, 0);
    });
  });
}
```

Testing services:

```dart
// test/unit/services/cache_service_test.dart
void main() {
  late CacheService cacheService;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    cacheService = CacheService.instance;
    await cacheService.initialize();
  });

  test('cacheData stores and retrieves data', () async {
    await cacheService.cacheData('test_key', {'value': 123});
    final result = await cacheService.getCachedData('test_key');

    expect(result['value'], 123);
  });

  test('expired cache returns null', () async {
    await cacheService.cacheData('test_key', 'data', ttl: Duration.zero);
    await Future.delayed(Duration(milliseconds: 10));

    final result = await cacheService.getCachedData('test_key');
    expect(result, isNull);
  });
}
```

### Widget Tests

```dart
// test/widget/widgets/post_card_test.dart
void main() {
  testWidgets('PostCard displays post content', (tester) async {
    final post = Post(
      id: 'test',
      author: Author(id: 'a1', displayName: 'Test', avatarSeed: 'seed'),
      communityId: 'c1',
      communityName: 'Test Community',
      content: 'Hello, world!',
      createdAt: DateTime.now(),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: ChangeNotifierProvider(
          create: (_) => AppState(),
          child: Scaffold(body: PostCard(post: post)),
        ),
      ),
    );

    expect(find.text('Hello, world!'), findsOneWidget);
    expect(find.text('Test'), findsOneWidget);
  });

  testWidgets('PostCard like button triggers action', (tester) async {
    // ... test interaction
  });
}
```

### Integration Tests

```dart
// integration_test/app_test.dart
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('Complete user flow test', (tester) async {
    await tester.pumpWidget(AiSocialApp());
    await tester.pumpAndSettle();

    // Wait for initialization
    await tester.pumpAndSettle(Duration(seconds: 3));

    // Verify feed loads
    expect(find.byType(FeedScreen), findsOneWidget);

    // Navigate to chat
    await tester.tap(find.text('Chat'));
    await tester.pumpAndSettle();
    expect(find.byType(CommunityChatScreen), findsOneWidget);

    // Test message sending
    await tester.enterText(find.byType(TextField), 'Test message');
    await tester.tap(find.byIcon(Icons.send));
    await tester.pumpAndSettle();
  });
}
```

### Test Utilities

```dart
// test/helpers/test_helpers.dart

Post createTestPost({
  String? id,
  String? content,
  Author? author,
}) {
  return Post(
    id: id ?? 'test_${DateTime.now().millisecondsSinceEpoch}',
    author: author ?? createTestAuthor(),
    communityId: 'test_community',
    communityName: 'Test Community',
    content: content ?? 'Test content',
    createdAt: DateTime.now(),
  );
}

Author createTestAuthor({String? id, String? name}) {
  return Author(
    id: id ?? 'author_1',
    displayName: name ?? 'Test Author',
    avatarSeed: 'test_seed',
  );
}

// Mock AppState for widget tests
class MockAppState extends ChangeNotifier implements AppState {
  @override
  List<Post> get posts => _posts;
  List<Post> _posts = [];

  void setMockPosts(List<Post> posts) {
    _posts = posts;
    notifyListeners();
  }
}
```

### Running Tests

```bash
# Run all tests
flutter test

# Run specific test file
flutter test test/unit/models/post_test.dart

# Run with coverage
flutter test --coverage

# Run integration tests
flutter test integration_test/

# Run tests with verbose output
flutter test --reporter expanded
```

---

## Dependencies

The app uses the following key packages (from `pubspec.yaml`):

| Package | Version | Purpose |
|---------|---------|---------|
| `provider` | ^6.1.2 | State management |
| `http` | ^1.2.2 | HTTP client |
| `web_socket_channel` | ^3.0.1 | WebSocket communication |
| `shared_preferences` | ^2.3.3 | Local storage |
| `connectivity_plus` | ^6.1.1 | Network detection |
| `uuid` | ^4.5.1 | Unique ID generation |
| `intl` | ^0.19.0 | Internationalization |
| `timeago` | ^3.7.0 | Relative time formatting |
| `cached_network_image` | ^3.4.1 | Image caching |
| `shimmer` | ^3.0.0 | Loading animations |
| `flutter_animate` | ^4.5.0 | Animation utilities |
| `flutter_svg` | ^2.0.10+1 | SVG rendering |

---

## Best Practices Summary

1. **State Management**: Use Provider for global state, local state for UI-specific data
2. **Services**: Singleton pattern for services, dispose properly
3. **Models**: Immutable where possible, factory constructors for JSON
4. **Error Handling**: Custom exceptions, graceful degradation
5. **Offline Support**: Queue actions, cache aggressively, optimistic updates
6. **Navigation**: Clear navigation patterns, pass data via constructor
7. **Testing**: Test models, services, and widgets separately
8. **Performance**: Lazy loading, pagination, avoid unnecessary rebuilds
