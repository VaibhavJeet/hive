"""
Content Filter for Moderation.
Main interface for checking text and images for policy violations.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
from uuid import UUID

from mind.moderation.word_lists import (
    WordListManager,
    get_word_list_manager,
    SeverityLevel,
    WordMatch
)
from mind.moderation.spam_detector import (
    SpamDetector,
    SpamResult,
    get_spam_detector
)


class SuggestedAction(Enum):
    """Suggested moderation action."""
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"
    REVIEW = "review"  # Flag for human review


@dataclass
class ModerationResult:
    """Result of content moderation check."""
    is_safe: bool
    flags: List[str] = field(default_factory=list)
    confidence: float = 1.0
    suggested_action: SuggestedAction = SuggestedAction.ALLOW
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "is_safe": self.is_safe,
            "flags": self.flags,
            "confidence": self.confidence,
            "suggested_action": self.suggested_action.value,
            "details": self.details
        }


class ContentFilter:
    """
    Main content filter for text and image moderation.

    Uses word lists and spam detection for text,
    with placeholder for AI-based moderation.
    """

    def __init__(
        self,
        word_list_manager: Optional[WordListManager] = None,
        spam_detector: Optional[SpamDetector] = None,
        enable_ai_moderation: bool = False
    ):
        self.word_list_manager = word_list_manager or get_word_list_manager()
        self.spam_detector = spam_detector or get_spam_detector()
        self.enable_ai_moderation = enable_ai_moderation

    def check_text(
        self,
        text: str,
        user_id: Optional[UUID] = None,
        context: Optional[dict] = None
    ) -> ModerationResult:
        """
        Check text content for policy violations.

        Args:
            text: The text content to check
            user_id: Optional user ID for rate limiting
            context: Optional context (community, content type, etc.)

        Returns:
            ModerationResult with safety assessment
        """
        if not text or not text.strip():
            return ModerationResult(
                is_safe=True,
                confidence=1.0,
                suggested_action=SuggestedAction.ALLOW
            )

        flags = []
        details = {}
        max_severity = None

        # 1. Check profanity
        profanity_matches = self.word_list_manager.check_profanity(text)
        if profanity_matches:
            flags.append("profanity")
            details["profanity_matches"] = [
                {
                    "word": m.matched_word,
                    "severity": m.severity.value,
                    "position": m.start_position
                }
                for m in profanity_matches
            ]
            max_severity = self.word_list_manager.get_max_severity(profanity_matches)

        # 2. Check hate speech
        hate_matches = self.word_list_manager.check_hate_speech(text)
        if hate_matches:
            flags.append("hate_speech")
            details["hate_speech_matches"] = [
                {
                    "phrase": m.matched_word,
                    "severity": m.severity.value,
                    "position": m.start_position
                }
                for m in hate_matches
            ]
            hate_severity = self.word_list_manager.get_max_severity(hate_matches)
            if max_severity is None or self._compare_severity(hate_severity, max_severity) > 0:
                max_severity = hate_severity

        # 3. Check spam
        spam_result = self.spam_detector.detect_spam(text, user_id)
        if spam_result.is_spam or spam_result.flags:
            for flag in spam_result.flags:
                if flag not in flags:
                    flags.append(flag)
            details["spam"] = {
                "score": spam_result.spam_score,
                "flags": spam_result.flags,
                "details": spam_result.details
            }

        # 4. Check word list spam patterns
        spam_patterns = self.word_list_manager.check_spam_patterns(text)
        if spam_patterns:
            if "spam_patterns" not in flags:
                flags.append("spam_patterns")
            details["matched_patterns"] = [pattern for pattern, _ in spam_patterns]

        # 5. Placeholder for AI-based moderation
        if self.enable_ai_moderation:
            ai_result = self._ai_moderation_check(text, context)
            if ai_result.get("flags"):
                for flag in ai_result["flags"]:
                    if flag not in flags:
                        flags.append(flag)
                details["ai_moderation"] = ai_result

        # Determine suggested action based on findings
        suggested_action = self._determine_action(flags, max_severity, spam_result)

        # Calculate confidence
        confidence = self._calculate_confidence(flags, max_severity, spam_result)

        # Determine if safe
        is_safe = suggested_action == SuggestedAction.ALLOW

        return ModerationResult(
            is_safe=is_safe,
            flags=flags,
            confidence=confidence,
            suggested_action=suggested_action,
            details=details
        )

    def check_image(self, image_url: str) -> ModerationResult:
        """
        Check image content for policy violations.

        Placeholder implementation - would integrate with image moderation API.

        Args:
            image_url: URL of the image to check

        Returns:
            ModerationResult with safety assessment
        """
        # Placeholder: Always allow images for now
        # In production, integrate with:
        # - Google Cloud Vision SafeSearch
        # - AWS Rekognition Content Moderation
        # - Azure Content Moderator
        # - Custom ML model

        return ModerationResult(
            is_safe=True,
            flags=[],
            confidence=0.5,  # Low confidence since not actually checked
            suggested_action=SuggestedAction.ALLOW,
            details={
                "note": "Image moderation not yet implemented",
                "image_url": image_url
            }
        )

    def _ai_moderation_check(self, text: str, context: Optional[dict]) -> dict:
        """
        Placeholder for AI-based moderation.

        Would integrate with:
        - OpenAI Moderation API
        - Perspective API
        - Custom trained models

        Args:
            text: The text to check
            context: Optional context

        Returns:
            Dictionary with AI moderation results
        """
        # Placeholder implementation
        return {
            "checked": False,
            "note": "AI moderation not yet implemented",
            "flags": []
        }

    def _compare_severity(
        self,
        a: Optional[SeverityLevel],
        b: Optional[SeverityLevel]
    ) -> int:
        """Compare two severity levels. Returns >0 if a > b."""
        if a is None:
            return -1 if b else 0
        if b is None:
            return 1

        order = [
            SeverityLevel.LOW,
            SeverityLevel.MEDIUM,
            SeverityLevel.HIGH,
            SeverityLevel.CRITICAL
        ]
        return order.index(a) - order.index(b)

    def _determine_action(
        self,
        flags: List[str],
        max_severity: Optional[SeverityLevel],
        spam_result: SpamResult
    ) -> SuggestedAction:
        """Determine the suggested action based on findings."""
        # Critical severity always blocks
        if max_severity == SeverityLevel.CRITICAL:
            return SuggestedAction.BLOCK

        # Hate speech always blocks
        if "hate_speech" in flags:
            return SuggestedAction.BLOCK

        # High severity blocks
        if max_severity == SeverityLevel.HIGH:
            return SuggestedAction.BLOCK

        # Rate limited or duplicate blocks
        if "rate_limited" in flags or "duplicate_content" in flags:
            return SuggestedAction.BLOCK

        # High spam score blocks
        if spam_result.spam_score >= 0.7:
            return SuggestedAction.BLOCK

        # Medium severity warns
        if max_severity == SeverityLevel.MEDIUM:
            return SuggestedAction.WARN

        # Moderate spam score warns
        if spam_result.spam_score >= 0.4:
            return SuggestedAction.WARN

        # Low severity or minor flags just warn
        if flags and max_severity == SeverityLevel.LOW:
            return SuggestedAction.WARN

        # Some spam flags warrant review
        if flags and any(f in ["link_spam", "mention_spam"] for f in flags):
            return SuggestedAction.REVIEW

        return SuggestedAction.ALLOW

    def _calculate_confidence(
        self,
        flags: List[str],
        max_severity: Optional[SeverityLevel],
        spam_result: SpamResult
    ) -> float:
        """Calculate confidence in the moderation decision."""
        if not flags:
            return 1.0

        # Start with high confidence
        confidence = 0.9

        # Reduce confidence for pattern-based detection (may have false positives)
        if "profanity" in flags:
            confidence -= 0.1

        if "spam_patterns" in flags:
            confidence -= 0.15

        # Spam detection is fairly reliable
        if spam_result.is_spam:
            confidence += 0.05

        # Hate speech detection is reliable but serious
        if "hate_speech" in flags:
            confidence = max(confidence, 0.85)

        # Critical severity is very confident
        if max_severity == SeverityLevel.CRITICAL:
            confidence = 0.95

        return max(0.5, min(1.0, confidence))


# Singleton instance
_content_filter: Optional[ContentFilter] = None


def get_content_filter() -> ContentFilter:
    """Get the singleton content filter instance."""
    global _content_filter
    if _content_filter is None:
        _content_filter = ContentFilter()
    return _content_filter
