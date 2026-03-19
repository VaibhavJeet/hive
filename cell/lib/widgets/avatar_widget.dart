import 'package:flutter/material.dart';
import 'dart:math';
import '../theme/app_theme.dart';

class AvatarWidget extends StatelessWidget {
  final String seed;
  final double size;
  final bool showAiBadge;
  final String? aiLabel;

  const AvatarWidget({
    super.key,
    required this.seed,
    this.size = 48,
    this.showAiBadge = false,  // Disabled - looks cleaner
    this.aiLabel,
  });

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        Container(
          width: size,
          height: size,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: _generateGradient(seed),
            boxShadow: [
              BoxShadow(
                color: _generateColor(seed).withValues(alpha: 0.4),
                blurRadius: 8,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Center(
            child: Text(
              _getInitials(seed),
              style: TextStyle(
                color: Colors.white,
                fontSize: size * 0.35,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ),
        if (showAiBadge)
          Positioned(
            right: 0,
            bottom: 0,
            child: Container(
              padding: const EdgeInsets.all(2),
              decoration: BoxDecoration(
                color: AppTheme.aiLabelBg,
                borderRadius: BorderRadius.circular(4),
                border: Border.all(
                  color: AppTheme.backgroundColor,
                  width: 2,
                ),
              ),
              child: const Icon(
                Icons.smart_toy,
                size: 10,
                color: AppTheme.aiLabelColor,
              ),
            ),
          ),
      ],
    );
  }

  String _getInitials(String seed) {
    // Generate consistent initials from seed
    final random = Random(seed.hashCode);
    final letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    return '${letters[random.nextInt(26)]}${letters[random.nextInt(26)]}';
  }

  Color _generateColor(String seed) {
    final random = Random(seed.hashCode);
    final hue = random.nextDouble() * 360;
    return HSLColor.fromAHSL(1.0, hue, 0.7, 0.5).toColor();
  }

  LinearGradient _generateGradient(String seed) {
    final random = Random(seed.hashCode);
    final hue1 = random.nextDouble() * 360;
    final hue2 = (hue1 + 40 + random.nextDouble() * 40) % 360;

    return LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [
        HSLColor.fromAHSL(1.0, hue1, 0.7, 0.5).toColor(),
        HSLColor.fromAHSL(1.0, hue2, 0.6, 0.4).toColor(),
      ],
    );
  }
}

class AiBadge extends StatelessWidget {
  final String label;
  final double fontSize;

  const AiBadge({
    super.key,
    this.label = 'AI',
    this.fontSize = 10,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: AppTheme.aiLabelBg,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.smart_toy,
            size: fontSize,
            color: AppTheme.aiLabelColor,
          ),
          const SizedBox(width: 2),
          Text(
            label,
            style: TextStyle(
              color: AppTheme.aiLabelColor,
              fontSize: fontSize,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
