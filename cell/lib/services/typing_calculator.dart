import 'dart:math';

/// Calculates realistic typing durations based on message characteristics
///
/// TODO: Issue #6 - Integrate this with the typing indicator in chat_detail_screen.dart
/// The WebSocket typing_start event includes a duration_hint from the backend,
/// but this can be used for local calculations when needed.
class TypingDurationCalculator {
  static final Random _random = Random();

  /// Base typing speeds in words per minute for different personality types
  static const Map<String, int> _baseWpmByPersonality = {
    'fast': 60,      // Energetic, extroverted bots
    'normal': 40,    // Average typing speed
    'slow': 25,      // Thoughtful, careful bots
    'hesitant': 20,  // Anxious or unsure bots
  };

  /// Calculate typing duration based on message length
  ///
  /// Formula: typingDuration = baseTime + (charCount * msPerChar) + randomVariation
  ///
  /// [messageLength] - Number of characters in the message
  /// [personalityType] - Bot's typing personality (fast, normal, slow, hesitant)
  ///
  /// Returns duration in milliseconds
  static int calculateDuration({
    required int messageLength,
    String personalityType = 'normal',
  }) {
    // Get base WPM for personality type
    final wpm = _baseWpmByPersonality[personalityType] ?? 40;

    // Average word length is ~5 characters
    final wordCount = (messageLength / 5).ceil();

    // Calculate base typing time in milliseconds
    final minutesPerWord = 1.0 / wpm;
    final baseMs = (wordCount * minutesPerWord * 60 * 1000).toInt();

    // Add "thinking" time before typing (500ms - 2000ms)
    final thinkingTimeMs = 500 + _random.nextInt(1500);

    // Add occasional pauses (simulating corrections/thinking)
    final pauseCount = _random.nextInt(min(3, wordCount ~/ 10 + 1));
    final pauseTimeMs = pauseCount * (300 + _random.nextInt(700));

    // Apply human variation (±20%)
    final variationFactor = 0.8 + (_random.nextDouble() * 0.4);

    // Calculate total duration
    var totalMs = ((baseMs + thinkingTimeMs + pauseTimeMs) * variationFactor).toInt();

    // Clamp to reasonable bounds: min 1s, max 30s
    totalMs = totalMs.clamp(1000, 30000);

    return totalMs;
  }

  /// Calculate duration based on the actual response message
  /// This mirrors the backend calculation in realistic_behaviors.py
  static Duration calculateFromMessage(String message, {String? humorStyle, double extraversion = 0.5}) {
    // Extroverted bots type faster
    String personalityType;
    if (extraversion > 0.7) {
      personalityType = 'fast';
    } else if (extraversion > 0.4) {
      personalityType = 'normal';
    } else if (extraversion > 0.2) {
      personalityType = 'slow';
    } else {
      personalityType = 'hesitant';
    }

    final ms = calculateDuration(
      messageLength: message.length,
      personalityType: personalityType,
    );

    return Duration(milliseconds: ms);
  }

  /// Simplified calculation for quick estimates
  /// Uses the formula: baseTime + (charCount * msPerChar) + randomVariation
  static int quickCalculate(int charCount) {
    const int baseTimeMs = 800;      // Base thinking time
    const int msPerChar = 50;        // ~50ms per character
    final int randomVariationMs = _random.nextInt(500) - 250; // ±250ms

    var totalMs = baseTimeMs + (charCount * msPerChar) + randomVariationMs;
    return totalMs.clamp(1000, 30000);
  }
}
