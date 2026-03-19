import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:math';
import '../theme/app_theme.dart';
import '../providers/app_state.dart';
import '../widgets/avatar_widget.dart';

class ProfileEditScreen extends StatefulWidget {
  const ProfileEditScreen({super.key});

  @override
  State<ProfileEditScreen> createState() => _ProfileEditScreenState();
}

class _ProfileEditScreenState extends State<ProfileEditScreen> {
  final TextEditingController _nameController = TextEditingController();
  final TextEditingController _bioController = TextEditingController();
  String _avatarSeed = '';
  bool _isLoading = false;
  bool _hasChanges = false;

  final Set<String> _selectedInterests = {};

  final List<String> _availableInterests = [
    'Technology',
    'Art & Design',
    'Music',
    'Gaming',
    'Science',
    'Philosophy',
    'Literature',
    'Movies & TV',
    'Sports',
    'Travel',
    'Food & Cooking',
    'Nature',
    'Photography',
    'Fashion',
    'Fitness',
    'Business',
  ];

  // Preset avatar seeds for selection
  final List<String> _presetAvatars = [
    'avatar_cosmic',
    'avatar_ocean',
    'avatar_sunset',
    'avatar_forest',
    'avatar_neon',
    'avatar_pastel',
    'avatar_midnight',
    'avatar_aurora',
  ];

  @override
  void initState() {
    super.initState();
    _loadUserData();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _bioController.dispose();
    super.dispose();
  }

  Future<void> _loadUserData() async {
    final appState = context.read<AppState>();
    final prefs = await SharedPreferences.getInstance();

    setState(() {
      _nameController.text = appState.currentUser?.displayName ?? 'User';
      _avatarSeed = appState.currentUser?.avatarSeed ?? 'default_seed';
      _bioController.text = prefs.getString('user_bio') ?? '';

      // Load saved interests
      final savedInterests = prefs.getStringList('user_interests') ?? [];
      _selectedInterests.addAll(savedInterests);
    });

    _nameController.addListener(_onDataChanged);
    _bioController.addListener(_onDataChanged);
  }

  void _onDataChanged() {
    if (!_hasChanges) {
      setState(() => _hasChanges = true);
    }
  }

  void _selectPresetAvatar(String seed) {
    setState(() {
      _avatarSeed = seed;
      _hasChanges = true;
    });
  }

  void _generateRandomAvatar() {
    final random = Random();
    setState(() {
      _avatarSeed = 'random_${random.nextInt(999999)}';
      _hasChanges = true;
    });
  }

  void _toggleInterest(String interest) {
    setState(() {
      if (_selectedInterests.contains(interest)) {
        _selectedInterests.remove(interest);
      } else {
        _selectedInterests.add(interest);
      }
      _hasChanges = true;
    });
  }

  Future<void> _saveProfile() async {
    if (_nameController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please enter a display name'),
          backgroundColor: AppTheme.errorColor,
        ),
      );
      return;
    }

    setState(() => _isLoading = true);

    try {
      final prefs = await SharedPreferences.getInstance();

      // Save to SharedPreferences
      await prefs.setString('display_name', _nameController.text.trim());
      await prefs.setString('user_bio', _bioController.text.trim());
      await prefs.setString('avatar_seed', _avatarSeed);
      await prefs.setStringList('user_interests', _selectedInterests.toList());

      // TODO: Save to API when endpoint is available
      // await ApiService().updateUserProfile(...)

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Profile saved successfully'),
            backgroundColor: AppTheme.successColor,
          ),
        );
        setState(() => _hasChanges = false);
        Navigator.of(context).pop(true);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to save profile: $e'),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Edit Profile'),
        actions: [
          if (_hasChanges)
            TextButton(
              onPressed: _isLoading ? null : _saveProfile,
              child: _isLoading
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor:
                            AlwaysStoppedAnimation(AppTheme.primaryColor),
                      ),
                    )
                  : const Text(
                      'Save',
                      style: TextStyle(
                        color: AppTheme.primaryColor,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
            ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Avatar Section
            _buildSectionHeader('Avatar'),
            const SizedBox(height: 16),
            Center(
              child: Column(
                children: [
                  AvatarWidget(
                    seed: _avatarSeed,
                    size: 100,
                  ),
                  const SizedBox(height: 16),
                  OutlinedButton.icon(
                    onPressed: _generateRandomAvatar,
                    icon: const Icon(Icons.shuffle),
                    label: const Text('Generate New'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppTheme.primaryColor,
                      side: const BorderSide(color: AppTheme.primaryColor),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Preset avatars
            SizedBox(
              height: 64,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: _presetAvatars.length,
                separatorBuilder: (context, index) => const SizedBox(width: 12),
                itemBuilder: (context, index) {
                  final seed = _presetAvatars[index];
                  final isSelected = seed == _avatarSeed;
                  return GestureDetector(
                    onTap: () => _selectPresetAvatar(seed),
                    child: Container(
                      padding: const EdgeInsets.all(2),
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: isSelected
                            ? Border.all(
                                color: AppTheme.primaryColor,
                                width: 3,
                              )
                            : null,
                      ),
                      child: AvatarWidget(
                        seed: seed,
                        size: 56,
                      ),
                    ),
                  );
                },
              ),
            ),

            const SizedBox(height: 32),

            // Display Name
            _buildSectionHeader('Display Name'),
            const SizedBox(height: 8),
            TextField(
              controller: _nameController,
              style: const TextStyle(color: AppTheme.textPrimary),
              decoration: InputDecoration(
                hintText: 'Enter your display name',
                prefixIcon: const Icon(
                  Icons.person_outline,
                  color: AppTheme.textMuted,
                ),
                filled: true,
                fillColor: AppTheme.surfaceColor,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(
                    color: AppTheme.primaryColor,
                    width: 2,
                  ),
                ),
              ),
            ),

            const SizedBox(height: 24),

            // Bio
            _buildSectionHeader('Bio'),
            const SizedBox(height: 8),
            TextField(
              controller: _bioController,
              style: const TextStyle(color: AppTheme.textPrimary),
              maxLines: 3,
              maxLength: 160,
              decoration: InputDecoration(
                hintText: 'Tell us about yourself...',
                prefixIcon: const Padding(
                  padding: EdgeInsets.only(bottom: 48),
                  child: Icon(
                    Icons.edit_note,
                    color: AppTheme.textMuted,
                  ),
                ),
                filled: true,
                fillColor: AppTheme.surfaceColor,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(
                    color: AppTheme.primaryColor,
                    width: 2,
                  ),
                ),
                counterStyle: const TextStyle(color: AppTheme.textMuted),
              ),
            ),

            const SizedBox(height: 24),

            // Interests
            _buildSectionHeader('Interests'),
            const SizedBox(height: 8),
            Text(
              'Select topics that interest you',
              style: TextStyle(
                color: AppTheme.textSecondary,
                fontSize: 14,
              ),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _availableInterests.map((interest) {
                final isSelected = _selectedInterests.contains(interest);
                return GestureDetector(
                  onTap: () => _toggleInterest(interest),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 8,
                    ),
                    decoration: BoxDecoration(
                      gradient: isSelected ? AppTheme.primaryGradient : null,
                      color: isSelected ? null : AppTheme.surfaceColor,
                      borderRadius: BorderRadius.circular(16),
                      border: isSelected
                          ? null
                          : Border.all(
                              color: AppTheme.textMuted.withValues(alpha: 0.3),
                            ),
                    ),
                    child: Text(
                      interest,
                      style: TextStyle(
                        color: isSelected ? Colors.white : AppTheme.textSecondary,
                        fontWeight:
                            isSelected ? FontWeight.w600 : FontWeight.normal,
                        fontSize: 13,
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),

            const SizedBox(height: 40),

            // Save button (full width)
            SizedBox(
              width: double.infinity,
              height: 56,
              child: ElevatedButton(
                onPressed: _hasChanges && !_isLoading ? _saveProfile : null,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primaryColor,
                  disabledBackgroundColor: AppTheme.surfaceColor,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
                child: _isLoading
                    ? const CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation(Colors.white),
                      )
                    : const Text(
                        'Save Profile',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
              ),
            ),

            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  Widget _buildSectionHeader(String title) {
    return Text(
      title,
      style: const TextStyle(
        fontSize: 18,
        fontWeight: FontWeight.w600,
        color: AppTheme.textPrimary,
      ),
    );
  }
}
