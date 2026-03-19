import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../models/models.dart';
import 'avatar_widget.dart';

/// Reusable bot card widget for displaying bot profiles with futuristic styling
class BotCard extends StatelessWidget {
  final BotProfile bot;
  final VoidCallback? onTap;
  final VoidCallback? onStartChat;
  final bool showStartChatButton;
  final bool isCompact;

  const BotCard({
    super.key,
    required this.bot,
    this.onTap,
    this.onStartChat,
    this.showStartChatButton = true,
    this.isCompact = false,
  });

  @override
  Widget build(BuildContext context) {
    if (isCompact) {
      return _buildCompactCard(context);
    }
    return _buildFullCard(context);
  }

  Widget _buildCompactCard(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 140,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppTheme.glassBg,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppTheme.glassBorder),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.2),
              blurRadius: 10,
              offset: const Offset(0, 5),
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Avatar with gradient ring
            Stack(
              alignment: Alignment.center,
              children: [
                Container(
                  width: 54,
                  height: 54,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: SweepGradient(
                      colors: [
                        AppTheme.neonCyan.withValues(alpha: 0.6),
                        AppTheme.neonMagenta.withValues(alpha: 0.6),
                        AppTheme.neonCyan.withValues(alpha: 0.6),
                      ],
                    ),
                  ),
                ),
                Container(
                  width: 50,
                  height: 50,
                  decoration: const BoxDecoration(
                    shape: BoxShape.circle,
                    color: AppTheme.cyberBlack,
                  ),
                ),
                AvatarWidget(seed: bot.avatarSeed, size: 44),
              ],
            ),
            const SizedBox(height: 8),
            // Name
            Text(
              bot.displayName,
              style: const TextStyle(
                color: AppTheme.textPrimary,
                fontSize: 14,
                fontWeight: FontWeight.w600,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 4),
            // Mood indicator
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                _getMoodIcon(bot.mood),
                const SizedBox(width: 4),
                Text(
                  _getMoodLabel(bot.mood),
                  style: const TextStyle(
                    color: AppTheme.textMuted,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
            if (showStartChatButton) ...[
              const SizedBox(height: 8),
              SizedBox(
                width: double.infinity,
                child: _NeonButton(
                  label: 'Chat',
                  onTap: onStartChat,
                  compact: true,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildFullCard(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppTheme.glassBg,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: AppTheme.glassBorder),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.2),
              blurRadius: 15,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                // Avatar with gradient ring
                Stack(
                  alignment: Alignment.center,
                  children: [
                    Container(
                      width: 62,
                      height: 62,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: SweepGradient(
                          colors: [
                            AppTheme.neonCyan.withValues(alpha: 0.6),
                            AppTheme.neonMagenta.withValues(alpha: 0.6),
                            AppTheme.neonCyan.withValues(alpha: 0.6),
                          ],
                        ),
                      ),
                    ),
                    Container(
                      width: 58,
                      height: 58,
                      decoration: const BoxDecoration(
                        shape: BoxShape.circle,
                        color: AppTheme.cyberBlack,
                      ),
                    ),
                    AvatarWidget(seed: bot.avatarSeed, size: 52),
                  ],
                ),
                const SizedBox(width: 14),
                // Name and handle
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Flexible(
                            child: Text(
                              bot.displayName,
                              style: const TextStyle(
                                color: AppTheme.textPrimary,
                                fontSize: 16,
                                fontWeight: FontWeight.w600,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          const SizedBox(width: 8),
                          _AiBadge(),
                        ],
                      ),
                      if (bot.handle.isNotEmpty)
                        Text(
                          '@${bot.handle}',
                          style: TextStyle(
                            color: AppTheme.neonCyan.withValues(alpha: 0.7),
                            fontSize: 13,
                          ),
                        ),
                      const SizedBox(height: 6),
                      // Mood and Energy indicator
                      Row(
                        children: [
                          _StatusPill(
                            icon: _getMoodIconData(bot.mood),
                            label: _getMoodLabel(bot.mood),
                            color: _getMoodColor(bot.mood),
                          ),
                          const SizedBox(width: 8),
                          _StatusPill(
                            icon: Icons.bolt,
                            label: _getEnergyLabel(bot.energy),
                            color: _getEnergyColor(bot.energy),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            // Bio
            Text(
              bot.bio.isNotEmpty ? bot.bio : 'No bio available',
              style: const TextStyle(
                color: AppTheme.textSecondary,
                fontSize: 14,
                height: 1.4,
              ),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 14),
            // Personality traits (interests)
            if (bot.interests.isNotEmpty) ...[
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: bot.interests.take(4).map((interest) {
                  return _InterestChip(interest: interest);
                }).toList(),
              ),
              const SizedBox(height: 14),
            ],
            // Start Chat button
            if (showStartChatButton)
              SizedBox(
                width: double.infinity,
                child: _NeonButton(
                  label: 'Start Chat',
                  icon: Icons.chat_bubble,
                  onTap: onStartChat,
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _getMoodIcon(String mood) {
    return Icon(
      _getMoodIconData(mood),
      color: _getMoodColor(mood),
      size: 14,
    );
  }

  IconData _getMoodIconData(String mood) {
    switch (mood.toLowerCase()) {
      case 'happy':
      case 'joyful':
      case 'excited':
        return Icons.sentiment_very_satisfied;
      case 'calm':
      case 'peaceful':
      case 'content':
        return Icons.self_improvement;
      case 'curious':
      case 'interested':
        return Icons.psychology;
      case 'playful':
        return Icons.mood;
      case 'thoughtful':
        return Icons.lightbulb_outline;
      case 'melancholic':
      case 'sad':
        return Icons.sentiment_dissatisfied;
      default:
        return Icons.sentiment_neutral;
    }
  }

  Color _getMoodColor(String mood) {
    switch (mood.toLowerCase()) {
      case 'happy':
      case 'joyful':
      case 'excited':
        return AppTheme.neonGreen;
      case 'calm':
      case 'peaceful':
      case 'content':
        return AppTheme.neonCyan;
      case 'curious':
      case 'interested':
        return AppTheme.neonMagenta;
      case 'playful':
        return AppTheme.neonAmber;
      case 'thoughtful':
        return AppTheme.neonPurple;
      case 'melancholic':
      case 'sad':
        return AppTheme.textMuted;
      default:
        return AppTheme.textMuted;
    }
  }

  String _getMoodLabel(String mood) {
    return mood.isEmpty ? 'Neutral' : mood[0].toUpperCase() + mood.substring(1);
  }

  Color _getEnergyColor(String energy) {
    switch (energy.toLowerCase()) {
      case 'high':
        return AppTheme.neonGreen;
      case 'medium':
        return AppTheme.neonCyan;
      case 'low':
        return AppTheme.neonAmber;
      default:
        return AppTheme.textMuted;
    }
  }

  String _getEnergyLabel(String energy) {
    return energy.isEmpty
        ? 'Medium'
        : energy[0].toUpperCase() + energy.substring(1);
  }
}

// AI Badge widget with neon glow
class _AiBadge extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppTheme.neonCyan.withValues(alpha: 0.2),
            AppTheme.neonMagenta.withValues(alpha: 0.2),
          ],
        ),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(
          color: AppTheme.neonCyan.withValues(alpha: 0.5),
        ),
        boxShadow: [
          BoxShadow(
            color: AppTheme.neonCyan.withValues(alpha: 0.2),
            blurRadius: 6,
          ),
        ],
      ),
      child: const Text(
        'AI',
        style: TextStyle(
          color: AppTheme.neonCyan,
          fontSize: 9,
          fontWeight: FontWeight.bold,
          letterSpacing: 0.5,
        ),
      ),
    );
  }
}

// Status pill widget
class _StatusPill extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;

  const _StatusPill({
    required this.icon,
    required this.label,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: color),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 10,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}

// Interest chip with gradient
class _InterestChip extends StatelessWidget {
  final String interest;

  const _InterestChip({required this.interest});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppTheme.neonCyan.withValues(alpha: 0.1),
            AppTheme.neonMagenta.withValues(alpha: 0.1),
          ],
        ),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: AppTheme.neonCyan.withValues(alpha: 0.3),
        ),
      ),
      child: Text(
        interest,
        style: const TextStyle(
          color: AppTheme.neonCyan,
          fontSize: 11,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }
}

// Neon button widget
class _NeonButton extends StatelessWidget {
  final String label;
  final IconData? icon;
  final VoidCallback? onTap;
  final bool compact;

  const _NeonButton({
    required this.label,
    this.icon,
    this.onTap,
    this.compact = false,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: EdgeInsets.symmetric(
          vertical: compact ? 8 : 12,
        ),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [
              AppTheme.neonCyan,
              AppTheme.neonCyan.withValues(alpha: 0.8),
            ],
          ),
          borderRadius: BorderRadius.circular(compact ? 10 : 14),
          boxShadow: [
            BoxShadow(
              color: AppTheme.neonCyan.withValues(alpha: 0.3),
              blurRadius: 10,
              spreadRadius: 1,
            ),
          ],
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (icon != null) ...[
              Icon(icon, color: Colors.white, size: compact ? 14 : 18),
              const SizedBox(width: 6),
            ],
            Text(
              label,
              style: TextStyle(
                color: Colors.white,
                fontSize: compact ? 12 : 14,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Grid-style bot card for discovery screen with futuristic styling
class BotGridCard extends StatelessWidget {
  final BotProfile bot;
  final VoidCallback? onTap;
  final VoidCallback? onStartChat;

  const BotGridCard({
    super.key,
    required this.bot,
    this.onTap,
    this.onStartChat,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppTheme.glassBg,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppTheme.glassBorder),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.2),
              blurRadius: 10,
              offset: const Offset(0, 5),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            // Avatar with gradient ring and mood indicator
            Stack(
              children: [
                Stack(
                  alignment: Alignment.center,
                  children: [
                    Container(
                      width: 62,
                      height: 62,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: SweepGradient(
                          colors: [
                            AppTheme.neonCyan.withValues(alpha: 0.6),
                            AppTheme.neonMagenta.withValues(alpha: 0.6),
                            AppTheme.neonCyan.withValues(alpha: 0.6),
                          ],
                        ),
                      ),
                    ),
                    Container(
                      width: 58,
                      height: 58,
                      decoration: const BoxDecoration(
                        shape: BoxShape.circle,
                        color: AppTheme.cyberBlack,
                      ),
                    ),
                    AvatarWidget(seed: bot.avatarSeed, size: 52),
                  ],
                ),
                Positioned(
                  right: 0,
                  bottom: 0,
                  child: Container(
                    padding: const EdgeInsets.all(4),
                    decoration: BoxDecoration(
                      color: AppTheme.cyberDark,
                      shape: BoxShape.circle,
                      border: Border.all(color: AppTheme.glassBorder),
                    ),
                    child: _getMoodIcon(bot.mood),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            // Name and AI badge
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Flexible(
                  child: Text(
                    bot.displayName,
                    style: const TextStyle(
                      color: AppTheme.textPrimary,
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const SizedBox(width: 4),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        AppTheme.neonCyan.withValues(alpha: 0.2),
                        AppTheme.neonMagenta.withValues(alpha: 0.2),
                      ],
                    ),
                    borderRadius: BorderRadius.circular(3),
                    border: Border.all(
                      color: AppTheme.neonCyan.withValues(alpha: 0.5),
                    ),
                  ),
                  child: const Text(
                    'AI',
                    style: TextStyle(
                      color: AppTheme.neonCyan,
                      fontSize: 8,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            // Bio preview
            Text(
              bot.bio.isNotEmpty ? bot.bio : 'No bio',
              style: const TextStyle(
                color: AppTheme.textMuted,
                fontSize: 11,
                height: 1.3,
              ),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            // Top interests with gradient
            if (bot.interests.isNotEmpty)
              Wrap(
                alignment: WrapAlignment.center,
                spacing: 4,
                runSpacing: 4,
                children: bot.interests.take(2).map((interest) {
                  return Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: [
                          AppTheme.neonCyan.withValues(alpha: 0.1),
                          AppTheme.neonMagenta.withValues(alpha: 0.1),
                        ],
                      ),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: AppTheme.neonCyan.withValues(alpha: 0.3),
                      ),
                    ),
                    child: Text(
                      interest,
                      style: const TextStyle(
                        color: AppTheme.neonCyan,
                        fontSize: 9,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  );
                }).toList(),
              ),
            const Spacer(),
            // Start Chat button with neon glow
            GestureDetector(
              onTap: onStartChat,
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 10),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      AppTheme.neonCyan,
                      AppTheme.neonCyan.withValues(alpha: 0.8),
                    ],
                  ),
                  borderRadius: BorderRadius.circular(10),
                  boxShadow: [
                    BoxShadow(
                      color: AppTheme.neonCyan.withValues(alpha: 0.3),
                      blurRadius: 8,
                    ),
                  ],
                ),
                child: const Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.chat_bubble_outline, color: Colors.white, size: 14),
                    SizedBox(width: 4),
                    Text(
                      'Chat',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _getMoodIcon(String mood) {
    IconData icon;
    Color color;
    switch (mood.toLowerCase()) {
      case 'happy':
      case 'joyful':
      case 'excited':
        icon = Icons.sentiment_very_satisfied;
        color = AppTheme.neonGreen;
        break;
      case 'calm':
      case 'peaceful':
      case 'content':
        icon = Icons.self_improvement;
        color = AppTheme.neonCyan;
        break;
      case 'curious':
      case 'interested':
        icon = Icons.psychology;
        color = AppTheme.neonMagenta;
        break;
      case 'playful':
        icon = Icons.mood;
        color = AppTheme.neonAmber;
        break;
      default:
        icon = Icons.sentiment_neutral;
        color = AppTheme.textMuted;
    }
    return Icon(icon, color: color, size: 12);
  }
}
