import 'dart:io';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import '../models/models.dart';
import '../providers/app_state.dart';
import '../theme/app_theme.dart';
import '../widgets/avatar_widget.dart';

class CreatePostScreen extends StatefulWidget {
  const CreatePostScreen({super.key});

  @override
  State<CreatePostScreen> createState() => _CreatePostScreenState();
}

class _CreatePostScreenState extends State<CreatePostScreen>
    with TickerProviderStateMixin {
  final TextEditingController _contentController = TextEditingController();
  final FocusNode _contentFocusNode = FocusNode();
  final int _maxCharacters = 2000;

  Community? _selectedCommunity;
  final List<String> _hashtags = [];
  bool _isPosting = false;
  bool _showSuccess = false;
  bool _isPreviewMode = false;
  File? _selectedImage;
  final ImagePicker _imagePicker = ImagePicker();

  late AnimationController _successController;
  late Animation<double> _successAnimation;
  late AnimationController _glowController;
  late Animation<double> _glowAnimation;
  late AnimationController _fadeController;
  late Animation<double> _fadeAnimation;

  @override
  void initState() {
    super.initState();
    _successController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );
    _successAnimation = CurvedAnimation(
      parent: _successController,
      curve: Curves.elasticOut,
    );

    _glowController = AnimationController(
      duration: const Duration(milliseconds: 2000),
      vsync: this,
    )..repeat(reverse: true);
    _glowAnimation = Tween<double>(begin: 0.3, end: 1.0).animate(
      CurvedAnimation(parent: _glowController, curve: Curves.easeInOut),
    );

    _fadeController = AnimationController(
      duration: const Duration(milliseconds: 400),
      vsync: this,
    );
    _fadeAnimation = CurvedAnimation(
      parent: _fadeController,
      curve: Curves.easeOut,
    );
    _fadeController.forward();

    WidgetsBinding.instance.addPostFrameCallback((_) {
      _contentFocusNode.requestFocus();
      final appState = context.read<AppState>();
      if (appState.communities.isNotEmpty && _selectedCommunity == null) {
        setState(() {
          _selectedCommunity =
              appState.selectedCommunity ?? appState.communities.first;
        });
      }
    });
  }

  @override
  void dispose() {
    _contentController.dispose();
    _contentFocusNode.dispose();
    _successController.dispose();
    _glowController.dispose();
    _fadeController.dispose();
    super.dispose();
  }

  int get _characterCount => _contentController.text.length;
  bool get _canPost =>
      _contentController.text.trim().isNotEmpty && _selectedCommunity != null;

  void _addHashtag(String tag) {
    if (!_hashtags.contains(tag)) {
      setState(() {
        _hashtags.add(tag);
      });
      final currentText = _contentController.text;
      final hashtagText = ' #$tag';
      if (!currentText.contains('#$tag')) {
        _contentController.text = currentText + hashtagText;
        _contentController.selection = TextSelection.fromPosition(
          TextPosition(offset: _contentController.text.length),
        );
      }
    }
  }

  void _removeHashtag(String tag) {
    setState(() {
      _hashtags.remove(tag);
    });
    final currentText = _contentController.text;
    _contentController.text =
        currentText.replaceAll(' #$tag', '').replaceAll('#$tag', '');
  }

  Future<void> _pickImage(ImageSource source) async {
    try {
      final XFile? pickedFile = await _imagePicker.pickImage(
        source: source,
        maxWidth: 1920,
        maxHeight: 1080,
        imageQuality: 85,
      );
      if (pickedFile != null) {
        setState(() {
          _selectedImage = File(pickedFile.path);
        });
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to pick image: $e'),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    }
  }

  void _removeImage() {
    setState(() {
      _selectedImage = null;
    });
  }

  void _showImageSourcePicker() {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (context) {
        return Container(
          decoration: BoxDecoration(
            color: AppTheme.cyberDark,
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
                  'Select Image Source',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: AppTheme.textPrimary,
                  ),
                ),
              ),
              ListTile(
                onTap: () {
                  Navigator.pop(context);
                  _pickImage(ImageSource.camera);
                },
                leading: Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    gradient: AppTheme.primaryGradient,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(
                    Icons.camera_alt,
                    color: Colors.white,
                  ),
                ),
                title: const Text(
                  'Camera',
                  style: TextStyle(color: AppTheme.textPrimary),
                ),
                subtitle: const Text(
                  'Take a new photo',
                  style: TextStyle(color: AppTheme.textMuted),
                ),
              ),
              ListTile(
                onTap: () {
                  Navigator.pop(context);
                  _pickImage(ImageSource.gallery);
                },
                leading: Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: AppTheme.cyberSurface,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(
                    Icons.photo_library,
                    color: AppTheme.neonMagenta,
                  ),
                ),
                title: const Text(
                  'Gallery',
                  style: TextStyle(color: AppTheme.textPrimary),
                ),
                subtitle: const Text(
                  'Choose from your photos',
                  style: TextStyle(color: AppTheme.textMuted),
                ),
              ),
              const SizedBox(height: 24),
            ],
          ),
        );
      },
    );
  }

  Future<void> _handlePost() async {
    if (!_canPost || _isPosting) return;

    setState(() => _isPosting = true);

    try {
      final appState = context.read<AppState>();
      await appState.createPost(
        content: _contentController.text.trim(),
        communityId: _selectedCommunity!.id,
        image: _selectedImage,
      );

      setState(() => _showSuccess = true);
      _successController.forward();

      await Future.delayed(const Duration(milliseconds: 1500));

      if (mounted) {
        Navigator.pop(context, true);
      }
    } catch (e) {
      setState(() => _isPosting = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to create post: $e'),
            backgroundColor: AppTheme.errorColor,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              AppTheme.cyberBlack,
              AppTheme.cyberDark,
              AppTheme.cyberDeeper,
            ],
          ),
        ),
        child: Stack(
          children: [
            // Animated background particles
            ...List.generate(6, (index) => _buildFloatingOrb(index)),

            // Main content
            SafeArea(
              child: FadeTransition(
                opacity: _fadeAnimation,
                child: Column(
                  children: [
                    _buildHeader(),
                    Expanded(
                      child: _isPreviewMode
                          ? _buildPreviewContent()
                          : _buildEditorContent(),
                    ),
                    _buildBottomBar(),
                  ],
                ),
              ),
            ),

            // Success overlay
            if (_showSuccess) _buildSuccessOverlay(),
          ],
        ),
      ),
    );
  }

  Widget _buildFloatingOrb(int index) {
    final random = math.Random(index);
    final size = 100.0 + random.nextDouble() * 200;
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
                      .withValues(alpha: 0.05 * _glowAnimation.value),
                  Colors.transparent,
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: AppTheme.glassBg,
        border: Border(
          bottom: BorderSide(
            color: AppTheme.neonCyan.withValues(alpha: 0.1),
          ),
        ),
      ),
      child: Row(
        children: [
          // Close button
          _buildGlassIconButton(
            icon: Icons.close,
            onTap: () => Navigator.pop(context),
          ),
          const SizedBox(width: 16),

          // Title with avatar
          Consumer<AppState>(
            builder: (context, appState, child) {
              return Row(
                children: [
                  AvatarWidget(
                    seed: appState.currentUser?.avatarSeed ?? 'user',
                    size: 36,
                  ),
                  const SizedBox(width: 12),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        appState.currentUser?.displayName ?? 'User',
                        style: const TextStyle(
                          fontWeight: FontWeight.w600,
                          fontSize: 14,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      const Text(
                        "What's on your mind?",
                        style: TextStyle(
                          fontSize: 11,
                          color: AppTheme.textMuted,
                        ),
                      ),
                    ],
                  ),
                ],
              );
            },
          ),

          const Spacer(),

          // Preview toggle
          _buildPreviewToggle(),

          const SizedBox(width: 12),

          // Post button
          _buildPostButton(),
        ],
      ),
    );
  }

  Widget _buildGlassIconButton({
    required IconData icon,
    required VoidCallback onTap,
    Color? iconColor,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 40,
        height: 40,
        decoration: BoxDecoration(
          color: AppTheme.cyberSurface.withValues(alpha: 0.5),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: AppTheme.glassBorder,
          ),
        ),
        child: Icon(
          icon,
          size: 20,
          color: iconColor ?? AppTheme.textSecondary,
        ),
      ),
    );
  }

  Widget _buildPreviewToggle() {
    return GestureDetector(
      onTap: () => setState(() => _isPreviewMode = !_isPreviewMode),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          gradient: _isPreviewMode ? AppTheme.primaryGradient : null,
          color: _isPreviewMode ? null : AppTheme.cyberSurface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: _isPreviewMode
                ? Colors.transparent
                : AppTheme.neonCyan.withValues(alpha: 0.3),
          ),
          boxShadow: _isPreviewMode
              ? [
                  BoxShadow(
                    color: AppTheme.neonCyan.withValues(alpha: 0.3),
                    blurRadius: 12,
                  ),
                ]
              : null,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              _isPreviewMode ? Icons.edit : Icons.visibility,
              size: 14,
              color: _isPreviewMode ? Colors.white : AppTheme.neonCyan,
            ),
            const SizedBox(width: 4),
            Text(
              _isPreviewMode ? 'Edit' : 'Preview',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: _isPreviewMode ? Colors.white : AppTheme.neonCyan,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPostButton() {
    return AnimatedBuilder(
      animation: _glowAnimation,
      builder: (context, child) {
        return GestureDetector(
          onTap: _canPost && !_isPosting ? _handlePost : null,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
            decoration: BoxDecoration(
              gradient: _canPost ? AppTheme.primaryGradient : null,
              color: _canPost ? null : AppTheme.cyberMuted,
              borderRadius: BorderRadius.circular(20),
              boxShadow: _canPost
                  ? [
                      BoxShadow(
                        color: AppTheme.neonCyan
                            .withValues(alpha: 0.4 * _glowAnimation.value),
                        blurRadius: 16,
                        spreadRadius: 0,
                      ),
                    ]
                  : null,
            ),
            child: _isPosting
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      valueColor: AlwaysStoppedAnimation(Colors.white),
                    ),
                  )
                : Text(
                    'Post',
                    style: TextStyle(
                      fontWeight: FontWeight.w600,
                      fontSize: 14,
                      color: _canPost ? Colors.white : AppTheme.textMuted,
                    ),
                  ),
          ),
        );
      },
    );
  }

  Widget _buildEditorContent() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Community selector
          _buildCommunitySelector(),

          const SizedBox(height: 24),

          // Content input with glass border
          _buildContentInput(),

          const SizedBox(height: 16),

          // Character counter
          _buildCharacterCounter(),

          const SizedBox(height: 24),

          // Media attachment buttons
          _buildMediaAttachments(),

          const SizedBox(height: 24),

          // Hashtag section
          _buildHashtagSection(),
        ],
      ),
    );
  }

  Widget _buildCommunitySelector() {
    return Consumer<AppState>(
      builder: (context, appState, child) {
        return GestureDetector(
          onTap: () => _showCommunityPicker(appState),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: AppTheme.glassBg,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: AppTheme.neonCyan.withValues(alpha: 0.2),
              ),
            ),
            child: Row(
              children: [
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    gradient: AppTheme.primaryGradient,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(
                    Icons.group,
                    size: 18,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Posting to',
                        style: TextStyle(
                          fontSize: 10,
                          color: AppTheme.textMuted,
                          letterSpacing: 1,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        _selectedCommunity?.name ?? 'Select community',
                        style: const TextStyle(
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: AppTheme.cyberSurface,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(
                    Icons.keyboard_arrow_down,
                    size: 20,
                    color: AppTheme.neonCyan,
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  void _showCommunityPicker(AppState appState) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (context) {
        return Container(
          decoration: BoxDecoration(
            color: AppTheme.cyberDark,
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
                  'Select Community',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: AppTheme.textPrimary,
                  ),
                ),
              ),
              ...appState.communities.map((community) {
                final isSelected = _selectedCommunity?.id == community.id;
                return ListTile(
                  onTap: () {
                    setState(() => _selectedCommunity = community);
                    Navigator.pop(context);
                  },
                  leading: Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      gradient:
                          isSelected ? AppTheme.primaryGradient : null,
                      color: isSelected ? null : AppTheme.cyberSurface,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(
                      Icons.group,
                      color: isSelected ? Colors.white : AppTheme.textSecondary,
                    ),
                  ),
                  title: Text(
                    community.name,
                    style: TextStyle(
                      color: isSelected
                          ? AppTheme.neonCyan
                          : AppTheme.textPrimary,
                      fontWeight:
                          isSelected ? FontWeight.w600 : FontWeight.normal,
                    ),
                  ),
                  trailing: isSelected
                      ? const Icon(Icons.check_circle, color: AppTheme.neonCyan)
                      : null,
                );
              }),
              const SizedBox(height: 24),
            ],
          ),
        );
      },
    );
  }

  Widget _buildContentInput() {
    return AnimatedBuilder(
      animation: _glowAnimation,
      builder: (context, child) {
        return Container(
          decoration: BoxDecoration(
            color: AppTheme.glassBg,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: _contentFocusNode.hasFocus
                  ? AppTheme.neonCyan.withValues(alpha: 0.5)
                  : AppTheme.glassBorder,
              width: _contentFocusNode.hasFocus ? 2 : 1,
            ),
            boxShadow: _contentFocusNode.hasFocus
                ? [
                    BoxShadow(
                      color: AppTheme.neonCyan
                          .withValues(alpha: 0.15 * _glowAnimation.value),
                      blurRadius: 20,
                      spreadRadius: -5,
                    ),
                  ]
                : null,
          ),
          child: TextField(
            controller: _contentController,
            focusNode: _contentFocusNode,
            maxLength: _maxCharacters,
            maxLines: null,
            minLines: 8,
            style: const TextStyle(
              fontSize: 16,
              height: 1.6,
              color: AppTheme.textPrimary,
            ),
            decoration: const InputDecoration(
              hintText: 'Share your thoughts with the community...',
              hintStyle: TextStyle(
                color: AppTheme.textMuted,
                fontSize: 16,
              ),
              border: InputBorder.none,
              counterText: '',
              contentPadding: EdgeInsets.all(20),
            ),
            inputFormatters: [
              LengthLimitingTextInputFormatter(_maxCharacters),
            ],
            onChanged: (_) => setState(() {}),
          ),
        );
      },
    );
  }

  Widget _buildCharacterCounter() {
    final remaining = _maxCharacters - _characterCount;
    final isNearLimit = remaining <= 200;
    final isWarning = remaining <= 100;
    final isAtLimit = remaining <= 0;

    final progress = _characterCount / _maxCharacters;

    return Row(
      children: [
        // Progress bar
        Expanded(
          child: Container(
            height: 4,
            decoration: BoxDecoration(
              color: AppTheme.cyberSurface,
              borderRadius: BorderRadius.circular(2),
            ),
            child: FractionallySizedBox(
              alignment: Alignment.centerLeft,
              widthFactor: progress.clamp(0.0, 1.0),
              child: Container(
                decoration: BoxDecoration(
                  gradient: isAtLimit
                      ? const LinearGradient(colors: [AppTheme.errorColor, AppTheme.neonRed])
                      : isWarning
                          ? const LinearGradient(colors: [AppTheme.warningColor, AppTheme.neonAmber])
                          : AppTheme.primaryGradient,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
          ),
        ),
        const SizedBox(width: 16),

        // Counter text
        AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: isAtLimit
                ? AppTheme.errorColor.withValues(alpha: 0.2)
                : isWarning
                    ? AppTheme.warningColor.withValues(alpha: 0.2)
                    : AppTheme.cyberSurface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: isAtLimit
                  ? AppTheme.errorColor.withValues(alpha: 0.5)
                  : isWarning
                      ? AppTheme.warningColor.withValues(alpha: 0.5)
                      : Colors.transparent,
            ),
          ),
          child: Text(
            isNearLimit ? '$remaining' : '$_characterCount / $_maxCharacters',
            style: TextStyle(
              fontSize: 12,
              fontWeight: isNearLimit ? FontWeight.w600 : FontWeight.normal,
              color: isAtLimit
                  ? AppTheme.errorColor
                  : isWarning
                      ? AppTheme.warningColor
                      : AppTheme.textMuted,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildMediaAttachments() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'ADD MEDIA',
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: AppTheme.textMuted,
            letterSpacing: 1.5,
          ),
        ),
        const SizedBox(height: 12),

        // Selected image preview
        if (_selectedImage != null) _buildImagePreview(),

        if (_selectedImage != null) const SizedBox(height: 16),

        Row(
          children: [
            _buildMediaButton(
              icon: Icons.image_outlined,
              label: 'Photo',
              color: AppTheme.neonCyan,
              onTap: _showImageSourcePicker,
              isActive: _selectedImage != null,
            ),
            const SizedBox(width: 12),
            _buildMediaButton(
              icon: Icons.gif_box_outlined,
              label: 'GIF',
              color: AppTheme.neonMagenta,
            ),
            const SizedBox(width: 12),
            _buildMediaButton(
              icon: Icons.poll_outlined,
              label: 'Poll',
              color: AppTheme.neonGreen,
            ),
            const SizedBox(width: 12),
            _buildMediaButton(
              icon: Icons.link_outlined,
              label: 'Link',
              color: AppTheme.neonAmber,
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildImagePreview() {
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: AppTheme.neonCyan.withValues(alpha: 0.3),
        ),
      ),
      child: Stack(
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(15),
            child: Image.file(
              _selectedImage!,
              width: double.infinity,
              height: 200,
              fit: BoxFit.cover,
            ),
          ),
          // Remove button
          Positioned(
            top: 8,
            right: 8,
            child: GestureDetector(
              onTap: _removeImage,
              child: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppTheme.cyberBlack.withValues(alpha: 0.8),
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: AppTheme.neonCyan.withValues(alpha: 0.5),
                  ),
                ),
                child: const Icon(
                  Icons.close,
                  size: 18,
                  color: AppTheme.textPrimary,
                ),
              ),
            ),
          ),
          // Image indicator
          Positioned(
            bottom: 8,
            left: 8,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: AppTheme.cyberBlack.withValues(alpha: 0.8),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: AppTheme.neonCyan.withValues(alpha: 0.3),
                ),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(
                    Icons.image,
                    size: 14,
                    color: AppTheme.neonCyan,
                  ),
                  const SizedBox(width: 4),
                  const Text(
                    'Image attached',
                    style: TextStyle(
                      fontSize: 11,
                      color: AppTheme.neonCyan,
                      fontWeight: FontWeight.w500,
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

  Widget _buildMediaButton({
    required IconData icon,
    required String label,
    required Color color,
    VoidCallback? onTap,
    bool isActive = false,
  }) {
    return Expanded(
      child: GestureDetector(
        onTap: onTap ?? () {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('$label attachment coming soon'),
              backgroundColor: AppTheme.cyberSurface,
            ),
          );
        },
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 16),
          decoration: BoxDecoration(
            color: isActive ? color.withValues(alpha: 0.25) : color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: isActive ? color : color.withValues(alpha: 0.3),
              width: isActive ? 2 : 1,
            ),
            boxShadow: isActive
                ? [
                    BoxShadow(
                      color: color.withValues(alpha: 0.3),
                      blurRadius: 12,
                    ),
                  ]
                : null,
          ),
          child: Column(
            children: [
              Icon(icon, color: color, size: 24),
              const SizedBox(height: 6),
              Text(
                label,
                style: TextStyle(
                  fontSize: 11,
                  color: color,
                  fontWeight: isActive ? FontWeight.w600 : FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHashtagSection() {
    final suggestedTags = [
      'AICompanions',
      'TechTalk',
      'Creative',
      'Discussion',
      'Ideas',
      'Future'
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'HASHTAGS',
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: AppTheme.textMuted,
            letterSpacing: 1.5,
          ),
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: suggestedTags.map((tag) {
            final isSelected = _hashtags.contains(tag);
            return GestureDetector(
              onTap: () {
                if (isSelected) {
                  _removeHashtag(tag);
                } else {
                  _addHashtag(tag);
                }
              },
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                padding:
                    const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                decoration: BoxDecoration(
                  gradient: isSelected ? AppTheme.primaryGradient : null,
                  color: isSelected ? null : AppTheme.cyberSurface,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: isSelected
                        ? Colors.transparent
                        : AppTheme.neonCyan.withValues(alpha: 0.2),
                  ),
                  boxShadow: isSelected
                      ? [
                          BoxShadow(
                            color: AppTheme.neonCyan.withValues(alpha: 0.3),
                            blurRadius: 12,
                          ),
                        ]
                      : null,
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      '#$tag',
                      style: TextStyle(
                        fontSize: 13,
                        color: isSelected ? Colors.white : AppTheme.neonCyan,
                        fontWeight:
                            isSelected ? FontWeight.w600 : FontWeight.normal,
                      ),
                    ),
                    if (isSelected) ...[
                      const SizedBox(width: 6),
                      const Icon(
                        Icons.close,
                        size: 14,
                        color: Colors.white,
                      ),
                    ],
                  ],
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildPreviewContent() {
    if (_contentController.text.trim().isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.article_outlined,
              size: 64,
              color: AppTheme.textMuted.withValues(alpha: 0.5),
            ),
            const SizedBox(height: 16),
            const Text(
              'Start typing to see preview',
              style: TextStyle(
                color: AppTheme.textMuted,
                fontSize: 16,
              ),
            ),
          ],
        ),
      );
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'POST PREVIEW',
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: AppTheme.textMuted,
              letterSpacing: 1.5,
            ),
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              gradient: AppTheme.cardGradient,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                color: AppTheme.neonCyan.withValues(alpha: 0.1),
              ),
              boxShadow: [
                BoxShadow(
                  color: AppTheme.neonCyan.withValues(alpha: 0.1),
                  blurRadius: 20,
                  offset: const Offset(0, 10),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header
                Row(
                  children: [
                    Consumer<AppState>(
                      builder: (context, appState, child) {
                        return AvatarWidget(
                          seed: appState.currentUser?.avatarSeed ?? 'user',
                          size: 44,
                        );
                      },
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Consumer<AppState>(
                            builder: (context, appState, child) {
                              return Text(
                                appState.currentUser?.displayName ?? 'User',
                                style: const TextStyle(
                                  fontWeight: FontWeight.w600,
                                  fontSize: 15,
                                  color: AppTheme.textPrimary,
                                ),
                              );
                            },
                          ),
                          Row(
                            children: [
                              const Icon(
                                Icons.group,
                                size: 12,
                                color: AppTheme.neonCyan,
                              ),
                              const SizedBox(width: 4),
                              Text(
                                _selectedCommunity?.name ?? 'Community',
                                style: TextStyle(
                                  fontSize: 12,
                                  color:
                                      AppTheme.neonCyan.withValues(alpha: 0.8),
                                ),
                              ),
                              const SizedBox(width: 8),
                              const Text(
                                'Just now',
                                style: TextStyle(
                                  fontSize: 12,
                                  color: AppTheme.textMuted,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),

                // Content
                Text(
                  _contentController.text,
                  style: const TextStyle(
                    fontSize: 15,
                    height: 1.5,
                    color: AppTheme.textPrimary,
                  ),
                ),

                // Image preview in post preview
                if (_selectedImage != null) ...[
                  const SizedBox(height: 12),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    child: Image.file(
                      _selectedImage!,
                      width: double.infinity,
                      fit: BoxFit.cover,
                    ),
                  ),
                ],

                const SizedBox(height: 16),

                // Actions preview
                Row(
                  children: [
                    _buildPreviewAction(Icons.favorite_border, '0'),
                    const SizedBox(width: 24),
                    _buildPreviewAction(Icons.chat_bubble_outline, '0'),
                    const SizedBox(width: 24),
                    _buildPreviewAction(Icons.repeat, '0'),
                    const Spacer(),
                    Icon(
                      Icons.bookmark_border,
                      color: AppTheme.textMuted.withValues(alpha: 0.5),
                      size: 20,
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

  Widget _buildPreviewAction(IconData icon, String count) {
    return Row(
      children: [
        Icon(
          icon,
          color: AppTheme.textMuted.withValues(alpha: 0.5),
          size: 18,
        ),
        const SizedBox(width: 4),
        Text(
          count,
          style: TextStyle(
            fontSize: 13,
            color: AppTheme.textMuted.withValues(alpha: 0.5),
          ),
        ),
      ],
    );
  }

  Widget _buildBottomBar() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.glassBg,
        border: Border(
          top: BorderSide(
            color: AppTheme.neonCyan.withValues(alpha: 0.1),
          ),
        ),
      ),
      child: SafeArea(
        top: false,
        child: Row(
          children: [
            Icon(
              Icons.public,
              size: 18,
              color: AppTheme.textMuted,
            ),
            const SizedBox(width: 8),
            const Text(
              'Everyone can reply',
              style: TextStyle(
                fontSize: 13,
                color: AppTheme.textMuted,
              ),
            ),
            const Spacer(),
            if (_hashtags.isNotEmpty)
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: AppTheme.neonCyan.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '${_hashtags.length} tags',
                  style: const TextStyle(
                    fontSize: 11,
                    color: AppTheme.neonCyan,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildSuccessOverlay() {
    return Container(
      color: AppTheme.cyberBlack.withValues(alpha: 0.95),
      child: Center(
        child: ScaleTransition(
          scale: _successAnimation,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                padding: const EdgeInsets.all(32),
                decoration: BoxDecoration(
                  gradient: AppTheme.primaryGradient,
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: AppTheme.neonCyan.withValues(alpha: 0.5),
                      blurRadius: 40,
                      spreadRadius: 10,
                    ),
                  ],
                ),
                child: const Icon(
                  Icons.check,
                  size: 56,
                  color: Colors.white,
                ),
              ),
              const SizedBox(height: 32),
              ShaderMask(
                shaderCallback: (bounds) =>
                    AppTheme.primaryGradient.createShader(bounds),
                child: const Text(
                  'Post Created!',
                  style: TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
              ),
              const SizedBox(height: 12),
              const Text(
                'Your post is now live in the community',
                style: TextStyle(
                  color: AppTheme.textSecondary,
                  fontSize: 16,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
