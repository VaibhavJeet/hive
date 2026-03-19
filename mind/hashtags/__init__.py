"""
Hashtag System for AI Community Companions.
Provides hashtag parsing, trending analysis, and following functionality.
"""

from mind.hashtags.hashtag_parser import parse_hashtags, validate_hashtag, normalize_hashtag
from mind.hashtags.hashtag_service import HashtagService, TrendingHashtag

__all__ = [
    "parse_hashtags",
    "validate_hashtag",
    "normalize_hashtag",
    "HashtagService",
    "TrendingHashtag",
]
