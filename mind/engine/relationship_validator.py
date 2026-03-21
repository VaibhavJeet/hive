"""
Relationship Validator - Post-generation validation layer to prevent hallucinated relationships.

This module validates LLM-generated responses to ensure they don't reference
relationships or entities that don't exist in the bot's actual relationship records.

Key features:
1. Extract entity mentions (bot names) from generated text
2. Cross-check mentions against actual relationship database
3. Flag hallucinated relationships for regeneration
4. Provide validation context for regeneration prompts
"""

import re
import logging
from typing import Dict, List, Set, Optional, Tuple, TYPE_CHECKING
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import async_session_factory, BotProfileDB, RelationshipDB

if TYPE_CHECKING:
    from mind.core.types import BotProfile

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of relationship validation."""
    is_valid: bool
    hallucinated_names: List[str]
    valid_names: List[str]
    all_mentioned_names: List[str]
    error_message: Optional[str] = None

    def get_regeneration_hint(self) -> str:
        """Generate a hint for regeneration if validation failed."""
        if self.is_valid:
            return ""
        if not self.hallucinated_names:
            return ""
        names_str = ", ".join(self.hallucinated_names)
        return (
            f"\n\nIMPORTANT: Do NOT mention {names_str} - you don't have a relationship with them. "
            f"Only reference people you actually know."
        )


class RelationshipValidator:
    """
    Validates LLM responses to prevent hallucinated relationships.

    Extracts entity mentions from generated text and verifies they exist
    in the bot's actual relationship records in the database.
    """

    # Common words that might be confused with names but shouldn't be flagged
    COMMON_WORDS_TO_IGNORE = {
        "the", "and", "but", "for", "with", "that", "this", "from", "about",
        "just", "like", "what", "when", "where", "who", "how", "why", "which",
        "their", "them", "they", "your", "you", "have", "has", "had", "was",
        "were", "been", "being", "would", "could", "should", "might", "must",
        "will", "can", "may", "shall", "do", "does", "did", "done", "doing",
        "here", "there", "some", "any", "all", "both", "each", "every", "few",
        "more", "most", "other", "such", "than", "then", "very", "even", "also",
        "because", "although", "while", "since", "until", "unless", "though",
        "after", "before", "during", "through", "between", "into", "onto",
        "upon", "within", "without", "against", "among", "around", "behind",
        "below", "beneath", "beside", "beyond", "down", "inside", "near",
        "off", "out", "outside", "over", "past", "through", "under", "up",
        "user", "friend", "someone", "nobody", "everybody", "anybody", "person",
        "people", "everyone", "anyone", "something", "nothing", "everything",
        "anything", "myself", "yourself", "himself", "herself", "itself",
        "ourselves", "yourselves", "themselves", "today", "tomorrow", "yesterday",
        "morning", "afternoon", "evening", "night", "week", "month", "year",
    }

    # Relationship indicator phrases that suggest the text is making claims
    RELATIONSHIP_INDICATORS = [
        r"my friend (\w+)",
        r"(\w+),? my friend",
        r"with (\w+)",
        r"told (\w+)",
        r"(\w+) told me",
        r"(\w+) said",
        r"asked (\w+)",
        r"(\w+) and I",
        r"I and (\w+)",
        r"me and (\w+)",
        r"(\w+) and me",
        r"talking to (\w+)",
        r"(\w+) mentioned",
        r"remember when (\w+)",
        r"(\w+) always",
        r"love (\w+)",
        r"miss (\w+)",
        r"hanging out with (\w+)",
        r"(\w+) thinks",
        r"(\w+) believes",
        r"(\w+) loves",
        r"(\w+) hates",
    ]

    def __init__(self):
        self._bot_name_cache: Dict[str, UUID] = {}  # name -> bot_id
        self._bot_handle_cache: Dict[str, UUID] = {}  # handle -> bot_id
        self._cache_initialized = False

    async def initialize_cache(self, session: Optional[AsyncSession] = None):
        """Initialize the bot name cache from database."""
        async def _init(sess: AsyncSession):
            stmt = select(BotProfileDB.id, BotProfileDB.display_name, BotProfileDB.handle).where(
                BotProfileDB.is_active == True,
                BotProfileDB.is_deleted == False
            )
            result = await sess.execute(stmt)
            rows = result.all()

            for bot_id, display_name, handle in rows:
                # Cache display name (lowercase for matching)
                name_lower = display_name.lower().strip()
                self._bot_name_cache[name_lower] = bot_id

                # Also cache first name only
                first_name = name_lower.split()[0] if name_lower else ""
                if first_name and len(first_name) > 2:
                    self._bot_name_cache[first_name] = bot_id

                # Cache handle (without @)
                handle_clean = handle.lower().strip().lstrip("@")
                self._bot_handle_cache[handle_clean] = bot_id

            self._cache_initialized = True
            logger.debug(f"[VALIDATOR] Cached {len(rows)} bot names")

        if session:
            await _init(session)
        else:
            async with async_session_factory() as sess:
                await _init(sess)

    def extract_potential_names(self, text: str) -> Set[str]:
        """
        Extract potential bot names from text.

        Uses multiple strategies:
        1. Capitalized words that might be names
        2. Words following relationship indicators
        3. @mentions

        Returns a set of potential names (lowercase) to check.
        """
        potential_names: Set[str] = set()

        # Strategy 1: Find @mentions (handles)
        mentions = re.findall(r"@(\w+)", text)
        for mention in mentions:
            potential_names.add(mention.lower())

        # Strategy 2: Find capitalized words that might be names
        # Look for words that are capitalized but not at start of sentence
        words = text.split()
        for i, word in enumerate(words):
            # Clean the word
            clean_word = re.sub(r"[^\w]", "", word)
            if not clean_word:
                continue

            # Check if it's capitalized (possible name)
            if clean_word[0].isupper() and clean_word.lower() not in self.COMMON_WORDS_TO_IGNORE:
                # Skip if it's at the start of a sentence (after . ! ?)
                if i > 0:
                    prev_word = words[i-1]
                    if not prev_word.endswith((".", "!", "?", ":", "\n")):
                        potential_names.add(clean_word.lower())
                elif i == 0 and len(clean_word) > 2:
                    # First word might still be a name if it's unusual
                    potential_names.add(clean_word.lower())

        # Strategy 3: Extract names from relationship indicator patterns
        text_lower = text.lower()
        for pattern in self.RELATIONSHIP_INDICATORS:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    for m in match:
                        if m and m.lower() not in self.COMMON_WORDS_TO_IGNORE:
                            potential_names.add(m.lower())
                elif match and match.lower() not in self.COMMON_WORDS_TO_IGNORE:
                    potential_names.add(match.lower())

        # Filter out common words
        potential_names = {
            name for name in potential_names
            if name.lower() not in self.COMMON_WORDS_TO_IGNORE
            and len(name) > 1
        }

        return potential_names

    async def get_bot_relationships(
        self,
        bot_id: UUID,
        session: Optional[AsyncSession] = None
    ) -> Set[UUID]:
        """Get all bot IDs that have a relationship with the given bot."""
        async def _get(sess: AsyncSession) -> Set[UUID]:
            # Get relationships where this bot is the source
            stmt = select(RelationshipDB.target_id).where(
                RelationshipDB.source_id == bot_id,
                RelationshipDB.interaction_count > 0  # Must have had actual interactions
            )
            result = await sess.execute(stmt)
            target_ids = {row[0] for row in result.all()}

            # Also get relationships where this bot is the target (bidirectional)
            stmt2 = select(RelationshipDB.source_id).where(
                RelationshipDB.target_id == bot_id,
                RelationshipDB.interaction_count > 0
            )
            result2 = await sess.execute(stmt2)
            source_ids = {row[0] for row in result2.all()}

            return target_ids | source_ids

        if session:
            return await _get(session)
        else:
            async with async_session_factory() as sess:
                return await _get(sess)

    async def get_known_bot_names(
        self,
        bot_id: UUID,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, UUID]:
        """
        Get mapping of names -> bot_ids for bots that this bot knows.

        Returns names (lowercase) that are valid to mention.
        """
        async def _get(sess: AsyncSession) -> Dict[str, UUID]:
            relationship_ids = await self.get_bot_relationships(bot_id, sess)

            if not relationship_ids:
                return {}

            # Get the names of these bots
            stmt = select(
                BotProfileDB.id, BotProfileDB.display_name, BotProfileDB.handle
            ).where(BotProfileDB.id.in_(relationship_ids))
            result = await sess.execute(stmt)
            rows = result.all()

            known_names: Dict[str, UUID] = {}
            for related_id, display_name, handle in rows:
                # Add display name
                name_lower = display_name.lower().strip()
                known_names[name_lower] = related_id

                # Add first name
                first_name = name_lower.split()[0] if name_lower else ""
                if first_name and len(first_name) > 2:
                    known_names[first_name] = related_id

                # Add handle
                handle_clean = handle.lower().strip().lstrip("@")
                known_names[handle_clean] = related_id

            return known_names

        if session:
            return await _get(session)
        else:
            async with async_session_factory() as sess:
                return await _get(sess)

    def name_to_bot_id(self, name: str) -> Optional[UUID]:
        """
        Look up a potential bot ID from a name using the cache.

        Returns None if the name doesn't match any known bot.
        """
        name_lower = name.lower().strip()

        # Check display name cache
        if name_lower in self._bot_name_cache:
            return self._bot_name_cache[name_lower]

        # Check handle cache
        if name_lower in self._bot_handle_cache:
            return self._bot_handle_cache[name_lower]

        return None

    async def validate_response(
        self,
        bot_id: UUID,
        response_text: str,
        session: Optional[AsyncSession] = None
    ) -> ValidationResult:
        """
        Validate an LLM-generated response for hallucinated relationships.

        Args:
            bot_id: The bot that generated this response
            response_text: The generated response text
            session: Optional database session

        Returns:
            ValidationResult with validity status and details
        """
        # Ensure cache is initialized
        if not self._cache_initialized:
            await self.initialize_cache(session)

        # Extract potential names from the response
        potential_names = self.extract_potential_names(response_text)

        if not potential_names:
            # No names mentioned, valid by default
            return ValidationResult(
                is_valid=True,
                hallucinated_names=[],
                valid_names=[],
                all_mentioned_names=[]
            )

        # Get names this bot actually knows
        known_names = await self.get_known_bot_names(bot_id, session)

        # Check each potential name
        hallucinated: List[str] = []
        valid: List[str] = []

        for name in potential_names:
            # Check if this name is a known bot
            matched_bot_id = self.name_to_bot_id(name)

            if matched_bot_id is None:
                # Not a bot name, ignore (could be referring to a human, place, etc.)
                continue

            # It's a bot name - check if the bot actually knows them
            if name in known_names:
                valid.append(name)
            else:
                hallucinated.append(name)

        is_valid = len(hallucinated) == 0

        if not is_valid:
            logger.warning(
                f"[VALIDATOR] Bot {bot_id} hallucinated relationships with: {hallucinated}"
            )

        return ValidationResult(
            is_valid=is_valid,
            hallucinated_names=hallucinated,
            valid_names=valid,
            all_mentioned_names=list(potential_names)
        )

    async def validate_and_suggest(
        self,
        bot_id: UUID,
        response_text: str,
        bot_profile: Optional["BotProfile"] = None,
        session: Optional[AsyncSession] = None
    ) -> Tuple[ValidationResult, str]:
        """
        Validate response and provide a regeneration hint if invalid.

        Returns:
            Tuple of (ValidationResult, regeneration_hint)
        """
        result = await self.validate_response(bot_id, response_text, session)

        if result.is_valid:
            return result, ""

        # Build regeneration hint
        hint = result.get_regeneration_hint()

        # If we have known valid names, suggest them
        if result.valid_names:
            valid_str = ", ".join(result.valid_names[:3])
            hint += f" You can mention: {valid_str}."

        return result, hint


# Singleton instance
_validator: Optional[RelationshipValidator] = None


def get_relationship_validator() -> RelationshipValidator:
    """Get or create the singleton relationship validator."""
    global _validator
    if _validator is None:
        _validator = RelationshipValidator()
    return _validator


async def validate_generated_response(
    bot_id: UUID,
    response_text: str,
    session: Optional[AsyncSession] = None
) -> ValidationResult:
    """
    Convenience function to validate a generated response.

    Usage:
        result = await validate_generated_response(bot_id, response_text)
        if not result.is_valid:
            # Regenerate with hint
            hint = result.get_regeneration_hint()
    """
    validator = get_relationship_validator()
    return await validator.validate_response(bot_id, response_text, session)
