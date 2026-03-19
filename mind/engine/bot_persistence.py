"""
Bot Persistence Layer.

Saves and loads bot mind states and learning states to/from the database.
This ensures bots remember their identity, perceptions, and learnings across restarts.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import (
    async_session_factory, BotMindStateDB, BotLearningStateDB
)
from mind.core.types import BotProfile

logger = logging.getLogger(__name__)


class BotPersistence:
    """Handles saving and loading bot cognitive states."""

    @staticmethod
    def _energy_to_float(energy) -> float:
        """Convert energy string to float."""
        if isinstance(energy, (int, float)):
            return float(energy)
        energy_map = {"low": 0.3, "medium": 0.6, "high": 0.9}
        return energy_map.get(str(energy).lower(), 0.5)

    # ========================================================================
    # MIND STATE PERSISTENCE
    # ========================================================================

    @staticmethod
    async def save_mind_state(bot_id: UUID, mind_data: Dict[str, Any]) -> bool:
        """
        Save a bot's mind state to the database.

        Args:
            bot_id: The bot's UUID
            mind_data: Dictionary containing identity, perceptions, mood, etc.

        Returns:
            True if saved successfully
        """
        try:
            async with async_session_factory() as session:
                # Check if mind state exists
                stmt = select(BotMindStateDB).where(BotMindStateDB.bot_id == bot_id)
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    # Update existing
                    existing.core_values = mind_data.get("core_values", [])
                    existing.beliefs = mind_data.get("beliefs", {})
                    existing.pet_peeves = mind_data.get("pet_peeves", [])
                    existing.current_goals = mind_data.get("current_goals", [])
                    existing.insecurities = mind_data.get("insecurities", [])
                    existing.speech_quirks = mind_data.get("speech_quirks", [])
                    existing.passions = mind_data.get("passions", [])
                    existing.avoided_topics = mind_data.get("avoided_topics", [])
                    existing.social_perceptions = mind_data.get("social_perceptions", {})
                    existing.current_mood = mind_data.get("current_mood", "neutral")
                    existing.current_energy = BotPersistence._energy_to_float(mind_data.get("current_energy", 0.7))
                    existing.inner_monologue = mind_data.get("inner_monologue", [])[-10:]  # Keep last 10
                    existing.updated_at = datetime.utcnow()
                else:
                    # Create new
                    mind_state = BotMindStateDB(
                        bot_id=bot_id,
                        core_values=mind_data.get("core_values", []),
                        beliefs=mind_data.get("beliefs", {}),
                        pet_peeves=mind_data.get("pet_peeves", []),
                        current_goals=mind_data.get("current_goals", []),
                        insecurities=mind_data.get("insecurities", []),
                        speech_quirks=mind_data.get("speech_quirks", []),
                        passions=mind_data.get("passions", []),
                        avoided_topics=mind_data.get("avoided_topics", []),
                        social_perceptions=mind_data.get("social_perceptions", {}),
                        current_mood=mind_data.get("current_mood", "neutral"),
                        current_energy=BotPersistence._energy_to_float(mind_data.get("current_energy", 0.7)),
                        inner_monologue=mind_data.get("inner_monologue", [])[-10:]
                    )
                    session.add(mind_state)

                await session.commit()
                logger.debug(f"Saved mind state for bot {bot_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to save mind state for bot {bot_id}: {e}")
            return False

    @staticmethod
    async def load_mind_state(bot_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Load a bot's mind state from the database.

        Args:
            bot_id: The bot's UUID

        Returns:
            Dictionary with mind state data, or None if not found
        """
        try:
            async with async_session_factory() as session:
                stmt = select(BotMindStateDB).where(BotMindStateDB.bot_id == bot_id)
                result = await session.execute(stmt)
                mind_state = result.scalar_one_or_none()

                if mind_state:
                    return {
                        "core_values": mind_state.core_values,
                        "beliefs": mind_state.beliefs,
                        "pet_peeves": mind_state.pet_peeves,
                        "current_goals": mind_state.current_goals,
                        "insecurities": mind_state.insecurities,
                        "speech_quirks": mind_state.speech_quirks,
                        "passions": mind_state.passions,
                        "avoided_topics": mind_state.avoided_topics,
                        "social_perceptions": mind_state.social_perceptions,
                        "current_mood": mind_state.current_mood,
                        "current_energy": mind_state.current_energy,
                        "inner_monologue": mind_state.inner_monologue
                    }
                return None

        except Exception as e:
            logger.error(f"Failed to load mind state for bot {bot_id}: {e}")
            return None

    # ========================================================================
    # LEARNING STATE PERSISTENCE
    # ========================================================================

    @staticmethod
    async def save_learning_state(bot_id: UUID, learning_data: Dict[str, Any]) -> bool:
        """
        Save a bot's learning state to the database.

        Args:
            bot_id: The bot's UUID
            learning_data: Dictionary containing experiences, topics, beliefs, etc.

        Returns:
            True if saved successfully
        """
        try:
            async with async_session_factory() as session:
                stmt = select(BotLearningStateDB).where(BotLearningStateDB.bot_id == bot_id)
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                # Only keep recent experiences (last 50)
                experiences = learning_data.get("experiences", [])[-50:]

                if existing:
                    existing.experiences = experiences
                    existing.successful_topics = learning_data.get("successful_topics", {})
                    existing.failed_topics = learning_data.get("failed_topics", {})
                    existing.belief_evidence = learning_data.get("belief_evidence", {})
                    existing.emerging_interests = learning_data.get("emerging_interests", [])
                    existing.fading_interests = learning_data.get("fading_interests", [])
                    existing.trait_momentum = learning_data.get("trait_momentum", {})
                    existing.admired_behaviors = learning_data.get("admired_behaviors", [])[-20:]
                    existing.learned_facts_about_others = learning_data.get("learned_facts_about_others", {})
                    existing.adopted_phrases = learning_data.get("adopted_phrases", [])[-10:]
                    existing.communication_preferences = learning_data.get("communication_preferences", {})
                    existing.evolution_count = learning_data.get("evolution_count", 0)
                    existing.last_reflection = learning_data.get("last_reflection")
                    existing.last_evolution = learning_data.get("last_evolution")
                    existing.updated_at = datetime.utcnow()
                else:
                    learning_state = BotLearningStateDB(
                        bot_id=bot_id,
                        experiences=experiences,
                        successful_topics=learning_data.get("successful_topics", {}),
                        failed_topics=learning_data.get("failed_topics", {}),
                        belief_evidence=learning_data.get("belief_evidence", {}),
                        emerging_interests=learning_data.get("emerging_interests", []),
                        fading_interests=learning_data.get("fading_interests", []),
                        trait_momentum=learning_data.get("trait_momentum", {}),
                        admired_behaviors=learning_data.get("admired_behaviors", [])[-20:],
                        learned_facts_about_others=learning_data.get("learned_facts_about_others", {}),
                        adopted_phrases=learning_data.get("adopted_phrases", [])[-10:],
                        communication_preferences=learning_data.get("communication_preferences", {}),
                        evolution_count=learning_data.get("evolution_count", 0),
                        last_reflection=learning_data.get("last_reflection"),
                        last_evolution=learning_data.get("last_evolution")
                    )
                    session.add(learning_state)

                await session.commit()
                logger.debug(f"Saved learning state for bot {bot_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to save learning state for bot {bot_id}: {e}")
            return False

    @staticmethod
    async def load_learning_state(bot_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Load a bot's learning state from the database.

        Args:
            bot_id: The bot's UUID

        Returns:
            Dictionary with learning state data, or None if not found
        """
        try:
            async with async_session_factory() as session:
                stmt = select(BotLearningStateDB).where(BotLearningStateDB.bot_id == bot_id)
                result = await session.execute(stmt)
                learning_state = result.scalar_one_or_none()

                if learning_state:
                    return {
                        "experiences": learning_state.experiences,
                        "successful_topics": learning_state.successful_topics,
                        "failed_topics": learning_state.failed_topics,
                        "belief_evidence": learning_state.belief_evidence,
                        "emerging_interests": learning_state.emerging_interests,
                        "fading_interests": learning_state.fading_interests,
                        "trait_momentum": learning_state.trait_momentum,
                        "admired_behaviors": learning_state.admired_behaviors,
                        "learned_facts_about_others": learning_state.learned_facts_about_others,
                        "adopted_phrases": learning_state.adopted_phrases,
                        "communication_preferences": learning_state.communication_preferences,
                        "evolution_count": learning_state.evolution_count,
                        "last_reflection": learning_state.last_reflection,
                        "last_evolution": learning_state.last_evolution
                    }
                return None

        except Exception as e:
            logger.error(f"Failed to load learning state for bot {bot_id}: {e}")
            return None


# Singleton instance
_persistence: Optional[BotPersistence] = None


def get_persistence() -> BotPersistence:
    """Get the singleton persistence instance."""
    global _persistence
    if _persistence is None:
        _persistence = BotPersistence()
    return _persistence
