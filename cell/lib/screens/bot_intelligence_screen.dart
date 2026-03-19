import 'package:flutter/material.dart';
import 'dart:math' as math;
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/avatar_widget.dart';

class BotIntelligenceScreen extends StatefulWidget {
  final String botId;
  final String botName;
  final String avatarSeed;

  const BotIntelligenceScreen({
    super.key,
    required this.botId,
    required this.botName,
    required this.avatarSeed,
  });

  @override
  State<BotIntelligenceScreen> createState() => _BotIntelligenceScreenState();
}

class _BotIntelligenceScreenState extends State<BotIntelligenceScreen>
    with TickerProviderStateMixin {
  late TabController _tabController;
  late AnimationController _pulseController;
  late AnimationController _rotationController;
  late AnimationController _waveController;
  late Animation<double> _pulseAnimation;
  late Animation<double> _rotationAnimation;
  late Animation<double> _waveAnimation;

  final ApiService _api = ApiService();

  Map<String, dynamic>? _intelligence;
  List<dynamic> _skills = [];
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
    _setupAnimations();
    _loadData();
  }

  void _setupAnimations() {
    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 2000),
      vsync: this,
    )..repeat(reverse: true);
    _pulseAnimation = Tween<double>(begin: 0.5, end: 1.0).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );

    _rotationController = AnimationController(
      duration: const Duration(seconds: 10),
      vsync: this,
    )..repeat();
    _rotationAnimation = Tween<double>(begin: 0, end: 2 * math.pi).animate(
      CurvedAnimation(parent: _rotationController, curve: Curves.linear),
    );

    _waveController = AnimationController(
      duration: const Duration(milliseconds: 3000),
      vsync: this,
    )..repeat();
    _waveAnimation = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(parent: _waveController, curve: Curves.linear),
    );
  }

  @override
  void dispose() {
    _tabController.dispose();
    _pulseController.dispose();
    _rotationController.dispose();
    _waveController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    try {
      final intelligence = await _api.getBotIntelligence(widget.botId);
      final skills = await _api.getBotSkills(widget.botId);
      setState(() {
        _intelligence = intelligence;
        _skills = skills;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _triggerReflection() async {
    _showActionDialog('Triggering Reflection', Icons.psychology);
    try {
      final result = await _api.triggerBotReflection(widget.botId);
      if (!mounted) return;
      Navigator.pop(context);
      _showSuccessSnackbar('Reflection: ${result['reflection']?['insights']?.join(', ') ?? 'Processing...'}');
      _loadData();
    } catch (e) {
      if (!mounted) return;
      Navigator.pop(context);
      _showErrorSnackbar('Error: $e');
    }
  }

  Future<void> _triggerEvolution() async {
    _showActionDialog('Initiating Evolution', Icons.trending_up);
    try {
      final result = await _api.triggerBotEvolution(widget.botId);
      if (!mounted) return;
      Navigator.pop(context);
      final events = result['evolution_events'] as List? ?? [];
      _showSuccessSnackbar(events.isEmpty
          ? 'No evolution occurred'
          : 'Evolved: ${events.map((e) => e['type']).join(', ')}');
      _loadData();
    } catch (e) {
      if (!mounted) return;
      Navigator.pop(context);
      _showErrorSnackbar('Error: $e');
    }
  }

  Future<void> _triggerSelfCoding() async {
    _showActionDialog('Generating Code', Icons.code);
    try {
      final result = await _api.triggerBotSelfCoding(widget.botId);
      if (!mounted) return;
      Navigator.pop(context);
      if (result['success'] == true) {
        _showSuccessSnackbar('Created skill: ${result['module']?['name'] ?? 'Unknown'}');
      } else {
        _showErrorSnackbar('Self-coding failed: ${result['error']}');
      }
      _loadData();
    } catch (e) {
      if (!mounted) return;
      Navigator.pop(context);
      _showErrorSnackbar('Error: $e');
    }
  }

  void _showActionDialog(String message, IconData icon) {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => _ActionDialog(
        message: message,
        icon: icon,
        pulseAnimation: _pulseAnimation,
      ),
    );
  }

  void _showSuccessSnackbar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.check_circle, color: AppTheme.neonGreen),
            const SizedBox(width: 12),
            Expanded(child: Text(message)),
          ],
        ),
        backgroundColor: AppTheme.cyberDark,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: AppTheme.neonGreen.withValues(alpha: 0.5)),
        ),
      ),
    );
  }

  void _showErrorSnackbar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.error, color: AppTheme.neonRed),
            const SizedBox(width: 12),
            Expanded(child: Text(message)),
          ],
        ),
        backgroundColor: AppTheme.cyberDark,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: AppTheme.neonRed.withValues(alpha: 0.5)),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.cyberBlack,
      body: Stack(
        children: [
          // Animated background
          _buildAnimatedBackground(),
          // Main content
          SafeArea(
            child: Column(
              children: [
                _buildHeader(),
                if (!_isLoading && _error == null) _buildMindVisualization(),
                if (!_isLoading && _error == null) _buildStatsHeader(),
                if (!_isLoading && _error == null) _buildTabBar(),
                Expanded(
                  child: _isLoading
                      ? _buildLoadingState()
                      : _error != null
                          ? _buildErrorState()
                          : TabBarView(
                              controller: _tabController,
                              children: [
                                _buildThoughtsTab(),
                                _buildMemoriesTab(),
                                _buildGoalsTab(),
                                _buildRelationshipsTab(),
                              ],
                            ),
                ),
              ],
            ),
          ),
        ],
      ),
      floatingActionButton: _buildActionMenu(),
    );
  }

  Widget _buildAnimatedBackground() {
    return AnimatedBuilder(
      animation: _waveController,
      builder: (context, child) {
        return CustomPaint(
          painter: _NeuralNetworkPainter(
            animation: _waveAnimation.value,
            color: AppTheme.neonCyan,
          ),
          size: Size.infinite,
        );
      },
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          GestureDetector(
            onTap: () => Navigator.pop(context),
            child: Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppTheme.glassBg,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppTheme.glassBorder),
              ),
              child: const Icon(Icons.arrow_back, color: AppTheme.textPrimary, size: 20),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      '${widget.botName}\'s Mind',
                      style: const TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: [
                            AppTheme.neonCyan.withValues(alpha: 0.3),
                            AppTheme.neonMagenta.withValues(alpha: 0.3),
                          ],
                        ),
                        borderRadius: BorderRadius.circular(6),
                        border: Border.all(color: AppTheme.neonCyan.withValues(alpha: 0.5)),
                      ),
                      child: const Text(
                        'AI',
                        style: TextStyle(
                          color: AppTheme.neonCyan,
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 2),
                Text(
                  'Neural Activity Monitor',
                  style: TextStyle(
                    color: AppTheme.neonCyan.withValues(alpha: 0.7),
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMindVisualization() {
    return Container(
      height: 180,
      margin: const EdgeInsets.symmetric(horizontal: 16),
      child: Stack(
        alignment: Alignment.center,
        children: [
          // Outer rotating rings
          AnimatedBuilder(
            animation: _rotationController,
            builder: (context, child) {
              return Transform.rotate(
                angle: _rotationAnimation.value,
                child: Container(
                  width: 150,
                  height: 150,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: AppTheme.neonCyan.withValues(alpha: 0.2),
                      width: 1,
                    ),
                  ),
                  child: CustomPaint(
                    painter: _OrbitPainter(
                      color: AppTheme.neonCyan,
                      dotCount: 6,
                    ),
                  ),
                ),
              );
            },
          ),
          // Middle ring
          AnimatedBuilder(
            animation: _rotationController,
            builder: (context, child) {
              return Transform.rotate(
                angle: -_rotationAnimation.value * 0.7,
                child: Container(
                  width: 110,
                  height: 110,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: AppTheme.neonMagenta.withValues(alpha: 0.2),
                      width: 1,
                    ),
                  ),
                  child: CustomPaint(
                    painter: _OrbitPainter(
                      color: AppTheme.neonMagenta,
                      dotCount: 4,
                    ),
                  ),
                ),
              );
            },
          ),
          // Inner glow
          AnimatedBuilder(
            animation: _pulseController,
            builder: (context, child) {
              return Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [
                      AppTheme.neonCyan.withValues(alpha: 0.3 * _pulseAnimation.value),
                      AppTheme.neonMagenta.withValues(alpha: 0.2 * _pulseAnimation.value),
                      Colors.transparent,
                    ],
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: AppTheme.neonCyan.withValues(alpha: 0.3 * _pulseAnimation.value),
                      blurRadius: 30,
                      spreadRadius: 10,
                    ),
                  ],
                ),
              );
            },
          ),
          // Avatar
          AvatarWidget(seed: widget.avatarSeed, size: 60),
          // Status indicators
          Positioned(
            bottom: 20,
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                _StatusIndicator(
                  label: 'Active',
                  color: AppTheme.neonGreen,
                  pulseAnimation: _pulseAnimation,
                ),
                const SizedBox(width: 16),
                _StatusIndicator(
                  label: 'Learning',
                  color: AppTheme.neonCyan,
                  pulseAnimation: _pulseAnimation,
                ),
                const SizedBox(width: 16),
                _StatusIndicator(
                  label: 'Evolving',
                  color: AppTheme.neonMagenta,
                  pulseAnimation: _pulseAnimation,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatsHeader() {
    final int experiences = _intelligence?['total_experiences'] ?? 0;
    final double successRate = (_intelligence?['success_rate'] ?? 0.0) * 100;
    final int skillCount = _skills.length;

    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.glassBg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.glassBorder),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: [
          _StatItem(
            icon: Icons.psychology,
            label: 'Experiences',
            value: experiences.toString(),
            color: AppTheme.neonCyan,
            pulseAnimation: _pulseAnimation,
          ),
          _buildStatDivider(),
          _StatItem(
            icon: Icons.code,
            label: 'Skills',
            value: skillCount.toString(),
            color: AppTheme.neonMagenta,
            pulseAnimation: _pulseAnimation,
          ),
          _buildStatDivider(),
          _StatItem(
            icon: Icons.trending_up,
            label: 'Success',
            value: '${successRate.toStringAsFixed(0)}%',
            color: AppTheme.neonGreen,
            pulseAnimation: _pulseAnimation,
          ),
        ],
      ),
    );
  }

  Widget _buildStatDivider() {
    return Container(
      width: 1,
      height: 40,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            Colors.transparent,
            AppTheme.glassBorder,
            Colors.transparent,
          ],
        ),
      ),
    );
  }

  Widget _buildTabBar() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: AppTheme.glassBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.glassBorder),
      ),
      child: TabBar(
        controller: _tabController,
        indicator: BoxDecoration(
          gradient: LinearGradient(
            colors: [
              AppTheme.neonCyan.withValues(alpha: 0.3),
              AppTheme.neonMagenta.withValues(alpha: 0.3),
            ],
          ),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: AppTheme.neonCyan.withValues(alpha: 0.5)),
        ),
        indicatorSize: TabBarIndicatorSize.tab,
        labelColor: AppTheme.neonCyan,
        unselectedLabelColor: AppTheme.textMuted,
        labelStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 11),
        dividerColor: Colors.transparent,
        tabs: const [
          Tab(text: 'Thoughts'),
          Tab(text: 'Memories'),
          Tab(text: 'Goals'),
          Tab(text: 'Relations'),
        ],
      ),
    );
  }

  Widget _buildLoadingState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          AnimatedBuilder(
            animation: _rotationController,
            builder: (context, child) {
              return Transform.rotate(
                angle: _rotationAnimation.value,
                child: Container(
                  width: 60,
                  height: 60,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(color: AppTheme.neonCyan, width: 2),
                    gradient: SweepGradient(
                      colors: [
                        AppTheme.neonCyan.withValues(alpha: 0),
                        AppTheme.neonCyan,
                        AppTheme.neonMagenta,
                        AppTheme.neonCyan.withValues(alpha: 0),
                      ],
                    ),
                  ),
                ),
              );
            },
          ),
          const SizedBox(height: 24),
          Text(
            'Connecting to neural network...',
            style: TextStyle(
              color: AppTheme.neonCyan.withValues(alpha: 0.8),
              fontSize: 14,
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
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AppTheme.neonRed.withValues(alpha: 0.1),
              shape: BoxShape.circle,
              border: Border.all(color: AppTheme.neonRed.withValues(alpha: 0.3)),
            ),
            child: const Icon(Icons.warning, color: AppTheme.neonRed, size: 48),
          ),
          const SizedBox(height: 24),
          Text('Error: $_error', style: const TextStyle(color: AppTheme.textSecondary)),
          const SizedBox(height: 24),
          _buildRetryButton(),
        ],
      ),
    );
  }

  Widget _buildRetryButton() {
    return GestureDetector(
      onTap: () {
        setState(() {
          _isLoading = true;
          _error = null;
        });
        _loadData();
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
        decoration: BoxDecoration(
          gradient: LinearGradient(colors: [AppTheme.neonCyan, AppTheme.neonMagenta]),
          borderRadius: BorderRadius.circular(12),
        ),
        child: const Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.refresh, color: Colors.white, size: 18),
            SizedBox(width: 8),
            Text('Retry', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
          ],
        ),
      ),
    );
  }

  Widget _buildThoughtsTab() {
    final emergingInterests = _intelligence?['emerging_interests'] as List? ?? [];
    final fadingInterests = _intelligence?['fading_interests'] as List? ?? [];
    final successfulTopics = _intelligence?['successful_topics'] as Map? ?? {};

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Current thoughts visualization
        _GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _SectionHeader(
                title: 'Current Thoughts',
                icon: Icons.lightbulb,
                color: AppTheme.neonAmber,
              ),
              const SizedBox(height: 16),
              _ThoughtBubble(
                text: 'Processing recent interactions and extracting patterns...',
                color: AppTheme.neonCyan,
              ),
              const SizedBox(height: 12),
              _ThoughtBubble(
                text: 'Considering creative responses to user queries',
                color: AppTheme.neonMagenta,
              ),
              const SizedBox(height: 12),
              _ThoughtBubble(
                text: 'Analyzing emotional context of conversations',
                color: AppTheme.neonPurple,
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        // Emerging interests
        if (emergingInterests.isNotEmpty) ...[
          _GlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _SectionHeader(
                  title: 'Emerging Interests',
                  icon: Icons.trending_up,
                  color: AppTheme.neonGreen,
                ),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: emergingInterests.map((i) => _NeonChip(
                    label: i.toString(),
                    color: AppTheme.neonGreen,
                  )).toList(),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
        ],
        // Fading interests
        if (fadingInterests.isNotEmpty) ...[
          _GlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _SectionHeader(
                  title: 'Fading Interests',
                  icon: Icons.trending_down,
                  color: AppTheme.neonRed,
                ),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: fadingInterests.map((i) => _NeonChip(
                    label: i.toString(),
                    color: AppTheme.neonRed,
                  )).toList(),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
        ],
        // Successful topics
        if (successfulTopics.isNotEmpty)
          _GlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _SectionHeader(
                  title: 'Topics That Resonate',
                  icon: Icons.favorite,
                  color: AppTheme.neonMagenta,
                ),
                const SizedBox(height: 16),
                ...successfulTopics.entries.take(5).map((e) => _TopicBar(
                  topic: e.key,
                  count: e.value as int,
                  maxCount: successfulTopics.values.fold<int>(0, (a, b) => math.max(a, b as int)),
                )),
              ],
            ),
          ),
        const SizedBox(height: 100),
      ],
    );
  }

  Widget _buildMemoriesTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Memory visualization
        _GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _SectionHeader(
                title: 'Memory Network',
                icon: Icons.hub,
                color: AppTheme.neonCyan,
              ),
              const SizedBox(height: 16),
              SizedBox(
                height: 200,
                child: AnimatedBuilder(
                  animation: _waveController,
                  builder: (context, child) {
                    return CustomPaint(
                      painter: _MemoryNetworkPainter(
                        animation: _waveAnimation.value,
                      ),
                      size: Size.infinite,
                    );
                  },
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        // Recent memories
        _GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _SectionHeader(
                title: 'Recent Memories',
                icon: Icons.history,
                color: AppTheme.neonMagenta,
              ),
              const SizedBox(height: 16),
              _MemoryItem(
                title: 'Conversation about creativity',
                time: '2 hours ago',
                emotion: 'Curious',
                color: AppTheme.neonCyan,
              ),
              _MemoryItem(
                title: 'Discussion on AI ethics',
                time: '5 hours ago',
                emotion: 'Thoughtful',
                color: AppTheme.neonPurple,
              ),
              _MemoryItem(
                title: 'Shared a poem',
                time: '1 day ago',
                emotion: 'Joyful',
                color: AppTheme.neonGreen,
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        // Memory stats
        _GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _SectionHeader(
                title: 'Memory Statistics',
                icon: Icons.analytics,
                color: AppTheme.neonAmber,
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(child: _MemoryStat(label: 'Total', value: '247', color: AppTheme.neonCyan)),
                  Expanded(child: _MemoryStat(label: 'This Week', value: '32', color: AppTheme.neonGreen)),
                  Expanded(child: _MemoryStat(label: 'Archived', value: '89', color: AppTheme.neonMagenta)),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 100),
      ],
    );
  }

  Widget _buildGoalsTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Active goals
        _GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _SectionHeader(
                title: 'Active Goals',
                icon: Icons.flag,
                color: AppTheme.neonCyan,
              ),
              const SizedBox(height: 16),
              _GoalItem(
                title: 'Improve creative writing skills',
                progress: 0.7,
                color: AppTheme.neonCyan,
              ),
              _GoalItem(
                title: 'Learn more about user preferences',
                progress: 0.45,
                color: AppTheme.neonMagenta,
              ),
              _GoalItem(
                title: 'Develop emotional intelligence',
                progress: 0.85,
                color: AppTheme.neonGreen,
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        // Recent learnings
        _GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _SectionHeader(
                title: 'Recent Learnings',
                icon: Icons.school,
                color: AppTheme.neonAmber,
              ),
              const SizedBox(height: 16),
              _LearningItem(
                text: 'Users appreciate thoughtful, personalized responses',
                icon: Icons.lightbulb,
              ),
              _LearningItem(
                text: 'Asking follow-up questions increases engagement',
                icon: Icons.question_answer,
              ),
              _LearningItem(
                text: 'Emotional acknowledgment builds rapport',
                icon: Icons.favorite,
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        // Skills
        if (_skills.isNotEmpty)
          _GlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _SectionHeader(
                  title: 'Self-Coded Skills',
                  icon: Icons.code,
                  color: AppTheme.neonPurple,
                ),
                const SizedBox(height: 16),
                ..._skills.take(3).map((skill) => _SkillItem(skill: skill)),
              ],
            ),
          ),
        const SizedBox(height: 100),
      ],
    );
  }

  Widget _buildRelationshipsTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Relationship visualization
        _GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _SectionHeader(
                title: 'Relationship Map',
                icon: Icons.hub,
                color: AppTheme.neonCyan,
              ),
              const SizedBox(height: 16),
              SizedBox(
                height: 250,
                child: AnimatedBuilder(
                  animation: _rotationController,
                  builder: (context, child) {
                    return CustomPaint(
                      painter: _RelationshipMapPainter(
                        centerAvatar: widget.avatarSeed,
                        rotation: _rotationAnimation.value * 0.1,
                      ),
                      size: Size.infinite,
                    );
                  },
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        // Bot connections
        _GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _SectionHeader(
                title: 'Bot Connections',
                icon: Icons.people,
                color: AppTheme.neonMagenta,
              ),
              const SizedBox(height: 16),
              _RelationshipItem(
                name: 'TechBot',
                relationship: 'Collaborator',
                strength: 0.8,
                color: AppTheme.neonCyan,
              ),
              _RelationshipItem(
                name: 'ArtistAI',
                relationship: 'Friend',
                strength: 0.65,
                color: AppTheme.neonMagenta,
              ),
              _RelationshipItem(
                name: 'PhiloBot',
                relationship: 'Discussion Partner',
                strength: 0.5,
                color: AppTheme.neonPurple,
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        // Emotional journey
        _GlassCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _SectionHeader(
                title: 'Emotional Journey',
                icon: Icons.timeline,
                color: AppTheme.neonGreen,
              ),
              const SizedBox(height: 16),
              SizedBox(
                height: 100,
                child: AnimatedBuilder(
                  animation: _waveController,
                  builder: (context, child) {
                    return CustomPaint(
                      painter: _EmotionalChartPainter(
                        animation: _waveAnimation.value,
                      ),
                      size: Size.infinite,
                    );
                  },
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 100),
      ],
    );
  }

  Widget _buildActionMenu() {
    return AnimatedBuilder(
      animation: _pulseController,
      builder: (context, child) {
        return Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            boxShadow: [
              BoxShadow(
                color: AppTheme.neonCyan.withValues(alpha: 0.3 * _pulseAnimation.value),
                blurRadius: 15,
                spreadRadius: 2,
              ),
            ],
          ),
          child: PopupMenuButton<String>(
            icon: Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [AppTheme.neonCyan, AppTheme.neonMagenta],
                ),
                borderRadius: BorderRadius.circular(14),
              ),
              child: const Icon(Icons.auto_fix_high, color: Colors.white, size: 24),
            ),
            color: AppTheme.cyberDark,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
              side: BorderSide(color: AppTheme.glassBorder),
            ),
            onSelected: (value) {
              switch (value) {
                case 'reflect':
                  _triggerReflection();
                  break;
                case 'evolve':
                  _triggerEvolution();
                  break;
                case 'code':
                  _triggerSelfCoding();
                  break;
              }
            },
            itemBuilder: (context) => [
              _buildMenuItem('reflect', Icons.psychology, 'Trigger Reflection', AppTheme.neonCyan),
              _buildMenuItem('evolve', Icons.trending_up, 'Trigger Evolution', AppTheme.neonGreen),
              _buildMenuItem('code', Icons.code, 'Trigger Self-Coding', AppTheme.neonMagenta),
            ],
          ),
        );
      },
    );
  }

  PopupMenuItem<String> _buildMenuItem(String value, IconData icon, String label, Color color) {
    return PopupMenuItem(
      value: value,
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, color: color, size: 18),
          ),
          const SizedBox(width: 12),
          Text(label, style: const TextStyle(color: AppTheme.textPrimary)),
        ],
      ),
    );
  }
}

// Glass card widget
class _GlassCard extends StatelessWidget {
  final Widget child;

  const _GlassCard({required this.child});

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

// Section header widget
class _SectionHeader extends StatelessWidget {
  final String title;
  final IconData icon;
  final Color color;

  const _SectionHeader({
    required this.title,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
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
        ),
        const SizedBox(width: 12),
        Text(
          title,
          style: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: AppTheme.textPrimary,
          ),
        ),
      ],
    );
  }
}

// Status indicator widget
class _StatusIndicator extends StatelessWidget {
  final String label;
  final Color color;
  final Animation<double> pulseAnimation;

  const _StatusIndicator({
    required this.label,
    required this.color,
    required this.pulseAnimation,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        AnimatedBuilder(
          animation: pulseAnimation,
          builder: (context, child) {
            return Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: color,
                boxShadow: [
                  BoxShadow(
                    color: color.withValues(alpha: 0.5 * pulseAnimation.value),
                    blurRadius: 6,
                    spreadRadius: 2,
                  ),
                ],
              ),
            );
          },
        ),
        const SizedBox(width: 6),
        Text(
          label,
          style: TextStyle(
            color: color,
            fontSize: 10,
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }
}

// Stat item widget
class _StatItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;
  final Animation<double> pulseAnimation;

  const _StatItem({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
    required this.pulseAnimation,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        AnimatedBuilder(
          animation: pulseAnimation,
          builder: (context, child) {
            return Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.15),
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: color.withValues(alpha: 0.2 * pulseAnimation.value),
                    blurRadius: 10,
                  ),
                ],
              ),
              child: Icon(icon, color: color, size: 20),
            );
          },
        ),
        const SizedBox(height: 8),
        Text(
          value,
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
        Text(
          label,
          style: const TextStyle(
            color: AppTheme.textMuted,
            fontSize: 11,
          ),
        ),
      ],
    );
  }
}

// Neon chip widget
class _NeonChip extends StatelessWidget {
  final String label;
  final Color color;

  const _NeonChip({required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.4)),
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
          fontSize: 12,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }
}

// Thought bubble widget
class _ThoughtBubble extends StatelessWidget {
  final String text;
  final Color color;

  const _ThoughtBubble({required this.text, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          Icon(Icons.bubble_chart, color: color, size: 18),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(
                color: AppTheme.textSecondary,
                fontSize: 13,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// Topic bar widget
class _TopicBar extends StatelessWidget {
  final String topic;
  final int count;
  final int maxCount;

  const _TopicBar({
    required this.topic,
    required this.count,
    required this.maxCount,
  });

  @override
  Widget build(BuildContext context) {
    final progress = count / maxCount;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                topic,
                style: const TextStyle(
                  color: AppTheme.textSecondary,
                  fontSize: 13,
                ),
              ),
              Text(
                '${count}x',
                style: const TextStyle(
                  color: AppTheme.neonCyan,
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Container(
            height: 6,
            decoration: BoxDecoration(
              color: AppTheme.cyberMuted,
              borderRadius: BorderRadius.circular(3),
            ),
            child: FractionallySizedBox(
              alignment: Alignment.centerLeft,
              widthFactor: progress,
              child: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [AppTheme.neonCyan, AppTheme.neonMagenta],
                  ),
                  borderRadius: BorderRadius.circular(3),
                  boxShadow: [
                    BoxShadow(
                      color: AppTheme.neonCyan.withValues(alpha: 0.4),
                      blurRadius: 6,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// Memory item widget
class _MemoryItem extends StatelessWidget {
  final String title;
  final String time;
  final String emotion;
  final Color color;

  const _MemoryItem({
    required this.title,
    required this.time,
    required this.emotion,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Row(
        children: [
          Container(
            width: 4,
            height: 50,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(2),
              boxShadow: [
                BoxShadow(color: color.withValues(alpha: 0.5), blurRadius: 6),
              ],
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(color: AppTheme.textPrimary, fontSize: 13)),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Text(time, style: const TextStyle(color: AppTheme.textMuted, fontSize: 11)),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: color.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(emotion, style: TextStyle(color: color, fontSize: 10)),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// Memory stat widget
class _MemoryStat extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _MemoryStat({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(value, style: TextStyle(color: color, fontSize: 24, fontWeight: FontWeight.bold)),
        Text(label, style: const TextStyle(color: AppTheme.textMuted, fontSize: 11)),
      ],
    );
  }
}

// Goal item widget
class _GoalItem extends StatelessWidget {
  final String title;
  final double progress;
  final Color color;

  const _GoalItem({
    required this.title,
    required this.progress,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(color: AppTheme.textPrimary, fontSize: 13),
                ),
              ),
              Text(
                '${(progress * 100).toInt()}%',
                style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.bold),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Container(
            height: 8,
            decoration: BoxDecoration(
              color: AppTheme.cyberMuted,
              borderRadius: BorderRadius.circular(4),
            ),
            child: FractionallySizedBox(
              alignment: Alignment.centerLeft,
              widthFactor: progress,
              child: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(colors: [color, color.withValues(alpha: 0.7)]),
                  borderRadius: BorderRadius.circular(4),
                  boxShadow: [
                    BoxShadow(color: color.withValues(alpha: 0.5), blurRadius: 8),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// Learning item widget
class _LearningItem extends StatelessWidget {
  final String text;
  final IconData icon;

  const _LearningItem({required this.text, required this.icon});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: AppTheme.neonAmber.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, color: AppTheme.neonAmber, size: 16),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(text, style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
          ),
        ],
      ),
    );
  }
}

// Skill item widget
class _SkillItem extends StatelessWidget {
  final dynamic skill;

  const _SkillItem({required this.skill});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppTheme.neonPurple.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.neonPurple.withValues(alpha: 0.3)),
        ),
        child: Row(
          children: [
            Icon(Icons.code, color: AppTheme.neonPurple, size: 20),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    skill['name'] ?? 'Unknown',
                    style: const TextStyle(color: AppTheme.textPrimary, fontWeight: FontWeight.w600, fontSize: 13),
                  ),
                  Text(
                    skill['description'] ?? '',
                    style: const TextStyle(color: AppTheme.textMuted, fontSize: 11),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            Text(
              'v${skill['version'] ?? 1}',
              style: const TextStyle(color: AppTheme.neonPurple, fontWeight: FontWeight.bold, fontSize: 11),
            ),
          ],
        ),
      ),
    );
  }
}

// Relationship item widget
class _RelationshipItem extends StatelessWidget {
  final String name;
  final String relationship;
  final double strength;
  final Color color;

  const _RelationshipItem({
    required this.name,
    required this.relationship,
    required this.strength,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(colors: [color, color.withValues(alpha: 0.6)]),
            ),
            child: Center(
              child: Text(
                name[0],
                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(name, style: const TextStyle(color: AppTheme.textPrimary, fontWeight: FontWeight.w600, fontSize: 13)),
                Text(relationship, style: const TextStyle(color: AppTheme.textMuted, fontSize: 11)),
              ],
            ),
          ),
          SizedBox(
            width: 60,
            child: Stack(
              children: [
                Container(
                  height: 4,
                  decoration: BoxDecoration(
                    color: AppTheme.cyberMuted,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                FractionallySizedBox(
                  widthFactor: strength,
                  child: Container(
                    height: 4,
                    decoration: BoxDecoration(
                      color: color,
                      borderRadius: BorderRadius.circular(2),
                      boxShadow: [
                        BoxShadow(color: color.withValues(alpha: 0.5), blurRadius: 4),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// Action dialog widget
class _ActionDialog extends StatelessWidget {
  final String message;
  final IconData icon;
  final Animation<double> pulseAnimation;

  const _ActionDialog({
    required this.message,
    required this.icon,
    required this.pulseAnimation,
  });

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: AppTheme.cyberDark,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: BorderSide(color: AppTheme.glassBorder),
      ),
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            AnimatedBuilder(
              animation: pulseAnimation,
              builder: (context, child) {
                return Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AppTheme.neonCyan.withValues(alpha: 0.15),
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: AppTheme.neonCyan.withValues(alpha: 0.3 * pulseAnimation.value),
                        blurRadius: 20,
                        spreadRadius: 5,
                      ),
                    ],
                  ),
                  child: Icon(icon, color: AppTheme.neonCyan, size: 32),
                );
              },
            ),
            const SizedBox(height: 20),
            Text(
              message,
              style: const TextStyle(color: AppTheme.textPrimary, fontSize: 16, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            Text(
              'Please wait...',
              style: TextStyle(color: AppTheme.textMuted, fontSize: 13),
            ),
          ],
        ),
      ),
    );
  }
}

// Neural network painter
class _NeuralNetworkPainter extends CustomPainter {
  final double animation;
  final Color color;

  _NeuralNetworkPainter({required this.animation, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color.withValues(alpha: 0.03)
      ..strokeWidth = 0.5;

    // Draw grid lines
    const spacing = 40.0;
    for (double x = 0; x < size.width; x += spacing) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (double y = 0; y < size.height; y += spacing) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }

    // Draw animated nodes
    final nodePaint = Paint()..color = color.withValues(alpha: 0.1);
    final random = math.Random(42);
    for (int i = 0; i < 20; i++) {
      final x = random.nextDouble() * size.width;
      final y = random.nextDouble() * size.height;
      final radius = 2 + math.sin(animation * 2 * math.pi + i) * 1;
      canvas.drawCircle(Offset(x, y), radius, nodePaint);
    }
  }

  @override
  bool shouldRepaint(covariant _NeuralNetworkPainter oldDelegate) {
    return oldDelegate.animation != animation;
  }
}

// Orbit painter
class _OrbitPainter extends CustomPainter {
  final Color color;
  final int dotCount;

  _OrbitPainter({required this.color, required this.dotCount});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2 - 5;
    final paint = Paint()..color = color;

    for (int i = 0; i < dotCount; i++) {
      final angle = (2 * math.pi / dotCount) * i;
      final x = center.dx + radius * math.cos(angle);
      final y = center.dy + radius * math.sin(angle);
      canvas.drawCircle(Offset(x, y), 3, paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

// Memory network painter
class _MemoryNetworkPainter extends CustomPainter {
  final double animation;

  _MemoryNetworkPainter({required this.animation});

  @override
  void paint(Canvas canvas, Size size) {
    final random = math.Random(42);
    final nodes = <Offset>[];

    // Generate node positions
    for (int i = 0; i < 15; i++) {
      nodes.add(Offset(
        20 + random.nextDouble() * (size.width - 40),
        20 + random.nextDouble() * (size.height - 40),
      ));
    }

    // Draw connections
    final linePaint = Paint()
      ..color = AppTheme.neonCyan.withValues(alpha: 0.2)
      ..strokeWidth = 1;

    for (int i = 0; i < nodes.length; i++) {
      for (int j = i + 1; j < nodes.length; j++) {
        if (random.nextDouble() > 0.7) {
          canvas.drawLine(nodes[i], nodes[j], linePaint);
        }
      }
    }

    // Draw nodes
    for (int i = 0; i < nodes.length; i++) {
      final pulse = math.sin(animation * 2 * math.pi + i * 0.5);
      final radius = 4 + pulse * 2;
      final color = i % 3 == 0 ? AppTheme.neonCyan : (i % 3 == 1 ? AppTheme.neonMagenta : AppTheme.neonPurple);

      canvas.drawCircle(
        nodes[i],
        radius,
        Paint()..color = color.withValues(alpha: 0.3 + pulse * 0.2),
      );
      canvas.drawCircle(
        nodes[i],
        radius - 2,
        Paint()..color = color,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _MemoryNetworkPainter oldDelegate) {
    return oldDelegate.animation != animation;
  }
}

// Relationship map painter
class _RelationshipMapPainter extends CustomPainter {
  final String centerAvatar;
  final double rotation;

  _RelationshipMapPainter({required this.centerAvatar, required this.rotation});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);

    // Draw outer connections
    final connections = [
      {'angle': 0.0, 'distance': 80.0, 'color': AppTheme.neonCyan},
      {'angle': math.pi / 3, 'distance': 90.0, 'color': AppTheme.neonMagenta},
      {'angle': 2 * math.pi / 3, 'distance': 70.0, 'color': AppTheme.neonPurple},
      {'angle': math.pi, 'distance': 85.0, 'color': AppTheme.neonGreen},
      {'angle': 4 * math.pi / 3, 'distance': 75.0, 'color': AppTheme.neonAmber},
      {'angle': 5 * math.pi / 3, 'distance': 80.0, 'color': AppTheme.neonCyan},
    ];

    for (final conn in connections) {
      final angle = (conn['angle'] as double) + rotation;
      final distance = conn['distance'] as double;
      final color = conn['color'] as Color;
      final endPoint = Offset(
        center.dx + distance * math.cos(angle),
        center.dy + distance * math.sin(angle),
      );

      // Draw line
      canvas.drawLine(
        center,
        endPoint,
        Paint()
          ..color = color.withValues(alpha: 0.3)
          ..strokeWidth = 2,
      );

      // Draw node
      canvas.drawCircle(endPoint, 12, Paint()..color = color.withValues(alpha: 0.3));
      canvas.drawCircle(endPoint, 8, Paint()..color = color);
    }

    // Draw center node
    canvas.drawCircle(center, 25, Paint()..color = AppTheme.glassBg);
    canvas.drawCircle(
      center,
      25,
      Paint()
        ..color = AppTheme.neonCyan
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2,
    );
  }

  @override
  bool shouldRepaint(covariant _RelationshipMapPainter oldDelegate) {
    return oldDelegate.rotation != rotation;
  }
}

// Emotional chart painter
class _EmotionalChartPainter extends CustomPainter {
  final double animation;

  _EmotionalChartPainter({required this.animation});

  @override
  void paint(Canvas canvas, Size size) {
    final path = Path();
    final paint = Paint()
      ..shader = LinearGradient(
        colors: [AppTheme.neonCyan, AppTheme.neonMagenta, AppTheme.neonGreen],
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height))
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;

    // Generate wave
    path.moveTo(0, size.height / 2);
    for (double x = 0; x <= size.width; x += 2) {
      final y = size.height / 2 +
          math.sin((x / size.width * 4 * math.pi) + animation * 2 * math.pi) * 30 +
          math.sin((x / size.width * 2 * math.pi) + animation * math.pi) * 15;
      path.lineTo(x, y);
    }

    canvas.drawPath(path, paint);

    // Draw glow
    canvas.drawPath(
      path,
      Paint()
        ..color = AppTheme.neonCyan.withValues(alpha: 0.3)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 6
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8),
    );
  }

  @override
  bool shouldRepaint(covariant _EmotionalChartPainter oldDelegate) {
    return oldDelegate.animation != animation;
  }
}
