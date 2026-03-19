"""
Spam Detection for Content Moderation.
Detects repetition, excessive caps, link spam, mention spam, and rate-based patterns.
"""

import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID


@dataclass
class SpamResult:
    """Result of spam detection check."""
    is_spam: bool
    spam_score: float  # 0.0 to 1.0
    flags: List[str] = field(default_factory=list)
    details: Dict[str, any] = field(default_factory=dict)


@dataclass
class UserRateInfo:
    """Tracks user posting rate."""
    timestamps: List[float] = field(default_factory=list)
    recent_content_hashes: List[int] = field(default_factory=list)
    warning_count: int = 0
    last_warning: Optional[float] = None


class SpamDetector:
    """
    Detects spam patterns in content and user behavior.

    Checks for:
    - Text repetition
    - Excessive capitalization
    - Link spam
    - Mention spam
    - Rate-based detection
    - Duplicate content
    """

    def __init__(
        self,
        max_caps_ratio: float = 0.5,
        max_links: int = 3,
        max_mentions: int = 5,
        max_posts_per_minute: int = 5,
        max_repetition_ratio: float = 0.3,
        duplicate_window_seconds: int = 300
    ):
        self.max_caps_ratio = max_caps_ratio
        self.max_links = max_links
        self.max_mentions = max_mentions
        self.max_posts_per_minute = max_posts_per_minute
        self.max_repetition_ratio = max_repetition_ratio
        self.duplicate_window_seconds = duplicate_window_seconds

        # Track user rates
        self._user_rates: Dict[str, UserRateInfo] = defaultdict(UserRateInfo)

        # Compiled patterns
        self._url_pattern = re.compile(
            r"https?://\S+|www\.\S+|[\w-]+\.(?:com|org|net|io|co|app|xyz)\S*",
            re.IGNORECASE
        )
        self._mention_pattern = re.compile(r"@\w+")
        self._repeated_char_pattern = re.compile(r"(.)\1{4,}")
        self._repeated_word_pattern = re.compile(r"\b(\w+)\b(?:\s+\1\b){2,}", re.IGNORECASE)

    def detect_spam(
        self,
        text: str,
        user_id: Optional[UUID] = None,
        check_rate: bool = True
    ) -> SpamResult:
        """
        Detect spam in text content.

        Args:
            text: The content to check
            user_id: Optional user ID for rate limiting
            check_rate: Whether to check posting rate

        Returns:
            SpamResult with spam detection details
        """
        flags = []
        details = {}
        spam_score = 0.0

        # 1. Check excessive capitalization
        caps_result = self._check_caps(text)
        if caps_result["is_excessive"]:
            flags.append("excessive_caps")
            spam_score += 0.2
            details["caps_ratio"] = caps_result["ratio"]

        # 2. Check link spam
        link_result = self._check_links(text)
        if link_result["is_spam"]:
            flags.append("link_spam")
            spam_score += 0.3
            details["link_count"] = link_result["count"]
            details["links"] = link_result["links"]

        # 3. Check mention spam
        mention_result = self._check_mentions(text)
        if mention_result["is_spam"]:
            flags.append("mention_spam")
            spam_score += 0.3
            details["mention_count"] = mention_result["count"]

        # 4. Check repetition
        repetition_result = self._check_repetition(text)
        if repetition_result["is_repetitive"]:
            flags.append("repetition")
            spam_score += 0.25
            details["repetition"] = repetition_result

        # 5. Check posting rate (if user_id provided)
        if check_rate and user_id:
            rate_result = self._check_rate(str(user_id), text)
            if rate_result["is_rate_limited"]:
                flags.append("rate_limited")
                spam_score += 0.4
                details["rate"] = rate_result
            if rate_result["is_duplicate"]:
                flags.append("duplicate_content")
                spam_score += 0.35
                details["duplicate"] = True

        # 6. Check for common spam phrases
        phrase_result = self._check_spam_phrases(text)
        if phrase_result["has_spam_phrases"]:
            flags.append("spam_phrases")
            spam_score += 0.2 * len(phrase_result["matched"])
            details["spam_phrases"] = phrase_result["matched"]

        # Cap score at 1.0
        spam_score = min(spam_score, 1.0)

        # Consider it spam if score is above threshold
        is_spam = spam_score >= 0.5 or "rate_limited" in flags

        return SpamResult(
            is_spam=is_spam,
            spam_score=spam_score,
            flags=flags,
            details=details
        )

    def _check_caps(self, text: str) -> Dict:
        """Check for excessive capitalization."""
        if len(text) < 10:
            return {"is_excessive": False, "ratio": 0.0}

        alpha_chars = [c for c in text if c.isalpha()]
        if not alpha_chars:
            return {"is_excessive": False, "ratio": 0.0}

        upper_count = sum(1 for c in alpha_chars if c.isupper())
        ratio = upper_count / len(alpha_chars)

        return {
            "is_excessive": ratio > self.max_caps_ratio,
            "ratio": round(ratio, 2)
        }

    def _check_links(self, text: str) -> Dict:
        """Check for link spam."""
        links = self._url_pattern.findall(text)
        is_spam = len(links) > self.max_links

        return {
            "is_spam": is_spam,
            "count": len(links),
            "links": links[:5]  # Only show first 5
        }

    def _check_mentions(self, text: str) -> Dict:
        """Check for mention spam."""
        mentions = self._mention_pattern.findall(text)
        is_spam = len(mentions) > self.max_mentions

        return {
            "is_spam": is_spam,
            "count": len(mentions),
            "mentions": mentions[:5]
        }

    def _check_repetition(self, text: str) -> Dict:
        """Check for repetitive content."""
        result = {
            "is_repetitive": False,
            "repeated_chars": [],
            "repeated_words": []
        }

        # Check repeated characters (e.g., "heeeeelp")
        repeated_chars = self._repeated_char_pattern.findall(text)
        if repeated_chars:
            result["repeated_chars"] = repeated_chars

        # Check repeated words (e.g., "buy buy buy")
        repeated_words = self._repeated_word_pattern.findall(text)
        if repeated_words:
            result["repeated_words"] = repeated_words

        # Check overall word repetition ratio
        words = text.lower().split()
        if len(words) >= 5:
            unique_words = set(words)
            repetition_ratio = 1 - (len(unique_words) / len(words))
            if repetition_ratio > self.max_repetition_ratio:
                result["is_repetitive"] = True
                result["repetition_ratio"] = round(repetition_ratio, 2)

        # Mark as repetitive if we found patterns
        if result["repeated_chars"] or result["repeated_words"]:
            result["is_repetitive"] = True

        return result

    def _check_rate(self, user_id: str, text: str) -> Dict:
        """Check posting rate and duplicate content."""
        now = time.time()
        user_info = self._user_rates[user_id]

        # Clean up old timestamps (older than 1 minute)
        user_info.timestamps = [
            t for t in user_info.timestamps
            if now - t < 60
        ]

        # Clean up old content hashes (older than duplicate window)
        # Keep last 20 hashes
        user_info.recent_content_hashes = user_info.recent_content_hashes[-20:]

        # Check rate limit
        posts_in_minute = len(user_info.timestamps)
        is_rate_limited = posts_in_minute >= self.max_posts_per_minute

        # Check for duplicate content
        content_hash = hash(text.lower().strip())
        is_duplicate = content_hash in user_info.recent_content_hashes

        # Record this post
        user_info.timestamps.append(now)
        user_info.recent_content_hashes.append(content_hash)

        # Increment warning count if spam detected
        if is_rate_limited or is_duplicate:
            user_info.warning_count += 1
            user_info.last_warning = now

        return {
            "is_rate_limited": is_rate_limited,
            "posts_in_minute": posts_in_minute,
            "is_duplicate": is_duplicate,
            "warning_count": user_info.warning_count
        }

    def _check_spam_phrases(self, text: str) -> Dict:
        """Check for common spam phrases."""
        spam_phrases = [
            r"follow\s+for\s+follow",
            r"like\s+for\s+like",
            r"dm\s+me\s+for",
            r"earn\s+money\s+from\s+home",
            r"click\s+(the\s+)?link\s+in\s+(my\s+)?bio",
            r"free\s+followers",
            r"guaranteed\s+(returns|profits)",
            r"make\s+\$?\d+\s+(per|a)\s+(day|hour|week)",
            r"limited\s+time\s+offer",
            r"act\s+now",
            r"100%\s+free",
            r"no\s+credit\s+card\s+(needed|required)",
        ]

        matched = []
        text_lower = text.lower()

        for phrase in spam_phrases:
            if re.search(phrase, text_lower):
                matched.append(phrase)

        return {
            "has_spam_phrases": len(matched) > 0,
            "matched": matched
        }

    def get_user_status(self, user_id: UUID) -> Dict:
        """Get spam status for a user."""
        user_info = self._user_rates.get(str(user_id))
        if not user_info:
            return {
                "warning_count": 0,
                "is_restricted": False,
                "posts_in_last_minute": 0
            }

        now = time.time()
        recent_posts = len([t for t in user_info.timestamps if now - t < 60])

        return {
            "warning_count": user_info.warning_count,
            "is_restricted": user_info.warning_count >= 5,
            "posts_in_last_minute": recent_posts,
            "last_warning": user_info.last_warning
        }

    def reset_user_warnings(self, user_id: UUID):
        """Reset warnings for a user (admin action)."""
        user_id_str = str(user_id)
        if user_id_str in self._user_rates:
            self._user_rates[user_id_str].warning_count = 0
            self._user_rates[user_id_str].last_warning = None

    def cleanup_old_data(self, max_age_seconds: int = 3600):
        """Clean up old user rate data."""
        now = time.time()
        to_remove = []

        for user_id, info in self._user_rates.items():
            # Remove if no activity in max_age_seconds
            if info.timestamps and now - max(info.timestamps) > max_age_seconds:
                to_remove.append(user_id)
            elif not info.timestamps:
                to_remove.append(user_id)

        for user_id in to_remove:
            del self._user_rates[user_id]


# Singleton instance
_spam_detector: Optional[SpamDetector] = None


def get_spam_detector() -> SpamDetector:
    """Get the singleton spam detector instance."""
    global _spam_detector
    if _spam_detector is None:
        _spam_detector = SpamDetector()
    return _spam_detector
