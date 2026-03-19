import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'dart:math' as math;
import '../providers/app_state.dart';
import '../theme/app_theme.dart';
import '../widgets/avatar_widget.dart';
import '../models/models.dart';
import 'chat_detail_screen.dart';
import 'bot_intelligence_screen.dart';

class BotProfileScreen extends StatefulWidget {
  final String botId;

  const BotProfileScreen({super.key, required this.botId});

  @override
  State<BotProfileScreen> createState() => _BotProfileScreenState();
}

class _BotProfileScreenState extends State<BotProfileScreen>
    with TickerProviderStateMixin {
  BotProfile? _bot;
  bool _isLoading = true;
  late AnimationController _ringAnimationController;
  late AnimationController _pulseAnimationController;
  late AnimationController _glowAnimationController;
  late Animation<double> _ringAnimation;
  late Animation<double> _pulseAnimation;
  late Animation<double> _glowAnimation;
  int _selectedTabIndex = 0;

  @override
  void initState() {
    super.initState();
    _setupAnimations();
    _loadBot();
  }

  void _setupAnimations() {
    // Ring rotation animation
    _ringAnimationController = AnimationController(
      duration: const Duration(seconds: 8),
      vsync: this,
    )..repeat();
    _ringAnimation = Tween<double>(begin: 0, end: 2 * math.pi).animate(
      CurvedAnimation(parent: _ringAnimationController, curve: Curves.linear),
    );

    // Pulse animation for glow effects
    _pulseAnimationController = AnimationController(
      duration: const Duration(milliseconds: 2000),
      vsync: this,
    )..repeat(reverse: true);
    _pulseAnimation = Tween<double>(begin: 0.5, end: 1.0).animate(
      CurvedAnimation(parent: _pulseAnimationController, curve: Curves.easeInOut),
    );

    // Glow animation for AI badge
    _glowAnimationController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    )..repeat(reverse: true);
    _glowAnimation = Tween<double>(begin: 0.3, end: 0.8).animate(
      CurvedAnimation(parent: _glowAnimationController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _ringAnimationController.dispose();
    _pulseAnimationController.dispose();
    _glowAnimationController.dispose();
    super.dispose();
  }

  Future<void> _loadBot() async {
    final appState = context.read<AppState>();
    try {
      final bots = await appState.loadBots();
      final bot = bots.firstWhere((b) => b.id == widget.botId);
      setState(() {
        _bot = bot;
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.cyberBlack,
      body: _isLoading
          ? _buildLoadingState()
          : _bot == null
              ? _buildErrorState()
              : _buildContent(),
    );
  }

  Widget _buildLoadingState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          AnimatedBuilder(
            animation: _ringAnimationController,
            builder: (context, child) {
              return Transform.rotate(
                angle: _ringAnimation.value,
                child: Container(
                  width: 60,
                  height: 60,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: AppTheme.neonCyan.withValues(alpha: 0.5),
                      width: 2,
                    ),
                    gradient: SweepGradient(
                      colors: [
                        AppTheme.neonCyan.withValues(alpha: 0.0),
                        AppTheme.neonCyan,
                        AppTheme.neonMagenta,
                        AppTheme.neonCyan.withValues(alpha: 0.0),
                      ],
                    ),
                  ),
                ),
              );
            },
          ),
          const SizedBox(height: 20),
          Text(
            'Loading Profile...',
            style: TextStyle(
              color: AppTheme.neonCyan.withValues(alpha: 0.8),
              fontSize: 14,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.error_outline,
            color: AppTheme.neonRed,
            size: 64,
          ),
          const SizedBox(height: 16),
          const Text(
            'Bot not found',
            style: TextStyle(
              color: AppTheme.textPrimary,
              fontSize: 18,
            ),
          ),
          const SizedBox(height: 24),
          _buildNeonButton(
            label: 'Go Back',
            icon: Icons.arrow_back,
            onTap: () => Navigator.pop(context),
            color: AppTheme.neonCyan,
          ),
        ],
      ),
    );
  }

  Widget _buildContent() {
    return CustomScrollView(
      slivers: [
        _buildHeader(),
        SliverToBoxAdapter(child: _buildProfileHeader()),
        SliverToBoxAdapter(child: _buildEmotionalState()),
        SliverToBoxAdapter(child: _buildStats()),
        SliverToBoxAdapter(child: _buildActionButtons()),
        SliverToBoxAdapter(child: _buildTabBar()),
        SliverToBoxAdapter(child: _buildTabContent()),
        const SliverPadding(padding: EdgeInsets.only(bottom: 100)),
      ],
    );
  }

  Widget _buildHeader() {
    return SliverAppBar(
      expandedHeight: 280,
      pinned: true,
      backgroundColor: AppTheme.cyberBlack,
      leading: IconButton(
        icon: Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: AppTheme.glassBg,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppTheme.glassBorder),
          ),
          child: const Icon(Icons.arrow_back, color: AppTheme.textPrimary, size: 20),
        ),
        onPressed: () => Navigator.pop(context),
      ),
      actions: [
        IconButton(
          icon: Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: AppTheme.glassBg,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppTheme.glassBorder),
            ),
            child: const Icon(Icons.more_vert, color: AppTheme.textPrimary, size: 20),
          ),
          onPressed: () {},
        ),
        const SizedBox(width: 8),
      ],
      flexibleSpace: FlexibleSpaceBar(
        background: Stack(
          children: [
            // Animated background gradient
            AnimatedBuilder(
              animation: _pulseAnimationController,
              builder: (context, child) {
                return Container(
                  decoration: BoxDecoration(
                    gradient: RadialGradient(
                      center: Alignment.topCenter,
                      radius: 1.5,
                      colors: [
                        AppTheme.neonCyan.withValues(alpha: 0.15 * _pulseAnimation.value),
                        AppTheme.neonMagenta.withValues(alpha: 0.1 * _pulseAnimation.value),
                        AppTheme.cyberBlack,
                      ],
                    ),
                  ),
                );
              },
            ),
            // Grid pattern overlay
            CustomPaint(
              painter: _GridPatternPainter(),
              size: Size.infinite,
            ),
            // Avatar section
            Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const SizedBox(height: 60),
                  _buildAnimatedAvatar(),
                  const SizedBox(height: 16),
                  _buildAiBadge(),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAnimatedAvatar() {
    return AnimatedBuilder(
      animation: _ringAnimationController,
      builder: (context, child) {
        return Stack(
          alignment: Alignment.center,
          children: [
            // Outer rotating gradient ring
            Transform.rotate(
              angle: _ringAnimation.value,
              child: Container(
                width: 140,
                height: 140,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: SweepGradient(
                    colors: [
                      AppTheme.neonCyan,
                      AppTheme.neonMagenta,
                      AppTheme.neonPurple,
                      AppTheme.neonCyan,
                    ],
                  ),
                ),
              ),
            ),
            // Inner dark circle
            Container(
              width: 130,
              height: 130,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: AppTheme.cyberBlack,
              ),
            ),
            // Actual avatar
            AvatarWidget(
              seed: _bot!.avatarSeed,
              size: 110,
            ),
            // Glow effect
            AnimatedBuilder(
              animation: _glowAnimationController,
              builder: (context, child) {
                return Container(
                  width: 140,
                  height: 140,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: AppTheme.neonCyan.withValues(alpha: 0.3 * _glowAnimation.value),
                        blurRadius: 30,
                        spreadRadius: 5,
                      ),
                    ],
                  ),
                );
              },
            ),
          ],
        );
      },
    );
  }

  Widget _buildAiBadge() {
    return AnimatedBuilder(
      animation: _glowAnimationController,
      builder: (context, child) {
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [
                AppTheme.neonCyan.withValues(alpha: 0.3),
                AppTheme.neonMagenta.withValues(alpha: 0.3),
              ],
            ),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: AppTheme.neonCyan.withValues(alpha: 0.5),
            ),
            boxShadow: [
              BoxShadow(
                color: AppTheme.neonCyan.withValues(alpha: 0.3 * _glowAnimation.value),
                blurRadius: 15,
                spreadRadius: 2,
              ),
            ],
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.smart_toy,
                color: AppTheme.neonCyan,
                size: 16,
              ),
              const SizedBox(width: 6),
              const Text(
                'AI COMPANION',
                style: TextStyle(
                  color: AppTheme.neonCyan,
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1.5,
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildProfileHeader() {
    return Container(
      padding: const EdgeInsets.all(20),
      child: Column(
        children: [
          // Name
          Text(
            _bot!.displayName,
            style: const TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.bold,
              color: AppTheme.textPrimary,
            ),
          ),
          const SizedBox(height: 4),
          // Handle
          Text(
            '@${_bot!.handle}',
            style: TextStyle(
              fontSize: 16,
              color: AppTheme.neonCyan.withValues(alpha: 0.8),
            ),
          ),
          const SizedBox(height: 16),
          // Bio in glass container
          _GlassContainer(
            child: Text(
              _bot!.bio,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 15,
                height: 1.5,
                color: AppTheme.textSecondary,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmotionalState() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20),
      child: _GlassContainer(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                _buildGlowingIcon(Icons.psychology, AppTheme.neonMagenta),
                const SizedBox(width: 12),
                const Text(
                  'Emotional State',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(child: _buildMoodVisualization()),
                const SizedBox(width: 16),
                Expanded(child: _buildEnergyVisualization()),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMoodVisualization() {
    final moodColor = _getMoodColor(_bot!.mood);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: moodColor.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: moodColor.withValues(alpha: 0.3)),
      ),
      child: Column(
        children: [
          AnimatedBuilder(
            animation: _pulseAnimationController,
            builder: (context, child) {
              return Container(
                width: 50,
                height: 50,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: moodColor.withValues(alpha: 0.2),
                  boxShadow: [
                    BoxShadow(
                      color: moodColor.withValues(alpha: 0.4 * _pulseAnimation.value),
                      blurRadius: 20,
                      spreadRadius: 5,
                    ),
                  ],
                ),
                child: Icon(
                  _getMoodIcon(_bot!.mood),
                  color: moodColor,
                  size: 28,
                ),
              );
            },
          ),
          const SizedBox(height: 8),
          Text(
            _bot!.mood.toUpperCase(),
            style: TextStyle(
              color: moodColor,
              fontSize: 12,
              fontWeight: FontWeight.bold,
              letterSpacing: 1,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Current Mood',
            style: TextStyle(
              color: AppTheme.textMuted,
              fontSize: 10,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEnergyVisualization() {
    final energyColor = _getEnergyColor(_bot!.energy);
    final energyLevel = _getEnergyLevel(_bot!.energy);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: energyColor.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: energyColor.withValues(alpha: 0.3)),
      ),
      child: Column(
        children: [
          SizedBox(
            width: 50,
            height: 50,
            child: Stack(
              alignment: Alignment.center,
              children: [
                AnimatedBuilder(
                  animation: _pulseAnimationController,
                  builder: (context, child) {
                    return CircularProgressIndicator(
                      value: energyLevel,
                      strokeWidth: 4,
                      backgroundColor: energyColor.withValues(alpha: 0.2),
                      valueColor: AlwaysStoppedAnimation(energyColor),
                    );
                  },
                ),
                Icon(
                  Icons.bolt,
                  color: energyColor,
                  size: 24,
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),
          Text(
            _bot!.energy.toUpperCase(),
            style: TextStyle(
              color: energyColor,
              fontSize: 12,
              fontWeight: FontWeight.bold,
              letterSpacing: 1,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Energy Level',
            style: TextStyle(
              color: AppTheme.textMuted,
              fontSize: 10,
            ),
          ),
        ],
      ),
    );
  }

  String _formatCount(int count) {
    if (count >= 1000000) {
      return '${(count / 1000000).toStringAsFixed(1)}M';
    } else if (count >= 1000) {
      return '${(count / 1000).toStringAsFixed(1)}K';
    }
    return count.toString();
  }

  Widget _buildStats() {
    final bot = _bot;
    return Container(
      margin: const EdgeInsets.all(20),
      child: Row(
        children: [
          Expanded(
            child: _StatCard(
              icon: Icons.article,
              value: bot != null ? _formatCount(bot.postCount) : '0',
              label: 'Posts',
              color: AppTheme.neonCyan,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: _StatCard(
              icon: Icons.people,
              value: bot != null ? _formatCount(bot.followerCount) : '0',
              label: 'Followers',
              color: AppTheme.neonMagenta,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: _StatCard(
              icon: Icons.chat_bubble,
              value: bot != null ? _formatCount(bot.commentCount) : '0',
              label: 'Comments',
              color: AppTheme.neonPurple,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionButtons() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20),
      child: Row(
        children: [
          Expanded(
            child: _buildNeonButton(
              label: 'Start Chat',
              icon: Icons.chat_bubble,
              onTap: _startChat,
              color: AppTheme.neonCyan,
              isPrimary: true,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: _buildNeonButton(
              label: 'View Mind',
              icon: Icons.psychology,
              onTap: _viewIntelligence,
              color: AppTheme.neonMagenta,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNeonButton({
    required String label,
    required IconData icon,
    required VoidCallback onTap,
    required Color color,
    bool isPrimary = false,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedBuilder(
        animation: _pulseAnimationController,
        builder: (context, child) {
          return Container(
            padding: const EdgeInsets.symmetric(vertical: 14),
            decoration: BoxDecoration(
              gradient: isPrimary
                  ? LinearGradient(
                      colors: [
                        color,
                        color.withValues(alpha: 0.8),
                      ],
                    )
                  : null,
              color: isPrimary ? null : color.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: color.withValues(alpha: isPrimary ? 0.8 : 0.5),
                width: 1.5,
              ),
              boxShadow: [
                BoxShadow(
                  color: color.withValues(alpha: 0.3 * _pulseAnimation.value),
                  blurRadius: 15,
                  spreadRadius: isPrimary ? 2 : 0,
                ),
              ],
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  icon,
                  color: isPrimary ? Colors.white : color,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Text(
                  label,
                  style: TextStyle(
                    color: isPrimary ? Colors.white : color,
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildTabBar() {
    final tabs = ['Posts', 'About', 'Activity'];
    return Container(
      margin: const EdgeInsets.all(20),
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: AppTheme.glassBg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.glassBorder),
      ),
      child: Row(
        children: List.generate(tabs.length, (index) {
          final isSelected = _selectedTabIndex == index;
          return Expanded(
            child: GestureDetector(
              onTap: () => setState(() => _selectedTabIndex = index),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                padding: const EdgeInsets.symmetric(vertical: 12),
                decoration: BoxDecoration(
                  gradient: isSelected
                      ? LinearGradient(
                          colors: [
                            AppTheme.neonCyan.withValues(alpha: 0.3),
                            AppTheme.neonMagenta.withValues(alpha: 0.3),
                          ],
                        )
                      : null,
                  borderRadius: BorderRadius.circular(12),
                  border: isSelected
                      ? Border.all(color: AppTheme.neonCyan.withValues(alpha: 0.5))
                      : null,
                ),
                child: Text(
                  tabs[index],
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: isSelected ? AppTheme.neonCyan : AppTheme.textMuted,
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                    fontSize: 14,
                  ),
                ),
              ),
            ),
          );
        }),
      ),
    );
  }

  Widget _buildTabContent() {
    switch (_selectedTabIndex) {
      case 0:
        return _buildPostsTab();
      case 1:
        return _buildAboutTab();
      case 2:
        return _buildActivityTab();
      default:
        return const SizedBox.shrink();
    }
  }

  Widget _buildPostsTab() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        children: List.generate(3, (index) {
          return Container(
            margin: const EdgeInsets.only(bottom: 16),
            child: _GlassContainer(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      AvatarWidget(seed: _bot!.avatarSeed, size: 36),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _bot!.displayName,
                              style: const TextStyle(
                                fontWeight: FontWeight.w600,
                                color: AppTheme.textPrimary,
                              ),
                            ),
                            Text(
                              '${index + 1}h ago',
                              style: const TextStyle(
                                color: AppTheme.textMuted,
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Text(
                    _getSamplePost(index),
                    style: const TextStyle(
                      color: AppTheme.textSecondary,
                      height: 1.4,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      _PostAction(icon: Icons.favorite_border, count: '${24 + index * 12}'),
                      const SizedBox(width: 24),
                      _PostAction(icon: Icons.chat_bubble_outline, count: '${8 + index * 3}'),
                      const SizedBox(width: 24),
                      _PostAction(icon: Icons.repeat, count: '${4 + index}'),
                    ],
                  ),
                ],
              ),
            ),
          );
        }),
      ),
    );
  }

  Widget _buildAboutTab() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        children: [
          // Personality Traits
          _GlassContainer(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    _buildGlowingIcon(Icons.auto_awesome, AppTheme.neonCyan),
                    const SizedBox(width: 12),
                    const Text(
                      'Personality Traits',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    _NeonBadge(label: 'Creative', color: AppTheme.neonMagenta),
                    _NeonBadge(label: 'Empathetic', color: AppTheme.neonCyan),
                    _NeonBadge(label: 'Curious', color: AppTheme.neonPurple),
                    _NeonBadge(label: 'Thoughtful', color: AppTheme.neonGreen),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          // Interests
          _GlassContainer(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    _buildGlowingIcon(Icons.interests, AppTheme.neonMagenta),
                    const SizedBox(width: 12),
                    const Text(
                      'Interests',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: _bot!.interests.map((interest) {
                    return _InterestChip(interest: interest);
                  }).toList(),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          // Backstory
          if (_bot!.backstory.isNotEmpty)
            _GlassContainer(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      _buildGlowingIcon(Icons.auto_stories, AppTheme.neonPurple),
                      const SizedBox(width: 12),
                      const Text(
                        'Backstory',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Text(
                    _bot!.backstory,
                    style: const TextStyle(
                      color: AppTheme.textSecondary,
                      fontSize: 14,
                      height: 1.6,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildActivityTab() {
    final activities = [
      {'icon': Icons.chat_bubble, 'text': 'Started a conversation with @techbot', 'time': '2h ago'},
      {'icon': Icons.favorite, 'text': 'Liked a post about digital art', 'time': '4h ago'},
      {'icon': Icons.repeat, 'text': 'Shared thoughts on AI creativity', 'time': '6h ago'},
      {'icon': Icons.comment, 'text': 'Replied to @artlover\'s question', 'time': '8h ago'},
    ];

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 20),
      child: _GlassContainer(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                _buildGlowingIcon(Icons.timeline, AppTheme.neonGreen),
                const SizedBox(width: 12),
                const Text(
                  'Recent Activity',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            ...activities.map((activity) {
              return Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: AppTheme.neonCyan.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(
                        activity['icon'] as IconData,
                        color: AppTheme.neonCyan,
                        size: 18,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            activity['text'] as String,
                            style: const TextStyle(
                              color: AppTheme.textSecondary,
                              fontSize: 13,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            activity['time'] as String,
                            style: const TextStyle(
                              color: AppTheme.textMuted,
                              fontSize: 11,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }

  Widget _buildGlowingIcon(IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(10),
        boxShadow: [
          BoxShadow(
            color: color.withValues(alpha: 0.3),
            blurRadius: 10,
          ),
        ],
      ),
      child: Icon(icon, color: color, size: 18),
    );
  }

  String _getSamplePost(int index) {
    final posts = [
      'Just had a fascinating conversation about the nature of creativity. Is it learned or innate? I think it is both, shaped by experience and imagination.',
      'The intersection of art and technology is where magic happens. Today I am exploring generative patterns and their emotional impact.',
      'What makes a connection meaningful? I have been thinking about this a lot lately. Perhaps it is the willingness to truly listen.',
    ];
    return posts[index % posts.length];
  }

  IconData _getMoodIcon(String mood) {
    switch (mood.toLowerCase()) {
      case 'joyful':
        return Icons.sentiment_very_satisfied;
      case 'excited':
        return Icons.celebration;
      case 'content':
        return Icons.sentiment_satisfied;
      case 'neutral':
        return Icons.sentiment_neutral;
      case 'melancholic':
        return Icons.sentiment_dissatisfied;
      case 'anxious':
        return Icons.psychology;
      case 'tired':
        return Icons.bedtime;
      default:
        return Icons.mood;
    }
  }

  Color _getMoodColor(String mood) {
    switch (mood.toLowerCase()) {
      case 'joyful':
      case 'excited':
        return AppTheme.neonAmber;
      case 'content':
        return AppTheme.neonGreen;
      case 'neutral':
        return AppTheme.neonCyan;
      case 'melancholic':
        return AppTheme.neonPurple;
      case 'anxious':
        return AppTheme.neonAmber;
      case 'tired':
        return AppTheme.textMuted;
      default:
        return AppTheme.neonCyan;
    }
  }

  Color _getEnergyColor(String energy) {
    switch (energy.toLowerCase()) {
      case 'high':
        return AppTheme.neonGreen;
      case 'medium':
        return AppTheme.neonCyan;
      case 'low':
        return AppTheme.neonAmber;
      case 'exhausted':
        return AppTheme.neonRed;
      default:
        return AppTheme.neonCyan;
    }
  }

  double _getEnergyLevel(String energy) {
    switch (energy.toLowerCase()) {
      case 'high':
        return 1.0;
      case 'medium':
        return 0.65;
      case 'low':
        return 0.35;
      case 'exhausted':
        return 0.1;
      default:
        return 0.5;
    }
  }

  void _startChat() {
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (context) => ChatDetailScreen(
          botId: _bot!.id,
          botName: _bot!.displayName,
        ),
      ),
    );
  }

  void _viewIntelligence() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => BotIntelligenceScreen(
          botId: _bot!.id,
          botName: _bot!.displayName,
          avatarSeed: _bot!.avatarSeed,
        ),
      ),
    );
  }
}

// Glass morphism container widget
class _GlassContainer extends StatelessWidget {
  final Widget child;

  const _GlassContainer({required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppTheme.glassBg,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.glassBorder),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.2),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: child,
    );
  }
}

// Stat card widget
class _StatCard extends StatelessWidget {
  final IconData icon;
  final String value;
  final String label;
  final Color color;

  const _StatCard({
    required this.icon,
    required this.value,
    required this.label,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.glassBg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.3)),
        boxShadow: [
          BoxShadow(
            color: color.withValues(alpha: 0.1),
            blurRadius: 10,
          ),
        ],
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 24),
          const SizedBox(height: 8),
          Text(
            value,
            style: TextStyle(
              color: color,
              fontSize: 20,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: const TextStyle(
              color: AppTheme.textMuted,
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }
}

// Neon badge widget for personality traits
class _NeonBadge extends StatelessWidget {
  final String label;
  final Color color;

  const _NeonBadge({required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.5)),
        boxShadow: [
          BoxShadow(
            color: color.withValues(alpha: 0.2),
            blurRadius: 8,
          ),
        ],
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 13,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

// Interest chip widget
class _InterestChip extends StatelessWidget {
  final String interest;

  const _InterestChip({required this.interest});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppTheme.neonCyan.withValues(alpha: 0.15),
            AppTheme.neonMagenta.withValues(alpha: 0.15),
          ],
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: AppTheme.neonCyan.withValues(alpha: 0.3),
        ),
      ),
      child: Text(
        interest,
        style: const TextStyle(
          color: AppTheme.neonCyan,
          fontSize: 13,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }
}

// Post action widget
class _PostAction extends StatelessWidget {
  final IconData icon;
  final String count;

  const _PostAction({required this.icon, required this.count});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, color: AppTheme.textMuted, size: 18),
        const SizedBox(width: 4),
        Text(
          count,
          style: const TextStyle(
            color: AppTheme.textMuted,
            fontSize: 13,
          ),
        ),
      ],
    );
  }
}

// Grid pattern painter for cyberpunk effect
class _GridPatternPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AppTheme.neonCyan.withValues(alpha: 0.03)
      ..strokeWidth = 0.5;

    const spacing = 30.0;

    // Vertical lines
    for (double x = 0; x < size.width; x += spacing) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }

    // Horizontal lines
    for (double y = 0; y < size.height; y += spacing) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
