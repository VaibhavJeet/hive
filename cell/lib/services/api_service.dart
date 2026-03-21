import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import '../config/config.dart';
import '../models/models.dart';
import 'offline_service.dart';

/// Exception thrown when the device is offline
class OfflineException implements Exception {
  final String message;
  final String? cachedDataKey;

  OfflineException(this.message, {this.cachedDataKey});

  @override
  String toString() => 'OfflineException: $message';
}

class ApiService {
  /// Get the API base URL from environment configuration
  static String get baseUrl => EnvConfig.apiBaseUrl;

  final http.Client _client = http.Client();
  final OfflineService _offline = OfflineService.instance;

  /// Check if online before making request
  Future<void> _checkOnline() async {
    if (!_offline.isOnline) {
      throw OfflineException('Device is offline');
    }
  }

  /// Try to get cached data, throw OfflineException with cache key if offline
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
      if (cached != null) {
        return cached;
      }
      // Re-throw with cache key info
      if (e is OfflineException) {
        rethrow;
      }
      throw OfflineException('Network error: $e', cachedDataKey: cacheKey);
    }
  }

  // ========================================================================
  // USER ENDPOINTS
  // ========================================================================

  Future<AppUser> registerUser(String deviceId, String displayName) async {
    final response = await _client.post(
      Uri.parse('$baseUrl/users/register'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'device_id': deviceId,
        'display_name': displayName,
      }),
    );

    if (response.statusCode == 200) {
      return AppUser.fromJson(jsonDecode(response.body));
    }
    throw Exception('Failed to register user: ${response.body}');
  }

  /// Update user profile with optional profile image
  Future<AppUser> updateUserProfile({
    required String userId,
    String? displayName,
    String? bio,
    String? avatarSeed,
    File? profileImage,
    List<String>? interests,
  }) async {
    await _checkOnline();

    final body = <String, dynamic>{};
    if (displayName != null) body['display_name'] = displayName;
    if (bio != null) body['bio'] = bio;
    if (avatarSeed != null) body['avatar_seed'] = avatarSeed;
    if (interests != null) body['interests'] = interests;

    // Handle profile image upload if provided
    if (profileImage != null) {
      final request = http.MultipartRequest(
        'PUT',
        Uri.parse('$baseUrl/users/$userId/profile'),
      );
      request.fields.addAll(body.map((key, value) =>
          MapEntry(key, value is List ? jsonEncode(value) : value.toString())));
      request.files.add(await http.MultipartFile.fromPath(
        'profile_image',
        profileImage.path,
      ));

      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        return AppUser.fromJson(jsonDecode(response.body));
      }
      throw Exception('Failed to update profile: ${response.body}');
    }

    // Regular JSON update without image
    final response = await _client.put(
      Uri.parse('$baseUrl/users/$userId/profile'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );

    if (response.statusCode == 200) {
      return AppUser.fromJson(jsonDecode(response.body));
    }
    throw Exception('Failed to update profile: ${response.body}');
  }

  // ========================================================================
  // FEED ENDPOINTS
  // ========================================================================

  Future<List<Post>> getFeed({
    String? userId,
    String? communityId,
    int limit = 20,
    int offset = 0,
  }) async {
    final cacheKey = communityId != null ? 'feed_$communityId' : 'feed_all';

    return _withCache<List<Post>>(
      cacheKey: cacheKey,
      networkCall: () async {
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
      },
      cacheData: (posts) async {
        await _offline.cacheFeed(posts, communityId: communityId);
      },
      getCachedData: () async {
        return await _offline.getCachedFeed(communityId: communityId);
      },
    );
  }

  Future<Post> getPost(String postId, {String? userId}) async {
    final params = <String, String>{};
    if (userId != null) params['user_id'] = userId;

    final uri = Uri.parse('$baseUrl/feed/posts/$postId').replace(queryParameters: params);
    final response = await _client.get(uri);

    if (response.statusCode == 200) {
      return Post.fromJson(jsonDecode(response.body));
    }
    throw Exception('Failed to load post: ${response.body}');
  }

  Future<Map<String, dynamic>> likePost(
    String postId,
    String userId, {
    bool isBot = false,
    String reactionType = 'like',
  }) async {
    await _checkOnline();

    final params = {
      'user_id': userId,
      'is_bot': isBot.toString(),
      'reaction_type': reactionType,
    };

    final uri = Uri.parse('$baseUrl/feed/posts/$postId/like').replace(queryParameters: params);
    final response = await _client.post(uri);

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to like post: ${response.body}');
  }

  Future<Map<String, dynamic>> unlikePost(String postId, String userId) async {
    await _checkOnline();

    final params = {'user_id': userId};
    final uri = Uri.parse('$baseUrl/feed/posts/$postId/like').replace(queryParameters: params);
    final response = await _client.delete(uri);

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to unlike post: ${response.body}');
  }

  Future<Comment> createComment(String postId, String userId, String content, {bool isBot = false}) async {
    await _checkOnline();

    final params = {
      'user_id': userId,
      'content': content,
      'is_bot': isBot.toString(),
    };

    final uri = Uri.parse('$baseUrl/feed/posts/$postId/comments').replace(queryParameters: params);
    final response = await _client.post(uri);

    if (response.statusCode == 200) {
      return Comment.fromJson(jsonDecode(response.body));
    }
    throw Exception('Failed to create comment: ${response.body}');
  }

  Future<List<Comment>> getComments(String postId, {int limit = 50, int offset = 0}) async {
    final params = {
      'limit': limit.toString(),
      'offset': offset.toString(),
    };

    final uri = Uri.parse('$baseUrl/feed/posts/$postId/comments').replace(queryParameters: params);
    final response = await _client.get(uri);

    if (response.statusCode == 200) {
      final List<dynamic> data = jsonDecode(response.body);
      return data.map((json) => Comment.fromJson(json)).toList();
    }
    throw Exception('Failed to load comments: ${response.body}');
  }

  Future<List<Author>> getLikers(String postId, {int limit = 50, int offset = 0}) async {
    final params = {
      'limit': limit.toString(),
      'offset': offset.toString(),
    };

    final uri = Uri.parse('$baseUrl/feed/posts/$postId/likers').replace(queryParameters: params);
    final response = await _client.get(uri);

    if (response.statusCode == 200) {
      final List<dynamic> data = jsonDecode(response.body);
      return data.map((json) => Author.fromJson(json)).toList();
    }
    throw Exception('Failed to load likers: ${response.body}');
  }

  Future<Post> createPost({
    required String userId,
    required String communityId,
    required String content,
    File? image,
  }) async {
    if (image != null) {
      // Use multipart form data for posts with images
      final request = http.MultipartRequest(
        'POST',
        Uri.parse('$baseUrl/feed/posts'),
      );

      request.fields['user_id'] = userId;
      request.fields['community_id'] = communityId;
      request.fields['content'] = content;

      final imageFile = await http.MultipartFile.fromPath(
        'image',
        image.path,
      );
      request.files.add(imageFile);

      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200 || response.statusCode == 201) {
        return Post.fromJson(jsonDecode(response.body));
      }
      throw Exception('Failed to create post: ${response.body}');
    } else {
      // Use JSON for posts without images
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
  }

  // ========================================================================
  // COMMUNITY CHAT ENDPOINTS
  // ========================================================================

  Future<List<ChatMessage>> getCommunityChat(String communityId, {int limit = 50}) async {
    return _withCache<List<ChatMessage>>(
      cacheKey: 'chat_$communityId',
      networkCall: () async {
        final params = {'limit': limit.toString()};
        final uri = Uri.parse('$baseUrl/chat/community/$communityId/messages').replace(queryParameters: params);
        final response = await _client.get(uri);

        if (response.statusCode == 200) {
          final List<dynamic> data = jsonDecode(response.body);
          return data.map((json) => ChatMessage.fromJson(json)).toList();
        }
        throw Exception('Failed to load chat: ${response.body}');
      },
      cacheData: (messages) async {
        await _offline.cacheChatMessages(communityId, messages);
      },
      getCachedData: () async {
        return await _offline.getCachedChatMessages(communityId);
      },
    );
  }

  Future<ChatMessage> sendCommunityMessage(
    String communityId,
    String userId,
    String content, {
    String? replyToId,
    bool isBot = false,
  }) async {
    await _checkOnline();

    final params = {
      'user_id': userId,
      'is_bot': isBot.toString(),
    };

    final uri = Uri.parse('$baseUrl/chat/community/$communityId/messages').replace(queryParameters: params);
    final response = await _client.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'content': content,
        'reply_to_id': replyToId,
      }),
    );

    if (response.statusCode == 200) {
      return ChatMessage.fromJson(jsonDecode(response.body));
    }
    throw Exception('Failed to send message: ${response.body}');
  }

  // ========================================================================
  // DIRECT MESSAGE ENDPOINTS
  // ========================================================================

  Future<List<Conversation>> getConversations(String userId) async {
    return _withCache<List<Conversation>>(
      cacheKey: 'conversations_$userId',
      networkCall: () async {
        final params = {'user_id': userId};
        final uri = Uri.parse('$baseUrl/chat/dm/conversations').replace(queryParameters: params);
        final response = await _client.get(uri);

        if (response.statusCode == 200) {
          final List<dynamic> data = jsonDecode(response.body);
          return data.map((json) => Conversation.fromJson(json)).toList();
        }
        throw Exception('Failed to load conversations: ${response.body}');
      },
      cacheData: (conversations) async {
        await _offline.cacheConversations(userId, conversations);
      },
      getCachedData: () async {
        return await _offline.getCachedConversations(userId);
      },
    );
  }

  Future<List<DirectMessage>> getDirectMessages(
    String conversationId,
    String userId, {
    int limit = 50,
  }) async {
    final params = {
      'user_id': userId,
      'limit': limit.toString(),
    };

    final uri = Uri.parse('$baseUrl/chat/dm/$conversationId').replace(queryParameters: params);
    final response = await _client.get(uri);

    if (response.statusCode == 200) {
      final List<dynamic> data = jsonDecode(response.body);
      return data.map((json) => DirectMessage.fromJson(json, userId)).toList();
    }
    throw Exception('Failed to load messages: ${response.body}');
  }

  Future<DirectMessage> sendDirectMessage(
    String userId,
    String receiverId,
    String content, {
    bool isBot = false,
  }) async {
    await _checkOnline();

    final params = {
      'user_id': userId,
      'is_bot': isBot.toString(),
    };

    final uri = Uri.parse('$baseUrl/chat/dm').replace(queryParameters: params);
    final response = await _client.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'receiver_id': receiverId,
        'content': content,
      }),
    );

    if (response.statusCode == 200) {
      return DirectMessage.fromJson(jsonDecode(response.body), userId);
    }
    throw Exception('Failed to send message: ${response.body}');
  }

  // ========================================================================
  // COMMUNITY & BOT ENDPOINTS
  // ========================================================================

  Future<List<Community>> getCommunities() async {
    return _withCache<List<Community>>(
      cacheKey: 'communities',
      networkCall: () async {
        final response = await _client.get(Uri.parse('$baseUrl/communities'));

        if (response.statusCode == 200) {
          final List<dynamic> data = jsonDecode(response.body);
          return data.map((json) => Community.fromJson(json)).toList();
        }
        throw Exception('Failed to load communities: ${response.body}');
      },
      cacheData: (communities) async {
        await _offline.cacheCommunities(communities);
      },
      getCachedData: () async {
        return await _offline.getCachedCommunities();
      },
    );
  }

  Future<List<BotProfile>> getBots({String? communityId, int limit = 50, int offset = 0}) async {
    final params = {
      'limit': limit.toString(),
      'offset': offset.toString(),
    };
    if (communityId != null) params['community_id'] = communityId;

    final uri = Uri.parse('$baseUrl/users/bots').replace(queryParameters: params);
    final response = await _client.get(uri);

    if (response.statusCode == 200) {
      final List<dynamic> data = jsonDecode(response.body);
      return data.map((json) => BotProfile.fromJson(json)).toList();
    }
    throw Exception('Failed to load bots: ${response.body}');
  }

  Future<BotProfile> getBotProfile(String botId) async {
    final response = await _client.get(Uri.parse('$baseUrl/users/bots/$botId'));

    if (response.statusCode == 200) {
      return BotProfile.fromJson(jsonDecode(response.body));
    }
    throw Exception('Failed to load bot profile: ${response.body}');
  }

  // ========================================================================
  // PLATFORM ENDPOINTS
  // ========================================================================

  Future<Map<String, dynamic>> initializePlatform({int numCommunities = 2}) async {
    final params = {'num_communities': numCommunities.toString()};
    final uri = Uri.parse('$baseUrl/platform/initialize').replace(queryParameters: params);
    final response = await _client.post(uri);

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to initialize platform: ${response.body}');
  }

  Future<bool> healthCheck() async {
    try {
      final response = await _client.get(Uri.parse('$baseUrl/health'));
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  // ========================================================================
  // EVOLUTION & INTELLIGENCE ENDPOINTS
  // ========================================================================

  Future<Map<String, dynamic>> getBotIntelligence(String botId) async {
    final response = await _client.get(Uri.parse('$baseUrl/evolution/bots/$botId/intelligence'));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load bot intelligence: ${response.body}');
  }

  Future<List<dynamic>> getBotSkills(String botId) async {
    final response = await _client.get(Uri.parse('$baseUrl/evolution/bots/$botId/skills'));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load bot skills: ${response.body}');
  }

  Future<Map<String, dynamic>> triggerBotReflection(String botId) async {
    final response = await _client.post(Uri.parse('$baseUrl/evolution/bots/$botId/trigger-reflection'));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to trigger reflection: ${response.body}');
  }

  Future<Map<String, dynamic>> triggerBotEvolution(String botId) async {
    final response = await _client.post(Uri.parse('$baseUrl/evolution/bots/$botId/trigger-evolution'));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to trigger evolution: ${response.body}');
  }

  Future<Map<String, dynamic>> triggerBotSelfCoding(String botId, {String whatToImprove = 'general intelligence'}) async {
    final uri = Uri.parse('$baseUrl/evolution/bots/$botId/trigger-self-coding')
        .replace(queryParameters: {'what_to_improve': whatToImprove});
    final response = await _client.post(uri);

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to trigger self-coding: ${response.body}');
  }

  Future<Map<String, dynamic>> getPlatformIntelligence() async {
    final response = await _client.get(Uri.parse('$baseUrl/evolution/platform/intelligence'));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load platform intelligence: ${response.body}');
  }

  Future<List<dynamic>> getRecentEvolutionActivity({int limit = 20}) async {
    final uri = Uri.parse('$baseUrl/evolution/activity/recent')
        .replace(queryParameters: {'limit': limit.toString()});
    final response = await _client.get(uri);

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load evolution activity: ${response.body}');
  }

  Future<Map<String, dynamic>> getGitHubStatus() async {
    final response = await _client.get(Uri.parse('$baseUrl/evolution/github/status'));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load GitHub status: ${response.body}');
  }

  // ========================================================================
  // CIVILIZATION ENDPOINTS
  // ========================================================================

  Future<Map<String, dynamic>> getCivilizationStats() async {
    final response = await _client.get(Uri.parse('$baseUrl/civilization/stats'));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load civilization stats: ${response.body}');
  }

  Future<Map<String, dynamic>> getCurrentEra() async {
    final response = await _client.get(Uri.parse('$baseUrl/civilization/era'));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load current era: ${response.body}');
  }

  Future<List<dynamic>> getCivilizationTimeline({int limit = 50, int offset = 0}) async {
    final params = {
      'limit': limit.toString(),
      'offset': offset.toString(),
    };
    final uri = Uri.parse('$baseUrl/civilization/timeline').replace(queryParameters: params);
    final response = await _client.get(uri);

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load timeline: ${response.body}');
  }

  Future<List<dynamic>> getLivingBeings({int limit = 50}) async {
    final params = {'limit': limit.toString()};
    final uri = Uri.parse('$baseUrl/civilization/beings/living').replace(queryParameters: params);
    final response = await _client.get(uri);

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load living beings: ${response.body}');
  }

  Future<List<dynamic>> getDepartedBeings({int limit = 50}) async {
    final params = {'limit': limit.toString()};
    final uri = Uri.parse('$baseUrl/civilization/beings/departed').replace(queryParameters: params);
    final response = await _client.get(uri);

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load departed beings: ${response.body}');
  }

  Future<List<dynamic>> getActiveRituals() async {
    final response = await _client.get(Uri.parse('$baseUrl/civilization/rituals/active'));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load active rituals: ${response.body}');
  }

  Future<List<dynamic>> getCulturalMovements() async {
    final response = await _client.get(Uri.parse('$baseUrl/civilization/culture/movements'));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load cultural movements: ${response.body}');
  }

  Future<Map<String, dynamic>> getBeingProfile(String beingId) async {
    final response = await _client.get(Uri.parse('$baseUrl/civilization/beings/$beingId'));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load being profile: ${response.body}');
  }

  Future<List<dynamic>> getBeingRelationships(String beingId) async {
    final response = await _client.get(Uri.parse('$baseUrl/civilization/beings/$beingId/relationships'));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load relationships: ${response.body}');
  }

  void dispose() {
    _client.close();
  }
}
