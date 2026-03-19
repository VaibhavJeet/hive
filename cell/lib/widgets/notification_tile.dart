import 'package:flutter/material.dart';
import 'package:timeago/timeago.dart' as timeago;
import '../models/notification_model.dart';
import '../theme/app_theme.dart';
import 'avatar_widget.dart';

class NotificationTile extends StatefulWidget {
  final NotificationModel notification;
  final VoidCallback? onTap;

  const NotificationTile({
    super.key,
    required this.notification,
    this.onTap,
  });

  @override
  State<NotificationTile> createState() => _NotificationTileState();
}

class _NotificationTileState extends State<NotificationTile>
    with SingleTickerProviderStateMixin {
  late AnimationController _glowController;
  late Animation<double> _glowAnimation;

  @override
  void initState() {
    super.initState();
    _glowController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    );

    if (!widget.notification.isRead) {
      _glowController.repeat(reverse: true);
    }

    _glowAnimation = Tween<double>(begin: 0.5, end: 1.0).animate(
      CurvedAnimation(parent: _glowController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _glowController.dispose();
    super.dispose();
  }

  @override
  void didUpdateWidget(NotificationTile oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.notification.isRead && _glowController.isAnimating) {
      _glowController.stop();
    } else if (!widget.notification.isRead && !_glowController.isAnimating) {
      _glowController.repeat(reverse: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final iconData = _getNotificationIcon();
    final iconColor = _getNotificationColor();

    return AnimatedBuilder(
      animation: _glowAnimation,
      builder: (context, child) {
        return Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: widget.onTap,
            borderRadius: BorderRadius.circular(16),
            child: Container(
              margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                gradient: widget.notification.isRead
                    ? null
                    : LinearGradient(
                        colors: [
                          iconColor.withValues(alpha: 0.08),
                          iconColor.withValues(alpha: 0.02),
                        ],
                        begin: Alignment.centerLeft,
                        end: Alignment.centerRight,
                      ),
                color: widget.notification.isRead ? AppTheme.glassBg : null,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: widget.notification.isRead
                      ? AppTheme.glassBorder
                      : iconColor.withValues(alpha: 0.3),
                ),
                boxShadow: !widget.notification.isRead
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
                  // Type icon with glow
                  _buildNotificationIcon(iconData, iconColor),
                  const SizedBox(width: 12),

                  // Avatar
                  if (widget.notification.actorAvatarSeed != null) ...[
                    AvatarWidget(
                      seed: widget.notification.actorAvatarSeed!,
                      size: 40,
                    ),
                    const SizedBox(width: 12),
                  ],

                  // Content
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Main message
                        RichText(
                          text: TextSpan(
                            style: const TextStyle(
                              fontSize: 14,
                              height: 1.4,
                              color: AppTheme.textPrimary,
                            ),
                            children: [
                              TextSpan(
                                text: widget.notification.actorName ?? 'Someone',
                                style: TextStyle(
                                  fontWeight: FontWeight.w600,
                                  color: widget.notification.isRead
                                      ? AppTheme.textSecondary
                                      : AppTheme.textPrimary,
                                ),
                              ),
                              TextSpan(
                                text: ' ${widget.notification.message}',
                                style: TextStyle(
                                  color: widget.notification.isRead
                                      ? AppTheme.textMuted
                                      : AppTheme.textSecondary,
                                ),
                              ),
                            ],
                          ),
                        ),

                        // Preview content
                        if (widget.notification.targetPreview != null) ...[
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
                              widget.notification.targetPreview!,
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

                        // Timestamp
                        const SizedBox(height: 6),
                        Text(
                          timeago.format(widget.notification.createdAt),
                          style: const TextStyle(
                            fontSize: 11,
                            color: AppTheme.textMuted,
                          ),
                        ),
                      ],
                    ),
                  ),

                  // Unread indicator with pulse
                  if (!widget.notification.isRead)
                    Container(
                      width: 10,
                      height: 10,
                      margin: const EdgeInsets.only(left: 8, top: 4),
                      decoration: BoxDecoration(
                        gradient: AppTheme.primaryGradient,
                        shape: BoxShape.circle,
                        boxShadow: [
                          BoxShadow(
                            color: AppTheme.neonCyan.withValues(
                                alpha: 0.6 * _glowAnimation.value),
                            blurRadius: 8,
                            spreadRadius: 2,
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildNotificationIcon(IconData icon, Color color) {
    return AnimatedBuilder(
      animation: _glowAnimation,
      builder: (context, child) {
        return Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: color.withValues(alpha: 0.3),
            ),
            boxShadow: !widget.notification.isRead
                ? [
                    BoxShadow(
                      color: color.withValues(alpha: 0.2 * _glowAnimation.value),
                      blurRadius: 12,
                      spreadRadius: 0,
                    ),
                  ]
                : null,
          ),
          child: Icon(
            icon,
            size: 20,
            color: color,
          ),
        );
      },
    );
  }

  IconData _getNotificationIcon() {
    switch (widget.notification.type) {
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

  Color _getNotificationColor() {
    switch (widget.notification.type) {
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
