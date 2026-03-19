// Offline action model for queuing actions when offline

import 'dart:convert';

/// Types of actions that can be queued for offline processing
enum ActionType {
  sendMessage,
  createPost,
  likePost,
  unlikePost,
  sendDm,
  createComment,
}

/// Extension to convert ActionType to/from string
extension ActionTypeExtension on ActionType {
  String get value {
    switch (this) {
      case ActionType.sendMessage:
        return 'send_message';
      case ActionType.createPost:
        return 'create_post';
      case ActionType.likePost:
        return 'like_post';
      case ActionType.unlikePost:
        return 'unlike_post';
      case ActionType.sendDm:
        return 'send_dm';
      case ActionType.createComment:
        return 'create_comment';
    }
  }

  static ActionType fromString(String value) {
    switch (value) {
      case 'send_message':
        return ActionType.sendMessage;
      case 'create_post':
        return ActionType.createPost;
      case 'like_post':
        return ActionType.likePost;
      case 'unlike_post':
        return ActionType.unlikePost;
      case 'send_dm':
        return ActionType.sendDm;
      case 'create_comment':
        return ActionType.createComment;
      default:
        throw ArgumentError('Unknown action type: $value');
    }
  }
}

/// Represents an action queued while offline
class OfflineAction {
  final String id;
  final ActionType type;
  final Map<String, dynamic> payload;
  final DateTime createdAt;
  int retryCount;
  String? errorMessage;

  OfflineAction({
    required this.id,
    required this.type,
    required this.payload,
    DateTime? createdAt,
    this.retryCount = 0,
    this.errorMessage,
  }) : createdAt = createdAt ?? DateTime.now();

  /// Create from JSON
  factory OfflineAction.fromJson(Map<String, dynamic> json) {
    return OfflineAction(
      id: json['id'] ?? '',
      type: ActionTypeExtension.fromString(json['type'] ?? 'send_message'),
      payload: json['payload'] ?? {},
      createdAt: DateTime.parse(json['created_at'] ?? DateTime.now().toIso8601String()),
      retryCount: json['retry_count'] ?? 0,
      errorMessage: json['error_message'],
    );
  }

  /// Convert to JSON
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'type': type.value,
      'payload': payload,
      'created_at': createdAt.toIso8601String(),
      'retry_count': retryCount,
      'error_message': errorMessage,
    };
  }

  /// Serialize to JSON string
  String serialize() {
    return jsonEncode(toJson());
  }

  /// Deserialize from JSON string
  static OfflineAction deserialize(String jsonStr) {
    return OfflineAction.fromJson(jsonDecode(jsonStr));
  }

  /// Check if action has exceeded max retries
  bool get hasExceededRetries => retryCount >= 3;

  /// Increment retry count
  void incrementRetry() {
    retryCount++;
  }

  @override
  String toString() {
    return 'OfflineAction(id: $id, type: ${type.value}, retries: $retryCount)';
  }
}
