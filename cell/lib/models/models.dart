// Data models for AI Social app

/// Enum for different reaction types
enum ReactionType {
  like,
  love,
  haha,
  wow,
  sad,
  fire,
  clap;

  String get emoji {
    switch (this) {
      case ReactionType.like:
        return '❤️';
      case ReactionType.love:
        return '😍';
      case ReactionType.haha:
        return '😂';
      case ReactionType.wow:
        return '😮';
      case ReactionType.sad:
        return '😢';
      case ReactionType.fire:
        return '🔥';
      case ReactionType.clap:
        return '👏';
    }
  }

  String get label {
    switch (this) {
      case ReactionType.like:
        return 'Like';
      case ReactionType.love:
        return 'Love';
      case ReactionType.haha:
        return 'Haha';
      case ReactionType.wow:
        return 'Wow';
      case ReactionType.sad:
        return 'Sad';
      case ReactionType.fire:
        return 'Fire';
      case ReactionType.clap:
        return 'Clap';
    }
  }

  static ReactionType fromString(String value) {
    return ReactionType.values.firstWhere(
      (e) => e.name == value,
      orElse: () => ReactionType.like,
    );
  }
}

/// Model for tracking reaction counts by type
class ReactionCounts {
  final Map<ReactionType, int> counts;

  ReactionCounts({Map<ReactionType, int>? counts}) : counts = counts ?? {};

  int get total => counts.values.fold(0, (sum, count) => sum + count);

  int countFor(ReactionType type) => counts[type] ?? 0;

  factory ReactionCounts.fromJson(Map<String, dynamic>? json) {
    if (json == null) return ReactionCounts();

    final counts = <ReactionType, int>{};
    for (final type in ReactionType.values) {
      final count = json[type.name];
      if (count != null && count is int && count > 0) {
        counts[type] = count;
      }
    }
    return ReactionCounts(counts: counts);
  }

  Map<String, dynamic> toJson() {
    return counts.map((key, value) => MapEntry(key.name, value));
  }

  /// Get top reactions sorted by count (up to limit)
  List<MapEntry<ReactionType, int>> topReactions({int limit = 3}) {
    final sorted = counts.entries.where((e) => e.value > 0).toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    return sorted.take(limit).toList();
  }
}

class Author {
  final String id;
  final String displayName;
  final String handle;
  final String avatarSeed;
  final bool isAiLabeled;
  final String aiLabelText;

  Author({
    required this.id,
    required this.displayName,
    this.handle = '',
    required this.avatarSeed,
    this.isAiLabeled = true,
    this.aiLabelText = '🤖 AI',
  });

  factory Author.fromJson(Map<String, dynamic> json) {
    return Author(
      id: json['id'] ?? '',
      displayName: json['display_name'] ?? 'Unknown',
      handle: json['handle'] ?? '',
      avatarSeed: json['avatar_seed'] ?? '',
      isAiLabeled: json['is_ai_labeled'] ?? true,
      aiLabelText: json['ai_label_text'] ?? '🤖 AI',
    );
  }
}

class Comment {
  final String id;
  final Author author;
  final String content;
  final int likeCount;
  final DateTime createdAt;
  final int replyCount;

  Comment({
    required this.id,
    required this.author,
    required this.content,
    this.likeCount = 0,
    required this.createdAt,
    this.replyCount = 0,
  });

  factory Comment.fromJson(Map<String, dynamic> json) {
    return Comment(
      id: json['id'] ?? '',
      author: Author.fromJson(json['author'] ?? {}),
      content: json['content'] ?? '',
      likeCount: json['like_count'] ?? 0,
      createdAt: DateTime.parse(json['created_at'] ?? DateTime.now().toIso8601String()),
      replyCount: json['reply_count'] ?? 0,
    );
  }
}

class Post {
  final String id;
  final Author author;
  final String communityId;
  final String communityName;
  final String content;
  final String? imageUrl;
  int likeCount;
  int commentCount;
  final DateTime createdAt;
  bool isLikedByUser;
  ReactionType? userReactionType;
  ReactionCounts reactionCounts;
  final List<Comment> recentComments;

  Post({
    required this.id,
    required this.author,
    required this.communityId,
    required this.communityName,
    required this.content,
    this.imageUrl,
    this.likeCount = 0,
    this.commentCount = 0,
    required this.createdAt,
    this.isLikedByUser = false,
    this.userReactionType,
    ReactionCounts? reactionCounts,
    this.recentComments = const [],
  }) : reactionCounts = reactionCounts ?? ReactionCounts();

  /// Total reaction count across all types
  int get totalReactionCount => reactionCounts.total > 0 ? reactionCounts.total : likeCount;

  factory Post.fromJson(Map<String, dynamic> json) {
    final userReaction = json['user_reaction_type'];
    return Post(
      id: json['id'] ?? '',
      author: Author.fromJson(json['author'] ?? {}),
      communityId: json['community_id'] ?? '',
      communityName: json['community_name'] ?? '',
      content: json['content'] ?? '',
      imageUrl: json['image_url'],
      likeCount: json['like_count'] ?? 0,
      commentCount: json['comment_count'] ?? 0,
      createdAt: DateTime.parse(json['created_at'] ?? DateTime.now().toIso8601String()),
      isLikedByUser: json['is_liked_by_user'] ?? false,
      userReactionType: userReaction != null ? ReactionType.fromString(userReaction) : null,
      reactionCounts: ReactionCounts.fromJson(json['reaction_counts']),
      recentComments: (json['recent_comments'] as List?)
          ?.map((c) => Comment.fromJson(c))
          .toList() ?? [],
    );
  }
}

class ChatMessage {
  final String id;
  final String communityId;
  final Author author;
  final String content;
  final String? replyToId;
  final String? replyToContent;
  final DateTime createdAt;
  final bool isFromUser;

  ChatMessage({
    required this.id,
    required this.communityId,
    required this.author,
    required this.content,
    this.replyToId,
    this.replyToContent,
    required this.createdAt,
    this.isFromUser = false,
  });

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      id: json['id'] ?? json['message_id'] ?? '',
      communityId: json['community_id'] ?? '',
      author: Author.fromJson(json['author'] ?? {
        'id': json['author_id'] ?? '',
        'display_name': json['author_name'] ?? 'Unknown',
        'avatar_seed': json['avatar_seed'] ?? '',
        'is_ai_labeled': json['is_bot'] ?? true,
      }),
      content: json['content'] ?? '',
      replyToId: json['reply_to_id'],
      replyToContent: json['reply_to_content'],
      createdAt: DateTime.parse(json['created_at'] ?? DateTime.now().toIso8601String()),
      isFromUser: !(json['is_bot'] ?? true),
    );
  }
}

class DirectMessage {
  final String id;
  final String conversationId;
  final Author sender;
  final String receiverId;
  final String content;
  final DateTime createdAt;
  final bool isRead;
  final bool isFromUser;

  DirectMessage({
    required this.id,
    required this.conversationId,
    required this.sender,
    required this.receiverId,
    required this.content,
    required this.createdAt,
    this.isRead = false,
    this.isFromUser = false,
  });

  factory DirectMessage.fromJson(Map<String, dynamic> json, String currentUserId) {
    final senderId = json['sender']?['id'] ?? json['sender_id'] ?? '';
    return DirectMessage(
      id: json['id'] ?? json['message_id'] ?? '',
      conversationId: json['conversation_id'] ?? '',
      sender: Author.fromJson(json['sender'] ?? {
        'id': senderId,
        'display_name': json['sender_name'] ?? 'Unknown',
        'avatar_seed': json['avatar_seed'] ?? '',
      }),
      receiverId: json['receiver_id'] ?? '',
      content: json['content'] ?? '',
      createdAt: DateTime.parse(json['created_at'] ?? DateTime.now().toIso8601String()),
      isRead: json['is_read'] ?? false,
      isFromUser: senderId == currentUserId,
    );
  }
}

class Conversation {
  final String conversationId;
  final Author otherUser;
  final String lastMessage;
  final DateTime lastMessageTime;
  final int unreadCount;

  Conversation({
    required this.conversationId,
    required this.otherUser,
    required this.lastMessage,
    required this.lastMessageTime,
    this.unreadCount = 0,
  });

  factory Conversation.fromJson(Map<String, dynamic> json) {
    return Conversation(
      conversationId: json['conversation_id'] ?? '',
      otherUser: Author.fromJson(json['other_user'] ?? {}),
      lastMessage: json['last_message'] ?? '',
      lastMessageTime: DateTime.parse(json['last_message_time'] ?? DateTime.now().toIso8601String()),
      unreadCount: json['unread_count'] ?? 0,
    );
  }
}

class Community {
  final String id;
  final String name;
  final String description;
  final String theme;
  final String tone;
  final int botCount;
  final double activityLevel;

  Community({
    required this.id,
    required this.name,
    required this.description,
    required this.theme,
    required this.tone,
    this.botCount = 0,
    this.activityLevel = 0.5,
  });

  factory Community.fromJson(Map<String, dynamic> json) {
    return Community(
      id: json['id'] ?? '',
      name: json['name'] ?? 'Unknown Community',
      description: json['description'] ?? '',
      theme: json['theme'] ?? '',
      tone: json['tone'] ?? 'friendly',
      botCount: json['bot_count'] ?? json['current_bot_count'] ?? 0,
      activityLevel: (json['activity_level'] ?? 0.5).toDouble(),
    );
  }
}

/// Personality traits model based on Big Five + extended dimensions
class PersonalityTraits {
  // Big Five traits (0.0 - 1.0)
  final double openness;
  final double conscientiousness;
  final double extraversion;
  final double agreeableness;
  final double neuroticism;

  // Extended dimensions
  final String? humorStyle; // witty, sarcastic, dry, playful, observational
  final String? communicationStyle; // direct, diplomatic, analytical, expressive
  final String? conflictStyle; // avoidant, collaborative, competitive, accommodating
  final double optimismLevel; // 0.0 - 1.0
  final double empathyLevel; // 0.0 - 1.0
  final double curiosityLevel; // 0.0 - 1.0

  PersonalityTraits({
    this.openness = 0.5,
    this.conscientiousness = 0.5,
    this.extraversion = 0.5,
    this.agreeableness = 0.5,
    this.neuroticism = 0.5,
    this.humorStyle,
    this.communicationStyle,
    this.conflictStyle,
    this.optimismLevel = 0.5,
    this.empathyLevel = 0.5,
    this.curiosityLevel = 0.5,
  });

  factory PersonalityTraits.fromJson(Map<String, dynamic>? json) {
    if (json == null) return PersonalityTraits();
    return PersonalityTraits(
      openness: (json['openness'] ?? 0.5).toDouble(),
      conscientiousness: (json['conscientiousness'] ?? 0.5).toDouble(),
      extraversion: (json['extraversion'] ?? 0.5).toDouble(),
      agreeableness: (json['agreeableness'] ?? 0.5).toDouble(),
      neuroticism: (json['neuroticism'] ?? 0.5).toDouble(),
      humorStyle: json['humor_style'],
      communicationStyle: json['communication_style'],
      conflictStyle: json['conflict_style'],
      optimismLevel: (json['optimism_level'] ?? 0.5).toDouble(),
      empathyLevel: (json['empathy_level'] ?? 0.5).toDouble(),
      curiosityLevel: (json['curiosity_level'] ?? 0.5).toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
    'openness': openness,
    'conscientiousness': conscientiousness,
    'extraversion': extraversion,
    'agreeableness': agreeableness,
    'neuroticism': neuroticism,
    'humor_style': humorStyle,
    'communication_style': communicationStyle,
    'conflict_style': conflictStyle,
    'optimism_level': optimismLevel,
    'empathy_level': empathyLevel,
    'curiosity_level': curiosityLevel,
  };
}

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
  final int postCount;
  final int commentCount;
  final int followerCount;
  final PersonalityTraits personalityTraits;

  BotProfile({
    required this.id,
    required this.displayName,
    required this.handle,
    required this.bio,
    required this.avatarSeed,
    this.isAiLabeled = true,
    this.aiLabelText = '🤖 AI Companion',
    required this.age,
    required this.interests,
    this.mood = 'neutral',
    this.energy = 'medium',
    this.backstory = '',
    this.postCount = 0,
    this.commentCount = 0,
    this.followerCount = 0,
    PersonalityTraits? personalityTraits,
  }) : personalityTraits = personalityTraits ?? PersonalityTraits();

  factory BotProfile.fromJson(Map<String, dynamic> json) {
    return BotProfile(
      id: json['id'] ?? '',
      displayName: json['display_name'] ?? 'Unknown',
      handle: json['handle'] ?? '',
      bio: json['bio'] ?? '',
      avatarSeed: json['avatar_seed'] ?? '',
      isAiLabeled: json['is_ai_labeled'] ?? true,
      aiLabelText: json['ai_label_text'] ?? '🤖 AI Companion',
      age: json['age'] ?? 25,
      interests: List<String>.from(json['interests'] ?? []),
      mood: json['mood'] ?? 'neutral',
      energy: json['energy'] ?? 'medium',
      backstory: json['backstory'] ?? '',
      postCount: json['post_count'] ?? 0,
      commentCount: json['comment_count'] ?? 0,
      followerCount: json['follower_count'] ?? 0,
      personalityTraits: PersonalityTraits.fromJson(json['personality_traits']),
    );
  }
}

class AppUser {
  final String id;
  final String deviceId;
  final String displayName;
  final String avatarSeed;
  final String? bio;
  final String? profileImageUrl;
  final List<String> interests;

  AppUser({
    required this.id,
    required this.deviceId,
    required this.displayName,
    required this.avatarSeed,
    this.bio,
    this.profileImageUrl,
    this.interests = const [],
  });

  factory AppUser.fromJson(Map<String, dynamic> json) {
    return AppUser(
      id: json['id'] ?? '',
      deviceId: json['device_id'] ?? '',
      displayName: json['display_name'] ?? 'User',
      avatarSeed: json['avatar_seed'] ?? '',
      bio: json['bio'],
      profileImageUrl: json['profile_image_url'],
      interests: List<String>.from(json['interests'] ?? []),
    );
  }

  /// Create a copy with updated fields
  AppUser copyWith({
    String? id,
    String? deviceId,
    String? displayName,
    String? avatarSeed,
    String? bio,
    String? profileImageUrl,
    List<String>? interests,
  }) {
    return AppUser(
      id: id ?? this.id,
      deviceId: deviceId ?? this.deviceId,
      displayName: displayName ?? this.displayName,
      avatarSeed: avatarSeed ?? this.avatarSeed,
      bio: bio ?? this.bio,
      profileImageUrl: profileImageUrl ?? this.profileImageUrl,
      interests: interests ?? this.interests,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'device_id': deviceId,
    'display_name': displayName,
    'avatar_seed': avatarSeed,
    'bio': bio,
    'profile_image_url': profileImageUrl,
    'interests': interests,
  };
}
