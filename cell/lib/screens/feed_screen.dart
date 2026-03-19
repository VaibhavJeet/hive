import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../providers/app_state.dart';
import '../theme/app_theme.dart';
import '../widgets/post_card.dart';
import '../widgets/design_system.dart';
import '../models/models.dart';
import 'bot_profile_screen.dart';
import 'post_detail_screen.dart';
import 'notifications_screen.dart';
import 'settings_screen.dart';

class FeedScreen extends StatefulWidget {
  const FeedScreen({super.key});

  @override
  State<FeedScreen> createState() => _FeedScreenState();
}

class _FeedScreenState extends State<FeedScreen> {
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - 200) {
      final appState = context.read<AppState>();
      if (!appState.isLoadingFeed && appState.hasMorePosts) {
        appState.loadFeed();
      }
    }
  }

  Future<void> _handleRefresh() async {
    HapticFeedback.mediumImpact();
    await context.read<AppState>().loadFeed(refresh: true);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bg,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            _buildHeader(),
            Expanded(
              child: Consumer<AppState>(
                builder: (context, appState, child) {
                  if (appState.posts.isEmpty && appState.isLoadingFeed) {
                    return _buildLoadingState();
                  }

                  if (appState.posts.isEmpty) {
                    return _buildEmptyState();
                  }

                  return RefreshIndicator(
                    onRefresh: _handleRefresh,
                    color: AppTheme.semanticBlue,
                    backgroundColor: AppTheme.surface,
                    child: CustomScrollView(
                      controller: _scrollController,
                      physics: const AlwaysScrollableScrollPhysics(),
                      slivers: [
                        // Community filter chips
                        SliverToBoxAdapter(
                          child: _buildCommunityFilter(appState),
                        ),

                        // Posts
                        SliverPadding(
                          padding: const EdgeInsets.only(top: 8, bottom: 120),
                          sliver: SliverList(
                            delegate: SliverChildBuilderDelegate(
                              (context, index) {
                                if (index == appState.posts.length) {
                                  return appState.isLoadingFeed
                                      ? _buildLoadingIndicator()
                                      : const SizedBox.shrink();
                                }

                                final post = appState.posts[index];
                                return PostCard(
                                  key: ValueKey(post.id),
                                  post: post,
                                  onTap: () => _openPostDetail(post),
                                  onAuthorTap: () => _openBotProfile(post.author),
                                );
                              },
                              childCount: appState.posts.length + 1,
                            ),
                          ),
                        ),
                      ],
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.bg,
        border: Border(
          bottom: BorderSide(color: AppTheme.border, width: 1),
        ),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: AppTheme.semanticBlue.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(
              Icons.auto_awesome,
              color: AppTheme.semanticBlue,
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'AI Social',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                  ),
                ),
                Text(
                  'Watch companions interact',
                  style: TextStyle(
                    color: AppTheme.textMuted,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
          _HeaderButton(
            icon: Icons.notifications_outlined,
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => const NotificationsScreen()),
              );
            },
            badgeCount: context.watch<AppState>().unreadNotificationCount,
          ),
          const SizedBox(width: 8),
          _HeaderButton(
            icon: Icons.settings_outlined,
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => const SettingsScreen()),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildCommunityFilter(AppState appState) {
    return SizedBox(
      height: 48,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        children: [
          _FilterChip(
            label: 'All',
            isSelected: appState.selectedCommunity == null,
            onTap: () {
              HapticFeedback.selectionClick();
              appState.selectCommunity(null);
            },
          ),
          ...appState.communities.map((community) => _FilterChip(
                label: community.name,
                isSelected: appState.selectedCommunity?.id == community.id,
                onTap: () {
                  HapticFeedback.selectionClick();
                  appState.selectCommunity(community);
                },
              )),
        ],
      ),
    );
  }

  Widget _buildLoadingState() {
    // TODO: Issue #2 - Add shimmer animation to skeleton cards
    // Install shimmer package: flutter pub add shimmer
    // Then wrap _SkeletonPostCard with Shimmer.fromColors()
    return ListView.builder(
      padding: const EdgeInsets.symmetric(vertical: 8),
      itemCount: 4,
      itemBuilder: (context, index) => const _SkeletonPostCard(),
    );
  }

  Widget _buildLoadingIndicator() {
    return const Padding(
      padding: EdgeInsets.all(24),
      child: Center(
        child: SizedBox(
          width: 24,
          height: 24,
          child: CircularProgressIndicator(
            strokeWidth: 2,
            valueColor: AlwaysStoppedAnimation(AppTheme.semanticBlue),
          ),
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return EmptyState(
      icon: Icons.article_outlined,
      title: 'No posts yet',
      description: 'Companions will start posting soon!\nPull down to refresh.',
      action: CleanButton(
        text: 'Refresh',
        icon: Icons.refresh,
        onPressed: _handleRefresh,
      ),
    );
  }

  void _openBotProfile(Author author) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => BotProfileScreen(botId: author.id),
      ),
    );
  }

  void _openPostDetail(Post post) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => PostDetailScreen(post: post),
      ),
    );
  }
}

class _HeaderButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;
  final int badgeCount;

  const _HeaderButton({
    required this.icon,
    required this.onTap,
    this.badgeCount = 0,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 40,
        height: 40,
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: AppTheme.border, width: 1),
        ),
        child: Stack(
          alignment: Alignment.center,
          children: [
            Icon(icon, size: 20, color: AppTheme.textDim),
            if (badgeCount > 0)
              Positioned(
                right: 6,
                top: 6,
                child: Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    color: AppTheme.semanticRed,
                    shape: BoxShape.circle,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final bool isSelected;
  final VoidCallback onTap;

  const _FilterChip({
    required this.label,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(right: 8),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected ? AppTheme.semanticBlue : AppTheme.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isSelected ? AppTheme.semanticBlue : AppTheme.border,
            width: 1,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected ? Colors.white : AppTheme.textDim,
            fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
            fontSize: 12,
          ),
        ),
      ),
    );
  }
}

/// Skeleton loading card for feed posts
/// TODO: Issue #2 - Wrap with Shimmer.fromColors for animation effect
class _SkeletonPostCard extends StatelessWidget {
  const _SkeletonPostCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Author row skeleton
          Row(
            children: [
              _skeletonBox(40, 40, isCircle: true),
              const SizedBox(width: 12),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _skeletonBox(100, 12),
                  const SizedBox(height: 4),
                  _skeletonBox(60, 10),
                ],
              ),
            ],
          ),
          const SizedBox(height: 12),
          // Content skeleton
          _skeletonBox(double.infinity, 14),
          const SizedBox(height: 8),
          _skeletonBox(250, 14),
          const SizedBox(height: 8),
          _skeletonBox(180, 14),
          const SizedBox(height: 16),
          // Actions row skeleton
          Row(
            children: [
              _skeletonBox(60, 24),
              const SizedBox(width: 16),
              _skeletonBox(60, 24),
              const Spacer(),
              _skeletonBox(24, 24),
            ],
          ),
        ],
      ),
    );
  }

  Widget _skeletonBox(double width, double height, {bool isCircle = false}) {
    return Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
        color: AppTheme.border.withValues(alpha: 0.5),
        borderRadius: isCircle ? null : BorderRadius.circular(4),
        shape: isCircle ? BoxShape.circle : BoxShape.rectangle,
      ),
    );
  }
}
