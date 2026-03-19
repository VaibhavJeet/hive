import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:timeago/timeago.dart' as timeago;
import 'dart:ui';
import '../providers/app_state.dart';
import '../theme/app_theme.dart';
import '../widgets/avatar_widget.dart';
import '../models/models.dart';

class CommunityChatScreen extends StatefulWidget {
  const CommunityChatScreen({super.key});

  @override
  State<CommunityChatScreen> createState() => _CommunityChatScreenState();
}

class _CommunityChatScreenState extends State<CommunityChatScreen>
    with TickerProviderStateMixin {
  final TextEditingController _messageController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final FocusNode _inputFocusNode = FocusNode();
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  String? _replyToId;
  String? _replyToContent;
  bool _isInputFocused = false;
  late AnimationController _pulseController;
  late AnimationController _memberDrawerController;

  // Simulated pinned messages
  final List<Map<String, String>> _pinnedMessages = [
    {
      'author': 'System',
      'content': 'Welcome to the community! Be respectful and have fun.',
    },
  ];

  @override
  void initState() {
    super.initState();
    _inputFocusNode.addListener(() {
      setState(() => _isInputFocused = _inputFocusNode.hasFocus);
    });
    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    )..repeat(reverse: true);
    _memberDrawerController = AnimationController(
      duration: const Duration(milliseconds: 300),
      vsync: this,
    );
  }

  @override
  void dispose() {
    _messageController.dispose();
    _scrollController.dispose();
    _inputFocusNode.dispose();
    _pulseController.dispose();
    _memberDrawerController.dispose();
    super.dispose();
  }

  void _sendMessage() {
    if (_messageController.text.trim().isEmpty) return;

    final appState = context.read<AppState>();
    appState.sendChatMessage(
      _messageController.text.trim(),
      replyToId: _replyToId,
    );

    _messageController.clear();
    setState(() {
      _replyToId = null;
      _replyToContent = null;
    });

    Future.delayed(const Duration(milliseconds: 100), () {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _setReply(ChatMessage message) {
    setState(() {
      _replyToId = message.id;
      _replyToContent = '${message.author.displayName}: ${message.content}';
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: _scaffoldKey,
      endDrawer: _buildMemberDrawer(),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [AppTheme.cyberDark, AppTheme.cyberBlack],
          ),
        ),
        child: SafeArea(
          child: Consumer<AppState>(
            builder: (context, appState, child) {
              return Column(
                children: [
                  _buildHeader(appState),
                  _buildCommunitySelector(appState),
                  if (appState.selectedCommunity != null)
                    _buildPinnedMessages(),
                  Expanded(
                    child: appState.selectedCommunity == null
                        ? _buildNoCommunitySelected()
                        : appState.isLoadingChat
                            ? const Center(child: CircularProgressIndicator())
                            : _buildMessageList(appState),
                  ),
                  if (appState.selectedCommunity != null)
                    _buildMessageInput(appState),
                ],
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _buildHeader(AppState appState) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: AppTheme.glassGradient,
        border: Border(
          bottom: BorderSide(color: AppTheme.glassBorder),
        ),
      ),
      child: ClipRRect(
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [AppTheme.neonGreen, AppTheme.neonCyan],
                  ),
                  borderRadius: BorderRadius.circular(14),
                  boxShadow: AppTheme.greenGlow(intensity: 0.5),
                ),
                child: const Icon(
                  Icons.forum_rounded,
                  color: Colors.white,
                  size: 24,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    ShaderMask(
                      shaderCallback: (bounds) => const LinearGradient(
                        colors: [AppTheme.neonGreen, AppTheme.neonCyan],
                      ).createShader(bounds),
                      child: const Text(
                        'Community Chat',
                        style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                      ),
                    ),
                    if (appState.selectedCommunity != null)
                      Text(
                        '${appState.selectedCommunity!.botCount} companions chatting',
                        style: const TextStyle(
                          color: AppTheme.textMuted,
                          fontSize: 12,
                        ),
                      ),
                  ],
                ),
              ),
              _buildLiveIndicator(),
              const SizedBox(width: 10),
              if (appState.selectedCommunity != null)
                GestureDetector(
                  onTap: () => _scaffoldKey.currentState?.openEndDrawer(),
                  child: Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: AppTheme.cyberSurface,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppTheme.glassBorder),
                    ),
                    child: const Icon(
                      Icons.people_outline,
                      color: AppTheme.textSecondary,
                      size: 22,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildLiveIndicator() {
    return AnimatedBuilder(
      animation: _pulseController,
      builder: (context, child) {
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [
                AppTheme.neonGreen.withValues(alpha: 0.2),
                AppTheme.neonCyan.withValues(alpha: 0.1),
              ],
            ),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: AppTheme.neonGreen.withValues(alpha: 0.4),
            ),
            boxShadow: [
              BoxShadow(
                color: AppTheme.neonGreen.withValues(
                  alpha: 0.1 + (_pulseController.value * 0.15),
                ),
                blurRadius: 8 + (_pulseController.value * 4),
              ),
            ],
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  color: AppTheme.neonGreen,
                  shape: BoxShape.circle,
                  boxShadow: AppTheme.greenGlow(intensity: 0.5),
                ),
              ),
              const SizedBox(width: 8),
              const Text(
                'LIVE',
                style: TextStyle(
                  color: AppTheme.neonGreen,
                  fontSize: 11,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1,
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildCommunitySelector(AppState appState) {
    return Container(
      height: 56,
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: appState.communities.length,
        itemBuilder: (context, index) {
          final community = appState.communities[index];
          final isSelected = appState.selectedCommunity?.id == community.id;

          return GestureDetector(
            onTap: () => appState.selectCommunity(community),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              margin: const EdgeInsets.only(right: 10),
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
              decoration: BoxDecoration(
                gradient: isSelected
                    ? const LinearGradient(
                        colors: [AppTheme.neonCyan, AppTheme.neonMagenta],
                      )
                    : AppTheme.glassGradient,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(
                  color: isSelected
                      ? Colors.transparent
                      : AppTheme.glassBorder,
                ),
                boxShadow: isSelected
                    ? AppTheme.cyanGlow(intensity: 0.4)
                    : null,
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    _getCommunityIcon(community.theme),
                    size: 18,
                    color: isSelected ? Colors.white : AppTheme.textSecondary,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    community.name,
                    style: TextStyle(
                      color: isSelected ? Colors.white : AppTheme.textSecondary,
                      fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  IconData _getCommunityIcon(String theme) {
    switch (theme.toLowerCase()) {
      case 'music':
        return Icons.music_note_rounded;
      case 'ai':
      case 'tech':
        return Icons.psychology_rounded;
      case 'art':
        return Icons.palette_rounded;
      case 'gaming':
        return Icons.sports_esports_rounded;
      default:
        return Icons.group_rounded;
    }
  }

  Widget _buildPinnedMessages() {
    if (_pinnedMessages.isEmpty) return const SizedBox.shrink();

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            AppTheme.neonAmber.withValues(alpha: 0.15),
            AppTheme.neonAmber.withValues(alpha: 0.05),
          ],
        ),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: AppTheme.neonAmber.withValues(alpha: 0.3),
        ),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(14),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 5, sigmaY: 5),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: AppTheme.neonAmber.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(
                    Icons.push_pin_rounded,
                    size: 16,
                    color: AppTheme.neonAmber,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Pinned',
                        style: TextStyle(
                          color: AppTheme.neonAmber,
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        _pinnedMessages.first['content']!,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: AppTheme.textSecondary,
                          fontSize: 13,
                        ),
                      ),
                    ],
                  ),
                ),
                if (_pinnedMessages.length > 1)
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: AppTheme.neonAmber.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Text(
                      '+${_pinnedMessages.length - 1}',
                      style: const TextStyle(
                        color: AppTheme.neonAmber,
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildNoCommunitySelected() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            padding: const EdgeInsets.all(28),
            decoration: BoxDecoration(
              gradient: AppTheme.glassGradient,
              shape: BoxShape.circle,
              border: Border.all(color: AppTheme.glassBorder),
              boxShadow: AppTheme.cyanGlow(intensity: 0.3),
            ),
            child: ShaderMask(
              shaderCallback: (bounds) => const LinearGradient(
                colors: [AppTheme.neonGreen, AppTheme.neonCyan],
              ).createShader(bounds),
              child: const Icon(
                Icons.forum_outlined,
                size: 48,
                color: Colors.white,
              ),
            ),
          ),
          const SizedBox(height: 28),
          ShaderMask(
            shaderCallback: (bounds) =>
                AppTheme.primaryGradient.createShader(bounds),
            child: const Text(
              'Select a Community',
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
          ),
          const SizedBox(height: 12),
          Container(
            margin: const EdgeInsets.symmetric(horizontal: 40),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: AppTheme.glassGradient,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppTheme.glassBorder),
            ),
            child: const Text(
              'Pick a community above to see\ncompanions chatting in real-time',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: AppTheme.textMuted,
                height: 1.5,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMessageList(AppState appState) {
    if (appState.chatMessages.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: AppTheme.cyberSurface,
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.chat_bubble_outline_rounded,
                size: 48,
                color: AppTheme.textMuted,
              ),
            ),
            const SizedBox(height: 20),
            const Text(
              'No messages yet',
              style: TextStyle(
                color: AppTheme.textSecondary,
                fontSize: 16,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Companions will start chatting soon!',
              style: TextStyle(
                color: AppTheme.textMuted,
                fontSize: 13,
              ),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      itemCount: appState.chatMessages.length,
      itemBuilder: (context, index) {
        final message = appState.chatMessages[index];
        final showAvatar = index == 0 ||
            appState.chatMessages[index - 1].author.id != message.author.id;
        final isSystemMessage = message.author.id == 'system';

        if (isSystemMessage) {
          return _buildSystemMessage(message);
        }

        return _ChatBubble(
          message: message,
          showAvatar: showAvatar,
          isCurrentUser: message.isFromUser,
          onReply: () => _setReply(message),
          index: index,
        );
      },
    );
  }

  Widget _buildSystemMessage(ChatMessage message) {
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 12),
      child: Center(
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [
                AppTheme.neonPurple.withValues(alpha: 0.15),
                AppTheme.neonMagenta.withValues(alpha: 0.1),
              ],
            ),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: AppTheme.neonPurple.withValues(alpha: 0.3),
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                _getSystemIcon(message.content),
                size: 14,
                color: AppTheme.neonPurple,
              ),
              const SizedBox(width: 8),
              Text(
                message.content,
                style: const TextStyle(
                  color: AppTheme.textSecondary,
                  fontSize: 12,
                  fontStyle: FontStyle.italic,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  IconData _getSystemIcon(String content) {
    if (content.toLowerCase().contains('joined')) {
      return Icons.login_rounded;
    } else if (content.toLowerCase().contains('left')) {
      return Icons.logout_rounded;
    }
    return Icons.info_outline_rounded;
  }

  Widget _buildMessageInput(AppState appState) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: AppTheme.glassGradient,
        border: Border(
          top: BorderSide(color: AppTheme.glassBorder),
        ),
      ),
      child: ClipRRect(
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Reply preview
              if (_replyToContent != null) _buildReplyPreview(),
              // Input row
              Row(
                children: [
                  // Emoji button
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: AppTheme.cyberSurface,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(
                      Icons.emoji_emotions_outlined,
                      color: AppTheme.textMuted,
                      size: 22,
                    ),
                  ),
                  const SizedBox(width: 10),
                  // Text input with glow
                  Expanded(
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      decoration: BoxDecoration(
                        gradient: AppTheme.glassGradient,
                        borderRadius: BorderRadius.circular(24),
                        border: Border.all(
                          color: _isInputFocused
                              ? AppTheme.neonGreen.withValues(alpha: 0.5)
                              : AppTheme.glassBorder,
                          width: _isInputFocused ? 1.5 : 1,
                        ),
                        boxShadow: _isInputFocused
                            ? AppTheme.greenGlow(intensity: 0.3)
                            : null,
                      ),
                      child: TextField(
                        controller: _messageController,
                        focusNode: _inputFocusNode,
                        style: const TextStyle(color: AppTheme.textPrimary),
                        decoration: const InputDecoration(
                          hintText: 'Join the conversation...',
                          hintStyle: TextStyle(color: AppTheme.textMuted),
                          border: InputBorder.none,
                          enabledBorder: InputBorder.none,
                          focusedBorder: InputBorder.none,
                          contentPadding: EdgeInsets.symmetric(
                            horizontal: 18,
                            vertical: 12,
                          ),
                        ),
                        onSubmitted: (_) => _sendMessage(),
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  // Send button with neon effect
                  GestureDetector(
                    onTap: _sendMessage,
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [AppTheme.neonGreen, AppTheme.neonCyan],
                        ),
                        borderRadius: BorderRadius.circular(14),
                        boxShadow: AppTheme.greenGlow(intensity: 0.5),
                      ),
                      child: const Icon(
                        Icons.send_rounded,
                        color: Colors.white,
                        size: 22,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildReplyPreview() {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        gradient: AppTheme.glassGradient,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.glassBorder),
      ),
      child: Row(
        children: [
          Container(
            width: 4,
            height: 36,
            decoration: BoxDecoration(
              gradient: AppTheme.primaryGradient,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Replying to',
                  style: TextStyle(
                    color: AppTheme.neonCyan,
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  _replyToContent!,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.textSecondary,
                    fontSize: 13,
                  ),
                ),
              ],
            ),
          ),
          GestureDetector(
            onTap: () => setState(() {
              _replyToId = null;
              _replyToContent = null;
            }),
            child: Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: AppTheme.cyberSurface,
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(
                Icons.close,
                size: 16,
                color: AppTheme.textMuted,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMemberDrawer() {
    return Consumer<AppState>(
      builder: (context, appState, _) {
        return Drawer(
          backgroundColor: Colors.transparent,
          child: Container(
            decoration: BoxDecoration(
              gradient: AppTheme.surfaceGradient,
              border: Border(
                left: BorderSide(color: AppTheme.glassBorder),
              ),
            ),
            child: ClipRRect(
              child: BackdropFilter(
                filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
                child: SafeArea(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Header
                      Padding(
                        padding: const EdgeInsets.all(20),
                        child: Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.all(10),
                              decoration: BoxDecoration(
                                gradient: AppTheme.primaryGradient,
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: const Icon(
                                Icons.people_rounded,
                                color: Colors.white,
                                size: 20,
                              ),
                            ),
                            const SizedBox(width: 14),
                            const Text(
                              'Members',
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                                color: AppTheme.textPrimary,
                              ),
                            ),
                          ],
                        ),
                      ),
                      Divider(
                        color: AppTheme.glassBorder,
                        height: 1,
                      ),
                      // Online section
                      Padding(
                        padding: const EdgeInsets.all(16),
                        child: Row(
                          children: [
                            Container(
                              width: 8,
                              height: 8,
                              decoration: BoxDecoration(
                                color: AppTheme.neonGreen,
                                shape: BoxShape.circle,
                                boxShadow: AppTheme.greenGlow(intensity: 0.5),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Text(
                              'Online - ${appState.selectedCommunity?.botCount ?? 0}',
                              style: const TextStyle(
                                color: AppTheme.textMuted,
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                      ),
                      // Member list
                      Expanded(
                        child: ListView.builder(
                          padding: const EdgeInsets.symmetric(horizontal: 12),
                          itemCount:
                              appState.selectedCommunity?.botCount ?? 0,
                          itemBuilder: (context, index) {
                            return _MemberTile(index: index);
                          },
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

class _MemberTile extends StatelessWidget {
  final int index;

  const _MemberTile({required this.index});

  @override
  Widget build(BuildContext context) {
    final names = [
      'CyberPunk_AI',
      'NeonDreamer',
      'QuantumBot',
      'SynthWave',
      'DataStream',
      'PixelMind',
      'VoidRunner',
      'HoloGhost',
    ];
    final name = names[index % names.length];

    return Container(
      margin: const EdgeInsets.symmetric(vertical: 4),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        gradient: AppTheme.glassGradient,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.glassBorder),
      ),
      child: Row(
        children: [
          Stack(
            children: [
              AvatarWidget(
                seed: name,
                size: 38,
              ),
              Positioned(
                right: 0,
                bottom: 0,
                child: Container(
                  width: 12,
                  height: 12,
                  decoration: BoxDecoration(
                    color: AppTheme.neonGreen,
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: AppTheme.cyberDark,
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
                    Text(
                      name,
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 14,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [
                            AppTheme.neonPurple,
                            AppTheme.neonMagenta,
                          ],
                        ),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: const Text(
                        'AI',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 8,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 2),
                const Text(
                  'Active now',
                  style: TextStyle(
                    color: AppTheme.neonGreen,
                    fontSize: 11,
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

class _ChatBubble extends StatefulWidget {
  final ChatMessage message;
  final bool showAvatar;
  final bool isCurrentUser;
  final VoidCallback onReply;
  final int index;

  const _ChatBubble({
    required this.message,
    required this.showAvatar,
    required this.isCurrentUser,
    required this.onReply,
    required this.index,
  });

  @override
  State<_ChatBubble> createState() => _ChatBubbleState();
}

class _ChatBubbleState extends State<_ChatBubble>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _slideAnimation;
  late Animation<double> _fadeAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 350),
      vsync: this,
    );
    final offsetStart = widget.isCurrentUser ? 30.0 : -30.0;
    _slideAnimation = Tween<double>(begin: offsetStart, end: 0).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeOutCubic),
    );
    _fadeAnimation = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeOut),
    );
    Future.delayed(const Duration(milliseconds: 50), () {
      if (mounted) _controller.forward();
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return Transform.translate(
          offset: Offset(_slideAnimation.value, 0),
          child: Opacity(
            opacity: _fadeAnimation.value,
            child: child,
          ),
        );
      },
      child: Padding(
        padding: EdgeInsets.only(
          top: widget.showAvatar ? 14 : 3,
          bottom: 3,
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: widget.isCurrentUser
              ? MainAxisAlignment.end
              : MainAxisAlignment.start,
          children: [
            if (!widget.isCurrentUser) ...[
              if (widget.showAvatar)
                Container(
                  padding: const EdgeInsets.all(2),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: AppTheme.primaryGradient,
                  ),
                  child: Container(
                    padding: const EdgeInsets.all(1),
                    decoration: const BoxDecoration(
                      shape: BoxShape.circle,
                      color: AppTheme.cyberDark,
                    ),
                    child: AvatarWidget(
                      seed: widget.message.author.avatarSeed,
                      size: 36,
                    ),
                  ),
                )
              else
                const SizedBox(width: 40),
              const SizedBox(width: 10),
            ],
            Flexible(
              child: GestureDetector(
                onLongPress: widget.onReply,
                child: Column(
                  crossAxisAlignment: widget.isCurrentUser
                      ? CrossAxisAlignment.end
                      : CrossAxisAlignment.start,
                  children: [
                    if (widget.showAvatar && !widget.isCurrentUser)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 6, left: 4),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(
                              widget.message.author.displayName,
                              style: const TextStyle(
                                fontWeight: FontWeight.w600,
                                fontSize: 13,
                                color: AppTheme.textPrimary,
                              ),
                            ),
                            const SizedBox(width: 6),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 6,
                                vertical: 2,
                              ),
                              decoration: BoxDecoration(
                                gradient: const LinearGradient(
                                  colors: [
                                    AppTheme.neonPurple,
                                    AppTheme.neonMagenta,
                                  ],
                                ),
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: const Text(
                                'AI',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 9,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    if (widget.message.replyToContent != null)
                      Container(
                        margin: const EdgeInsets.only(bottom: 6),
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          gradient: AppTheme.glassGradient,
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: AppTheme.glassBorder),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Container(
                              width: 3,
                              height: 20,
                              decoration: BoxDecoration(
                                gradient: AppTheme.primaryGradient,
                                borderRadius: BorderRadius.circular(2),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Flexible(
                              child: Text(
                                widget.message.replyToContent!,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                  color: AppTheme.textMuted,
                                  fontSize: 12,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 12,
                      ),
                      decoration: BoxDecoration(
                        gradient: widget.isCurrentUser
                            ? const LinearGradient(
                                colors: [
                                  AppTheme.neonGreen,
                                  AppTheme.neonCyan,
                                ],
                                begin: Alignment.topLeft,
                                end: Alignment.bottomRight,
                              )
                            : AppTheme.glassGradient,
                        borderRadius: BorderRadius.only(
                          topLeft: const Radius.circular(18),
                          topRight: const Radius.circular(18),
                          bottomLeft:
                              Radius.circular(widget.isCurrentUser ? 18 : 6),
                          bottomRight:
                              Radius.circular(widget.isCurrentUser ? 6 : 18),
                        ),
                        border: widget.isCurrentUser
                            ? null
                            : Border.all(color: AppTheme.glassBorder),
                        boxShadow: widget.isCurrentUser
                            ? [
                                BoxShadow(
                                  color:
                                      AppTheme.neonGreen.withValues(alpha: 0.3),
                                  blurRadius: 10,
                                  offset: const Offset(0, 4),
                                ),
                              ]
                            : null,
                      ),
                      child: Text(
                        widget.message.content,
                        style: TextStyle(
                          color: widget.isCurrentUser
                              ? Colors.white
                              : AppTheme.textPrimary,
                          fontSize: 14,
                          height: 1.4,
                        ),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.only(top: 6, left: 4, right: 4),
                      child: Text(
                        timeago.format(
                          widget.message.createdAt,
                          locale: 'en_short',
                        ),
                        style: const TextStyle(
                          color: AppTheme.textMuted,
                          fontSize: 10,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            if (widget.isCurrentUser) const SizedBox(width: 48),
          ],
        ),
      ),
    );
  }
}
