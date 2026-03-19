import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';
import '../providers/settings_provider.dart';
import 'edit_profile_screen.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen>
    with TickerProviderStateMixin {
  late AnimationController _fadeController;
  late Animation<double> _fadeAnimation;
  late AnimationController _glowController;
  late Animation<double> _glowAnimation;

  @override
  void initState() {
    super.initState();
    _fadeController = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    );
    _fadeAnimation = CurvedAnimation(
      parent: _fadeController,
      curve: Curves.easeOut,
    );
    _fadeController.forward();

    _glowController = AnimationController(
      duration: const Duration(milliseconds: 2500),
      vsync: this,
    )..repeat(reverse: true);
    _glowAnimation = Tween<double>(begin: 0.3, end: 1.0).animate(
      CurvedAnimation(parent: _glowController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _fadeController.dispose();
    _glowController.dispose();
    super.dispose();
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
            ...List.generate(4, (index) => _buildFloatingOrb(index)),

            // Main content
            SafeArea(
              child: FadeTransition(
                opacity: _fadeAnimation,
                child: Consumer<SettingsProvider>(
                  builder: (context, settings, child) {
                    return CustomScrollView(
                      slivers: [
                        // App bar
                        SliverAppBar(
                          backgroundColor: Colors.transparent,
                          elevation: 0,
                          pinned: true,
                          expandedHeight: 100,
                          leading: _buildBackButton(),
                          flexibleSpace: FlexibleSpaceBar(
                            title: ShaderMask(
                              shaderCallback: (bounds) =>
                                  AppTheme.primaryGradient.createShader(bounds),
                              child: const Text(
                                'Settings',
                                style: TextStyle(
                                  fontWeight: FontWeight.bold,
                                  color: Colors.white,
                                ),
                              ),
                            ),
                            centerTitle: true,
                          ),
                        ),

                        // Settings content
                        SliverPadding(
                          padding: const EdgeInsets.all(16),
                          sliver: SliverList(
                            delegate: SliverChildListDelegate([
                              // Account Section
                              _buildSectionCard(
                                title: 'Account',
                                icon: Icons.person_outline,
                                children: [
                                  _buildSettingsTile(
                                    icon: Icons.edit_outlined,
                                    title: 'Edit Profile',
                                    subtitle: 'Change your name, avatar, and bio',
                                    onTap: () {
                                      Navigator.of(context).push(
                                        MaterialPageRoute(
                                          builder: (_) =>
                                              const EditProfileScreen(),
                                        ),
                                      );
                                    },
                                  ),
                                  _buildDivider(),
                                  _buildSettingsTile(
                                    icon: Icons.lock_outline,
                                    title: 'Change Password',
                                    subtitle: 'Update your account password',
                                    onTap: () => _showChangePasswordDialog(),
                                  ),
                                  _buildDivider(),
                                  _buildSettingsTile(
                                    icon: Icons.delete_forever,
                                    iconColor: AppTheme.errorColor,
                                    title: 'Delete Account',
                                    subtitle: 'Permanently delete your account',
                                    titleColor: AppTheme.errorColor,
                                    onTap: () => _showDeleteAccountDialog(),
                                    showDanger: true,
                                  ),
                                ],
                              ),

                              const SizedBox(height: 20),

                              // Notifications Section
                              _buildSectionCard(
                                title: 'Notifications',
                                icon: Icons.notifications_outlined,
                                children: [
                                  _buildSwitchTile(
                                    icon: Icons.notifications_active_outlined,
                                    title: 'Push Notifications',
                                    subtitle: 'Receive notifications on your device',
                                    value: settings.pushNotificationsEnabled,
                                    onChanged: (value) =>
                                        settings.setPushNotifications(value),
                                  ),
                                  _buildDivider(),
                                  _buildSwitchTile(
                                    icon: Icons.chat_bubble_outline,
                                    title: 'DM Notifications',
                                    subtitle: 'Get notified about direct messages',
                                    value: settings.dmNotificationsEnabled,
                                    onChanged: (value) =>
                                        settings.setDmNotifications(value),
                                  ),
                                  _buildDivider(),
                                  _buildSwitchTile(
                                    icon: Icons.alternate_email,
                                    title: 'Mentions',
                                    subtitle: 'Get notified when someone mentions you',
                                    value: settings.mentionNotificationsEnabled,
                                    onChanged: (value) =>
                                        settings.setMentionNotifications(value),
                                  ),
                                ],
                              ),

                              const SizedBox(height: 20),

                              // Privacy Section
                              _buildSectionCard(
                                title: 'Privacy',
                                icon: Icons.shield_outlined,
                                children: [
                                  _buildSettingsTile(
                                    icon: Icons.block,
                                    title: 'Blocked Bots',
                                    subtitle: 'Manage your blocked AI companions',
                                    onTap: () => _showBlockedBotsScreen(),
                                  ),
                                  _buildDivider(),
                                  _buildSettingsTile(
                                    icon: Icons.storage_outlined,
                                    title: 'Data Settings',
                                    subtitle: 'Manage your data and privacy',
                                    onTap: () => _showDataSettingsDialog(),
                                  ),
                                ],
                              ),

                              const SizedBox(height: 20),

                              // Appearance Section
                              _buildSectionCard(
                                title: 'Appearance',
                                icon: Icons.palette_outlined,
                                children: [
                                  _buildThemeSelector(settings),
                                  _buildDivider(),
                                  _buildFontSizeSlider(settings),
                                ],
                              ),

                              const SizedBox(height: 20),

                              // About Section
                              _buildSectionCard(
                                title: 'About',
                                icon: Icons.info_outline,
                                children: [
                                  _buildSettingsTile(
                                    icon: Icons.verified_outlined,
                                    title: 'Version',
                                    subtitle: '1.0.0 (Build 1)',
                                    trailing: _buildVersionBadge(),
                                  ),
                                  _buildDivider(),
                                  _buildSettingsTile(
                                    icon: Icons.article_outlined,
                                    title: 'Licenses',
                                    subtitle: 'Open source licenses',
                                    onTap: () => _showLicensesPage(),
                                  ),
                                  _buildDivider(),
                                  _buildSettingsTile(
                                    icon: Icons.feedback_outlined,
                                    title: 'Send Feedback',
                                    subtitle: 'Help us improve the app',
                                    onTap: () => _showFeedbackDialog(),
                                  ),
                                ],
                              ),

                              const SizedBox(height: 32),

                              // Logout button
                              _buildLogoutButton(),

                              const SizedBox(height: 16),

                              // Reset settings
                              _buildResetButton(settings),

                              const SizedBox(height: 40),
                            ]),
                          ),
                        ),
                      ],
                    );
                  },
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFloatingOrb(int index) {
    final random = math.Random(index + 10);
    final size = 120.0 + random.nextDouble() * 180;
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
                      .withValues(alpha: 0.04 * _glowAnimation.value),
                  Colors.transparent,
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildBackButton() {
    return Padding(
      padding: const EdgeInsets.all(8.0),
      child: GestureDetector(
        onTap: () => Navigator.pop(context),
        child: Container(
          decoration: BoxDecoration(
            color: AppTheme.glassBg,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppTheme.glassBorder),
          ),
          child: const Icon(
            Icons.arrow_back,
            color: AppTheme.textSecondary,
          ),
        ),
      ),
    );
  }

  Widget _buildSectionCard({
    required String title,
    required IconData icon,
    required List<Widget> children,
  }) {
    return Container(
      decoration: BoxDecoration(
        gradient: AppTheme.cardGradient,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: AppTheme.neonCyan.withValues(alpha: 0.1),
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.3),
            blurRadius: 20,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Section header
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    gradient: AppTheme.primaryGradient,
                    borderRadius: BorderRadius.circular(10),
                    boxShadow: AppTheme.cyanGlow(intensity: 0.3),
                  ),
                  child: Icon(icon, size: 18, color: Colors.white),
                ),
                const SizedBox(width: 12),
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: AppTheme.textPrimary,
                  ),
                ),
              ],
            ),
          ),
          Container(
            height: 1,
            margin: const EdgeInsets.symmetric(horizontal: 16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  Colors.transparent,
                  AppTheme.neonCyan.withValues(alpha: 0.2),
                  Colors.transparent,
                ],
              ),
            ),
          ),
          // Section content
          Padding(
            padding: const EdgeInsets.all(8),
            child: Column(children: children),
          ),
        ],
      ),
    );
  }

  Widget _buildDivider() {
    return Container(
      height: 1,
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      color: AppTheme.cyberSurface.withValues(alpha: 0.5),
    );
  }

  Widget _buildSettingsTile({
    required IconData icon,
    required String title,
    required String subtitle,
    Color? iconColor,
    Color? titleColor,
    VoidCallback? onTap,
    Widget? trailing,
    bool showDanger = false,
  }) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
          child: Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: (iconColor ?? AppTheme.neonCyan).withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                  border: showDanger
                      ? Border.all(
                          color: AppTheme.errorColor.withValues(alpha: 0.3))
                      : null,
                ),
                child: Icon(
                  icon,
                  color: iconColor ?? AppTheme.neonCyan,
                  size: 22,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: TextStyle(
                        color: titleColor ?? AppTheme.textPrimary,
                        fontWeight: FontWeight.w500,
                        fontSize: 15,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: const TextStyle(
                        color: AppTheme.textMuted,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              trailing ??
                  (onTap != null
                      ? Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: AppTheme.cyberSurface,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Icon(
                            Icons.chevron_right,
                            color: AppTheme.textMuted.withValues(alpha: 0.7),
                            size: 18,
                          ),
                        )
                      : const SizedBox.shrink()),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSwitchTile({
    required IconData icon,
    required String title,
    required String subtitle,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: AppTheme.neonCyan.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(
              icon,
              color: AppTheme.neonCyan,
              size: 22,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: AppTheme.textPrimary,
                    fontWeight: FontWeight.w500,
                    fontSize: 15,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: const TextStyle(
                    color: AppTheme.textMuted,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
          _buildNeonSwitch(value: value, onChanged: onChanged),
        ],
      ),
    );
  }

  Widget _buildNeonSwitch({
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    return AnimatedBuilder(
      animation: _glowAnimation,
      builder: (context, child) {
        return GestureDetector(
          onTap: () => onChanged(!value),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 250),
            width: 56,
            height: 32,
            padding: const EdgeInsets.all(3),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              gradient: value ? AppTheme.primaryGradient : null,
              color: value ? null : AppTheme.cyberMuted,
              boxShadow: value
                  ? [
                      BoxShadow(
                        color: AppTheme.neonCyan
                            .withValues(alpha: 0.4 * _glowAnimation.value),
                        blurRadius: 12,
                        spreadRadius: 0,
                      ),
                    ]
                  : null,
            ),
            child: AnimatedAlign(
              duration: const Duration(milliseconds: 250),
              curve: Curves.easeInOut,
              alignment: value ? Alignment.centerRight : Alignment.centerLeft,
              child: Container(
                width: 26,
                height: 26,
                decoration: BoxDecoration(
                  color: Colors.white,
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.2),
                      blurRadius: 4,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildThemeSelector(SettingsProvider settings) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: AppTheme.neonMagenta.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(
                  Icons.dark_mode,
                  color: AppTheme.neonMagenta,
                  size: 22,
                ),
              ),
              const SizedBox(width: 14),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Theme',
                      style: TextStyle(
                        color: AppTheme.textPrimary,
                        fontWeight: FontWeight.w500,
                        fontSize: 15,
                      ),
                    ),
                    SizedBox(height: 2),
                    Text(
                      'Choose your preferred theme',
                      style: TextStyle(
                        color: AppTheme.textMuted,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(
              color: AppTheme.cyberSurface,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Row(
              children: [
                _buildThemeOption(
                  settings,
                  ThemeMode.light,
                  Icons.light_mode,
                  'Light',
                ),
                _buildThemeOption(
                  settings,
                  ThemeMode.dark,
                  Icons.dark_mode,
                  'Dark',
                ),
                _buildThemeOption(
                  settings,
                  ThemeMode.system,
                  Icons.auto_mode,
                  'Auto',
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildThemeOption(
    SettingsProvider settings,
    ThemeMode mode,
    IconData icon,
    String label,
  ) {
    final isSelected = settings.themeMode == mode;
    return Expanded(
      child: GestureDetector(
        onTap: () => settings.setThemeMode(mode),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 250),
          padding: const EdgeInsets.symmetric(vertical: 12),
          decoration: BoxDecoration(
            gradient: isSelected ? AppTheme.primaryGradient : null,
            borderRadius: BorderRadius.circular(12),
            boxShadow: isSelected
                ? [
                    BoxShadow(
                      color: AppTheme.neonCyan.withValues(alpha: 0.3),
                      blurRadius: 12,
                    ),
                  ]
                : null,
          ),
          child: Column(
            children: [
              Icon(
                icon,
                color: isSelected ? Colors.white : AppTheme.textMuted,
                size: 22,
              ),
              const SizedBox(height: 6),
              Text(
                label,
                style: TextStyle(
                  color: isSelected ? Colors.white : AppTheme.textMuted,
                  fontSize: 12,
                  fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildFontSizeSlider(SettingsProvider settings) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: AppTheme.neonGreen.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(
                  Icons.text_fields,
                  color: AppTheme.neonGreen,
                  size: 22,
                ),
              ),
              const SizedBox(width: 14),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Font Size',
                      style: TextStyle(
                        color: AppTheme.textPrimary,
                        fontWeight: FontWeight.w500,
                        fontSize: 15,
                      ),
                    ),
                    SizedBox(height: 2),
                    Text(
                      'Adjust text size for better readability',
                      style: TextStyle(
                        color: AppTheme.textMuted,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              const Text(
                'A',
                style: TextStyle(
                  color: AppTheme.textMuted,
                  fontSize: 12,
                ),
              ),
              Expanded(
                child: SliderTheme(
                  data: SliderTheme.of(context).copyWith(
                    activeTrackColor: AppTheme.neonGreen,
                    inactiveTrackColor: AppTheme.cyberMuted,
                    thumbColor: Colors.white,
                    overlayColor: AppTheme.neonGreen.withValues(alpha: 0.2),
                    trackHeight: 6,
                    thumbShape: const RoundSliderThumbShape(
                      enabledThumbRadius: 10,
                    ),
                  ),
                  child: Slider(
                    value: settings.fontSizeScale,
                    min: 0.8,
                    max: 1.4,
                    divisions: 6,
                    onChanged: (value) => settings.setFontSizeScale(value),
                  ),
                ),
              ),
              const Text(
                'A',
                style: TextStyle(
                  color: AppTheme.textMuted,
                  fontSize: 22,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildVersionBadge() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        gradient: AppTheme.primaryGradient,
        borderRadius: BorderRadius.circular(12),
      ),
      child: const Text(
        'Latest',
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w600,
          color: Colors.white,
        ),
      ),
    );
  }

  Widget _buildLogoutButton() {
    return AnimatedBuilder(
      animation: _glowAnimation,
      builder: (context, child) {
        return GestureDetector(
          onTap: () => _showLogoutDialog(),
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  AppTheme.neonAmber.withValues(alpha: 0.2),
                  AppTheme.neonAmber.withValues(alpha: 0.1),
                ],
              ),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: AppTheme.neonAmber.withValues(alpha: 0.4),
              ),
            ),
            child: const Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  Icons.logout,
                  color: AppTheme.neonAmber,
                  size: 22,
                ),
                SizedBox(width: 10),
                Text(
                  'Log Out',
                  style: TextStyle(
                    color: AppTheme.neonAmber,
                    fontWeight: FontWeight.w600,
                    fontSize: 16,
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildResetButton(SettingsProvider settings) {
    return GestureDetector(
      onTap: () => _showResetSettingsDialog(settings),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          color: AppTheme.cyberSurface.withValues(alpha: 0.5),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: AppTheme.textMuted.withValues(alpha: 0.2),
          ),
        ),
        child: const Center(
          child: Text(
            'Reset All Settings',
            style: TextStyle(
              color: AppTheme.textMuted,
              fontWeight: FontWeight.w500,
              fontSize: 14,
            ),
          ),
        ),
      ),
    );
  }

  void _showChangePasswordDialog() {
    showDialog(
      context: context,
      builder: (context) => _buildFuturisticDialog(
        icon: Icons.lock_outline,
        iconColor: AppTheme.neonCyan,
        title: 'Change Password',
        content: 'Password change is not available for anonymous users.',
        actions: [
          _buildDialogButton(
            label: 'OK',
            isPrimary: true,
            onTap: () => Navigator.of(context).pop(),
          ),
        ],
      ),
    );
  }

  void _showDeleteAccountDialog() {
    showDialog(
      context: context,
      builder: (context) => _buildFuturisticDialog(
        icon: Icons.warning_amber,
        iconColor: AppTheme.errorColor,
        title: 'Delete Account',
        content:
            'Are you sure you want to delete your account? This action cannot be undone and all your data will be permanently removed.',
        actions: [
          _buildDialogButton(
            label: 'Cancel',
            onTap: () => Navigator.of(context).pop(),
          ),
          _buildDialogButton(
            label: 'Delete',
            isDanger: true,
            onTap: () {
              Navigator.of(context).pop();
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Account deletion is not available yet'),
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  void _showBlockedBotsScreen() {
    showDialog(
      context: context,
      builder: (context) => _buildFuturisticDialog(
        icon: Icons.block,
        iconColor: AppTheme.neonMagenta,
        title: 'Blocked Bots',
        content: 'You have not blocked any AI companions.',
        actions: [
          _buildDialogButton(
            label: 'OK',
            isPrimary: true,
            onTap: () => Navigator.of(context).pop(),
          ),
        ],
      ),
    );
  }

  void _showDataSettingsDialog() {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (context) => Container(
        decoration: BoxDecoration(
          gradient: AppTheme.cardGradient,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          border: Border.all(
            color: AppTheme.neonCyan.withValues(alpha: 0.2),
          ),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 40,
              height: 4,
              margin: const EdgeInsets.symmetric(vertical: 12),
              decoration: BoxDecoration(
                color: AppTheme.textMuted,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const Padding(
              padding: EdgeInsets.all(16),
              child: Text(
                'Data Settings',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.textPrimary,
                ),
              ),
            ),
            _buildBottomSheetTile(
              icon: Icons.download,
              iconColor: AppTheme.neonCyan,
              title: 'Download My Data',
              subtitle: 'Export your data as JSON',
              onTap: () {
                Navigator.of(context).pop();
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Data export coming soon')),
                );
              },
            ),
            _buildBottomSheetTile(
              icon: Icons.delete_sweep,
              iconColor: AppTheme.errorColor,
              title: 'Clear Chat History',
              subtitle: 'Delete all your messages',
              onTap: () {
                Navigator.of(context).pop();
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Chat history cleared')),
                );
              },
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  Widget _buildBottomSheetTile({
    required IconData icon,
    required Color iconColor,
    required String title,
    required String subtitle,
    required VoidCallback onTap,
  }) {
    return ListTile(
      onTap: onTap,
      leading: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: iconColor.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Icon(icon, color: iconColor),
      ),
      title: Text(
        title,
        style: const TextStyle(
          color: AppTheme.textPrimary,
          fontWeight: FontWeight.w500,
        ),
      ),
      subtitle: Text(
        subtitle,
        style: const TextStyle(
          color: AppTheme.textMuted,
          fontSize: 12,
        ),
      ),
      trailing: const Icon(
        Icons.chevron_right,
        color: AppTheme.textMuted,
      ),
    );
  }

  void _showLicensesPage() {
    showLicensePage(
      context: context,
      applicationName: 'AI Social',
      applicationVersion: '1.0.0',
      applicationIcon: Container(
        width: 64,
        height: 64,
        decoration: BoxDecoration(
          gradient: AppTheme.primaryGradient,
          borderRadius: BorderRadius.circular(16),
          boxShadow: AppTheme.cyanGlow(intensity: 0.5),
        ),
        child: const Icon(
          Icons.auto_awesome,
          size: 32,
          color: Colors.white,
        ),
      ),
    );
  }

  void _showFeedbackDialog() {
    final feedbackController = TextEditingController();
    showDialog(
      context: context,
      builder: (context) => Dialog(
        backgroundColor: Colors.transparent,
        child: Container(
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            gradient: AppTheme.cardGradient,
            borderRadius: BorderRadius.circular(24),
            border: Border.all(
              color: AppTheme.neonCyan.withValues(alpha: 0.2),
            ),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 56,
                height: 56,
                decoration: BoxDecoration(
                  gradient: AppTheme.primaryGradient,
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: AppTheme.cyanGlow(intensity: 0.5),
                ),
                child: const Icon(
                  Icons.feedback_outlined,
                  color: Colors.white,
                  size: 28,
                ),
              ),
              const SizedBox(height: 20),
              const Text(
                'Send Feedback',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.textPrimary,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'We would love to hear your thoughts!',
                style: TextStyle(
                  color: AppTheme.textSecondary,
                ),
              ),
              const SizedBox(height: 20),
              TextField(
                controller: feedbackController,
                maxLines: 4,
                style: const TextStyle(color: AppTheme.textPrimary),
                decoration: InputDecoration(
                  hintText: 'Your feedback...',
                  hintStyle: const TextStyle(color: AppTheme.textMuted),
                  filled: true,
                  fillColor: AppTheme.cyberSurface,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                    borderSide: BorderSide.none,
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                    borderSide: const BorderSide(
                      color: AppTheme.neonCyan,
                      width: 2,
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 24),
              Row(
                children: [
                  Expanded(
                    child: _buildDialogButton(
                      label: 'Cancel',
                      onTap: () => Navigator.of(context).pop(),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _buildDialogButton(
                      label: 'Send',
                      isPrimary: true,
                      onTap: () {
                        Navigator.of(context).pop();
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Thank you for your feedback!'),
                            backgroundColor: AppTheme.successColor,
                          ),
                        );
                      },
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

  void _showLogoutDialog() {
    showDialog(
      context: context,
      builder: (context) => _buildFuturisticDialog(
        icon: Icons.logout,
        iconColor: AppTheme.neonAmber,
        title: 'Log Out',
        content: 'Are you sure you want to log out of your account?',
        actions: [
          _buildDialogButton(
            label: 'Cancel',
            onTap: () => Navigator.of(context).pop(),
          ),
          _buildDialogButton(
            label: 'Log Out',
            isPrimary: true,
            onTap: () {
              Navigator.of(context).pop();
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Logged out successfully'),
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  void _showResetSettingsDialog(SettingsProvider settings) {
    showDialog(
      context: context,
      builder: (context) => _buildFuturisticDialog(
        icon: Icons.refresh,
        iconColor: AppTheme.neonMagenta,
        title: 'Reset Settings',
        content:
            'Are you sure you want to reset all settings to their default values?',
        actions: [
          _buildDialogButton(
            label: 'Cancel',
            onTap: () => Navigator.of(context).pop(),
          ),
          _buildDialogButton(
            label: 'Reset',
            isDanger: true,
            onTap: () async {
              await settings.resetSettings();
              if (mounted) {
                Navigator.of(context).pop();
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Settings reset to defaults'),
                    backgroundColor: AppTheme.successColor,
                  ),
                );
              }
            },
          ),
        ],
      ),
    );
  }

  Widget _buildFuturisticDialog({
    required IconData icon,
    required Color iconColor,
    required String title,
    required String content,
    required List<Widget> actions,
  }) {
    return Dialog(
      backgroundColor: Colors.transparent,
      child: Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          gradient: AppTheme.cardGradient,
          borderRadius: BorderRadius.circular(24),
          border: Border.all(
            color: iconColor.withValues(alpha: 0.3),
          ),
          boxShadow: [
            BoxShadow(
              color: iconColor.withValues(alpha: 0.2),
              blurRadius: 30,
              spreadRadius: -5,
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                color: iconColor.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(
                  color: iconColor.withValues(alpha: 0.3),
                ),
              ),
              child: Icon(icon, color: iconColor, size: 28),
            ),
            const SizedBox(height: 20),
            Text(
              title,
              style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              content,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: AppTheme.textSecondary,
                height: 1.5,
              ),
            ),
            const SizedBox(height: 24),
            Row(
              children: actions
                  .map((action) => Expanded(child: action))
                  .toList()
                  .expand((e) => [e, const SizedBox(width: 12)])
                  .toList()
                ..removeLast(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDialogButton({
    required String label,
    required VoidCallback onTap,
    bool isPrimary = false,
    bool isDanger = false,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          gradient: isPrimary
              ? AppTheme.primaryGradient
              : isDanger
                  ? const LinearGradient(
                      colors: [AppTheme.errorColor, AppTheme.neonRed])
                  : null,
          color: isPrimary || isDanger ? null : AppTheme.cyberSurface,
          borderRadius: BorderRadius.circular(12),
          boxShadow: isPrimary
              ? AppTheme.cyanGlow(intensity: 0.3)
              : isDanger
                  ? [
                      BoxShadow(
                        color: AppTheme.errorColor.withValues(alpha: 0.3),
                        blurRadius: 12,
                      ),
                    ]
                  : null,
        ),
        child: Center(
          child: Text(
            label,
            style: TextStyle(
              color: isPrimary || isDanger ? Colors.white : AppTheme.textSecondary,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ),
    );
  }
}
