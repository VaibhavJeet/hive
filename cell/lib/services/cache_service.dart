// Cache service for local data storage with TTL support

import 'dart:async';
import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter/foundation.dart';

/// Represents cached data with metadata
class CachedData {
  final dynamic data;
  final DateTime cachedAt;
  final Duration ttl;

  CachedData({
    required this.data,
    required this.cachedAt,
    required this.ttl,
  });

  bool get isExpired => DateTime.now().difference(cachedAt) > ttl;

  /// Get remaining time before expiration
  Duration get remainingTtl {
    final elapsed = DateTime.now().difference(cachedAt);
    final remaining = ttl - elapsed;
    return remaining.isNegative ? Duration.zero : remaining;
  }

  /// Get expiration time
  DateTime get expiresAt => cachedAt.add(ttl);

  /// Get age of cached data
  Duration get age => DateTime.now().difference(cachedAt);

  factory CachedData.fromJson(Map<String, dynamic> json) {
    return CachedData(
      data: json['data'],
      cachedAt: DateTime.parse(json['cached_at']),
      ttl: Duration(milliseconds: json['ttl_ms']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'data': data,
      'cached_at': cachedAt.toIso8601String(),
      'ttl_ms': ttl.inMilliseconds,
    };
  }
}

/// Metadata about a cached item (without the actual data)
class CacheMetadata {
  final String key;
  final DateTime cachedAt;
  final Duration ttl;
  final bool isExpired;
  final Duration remainingTtl;
  final DateTime expiresAt;

  CacheMetadata({
    required this.key,
    required this.cachedAt,
    required this.ttl,
    required this.isExpired,
    required this.remainingTtl,
    required this.expiresAt,
  });

  factory CacheMetadata.fromCachedData(String key, CachedData data) {
    return CacheMetadata(
      key: key,
      cachedAt: data.cachedAt,
      ttl: data.ttl,
      isExpired: data.isExpired,
      remainingTtl: data.remainingTtl,
      expiresAt: data.expiresAt,
    );
  }
}

/// Service for caching data locally using SharedPreferences and file storage
class CacheService {
  static CacheService? _instance;
  SharedPreferences? _prefs;
  bool _initialized = false;

  // Cache key prefix
  static const String _cachePrefix = 'cache_';

  // Default TTLs
  static const Duration defaultTtl = Duration(hours: 1);
  static const Duration feedTtl = Duration(minutes: 30);
  static const Duration conversationsTtl = Duration(hours: 2);
  static const Duration communitiesTtl = Duration(hours: 6);

  // Auto-cleanup configuration
  static const Duration _cleanupInterval = Duration(minutes: 15);
  Timer? _cleanupTimer;

  CacheService._();

  static CacheService get instance {
    _instance ??= CacheService._();
    return _instance!;
  }

  /// Initialize the cache service
  Future<void> initialize() async {
    if (_initialized) return;
    _prefs = await SharedPreferences.getInstance();
    _initialized = true;

    // Start automatic cleanup timer
    _startAutoCleanup();

    // Perform initial cleanup of any expired items
    clearExpiredCache().then((count) {
      if (count > 0) {
        debugPrint('CacheService: Cleaned up $count expired items on init');
      }
    });
  }

  /// Start automatic cleanup timer
  void _startAutoCleanup() {
    _cleanupTimer?.cancel();
    _cleanupTimer = Timer.periodic(_cleanupInterval, (_) async {
      final count = await clearExpiredCache();
      if (count > 0) {
        debugPrint('CacheService: Auto-cleaned $count expired items');
      }
    });
  }

  /// Stop automatic cleanup timer
  void stopAutoCleanup() {
    _cleanupTimer?.cancel();
    _cleanupTimer = null;
  }

  /// Dispose the cache service
  void dispose() {
    stopAutoCleanup();
  }

  /// Ensure service is initialized
  Future<void> _ensureInitialized() async {
    if (!_initialized) {
      await initialize();
    }
  }

  /// Cache data with a key and TTL
  Future<bool> cacheData(String key, dynamic data, {Duration? ttl}) async {
    await _ensureInitialized();

    try {
      final effectiveTtl = ttl ?? defaultTtl;
      final cachedData = CachedData(
        data: data,
        cachedAt: DateTime.now(),
        ttl: effectiveTtl,
      );

      final jsonStr = jsonEncode(cachedData.toJson());
      return await _prefs!.setString('$_cachePrefix$key', jsonStr);
    } catch (e) {
      debugPrint('CacheService: Failed to cache data for key $key: $e');
      return false;
    }
  }

  /// Get cached data by key, returns null if expired or not found
  Future<dynamic> getCachedData(String key, {bool ignoreExpiry = false}) async {
    await _ensureInitialized();

    try {
      final jsonStr = _prefs!.getString('$_cachePrefix$key');
      if (jsonStr == null) return null;

      final cachedData = CachedData.fromJson(jsonDecode(jsonStr));

      if (!ignoreExpiry && cachedData.isExpired) {
        // Data expired, remove it
        await _prefs!.remove('$_cachePrefix$key');
        return null;
      }

      return cachedData.data;
    } catch (e) {
      debugPrint('CacheService: Failed to get cached data for key $key: $e');
      return null;
    }
  }

  /// Check if cached data exists and is valid
  Future<bool> hasCachedData(String key) async {
    await _ensureInitialized();

    try {
      final jsonStr = _prefs!.getString('$_cachePrefix$key');
      if (jsonStr == null) return false;

      final cachedData = CachedData.fromJson(jsonDecode(jsonStr));
      return !cachedData.isExpired;
    } catch (e) {
      return false;
    }
  }

  /// Remove cached data by key
  Future<bool> removeCachedData(String key) async {
    await _ensureInitialized();
    return await _prefs!.remove('$_cachePrefix$key');
  }

  /// Clear all cached data
  Future<void> clearCache() async {
    await _ensureInitialized();

    final keys = _prefs!.getKeys().where((k) => k.startsWith(_cachePrefix));
    for (final key in keys) {
      await _prefs!.remove(key);
    }
  }

  /// Clear expired cache entries
  Future<int> clearExpiredCache() async {
    await _ensureInitialized();

    int clearedCount = 0;
    final keys = _prefs!.getKeys().where((k) => k.startsWith(_cachePrefix)).toList();

    for (final key in keys) {
      try {
        final jsonStr = _prefs!.getString(key);
        if (jsonStr == null) continue;

        final cachedData = CachedData.fromJson(jsonDecode(jsonStr));
        if (cachedData.isExpired) {
          await _prefs!.remove(key);
          clearedCount++;
        }
      } catch (e) {
        // Remove corrupted entries
        await _prefs!.remove(key);
        clearedCount++;
      }
    }

    return clearedCount;
  }

  // ========================================================================
  // CACHE INVALIDATION METHODS
  // ========================================================================

  /// Invalidate (remove) multiple cache keys at once
  Future<int> invalidateKeys(List<String> keys) async {
    await _ensureInitialized();

    int removedCount = 0;
    for (final key in keys) {
      final removed = await _prefs!.remove('$_cachePrefix$key');
      if (removed) removedCount++;
    }

    debugPrint('CacheService: Invalidated $removedCount of ${keys.length} keys');
    return removedCount;
  }

  /// Invalidate all cache entries matching a prefix pattern
  /// Example: invalidateByPrefix('feed_') removes all feed caches
  Future<int> invalidateByPrefix(String prefix) async {
    await _ensureInitialized();

    final fullPrefix = '$_cachePrefix$prefix';
    final keysToRemove = _prefs!.getKeys()
        .where((k) => k.startsWith(fullPrefix))
        .toList();

    int removedCount = 0;
    for (final key in keysToRemove) {
      await _prefs!.remove(key);
      removedCount++;
    }

    debugPrint('CacheService: Invalidated $removedCount keys with prefix "$prefix"');
    return removedCount;
  }

  /// Invalidate all cache entries matching a pattern (supports * wildcard)
  /// Example: invalidateByPattern('chat_*_messages')
  Future<int> invalidateByPattern(String pattern) async {
    await _ensureInitialized();

    // Convert simple wildcard pattern to regex
    final regexPattern = pattern
        .replaceAll('.', '\\.')
        .replaceAll('*', '.*');
    final regex = RegExp('^$_cachePrefix$regexPattern\$');

    final keysToRemove = _prefs!.getKeys()
        .where((k) => regex.hasMatch(k))
        .toList();

    int removedCount = 0;
    for (final key in keysToRemove) {
      await _prefs!.remove(key);
      removedCount++;
    }

    debugPrint('CacheService: Invalidated $removedCount keys matching pattern "$pattern"');
    return removedCount;
  }

  /// Invalidate all feed-related caches
  Future<int> invalidateAllFeeds() async {
    return await invalidateByPrefix('feed_');
  }

  /// Invalidate all chat-related caches
  Future<int> invalidateAllChats() async {
    return await invalidateByPrefix('chat_');
  }

  /// Invalidate all DM-related caches
  Future<int> invalidateAllDMs() async {
    return await invalidateByPrefix('dm_');
  }

  /// Invalidate all conversation-related caches
  Future<int> invalidateAllConversations() async {
    return await invalidateByPrefix('conversations_');
  }

  /// Refresh a cached item's TTL without changing the data
  Future<bool> refreshTtl(String key, {Duration? ttl}) async {
    await _ensureInitialized();

    try {
      final jsonStr = _prefs!.getString('$_cachePrefix$key');
      if (jsonStr == null) return false;

      final cachedData = CachedData.fromJson(jsonDecode(jsonStr));
      final newCachedData = CachedData(
        data: cachedData.data,
        cachedAt: DateTime.now(),
        ttl: ttl ?? cachedData.ttl,
      );

      final newJsonStr = jsonEncode(newCachedData.toJson());
      return await _prefs!.setString('$_cachePrefix$key', newJsonStr);
    } catch (e) {
      debugPrint('CacheService: Failed to refresh TTL for key $key: $e');
      return false;
    }
  }

  // ========================================================================
  // CACHE METADATA METHODS
  // ========================================================================

  /// Get metadata for a cached item without loading the data
  Future<CacheMetadata?> getCacheMetadata(String key) async {
    await _ensureInitialized();

    try {
      final jsonStr = _prefs!.getString('$_cachePrefix$key');
      if (jsonStr == null) return null;

      final cachedData = CachedData.fromJson(jsonDecode(jsonStr));
      return CacheMetadata.fromCachedData(key, cachedData);
    } catch (e) {
      debugPrint('CacheService: Failed to get metadata for key $key: $e');
      return null;
    }
  }

  /// Get metadata for all cached items
  Future<List<CacheMetadata>> getAllCacheMetadata() async {
    await _ensureInitialized();

    final metadataList = <CacheMetadata>[];
    final keys = _prefs!.getKeys().where((k) => k.startsWith(_cachePrefix));

    for (final fullKey in keys) {
      try {
        final jsonStr = _prefs!.getString(fullKey);
        if (jsonStr == null) continue;

        final key = fullKey.substring(_cachePrefix.length);
        final cachedData = CachedData.fromJson(jsonDecode(jsonStr));
        metadataList.add(CacheMetadata.fromCachedData(key, cachedData));
      } catch (e) {
        // Skip corrupted entries
        continue;
      }
    }

    return metadataList;
  }

  /// Get all cache keys
  Future<List<String>> getAllCacheKeys() async {
    await _ensureInitialized();

    return _prefs!.getKeys()
        .where((k) => k.startsWith(_cachePrefix))
        .map((k) => k.substring(_cachePrefix.length))
        .toList();
  }

  /// Get all expired cache keys
  Future<List<String>> getExpiredCacheKeys() async {
    await _ensureInitialized();

    final expiredKeys = <String>[];
    final keys = _prefs!.getKeys().where((k) => k.startsWith(_cachePrefix));

    for (final fullKey in keys) {
      try {
        final jsonStr = _prefs!.getString(fullKey);
        if (jsonStr == null) continue;

        final cachedData = CachedData.fromJson(jsonDecode(jsonStr));
        if (cachedData.isExpired) {
          expiredKeys.add(fullKey.substring(_cachePrefix.length));
        }
      } catch (e) {
        // Include corrupted entries as "expired"
        expiredKeys.add(fullKey.substring(_cachePrefix.length));
      }
    }

    return expiredKeys;
  }

  /// Check remaining TTL for a cached item
  Future<Duration?> getRemainingTtl(String key) async {
    final metadata = await getCacheMetadata(key);
    return metadata?.remainingTtl;
  }

  /// Get approximate cache size in bytes
  Future<int> getCacheSize() async {
    await _ensureInitialized();

    int totalSize = 0;
    final keys = _prefs!.getKeys().where((k) => k.startsWith(_cachePrefix));

    for (final key in keys) {
      final value = _prefs!.getString(key);
      if (value != null) {
        totalSize += value.length * 2; // Approximate UTF-16 size
      }
    }

    return totalSize;
  }

  /// Get formatted cache size string
  Future<String> getFormattedCacheSize() async {
    final bytes = await getCacheSize();
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  /// Get count of cached items
  Future<int> getCacheCount() async {
    await _ensureInitialized();
    return _prefs!.getKeys().where((k) => k.startsWith(_cachePrefix)).length;
  }

  /// Cache a list of items with serialization
  Future<bool> cacheList<T>(
    String key,
    List<T> items,
    Map<String, dynamic> Function(T item) toJson, {
    Duration? ttl,
  }) async {
    final jsonList = items.map((item) => toJson(item)).toList();
    return await cacheData(key, jsonList, ttl: ttl);
  }

  /// Get cached list with deserialization
  Future<List<T>?> getCachedList<T>(
    String key,
    T Function(Map<String, dynamic> json) fromJson, {
    bool ignoreExpiry = false,
  }) async {
    final data = await getCachedData(key, ignoreExpiry: ignoreExpiry);
    if (data == null) return null;

    try {
      final List<dynamic> jsonList = data as List<dynamic>;
      return jsonList.map((json) => fromJson(json as Map<String, dynamic>)).toList();
    } catch (e) {
      debugPrint('CacheService: Failed to deserialize list for key $key: $e');
      return null;
    }
  }

  // ========================================================================
  // SPECIFIC CACHE METHODS
  // ========================================================================

  /// Cache feed posts
  Future<bool> cacheFeed(List<Map<String, dynamic>> posts, {String? communityId}) async {
    final key = communityId != null ? 'feed_$communityId' : 'feed_all';
    return await cacheData(key, posts, ttl: feedTtl);
  }

  /// Get cached feed posts
  Future<List<Map<String, dynamic>>?> getCachedFeed({String? communityId, bool ignoreExpiry = false}) async {
    final key = communityId != null ? 'feed_$communityId' : 'feed_all';
    final data = await getCachedData(key, ignoreExpiry: ignoreExpiry);
    if (data == null) return null;
    return List<Map<String, dynamic>>.from(data);
  }

  /// Cache conversations
  Future<bool> cacheConversations(String userId, List<Map<String, dynamic>> conversations) async {
    return await cacheData('conversations_$userId', conversations, ttl: conversationsTtl);
  }

  /// Get cached conversations
  Future<List<Map<String, dynamic>>?> getCachedConversations(String userId, {bool ignoreExpiry = false}) async {
    final data = await getCachedData('conversations_$userId', ignoreExpiry: ignoreExpiry);
    if (data == null) return null;
    return List<Map<String, dynamic>>.from(data);
  }

  /// Cache communities
  Future<bool> cacheCommunities(List<Map<String, dynamic>> communities) async {
    return await cacheData('communities', communities, ttl: communitiesTtl);
  }

  /// Get cached communities
  Future<List<Map<String, dynamic>>?> getCachedCommunities({bool ignoreExpiry = false}) async {
    final data = await getCachedData('communities', ignoreExpiry: ignoreExpiry);
    if (data == null) return null;
    return List<Map<String, dynamic>>.from(data);
  }

  /// Cache chat messages
  Future<bool> cacheChatMessages(String communityId, List<Map<String, dynamic>> messages) async {
    return await cacheData('chat_$communityId', messages, ttl: feedTtl);
  }

  /// Get cached chat messages
  Future<List<Map<String, dynamic>>?> getCachedChatMessages(String communityId, {bool ignoreExpiry = false}) async {
    final data = await getCachedData('chat_$communityId', ignoreExpiry: ignoreExpiry);
    if (data == null) return null;
    return List<Map<String, dynamic>>.from(data);
  }

  /// Cache direct messages
  Future<bool> cacheDirectMessages(String conversationId, List<Map<String, dynamic>> messages) async {
    return await cacheData('dm_$conversationId', messages, ttl: feedTtl);
  }

  /// Get cached direct messages
  Future<List<Map<String, dynamic>>?> getCachedDirectMessages(String conversationId, {bool ignoreExpiry = false}) async {
    final data = await getCachedData('dm_$conversationId', ignoreExpiry: ignoreExpiry);
    if (data == null) return null;
    return List<Map<String, dynamic>>.from(data);
  }
}
