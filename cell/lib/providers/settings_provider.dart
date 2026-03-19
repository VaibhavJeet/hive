import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class SettingsProvider extends ChangeNotifier {
  // Keys for SharedPreferences
  static const String _keyThemeMode = 'theme_mode';
  static const String _keyFontSize = 'font_size';
  static const String _keyPushNotifications = 'push_notifications';
  static const String _keyDmNotifications = 'dm_notifications';
  static const String _keyMentionNotifications = 'mention_notifications';
  static const String _keyOnboardingComplete = 'onboarding_complete';

  // Theme settings
  ThemeMode _themeMode = ThemeMode.dark;
  double _fontSizeScale = 1.0;

  // Notification settings
  bool _pushNotificationsEnabled = true;
  bool _dmNotificationsEnabled = true;
  bool _mentionNotificationsEnabled = true;

  // Onboarding state
  bool _onboardingComplete = false;

  // Getters
  ThemeMode get themeMode => _themeMode;
  double get fontSizeScale => _fontSizeScale;
  bool get pushNotificationsEnabled => _pushNotificationsEnabled;
  bool get dmNotificationsEnabled => _dmNotificationsEnabled;
  bool get mentionNotificationsEnabled => _mentionNotificationsEnabled;
  bool get onboardingComplete => _onboardingComplete;

  // Load settings from SharedPreferences
  Future<void> loadSettings() async {
    final prefs = await SharedPreferences.getInstance();

    // Load theme mode
    final themeModeIndex = prefs.getInt(_keyThemeMode) ?? 2; // Default to dark
    _themeMode = ThemeMode.values[themeModeIndex.clamp(0, ThemeMode.values.length - 1)];

    // Load font size
    _fontSizeScale = prefs.getDouble(_keyFontSize) ?? 1.0;

    // Load notification settings
    _pushNotificationsEnabled = prefs.getBool(_keyPushNotifications) ?? true;
    _dmNotificationsEnabled = prefs.getBool(_keyDmNotifications) ?? true;
    _mentionNotificationsEnabled = prefs.getBool(_keyMentionNotifications) ?? true;

    // Load onboarding state
    _onboardingComplete = prefs.getBool(_keyOnboardingComplete) ?? false;

    notifyListeners();
  }

  // Theme settings
  Future<void> setThemeMode(ThemeMode mode) async {
    _themeMode = mode;
    notifyListeners();

    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyThemeMode, mode.index);
  }

  Future<void> setFontSizeScale(double scale) async {
    _fontSizeScale = scale.clamp(0.8, 1.4);
    notifyListeners();

    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble(_keyFontSize, _fontSizeScale);
  }

  // Notification settings
  Future<void> setPushNotifications(bool enabled) async {
    _pushNotificationsEnabled = enabled;
    notifyListeners();

    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_keyPushNotifications, enabled);
  }

  Future<void> setDmNotifications(bool enabled) async {
    _dmNotificationsEnabled = enabled;
    notifyListeners();

    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_keyDmNotifications, enabled);
  }

  Future<void> setMentionNotifications(bool enabled) async {
    _mentionNotificationsEnabled = enabled;
    notifyListeners();

    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_keyMentionNotifications, enabled);
  }

  // Onboarding
  Future<void> completeOnboarding() async {
    _onboardingComplete = true;
    notifyListeners();

    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_keyOnboardingComplete, true);
  }

  Future<void> resetOnboarding() async {
    _onboardingComplete = false;
    notifyListeners();

    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_keyOnboardingComplete, false);
  }

  // Reset all settings
  Future<void> resetSettings() async {
    _themeMode = ThemeMode.dark;
    _fontSizeScale = 1.0;
    _pushNotificationsEnabled = true;
    _dmNotificationsEnabled = true;
    _mentionNotificationsEnabled = true;
    notifyListeners();

    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyThemeMode, ThemeMode.dark.index);
    await prefs.setDouble(_keyFontSize, 1.0);
    await prefs.setBool(_keyPushNotifications, true);
    await prefs.setBool(_keyDmNotifications, true);
    await prefs.setBool(_keyMentionNotifications, true);
  }
}
