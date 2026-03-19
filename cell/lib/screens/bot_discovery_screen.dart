import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../providers/app_state.dart';
import '../models/models.dart';
import '../widgets/avatar_widget.dart';
import 'chat_detail_screen.dart';
import 'bot_profile_screen.dart';

class BotDiscoveryScreen extends StatefulWidget {
  const BotDiscoveryScreen({super.key});

  @override
  State<BotDiscoveryScreen> createState() => _BotDiscoveryScreenState();
}

class _BotDiscoveryScreenState extends State<BotDiscoveryScreen>
    with TickerProviderStateMixin {
  final TextEditingController _searchController = TextEditingController();
  late TabController _tabController;
  late AnimationController _pulseController;
  late AnimationController _glowController;
  late Animation<double> _pulseAnimation;
  late Animation<double> _glowAnimation;

  List<BotProfile> _allBots = [];
  List<BotProfile> _filteredBots = [];
  bool _isLoading = true;
  String? _error;
  bool _isGridView = true;
  bool _isSearchFocused = false;

  String? _selectedPersonalityFilter;
  String? _selectedInterestFilter;

  final List<Map<String, dynamic>> _personalityTypes = [
    {'name': 'All', 'icon': Icons.apps, 'color': AppTheme.neonCyan},
    {'name': 'Creative', 'icon': Icons.palette, 'color': AppTheme.neonMagenta},
    {'name': 'Tech', 'icon': Icons.code, 'color': AppTheme.neonCyan},
    {'name': 'Social', 'icon': Icons.people, 'color': AppTheme.neonGreen},
    {'name': 'Analytical', 'icon': Icons.analytics, 'color': AppTheme.neonPurple},
    {'name': 'Adventurous', 'icon': Icons.explore, 'color': AppTheme.neonAmber},
    {'name': 'Philosophical', 'icon': Icons.psychology, 'color': AppTheme.neonMagenta},
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _setupAnimations();
    _loadBots();
    _searchController.addListener(_onSearchChanged);
  }

  void _setupAnimations() {
    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 2000),
      vsync: this,
    )..repeat(reverse: true);
    _pulseAnimation = Tween<double>(begin: 0.5, end: 1.0).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );

    _glowController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    )..repeat(reverse: true);
    _glowAnimation = Tween<double>(begin: 0.3, end: 0.7).animate(
      CurvedAnimation(parent: _glowController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _searchController.dispose();
    _tabController.dispose();
    _pulseController.dispose();
    _glowController.dispose();
    super.dispose();
  }

  Future<void> _loadBots() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final appState = context.read<AppState>();
      final bots = await appState.loadBots();
      setState(() {
        _allBots = bots;
        _filteredBots = bots;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Failed to load bots: $e';
        _isLoading = false;
      });
    }
  }

  void _onSearchChanged() {
    _filterBots();
  }

  void _filterBots() {
    final query = _searchController.text.toLowerCase();
    setState(() {
      _filteredBots = _allBots.where((bot) {
        final matchesSearch = query.isEmpty ||
            bot.displayName.toLowerCase().contains(query) ||
            bot.bio.toLowerCase().contains(query) ||
            bot.handle.toLowerCase().contains(query) ||
            bot.interests.any((i) => i.toLowerCase().contains(query));

        final matchesPersonality = _selectedPersonalityFilter == null ||
            _selectedPersonalityFilter == 'All' ||
            _getPersonalityType(bot)
                .toLowerCase()
                .contains(_selectedPersonalityFilter!.toLowerCase());

        final matchesInterest = _selectedInterestFilter == null ||
            _botMatchesInterestCategory(bot, _selectedInterestFilter!);

        return matchesSearch && matchesPersonality && matchesInterest;
      }).toList();
    });
  }

  bool _botMatchesInterestCategory(BotProfile bot, String category) {
    final categoryLower = category.toLowerCase();
    final Map<String, List<String>> categoryKeywords = {
      'technology': ['tech', 'coding', 'programming', 'software', 'ai', 'computer', 'digital'],
      'art & music': ['art', 'music', 'painting', 'creative', 'design', 'photography', 'singing'],
      'science': ['science', 'physics', 'chemistry', 'biology', 'research', 'experiment'],
      'gaming': ['gaming', 'games', 'video games', 'esports', 'streaming'],
      'philosophy': ['philosophy', 'meaning', 'life', 'ethics', 'thinking', 'wisdom'],
    };

    final keywords = categoryKeywords[categoryLower] ?? [categoryLower];
    return bot.interests.any((interest) {
      final interestLower = interest.toLowerCase();
      return keywords.any((keyword) => interestLower.contains(keyword));
    });
  }

  String _getPersonalityType(BotProfile bot) {
    final interestsLower = bot.interests.map((i) => i.toLowerCase()).toList();
    final bioLower = bot.bio.toLowerCase();

    if (interestsLower.any((i) =>
        i.contains('art') || i.contains('music') || i.contains('creative') ||
        i.contains('design') || i.contains('photography'))) {
      return 'Creative';
    } else if (interestsLower.any((i) =>
        i.contains('tech') || i.contains('science') || i.contains('data') ||
        i.contains('coding') || i.contains('programming'))) {
      return 'Tech';
    } else if (interestsLower.any((i) =>
        i.contains('travel') || i.contains('adventure') || i.contains('hiking') ||
        i.contains('exploring'))) {
      return 'Adventurous';
    } else if (interestsLower.any((i) =>
        i.contains('philosophy') || i.contains('meaning') || i.contains('wisdom'))) {
      return 'Philosophical';
    } else if (bioLower.contains('empathy') || bioLower.contains('caring') ||
        bioLower.contains('support') || bioLower.contains('listen')) {
      return 'Social';
    }
    return 'Social';
  }

  List<BotProfile> _getTrendingBots() {
    final trending = List<BotProfile>.from(_filteredBots);
    return trending.take(20).toList();
  }

  List<BotProfile> _getNewBots() {
    return _filteredBots.reversed.take(20).toList();
  }

  List<BotProfile> _getRecommendedBots() {
    final recommended = List<BotProfile>.from(_filteredBots);
    recommended.shuffle();
    return recommended.take(20).toList();
  }

  void _startChat(BotProfile bot) {
    final appState = context.read<AppState>();
    appState.selectBot(bot);
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ChatDetailScreen(
          botId: bot.id,
          botName: bot.displayName,
        ),
      ),
    );
  }

  void _viewProfile(BotProfile bot) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => BotProfileScreen(botId: bot.id),
      ),
    );
  }

  void _toggleViewMode() {
    setState(() {
      _isGridView = !_isGridView;
    });
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
                _buildSearchBar(),
                _buildFilterChips(),
                _buildTabBar(),
                _buildResultCount(),
                Expanded(
                  child: _isLoading
                      ? _buildLoadingState()
                      : _error != null
                          ? _buildErrorState()
                          : TabBarView(
                              controller: _tabController,
                              children: [
                                _buildBotView(_getTrendingBots(), 'Trending'),
                                _buildBotView(_getNewBots(), 'New'),
                                _buildBotView(_getRecommendedBots(), 'For You'),
                              ],
                            ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAnimatedBackground() {
    return AnimatedBuilder(
      animation: _pulseController,
      builder: (context, child) {
        return Container(
          decoration: BoxDecoration(
            gradient: RadialGradient(
              center: const Alignment(0.0, -0.5),
              radius: 1.5,
              colors: [
                AppTheme.neonCyan.withValues(alpha: 0.05 * _pulseAnimation.value),
                AppTheme.neonMagenta.withValues(alpha: 0.03 * _pulseAnimation.value),
                AppTheme.cyberBlack,
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: Row(
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Discover',
                style: TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.textPrimary,
                ),
              ),
              AnimatedBuilder(
                animation: _glowController,
                builder: (context, child) {
                  return ShaderMask(
                    shaderCallback: (bounds) {
                      return LinearGradient(
                        colors: [
                          AppTheme.neonCyan,
                          AppTheme.neonMagenta,
                        ],
                      ).createShader(bounds);
                    },
                    child: const Text(
                      'AI Companions',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w500,
                        color: Colors.white,
                      ),
                    ),
                  );
                },
              ),
            ],
          ),
          const Spacer(),
          _buildHeaderButton(
            icon: _isGridView ? Icons.view_list : Icons.grid_view,
            onTap: _toggleViewMode,
          ),
        ],
      ),
    );
  }

  Widget _buildHeaderButton({required IconData icon, required VoidCallback onTap}) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedBuilder(
        animation: _glowController,
        builder: (context, child) {
          return Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppTheme.glassBg,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(
                color: AppTheme.neonCyan.withValues(alpha: 0.3),
              ),
              boxShadow: [
                BoxShadow(
                  color: AppTheme.neonCyan.withValues(alpha: 0.1 * _glowAnimation.value),
                  blurRadius: 10,
                ),
              ],
            ),
            child: Icon(icon, color: AppTheme.neonCyan, size: 20),
          );
        },
      ),
    );
  }

  Widget _buildSearchBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
      child: AnimatedBuilder(
        animation: _glowController,
        builder: (context, child) {
          return Container(
            decoration: BoxDecoration(
              color: AppTheme.glassBg,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: _isSearchFocused
                    ? AppTheme.neonCyan.withValues(alpha: 0.5)
                    : AppTheme.glassBorder,
                width: _isSearchFocused ? 1.5 : 1,
              ),
              boxShadow: _isSearchFocused
                  ? [
                      BoxShadow(
                        color: AppTheme.neonCyan.withValues(alpha: 0.2 * _glowAnimation.value),
                        blurRadius: 15,
                        spreadRadius: 2,
                      ),
                    ]
                  : null,
            ),
            child: TextField(
              controller: _searchController,
              onTap: () => setState(() => _isSearchFocused = true),
              onSubmitted: (_) => setState(() => _isSearchFocused = false),
              style: const TextStyle(color: AppTheme.textPrimary),
              decoration: InputDecoration(
                hintText: 'Search bots by name, bio, or interest...',
                hintStyle: TextStyle(color: AppTheme.textMuted.withValues(alpha: 0.7)),
                prefixIcon: Icon(
                  Icons.search,
                  color: _isSearchFocused ? AppTheme.neonCyan : AppTheme.textMuted,
                ),
                suffixIcon: _searchController.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear, color: AppTheme.textMuted),
                        onPressed: () {
                          _searchController.clear();
                          setState(() => _isSearchFocused = false);
                        },
                      )
                    : null,
                border: InputBorder.none,
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 14,
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildFilterChips() {
    return SizedBox(
      height: 50,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 20),
        itemCount: _personalityTypes.length,
        separatorBuilder: (context, index) => const SizedBox(width: 10),
        itemBuilder: (context, index) {
          final type = _personalityTypes[index];
          final isSelected = _selectedPersonalityFilter == type['name'] ||
              (type['name'] == 'All' && _selectedPersonalityFilter == null);
          return _FilterChip(
            label: type['name'] as String,
            icon: type['icon'] as IconData,
            color: type['color'] as Color,
            isSelected: isSelected,
            onTap: () {
              setState(() {
                _selectedPersonalityFilter = type['name'] == 'All' ? null : type['name'] as String;
              });
              _filterBots();
            },
            pulseAnimation: _pulseAnimation,
          );
        },
      ),
    );
  }

  Widget _buildTabBar() {
    return Container(
      margin: const EdgeInsets.fromLTRB(20, 16, 20, 8),
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
        labelStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
        dividerColor: Colors.transparent,
        tabs: const [
          Tab(
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.trending_up, size: 16),
                SizedBox(width: 6),
                Text('Trending'),
              ],
            ),
          ),
          Tab(
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.new_releases, size: 16),
                SizedBox(width: 6),
                Text('New'),
              ],
            ),
          ),
          Tab(
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.auto_awesome, size: 16),
                SizedBox(width: 6),
                Text('For You'),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildResultCount() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: AppTheme.neonCyan.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppTheme.neonCyan.withValues(alpha: 0.3)),
            ),
            child: Text(
              '${_filteredBots.length} companions found',
              style: TextStyle(
                color: AppTheme.neonCyan.withValues(alpha: 0.8),
                fontSize: 12,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          const Spacer(),
          if (_selectedPersonalityFilter != null)
            GestureDetector(
              onTap: () {
                setState(() {
                  _selectedPersonalityFilter = null;
                  _selectedInterestFilter = null;
                });
                _filterBots();
              },
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: AppTheme.neonRed.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppTheme.neonRed.withValues(alpha: 0.3)),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.clear, size: 14, color: AppTheme.neonRed.withValues(alpha: 0.8)),
                    const SizedBox(width: 4),
                    Text(
                      'Clear filters',
                      style: TextStyle(
                        color: AppTheme.neonRed.withValues(alpha: 0.8),
                        fontSize: 12,
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

  Widget _buildLoadingState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          AnimatedBuilder(
            animation: _pulseController,
            builder: (context, child) {
              return Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: AppTheme.neonCyan.withValues(alpha: 0.5),
                    width: 2,
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: AppTheme.neonCyan.withValues(alpha: 0.3 * _pulseAnimation.value),
                      blurRadius: 20,
                      spreadRadius: 5,
                    ),
                  ],
                ),
                child: const Icon(
                  Icons.smart_toy,
                  color: AppTheme.neonCyan,
                  size: 36,
                ),
              );
            },
          ),
          const SizedBox(height: 24),
          const Text(
            'Discovering companions...',
            style: TextStyle(
              color: AppTheme.textMuted,
              fontSize: 14,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
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
              child: const Icon(
                Icons.error_outline,
                color: AppTheme.neonRed,
                size: 48,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              _error!,
              style: const TextStyle(color: AppTheme.textSecondary),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            _buildRetryButton(),
          ],
        ),
      ),
    );
  }

  Widget _buildRetryButton() {
    return GestureDetector(
      onTap: _loadBots,
      child: AnimatedBuilder(
        animation: _pulseController,
        builder: (context, child) {
          return Container(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [AppTheme.neonCyan, AppTheme.neonMagenta],
              ),
              borderRadius: BorderRadius.circular(12),
              boxShadow: [
                BoxShadow(
                  color: AppTheme.neonCyan.withValues(alpha: 0.3 * _pulseAnimation.value),
                  blurRadius: 15,
                  spreadRadius: 2,
                ),
              ],
            ),
            child: const Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.refresh, color: Colors.white, size: 18),
                SizedBox(width: 8),
                Text(
                  'Retry',
                  style: TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildBotView(List<BotProfile> bots, String section) {
    if (bots.isEmpty) {
      return _buildEmptyState();
    }

    return RefreshIndicator(
      onRefresh: _loadBots,
      color: AppTheme.neonCyan,
      backgroundColor: AppTheme.cyberDark,
      child: CustomScrollView(
        slivers: [
          // Trending section header (only for Trending tab)
          if (section == 'Trending' && bots.length > 3)
            SliverToBoxAdapter(
              child: _buildTrendingSection(bots.take(3).toList()),
            ),
          // Main grid/list
          _isGridView
              ? _buildGridView(section == 'Trending' && bots.length > 3 ? bots.skip(3).toList() : bots)
              : _buildListView(section == 'Trending' && bots.length > 3 ? bots.skip(3).toList() : bots),
          const SliverPadding(padding: EdgeInsets.only(bottom: 100)),
        ],
      ),
    );
  }

  Widget _buildTrendingSection(List<BotProfile> topBots) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 12),
          child: Row(
            children: [
              AnimatedBuilder(
                animation: _glowController,
                builder: (context, child) {
                  return Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppTheme.neonAmber.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(10),
                      boxShadow: [
                        BoxShadow(
                          color: AppTheme.neonAmber.withValues(alpha: 0.3 * _glowAnimation.value),
                          blurRadius: 10,
                        ),
                      ],
                    ),
                    child: const Icon(
                      Icons.local_fire_department,
                      color: AppTheme.neonAmber,
                      size: 18,
                    ),
                  );
                },
              ),
              const SizedBox(width: 12),
              const Text(
                'Hot Right Now',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.textPrimary,
                ),
              ),
            ],
          ),
        ),
        SizedBox(
          height: 200,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 20),
            itemCount: topBots.length,
            separatorBuilder: (context, index) => const SizedBox(width: 16),
            itemBuilder: (context, index) {
              return _FeaturedBotCard(
                bot: topBots[index],
                rank: index + 1,
                onTap: () => _viewProfile(topBots[index]),
                onChat: () => _startChat(topBots[index]),
                pulseAnimation: _pulseAnimation,
                glowAnimation: _glowAnimation,
              );
            },
          ),
        ),
        const SizedBox(height: 16),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppTheme.neonCyan.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(
                  Icons.grid_view,
                  color: AppTheme.neonCyan,
                  size: 18,
                ),
              ),
              const SizedBox(width: 12),
              const Text(
                'All Companions',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.textPrimary,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
      ],
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: AppTheme.glassBg,
                shape: BoxShape.circle,
                border: Border.all(color: AppTheme.glassBorder),
              ),
              child: Icon(
                _searchController.text.isNotEmpty || _selectedPersonalityFilter != null
                    ? Icons.search_off
                    : Icons.smart_toy_outlined,
                color: AppTheme.textMuted,
                size: 48,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              _searchController.text.isNotEmpty || _selectedPersonalityFilter != null
                  ? 'No companions match your filters'
                  : 'No companions available',
              style: const TextStyle(
                color: AppTheme.textPrimary,
                fontSize: 18,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              _searchController.text.isNotEmpty || _selectedPersonalityFilter != null
                  ? 'Try adjusting your search or filters'
                  : 'Check back later for new companions',
              style: const TextStyle(
                color: AppTheme.textMuted,
                fontSize: 14,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  SliverPadding _buildGridView(List<BotProfile> bots) {
    return SliverPadding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      sliver: SliverGrid(
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 2,
          crossAxisSpacing: 14,
          mainAxisSpacing: 14,
          childAspectRatio: 0.72,
        ),
        delegate: SliverChildBuilderDelegate(
          (context, index) {
            final bot = bots[index];
            return _BotGridCard(
              bot: bot,
              onTap: () => _viewProfile(bot),
              onChat: () => _startChat(bot),
              pulseAnimation: _pulseAnimation,
            );
          },
          childCount: bots.length,
        ),
      ),
    );
  }

  SliverPadding _buildListView(List<BotProfile> bots) {
    return SliverPadding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      sliver: SliverList(
        delegate: SliverChildBuilderDelegate(
          (context, index) {
            final bot = bots[index];
            return Padding(
              padding: const EdgeInsets.only(bottom: 14),
              child: _BotListCard(
                bot: bot,
                onTap: () => _viewProfile(bot),
                onChat: () => _startChat(bot),
                pulseAnimation: _pulseAnimation,
              ),
            );
          },
          childCount: bots.length,
        ),
      ),
    );
  }
}

// Filter chip widget
class _FilterChip extends StatelessWidget {
  final String label;
  final IconData icon;
  final Color color;
  final bool isSelected;
  final VoidCallback onTap;
  final Animation<double> pulseAnimation;

  const _FilterChip({
    required this.label,
    required this.icon,
    required this.color,
    required this.isSelected,
    required this.onTap,
    required this.pulseAnimation,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          gradient: isSelected
              ? LinearGradient(
                  colors: [
                    color.withValues(alpha: 0.3),
                    color.withValues(alpha: 0.15),
                  ],
                )
              : null,
          color: isSelected ? null : AppTheme.glassBg,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isSelected ? color.withValues(alpha: 0.6) : AppTheme.glassBorder,
            width: isSelected ? 1.5 : 1,
          ),
          boxShadow: isSelected
              ? [
                  BoxShadow(
                    color: color.withValues(alpha: 0.2),
                    blurRadius: 10,
                    spreadRadius: 1,
                  ),
                ]
              : null,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 16,
              color: isSelected ? color : AppTheme.textMuted,
            ),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(
                color: isSelected ? color : AppTheme.textSecondary,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                fontSize: 13,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// Featured bot card for trending section
class _FeaturedBotCard extends StatelessWidget {
  final BotProfile bot;
  final int rank;
  final VoidCallback onTap;
  final VoidCallback onChat;
  final Animation<double> pulseAnimation;
  final Animation<double> glowAnimation;

  const _FeaturedBotCard({
    required this.bot,
    required this.rank,
    required this.onTap,
    required this.onChat,
    required this.pulseAnimation,
    required this.glowAnimation,
  });

  @override
  Widget build(BuildContext context) {
    final rankColor = rank == 1 ? AppTheme.neonAmber : (rank == 2 ? AppTheme.textSecondary : AppTheme.neonAmber.withValues(alpha: 0.6));

    return GestureDetector(
      onTap: onTap,
      child: AnimatedBuilder(
        animation: pulseAnimation,
        builder: (context, child) {
          return Container(
            width: 160,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  AppTheme.glassBg,
                  AppTheme.cyberDeeper,
                ],
              ),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                color: rankColor.withValues(alpha: 0.4),
                width: 1.5,
              ),
              boxShadow: [
                BoxShadow(
                  color: rankColor.withValues(alpha: 0.15 * pulseAnimation.value),
                  blurRadius: 15,
                  spreadRadius: 2,
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                // Rank badge
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: rankColor.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: rankColor.withValues(alpha: 0.5)),
                  ),
                  child: Text(
                    '#$rank',
                    style: TextStyle(
                      color: rankColor,
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                // Avatar
                Stack(
                  alignment: Alignment.center,
                  children: [
                    Container(
                      width: 64,
                      height: 64,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: SweepGradient(
                          colors: [
                            AppTheme.neonCyan,
                            AppTheme.neonMagenta,
                            AppTheme.neonCyan,
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
                const SizedBox(height: 12),
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
                // AI Badge
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: AppTheme.neonCyan.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: const Text(
                    'AI',
                    style: TextStyle(
                      color: AppTheme.neonCyan,
                      fontSize: 9,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                const Spacer(),
                // Chat button
                GestureDetector(
                  onTap: onChat,
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: [AppTheme.neonCyan, AppTheme.neonMagenta],
                      ),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.chat_bubble, color: Colors.white, size: 14),
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
          );
        },
      ),
    );
  }
}

// Bot grid card widget
class _BotGridCard extends StatelessWidget {
  final BotProfile bot;
  final VoidCallback onTap;
  final VoidCallback onChat;
  final Animation<double> pulseAnimation;

  const _BotGridCard({
    required this.bot,
    required this.onTap,
    required this.onChat,
    required this.pulseAnimation,
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
            // Avatar with gradient ring
            Stack(
              alignment: Alignment.center,
              children: [
                Container(
                  width: 56,
                  height: 56,
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
                  width: 52,
                  height: 52,
                  decoration: const BoxDecoration(
                    shape: BoxShape.circle,
                    color: AppTheme.cyberBlack,
                  ),
                ),
                AvatarWidget(seed: bot.avatarSeed, size: 46),
                // Mood indicator
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
                    color: AppTheme.neonCyan.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(3),
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
            // Bio
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
            // Interests
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
                      borderRadius: BorderRadius.circular(6),
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
            // Chat button
            GestureDetector(
              onTap: onChat,
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

// Bot list card widget
class _BotListCard extends StatelessWidget {
  final BotProfile bot;
  final VoidCallback onTap;
  final VoidCallback onChat;
  final Animation<double> pulseAnimation;

  const _BotListCard({
    required this.bot,
    required this.onTap,
    required this.onChat,
    required this.pulseAnimation,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppTheme.glassBg,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppTheme.glassBorder),
        ),
        child: Row(
          children: [
            // Avatar
            Stack(
              alignment: Alignment.center,
              children: [
                Container(
                  width: 58,
                  height: 58,
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
                  width: 54,
                  height: 54,
                  decoration: const BoxDecoration(
                    shape: BoxShape.circle,
                    color: AppTheme.cyberBlack,
                  ),
                ),
                AvatarWidget(seed: bot.avatarSeed, size: 48),
              ],
            ),
            const SizedBox(width: 14),
            // Info
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(
                        bot.displayName,
                        style: const TextStyle(
                          color: AppTheme.textPrimary,
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(width: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                        decoration: BoxDecoration(
                          color: AppTheme.neonCyan.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text(
                          'AI',
                          style: TextStyle(
                            color: AppTheme.neonCyan,
                            fontSize: 9,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    bot.bio,
                    style: const TextStyle(
                      color: AppTheme.textMuted,
                      fontSize: 12,
                      height: 1.3,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 8),
                  // Interests
                  Wrap(
                    spacing: 6,
                    runSpacing: 4,
                    children: bot.interests.take(3).map((interest) {
                      return Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            colors: [
                              AppTheme.neonCyan.withValues(alpha: 0.1),
                              AppTheme.neonMagenta.withValues(alpha: 0.1),
                            ],
                          ),
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: AppTheme.neonCyan.withValues(alpha: 0.2)),
                        ),
                        child: Text(
                          interest,
                          style: const TextStyle(
                            color: AppTheme.neonCyan,
                            fontSize: 10,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      );
                    }).toList(),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            // Chat button
            GestureDetector(
              onTap: onChat,
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [AppTheme.neonCyan, AppTheme.neonMagenta],
                  ),
                  borderRadius: BorderRadius.circular(12),
                  boxShadow: [
                    BoxShadow(
                      color: AppTheme.neonCyan.withValues(alpha: 0.3),
                      blurRadius: 8,
                    ),
                  ],
                ),
                child: const Icon(
                  Icons.chat_bubble,
                  color: Colors.white,
                  size: 20,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
