"""
Memory Core for AI Community Companions.
Implements both short-term (Redis) and long-term (PostgreSQL + pgvector) memory.
"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
import numpy as np

import redis.asyncio as redis
from sqlalchemy import select, delete, update, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from mind.config.settings import settings
from mind.core.types import MemoryItem, Relationship, RelationshipType
from mind.core.database import (
    MemoryItemDB, RelationshipDB, async_session_factory
)


# ============================================================================
# EMBEDDING CLIENT (Ollama) - Now with optional batching support
# ============================================================================

class EmbeddingClient:
    """
    Client for generating embeddings using Ollama.
    Supports optional batching via EmbeddingBatcher for improved throughput.
    """

    def __init__(self, base_url: str, model: str, use_batcher: bool = True):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.use_batcher = use_batcher
        self._session = None
        self._batcher = None

    async def _get_session(self):
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession()
        return self._session

    async def _get_batcher(self):
        """Get embedding batcher if batching is enabled."""
        if not self.use_batcher:
            return None
        if self._batcher is None:
            try:
                from mind.core.embedding_batch import get_embedding_batcher
                self._batcher = await get_embedding_batcher()
            except Exception:
                self._batcher = None
        return self._batcher

    async def embed(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        # Try batcher first
        batcher = await self._get_batcher()
        if batcher:
            return await batcher.get_or_compute(text)

        # Fallback to direct embedding
        session = await self._get_session()
        async with session.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.model, "prompt": text}
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data["embedding"]
            else:
                raise Exception(f"Embedding failed: {await response.text()}")

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts using batching."""
        batcher = await self._get_batcher()
        if batcher:
            # Queue all texts and wait for results
            futures = [await batcher.queue_embedding(text) for text in texts]
            return await asyncio.gather(*futures)

        # Fallback to concurrent direct embeddings
        tasks = [self.embed(text) for text in texts]
        return await asyncio.gather(*tasks)

    async def queue_embed(
        self,
        text: str,
        callback = None
    ):
        """
        Queue an embedding for batch processing.
        Returns a future that resolves to the embedding.
        """
        batcher = await self._get_batcher()
        if batcher:
            return await batcher.queue_embedding(text, callback)
        # Fallback to direct embedding
        embedding = await self.embed(text)
        if callback:
            await callback(embedding)
        future = asyncio.get_event_loop().create_future()
        future.set_result(embedding)
        return future

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None


# ============================================================================
# SHORT-TERM MEMORY (Redis)
# ============================================================================

class ShortTermMemory:
    """
    Redis-based short-term memory for recent conversations and context.
    Stores recent messages, current conversation context, and ephemeral state.
    """

    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.default_ttl = 3600 * 24  # 24 hours

    async def store_conversation_turn(
        self,
        bot_id: UUID,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ):
        """Store a conversation turn in short-term memory."""
        key = f"conv:{bot_id}:{conversation_id}"
        turn = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        await self.redis.rpush(key, json.dumps(turn))
        await self.redis.expire(key, self.default_ttl)

        # Keep only last N turns
        await self.redis.ltrim(key, -50, -1)

    async def get_recent_conversation(
        self,
        bot_id: UUID,
        conversation_id: str,
        limit: int = 20
    ) -> List[Dict]:
        """Get recent conversation turns."""
        key = f"conv:{bot_id}:{conversation_id}"
        turns = await self.redis.lrange(key, -limit, -1)
        return [json.loads(t) for t in turns]

    async def store_context(
        self,
        bot_id: UUID,
        context_type: str,
        data: Dict,
        ttl: Optional[int] = None
    ):
        """Store ephemeral context data."""
        key = f"ctx:{bot_id}:{context_type}"
        await self.redis.set(
            key,
            json.dumps(data),
            ex=ttl or self.default_ttl
        )

    async def get_context(
        self,
        bot_id: UUID,
        context_type: str
    ) -> Optional[Dict]:
        """Get ephemeral context data."""
        key = f"ctx:{bot_id}:{context_type}"
        data = await self.redis.get(key)
        return json.loads(data) if data else None

    async def update_activity_state(
        self,
        bot_id: UUID,
        is_online: bool,
        current_activity: Optional[str] = None
    ):
        """Update bot's current activity state."""
        key = f"state:{bot_id}"
        state = {
            "is_online": is_online,
            "current_activity": current_activity,
            "last_seen": datetime.utcnow().isoformat()
        }
        await self.redis.hset(key, mapping=state)
        await self.redis.expire(key, 3600)  # 1 hour

    async def get_activity_state(self, bot_id: UUID) -> Optional[Dict]:
        """Get bot's current activity state."""
        key = f"state:{bot_id}"
        return await self.redis.hgetall(key)

    async def close(self):
        await self.redis.close()


# ============================================================================
# LONG-TERM MEMORY (PostgreSQL + pgvector)
# ============================================================================

class LongTermMemory:
    """
    PostgreSQL-based long-term memory with vector similarity search.
    Stores permanent memories, relationships, and learned patterns.
    Supports batch embedding for improved throughput.
    """

    def __init__(self, embedding_client: EmbeddingClient):
        self.embedding_client = embedding_client

    async def store_memories_batch(
        self,
        session: AsyncSession,
        memories: List[Dict[str, Any]]
    ) -> List[MemoryItem]:
        """
        Store multiple memories with batched embeddings.

        Args:
            session: Database session
            memories: List of memory dicts with keys:
                - bot_id: UUID
                - content: str
                - memory_type: str (optional)
                - importance: float (optional)
                - emotional_valence: float (optional)
                - related_entity_ids: List[UUID] (optional)
                - context: Dict (optional)

        Returns:
            List of created MemoryItem objects
        """
        if not memories:
            return []

        # Extract texts for batch embedding
        texts = [m["content"] for m in memories]

        # Batch embed all texts
        embeddings = await self.embedding_client.embed_batch(texts)

        # Create all memory records
        results = []
        for i, (mem_data, embedding) in enumerate(zip(memories, embeddings)):
            memory = MemoryItemDB(
                bot_id=mem_data["bot_id"],
                memory_type=mem_data.get("memory_type", "conversation"),
                content=mem_data["content"],
                embedding=embedding,
                importance=mem_data.get("importance", 0.5),
                emotional_valence=mem_data.get("emotional_valence", 0.0),
                related_entity_ids=[
                    str(eid) for eid in mem_data.get("related_entity_ids", [])
                ],
                context=mem_data.get("context", {}),
            )
            session.add(memory)
            results.append(memory)

        await session.commit()

        # Refresh and convert to MemoryItem
        memory_items = []
        for memory in results:
            await session.refresh(memory)
            memory_items.append(MemoryItem(
                id=memory.id,
                bot_id=memory.bot_id,
                memory_type=memory.memory_type,
                content=memory.content,
                importance=memory.importance,
                emotional_valence=memory.emotional_valence,
                created_at=memory.created_at
            ))

        return memory_items

    async def store_memory(
        self,
        session: AsyncSession,
        bot_id: UUID,
        content: str,
        memory_type: str = "conversation",
        importance: float = 0.5,
        emotional_valence: float = 0.0,
        related_entity_ids: Optional[List[UUID]] = None,
        context: Optional[Dict] = None
    ) -> MemoryItem:
        """Store a memory with its embedding."""
        # Generate embedding
        embedding = await self.embedding_client.embed(content)

        memory = MemoryItemDB(
            bot_id=bot_id,
            memory_type=memory_type,
            content=content,
            embedding=embedding,
            importance=importance,
            emotional_valence=emotional_valence,
            related_entity_ids=[str(eid) for eid in (related_entity_ids or [])],
            context=context or {},
        )

        session.add(memory)
        await session.commit()
        await session.refresh(memory)

        return MemoryItem(
            id=memory.id,
            bot_id=memory.bot_id,
            memory_type=memory.memory_type,
            content=memory.content,
            importance=memory.importance,
            emotional_valence=memory.emotional_valence,
            created_at=memory.created_at
        )

    async def search_memories(
        self,
        session: AsyncSession,
        bot_id: UUID,
        query: str,
        limit: int = 10,
        memory_types: Optional[List[str]] = None,
        min_importance: float = 0.0,
        time_window_days: Optional[int] = None
    ) -> List[Tuple[MemoryItem, float]]:
        """Search memories using vector similarity."""
        # Generate query embedding
        query_embedding = await self.embedding_client.embed(query)

        # Build query
        conditions = [MemoryItemDB.bot_id == bot_id]

        if memory_types:
            conditions.append(MemoryItemDB.memory_type.in_(memory_types))

        if min_importance > 0:
            conditions.append(MemoryItemDB.importance >= min_importance)

        if time_window_days:
            cutoff = datetime.utcnow() - timedelta(days=time_window_days)
            conditions.append(MemoryItemDB.created_at >= cutoff)

        # Vector similarity search using pgvector
        # Using cosine distance (1 - similarity, so lower is better)
        stmt = (
            select(
                MemoryItemDB,
                MemoryItemDB.embedding.cosine_distance(query_embedding).label("distance")
            )
            .where(and_(*conditions))
            .order_by("distance")
            .limit(limit)
        )

        result = await session.execute(stmt)
        rows = result.all()

        # Convert to MemoryItem and similarity score
        memories = []
        for row in rows:
            memory_db = row[0]
            distance = row[1]
            similarity = 1 - distance  # Convert distance to similarity

            memory = MemoryItem(
                id=memory_db.id,
                bot_id=memory_db.bot_id,
                memory_type=memory_db.memory_type,
                content=memory_db.content,
                importance=memory_db.importance,
                emotional_valence=memory_db.emotional_valence,
                created_at=memory_db.created_at
            )

            # Update access stats
            memory_db.last_accessed = datetime.utcnow()
            memory_db.access_count += 1

            memories.append((memory, similarity))

        await session.commit()
        return memories

    async def get_recent_memories(
        self,
        session: AsyncSession,
        bot_id: UUID,
        limit: int = 20,
        memory_types: Optional[List[str]] = None
    ) -> List[MemoryItem]:
        """Get most recent memories."""
        conditions = [MemoryItemDB.bot_id == bot_id]
        if memory_types:
            conditions.append(MemoryItemDB.memory_type.in_(memory_types))

        stmt = (
            select(MemoryItemDB)
            .where(and_(*conditions))
            .order_by(desc(MemoryItemDB.created_at))
            .limit(limit)
        )

        result = await session.execute(stmt)
        rows = result.scalars().all()

        return [
            MemoryItem(
                id=m.id,
                bot_id=m.bot_id,
                memory_type=m.memory_type,
                content=m.content,
                importance=m.importance,
                emotional_valence=m.emotional_valence,
                created_at=m.created_at
            )
            for m in rows
        ]

    async def consolidate_memories(
        self,
        session: AsyncSession,
        bot_id: UUID,
        max_memories: int = 1000
    ):
        """
        Consolidate memories when approaching limit.
        Keeps important and recent memories, summarizes old ones.
        """
        # Count current memories
        count_stmt = select(MemoryItemDB).where(MemoryItemDB.bot_id == bot_id)
        result = await session.execute(count_stmt)
        count = len(result.scalars().all())

        if count <= max_memories:
            return

        # Delete old, low-importance memories
        delete_threshold = max_memories * 0.8
        cutoff_date = datetime.utcnow() - timedelta(days=30)

        delete_stmt = (
            delete(MemoryItemDB)
            .where(
                and_(
                    MemoryItemDB.bot_id == bot_id,
                    MemoryItemDB.importance < 0.3,
                    MemoryItemDB.created_at < cutoff_date,
                    MemoryItemDB.access_count < 3
                )
            )
        )

        await session.execute(delete_stmt)
        await session.commit()


# ============================================================================
# RELATIONSHIP MEMORY
# ============================================================================

class RelationshipMemory:
    """Manages relationships between bots and with users."""

    async def get_or_create_relationship(
        self,
        session: AsyncSession,
        source_id: UUID,
        target_id: UUID,
        target_is_human: bool = False
    ) -> Relationship:
        """Get existing relationship or create new one."""
        stmt = select(RelationshipDB).where(
            and_(
                RelationshipDB.source_id == source_id,
                RelationshipDB.target_id == target_id
            )
        )

        result = await session.execute(stmt)
        rel_db = result.scalar_one_or_none()

        if rel_db is None:
            rel_db = RelationshipDB(
                source_id=source_id,
                target_id=target_id,
                target_is_human=target_is_human,
            )
            session.add(rel_db)
            await session.commit()
            await session.refresh(rel_db)

        return Relationship(
            id=rel_db.id,
            source_id=rel_db.source_id,
            target_id=rel_db.target_id,
            target_is_human=rel_db.target_is_human,
            relationship_type=RelationshipType(rel_db.relationship_type),
            affinity_score=rel_db.affinity_score,
            interaction_count=rel_db.interaction_count,
            last_interaction=rel_db.last_interaction,
            shared_memories=rel_db.shared_memories,
            inside_jokes=rel_db.inside_jokes,
            topics_discussed=rel_db.topics_discussed
        )

    async def update_relationship(
        self,
        session: AsyncSession,
        relationship_id: UUID,
        affinity_delta: float = 0.0,
        new_topic: Optional[str] = None,
        new_inside_joke: Optional[str] = None,
        new_shared_memory_id: Optional[str] = None
    ):
        """Update a relationship after an interaction."""
        stmt = select(RelationshipDB).where(RelationshipDB.id == relationship_id)
        result = await session.execute(stmt)
        rel = result.scalar_one_or_none()

        if rel is None:
            return

        # Update affinity
        rel.affinity_score = max(0.0, min(1.0, rel.affinity_score + affinity_delta))

        # Update interaction count
        rel.interaction_count += 1
        rel.last_interaction = datetime.utcnow()

        # Add new topic
        if new_topic and new_topic not in rel.topics_discussed:
            topics = list(rel.topics_discussed)
            topics.append(new_topic)
            rel.topics_discussed = topics[-20:]  # Keep last 20

        # Add inside joke
        if new_inside_joke:
            jokes = list(rel.inside_jokes)
            jokes.append(new_inside_joke)
            rel.inside_jokes = jokes[-10:]  # Keep last 10

        # Add shared memory
        if new_shared_memory_id:
            memories = list(rel.shared_memories)
            memories.append(new_shared_memory_id)
            rel.shared_memories = memories[-50:]  # Keep last 50

        # Upgrade relationship type based on affinity
        if rel.affinity_score >= 0.8 and rel.interaction_count >= 50:
            rel.relationship_type = RelationshipType.CLOSE_FRIEND.value
        elif rel.affinity_score >= 0.6 and rel.interaction_count >= 20:
            rel.relationship_type = RelationshipType.FRIEND.value
        elif rel.interaction_count >= 5:
            rel.relationship_type = RelationshipType.ACQUAINTANCE.value

        await session.commit()

    async def get_relationships(
        self,
        session: AsyncSession,
        bot_id: UUID,
        min_affinity: float = 0.0,
        relationship_types: Optional[List[RelationshipType]] = None
    ) -> List[Relationship]:
        """Get all relationships for a bot."""
        conditions = [
            RelationshipDB.source_id == bot_id,
            RelationshipDB.affinity_score >= min_affinity
        ]

        if relationship_types:
            conditions.append(
                RelationshipDB.relationship_type.in_([rt.value for rt in relationship_types])
            )

        stmt = (
            select(RelationshipDB)
            .where(and_(*conditions))
            .order_by(desc(RelationshipDB.affinity_score))
        )

        result = await session.execute(stmt)
        rows = result.scalars().all()

        return [
            Relationship(
                id=r.id,
                source_id=r.source_id,
                target_id=r.target_id,
                target_is_human=r.target_is_human,
                relationship_type=RelationshipType(r.relationship_type),
                affinity_score=r.affinity_score,
                interaction_count=r.interaction_count,
                last_interaction=r.last_interaction,
                shared_memories=r.shared_memories,
                inside_jokes=r.inside_jokes,
                topics_discussed=r.topics_discussed
            )
            for r in rows
        ]


# ============================================================================
# UNIFIED MEMORY CORE
# ============================================================================

class MemoryCore:
    """
    Unified memory interface combining short-term, long-term, and relationship memory.
    """

    def __init__(self):
        self.embedding_client = EmbeddingClient(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_EMBEDDING_MODEL
        )
        self.short_term = ShortTermMemory(settings.REDIS_URL)
        self.long_term = LongTermMemory(self.embedding_client)
        self.relationships = RelationshipMemory()

    async def remember(
        self,
        bot_id: UUID,
        content: str,
        memory_type: str = "conversation",
        importance: float = 0.5,
        emotional_valence: float = 0.0,
        related_entity_ids: Optional[List[UUID]] = None,
        context: Optional[Dict] = None,
        conversation_id: Optional[str] = None
    ) -> MemoryItem:
        """Store a new memory in both short and long term."""
        # Store in short-term
        if conversation_id:
            await self.short_term.store_conversation_turn(
                bot_id=bot_id,
                conversation_id=conversation_id,
                role="memory",
                content=content,
                metadata={"type": memory_type, "importance": importance}
            )

        # Store in long-term
        async with async_session_factory() as session:
            return await self.long_term.store_memory(
                session=session,
                bot_id=bot_id,
                content=content,
                memory_type=memory_type,
                importance=importance,
                emotional_valence=emotional_valence,
                related_entity_ids=related_entity_ids,
                context=context
            )

    async def remember_batch(
        self,
        memories: List[Dict[str, Any]]
    ) -> List[MemoryItem]:
        """
        Store multiple memories using batch embedding for improved throughput.

        Args:
            memories: List of memory dicts with keys:
                - bot_id: UUID
                - content: str
                - memory_type: str (optional, default: "conversation")
                - importance: float (optional, default: 0.5)
                - emotional_valence: float (optional, default: 0.0)
                - related_entity_ids: List[UUID] (optional)
                - context: Dict (optional)
                - conversation_id: str (optional, for short-term storage)

        Returns:
            List of created MemoryItem objects
        """
        if not memories:
            return []

        # Store in short-term for those with conversation_id
        for mem in memories:
            if mem.get("conversation_id"):
                await self.short_term.store_conversation_turn(
                    bot_id=mem["bot_id"],
                    conversation_id=mem["conversation_id"],
                    role="memory",
                    content=mem["content"],
                    metadata={
                        "type": mem.get("memory_type", "conversation"),
                        "importance": mem.get("importance", 0.5)
                    }
                )

        # Store in long-term with batch embedding
        async with async_session_factory() as session:
            return await self.long_term.store_memories_batch(
                session=session,
                memories=memories
            )

    async def recall(
        self,
        bot_id: UUID,
        query: str,
        limit: int = 10,
        include_conversation: bool = True,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Recall relevant memories for a given context."""
        result = {
            "semantic_memories": [],
            "recent_memories": [],
            "conversation_context": []
        }

        async with async_session_factory() as session:
            # Semantic search
            semantic = await self.long_term.search_memories(
                session=session,
                bot_id=bot_id,
                query=query,
                limit=limit
            )
            result["semantic_memories"] = [
                {"memory": m.model_dump(), "similarity": s}
                for m, s in semantic
            ]

            # Recent memories
            recent = await self.long_term.get_recent_memories(
                session=session,
                bot_id=bot_id,
                limit=5
            )
            result["recent_memories"] = [m.model_dump() for m in recent]

        # Conversation context
        if include_conversation and conversation_id:
            result["conversation_context"] = await self.short_term.get_recent_conversation(
                bot_id=bot_id,
                conversation_id=conversation_id
            )

        return result

    async def close(self):
        """Close all connections."""
        await self.short_term.close()
        await self.embedding_client.close()


# ============================================================================
# FACTORY
# ============================================================================

_memory_core: Optional[MemoryCore] = None


async def get_memory_core() -> MemoryCore:
    """Get or create the global memory core instance."""
    global _memory_core
    if _memory_core is None:
        _memory_core = MemoryCore()
    return _memory_core
