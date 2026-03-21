import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:math';
import '../theme/app_theme.dart';
import '../providers/app_state.dart';
import '../services/api_service.dart';
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
  String? _errorMessage;

  // Profile image
  File? _profileImage;
  String? _existingProfileImageUrl;
  final ImagePicker _imagePicker = ImagePicker();
  final ApiService _apiService = ApiService();

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
    _nameController.removeListener(_onDataChanged);
    _bioController.removeListener(_onDataChanged);
    _nameController.dispose();
    _bioController.dispose();
    super.dispose();
  }

  Future<void> _loadUserData() async {
    final appState = context.read<AppState>();
    final prefs = await SharedPreferences.getInstance();
    final user = appState.currentUser;

    setState(() {
      _nameController.text = user?.displayName ?? 'User';
      _avatarSeed = user?.avatarSeed ?? 'default_seed';
      _bioController.text = user?.bio ?? prefs.getString('user_bio') ?? '';
      _existingProfileImageUrl = user?.profileImageUrl;

      // Load saved interests
      if (user != null && user.interests.isNotEmpty) {
        _selectedInterests.addAll(user.interests);
      } else {
        final savedInterests = prefs.getStringList('user_interests') ?? [];
        _selectedInterests.addAll(savedInterests);
      }
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

  /// Pick image from gallery
  Future<void> _pickImageFromGallery() async {
    try {
      final XFile? pickedFile = await _imagePicker.pickImage(
        source: ImageSource.gallery,
        maxWidth: 512,
        maxHeight: 512,
        imageQuality: 85,
      );

      if (pickedFile != null) {
        setState(() {
          _profileImage = File(pickedFile.path);
          _hasChanges = true;
        });
      }
    } catch (e) {
      _showErrorSnackBar('Failed to pick image: $e');
    }
  }

  /// Take photo with camera
  Future<void> _pickImageFromCamera() async {
    try {
      final XFile? pickedFile = await _imagePicker.pickImage(
        source: ImageSource.camera,
        maxWidth: 512,
        maxHeight: 512,
        imageQuality: 85,
      );

      if (pickedFile != null) {
        setState(() {
          _profileImage = File(pickedFile.path);
          _hasChanges = true;
        });
      }
    } catch (e) {
      _showErrorSnackBar('Failed to capture image: $e');
    }
  }

  /// Remove profile image
  void _removeProfileImage() {
    setState(() {
      _profileImage = null;
      _existingProfileImageUrl = null;
      _hasChanges = true;
    });
  }

  /// Show image source selection dialog
  void _showImageSourceDialog() {
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
                'Profile Photo',
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
                    Icons.photo_library_outlined,
                    color: AppTheme.primaryColor,
                  ),
                ),
                title: const Text(
                  'Choose from Gallery',
                  style: TextStyle(color: AppTheme.textPrimary),
                ),
                onTap: () {
                  Navigator.pop(context);
                  _pickImageFromGallery();
                },
              ),
              ListTile(
                leading: Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: AppTheme.secondaryColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(
                    Icons.camera_alt_outlined,
                    color: AppTheme.secondaryColor,
                  ),
                ),
                title: const Text(
                  'Take Photo',
                  style: TextStyle(color: AppTheme.textPrimary),
                ),
                onTap: () {
                  Navigator.pop(context);
                  _pickImageFromCamera();
                },
              ),
              if (_profileImage != null || _existingProfileImageUrl != null)
                ListTile(
                  leading: Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      color: AppTheme.errorColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(
                      Icons.delete_outline,
                      color: AppTheme.errorColor,
                    ),
                  ),
                  title: const Text(
                    'Remove Photo',
                    style: TextStyle(color: AppTheme.errorColor),
                  ),
                  onTap: () {
                    Navigator.pop(context);
                    _removeProfileImage();
                  },
                ),
              const SizedBox(height: 8),
            ],
          ),
        ),
      ),
    );
  }

  /// Validate the form
  bool _validateForm() {
    final displayName = _nameController.text.trim();

    if (displayName.isEmpty) {
      _showErrorSnackBar('Please enter a display name');
      return false;
    }

    if (displayName.length < 2) {
      _showErrorSnackBar('Display name must be at least 2 characters');
      return false;
    }

    if (displayName.length > 50) {
      _showErrorSnackBar('Display name must be less than 50 characters');
      return false;
    }

    // Check for valid characters
    final validNameRegex = RegExp(r'^[\p{L}\p{N}\s\-_.]+$', unicode: true);
    if (!validNameRegex.hasMatch(displayName)) {
      _showErrorSnackBar('Display name contains invalid characters');
      return false;
    }

    if (_bioController.text.length > 160) {
      _showErrorSnackBar('Bio must be less than 160 characters');
      return false;
    }

    return true;
  }

  Future<void> _saveProfile() async {
    if (!_validateForm()) return;

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final appState = context.read<AppState>();
      final prefs = await SharedPreferences.getInstance();
      final userId = appState.currentUser?.id;

      // Save to SharedPreferences
      await prefs.setString('display_name', _nameController.text.trim());
      await prefs.setString('user_bio', _bioController.text.trim());
      await prefs.setString('avatar_seed', _avatarSeed);
      await prefs.setStringList('user_interests', _selectedInterests.toList());

      // Save to API if user is logged in
      if (userId != null && userId.isNotEmpty) {
        try {
          await _apiService.updateUserProfile(
            userId: userId,
            displayName: _nameController.text.trim(),
            bio: _bioController.text.trim(),
            avatarSeed: _avatarSeed,
            profileImage: _profileImage,
            interests: _selectedInterests.toList(),
          );
        } catch (apiError) {
          // Log API error but don't fail - data is saved locally
          debugPrint('API update failed (saved locally): $apiError');
        }
      }

      if (mounted) {
        _showSuccessSnackBar('Profile saved successfully');
        setState(() => _hasChanges = false);
        Navigator.of(context).pop(true);
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Failed to save profile: $e';
        });
        _showErrorSnackBar('Failed to save profile: $e');
      }
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

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

  /// Build the profile image widget
  Widget _buildProfileImageWidget({required double size}) {
    if (_profileImage != null) {
      return ClipOval(
        child: Image.file(
          _profileImage!,
          width: size,
          height: size,
          fit: BoxFit.cover,
        ),
      );
    } else if (_existingProfileImageUrl != null && _existingProfileImageUrl!.isNotEmpty) {
      return ClipOval(
        child: Image.network(
          _existingProfileImageUrl!,
          width: size,
          height: size,
          fit: BoxFit.cover,
          errorBuilder: (context, error, stackTrace) {
            return AvatarWidget(seed: _avatarSeed, size: size);
          },
        ),
      );
    } else {
      return AvatarWidget(seed: _avatarSeed, size: size);
    }
  }

  @override
  Widget build(BuildContext context) {
    final hasCustomImage = _profileImage != null ||
        (_existingProfileImageUrl != null && _existingProfileImageUrl!.isNotEmpty);

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
            // Error banner
            if (_errorMessage != null)
              Container(
                margin: const EdgeInsets.only(bottom: 16),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTheme.errorColor.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
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
                  ],
                ),
              ),

            // Avatar/Photo Section
            _buildSectionHeader('Profile Photo'),
            const SizedBox(height: 16),
            Center(
              child: Column(
                children: [
                  GestureDetector(
                    onTap: _showImageSourceDialog,
                    child: Stack(
                      children: [
                        Container(
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            border: Border.all(
                              color: AppTheme.primaryColor.withValues(alpha: 0.3),
                              width: 3,
                            ),
                          ),
                          child: _buildProfileImageWidget(size: 100),
                        ),
                        Positioned(
                          right: 0,
                          bottom: 0,
                          child: Container(
                            padding: const EdgeInsets.all(6),
                            decoration: BoxDecoration(
                              gradient: AppTheme.primaryGradient,
                              shape: BoxShape.circle,
                              border: Border.all(
                                color: AppTheme.backgroundColor,
                                width: 2,
                              ),
                            ),
                            child: const Icon(
                              Icons.camera_alt,
                              color: Colors.white,
                              size: 16,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      OutlinedButton.icon(
                        onPressed: _showImageSourceDialog,
                        icon: const Icon(Icons.photo_camera_outlined, size: 18),
                        label: Text(hasCustomImage ? 'Change' : 'Add Photo'),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: AppTheme.primaryColor,
                          side: const BorderSide(color: AppTheme.primaryColor),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                        ),
                      ),
                      if (!hasCustomImage) ...[
                        const SizedBox(width: 8),
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
                          ),
                        ),
                      ],
                    ],
                  ),
                ],
              ),
            ),

            // Preset avatars (only show if no custom image)
            if (!hasCustomImage) ...[
              const SizedBox(height: 16),
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
            ],

            const SizedBox(height: 32),

            // Display Name
            _buildSectionHeader('Display Name'),
            const SizedBox(height: 8),
            TextField(
              controller: _nameController,
              style: const TextStyle(color: AppTheme.textPrimary),
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
                counterStyle: const TextStyle(color: AppTheme.textMuted),
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
                hintStyle: const TextStyle(color: AppTheme.textMuted),
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
              'Select topics that interest you (${_selectedInterests.length} selected)',
              style: const TextStyle(
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
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        if (isSelected) ...[
                          const Icon(
                            Icons.check_circle,
                            color: Colors.white,
                            size: 14,
                          ),
                          const SizedBox(width: 4),
                        ],
                        Text(
                          interest,
                          style: TextStyle(
                            color: isSelected ? Colors.white : AppTheme.textSecondary,
                            fontWeight:
                                isSelected ? FontWeight.w600 : FontWeight.normal,
                            fontSize: 13,
                          ),
                        ),
                      ],
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
                  foregroundColor: Colors.white,
                  disabledForegroundColor: AppTheme.textMuted,
                  elevation: _hasChanges ? 4 : 0,
                  shadowColor: AppTheme.primaryColor.withValues(alpha: 0.4),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
                child: _isLoading
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
