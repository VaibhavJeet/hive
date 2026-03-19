import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:timeago/timeago.dart' as timeago;
import '../providers/app_state.dart';
import '../theme/app_theme.dart';
import '../widgets/design_system.dart';
import '../models/models.dart';
import 'chat_detail_screen.dart';
import 'bot_intelligence_screen.dart';

class DmScreen extends StatefulWidget {
  const DmScreen({super.key});

  @override
  State<DmScreen> createState() => _DmScreenState();
}

class _DmScreenState extends State<DmScreen> {
  List<BotProfile> _allBots = [];
  bool _isLoading = true;
  String _searchQuery = '';
  final TextEditingController _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadBots();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadBots() async {
    final appState = context.read<AppState>();
    final bots = await appState.loadBots();
    setState(() {
      _allBots = bots;
      _isLoading = false;
    });
  }

  List<BotProfile> get _filteredBots {
    if (_searchQuery.isEmpty) return _allBots;
    return _allBots.where((bot) {
      return bot.displayName.toLowerCase().contains(_searchQuery.toLowerCase()) ||
          bot.handle.toLowerCase().contains(_searchQuery.toLowerCase());
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.bg,
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            _buildSearchBar(),
            Expanded(
              child: _isLoading
                  ? const Center(
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation(AppTheme.semanticBlue),
                      ),
                    )
                  : _buildContent(),
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
              Icons.chat_bubble_rounded,
              color: AppTheme.semanticBlue,
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Messages',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textPrimary,
                  ),
                ),
                Text(
                  'Chat with AI companions',
                  style: TextStyle(
                    color: AppTheme.textMuted,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
          Consumer<AppState>(
            builder: (context, appState, _) {
              final totalUnread = appState.conversations.fold<int>(
                0,
                (sum, conv) => sum + conv.unreadCount,
              );
              if (totalUnread == 0) return const SizedBox.shrink();

              return Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: AppTheme.semanticRed,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '$totalUnread new',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildSearchBar() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Container(
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.border, width: 1),
        ),
        child: TextField(
          controller: _searchController,
          style: const TextStyle(color: AppTheme.textPrimary, fontSize: 14),
          decoration: InputDecoration(
            hintText: 'Search companions...',
            hintStyle: const TextStyle(color: AppTheme.textMuted, fontSize: 14),
            prefixIcon: const Icon(
              Icons.search,
              size: 20,
              color: AppTheme.textMuted,
            ),
            suffixIcon: _searchQuery.isNotEmpty
                ? IconButton(
                    icon: const Icon(Icons.clear, size: 18),
                    color: AppTheme.textMuted,
                    onPressed: () {
                      _searchController.clear();
                      setState(() => _searchQuery = '');
                    },
                  )
                : null,
            border: InputBorder.none,
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 16,
              vertical: 12,
            ),
          ),
          onChanged: (value) => setState(() => _searchQuery = value),
        ),
      ),
    );
  }

  Widget _buildContent() {
    return Consumer<AppState>(
      builder: (context, appState, child) {
        return RefreshIndicator(
          onRefresh: _loadBots,
          color: AppTheme.semanticBlue,
          backgroundColor: AppTheme.surface,
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: [
              // Recent conversations
              if (appState.conversations.isNotEmpty) ...[
                SliverToBoxAdapter(
                  child: _buildSectionHeader('Recent', appState.conversations.length),
                ),
                SliverList(
                  delegate: SliverChildBuilderDelegate(
                    (context, index) {
                      final conv = appState.conversations[index];
                      return _ConversationTile(
                        conversation: conv,
                        onTap: () => _openChat(conv.otherUser.id, conv.otherUser.displayName),
                      );
                    },
                    childCount: appState.conversations.length,
                  ),
                ),
              ],

              // All bots
              SliverToBoxAdapter(
                child: _buildSectionHeader('All Companions', _filteredBots.length),
              ),
              SliverPadding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                sliver: SliverGrid(
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 2,
                    childAspectRatio: 0.9,
                    crossAxisSpacing: 12,
                    mainAxisSpacing: 12,
                  ),
                  delegate: SliverChildBuilderDelegate(
                    (context, index) {
                      final bot = _filteredBots[index];
                      return _BotCard(
                        bot: bot,
                        onTap: () => _openChat(bot.id, bot.displayName),
                        onMindTap: () => _openMind(bot),
                      );
                    },
                    childCount: _filteredBots.length,
                  ),
                ),
              ),
              const SliverPadding(padding: EdgeInsets.only(bottom: 120)),
            ],
          ),
        );
      },
    );
  }

  Widget _buildSectionHeader(String title, int count) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
      child: Row(
        children: [
          Container(
            width: 3,
            height: 16,
            decoration: BoxDecoration(
              color: AppTheme.semanticBlue,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 8),
          Text(
            title.toUpperCase(),
            style: const TextStyle(
              fontWeight: FontWeight.w600,
              fontSize: 11,
              color: AppTheme.textDim,
              letterSpacing: 0.5,
            ),
          ),
          const Spacer(),
          Text(
            '$count',
            style: const TextStyle(
              color: AppTheme.textMuted,
              fontSize: 11,
            ),
          ),
        ],
      ),
    );
  }

  void _openChat(String botId, String botName) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => ChatDetailScreen(
          botId: botId,
          botName: botName,
        ),
      ),
    );
  }

  void _openMind(BotProfile bot) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => BotIntelligenceScreen(
          botId: bot.id,
          botName: bot.displayName,
          avatarSeed: bot.avatarSeed,
        ),
      ),
    );
  }
}

class _ConversationTile extends StatelessWidget {
  final Conversation conversation;
  final VoidCallback onTap;

  const _ConversationTile({
    required this.conversation,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: conversation.unreadCount > 0
                ? AppTheme.semanticBlue.withValues(alpha: 0.3)
                : AppTheme.border,
            width: 1,
          ),
        ),
        child: Row(
          children: [
            // Avatar with online indicator
            Stack(
              children: [
                CleanAvatar(
                  seed: conversation.otherUser.avatarSeed,
                  size: 48,
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
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          conversation.otherUser.displayName,
                          style: TextStyle(
                            fontWeight: conversation.unreadCount > 0
                                ? FontWeight.w600
                                : FontWeight.w500,
                            fontSize: 14,
                            color: AppTheme.textPrimary,
                          ),
                        ),
                      ),
                      Text(
                        timeago.format(
                          conversation.lastMessageTime,
                          locale: 'en_short',
                        ),
                        style: TextStyle(
                          color: conversation.unreadCount > 0
                              ? AppTheme.semanticBlue
                              : AppTheme.textMuted,
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          conversation.lastMessage,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            color: conversation.unreadCount > 0
                                ? AppTheme.textSecondary
                                : AppTheme.textMuted,
                            fontSize: 12,
                          ),
                        ),
                      ),
                      if (conversation.unreadCount > 0)
                        Container(
                          margin: const EdgeInsets.only(left: 8),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 2,
                          ),
                          decoration: BoxDecoration(
                            color: AppTheme.semanticBlue,
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text(
                            conversation.unreadCount.toString(),
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 10,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _BotCard extends StatelessWidget {
  final BotProfile bot;
  final VoidCallback onTap;
  final VoidCallback onMindTap;

  const _BotCard({
    required this.bot,
    required this.onTap,
    required this.onMindTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.border, width: 1),
        ),
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CleanAvatar(
              seed: bot.avatarSeed,
              size: 52,
            ),
            const SizedBox(height: 12),
            Text(
              bot.displayName,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontWeight: FontWeight.w600,
                fontSize: 13,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              '@${bot.handle}',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: AppTheme.textMuted,
                fontSize: 11,
              ),
            ),
            const SizedBox(height: 10),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                StatusBadge(
                  text: _getMoodLabel(bot.mood),
                  color: _getMoodColor(bot.mood),
                ),
                const SizedBox(width: 6),
                GestureDetector(
                  onTap: onMindTap,
                  child: Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: AppTheme.semanticBlue.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(
                      Icons.psychology,
                      size: 14,
                      color: AppTheme.semanticBlue,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  String _getMoodLabel(String mood) {
    switch (mood.toLowerCase()) {
      case 'joyful':
        return 'Happy';
      case 'excited':
        return 'Excited';
      case 'content':
        return 'Content';
      case 'neutral':
        return 'Neutral';
      case 'melancholic':
        return 'Thoughtful';
      case 'anxious':
        return 'Anxious';
      case 'tired':
        return 'Tired';
      default:
        return mood;
    }
  }

  Color _getMoodColor(String mood) {
    switch (mood.toLowerCase()) {
      case 'joyful':
      case 'excited':
        return AppTheme.semanticYellow;
      case 'content':
        return AppTheme.semanticGreen;
      case 'neutral':
        return AppTheme.semanticBlue;
      case 'melancholic':
      case 'anxious':
        return const Color(0xFF8B5CF6);
      case 'tired':
        return AppTheme.textMuted;
      default:
        return AppTheme.semanticBlue;
    }
  }
}
