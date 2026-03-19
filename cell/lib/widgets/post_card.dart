import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:timeago/timeago.dart' as timeago;
import '../models/models.dart';
import '../providers/app_state.dart';
import '../theme/app_theme.dart';
import 'design_system.dart';

class PostCard extends StatefulWidget {
  final Post post;
  final VoidCallback? onTap;
  final VoidCallback? onAuthorTap;

  const PostCard({
    super.key,
    required this.post,
    this.onTap,
    this.onAuthorTap,
  });

  @override
  State<PostCard> createState() => _PostCardState();
}

class _PostCardState extends State<PostCard> with TickerProviderStateMixin {
  late AnimationController _likeController;
  late AnimationController _heartBurstController;
  late Animation<double> _heartBurstScale;
  late Animation<double> _heartBurstOpacity;

  bool _showCommentInput = false;
  bool _showHeartBurst = false;
  final _commentController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _likeController = AnimationController(
      duration: const Duration(milliseconds: 200),
      vsync: this,
    );

    _heartBurstController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );

    _heartBurstScale = TweenSequence<double>([
      TweenSequenceItem(tween: Tween(begin: 0.0, end: 1.4), weight: 30),
      TweenSequenceItem(tween: Tween(begin: 1.4, end: 1.0), weight: 20),
      TweenSequenceItem(tween: Tween(begin: 1.0, end: 1.2), weight: 25),
      TweenSequenceItem(tween: Tween(begin: 1.2, end: 0.0), weight: 25),
    ]).animate(CurvedAnimation(
      parent: _heartBurstController,
      curve: Curves.easeOut,
    ));

    _heartBurstOpacity = TweenSequence<double>([
      TweenSequenceItem(tween: Tween(begin: 0.0, end: 1.0), weight: 20),
      TweenSequenceItem(tween: Tween(begin: 1.0, end: 1.0), weight: 50),
      TweenSequenceItem(tween: Tween(begin: 1.0, end: 0.0), weight: 30),
    ]).animate(_heartBurstController);
  }

  @override
  void dispose() {
    _likeController.dispose();
    _heartBurstController.dispose();
    _commentController.dispose();
    super.dispose();
  }

  void _handleDoubleTapLike() {
    if (!widget.post.isLikedByUser) {
      _handleQuickLike();
      _showHeartBurstAnimation();
    }
  }

  void _showHeartBurstAnimation() {
    setState(() => _showHeartBurst = true);
    _heartBurstController.forward(from: 0).then((_) {
      if (mounted) setState(() => _showHeartBurst = false);
    });
  }

  void _handleQuickLike() {
    final appState = context.read<AppState>();
    final reactionType = widget.post.userReactionType ?? ReactionType.like;
    appState.likePost(widget.post, reactionType: reactionType);

    if (!widget.post.isLikedByUser) {
      _likeController.forward().then((_) => _likeController.reverse());
      HapticFeedback.lightImpact();
    }
  }

  void _handleComment() {
    if (_commentController.text.trim().isEmpty) return;

    final appState = context.read<AppState>();
    appState.commentOnPost(widget.post, _commentController.text.trim());
    _commentController.clear();
    setState(() => _showCommentInput = false);
    HapticFeedback.lightImpact();
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: widget.onTap,
      onDoubleTap: _handleDoubleTapLike,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(AppTheme.radiusMd),
          border: Border.all(color: AppTheme.border, width: 1),
        ),
        child: Stack(
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildHeader(),
                _buildContent(),
                if (widget.post.imageUrl != null) _buildMediaContent(),
                _buildReactionSummary(),
                _buildActionBar(),
                if (widget.post.recentComments.isNotEmpty) _buildCommentPreview(),
                if (_showCommentInput) _buildCommentInput(),
                const SizedBox(height: 8),
              ],
            ),
            if (_showHeartBurst) _buildHeartBurst(),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Row(
        children: [
          GestureDetector(
            onTap: widget.onAuthorTap,
            child: Stack(
              children: [
                CleanAvatar(
                  seed: widget.post.author.avatarSeed,
                  size: 40,
                ),
                Positioned(
                  right: 0,
                  bottom: 0,
                  child: Container(
                    width: 12,
                    height: 12,
                    decoration: BoxDecoration(
                      color: AppTheme.semanticGreen,
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: AppTheme.surface,
                        width: 2,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        widget.post.author.displayName,
                        style: const TextStyle(
                          fontWeight: FontWeight.w600,
                          fontSize: 13,
                          color: AppTheme.textPrimary,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 6),
                    if (widget.post.author.isAiLabeled) _buildAiBadge(),
                  ],
                ),
                const SizedBox(height: 2),
                Row(
                  children: [
                    Text(
                      widget.post.communityName,
                      style: TextStyle(
                        color: AppTheme.semanticBlue,
                        fontSize: 11,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    Container(
                      margin: const EdgeInsets.symmetric(horizontal: 6),
                      width: 3,
                      height: 3,
                      decoration: const BoxDecoration(
                        color: AppTheme.textMuted,
                        shape: BoxShape.circle,
                      ),
                    ),
                    Text(
                      timeago.format(widget.post.createdAt),
                      style: const TextStyle(
                        color: AppTheme.textMuted,
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          _buildMoreButton(),
        ],
      ),
    );
  }

  Widget _buildAiBadge() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: const Color(0xFF8B5CF6).withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(4),
      ),
      child: const Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.auto_awesome,
            size: 10,
            color: Color(0xFF8B5CF6),
          ),
          SizedBox(width: 3),
          Text(
            'AI',
            style: TextStyle(
              color: Color(0xFF8B5CF6),
              fontSize: 9,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMoreButton() {
    return GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick();
        _showPostOptions();
      },
      child: Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: AppTheme.surfaceHover,
          borderRadius: BorderRadius.circular(8),
        ),
        child: const Icon(
          Icons.more_horiz_rounded,
          color: AppTheme.textMuted,
          size: 18,
        ),
      ),
    );
  }

  void _showPostOptions() {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (context) => Container(
        decoration: const BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
        ),
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 32,
              height: 4,
              decoration: BoxDecoration(
                color: AppTheme.border,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 16),
            _buildOptionTile(Icons.bookmark_outline, 'Save Post'),
            _buildOptionTile(Icons.share_outlined, 'Share'),
            _buildOptionTile(Icons.link_outlined, 'Copy Link'),
            _buildOptionTile(Icons.flag_outlined, 'Report', isDestructive: true),
            SizedBox(height: MediaQuery.of(context).padding.bottom),
          ],
        ),
      ),
    );
  }

  Widget _buildOptionTile(IconData icon, String label, {bool isDestructive = false}) {
    return ListTile(
      leading: Icon(
        icon,
        color: isDestructive ? AppTheme.semanticRed : AppTheme.textDim,
        size: 20,
      ),
      title: Text(
        label,
        style: TextStyle(
          color: isDestructive ? AppTheme.semanticRed : AppTheme.textPrimary,
          fontSize: 14,
        ),
      ),
      onTap: () {
        Navigator.pop(context);
        HapticFeedback.selectionClick();
      },
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      contentPadding: const EdgeInsets.symmetric(horizontal: 8),
    );
  }

  Widget _buildContent() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: Text(
        widget.post.content,
        style: const TextStyle(
          fontSize: 14,
          height: 1.5,
          color: AppTheme.textPrimary,
        ),
      ),
    );
  }

  Widget _buildMediaContent() {
    return Container(
      margin: const EdgeInsets.only(top: 12, left: 12, right: 12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.border, width: 1),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(7),
        child: Image.network(
          widget.post.imageUrl!,
          fit: BoxFit.cover,
          errorBuilder: (context, error, stackTrace) => Container(
            height: 200,
            color: AppTheme.surfaceHover,
            child: const Center(
              child: Icon(Icons.image_not_supported, color: AppTheme.textMuted),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildReactionSummary() {
    if (widget.post.totalReactionCount == 0) {
      return const SizedBox(height: 8);
    }

    final topReactions = widget.post.reactionCounts.topReactions(limit: 3);

    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 0),
      child: Row(
        children: [
          SizedBox(
            width: topReactions.length * 16.0 + 8,
            height: 20,
            child: Stack(
              children: [
                for (int i = 0; i < topReactions.length; i++)
                  Positioned(
                    left: i * 12.0,
                    child: Container(
                      padding: const EdgeInsets.all(2),
                      decoration: BoxDecoration(
                        color: AppTheme.surface,
                        shape: BoxShape.circle,
                        border: Border.all(color: AppTheme.border, width: 1),
                      ),
                      child: Text(
                        topReactions[i].key.emoji,
                        style: const TextStyle(fontSize: 10),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          Text(
            '${widget.post.totalReactionCount}',
            style: const TextStyle(
              color: AppTheme.textMuted,
              fontSize: 12,
              fontWeight: FontWeight.w500,
            ),
          ),
          const Spacer(),
          if (widget.post.commentCount > 0)
            Text(
              '${widget.post.commentCount} comments',
              style: const TextStyle(
                color: AppTheme.textMuted,
                fontSize: 11,
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildActionBar() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      padding: const EdgeInsets.symmetric(vertical: 4),
      decoration: const BoxDecoration(
        border: Border(
          top: BorderSide(color: AppTheme.borderSubtle, width: 1),
        ),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: [
          _buildLikeButton(),
          _ActionButton(
            icon: Icons.chat_bubble_outline_rounded,
            label: widget.post.commentCount > 0 ? widget.post.commentCount.toString() : 'Comment',
            onTap: () => setState(() => _showCommentInput = !_showCommentInput),
          ),
          _ActionButton(
            icon: Icons.share_outlined,
            label: 'Share',
            onTap: () => HapticFeedback.selectionClick(),
          ),
          _ActionButton(
            icon: Icons.bookmark_outline_rounded,
            label: 'Save',
            onTap: () => HapticFeedback.selectionClick(),
          ),
        ],
      ),
    );
  }

  Widget _buildLikeButton() {
    final hasReaction = widget.post.isLikedByUser && widget.post.userReactionType != null;
    final reactionType = widget.post.userReactionType ?? ReactionType.like;

    return GestureDetector(
      onTap: _handleQuickLike,
      child: AnimatedBuilder(
        animation: _likeController,
        builder: (context, child) {
          return Transform.scale(
            scale: 1.0 + (_likeController.value * 0.2),
            child: child,
          );
        },
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: hasReaction
                ? _getReactionColor(reactionType).withValues(alpha: 0.1)
                : Colors.transparent,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (hasReaction)
                Text(reactionType.emoji, style: const TextStyle(fontSize: 18))
              else
                Icon(
                  widget.post.isLikedByUser ? Icons.favorite : Icons.favorite_outline_rounded,
                  size: 18,
                  color: widget.post.isLikedByUser ? AppTheme.semanticRed : AppTheme.textDim,
                ),
              const SizedBox(width: 6),
              Text(
                widget.post.totalReactionCount > 0 ? widget.post.totalReactionCount.toString() : 'Like',
                style: TextStyle(
                  color: hasReaction ? _getReactionColor(reactionType) : AppTheme.textDim,
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Color _getReactionColor(ReactionType type) {
    switch (type) {
      case ReactionType.like:
        return AppTheme.semanticRed;
      case ReactionType.love:
        return Colors.pink;
      case ReactionType.haha:
        return AppTheme.semanticYellow;
      case ReactionType.wow:
        return Colors.orange;
      case ReactionType.sad:
        return AppTheme.semanticBlue;
      case ReactionType.fire:
        return Colors.deepOrange;
      case ReactionType.clap:
        return AppTheme.semanticGreen;
    }
  }

  Widget _buildCommentPreview() {
    return Column(
      children: [
        const Divider(color: AppTheme.borderSubtle, height: 1),
        ...widget.post.recentComments.take(2).map((comment) => _CommentTile(comment: comment)),
        if (widget.post.commentCount > 2)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: GestureDetector(
              onTap: widget.onTap,
              child: Text(
                'View all ${widget.post.commentCount} comments',
                style: const TextStyle(
                  color: AppTheme.textMuted,
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildCommentInput() {
    return Container(
      margin: const EdgeInsets.fromLTRB(12, 0, 12, 8),
      decoration: BoxDecoration(
        color: AppTheme.surfaceHover,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.border, width: 1),
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _commentController,
              decoration: const InputDecoration(
                hintText: 'Write a comment...',
                hintStyle: TextStyle(color: AppTheme.textMuted, fontSize: 13),
                contentPadding: EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                border: InputBorder.none,
              ),
              style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary),
              onSubmitted: (_) => _handleComment(),
            ),
          ),
          GestureDetector(
            onTap: _handleComment,
            child: Container(
              margin: const EdgeInsets.all(4),
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppTheme.semanticBlue,
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.send_rounded,
                color: Colors.white,
                size: 16,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeartBurst() {
    return Positioned.fill(
      child: Center(
        child: AnimatedBuilder(
          animation: _heartBurstController,
          builder: (context, child) {
            return Opacity(
              opacity: _heartBurstOpacity.value,
              child: Transform.scale(
                scale: _heartBurstScale.value,
                child: const Icon(
                  Icons.favorite,
                  color: AppTheme.semanticRed,
                  size: 80,
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}

class _ActionButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _ActionButton({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 18,
              color: AppTheme.textDim,
            ),
            const SizedBox(width: 6),
            Text(
              label,
              style: const TextStyle(
                color: AppTheme.textDim,
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CommentTile extends StatelessWidget {
  final Comment comment;

  const _CommentTile({required this.comment});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CleanAvatar(
            seed: comment.author.avatarSeed,
            size: 28,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppTheme.surfaceHover,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(
                        comment.author.displayName,
                        style: const TextStyle(
                          fontWeight: FontWeight.w600,
                          fontSize: 12,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        timeago.format(comment.createdAt, locale: 'en_short'),
                        style: const TextStyle(
                          color: AppTheme.textMuted,
                          fontSize: 10,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    comment.content,
                    style: const TextStyle(
                      fontSize: 12,
                      height: 1.4,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
