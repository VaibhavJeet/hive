// Offline banner widget shown when device is offline

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

/// Banner displayed when the device is offline
class OfflineBanner extends StatelessWidget {
  final bool isOffline;
  final int queuedActionsCount;
  final VoidCallback? onRetry;

  const OfflineBanner({
    super.key,
    required this.isOffline,
    this.queuedActionsCount = 0,
    this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    if (!isOffline) return const SizedBox.shrink();

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
      decoration: BoxDecoration(
        color: Colors.orange.shade800,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.2),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: SafeArea(
        bottom: false,
        child: Row(
          children: [
            // Animated connection icon
            _buildAnimatedIcon(),
            const SizedBox(width: 12),
            // Message
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    "You're offline",
                    style: TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                      fontSize: 14,
                    ),
                  ),
                  Text(
                    queuedActionsCount > 0
                        ? 'Some features unavailable. $queuedActionsCount action${queuedActionsCount > 1 ? 's' : ''} queued.'
                        : 'Some features unavailable.',
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.9),
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ),
            // Retry button
            if (onRetry != null)
              IconButton(
                icon: const Icon(Icons.refresh, color: Colors.white),
                onPressed: onRetry,
                tooltip: 'Retry connection',
              ),
          ],
        ),
      ),
    ).animate().fadeIn(duration: 300.ms).slideY(begin: -1, end: 0, duration: 300.ms);
  }

  Widget _buildAnimatedIcon() {
    return Stack(
      alignment: Alignment.center,
      children: [
        // Pulsing background
        Container(
          width: 32,
          height: 32,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: Colors.white.withValues(alpha: 0.2),
          ),
        ).animate(onPlay: (controller) => controller.repeat())
          .scale(
            begin: const Offset(1, 1),
            end: const Offset(1.3, 1.3),
            duration: 1000.ms,
          )
          .fadeOut(duration: 1000.ms),
        // Icon
        const Icon(
          Icons.wifi_off,
          color: Colors.white,
          size: 20,
        ),
      ],
    );
  }
}

/// Compact offline indicator for app bars
class OfflineIndicator extends StatelessWidget {
  final bool isOffline;

  const OfflineIndicator({
    super.key,
    required this.isOffline,
  });

  @override
  Widget build(BuildContext context) {
    if (!isOffline) return const SizedBox.shrink();

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.orange.shade700,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.wifi_off,
            color: Colors.white,
            size: 14,
          ).animate(onPlay: (controller) => controller.repeat())
            .fadeIn(duration: 500.ms)
            .then()
            .fadeOut(duration: 500.ms),
          const SizedBox(width: 4),
          const Text(
            'Offline',
            style: TextStyle(
              color: Colors.white,
              fontSize: 12,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}

/// Connection status widget showing real-time connectivity
class ConnectionStatusWidget extends StatelessWidget {
  final bool isConnected;
  final bool isConnecting;

  const ConnectionStatusWidget({
    super.key,
    required this.isConnected,
    this.isConnecting = false,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: _getStatusColor(),
          ),
        ),
        const SizedBox(width: 6),
        Text(
          _getStatusText(),
          style: TextStyle(
            fontSize: 12,
            color: Theme.of(context).textTheme.bodySmall?.color,
          ),
        ),
      ],
    );
  }

  Color _getStatusColor() {
    if (isConnecting) return Colors.orange;
    return isConnected ? Colors.green : Colors.red;
  }

  String _getStatusText() {
    if (isConnecting) return 'Connecting...';
    return isConnected ? 'Connected' : 'Offline';
  }
}

/// Snackbar helper for showing offline notifications
class OfflineSnackBar {
  static void showOffline(BuildContext context) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.wifi_off, color: Colors.white),
            const SizedBox(width: 12),
            const Text("You're offline. Changes will sync when connected."),
          ],
        ),
        backgroundColor: Colors.orange.shade800,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 3),
      ),
    );
  }

  static void showBackOnline(BuildContext context, {int syncedCount = 0}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.wifi, color: Colors.white),
            const SizedBox(width: 12),
            Text(syncedCount > 0
                ? "You're back online! $syncedCount action${syncedCount > 1 ? 's' : ''} synced."
                : "You're back online!"),
          ],
        ),
        backgroundColor: Colors.green.shade700,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 2),
      ),
    );
  }
}
