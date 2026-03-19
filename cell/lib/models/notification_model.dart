/// Notification types for the app
enum NotificationType {
  like,
  comment,
  mention,
  dm,
  follow,
}

/// Model for notifications
class NotificationModel {
  final String id;
  final NotificationType type;
  final String message;
  final String? actorId;
  final String? actorName;
  final String? actorAvatarSeed;
  final String? targetId; // Post ID, conversation ID, etc.
  final String? targetPreview; // Preview of the content
  final DateTime createdAt;
  final bool isRead;

  NotificationModel({
    required this.id,
    required this.type,
    required this.message,
    this.actorId,
    this.actorName,
    this.actorAvatarSeed,
    this.targetId,
    this.targetPreview,
    required this.createdAt,
    this.isRead = false,
  });

  factory NotificationModel.fromJson(Map<String, dynamic> json) {
    return NotificationModel(
      id: json['id'] ?? '',
      type: _parseNotificationType(json['type']),
      message: json['message'] ?? '',
      actorId: json['actor_id'],
      actorName: json['actor_name'],
      actorAvatarSeed: json['actor_avatar_seed'],
      targetId: json['target_id'],
      targetPreview: json['target_preview'],
      createdAt: DateTime.parse(json['created_at'] ?? DateTime.now().toIso8601String()),
      isRead: json['is_read'] ?? false,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'type': type.name,
      'message': message,
      'actor_id': actorId,
      'actor_name': actorName,
      'actor_avatar_seed': actorAvatarSeed,
      'target_id': targetId,
      'target_preview': targetPreview,
      'created_at': createdAt.toIso8601String(),
      'is_read': isRead,
    };
  }

  NotificationModel copyWith({
    String? id,
    NotificationType? type,
    String? message,
    String? actorId,
    String? actorName,
    String? actorAvatarSeed,
    String? targetId,
    String? targetPreview,
    DateTime? createdAt,
    bool? isRead,
  }) {
    return NotificationModel(
      id: id ?? this.id,
      type: type ?? this.type,
      message: message ?? this.message,
      actorId: actorId ?? this.actorId,
      actorName: actorName ?? this.actorName,
      actorAvatarSeed: actorAvatarSeed ?? this.actorAvatarSeed,
      targetId: targetId ?? this.targetId,
      targetPreview: targetPreview ?? this.targetPreview,
      createdAt: createdAt ?? this.createdAt,
      isRead: isRead ?? this.isRead,
    );
  }

  static NotificationType _parseNotificationType(dynamic value) {
    if (value is String) {
      switch (value.toLowerCase()) {
        case 'like':
          return NotificationType.like;
        case 'comment':
          return NotificationType.comment;
        case 'mention':
          return NotificationType.mention;
        case 'dm':
          return NotificationType.dm;
        case 'follow':
          return NotificationType.follow;
        default:
          return NotificationType.like;
      }
    }
    return NotificationType.like;
  }
}
