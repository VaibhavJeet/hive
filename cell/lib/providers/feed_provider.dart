import 'dart:io';
import 'package:flutter/foundation.dart';
import '../models/models.dart';
import '../models/offline_action.dart';
import '../services/api_service.dart';
import '../services/offline_service.dart';

class FeedProvider extends ChangeNotifier {
  final ApiService _api = ApiService();
  final OfflineService _offlineService = OfflineService.instance;

  // Feed state
  List<Post> _posts = [];
  bool _isLoadingFeed = false;
  bool _hasMorePosts = true;
  String? _error;

  // Current user ID (set from AppState)
  String? _currentUserId;

  // Selected community ID for filtering
  String? _selectedCommunityId;

  // Getters
  List<Post> get posts => _posts;
  bool get isLoadingFeed => _isLoadingFeed;
  bool get hasMorePosts => _hasMorePosts;
  String? get error => _error;

  // Setter for current user (called from AppState during initialization)
  void setCurrentUserId(String? userId) {
    _currentUserId = userId;
  }

  // Setter for selected community
  void setSelectedCommunityId(String? communityId) {
    _selectedCommunityId = communityId;
  }

  // Clear error
  void clearError() {
    _error = null;
    notifyListeners();
  }

  // Add a post to the beginning of the list (for WebSocket updates)
  void addPost(Post post) {
    _posts.insert(0, post);
    notifyListeners();
  }

  // Update post like count (for WebSocket updates)
  void updatePostLikeCount(String postId, int likeCount) {
    final index = _posts.indexWhere((p) => p.id == postId);
    if (index != -1) {
      _posts[index].likeCount = likeCount;
      notifyListeners();
    }
  }

  // Load feed
  Future<void> loadFeed({bool refresh = false}) async {
    if (_isLoadingFeed) return;

    _isLoadingFeed = true;
    if (refresh) {
      _posts = [];
      _hasMorePosts = true;
    }
    notifyListeners();

    try {
      final newPosts = await _api.getFeed(
        userId: _currentUserId,
        communityId: _selectedCommunityId,
        offset: refresh ? 0 : _posts.length,
      );

      if (refresh) {
        _posts = newPosts;
      } else {
        _posts.addAll(newPosts);
      }
      _hasMorePosts = newPosts.length >= 20;
      _error = null;
    } catch (e) {
      _error = 'Failed to load feed: $e';
    } finally {
      _isLoadingFeed = false;
      notifyListeners();
    }
  }

  // Like post
  Future<void> likePost(Post post, {ReactionType reactionType = ReactionType.like}) async {
    if (_currentUserId == null) return;

    // Optimistic update
    final wasLiked = post.isLikedByUser;
    final previousReactionType = post.userReactionType;

    if (wasLiked && post.userReactionType == reactionType) {
      // Remove reaction (toggle off)
      post.isLikedByUser = false;
      post.userReactionType = null;
      post.likeCount -= 1;
      // Update reaction counts
      final currentCount = post.reactionCounts.counts[reactionType] ?? 0;
      if (currentCount > 0) {
        post.reactionCounts.counts[reactionType] = currentCount - 1;
      }
    } else {
      // Add or change reaction
      if (wasLiked && previousReactionType != null) {
        // Changing reaction type - decrement old, increment new
        final oldCount = post.reactionCounts.counts[previousReactionType] ?? 0;
        if (oldCount > 0) {
          post.reactionCounts.counts[previousReactionType] = oldCount - 1;
        }
      } else if (!wasLiked) {
        // New reaction
        post.likeCount += 1;
      }
      post.isLikedByUser = true;
      post.userReactionType = reactionType;
      post.reactionCounts.counts[reactionType] =
          (post.reactionCounts.counts[reactionType] ?? 0) + 1;
    }
    notifyListeners();

    try {
      if (!post.isLikedByUser) {
        await _api.unlikePost(post.id, _currentUserId!);
      } else {
        await _api.likePost(post.id, _currentUserId!, reactionType: reactionType.name);
      }
    } on OfflineException {
      // Queue for later when back online
      await _offlineService.queueAction(
        !post.isLikedByUser ? ActionType.unlikePost : ActionType.likePost,
        {
          'post_id': post.id,
          'user_id': _currentUserId!,
          'reaction_type': reactionType.name,
        },
      );
      notifyListeners();
    } catch (e) {
      // Revert optimistic update on error
      post.isLikedByUser = wasLiked;
      post.userReactionType = previousReactionType;
      if (wasLiked && previousReactionType == reactionType) {
        post.likeCount += 1;
      } else if (!wasLiked) {
        post.likeCount -= 1;
      }
      _error = 'Failed to react to post: $e';
      notifyListeners();
    }
  }

  // Comment on post
  Future<void> commentOnPost(Post post, String content) async {
    if (_currentUserId == null) return;

    try {
      final comment = await _api.createComment(post.id, _currentUserId!, content);
      post.recentComments.insert(0, comment);
      post.commentCount++;
      notifyListeners();
    } on OfflineException {
      // Queue comment for later
      await _offlineService.queueAction(
        ActionType.createComment,
        {'post_id': post.id, 'user_id': _currentUserId!, 'content': content},
      );
      _error = 'Comment will be posted when back online';
      notifyListeners();
    } catch (e) {
      _error = 'Failed to comment: $e';
      notifyListeners();
    }
  }

  // Create post
  Future<Post> createPost({
    required String content,
    required String communityId,
    File? image,
  }) async {
    if (_currentUserId == null) {
      throw Exception('User not logged in');
    }

    try {
      final post = await _api.createPost(
        userId: _currentUserId!,
        communityId: communityId,
        content: content,
        image: image,
      );

      // Add to local posts list
      _posts.insert(0, post);

      // Invalidate feed cache since we have new data
      await _offlineService.invalidateFeedCache(communityId: communityId);

      notifyListeners();

      return post;
    } catch (e) {
      _error = 'Failed to create post: $e';
      notifyListeners();
      rethrow;
    }
  }

  // Load cached feed for offline mode
  Future<void> loadCachedFeed() async {
    _posts = await _offlineService.getCachedFeed();
    notifyListeners();
  }
}
