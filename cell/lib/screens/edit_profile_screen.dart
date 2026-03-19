import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:math';
import '../theme/app_theme.dart';
import '../providers/app_state.dart';
import '../widgets/avatar_widget.dart';

/// Profile editing screen with display name, bio, avatar selection, and interest tags
class EditProfileScreen extends StatefulWidget {
  const EditProfileScreen({super.key});

  @override
  State<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends State<EditProfileScreen> {
  // Form key for validation
  final _formKey = GlobalKey<FormState>();

  // Text controllers
  final TextEditingController _displayNameController = TextEditingController();
  final TextEditingController _bioController = TextEditingController();

  // State variables
  String _avatarSeed = '';
  bool _isLoading = false;
  bool _isSaving = false;
  bool _hasChanges = false;
  String? _errorMessage;

  // Selected interests
  final Set<String> _selectedInterests = {};

  // Available interest tags
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
    'Health & Wellness',
    'Education',
    'Politics',
    'Environment',
    'AI & Machine Learning',
    'Startups',
    'Cryptocurrency',
    'Anime & Manga',
  ];

  // Preset avatar seeds for quick selection
  final List<String> _presetAvatars = [
    'avatar_cosmic',
    'avatar_ocean',
    'avatar_sunset',
    'avatar_forest',
    'avatar_neon',
    'avatar_pastel',
    'avatar_midnight',
    'avatar_aurora',
    'avatar_ember',
    'avatar_frost',
    'avatar_bloom',
    'avatar_storm',
  ];

  @override
  void initState() {
    super.initState();
    _loadUserData();
  }

  @override
  void dispose() {
    _displayNameController.dispose();
    _bioController.dispose();
    super.dispose();
  }

  /// Load existing user data from SharedPreferences and AppState
  Future<void> _loadUserData() async {
    setState(() => _isLoading = true);

    try {
      final appState = context.read<AppState>();
      final prefs = await SharedPreferences.getInstance();

      setState(() {
        // Load display name from user or preferences
        _displayNameController.text =
            appState.currentUser?.displayName ??
            prefs.getString('display_name') ??
            'User';

        // Load avatar seed
        _avatarSeed =
            appState.currentUser?.avatarSeed ??
            prefs.getString('avatar_seed') ??
            'default_seed';

        // Load bio
        _bioController.text = prefs.getString('user_bio') ?? '';

        // Load saved interests
        final savedInterests = prefs.getStringList('user_interests') ?? [];
        _selectedInterests.addAll(savedInterests);

        _isLoading = false;
      });

      // Add listeners for change detection after initial load
      _displayNameController.addListener(_onFormChanged);
      _bioController.addListener(_onFormChanged);
    } catch (e) {
      setState(() {
        _isLoading = false;
        _errorMessage = 'Failed to load profile data: $e';
      });
    }
  }

  /// Called when any form field changes
  void _onFormChanged() {
    if (!_hasChanges) {
      setState(() => _hasChanges = true);
    }
  }

  /// Select a preset avatar
  void _selectPresetAvatar(String seed) {
    setState(() {
      _avatarSeed = seed;
      _hasChanges = true;
    });
  }

  /// Generate a random avatar seed
  void _generateRandomAvatar() {
    final random = Random();
    setState(() {
      _avatarSeed = 'random_${DateTime.now().millisecondsSinceEpoch}_${random.nextInt(999999)}';
      _hasChanges = true;
    });
  }

  /// Show avatar picker options bottom sheet
  void _showAvatarPickerOptions() {
    showModalBottomSheet(
      context: context,
      backgroundColor: AppTheme.cardColor,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: AppTheme.textMuted.withValues(alpha: 0.3),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(height: 20),
              const Text(
                'Choose Avatar',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textPrimary,
                ),
              ),
              const SizedBox(height: 20),
              ListTile(
                leading: Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: AppTheme.primaryColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(
                    Icons.shuffle,
                    color: AppTheme.primaryColor,
                  ),
                ),
                title: const Text(
                  'Generate Random',
                  style: TextStyle(color: AppTheme.textPrimary),
                ),
                subtitle: const Text(
                  'Create a unique avatar',
                  style: TextStyle(color: AppTheme.textSecondary, fontSize: 12),
                ),
                onTap: () {
                  Navigator.pop(context);
                  _generateRandomAvatar();
                },
              ),
              const Divider(height: 1, indent: 72),
              const Padding(
                padding: EdgeInsets.fromLTRB(16, 16, 16, 8),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    'Or choose a preset:',
                    style: TextStyle(
                      fontSize: 14,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ),
              ),
              SizedBox(
                height: 80,
                child: ListView.separated(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  scrollDirection: Axis.horizontal,
                  itemCount: _presetAvatars.length,
                  separatorBuilder: (context, index) => const SizedBox(width: 12),
                  itemBuilder: (context, index) {
                    final seed = _presetAvatars[index];
                    final isSelected = seed == _avatarSeed;
                    return GestureDetector(
                      onTap: () {
                        _selectPresetAvatar(seed);
                        Navigator.pop(context);
                      },
                      child: Container(
                        padding: const EdgeInsets.all(3),
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: isSelected
                              ? Border.all(color: AppTheme.primaryColor, width: 3)
                              : null,
                        ),
                        child: AvatarWidget(seed: seed, size: 64),
                      ),
                    );
                  },
                ),
              ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }

  /// Toggle interest tag selection
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

  /// Validate the form
  bool _validateForm() {
    if (_displayNameController.text.trim().isEmpty) {
      _showErrorSnackBar('Please enter a display name');
      return false;
    }

    if (_displayNameController.text.trim().length < 2) {
      _showErrorSnackBar('Display name must be at least 2 characters');
      return false;
    }

    if (_displayNameController.text.trim().length > 50) {
      _showErrorSnackBar('Display name must be less than 50 characters');
      return false;
    }

    if (_bioController.text.length > 500) {
      _showErrorSnackBar('Bio must be less than 500 characters');
      return false;
    }

    return true;
  }

  /// Save profile data
  Future<void> _saveProfile() async {
    if (!_validateForm()) return;

    setState(() {
      _isSaving = true;
      _errorMessage = null;
    });

    try {
      final prefs = await SharedPreferences.getInstance();

      // Save to SharedPreferences
      await prefs.setString('display_name', _displayNameController.text.trim());
      await prefs.setString('user_bio', _bioController.text.trim());
      await prefs.setString('avatar_seed', _avatarSeed);
      await prefs.setStringList('user_interests', _selectedInterests.toList());

      // TODO: Save to API when endpoint is available
      // await ApiService().updateUserProfile(
      //   displayName: _displayNameController.text.trim(),
      //   bio: _bioController.text.trim(),
      //   avatarSeed: _avatarSeed,
      //   interests: _selectedInterests.toList(),
      // );

      if (mounted) {
        _showSuccessSnackBar('Profile saved successfully');
        setState(() {
          _hasChanges = false;
          _isSaving = false;
        });
        Navigator.of(context).pop(true); // Return true to indicate success
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isSaving = false;
          _errorMessage = 'Failed to save profile: $e';
        });
        _showErrorSnackBar('Failed to save profile: $e');
      }
    }
  }

  /// Cancel editing and discard changes
  void _cancelEditing() {
    if (_hasChanges) {
      _showDiscardChangesDialog();
    } else {
      Navigator.of(context).pop(false);
    }
  }

  /// Show dialog to confirm discarding changes
  void _showDiscardChangesDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppTheme.cardColor,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
        title: const Text(
          'Discard Changes?',
          style: TextStyle(color: AppTheme.textPrimary),
        ),
        content: const Text(
          'You have unsaved changes. Are you sure you want to discard them?',
          style: TextStyle(color: AppTheme.textSecondary),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Keep Editing'),
          ),
          TextButton(
            onPressed: () {
              Navigator.of(context).pop();
              Navigator.of(context).pop(false);
            },
            style: TextButton.styleFrom(foregroundColor: AppTheme.errorColor),
            child: const Text('Discard'),
          ),
        ],
      ),
    );
  }

  /// Show error snackbar
  void _showErrorSnackBar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: AppTheme.errorColor,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        margin: const EdgeInsets.all(16),
      ),
    );
  }

  /// Show success snackbar
  void _showSuccessSnackBar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: AppTheme.successColor,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        margin: const EdgeInsets.all(16),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !_hasChanges,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop && _hasChanges) {
          _showDiscardChangesDialog();
        }
      },
      child: Scaffold(
        appBar: _buildAppBar(),
        body: _isLoading ? _buildLoadingState() : _buildForm(),
      ),
    );
  }

  /// Build app bar with save/cancel actions
  PreferredSizeWidget _buildAppBar() {
    return AppBar(
      title: const Text('Edit Profile'),
      leading: IconButton(
        icon: const Icon(Icons.close),
        onPressed: _cancelEditing,
      ),
      actions: [
        if (_hasChanges)
          TextButton(
            onPressed: _isSaving ? null : _saveProfile,
            child: _isSaving
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      valueColor: AlwaysStoppedAnimation(AppTheme.primaryColor),
                    ),
                  )
                : const Text(
                    'Save',
                    style: TextStyle(
                      color: AppTheme.primaryColor,
                      fontWeight: FontWeight.w600,
                      fontSize: 16,
                    ),
                  ),
          ),
      ],
    );
  }

  /// Build loading state
  Widget _buildLoadingState() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          CircularProgressIndicator(
            valueColor: AlwaysStoppedAnimation(AppTheme.primaryColor),
          ),
          SizedBox(height: 16),
          Text(
            'Loading profile...',
            style: TextStyle(color: AppTheme.textSecondary),
          ),
        ],
      ),
    );
  }

  /// Build the main form
  Widget _buildForm() {
    return Form(
      key: _formKey,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Error message banner
            if (_errorMessage != null) _buildErrorBanner(),

            // Avatar Section
            _buildAvatarSection(),
            const SizedBox(height: 32),

            // Display Name Section
            _buildDisplayNameSection(),
            const SizedBox(height: 24),

            // Bio Section
            _buildBioSection(),
            const SizedBox(height: 24),

            // Interests Section
            _buildInterestsSection(),
            const SizedBox(height: 40),

            // Action Buttons
            _buildActionButtons(),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  /// Build error banner
  Widget _buildErrorBanner() {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.errorColor.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.errorColor.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline, color: AppTheme.errorColor, size: 20),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              _errorMessage!,
              style: const TextStyle(color: AppTheme.errorColor, fontSize: 14),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.close, color: AppTheme.errorColor, size: 18),
            onPressed: () => setState(() => _errorMessage = null),
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(),
          ),
        ],
      ),
    );
  }

  /// Build section header
  Widget _buildSectionHeader(String title, {String? subtitle}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: const TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppTheme.textPrimary,
          ),
        ),
        if (subtitle != null) ...[
          const SizedBox(height: 4),
          Text(
            subtitle,
            style: const TextStyle(
              fontSize: 14,
              color: AppTheme.textSecondary,
            ),
          ),
        ],
      ],
    );
  }

  /// Build avatar section
  Widget _buildAvatarSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionHeader('Avatar', subtitle: 'Choose how you appear to others'),
        const SizedBox(height: 16),

        // Current avatar display
        Center(
          child: Stack(
            children: [
              // Avatar
              GestureDetector(
                onTap: _showAvatarPickerOptions,
                child: Container(
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: AppTheme.primaryColor.withValues(alpha: 0.3),
                      width: 3,
                    ),
                  ),
                  child: AvatarWidget(
                    seed: _avatarSeed,
                    size: 120,
                  ),
                ),
              ),

              // Edit button overlay
              Positioned(
                right: 0,
                bottom: 0,
                child: GestureDetector(
                  onTap: _showAvatarPickerOptions,
                  child: Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      gradient: AppTheme.primaryGradient,
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: AppTheme.backgroundColor,
                        width: 3,
                      ),
                    ),
                    child: const Icon(
                      Icons.edit,
                      color: Colors.white,
                      size: 20,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),

        // Quick action buttons
        Center(
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              OutlinedButton.icon(
                onPressed: _showAvatarPickerOptions,
                icon: const Icon(Icons.palette_outlined, size: 18),
                label: const Text('Choose'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppTheme.primaryColor,
                  side: const BorderSide(color: AppTheme.primaryColor),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                ),
              ),
              const SizedBox(width: 12),
              OutlinedButton.icon(
                onPressed: _generateRandomAvatar,
                icon: const Icon(Icons.shuffle, size: 18),
                label: const Text('Random'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppTheme.secondaryColor,
                  side: const BorderSide(color: AppTheme.secondaryColor),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),

        // Preset avatars carousel
        const Text(
          'Quick presets:',
          style: TextStyle(
            fontSize: 14,
            color: AppTheme.textSecondary,
          ),
        ),
        const SizedBox(height: 12),
        SizedBox(
          height: 72,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: _presetAvatars.length,
            separatorBuilder: (context, index) => const SizedBox(width: 12),
            itemBuilder: (context, index) {
              final seed = _presetAvatars[index];
              final isSelected = seed == _avatarSeed;
              return GestureDetector(
                onTap: () => _selectPresetAvatar(seed),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  padding: const EdgeInsets.all(3),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: isSelected
                        ? Border.all(
                            color: AppTheme.primaryColor,
                            width: 3,
                          )
                        : Border.all(
                            color: AppTheme.textMuted.withValues(alpha: 0.2),
                            width: 2,
                          ),
                  ),
                  child: AvatarWidget(
                    seed: seed,
                    size: 58,
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  /// Build display name section
  Widget _buildDisplayNameSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionHeader('Display Name', subtitle: 'This is how others will see you'),
        const SizedBox(height: 12),
        TextFormField(
          controller: _displayNameController,
          style: const TextStyle(color: AppTheme.textPrimary, fontSize: 16),
          maxLength: 50,
          decoration: InputDecoration(
            hintText: 'Enter your display name',
            hintStyle: const TextStyle(color: AppTheme.textMuted),
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
            errorBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(
                color: AppTheme.errorColor,
                width: 2,
              ),
            ),
            counterStyle: const TextStyle(color: AppTheme.textMuted),
          ),
          validator: (value) {
            if (value == null || value.trim().isEmpty) {
              return 'Display name is required';
            }
            if (value.trim().length < 2) {
              return 'Must be at least 2 characters';
            }
            return null;
          },
        ),
      ],
    );
  }

  /// Build bio section
  Widget _buildBioSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionHeader('About Me', subtitle: 'Tell others a bit about yourself'),
        const SizedBox(height: 12),
        TextFormField(
          controller: _bioController,
          style: const TextStyle(color: AppTheme.textPrimary, fontSize: 16),
          maxLines: 4,
          maxLength: 500,
          decoration: InputDecoration(
            hintText: 'Write a short bio...',
            hintStyle: const TextStyle(color: AppTheme.textMuted),
            alignLabelWithHint: true,
            prefixIcon: const Padding(
              padding: EdgeInsets.only(bottom: 72),
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
      ],
    );
  }

  /// Build interests section
  Widget _buildInterestsSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionHeader(
          'Interests',
          subtitle: 'Select topics that interest you (${_selectedInterests.length} selected)',
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 8,
          runSpacing: 10,
          children: _availableInterests.map((interest) {
            final isSelected = _selectedInterests.contains(interest);
            return GestureDetector(
              onTap: () => _toggleInterest(interest),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 10,
                ),
                decoration: BoxDecoration(
                  gradient: isSelected ? AppTheme.primaryGradient : null,
                  color: isSelected ? null : AppTheme.surfaceColor,
                  borderRadius: BorderRadius.circular(20),
                  border: isSelected
                      ? null
                      : Border.all(
                          color: AppTheme.textMuted.withValues(alpha: 0.3),
                        ),
                  boxShadow: isSelected
                      ? [
                          BoxShadow(
                            color: AppTheme.primaryColor.withValues(alpha: 0.3),
                            blurRadius: 8,
                            offset: const Offset(0, 2),
                          ),
                        ]
                      : null,
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (isSelected) ...[
                      const Icon(
                        Icons.check_circle,
                        color: Colors.white,
                        size: 16,
                      ),
                      const SizedBox(width: 6),
                    ],
                    Text(
                      interest,
                      style: TextStyle(
                        color: isSelected ? Colors.white : AppTheme.textSecondary,
                        fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                        fontSize: 14,
                      ),
                    ),
                  ],
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  /// Build action buttons
  Widget _buildActionButtons() {
    return Column(
      children: [
        // Save button
        SizedBox(
          width: double.infinity,
          height: 56,
          child: ElevatedButton(
            onPressed: _hasChanges && !_isSaving ? _saveProfile : null,
            style: ElevatedButton.styleFrom(
              backgroundColor: AppTheme.primaryColor,
              disabledBackgroundColor: AppTheme.surfaceColor,
              foregroundColor: Colors.white,
              disabledForegroundColor: AppTheme.textMuted,
              elevation: _hasChanges ? 4 : 0,
              shadowColor: AppTheme.primaryColor.withValues(alpha: 0.4),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
            ),
            child: _isSaving
                ? const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation(Colors.white),
                        ),
                      ),
                      SizedBox(width: 12),
                      Text(
                        'Saving...',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
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
        const SizedBox(height: 12),

        // Cancel button
        SizedBox(
          width: double.infinity,
          height: 56,
          child: OutlinedButton(
            onPressed: _isSaving ? null : _cancelEditing,
            style: OutlinedButton.styleFrom(
              foregroundColor: AppTheme.textSecondary,
              side: BorderSide(
                color: AppTheme.textMuted.withValues(alpha: 0.3),
              ),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
            ),
            child: const Text(
              'Cancel',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ),
      ],
    );
  }
}
