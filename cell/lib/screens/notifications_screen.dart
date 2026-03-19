import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:timeago/timeago.dart' as timeago;
import '../models/notification_model.dart';
import '../providers/app_state.dart';
import '../theme/app_theme.dart';
import '../widgets/avatar_widget.dart';
import 'post_detail_screen.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen>
    with TickerProviderStateMixin {
  bool _isLoading = true;
  int _selectedFilter = 0;
  final List<String> _filters = ['All', 'Likes', 'Comments', 'Mentions', 'Follows'];

  late AnimationController _fadeController;
  late Animation<double> _fadeAnimation;
  late AnimationController _glowController;
  late Animation<double> _glowAnimation;
  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;

  @override
  void initState() {
    super.initState();
    _fadeController = AnimationController(
      duration: const Duration(milliseconds: 500),
      vsync: this,
    );
    _fadeAnimation = CurvedAnimation(
      parent: _fadeController,
      curve: Curves.easeOut,
    );

    _glowController = AnimationController(
      duration: const Duration(milliseconds: 2000),
      vsync: this,
    )..repeat(reverse: true);
    _glowAnimation = Tween<double>(begin: 0.4, end: 1.0).animate(
      CurvedAnimation(parent: _glowController, curve: Curves.easeInOut),
    );

    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    )..repeat(reverse: true);
    _pulseAnimation = Tween<double>(begin: 0.8, end: 1.2).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );

    _loadNotifications();
  }

  @override
  void dispose() {
    _fadeController.dispose();
    _glowController.dispose();
    _pulseController.dispose();
    super.dispose();
  }

  Future<void> _loadNotifications() async {
    setState(() => _isLoading = true);
    final appState = context.read<AppState>();
    await appState.loadNotifications();
    setState(() => _isLoading = false);
    _fadeController.forward();
  }

  Future<void> _markAllAsRead() async {
    final appState = context.read<AppState>();
    await appState.markAllNotificationsRead();
  }

  List<NotificationModel> _filterNotifications(List<NotificationModel> notifications) {
    if (_selectedFilter == 0) return notifications;

    NotificationType? filterType;
    switch (_selectedFilter) {
      case 1:
        filterType = NotificationType.like;
        break;
      case 2:
        filterType = NotificationType.comment;
        break;
      case 3:
        filterType = NotificationType.mention;
        break;
      case 4:
        filterType = NotificationType.follow;
        break;
    }

    if (filterType == null) return notifications;
    return notifications.where((n) => n.type == filterType).toList();
  }

  Map<String, List<NotificationModel>> _groupNotificationsByDate(
      List<NotificationModel> notifications) {
    final Map<String, List<NotificationModel>> grouped = {};
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final yesterday = today.subtract(const Duration(days: 1));

    for (final notification in notifications) {
      final notifDate = DateTime(
        notification.createdAt.year,
        notification.createdAt.month,
        notification.createdAt.day,
      );

      String key;
      if (notifDate == today) {
        key = 'Today';
      } else if (notifDate == yesterday) {
        key = 'Yesterday';
      } else if (notifDate.isAfter(today.subtract(const Duration(days: 7)))) {
        key = 'This Week';
      } else {
        key = 'Earlier';
      }

      grouped.putIfAbsent(key, () => []);
      grouped[key]!.add(notification);
    }

    return grouped;
  }

  void _handleNotificationTap(NotificationModel notification) {
    final appState = context.read<AppState>();
    appState.markNotificationRead(notification.id);

    switch (notification.type) {
      case NotificationType.like:
      case NotificationType.comment:
      case NotificationType.mention:
        if (notification.targetId != null) {
          _navigateToPost(notification.targetId!);
        }
        break;
      case NotificationType.dm:
        Navigator.pop(context);
        break;
      case NotificationType.follow:
        break;
    }
  }

  void _navigateToPost(String postId) async {
    final appState = context.read<AppState>();
    final posts = appState.posts;
    final post = posts.where((p) => p.id == postId).firstOrNull;

    if (post != null) {
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (context) => PostDetailScreen(post: post),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              AppTheme.cyberBlack,
              AppTheme.cyberDark,
              AppTheme.cyberDeeper,
            ],
          ),
        ),
        child: Stack(
          children: [
            // Background orbs
            ...List.generate(5, (index) => _buildFloatingOrb(index)),

            // Main content
            SafeArea(
              child: Column(
                children: [
                  _buildHeader(),
                  _buildFilterTabs(),
                  Expanded(
                    child: _buildNotificationsList(),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFloatingOrb(int index) {
    final random = math.Random(index + 5);
    final size = 100.0 + random.nextDouble() * 150;
    final left = random.nextDouble() * MediaQuery.of(context).size.width;
    final top = random.nextDouble() * MediaQuery.of(context).size.height;

    return Positioned(
      left: left - size / 2,
      top: top - size / 2,
      child: AnimatedBuilder(
        animation: _glowAnimation,
        builder: (context, child) {
          return Container(
            width: size,
            height: size,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(
                colors: [
                  (index.isEven ? AppTheme.neonCyan : AppTheme.neonMagenta)
                      .withValues(alpha: 0.03 * _glowAnimation.value),
                  Colors.transparent,
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.glassBg,
        border: Border(
          bottom: BorderSide(
            color: AppTheme.neonCyan.withValues(alpha: 0.1),
          ),
        ),
      ),
      child: Row(
        children: [
          // Back button
          GestureDetector(
            onTap: () => Navigator.pop(context),
            child: Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: AppTheme.cyberSurface,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppTheme.glassBorder),
              ),
              child: const Icon(
                Icons.arrow_back,
                color: AppTheme.textSecondary,
                size: 22,
              ),
            ),
          ),
          const SizedBox(width: 16),

          // Title
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                ShaderMask(
                  shaderCallback: (bounds) =>
                      AppTheme.primaryGradient.createShader(bounds),
                  child: const Text(
                    'Notifications',
                    style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                ),
                Consumer<AppState>(
                  builder: (context, appState, child) {
                    final unreadCount =
                        appState.notifications.where((n) => !n.isRead).length;
                    if (unreadCount == 0) return const SizedBox.shrink();
                    return Text(
                      '$unreadCount unread',
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppTheme.neonCyan,
                      ),
                    );
                  },
                ),
              ],
            ),
          ),

          // Mark all read button
          Consumer<AppState>(
            builder: (context, appState, child) {
              final hasUnread = appState.notifications.any((n) => !n.isRead);
              if (!hasUnread) return const SizedBox.shrink();

              return GestureDetector(
                onTap: _markAllAsRead,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                  decoration: BoxDecoration(
                    gradient: AppTheme.primaryGradient,
                    borderRadius: BorderRadius.circular(20),
                    boxShadow: AppTheme.cyanGlow(intensity: 0.3),
                  ),
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.done_all,
                        color: Colors.white,
                        size: 16,
                      ),
                      SizedBox(width: 6),
                      Text(
                        'Read all',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildFilterTabs() {
    return Container(
      height: 56,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        itemCount: _filters.length,
        itemBuilder: (context, index) {
          final isSelected = _selectedFilter == index;
          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: GestureDetector(
              onTap: () => setState(() => _selectedFilter = index),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                padding: const EdgeInsets.symmetric(horizontal: 16),
                decoration: BoxDecoration(
                  gradient: isSelected ? AppTheme.primaryGradient : null,
                  color: isSelected ? null : AppTheme.cyberSurface,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: isSelected
                        ? Colors.transparent
                        : AppTheme.neonCyan.withValues(alpha: 0.2),
                  ),
                  boxShadow: isSelected
                      ? AppTheme.cyanGlow(intensity: 0.3)
                      : null,
                ),
                child: Center(
                  child: Text(
                    _filters[index],
                    style: TextStyle(
                      color: isSelected ? Colors.white : AppTheme.textSecondary,
                      fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                      fontSize: 13,
                    ),
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildNotificationsList() {
    return Consumer<AppState>(
      builder: (context, appState, child) {
        if (_isLoading) {
          return _buildLoadingState();
        }

        final filteredNotifications = _filterNotifications(appState.notifications);

        if (filteredNotifications.isEmpty) {
          return _buildEmptyState();
        }

        final groupedNotifications =
            _groupNotificationsByDate(filteredNotifications);
        final groups = ['Today', 'Yesterday', 'This Week', 'Earlier']
            .where((key) => groupedNotifications.containsKey(key))
            .toList();

        return FadeTransition(
          opacity: _fadeAnimation,
          child: RefreshIndicator(
            onRefresh: _loadNotifications,
            color: AppTheme.neonCyan,
            backgroundColor: AppTheme.cyberSurface,
            child: ListView.builder(
              padding: const EdgeInsets.only(bottom: 100),
              itemCount: groups.fold<int>(0, (sum, key) {
                return sum + 1 + (groupedNotifications[key]?.length ?? 0);
              }),
              itemBuilder: (context, index) {
                int currentIndex = 0;
                for (final group in groups) {
                  final notifications = groupedNotifications[group]!;

                  if (index == currentIndex) {
                    return _buildSectionHeader(group);
                  }
                  currentIndex++;

                  if (index < currentIndex + notifications.length) {
                    final notifIndex = index - currentIndex;
                    return _buildNotificationTile(notifications[notifIndex]);
                  }
                  currentIndex += notifications.length;
                }
                return const SizedBox.shrink();
              },
            ),
          ),
        );
      },
    );
  }

  Widget _buildLoadingState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          AnimatedBuilder(
            animation: _pulseAnimation,
            builder: (context, child) {
              return Transform.scale(
                scale: _pulseAnimation.value,
                child: Container(
                  width: 60,
                  height: 60,
                  decoration: BoxDecoration(
                    gradient: AppTheme.primaryGradient,
                    shape: BoxShape.circle,
                    boxShadow: AppTheme.cyanGlow(intensity: 0.5),
                  ),
                  child: const Icon(
                    Icons.notifications_outlined,
                    color: Colors.white,
                    size: 28,
                  ),
                ),
              );
            },
          ),
          const SizedBox(height: 20),
          const Text(
            'Loading notifications...',
            style: TextStyle(
              color: AppTheme.textMuted,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          AnimatedBuilder(
            animation: _glowAnimation,
            builder: (context, child) {
              return Container(
                padding: const EdgeInsets.all(32),
                decoration: BoxDecoration(
                  color: AppTheme.cyberSurface,
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: AppTheme.neonCyan
                          .withValues(alpha: 0.2 * _glowAnimation.value),
                      blurRadius: 30,
                      spreadRadius: 0,
                    ),
                  ],
                ),
                child: ShaderMask(
                  shaderCallback: (bounds) =>
                      AppTheme.primaryGradient.createShader(bounds),
                  child: const Icon(
                    Icons.notifications_off_outlined,
                    size: 56,
                    color: Colors.white,
                  ),
                ),
              );
            },
          ),
          const SizedBox(height: 28),
          const Text(
            'No notifications yet',
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.bold,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 10),
          const Text(
            'When companions interact with your content,\nyou\'ll see it here.',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: AppTheme.textMuted,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title) {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 12),
      child: Row(
        children: [
          Container(
            width: 4,
            height: 16,
            decoration: BoxDecoration(
              gradient: AppTheme.primaryGradient,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 10),
          Text(
            title.toUpperCase(),
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppTheme.textMuted,
              letterSpacing: 1.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNotificationTile(NotificationModel notification) {
    final iconData = _getNotificationIcon(notification.type);
    final iconColor = _getNotificationColor(notification.type);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: GestureDetector(
        onTap: () => _handleNotificationTap(notification),
        child: AnimatedBuilder(
          animation: _glowAnimation,
          builder: (context, child) {
            return Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                gradient: notification.isRead
                    ? null
                    : LinearGradient(
                        colors: [
                          iconColor.withValues(alpha: 0.08),
                          iconColor.withValues(alpha: 0.02),
                        ],
                        begin: Alignment.centerLeft,
                        end: Alignment.centerRight,
                      ),
                color: notification.isRead ? AppTheme.glassBg : null,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: notification.isRead
                      ? AppTheme.glassBorder
                      : iconColor.withValues(alpha: 0.3),
                ),
                boxShadow: !notification.isRead
                    ? [
                        BoxShadow(
                          color: iconColor
                              .withValues(alpha: 0.15 * _glowAnimation.value),
                          blurRadius: 16,
                          spreadRadius: -4,
                        ),
                      ]
                    : null,
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Type icon
                  Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      color: iconColor.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: iconColor.withValues(alpha: 0.3),
                      ),
                    ),
                    child: Icon(
                      iconData,
                      size: 20,
                      color: iconColor,
                    ),
                  ),
                  const SizedBox(width: 12),

                  // Avatar
                  if (notification.actorAvatarSeed != null) ...[
                    AvatarWidget(
                      seed: notification.actorAvatarSeed!,
                      size: 40,
                    ),
                    const SizedBox(width: 12),
                  ],

                  // Content
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        RichText(
                          text: TextSpan(
                            style: const TextStyle(
                              fontSize: 14,
                              height: 1.4,
                              color: AppTheme.textPrimary,
                            ),
                            children: [
                              TextSpan(
                                text: notification.actorName ?? 'Someone',
                                style: TextStyle(
                                  fontWeight: FontWeight.w600,
                                  color: notification.isRead
                                      ? AppTheme.textSecondary
                                      : AppTheme.textPrimary,
                                ),
                              ),
                              TextSpan(
                                text: ' ${notification.message}',
                                style: TextStyle(
                                  color: notification.isRead
                                      ? AppTheme.textMuted
                                      : AppTheme.textSecondary,
                                ),
                              ),
                            ],
                          ),
                        ),
                        if (notification.targetPreview != null) ...[
                          const SizedBox(height: 8),
                          Container(
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: AppTheme.cyberSurface.withValues(alpha: 0.5),
                              borderRadius: BorderRadius.circular(10),
                              border: Border.all(
                                color: AppTheme.glassBorder,
                              ),
                            ),
                            child: Text(
                              notification.targetPreview!,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                fontSize: 12,
                                color: AppTheme.textMuted,
                                fontStyle: FontStyle.italic,
                              ),
                            ),
                          ),
                        ],
                        const SizedBox(height: 6),
                        Text(
                          timeago.format(notification.createdAt),
                          style: const TextStyle(
                            fontSize: 11,
                            color: AppTheme.textMuted,
                          ),
                        ),
                      ],
                    ),
                  ),

                  // Unread indicator
                  if (!notification.isRead)
                    AnimatedBuilder(
                      animation: _pulseAnimation,
                      builder: (context, child) {
                        return Container(
                          width: 10,
                          height: 10,
                          margin: const EdgeInsets.only(left: 8, top: 4),
                          decoration: BoxDecoration(
                            gradient: AppTheme.primaryGradient,
                            shape: BoxShape.circle,
                            boxShadow: [
                              BoxShadow(
                                color: AppTheme.neonCyan.withValues(
                                    alpha: 0.6 * (_pulseAnimation.value - 0.8) / 0.4),
                                blurRadius: 8,
                                spreadRadius: 2,
                              ),
                            ],
                          ),
                        );
                      },
                    ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }

  IconData _getNotificationIcon(NotificationType type) {
    switch (type) {
      case NotificationType.like:
        return Icons.favorite;
      case NotificationType.comment:
        return Icons.chat_bubble;
      case NotificationType.mention:
        return Icons.alternate_email;
      case NotificationType.dm:
        return Icons.mail;
      case NotificationType.follow:
        return Icons.person_add;
    }
  }

  Color _getNotificationColor(NotificationType type) {
    switch (type) {
      case NotificationType.like:
        return AppTheme.neonMagenta;
      case NotificationType.comment:
        return AppTheme.neonCyan;
      case NotificationType.mention:
        return AppTheme.neonAmber;
      case NotificationType.dm:
        return AppTheme.neonPurple;
      case NotificationType.follow:
        return AppTheme.neonGreen;
    }
  }
}
