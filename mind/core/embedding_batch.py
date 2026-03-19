"""
Embedding Batcher for AI Community Companions.
Batches embedding requests for improved throughput.
"""

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any, Awaitable
from collections import deque

from mind.config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingRequest:
    """A queued embedding request."""
    text: str
    text_hash: str
    callback: Optional[Callable[[List[float]], Awaitable[None]]] = None
    future: Optional[asyncio.Future] = None
    created_at: float = field(default_factory=time.time)


class EmbeddingBatcher:
    """
    Batches embedding requests for efficient processing.

    Features:
    - Queue embeddings with callbacks
    - Process in batches for throughput
    - Automatic batch processing on timer or when full
    - Caching of computed embeddings
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        batch_size: int = 32,
        batch_interval: float = 5.0,
        cache_size: int = 10000
    ):
        """
        Initialize the embedding batcher.

        Args:
            base_url: Ollama base URL
            model: Embedding model name
            batch_size: Maximum batch size before processing
            batch_interval: Max seconds to wait before processing batch
            cache_size: Maximum cached embeddings
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.batch_size = batch_size
        self.batch_interval = batch_interval
        self.cache_size = cache_size

        self._queue: deque[EmbeddingRequest] = deque()
        self._cache: Dict[str, List[float]] = {}
        self._cache_order: deque[str] = deque()

        self._lock = asyncio.Lock()
        self._batch_task: Optional[asyncio.Task] = None
        self._running = False

        self._session = None

        # Stats
        self.total_requests = 0
        self.cache_hits = 0
        self.batches_processed = 0
        self.total_embeddings = 0

    async def _get_session(self):
        """Get or create aiohttp session."""
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession()
        return self._session

    def _hash_text(self, text: str) -> str:
        """Create a hash for the text."""
        return hashlib.sha256(text.encode()).hexdigest()[:32]

    async def queue_embedding(
        self,
        text: str,
        callback: Optional[Callable[[List[float]], Awaitable[None]]] = None
    ) -> asyncio.Future:
        """
        Queue an embedding request.

        Args:
            text: Text to embed
            callback: Optional async callback when embedding is ready

        Returns:
            Future that resolves to the embedding
        """
        self.total_requests += 1
        text_hash = self._hash_text(text)

        # Check cache first
        if text_hash in self._cache:
            self.cache_hits += 1
            embedding = self._cache[text_hash]

            if callback:
                asyncio.create_task(callback(embedding))

            future = asyncio.get_event_loop().create_future()
            future.set_result(embedding)
            return future

        # Create request
        future = asyncio.get_event_loop().create_future()
        request = EmbeddingRequest(
            text=text,
            text_hash=text_hash,
            callback=callback,
            future=future
        )

        async with self._lock:
            self._queue.append(request)

            # Process immediately if batch is full
            if len(self._queue) >= self.batch_size:
                asyncio.create_task(self.process_batch())

        return future

    async def get_or_compute(self, text: str) -> List[float]:
        """
        Get embedding for text, computing if necessary.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        text_hash = self._hash_text(text)

        # Check cache
        if text_hash in self._cache:
            self.cache_hits += 1
            return self._cache[text_hash]

        # Compute directly
        embedding = await self._compute_single(text)

        # Cache it
        self._add_to_cache(text_hash, embedding)

        return embedding

    async def _compute_single(self, text: str) -> List[float]:
        """Compute a single embedding."""
        session = await self._get_session()

        async with session.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.model, "prompt": text}
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data["embedding"]
            else:
                error = await response.text()
                raise Exception(f"Embedding failed: {error}")

    async def _compute_batch(self, texts: List[str]) -> List[List[float]]:
        """Compute embeddings for a batch of texts."""
        # Ollama doesn't support batch embeddings natively,
        # so we use concurrent requests
        tasks = [self._compute_single(text) for text in texts]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def _add_to_cache(self, text_hash: str, embedding: List[float]) -> None:
        """Add embedding to cache with LRU eviction."""
        if text_hash in self._cache:
            return

        # Evict oldest if at capacity
        while len(self._cache) >= self.cache_size:
            old_hash = self._cache_order.popleft()
            self._cache.pop(old_hash, None)

        self._cache[text_hash] = embedding
        self._cache_order.append(text_hash)

    async def process_batch(self) -> int:
        """
        Process all queued embedding requests.

        Returns:
            Number of embeddings processed
        """
        async with self._lock:
            if not self._queue:
                return 0

            # Get all requests up to batch size
            batch: List[EmbeddingRequest] = []
            while self._queue and len(batch) < self.batch_size:
                batch.append(self._queue.popleft())

        if not batch:
            return 0

        # Deduplicate by hash
        unique_texts: Dict[str, str] = {}
        request_by_hash: Dict[str, List[EmbeddingRequest]] = {}

        for req in batch:
            if req.text_hash not in unique_texts:
                unique_texts[req.text_hash] = req.text
                request_by_hash[req.text_hash] = []
            request_by_hash[req.text_hash].append(req)

        # Compute embeddings
        texts = list(unique_texts.values())
        hashes = list(unique_texts.keys())

        logger.debug(f"[EMBED_BATCH] Processing batch of {len(texts)} unique texts")

        try:
            embeddings = await self._compute_batch(texts)

            for i, (text_hash, embedding) in enumerate(zip(hashes, embeddings)):
                if isinstance(embedding, Exception):
                    # Handle error
                    for req in request_by_hash[text_hash]:
                        if req.future and not req.future.done():
                            req.future.set_exception(embedding)
                    continue

                # Cache the embedding
                self._add_to_cache(text_hash, embedding)
                self.total_embeddings += 1

                # Fulfill requests
                for req in request_by_hash[text_hash]:
                    if req.callback:
                        asyncio.create_task(req.callback(embedding))
                    if req.future and not req.future.done():
                        req.future.set_result(embedding)

            self.batches_processed += 1
            logger.debug(f"[EMBED_BATCH] Batch complete: {len(texts)} embeddings")

        except Exception as e:
            logger.error(f"[EMBED_BATCH] Batch processing failed: {e}")
            # Fail all requests
            for req in batch:
                if req.future and not req.future.done():
                    req.future.set_exception(e)

        return len(batch)

    async def start(self) -> None:
        """Start the batch processing loop."""
        if self._running:
            return

        self._running = True

        async def batch_loop():
            while self._running:
                try:
                    await asyncio.sleep(self.batch_interval)
                    if self._queue:
                        await self.process_batch()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"[EMBED_BATCH] Batch loop error: {e}")

        self._batch_task = asyncio.create_task(batch_loop())
        logger.info(f"[EMBED_BATCH] Started (batch_size={self.batch_size}, interval={self.batch_interval}s)")

    async def stop(self) -> None:
        """Stop the batch processing loop."""
        self._running = False

        # Process remaining queue
        while self._queue:
            await self.process_batch()

        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass
            self._batch_task = None

        logger.info("[EMBED_BATCH] Stopped")

    def get_stats(self) -> Dict[str, Any]:
        """Get batcher statistics."""
        total = self.total_requests
        hit_rate = self.cache_hits / max(1, total)

        return {
            "queue_size": len(self._queue),
            "cache_size": len(self._cache),
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_hit_rate": round(hit_rate, 4),
            "batches_processed": self.batches_processed,
            "total_embeddings": self.total_embeddings,
            "avg_batch_size": round(
                self.total_embeddings / max(1, self.batches_processed), 2
            )
        }

    async def close(self) -> None:
        """Close the batcher and cleanup."""
        await self.stop()

        if self._session:
            await self._session.close()
            self._session = None

        self._cache.clear()
        self._cache_order.clear()

        logger.info("[EMBED_BATCH] Closed")


# ============================================================================
# FACTORY
# ============================================================================

_embedding_batcher: Optional[EmbeddingBatcher] = None


async def get_embedding_batcher() -> EmbeddingBatcher:
    """Get or create the global embedding batcher."""
    global _embedding_batcher

    if _embedding_batcher is None:
        _embedding_batcher = EmbeddingBatcher(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_EMBEDDING_MODEL,
            batch_size=getattr(settings, 'EMBEDDING_BATCH_SIZE', 32),
            batch_interval=getattr(settings, 'EMBEDDING_BATCH_INTERVAL', 5.0)
        )
        await _embedding_batcher.start()

    return _embedding_batcher


async def close_embedding_batcher() -> None:
    """Close the global embedding batcher."""
    global _embedding_batcher

    if _embedding_batcher is not None:
        await _embedding_batcher.close()
        _embedding_batcher = None
