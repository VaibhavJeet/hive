import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// worldmonitor-inspired Design System for AI Social App
/// Clean, professional, monospace-focused aesthetic
class AppTheme {
  AppTheme._();

  // ===== Color Palette (worldmonitor design) =====

  // Background colors
  static const Color bg = Color(0xFF0A0A0A);
  static const Color bgSecondary = Color(0xFF111111);
  static const Color surface = Color(0xFF141414);
  static const Color surfaceHover = Color(0xFF1E1E1E);
  static const Color surfaceActive = Color(0xFF1A1A2E);

  // Border colors
  static const Color border = Color(0xFF2A2A2A);
  static const Color borderStrong = Color(0xFF444444);
  static const Color borderSubtle = Color(0xFF1A1A1A);

  // Semantic colors
  static const Color semanticGreen = Color(0xFF44FF88);
  static const Color semanticRed = Color(0xFFFF4444);
  static const Color semanticYellow = Color(0xFFFFAA00);
  static const Color semanticBlue = Color(0xFF3B82F6);
  static const Color semanticInfo = Color(0xFF3B82F6);

  // Status colors
  static const Color successColor = semanticGreen;
  static const Color warningColor = semanticYellow;
  static const Color errorColor = semanticRed;
  static const Color infoColor = semanticBlue;

  // Text colors
  static const Color textPrimary = Color(0xFFE8E8E8);
  static const Color textSecondary = Color(0xFFA0A0A0);
  static const Color textMuted = Color(0xFF666666);
  static const Color textDim = Color(0xFF888888);
  static const Color textDisabled = Color(0xFF555555);
  static const Color textAccent = Color(0xFFFFFFFF);

  // Panel/Card colors
  static const Color panelBg = Color(0xFF141414);
  static const Color panelBorder = Color(0xFF2A2A2A);
  static const Color inputBg = Color(0xFF1A1A1A);

  // Overlay colors
  static const Color overlaySubtle = Color(0x08FFFFFF);
  static const Color overlayLight = Color(0x0DFFFFFF);
  static const Color overlayMedium = Color(0x1AFFFFFF);

  // Legacy compatibility (mapping to new colors)
  static const Color cyberBlack = bg;
  static const Color cyberDark = bgSecondary;
  static const Color cyberDeeper = surface;
  static const Color cyberSurface = surfaceHover;
  static const Color cyberMuted = border;
  static const Color neonCyan = semanticBlue;
  static const Color neonMagenta = semanticRed;
  static const Color neonGreen = semanticGreen;
  static const Color neonAmber = semanticYellow;
  static const Color neonPurple = Color(0xFF8B5CF6);
  static const Color neonRed = semanticRed;
  static const Color primaryColor = semanticBlue;
  static const Color secondaryColor = semanticGreen;
  static const Color accentColor = semanticGreen;
  static const Color backgroundColor = bg;
  static const Color surfaceColor = surface;
  static const Color cardColor = surface;
  static const Color glassBg = Color(0xE6141414);
  static const Color glassBorder = Color(0x1A3B82F6);
  static const Color glassHighlight = Color(0x08FFFFFF);

  // AI indicator colors
  static const Color aiLabelColor = neonPurple;
  static const Color aiLabelBg = Color(0xFF1A1A2E);

  // ===== Gradients (subtle, professional) =====

  static const LinearGradient primaryGradient = LinearGradient(
    colors: [semanticBlue, Color(0xFF6366F1)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient successGradient = LinearGradient(
    colors: [semanticGreen, Color(0xFF22C55E)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient cardGradient = LinearGradient(
    colors: [surface, bgSecondary],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient glassGradient = LinearGradient(
    colors: [Color(0xE6141414), Color(0xF2111111)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient surfaceGradient = LinearGradient(
    colors: [surface, bgSecondary],
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
  );

  // Legacy gradient aliases
  static const LinearGradient cyberGradient = primaryGradient;

  // ===== Shadows (subtle, professional) =====

  static List<BoxShadow> subtleGlow(Color color, {double intensity = 1.0}) => [
        BoxShadow(
          color: color.withValues(alpha: 0.15 * intensity),
          blurRadius: 6 * intensity,
          spreadRadius: 0,
        ),
      ];

  static List<BoxShadow> blueGlow({double intensity = 1.0}) =>
      subtleGlow(semanticBlue, intensity: intensity);

  static List<BoxShadow> greenGlow({double intensity = 1.0}) =>
      subtleGlow(semanticGreen, intensity: intensity);

  static List<BoxShadow> redGlow({double intensity = 1.0}) =>
      subtleGlow(semanticRed, intensity: intensity);

  static List<BoxShadow> yellowGlow({double intensity = 1.0}) =>
      subtleGlow(semanticYellow, intensity: intensity);

  // Legacy glow aliases
  static List<BoxShadow> cyanGlow({double intensity = 1.0}) =>
      blueGlow(intensity: intensity);
  static List<BoxShadow> magentaGlow({double intensity = 1.0}) =>
      redGlow(intensity: intensity);
  static List<BoxShadow> amberGlow({double intensity = 1.0}) =>
      yellowGlow(intensity: intensity);

  static List<BoxShadow> cardShadow = [
    const BoxShadow(
      color: Color(0x40000000),
      blurRadius: 16,
      offset: Offset(0, 4),
    ),
  ];

  static List<BoxShadow> elevatedShadow = [
    const BoxShadow(
      color: Color(0x50000000),
      blurRadius: 24,
      offset: Offset(0, 8),
    ),
  ];

  // ===== Border Radius =====

  static const double radiusXs = 4.0;
  static const double radiusSm = 8.0;
  static const double radiusMd = 12.0;
  static const double radiusLg = 16.0;
  static const double radiusXl = 20.0;
  static const double radiusXxl = 28.0;

  // ===== Spacing =====

  static const double spacingXxs = 2.0;
  static const double spacingXs = 4.0;
  static const double spacingSm = 8.0;
  static const double spacingMd = 12.0;
  static const double spacingLg = 16.0;
  static const double spacingXl = 20.0;
  static const double spacingXxl = 24.0;
  static const double spacing3Xl = 32.0;
  static const double spacing4Xl = 48.0;

  // ===== Dark Theme =====

  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      fontFamily: 'Inter',

      // Color Scheme (worldmonitor)
      colorScheme: const ColorScheme.dark(
        primary: semanticBlue,
        onPrimary: Colors.white,
        primaryContainer: Color(0xFF1E3A5F),
        onPrimaryContainer: semanticBlue,
        secondary: semanticGreen,
        onSecondary: bg,
        secondaryContainer: Color(0xFF0D3320),
        onSecondaryContainer: semanticGreen,
        tertiary: semanticYellow,
        onTertiary: bg,
        tertiaryContainer: Color(0xFF3D2E00),
        onTertiaryContainer: semanticYellow,
        error: errorColor,
        onError: Colors.white,
        errorContainer: Color(0xFF3D1111),
        onErrorContainer: errorColor,
        surface: surface,
        onSurface: textPrimary,
        surfaceContainerHighest: surfaceHover,
        onSurfaceVariant: textSecondary,
        outline: border,
        outlineVariant: borderSubtle,
        shadow: Colors.black,
        scrim: Colors.black,
        inverseSurface: textPrimary,
        onInverseSurface: bg,
        inversePrimary: Color(0xFF1E40AF),
      ),

      // Scaffold
      scaffoldBackgroundColor: bg,

      // AppBar Theme
      appBarTheme: AppBarTheme(
        backgroundColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        systemOverlayStyle: const SystemUiOverlayStyle(
          statusBarColor: Colors.transparent,
          statusBarIconBrightness: Brightness.light,
          statusBarBrightness: Brightness.dark,
        ),
        titleTextStyle: const TextStyle(
          color: textPrimary,
          fontSize: 20,
          fontWeight: FontWeight.w600,
          fontFamily: 'Inter',
          letterSpacing: -0.5,
        ),
        toolbarTextStyle: const TextStyle(
          color: textPrimary,
          fontSize: 16,
          fontFamily: 'Inter',
        ),
        iconTheme: const IconThemeData(color: textPrimary, size: 24),
        actionsIconTheme: const IconThemeData(color: textSecondary, size: 24),
        surfaceTintColor: Colors.transparent,
        shadowColor: Colors.transparent,
        shape: const Border(
          bottom: BorderSide(
            color: glassBorder,
            width: 1,
          ),
        ),
      ),

      // Card Theme
      cardTheme: CardThemeData(
        color: cyberDeeper,
        elevation: 0,
        shadowColor: Colors.transparent,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusLg),
          side: const BorderSide(
            color: glassBorder,
            width: 1,
          ),
        ),
        margin: EdgeInsets.zero,
        clipBehavior: Clip.antiAlias,
      ),

      // Bottom Navigation Bar Theme
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: Colors.transparent,
        selectedItemColor: neonCyan,
        unselectedItemColor: textMuted,
        type: BottomNavigationBarType.fixed,
        elevation: 0,
        selectedLabelStyle: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w600,
          fontFamily: 'Inter',
        ),
        unselectedLabelStyle: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w500,
          fontFamily: 'Inter',
        ),
        showSelectedLabels: true,
        showUnselectedLabels: true,
      ),

      // Navigation Bar Theme (Material 3)
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: glassBg,
        elevation: 0,
        height: 72,
        indicatorColor: neonCyan.withValues(alpha: 0.15),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const IconThemeData(color: neonCyan, size: 24);
          }
          return const IconThemeData(color: textMuted, size: 24);
        }),
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const TextStyle(
              color: neonCyan,
              fontSize: 12,
              fontWeight: FontWeight.w600,
              fontFamily: 'Inter',
            );
          }
          return const TextStyle(
            color: textMuted,
            fontSize: 12,
            fontWeight: FontWeight.w500,
            fontFamily: 'Inter',
          );
        }),
        surfaceTintColor: Colors.transparent,
        shadowColor: Colors.transparent,
      ),

      // Input Decoration Theme
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: cyberDeeper,
        hintStyle: const TextStyle(
          color: textMuted,
          fontSize: 14,
          fontWeight: FontWeight.w400,
        ),
        labelStyle: const TextStyle(
          color: textSecondary,
          fontSize: 14,
          fontWeight: FontWeight.w500,
        ),
        floatingLabelStyle: const TextStyle(
          color: neonCyan,
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
        helperStyle: const TextStyle(
          color: textMuted,
          fontSize: 12,
        ),
        errorStyle: const TextStyle(
          color: errorColor,
          fontSize: 12,
          fontWeight: FontWeight.w500,
        ),
        prefixIconColor: textMuted,
        suffixIconColor: textMuted,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusMd),
          borderSide: const BorderSide(color: cyberMuted, width: 1),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusMd),
          borderSide: const BorderSide(color: cyberMuted, width: 1),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusMd),
          borderSide: const BorderSide(color: neonCyan, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusMd),
          borderSide: const BorderSide(color: errorColor, width: 1),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusMd),
          borderSide: const BorderSide(color: errorColor, width: 2),
        ),
        disabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusMd),
          borderSide: BorderSide(color: cyberMuted.withValues(alpha: 0.5), width: 1),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        isDense: false,
      ),

      // Elevated Button Theme
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: neonCyan,
          foregroundColor: cyberBlack,
          disabledBackgroundColor: cyberMuted,
          disabledForegroundColor: textDisabled,
          elevation: 0,
          shadowColor: Colors.transparent,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radiusMd),
          ),
          textStyle: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            fontFamily: 'Inter',
            letterSpacing: 0.5,
          ),
        ),
      ),

      // Outlined Button Theme
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: neonCyan,
          disabledForegroundColor: textDisabled,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          side: const BorderSide(color: neonCyan, width: 2),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radiusMd),
          ),
          textStyle: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            fontFamily: 'Inter',
            letterSpacing: 0.5,
          ),
        ),
      ),

      // Text Button Theme
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: neonCyan,
          disabledForegroundColor: textDisabled,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radiusSm),
          ),
          textStyle: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            fontFamily: 'Inter',
          ),
        ),
      ),

      // Filled Button Theme
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: neonCyan,
          foregroundColor: cyberBlack,
          disabledBackgroundColor: cyberMuted,
          disabledForegroundColor: textDisabled,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radiusMd),
          ),
          textStyle: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            fontFamily: 'Inter',
            letterSpacing: 0.5,
          ),
        ),
      ),

      // Icon Button Theme
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(
          foregroundColor: textSecondary,
          hoverColor: neonCyan.withValues(alpha: 0.1),
          focusColor: neonCyan.withValues(alpha: 0.15),
          highlightColor: neonCyan.withValues(alpha: 0.1),
        ),
      ),

      // Floating Action Button Theme
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: neonCyan,
        foregroundColor: cyberBlack,
        elevation: 4,
        focusElevation: 6,
        hoverElevation: 8,
        highlightElevation: 6,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusLg),
        ),
        extendedTextStyle: const TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          fontFamily: 'Inter',
          letterSpacing: 0.5,
        ),
      ),

      // Chip Theme
      chipTheme: ChipThemeData(
        backgroundColor: cyberDeeper,
        deleteIconColor: textMuted,
        disabledColor: cyberMuted,
        selectedColor: neonCyan.withValues(alpha: 0.2),
        secondarySelectedColor: neonMagenta.withValues(alpha: 0.2),
        labelPadding: const EdgeInsets.symmetric(horizontal: 8),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusSm),
          side: const BorderSide(color: cyberMuted, width: 1),
        ),
        labelStyle: const TextStyle(
          color: textPrimary,
          fontSize: 13,
          fontWeight: FontWeight.w500,
          fontFamily: 'Inter',
        ),
        secondaryLabelStyle: const TextStyle(
          color: textSecondary,
          fontSize: 13,
          fontWeight: FontWeight.w500,
          fontFamily: 'Inter',
        ),
        brightness: Brightness.dark,
        elevation: 0,
        pressElevation: 0,
      ),

      // Dialog Theme
      dialogTheme: DialogThemeData(
        backgroundColor: cyberDark,
        elevation: 24,
        shadowColor: neonCyan.withValues(alpha: 0.1),
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusXl),
          side: BorderSide(
            color: neonCyan.withValues(alpha: 0.2),
            width: 1,
          ),
        ),
        titleTextStyle: const TextStyle(
          color: textPrimary,
          fontSize: 20,
          fontWeight: FontWeight.w600,
          fontFamily: 'Inter',
        ),
        contentTextStyle: const TextStyle(
          color: textSecondary,
          fontSize: 14,
          fontWeight: FontWeight.w400,
          fontFamily: 'Inter',
          height: 1.5,
        ),
      ),

      // Bottom Sheet Theme
      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: cyberDark,
        modalBackgroundColor: cyberDark,
        elevation: 16,
        shadowColor: neonCyan.withValues(alpha: 0.1),
        surfaceTintColor: Colors.transparent,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(radiusXl)),
          side: BorderSide(
            color: glassBorder,
            width: 1,
          ),
        ),
        dragHandleColor: cyberMuted,
        dragHandleSize: const Size(40, 4),
        showDragHandle: true,
        modalElevation: 24,
      ),

      // Snackbar Theme
      snackBarTheme: SnackBarThemeData(
        backgroundColor: cyberDeeper,
        contentTextStyle: const TextStyle(
          color: textPrimary,
          fontSize: 14,
          fontWeight: FontWeight.w500,
          fontFamily: 'Inter',
        ),
        actionTextColor: neonCyan,
        behavior: SnackBarBehavior.floating,
        elevation: 8,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusMd),
          side: const BorderSide(
            color: glassBorder,
            width: 1,
          ),
        ),
        insetPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      ),

      // Tab Bar Theme
      tabBarTheme: TabBarThemeData(
        labelColor: neonCyan,
        unselectedLabelColor: textMuted,
        labelStyle: const TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          fontFamily: 'Inter',
        ),
        unselectedLabelStyle: const TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w500,
          fontFamily: 'Inter',
        ),
        indicator: BoxDecoration(
          border: Border(
            bottom: BorderSide(
              color: neonCyan,
              width: 2,
            ),
          ),
        ),
        indicatorSize: TabBarIndicatorSize.tab,
        dividerColor: cyberMuted,
        dividerHeight: 1,
      ),

      // Divider Theme
      dividerTheme: const DividerThemeData(
        color: cyberMuted,
        thickness: 1,
        space: 1,
      ),

      // List Tile Theme
      listTileTheme: const ListTileThemeData(
        iconColor: textSecondary,
        textColor: textPrimary,
        contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        dense: false,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(radiusMd)),
        ),
        titleTextStyle: TextStyle(
          color: textPrimary,
          fontSize: 16,
          fontWeight: FontWeight.w500,
          fontFamily: 'Inter',
        ),
        subtitleTextStyle: TextStyle(
          color: textSecondary,
          fontSize: 14,
          fontWeight: FontWeight.w400,
          fontFamily: 'Inter',
        ),
        leadingAndTrailingTextStyle: TextStyle(
          color: textMuted,
          fontSize: 12,
          fontWeight: FontWeight.w500,
          fontFamily: 'Inter',
        ),
      ),

      // Switch Theme
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return neonCyan;
          }
          return textMuted;
        }),
        trackColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return neonCyan.withValues(alpha: 0.3);
          }
          return cyberMuted;
        }),
        trackOutlineColor: WidgetStateProperty.all(Colors.transparent),
      ),

      // Checkbox Theme
      checkboxTheme: CheckboxThemeData(
        fillColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return neonCyan;
          }
          return Colors.transparent;
        }),
        checkColor: WidgetStateProperty.all(cyberBlack),
        side: const BorderSide(color: cyberMuted, width: 2),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusXs),
        ),
      ),

      // Radio Theme
      radioTheme: RadioThemeData(
        fillColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return neonCyan;
          }
          return cyberMuted;
        }),
      ),

      // Slider Theme
      sliderTheme: SliderThemeData(
        activeTrackColor: neonCyan,
        inactiveTrackColor: cyberMuted,
        thumbColor: neonCyan,
        overlayColor: neonCyan.withValues(alpha: 0.2),
        valueIndicatorColor: cyberDeeper,
        valueIndicatorTextStyle: const TextStyle(
          color: neonCyan,
          fontSize: 12,
          fontWeight: FontWeight.w600,
          fontFamily: 'Inter',
        ),
        trackHeight: 4,
        thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 8),
      ),

      // Progress Indicator Theme
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: neonCyan,
        linearTrackColor: cyberMuted,
        circularTrackColor: cyberMuted,
      ),

      // Tooltip Theme
      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: cyberSurface,
          borderRadius: BorderRadius.circular(radiusSm),
          border: Border.all(color: glassBorder),
          boxShadow: [
            BoxShadow(
              color: neonCyan.withValues(alpha: 0.1),
              blurRadius: 8,
            ),
          ],
        ),
        textStyle: const TextStyle(
          color: textPrimary,
          fontSize: 12,
          fontWeight: FontWeight.w500,
          fontFamily: 'Inter',
        ),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      ),

      // Popup Menu Theme
      popupMenuTheme: PopupMenuThemeData(
        color: cyberDark,
        elevation: 8,
        shadowColor: neonCyan.withValues(alpha: 0.1),
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusMd),
          side: const BorderSide(color: glassBorder, width: 1),
        ),
        textStyle: const TextStyle(
          color: textPrimary,
          fontSize: 14,
          fontWeight: FontWeight.w500,
          fontFamily: 'Inter',
        ),
      ),

      // Drawer Theme
      drawerTheme: const DrawerThemeData(
        backgroundColor: cyberDark,
        elevation: 16,
        surfaceTintColor: Colors.transparent,
        shadowColor: Colors.black45,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.horizontal(right: Radius.circular(radiusXl)),
        ),
      ),

      // Badge Theme
      badgeTheme: BadgeThemeData(
        backgroundColor: neonMagenta,
        textColor: Colors.white,
        textStyle: const TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w700,
          fontFamily: 'Inter',
        ),
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      ),

      // Search Bar Theme
      searchBarTheme: SearchBarThemeData(
        backgroundColor: WidgetStateProperty.all(cyberDeeper),
        elevation: WidgetStateProperty.all(0),
        shadowColor: WidgetStateProperty.all(Colors.transparent),
        surfaceTintColor: WidgetStateProperty.all(Colors.transparent),
        shape: WidgetStateProperty.all(
          RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radiusLg),
            side: const BorderSide(color: cyberMuted, width: 1),
          ),
        ),
        hintStyle: WidgetStateProperty.all(
          const TextStyle(
            color: textMuted,
            fontSize: 14,
            fontWeight: FontWeight.w400,
            fontFamily: 'Inter',
          ),
        ),
        textStyle: WidgetStateProperty.all(
          const TextStyle(
            color: textPrimary,
            fontSize: 14,
            fontWeight: FontWeight.w400,
            fontFamily: 'Inter',
          ),
        ),
        padding: WidgetStateProperty.all(
          const EdgeInsets.symmetric(horizontal: 16),
        ),
      ),

      // Text Theme
      textTheme: const TextTheme(
        // Display styles
        displayLarge: TextStyle(
          color: textPrimary,
          fontSize: 57,
          fontWeight: FontWeight.w400,
          fontFamily: 'Inter',
          letterSpacing: -0.25,
          height: 1.12,
        ),
        displayMedium: TextStyle(
          color: textPrimary,
          fontSize: 45,
          fontWeight: FontWeight.w400,
          fontFamily: 'Inter',
          letterSpacing: 0,
          height: 1.16,
        ),
        displaySmall: TextStyle(
          color: textPrimary,
          fontSize: 36,
          fontWeight: FontWeight.w400,
          fontFamily: 'Inter',
          letterSpacing: 0,
          height: 1.22,
        ),

        // Headline styles
        headlineLarge: TextStyle(
          color: textPrimary,
          fontSize: 32,
          fontWeight: FontWeight.w700,
          fontFamily: 'Inter',
          letterSpacing: -0.5,
          height: 1.25,
        ),
        headlineMedium: TextStyle(
          color: textPrimary,
          fontSize: 28,
          fontWeight: FontWeight.w600,
          fontFamily: 'Inter',
          letterSpacing: -0.25,
          height: 1.29,
        ),
        headlineSmall: TextStyle(
          color: textPrimary,
          fontSize: 24,
          fontWeight: FontWeight.w600,
          fontFamily: 'Inter',
          letterSpacing: 0,
          height: 1.33,
        ),

        // Title styles
        titleLarge: TextStyle(
          color: textPrimary,
          fontSize: 22,
          fontWeight: FontWeight.w600,
          fontFamily: 'Inter',
          letterSpacing: 0,
          height: 1.27,
        ),
        titleMedium: TextStyle(
          color: textPrimary,
          fontSize: 16,
          fontWeight: FontWeight.w600,
          fontFamily: 'Inter',
          letterSpacing: 0.15,
          height: 1.50,
        ),
        titleSmall: TextStyle(
          color: textSecondary,
          fontSize: 14,
          fontWeight: FontWeight.w500,
          fontFamily: 'Inter',
          letterSpacing: 0.1,
          height: 1.43,
        ),

        // Body styles
        bodyLarge: TextStyle(
          color: textPrimary,
          fontSize: 16,
          fontWeight: FontWeight.w400,
          fontFamily: 'Inter',
          letterSpacing: 0.5,
          height: 1.50,
        ),
        bodyMedium: TextStyle(
          color: textPrimary,
          fontSize: 14,
          fontWeight: FontWeight.w400,
          fontFamily: 'Inter',
          letterSpacing: 0.25,
          height: 1.43,
        ),
        bodySmall: TextStyle(
          color: textSecondary,
          fontSize: 12,
          fontWeight: FontWeight.w400,
          fontFamily: 'Inter',
          letterSpacing: 0.4,
          height: 1.33,
        ),

        // Label styles
        labelLarge: TextStyle(
          color: textPrimary,
          fontSize: 14,
          fontWeight: FontWeight.w600,
          fontFamily: 'Inter',
          letterSpacing: 0.1,
          height: 1.43,
        ),
        labelMedium: TextStyle(
          color: textSecondary,
          fontSize: 12,
          fontWeight: FontWeight.w500,
          fontFamily: 'Inter',
          letterSpacing: 0.5,
          height: 1.33,
        ),
        labelSmall: TextStyle(
          color: textMuted,
          fontSize: 11,
          fontWeight: FontWeight.w500,
          fontFamily: 'Inter',
          letterSpacing: 0.5,
          height: 1.45,
        ),
      ),
    );
  }

  // ===== Light Theme (Clean Professional) =====

  static ThemeData get lightTheme {
    const lightBackground = Color(0xFFF8F9FC);
    const lightSurface = Color(0xFFFFFFFF);
    const lightCard = Color(0xFFF0F2F5);
    const lightBorder = Color(0xFFE0E4EB);
    const lightTextPrimary = Color(0xFF1A1D26);
    const lightTextSecondary = Color(0xFF5A6170);
    const lightTextMuted = Color(0xFF9099A8);
    const lightPrimary = Color(0xFF0088A0);
    const lightSecondary = Color(0xFFB3006D);

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      fontFamily: 'Inter',

      colorScheme: const ColorScheme.light(
        primary: lightPrimary,
        onPrimary: Colors.white,
        secondary: lightSecondary,
        onSecondary: Colors.white,
        surface: lightSurface,
        onSurface: lightTextPrimary,
        error: errorColor,
        onError: Colors.white,
        outline: lightBorder,
      ),

      scaffoldBackgroundColor: lightBackground,

      appBarTheme: AppBarTheme(
        backgroundColor: lightSurface,
        elevation: 0,
        scrolledUnderElevation: 1,
        systemOverlayStyle: const SystemUiOverlayStyle(
          statusBarColor: Colors.transparent,
          statusBarIconBrightness: Brightness.dark,
          statusBarBrightness: Brightness.light,
        ),
        titleTextStyle: const TextStyle(
          color: lightTextPrimary,
          fontSize: 20,
          fontWeight: FontWeight.w600,
          fontFamily: 'Inter',
        ),
        iconTheme: const IconThemeData(color: lightTextPrimary),
        surfaceTintColor: Colors.transparent,
        shape: const Border(
          bottom: BorderSide(color: lightBorder, width: 1),
        ),
      ),

      cardTheme: CardThemeData(
        color: lightSurface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusLg),
          side: const BorderSide(color: lightBorder, width: 1),
        ),
      ),

      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: lightCard,
        hintStyle: const TextStyle(color: lightTextMuted),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusMd),
          borderSide: const BorderSide(color: lightBorder),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusMd),
          borderSide: const BorderSide(color: lightBorder),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusMd),
          borderSide: const BorderSide(color: lightPrimary, width: 2),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: lightPrimary,
          foregroundColor: Colors.white,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radiusMd),
          ),
        ),
      ),

      textTheme: const TextTheme(
        headlineLarge: TextStyle(
          color: lightTextPrimary,
          fontSize: 32,
          fontWeight: FontWeight.w700,
          fontFamily: 'Inter',
        ),
        headlineMedium: TextStyle(
          color: lightTextPrimary,
          fontSize: 28,
          fontWeight: FontWeight.w600,
          fontFamily: 'Inter',
        ),
        headlineSmall: TextStyle(
          color: lightTextPrimary,
          fontSize: 24,
          fontWeight: FontWeight.w600,
          fontFamily: 'Inter',
        ),
        titleLarge: TextStyle(
          color: lightTextPrimary,
          fontSize: 22,
          fontWeight: FontWeight.w600,
          fontFamily: 'Inter',
        ),
        titleMedium: TextStyle(
          color: lightTextPrimary,
          fontSize: 16,
          fontWeight: FontWeight.w600,
          fontFamily: 'Inter',
        ),
        titleSmall: TextStyle(
          color: lightTextSecondary,
          fontSize: 14,
          fontWeight: FontWeight.w500,
          fontFamily: 'Inter',
        ),
        bodyLarge: TextStyle(
          color: lightTextPrimary,
          fontSize: 16,
          fontFamily: 'Inter',
        ),
        bodyMedium: TextStyle(
          color: lightTextPrimary,
          fontSize: 14,
          fontFamily: 'Inter',
        ),
        bodySmall: TextStyle(
          color: lightTextSecondary,
          fontSize: 12,
          fontFamily: 'Inter',
        ),
        labelLarge: TextStyle(
          color: lightTextPrimary,
          fontSize: 14,
          fontWeight: FontWeight.w600,
          fontFamily: 'Inter',
        ),
        labelMedium: TextStyle(
          color: lightTextSecondary,
          fontSize: 12,
          fontWeight: FontWeight.w500,
          fontFamily: 'Inter',
        ),
        labelSmall: TextStyle(
          color: lightTextMuted,
          fontSize: 11,
          fontWeight: FontWeight.w500,
          fontFamily: 'Inter',
        ),
      ),
    );
  }
}

// ===== Theme Extensions =====

/// Extension for easy color access via BuildContext
extension AppColors on BuildContext {
  // Primary colors
  Color get primaryColor => AppTheme.neonCyan;
  Color get secondaryColor => AppTheme.neonMagenta;
  Color get accentColor => AppTheme.neonGreen;

  // Background colors
  Color get backgroundColor => AppTheme.cyberBlack;
  Color get surfaceColor => AppTheme.cyberSurface;
  Color get cardColor => AppTheme.cyberDeeper;

  // Text colors
  Color get textPrimary => AppTheme.textPrimary;
  Color get textSecondary => AppTheme.textSecondary;
  Color get textMuted => AppTheme.textMuted;

  // Status colors
  Color get successColor => AppTheme.successColor;
  Color get warningColor => AppTheme.warningColor;
  Color get errorColor => AppTheme.errorColor;
  Color get infoColor => AppTheme.infoColor;

  // Neon colors
  Color get neonCyan => AppTheme.neonCyan;
  Color get neonMagenta => AppTheme.neonMagenta;
  Color get neonGreen => AppTheme.neonGreen;
  Color get neonAmber => AppTheme.neonAmber;
  Color get neonPurple => AppTheme.neonPurple;
}

/// Status color helper for different states
class StatusColors {
  static const Color online = AppTheme.neonGreen;
  static const Color offline = AppTheme.textMuted;
  static const Color busy = AppTheme.neonAmber;
  static const Color error = AppTheme.errorColor;
  static const Color warning = AppTheme.warningColor;
  static const Color success = AppTheme.neonGreen;
  static const Color info = AppTheme.neonCyan;
  static const Color pending = AppTheme.neonPurple;

  static Color fromStatus(String status) {
    switch (status.toLowerCase()) {
      case 'online':
      case 'active':
      case 'success':
      case 'completed':
        return online;
      case 'offline':
      case 'inactive':
        return offline;
      case 'busy':
      case 'away':
        return busy;
      case 'error':
      case 'failed':
        return error;
      case 'warning':
        return warning;
      case 'info':
        return info;
      case 'pending':
      case 'processing':
        return pending;
      default:
        return offline;
    }
  }
}

// ===== Custom Decorations =====

/// Glassmorphism decoration for cards
class GlassDecoration extends BoxDecoration {
  GlassDecoration({
    Color glowColor = AppTheme.neonCyan,
    double glowIntensity = 0.15,
    double borderOpacity = 0.12,
    double backgroundOpacity = 0.7,
    double blurRadius = 12,
    BorderRadius? borderRadius,
  }) : super(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              AppTheme.cyberSurface.withValues(alpha: backgroundOpacity * 0.8),
              AppTheme.cyberDark.withValues(alpha: backgroundOpacity),
            ],
          ),
          borderRadius: borderRadius ?? BorderRadius.circular(AppTheme.radiusLg),
          border: Border.all(
            color: glowColor.withValues(alpha: borderOpacity),
            width: 1,
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.4),
              blurRadius: 32,
              offset: const Offset(0, 8),
            ),
            BoxShadow(
              color: glowColor.withValues(alpha: glowIntensity),
              blurRadius: blurRadius,
              spreadRadius: 0,
            ),
          ],
        );
}

/// Neon glow decoration for highlighted elements
class NeonGlowDecoration extends BoxDecoration {
  NeonGlowDecoration({
    required Color color,
    double intensity = 1.0,
    BorderRadius? borderRadius,
    bool filled = false,
  }) : super(
          color: filled ? color.withValues(alpha: 0.1) : Colors.transparent,
          borderRadius: borderRadius ?? BorderRadius.circular(AppTheme.radiusMd),
          border: Border.all(
            color: color.withValues(alpha: 0.5 * intensity),
            width: 2,
          ),
          boxShadow: [
            BoxShadow(
              color: color.withValues(alpha: 0.3 * intensity),
              blurRadius: 10 * intensity,
              spreadRadius: 0,
            ),
            BoxShadow(
              color: color.withValues(alpha: 0.15 * intensity),
              blurRadius: 20 * intensity,
              spreadRadius: 0,
            ),
          ],
        );
}

/// Input field decoration with neon focus effect
class NeonInputDecoration extends InputDecoration {
  NeonInputDecoration({
    required String hint,
    IconData? prefixIcon,
    super.suffix,
    Color focusColor = AppTheme.neonCyan,
  }) : super(
          hintText: hint,
          hintStyle: const TextStyle(
            color: AppTheme.textMuted,
            fontSize: 14,
          ),
          prefixIcon: prefixIcon != null
              ? Icon(prefixIcon, color: AppTheme.textMuted, size: 20)
              : null,
          filled: true,
          fillColor: AppTheme.cyberDeeper,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(AppTheme.radiusMd),
            borderSide: const BorderSide(color: AppTheme.cyberMuted, width: 1),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(AppTheme.radiusMd),
            borderSide: const BorderSide(color: AppTheme.cyberMuted, width: 1),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(AppTheme.radiusMd),
            borderSide: BorderSide(color: focusColor, width: 2),
          ),
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        );
}

/// Cyber card decoration with corner accents
class CyberCardDecoration extends BoxDecoration {
  CyberCardDecoration({
    Color accentColor = AppTheme.neonCyan,
    bool elevated = false,
  }) : super(
          gradient: const LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              Color(0xCC252538),
              Color(0xE612121A),
            ],
          ),
          borderRadius: BorderRadius.circular(AppTheme.radiusLg),
          border: Border.all(
            color: accentColor.withValues(alpha: 0.12),
            width: 1,
          ),
          boxShadow: elevated
              ? [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.4),
                    blurRadius: 32,
                    offset: const Offset(0, 8),
                  ),
                  BoxShadow(
                    color: accentColor.withValues(alpha: 0.1),
                    blurRadius: 20,
                    spreadRadius: 0,
                  ),
                ]
              : null,
        );
}

// ===== Text Styles =====

/// Monospace text style for data/numbers
class MonoTextStyle extends TextStyle {
  const MonoTextStyle({
    double fontSize = 14,
    FontWeight fontWeight = FontWeight.w500,
    Color color = AppTheme.textPrimary,
  }) : super(
          fontFamily: 'JetBrains Mono',
          fontSize: fontSize,
          fontWeight: fontWeight,
          color: color,
          letterSpacing: 0.5,
        );
}

/// Neon text style with glow effect (use with ShaderMask or custom painter)
class NeonTextStyle extends TextStyle {
  const NeonTextStyle({
    required Color color,
    double fontSize = 16,
    FontWeight fontWeight = FontWeight.w600,
  }) : super(
          color: color,
          fontSize: fontSize,
          fontWeight: fontWeight,
          fontFamily: 'Inter',
          letterSpacing: 0.5,
        );
}

// ===== Animation Durations =====

class AppAnimations {
  static const Duration fast = Duration(milliseconds: 150);
  static const Duration normal = Duration(milliseconds: 300);
  static const Duration slow = Duration(milliseconds: 500);
  static const Duration verySlow = Duration(milliseconds: 800);

  static const Curve defaultCurve = Curves.easeOutCubic;
  static const Curve bouncyCurve = Curves.elasticOut;
  static const Curve smoothCurve = Curves.easeInOutCubic;
}
