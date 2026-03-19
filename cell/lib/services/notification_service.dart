import 'dart:convert';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:http/http.dart' as http;
import '../models/notification_model.dart';

class NotificationService {
  static String get baseUrl {
    if (kIsWeb) {
      return 'http://localhost:8000';
    } else {
      return 'http://10.0.2.2:8000';
    }
  }

  final http.Client _client = http.Client();

  /// Get all notifications for a user
  Future<List<NotificationModel>> getNotifications(String userId, {int limit = 50, int offset = 0}) async {
    try {
      final params = {
        'user_id': userId,
        'limit': limit.toString(),
        'offset': offset.toString(),
      };

      final uri = Uri.parse('$baseUrl/notifications').replace(queryParameters: params);
      final response = await _client.get(uri);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        // API returns {notifications: [...], unread_count: N, total: N}
        final List<dynamic> notifications = data['notifications'] ?? data;
        return notifications.map((json) => NotificationModel.fromJson(json)).toList();
      }

      // Return empty list if no notifications
      return [];
    } catch (e) {
      // Return empty list on error (don't use mock data in production)
      return [];
    }
  }

  /// Mark a single notification as read
  Future<bool> markAsRead(String notificationId) async {
    try {
      final uri = Uri.parse('$baseUrl/notifications/$notificationId/read');
      final response = await _client.post(uri);
      return response.statusCode == 200;
    } catch (e) {
      return true; // Assume success for offline mode
    }
  }

  /// Mark all notifications as read for a user
  Future<bool> markAllRead(String userId) async {
    try {
      final params = {'user_id': userId};
      final uri = Uri.parse('$baseUrl/notifications/read-all').replace(queryParameters: params);
      final response = await _client.post(uri);
      return response.statusCode == 200;
    } catch (e) {
      return true; // Assume success for offline mode
    }
  }

  /// Get unread notification count for a user
  Future<int> getUnreadCount(String userId) async {
    try {
      final params = {'user_id': userId};
      final uri = Uri.parse('$baseUrl/notifications/unread-count').replace(queryParameters: params);
      final response = await _client.get(uri);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['count'] ?? 0;
      }
      return 0;
    } catch (e) {
      return 0;
    }
  }

  void dispose() {
    _client.close();
  }
}
