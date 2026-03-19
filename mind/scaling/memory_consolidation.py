"""
Memory Consolidation Manager for AI Community Companions.

Handles consolidation, summarization, and archival of bot memories
to manage storage and maintain performance.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID, uuid4
from dataclasses import dataclass, field

from sqlalchemy import select, delete, update, and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import (
    async_session_factory,
    MemoryItemDB,
    BotProfileDB,
)


logger = logging.getLogger(__name__)


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class MemoryStats:
    """Statistics about a bot's memories."""
    bot_id: UUID
    total_memories: int
    active_memories: int
    archived_memories: int
    size_bytes: int
    oldest_memory: Optional[datetime]
    newest_memory: Optional[datetime]
    memory_types: Dict[str, int]
    avg_importance: float
    consolidation_candidates: int
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "bot_id": str(self.bot_id),
            "total_memories": self.total_memories,
            "active_memories": self.active_memories,
            "archived_memories": self.archived_memories,
            "size_bytes": self.size_bytes,
            "oldest_memory": self.oldest_memory.isoformat() if self.oldest_memory else None,
            "newest_memory": self.newest_memory.isoformat() if self.newest_memory else None,
            "memory_types": self.memory_types,
            "avg_importance": self.avg_importance,
            "consolidation_candidates": self.consolidation_candidates,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ConsolidationResult:
    """Result of a memory consolidation operation."""
    bot_id: UUID
    memories_processed: int
    memories_merged: int
    memories_summarized: int
    memories_archived: int
    storage_saved_bytes: int
    new_summaries: List[str]


@dataclass
class MemorySummary:
    """A summary of consolidated memories."""
    id: UUID
    bot_id: UUID
    summary_content: str
    source_memory_ids: List[UUID]
    time_range_start: datetime
    time_range_end: datetime
    importance: float
    created_at: datetime = field(default_factory=datetime.utcnow)


# ============================================================================
# MEMORY CONSOLIDATION MANAGER
# ============================================================================

class MemoryConsolidationManager:
    """
    Manages memory consolidation for bots.

    Responsibilities:
    - Merge similar memories
    - Summarize old memories
    - Archive infrequently accessed memories
    - Track memory statistics
    """

    def __init__(
        self,
        similarity_threshold: float = 0.85,
        summarize_after_days: int = 30,
        archive_after_days: int = 90,
        max_memories_per_bot: int = 1000
    ):
        """
        Initialize the consolidation manager.

        Args:
            similarity_threshold: Threshold for merging similar memories
            summarize_after_days: Days before memories are summarized
            archive_after_days: Days before memories are archived
            max_memories_per_bot: Maximum memories per bot before forced consolidation
        """
        self.similarity_threshold = similarity_threshold
        self.summarize_after_days = summarize_after_days
        self.archive_after_days = archive_after_days
        self.max_memories_per_bot = max_memories_per_bot

    async def consolidate_bot_memories(
        self,
        bot_id: UUID,
        session: Optional[AsyncSession] = None
    ) -> ConsolidationResult:
        """
        Consolidate memories for a bot.

        This operation:
        1. Finds similar memories and merges them
        2. Creates summaries of related memories
        3. Removes redundant information

        Args:
            bot_id: The bot whose memories to consolidate
            session: Optional database session

        Returns:
            ConsolidationResult with details of the operation
        """
        async def _consolidate(sess: AsyncSession) -> ConsolidationResult:
            # Get all active memories for the bot
            stmt = (
                select(MemoryItemDB)
                .where(MemoryItemDB.bot_id == bot_id)
                .order_by(MemoryItemDB.created_at.desc())
            )
            result = await sess.execute(stmt)
            memories = result.scalars().all()

            if len(memories) < 10:
                return ConsolidationResult(
                    bot_id=bot_id,
                    memories_processed=0,
                    memories_merged=0,
                    memories_summarized=0,
                    memories_archived=0,
                    storage_saved_bytes=0,
                    new_summaries=[]
                )

            memories_merged = 0
            storage_saved = 0
            new_summaries = []

            # Group memories by type
            type_groups: Dict[str, List[MemoryItemDB]] = {}
            for memory in memories:
                if memory.memory_type not in type_groups:
                    type_groups[memory.memory_type] = []
                type_groups[memory.memory_type].append(memory)

            # Merge similar memories within each group
            for memory_type, group_memories in type_groups.items():
                if len(group_memories) < 5:
                    continue

                # Find similar memories using content comparison
                merged_ids = set()

                for i, mem1 in enumerate(group_memories):
                    if mem1.id in merged_ids:
                        continue

                    similar = [mem1]

                    for mem2 in group_memories[i + 1:]:
                        if mem2.id in merged_ids:
                            continue

                        # Simple content similarity check
                        if self._are_similar(mem1.content, mem2.content):
                            similar.append(mem2)
                            merged_ids.add(mem2.id)

                    if len(similar) > 1:
                        # Merge the memories
                        merged_content = self._merge_contents([m.content for m in similar])
                        merged_importance = max(m.importance for m in similar)

                        # Update the first memory with merged content
                        mem1.content = merged_content
                        mem1.importance = merged_importance
                        mem1.access_count = sum(m.access_count for m in similar)

                        # Delete the other memories
                        for mem in similar[1:]:
                            storage_saved += len(mem.content.encode('utf-8'))
                            await sess.delete(mem)
                            memories_merged += 1

                        new_summaries.append(f"Merged {len(similar)} {memory_type} memories")

            await sess.commit()

            return ConsolidationResult(
                bot_id=bot_id,
                memories_processed=len(memories),
                memories_merged=memories_merged,
                memories_summarized=0,
                memories_archived=0,
                storage_saved_bytes=storage_saved,
                new_summaries=new_summaries
            )

        if session:
            return await _consolidate(session)
        else:
            async with async_session_factory() as sess:
                return await _consolidate(sess)

    def _are_similar(self, content1: str, content2: str) -> bool:
        """
        Check if two memory contents are similar.

        Uses a simple word overlap similarity measure.
        """
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())

        if not words1 or not words2:
            return False

        intersection = words1 & words2
        union = words1 | words2

        jaccard = len(intersection) / len(union)
        return jaccard >= self.similarity_threshold

    def _merge_contents(self, contents: List[str]) -> str:
        """Merge multiple memory contents into one."""
        # Simple merge: combine unique information
        all_words = []
        seen = set()

        for content in contents:
            for word in content.split():
                if word.lower() not in seen:
                    all_words.append(word)
                    seen.add(word.lower())

        # Limit merged content length
        merged = " ".join(all_words[:200])
        return merged

    async def summarize_old_memories(
        self,
        bot_id: UUID,
        days: int = 30,
        session: Optional[AsyncSession] = None
    ) -> ConsolidationResult:
        """
        Create summaries of old memories.

        Groups memories by time period and creates summary memories.

        Args:
            bot_id: The bot whose memories to summarize
            days: Summarize memories older than this many days
            session: Optional database session

        Returns:
            ConsolidationResult with details
        """
        async def _summarize(sess: AsyncSession) -> ConsolidationResult:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Get old memories
            stmt = (
                select(MemoryItemDB)
                .where(
                    and_(
                        MemoryItemDB.bot_id == bot_id,
                        MemoryItemDB.created_at < cutoff_date,
                        MemoryItemDB.memory_type != "summary"  # Don't summarize summaries
                    )
                )
                .order_by(MemoryItemDB.created_at)
            )
            result = await sess.execute(stmt)
            old_memories = result.scalars().all()

            if len(old_memories) < 10:
                return ConsolidationResult(
                    bot_id=bot_id,
                    memories_processed=0,
                    memories_merged=0,
                    memories_summarized=0,
                    memories_archived=0,
                    storage_saved_bytes=0,
                    new_summaries=[]
                )

            # Group by week
            week_groups: Dict[str, List[MemoryItemDB]] = {}
            for memory in old_memories:
                week_key = memory.created_at.strftime("%Y-W%W")
                if week_key not in week_groups:
                    week_groups[week_key] = []
                week_groups[week_key].append(memory)

            new_summaries = []
            memories_summarized = 0
            storage_saved = 0

            for week_key, week_memories in week_groups.items():
                if len(week_memories) < 5:
                    continue

                # Create a summary
                contents = [m.content for m in week_memories]
                summary_content = self._create_summary(contents)

                # Find time range
                time_start = min(m.created_at for m in week_memories)
                time_end = max(m.created_at for m in week_memories)
                avg_importance = sum(m.importance for m in week_memories) / len(week_memories)

                # Create summary memory
                summary = MemoryItemDB(
                    bot_id=bot_id,
                    memory_type="summary",
                    content=summary_content,
                    importance=avg_importance,
                    context={
                        "source_count": len(week_memories),
                        "time_range_start": time_start.isoformat(),
                        "time_range_end": time_end.isoformat(),
                        "original_types": list(set(m.memory_type for m in week_memories))
                    }
                )
                sess.add(summary)

                # Mark original memories as archived (low importance)
                for memory in week_memories:
                    storage_saved += len(memory.content.encode('utf-8'))
                    memory.importance = 0.1  # Reduce importance
                    memories_summarized += 1

                new_summaries.append(f"Week {week_key}: {len(week_memories)} memories")

            await sess.commit()

            return ConsolidationResult(
                bot_id=bot_id,
                memories_processed=len(old_memories),
                memories_merged=0,
                memories_summarized=memories_summarized,
                memories_archived=0,
                storage_saved_bytes=storage_saved,
                new_summaries=new_summaries
            )

        if session:
            return await _summarize(session)
        else:
            async with async_session_factory() as sess:
                return await _summarize(sess)

    def _create_summary(self, contents: List[str]) -> str:
        """Create a summary from multiple memory contents."""
        # Simple extractive summary: take key phrases
        all_words = []
        word_freq: Dict[str, int] = {}

        for content in contents:
            for word in content.split():
                word_lower = word.lower()
                word_freq[word_lower] = word_freq.get(word_lower, 0) + 1
                if word_lower not in [w.lower() for w in all_words]:
                    all_words.append(word)

        # Sort by frequency and take top words
        sorted_words = sorted(all_words, key=lambda w: word_freq.get(w.lower(), 0), reverse=True)
        summary = " ".join(sorted_words[:100])

        return f"Summary of {len(contents)} memories: {summary}"

    async def archive_memories(
        self,
        bot_id: UUID,
        older_than_days: int = 90,
        session: Optional[AsyncSession] = None
    ) -> ConsolidationResult:
        """
        Archive old, low-importance memories.

        Moves memories to archive storage and removes from active database.

        Args:
            bot_id: The bot whose memories to archive
            older_than_days: Archive memories older than this many days
            session: Optional database session

        Returns:
            ConsolidationResult with details
        """
        async def _archive(sess: AsyncSession) -> ConsolidationResult:
            cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)

            # Find memories to archive
            stmt = select(MemoryItemDB).where(
                and_(
                    MemoryItemDB.bot_id == bot_id,
                    MemoryItemDB.created_at < cutoff_date,
                    MemoryItemDB.importance < 0.3,
                    MemoryItemDB.access_count < 3
                )
            )
            result = await sess.execute(stmt)
            memories_to_archive = result.scalars().all()

            if not memories_to_archive:
                return ConsolidationResult(
                    bot_id=bot_id,
                    memories_processed=0,
                    memories_merged=0,
                    memories_summarized=0,
                    memories_archived=0,
                    storage_saved_bytes=0,
                    new_summaries=[]
                )

            # Archive to ArchivedMemoryDB
            from mind.core.database import ArchivedMemoryDB

            archive_id = uuid4()
            storage_saved = 0

            # Create archive record
            archive_data = [
                {
                    "id": str(m.id),
                    "type": m.memory_type,
                    "content": m.content[:500],  # Truncate for storage
                    "importance": m.importance,
                    "created_at": m.created_at.isoformat()
                }
                for m in memories_to_archive[:100]  # Limit to 100 per archive
            ]

            archive = ArchivedMemoryDB(
                id=archive_id,
                bot_id=bot_id,
                archive_type="age_based",
                memory_count=len(memories_to_archive),
                original_memories=archive_data,
                summary=f"Archived {len(memories_to_archive)} memories older than {older_than_days} days",
                created_at=datetime.utcnow()
            )
            sess.add(archive)

            # Delete the archived memories
            for memory in memories_to_archive:
                storage_saved += len(memory.content.encode('utf-8'))
                await sess.delete(memory)

            await sess.commit()

            logger.info(f"Archived {len(memories_to_archive)} memories for bot {bot_id}")

            return ConsolidationResult(
                bot_id=bot_id,
                memories_processed=len(memories_to_archive),
                memories_merged=0,
                memories_summarized=0,
                memories_archived=len(memories_to_archive),
                storage_saved_bytes=storage_saved,
                new_summaries=[f"Archived to {archive_id}"]
            )

        if session:
            return await _archive(session)
        else:
            async with async_session_factory() as sess:
                return await _archive(sess)

    async def get_memory_stats(
        self,
        bot_id: UUID,
        session: Optional[AsyncSession] = None
    ) -> MemoryStats:
        """
        Get memory statistics for a bot.

        Args:
            bot_id: The bot to analyze
            session: Optional database session

        Returns:
            MemoryStats with detailed statistics
        """
        async def _get_stats(sess: AsyncSession) -> MemoryStats:
            # Total memories
            total_stmt = select(func.count()).select_from(MemoryItemDB).where(
                MemoryItemDB.bot_id == bot_id
            )
            total_result = await sess.execute(total_stmt)
            total_memories = total_result.scalar() or 0

            # Get archived count
            from mind.core.database import ArchivedMemoryDB

            archived_stmt = select(func.sum(ArchivedMemoryDB.memory_count)).where(
                ArchivedMemoryDB.bot_id == bot_id
            )
            archived_result = await sess.execute(archived_stmt)
            archived_memories = archived_result.scalar() or 0

            # Memory types breakdown
            types_stmt = (
                select(MemoryItemDB.memory_type, func.count())
                .where(MemoryItemDB.bot_id == bot_id)
                .group_by(MemoryItemDB.memory_type)
            )
            types_result = await sess.execute(types_stmt)
            memory_types = {row[0]: row[1] for row in types_result.all()}

            # Date range
            dates_stmt = select(
                func.min(MemoryItemDB.created_at),
                func.max(MemoryItemDB.created_at)
            ).where(MemoryItemDB.bot_id == bot_id)
            dates_result = await sess.execute(dates_stmt)
            dates_row = dates_result.one_or_none()
            oldest_memory = dates_row[0] if dates_row else None
            newest_memory = dates_row[1] if dates_row else None

            # Average importance
            importance_stmt = select(func.avg(MemoryItemDB.importance)).where(
                MemoryItemDB.bot_id == bot_id
            )
            importance_result = await sess.execute(importance_stmt)
            avg_importance = importance_result.scalar() or 0.5

            # Estimate size
            size_stmt = select(func.sum(func.length(MemoryItemDB.content))).where(
                MemoryItemDB.bot_id == bot_id
            )
            size_result = await sess.execute(size_stmt)
            size_bytes = size_result.scalar() or 0

            # Consolidation candidates (old, low importance)
            cutoff_date = datetime.utcnow() - timedelta(days=self.summarize_after_days)
            candidates_stmt = select(func.count()).select_from(MemoryItemDB).where(
                and_(
                    MemoryItemDB.bot_id == bot_id,
                    MemoryItemDB.created_at < cutoff_date,
                    MemoryItemDB.importance < 0.5
                )
            )
            candidates_result = await sess.execute(candidates_stmt)
            consolidation_candidates = candidates_result.scalar() or 0

            return MemoryStats(
                bot_id=bot_id,
                total_memories=total_memories,
                active_memories=total_memories,
                archived_memories=archived_memories,
                size_bytes=size_bytes,
                oldest_memory=oldest_memory,
                newest_memory=newest_memory,
                memory_types=memory_types,
                avg_importance=avg_importance,
                consolidation_candidates=consolidation_candidates
            )

        if session:
            return await _get_stats(session)
        else:
            async with async_session_factory() as sess:
                return await _get_stats(sess)

    async def full_consolidation(
        self,
        bot_id: UUID,
        session: Optional[AsyncSession] = None
    ) -> ConsolidationResult:
        """
        Run full consolidation pipeline for a bot.

        1. Merge similar memories
        2. Summarize old memories
        3. Archive ancient memories

        Args:
            bot_id: The bot to consolidate
            session: Optional database session

        Returns:
            Combined ConsolidationResult
        """
        async def _full(sess: AsyncSession) -> ConsolidationResult:
            # Step 1: Merge similar
            merge_result = await self.consolidate_bot_memories(bot_id, sess)

            # Step 2: Summarize old
            summarize_result = await self.summarize_old_memories(bot_id, self.summarize_after_days, sess)

            # Step 3: Archive ancient
            archive_result = await self.archive_memories(bot_id, self.archive_after_days, sess)

            return ConsolidationResult(
                bot_id=bot_id,
                memories_processed=merge_result.memories_processed + summarize_result.memories_processed + archive_result.memories_processed,
                memories_merged=merge_result.memories_merged,
                memories_summarized=summarize_result.memories_summarized,
                memories_archived=archive_result.memories_archived,
                storage_saved_bytes=merge_result.storage_saved_bytes + summarize_result.storage_saved_bytes + archive_result.storage_saved_bytes,
                new_summaries=merge_result.new_summaries + summarize_result.new_summaries + archive_result.new_summaries
            )

        if session:
            return await _full(session)
        else:
            async with async_session_factory() as sess:
                return await _full(sess)


# ============================================================================
# FACTORY
# ============================================================================

_consolidation_manager: Optional[MemoryConsolidationManager] = None


def get_consolidation_manager() -> MemoryConsolidationManager:
    """Get the singleton consolidation manager."""
    global _consolidation_manager
    if _consolidation_manager is None:
        _consolidation_manager = MemoryConsolidationManager()
    return _consolidation_manager
