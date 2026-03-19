"""
Memory Decay - Realistic memory forgetting and consolidation.

Implements realistic memory dynamics:
- Exponential decay based on time
- Access frequency affects retention
- Important memories decay slower
- Consolidation merges similar old memories
- Low-importance memories can be forgotten
"""

import logging
import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from uuid import UUID

from sqlalchemy import select, delete, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import async_session_factory, MemoryItemDB

logger = logging.getLogger(__name__)


@dataclass
class MemoryDecayConfig:
    """Configuration for memory decay behavior."""
    # Base decay rate (per day)
    base_decay_rate: float = 0.05

    # Importance threshold below which memories can be forgotten
    forget_threshold: float = 0.2

    # Minimum importance for a memory to never be forgotten
    protected_threshold: float = 0.8

    # How much access frequency slows decay
    access_frequency_weight: float = 0.1

    # How much emotional valence affects decay (stronger emotions = slower decay)
    emotional_weight: float = 0.15

    # Maximum age (days) before considering consolidation
    consolidation_age_days: int = 7

    # Similarity threshold for consolidation (0-1)
    consolidation_similarity: float = 0.8


class MemoryDecayManager:
    """
    Manages memory decay, consolidation, and forgetting.

    This makes bot memory more realistic by implementing:
    1. Gradual forgetting of unimportant memories
    2. Strengthening of frequently accessed memories
    3. Consolidation of similar old memories
    """

    def __init__(self, config: Optional[MemoryDecayConfig] = None):
        self.config = config or MemoryDecayConfig()
        self._last_decay_run: Dict[UUID, datetime] = {}

    def calculate_decay_factor(
        self,
        days_since_creation: float,
        importance: float,
        access_count: int,
        emotional_valence: float
    ) -> float:
        """
        Calculate decay factor for a memory.

        Returns a multiplier (0-1) where:
        - 1.0 = no decay (memory fully retained)
        - 0.0 = fully decayed (should be forgotten)
        """
        # Base exponential decay
        base_decay = math.exp(-self.config.base_decay_rate * days_since_creation)

        # Importance protection (high importance = slower decay)
        importance_factor = 0.5 + (importance * 0.5)

        # Access frequency bonus (more access = slower decay)
        access_bonus = min(1.0, access_count * self.config.access_frequency_weight)

        # Emotional intensity protection (strong emotions = slower decay)
        emotion_factor = 1.0 + (abs(emotional_valence) * self.config.emotional_weight)

        # Combine factors
        decay_factor = base_decay * importance_factor * emotion_factor * (1.0 + access_bonus)

        return min(1.0, max(0.0, decay_factor))

    def calculate_importance(
        self,
        memory_content: str,
        original_importance: float,
        access_count: int,
        emotional_valence: float,
        days_old: float
    ) -> float:
        """
        Calculate current effective importance of a memory.

        Importance evolves based on:
        - Original importance
        - How often it's been accessed
        - Emotional significance
        - Age (older unused = less important)
        """
        # Start with original importance
        importance = original_importance

        # Boost for frequent access
        access_boost = min(0.2, access_count * 0.02)
        importance += access_boost

        # Boost for emotional significance
        emotion_boost = abs(emotional_valence) * 0.15
        importance += emotion_boost

        # Decay penalty for old, unused memories
        if access_count == 0 and days_old > 3:
            age_penalty = min(0.3, days_old * 0.02)
            importance -= age_penalty

        # Boost for content with specific characteristics
        content_lower = memory_content.lower()
        if any(word in content_lower for word in ["important", "remember", "significant", "promise", "secret"]):
            importance += 0.1

        return min(1.0, max(0.0, importance))

    async def apply_decay(self, bot_id: UUID) -> Dict[str, int]:
        """
        Apply decay to all memories for a bot.

        Returns statistics about the decay operation.
        """
        stats = {
            "memories_processed": 0,
            "importance_reduced": 0,
            "marked_for_forget": 0,
            "protected": 0
        }

        try:
            async with async_session_factory() as session:
                # Get all memories for this bot
                stmt = select(MemoryItemDB).where(MemoryItemDB.bot_id == bot_id)
                result = await session.execute(stmt)
                memories = result.scalars().all()

                now = datetime.utcnow()

                for memory in memories:
                    stats["memories_processed"] += 1

                    # Calculate days since creation
                    days_old = (now - memory.created_at).total_seconds() / 86400

                    # Calculate decay factor
                    decay_factor = self.calculate_decay_factor(
                        days_since_creation=days_old,
                        importance=memory.importance,
                        access_count=memory.access_count,
                        emotional_valence=memory.emotional_valence
                    )

                    # Apply decay to importance
                    new_importance = memory.importance * decay_factor

                    # Protected memories (very important)
                    if memory.importance >= self.config.protected_threshold:
                        stats["protected"] += 1
                        # Still decay slightly, but maintain minimum
                        new_importance = max(self.config.protected_threshold * 0.9, new_importance)
                    else:
                        # Regular decay
                        if new_importance < memory.importance:
                            stats["importance_reduced"] += 1

                    # Mark very low importance for potential forgetting
                    if new_importance < self.config.forget_threshold:
                        stats["marked_for_forget"] += 1

                    # Update memory
                    memory.importance = new_importance

                await session.commit()

                self._last_decay_run[bot_id] = now
                logger.debug(f"Decay applied for bot {bot_id}: {stats}")

        except Exception as e:
            logger.error(f"Failed to apply decay for bot {bot_id}: {e}")

        return stats

    async def consolidate_memories(
        self,
        bot_id: UUID,
        max_consolidations: int = 10
    ) -> int:
        """
        Consolidate similar old memories into combined memories.

        This simulates how human memory works - old, similar memories
        get merged together into generalized memories.

        Returns number of consolidations performed.
        """
        consolidation_count = 0

        try:
            async with async_session_factory() as session:
                # Get old memories eligible for consolidation
                cutoff_date = datetime.utcnow() - timedelta(days=self.config.consolidation_age_days)

                stmt = (
                    select(MemoryItemDB)
                    .where(
                        and_(
                            MemoryItemDB.bot_id == bot_id,
                            MemoryItemDB.created_at < cutoff_date,
                            MemoryItemDB.importance < self.config.protected_threshold
                        )
                    )
                    .order_by(MemoryItemDB.created_at)
                )

                result = await session.execute(stmt)
                old_memories = result.scalars().all()

                if len(old_memories) < 2:
                    return 0

                # Group by memory type
                by_type: Dict[str, List[MemoryItemDB]] = {}
                for mem in old_memories:
                    if mem.memory_type not in by_type:
                        by_type[mem.memory_type] = []
                    by_type[mem.memory_type].append(mem)

                # Find similar memories within each type
                for mem_type, memories in by_type.items():
                    if len(memories) < 2 or consolidation_count >= max_consolidations:
                        continue

                    # Simple similarity: check for shared words
                    for i, mem1 in enumerate(memories):
                        if consolidation_count >= max_consolidations:
                            break

                        for mem2 in memories[i + 1:]:
                            if consolidation_count >= max_consolidations:
                                break

                            similarity = self._calculate_text_similarity(
                                mem1.content,
                                mem2.content
                            )

                            if similarity >= self.config.consolidation_similarity:
                                # Consolidate: merge into one, delete the other
                                consolidated_content = self._merge_memory_content(
                                    mem1.content,
                                    mem2.content
                                )

                                mem1.content = consolidated_content
                                mem1.importance = max(mem1.importance, mem2.importance)
                                mem1.access_count = mem1.access_count + mem2.access_count
                                mem1.emotional_valence = (
                                    mem1.emotional_valence + mem2.emotional_valence
                                ) / 2

                                # Delete the merged memory
                                await session.delete(mem2)
                                consolidation_count += 1

                                logger.debug(
                                    f"Consolidated memories for bot {bot_id}: "
                                    f"{mem1.content[:50]}..."
                                )

                await session.commit()

        except Exception as e:
            logger.error(f"Failed to consolidate memories for bot {bot_id}: {e}")

        return consolidation_count

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple word-based similarity between two texts."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _merge_memory_content(self, content1: str, content2: str) -> str:
        """Merge two memory contents into a consolidated memory."""
        # Simple merge: take the longer one and note there were multiple instances
        if len(content1) >= len(content2):
            base = content1
        else:
            base = content2

        # Add a note that this is a consolidated memory
        if "(consolidated)" not in base:
            base = f"{base} (consolidated from multiple similar memories)"

        return base

    async def forget_low_importance(
        self,
        bot_id: UUID,
        threshold: float = 0.2,
        max_forget: int = 50
    ) -> int:
        """
        Delete memories below the importance threshold.

        This simulates forgetting - low importance memories that have
        decayed over time are removed from storage.

        Returns number of memories forgotten.
        """
        forgotten_count = 0

        try:
            async with async_session_factory() as session:
                # Find memories below threshold
                stmt = (
                    select(MemoryItemDB)
                    .where(
                        and_(
                            MemoryItemDB.bot_id == bot_id,
                            MemoryItemDB.importance < threshold
                        )
                    )
                    .order_by(MemoryItemDB.importance)
                    .limit(max_forget)
                )

                result = await session.execute(stmt)
                to_forget = result.scalars().all()

                for memory in to_forget:
                    # Additional checks before forgetting
                    days_old = (datetime.utcnow() - memory.created_at).total_seconds() / 86400

                    # Don't forget very recent memories regardless of importance
                    if days_old < 1:
                        continue

                    # Don't forget if accessed recently
                    days_since_access = (datetime.utcnow() - memory.last_accessed).total_seconds() / 86400
                    if days_since_access < 2:
                        continue

                    await session.delete(memory)
                    forgotten_count += 1

                await session.commit()

                if forgotten_count > 0:
                    logger.info(f"Bot {bot_id} forgot {forgotten_count} low-importance memories")

        except Exception as e:
            logger.error(f"Failed to forget memories for bot {bot_id}: {e}")

        return forgotten_count

    async def strengthen_memory(
        self,
        bot_id: UUID,
        memory_id: UUID,
        boost: float = 0.1
    ) -> bool:
        """
        Strengthen a specific memory (when it's accessed/recalled).

        This implements the spacing effect - memories that are
        retrieved become stronger.
        """
        try:
            async with async_session_factory() as session:
                stmt = select(MemoryItemDB).where(
                    and_(
                        MemoryItemDB.id == memory_id,
                        MemoryItemDB.bot_id == bot_id
                    )
                )
                result = await session.execute(stmt)
                memory = result.scalar_one_or_none()

                if memory:
                    memory.importance = min(1.0, memory.importance + boost)
                    memory.access_count += 1
                    memory.last_accessed = datetime.utcnow()
                    await session.commit()
                    return True

        except Exception as e:
            logger.error(f"Failed to strengthen memory {memory_id}: {e}")

        return False

    async def get_decaying_memories(
        self,
        bot_id: UUID,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get memories that are close to being forgotten."""
        try:
            async with async_session_factory() as session:
                stmt = (
                    select(MemoryItemDB)
                    .where(
                        and_(
                            MemoryItemDB.bot_id == bot_id,
                            MemoryItemDB.importance < 0.4,
                            MemoryItemDB.importance > self.config.forget_threshold
                        )
                    )
                    .order_by(MemoryItemDB.importance)
                    .limit(limit)
                )

                result = await session.execute(stmt)
                memories = result.scalars().all()

                return [
                    {
                        "id": str(mem.id),
                        "content": mem.content,
                        "importance": mem.importance,
                        "days_old": (datetime.utcnow() - mem.created_at).days,
                        "access_count": mem.access_count
                    }
                    for mem in memories
                ]

        except Exception as e:
            logger.error(f"Failed to get decaying memories for bot {bot_id}: {e}")
            return []

    def should_run_decay(self, bot_id: UUID, interval_hours: int = 6) -> bool:
        """Check if decay should be run for a bot based on time interval."""
        last_run = self._last_decay_run.get(bot_id)
        if not last_run:
            return True

        hours_since = (datetime.utcnow() - last_run).total_seconds() / 3600
        return hours_since >= interval_hours


# Singleton
_memory_decay_manager: Optional[MemoryDecayManager] = None


def get_memory_decay_manager() -> MemoryDecayManager:
    """Get the singleton memory decay manager."""
    global _memory_decay_manager
    if _memory_decay_manager is None:
        _memory_decay_manager = MemoryDecayManager()
    return _memory_decay_manager
