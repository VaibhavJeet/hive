"""
Hashtag Parser for AI Community Companions.
Extracts, validates, and normalizes hashtags from text.
"""

import re
from typing import List


# Regex pattern to match hashtags
# Matches # followed by alphanumeric characters and underscores
# Does not match hashtags with only numbers
HASHTAG_PATTERN = re.compile(r'#([a-zA-Z_][a-zA-Z0-9_]*)', re.UNICODE)

# Min and max length for hashtags (excluding the # symbol)
MIN_HASHTAG_LENGTH = 2
MAX_HASHTAG_LENGTH = 50


def normalize_hashtag(tag: str) -> str:
    """
    Normalize a hashtag by converting to lowercase and stripping special characters.

    Args:
        tag: The hashtag to normalize (with or without # prefix)

    Returns:
        Normalized hashtag without the # prefix
    """
    # Remove # prefix if present
    if tag.startswith('#'):
        tag = tag[1:]

    # Convert to lowercase
    tag = tag.lower()

    # Strip any leading/trailing underscores
    tag = tag.strip('_')

    # Replace multiple underscores with single underscore
    tag = re.sub(r'_+', '_', tag)

    return tag


def validate_hashtag(tag: str) -> bool:
    """
    Validate a hashtag meets the requirements.

    Requirements:
    - Min 2 characters, max 50 characters (excluding #)
    - No spaces
    - Must contain at least one letter
    - Only alphanumeric characters and underscores allowed

    Args:
        tag: The hashtag to validate (with or without # prefix)

    Returns:
        True if valid, False otherwise
    """
    # Remove # prefix if present
    if tag.startswith('#'):
        tag = tag[1:]

    # Check length
    if len(tag) < MIN_HASHTAG_LENGTH or len(tag) > MAX_HASHTAG_LENGTH:
        return False

    # Check for spaces
    if ' ' in tag:
        return False

    # Must contain at least one letter
    if not any(c.isalpha() for c in tag):
        return False

    # Only alphanumeric and underscores allowed
    if not re.match(r'^[a-zA-Z0-9_]+$', tag):
        return False

    return True


def parse_hashtags(text: str) -> List[str]:
    """
    Extract and parse hashtags from text.

    Extracts all valid hashtags from the given text, normalizes them,
    removes duplicates, and returns a list of unique hashtags.

    Args:
        text: The text to extract hashtags from

    Returns:
        List of normalized, unique, valid hashtags (without # prefix)
    """
    if not text:
        return []

    # Find all potential hashtags
    matches = HASHTAG_PATTERN.findall(text)

    # Process and validate each match
    hashtags = []
    seen = set()

    for match in matches:
        # Normalize the hashtag
        normalized = normalize_hashtag(match)

        # Skip if empty after normalization
        if not normalized:
            continue

        # Skip if already seen
        if normalized in seen:
            continue

        # Validate the hashtag
        if not validate_hashtag(normalized):
            continue

        hashtags.append(normalized)
        seen.add(normalized)

    return hashtags


def extract_hashtags_with_positions(text: str) -> List[dict]:
    """
    Extract hashtags from text along with their positions.

    Useful for highlighting or linking hashtags in the UI.

    Args:
        text: The text to extract hashtags from

    Returns:
        List of dicts with 'tag', 'start', 'end' keys
    """
    if not text:
        return []

    results = []
    seen = set()

    for match in HASHTAG_PATTERN.finditer(text):
        tag = normalize_hashtag(match.group(1))

        if not tag or not validate_hashtag(tag):
            continue

        # Track unique tags but include all positions
        results.append({
            'tag': tag,
            'start': match.start(),
            'end': match.end(),
            'original': match.group(0)
        })
        seen.add(tag)

    return results
