"""
Word Lists for Content Moderation.
Provides pattern matching for profanity, hate speech, and common evasions.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple


class SeverityLevel(Enum):
    """Severity levels for flagged content."""
    LOW = "low"  # Mild language, may warn
    MEDIUM = "medium"  # Offensive content, likely warn
    HIGH = "high"  # Serious violations, likely block
    CRITICAL = "critical"  # Extreme content, always block


@dataclass
class WordMatch:
    """Result of a word match check."""
    matched_word: str
    original_text: str
    category: str
    severity: SeverityLevel
    start_position: int
    end_position: int


class WordListManager:
    """
    Manages word lists for content moderation.
    Handles profanity, hate speech, and leet speak evasions.
    """

    def __init__(self):
        self._profanity_list: Dict[str, SeverityLevel] = {}
        self._hate_speech_list: Dict[str, SeverityLevel] = {}
        self._spam_patterns: List[str] = []
        self._leet_speak_map: Dict[str, List[str]] = {}
        self._compiled_patterns: Dict[str, re.Pattern] = {}

        self._initialize_word_lists()
        self._initialize_leet_speak()
        self._compile_patterns()

    def _initialize_word_lists(self):
        """Initialize word lists with common patterns."""
        # Profanity list with severity levels
        # Note: These are placeholder patterns - in production, use a comprehensive list
        self._profanity_list = {
            # Low severity - mild language
            "damn": SeverityLevel.LOW,
            "hell": SeverityLevel.LOW,
            "crap": SeverityLevel.LOW,
            "suck": SeverityLevel.LOW,
            "darn": SeverityLevel.LOW,

            # Medium severity - offensive language
            "ass": SeverityLevel.MEDIUM,
            "bastard": SeverityLevel.MEDIUM,
            "bitch": SeverityLevel.MEDIUM,
            "piss": SeverityLevel.MEDIUM,

            # High severity - strong profanity (using pattern placeholders)
            "f*ck": SeverityLevel.HIGH,
            "sh*t": SeverityLevel.HIGH,
            "c*nt": SeverityLevel.CRITICAL,
        }

        # Hate speech indicators (patterns)
        self._hate_speech_list = {
            "hate all": SeverityLevel.HIGH,
            "kill all": SeverityLevel.CRITICAL,
            "death to": SeverityLevel.CRITICAL,
            "exterminate": SeverityLevel.HIGH,
            "gas the": SeverityLevel.CRITICAL,
            "genocide": SeverityLevel.HIGH,
        }

        # Spam patterns
        self._spam_patterns = [
            r"(buy|click|subscribe|follow|check out).{0,20}(now|today|link|here)",
            r"(free|win|winner).{0,15}(money|cash|prize|gift)",
            r"https?://\S+\s*(https?://\S+){2,}",  # Multiple links
            r"(.)\1{5,}",  # Repeated characters
            r"(BUY|WIN|FREE|CLICK|SUBSCRIBE){2,}",  # Repeated spam keywords
            r"@\w+\s*(@\w+\s*){4,}",  # Mention spam (5+ mentions)
        ]

    def _initialize_leet_speak(self):
        """Initialize leet speak character substitution map."""
        self._leet_speak_map = {
            "a": ["4", "@", "^", "/\\"],
            "b": ["8", "6", "|3"],
            "c": ["(", "[", "<", "{"],
            "e": ["3", "€", "£"],
            "g": ["9", "6"],
            "h": ["#", "|-|"],
            "i": ["1", "!", "|", "l"],
            "l": ["1", "|", "!", "7"],
            "o": ["0", "()", "[]", "{}"],
            "s": ["5", "$", "z"],
            "t": ["7", "+"],
            "u": ["v", "|_|"],
            "z": ["2"],
        }

    def _compile_patterns(self):
        """Compile regex patterns for efficient matching."""
        # Compile spam patterns
        for i, pattern in enumerate(self._spam_patterns):
            try:
                self._compiled_patterns[f"spam_{i}"] = re.compile(
                    pattern, re.IGNORECASE
                )
            except re.error:
                pass  # Skip invalid patterns

        # Compile hate speech patterns
        for phrase in self._hate_speech_list:
            pattern = self._create_leet_pattern(phrase)
            try:
                self._compiled_patterns[f"hate_{phrase}"] = re.compile(
                    pattern, re.IGNORECASE
                )
            except re.error:
                pass

    def _create_leet_pattern(self, word: str) -> str:
        """Create a regex pattern that matches leet speak variations."""
        pattern_parts = []

        for char in word.lower():
            if char in self._leet_speak_map:
                alternatives = [re.escape(char)] + [
                    re.escape(alt) for alt in self._leet_speak_map[char]
                ]
                pattern_parts.append(f"[{''.join(alternatives)}]")
            elif char == " ":
                # Allow various separators between words
                pattern_parts.append(r"[\s._-]*")
            else:
                pattern_parts.append(re.escape(char))

        return "".join(pattern_parts)

    def normalize_text(self, text: str) -> str:
        """Normalize text by converting leet speak to regular characters."""
        normalized = text.lower()

        # Replace leet speak characters
        for char, replacements in self._leet_speak_map.items():
            for replacement in replacements:
                normalized = normalized.replace(replacement.lower(), char)

        # Remove repeated characters (more than 2)
        normalized = re.sub(r"(.)\1{2,}", r"\1\1", normalized)

        # Remove separators that might be used to evade filters
        normalized = re.sub(r"[\s._-]+", " ", normalized)

        return normalized.strip()

    def check_profanity(self, text: str) -> List[WordMatch]:
        """
        Check text for profanity.

        Args:
            text: The text to check

        Returns:
            List of WordMatch objects for found profanity
        """
        matches = []
        normalized = self.normalize_text(text)
        lower_text = text.lower()

        for word, severity in self._profanity_list.items():
            # Create pattern for the word with leet speak variations
            pattern = self._create_leet_pattern(word)

            try:
                for match in re.finditer(pattern, lower_text):
                    matches.append(WordMatch(
                        matched_word=word,
                        original_text=match.group(),
                        category="profanity",
                        severity=severity,
                        start_position=match.start(),
                        end_position=match.end()
                    ))
            except re.error:
                continue

        # Also check normalized text for hidden words
        for word, severity in self._profanity_list.items():
            if word in normalized and not any(m.matched_word == word for m in matches):
                idx = normalized.find(word)
                matches.append(WordMatch(
                    matched_word=word,
                    original_text=word,
                    category="profanity",
                    severity=severity,
                    start_position=idx,
                    end_position=idx + len(word)
                ))

        return matches

    def check_hate_speech(self, text: str) -> List[WordMatch]:
        """
        Check text for hate speech patterns.

        Args:
            text: The text to check

        Returns:
            List of WordMatch objects for found hate speech
        """
        matches = []

        for phrase, severity in self._hate_speech_list.items():
            pattern_key = f"hate_{phrase}"
            if pattern_key in self._compiled_patterns:
                pattern = self._compiled_patterns[pattern_key]
                for match in pattern.finditer(text):
                    matches.append(WordMatch(
                        matched_word=phrase,
                        original_text=match.group(),
                        category="hate_speech",
                        severity=severity,
                        start_position=match.start(),
                        end_position=match.end()
                    ))

        return matches

    def check_spam_patterns(self, text: str) -> List[Tuple[str, str]]:
        """
        Check text for spam patterns.

        Args:
            text: The text to check

        Returns:
            List of tuples (pattern_name, matched_text)
        """
        matches = []

        for key, pattern in self._compiled_patterns.items():
            if key.startswith("spam_"):
                for match in pattern.finditer(text):
                    matches.append((key, match.group()))

        return matches

    def get_max_severity(self, matches: List[WordMatch]) -> Optional[SeverityLevel]:
        """Get the maximum severity from a list of matches."""
        if not matches:
            return None

        severity_order = [
            SeverityLevel.LOW,
            SeverityLevel.MEDIUM,
            SeverityLevel.HIGH,
            SeverityLevel.CRITICAL
        ]

        max_index = max(severity_order.index(m.severity) for m in matches)
        return severity_order[max_index]

    def add_word(self, word: str, category: str, severity: SeverityLevel):
        """Add a word to the appropriate list."""
        if category == "profanity":
            self._profanity_list[word.lower()] = severity
        elif category == "hate_speech":
            self._hate_speech_list[word.lower()] = severity
            # Recompile pattern for new hate speech
            pattern = self._create_leet_pattern(word)
            try:
                self._compiled_patterns[f"hate_{word}"] = re.compile(
                    pattern, re.IGNORECASE
                )
            except re.error:
                pass

    def remove_word(self, word: str, category: str):
        """Remove a word from the appropriate list."""
        word_lower = word.lower()
        if category == "profanity" and word_lower in self._profanity_list:
            del self._profanity_list[word_lower]
        elif category == "hate_speech" and word_lower in self._hate_speech_list:
            del self._hate_speech_list[word_lower]
            pattern_key = f"hate_{word_lower}"
            if pattern_key in self._compiled_patterns:
                del self._compiled_patterns[pattern_key]


# Singleton instance
_word_list_manager: Optional[WordListManager] = None


def get_word_list_manager() -> WordListManager:
    """Get the singleton word list manager instance."""
    global _word_list_manager
    if _word_list_manager is None:
        _word_list_manager = WordListManager()
    return _word_list_manager
