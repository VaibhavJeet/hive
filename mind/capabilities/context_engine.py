"""
Context Engine - Manages conversation context, compaction, and summarization.

Handles long conversations by intelligently compacting older messages while
preserving important context. Enables bots to maintain coherent conversations
even across extended interactions.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """A single message in a conversation."""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)
    token_estimate: int = 0

    def __post_init__(self):
        if self.token_estimate == 0:
            # Rough estimate: ~4 chars per token
            self.token_estimate = len(self.content) // 4 + 1


@dataclass
class ConversationContext:
    """
    Holds the full context of a conversation.

    Manages message history, tracks token usage, and handles
    compaction when context grows too large.
    """
    conversation_id: str
    messages: list[Message] = field(default_factory=list)
    summary: Optional[str] = None
    max_tokens: int = 8000
    compaction_threshold: float = 0.8  # Compact at 80% of max
    metadata: dict = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        """Estimate total tokens in context."""
        base = len(self.summary) // 4 if self.summary else 0
        return base + sum(m.token_estimate for m in self.messages)

    @property
    def needs_compaction(self) -> bool:
        """Check if context should be compacted."""
        return self.total_tokens > (self.max_tokens * self.compaction_threshold)

    def add_message(self, role: str, content: str, **metadata) -> Message:
        """Add a message to the conversation."""
        msg = Message(role=role, content=content, metadata=metadata)
        self.messages.append(msg)
        return msg

    def get_recent_messages(self, count: int = 10) -> list[Message]:
        """Get the most recent messages."""
        return self.messages[-count:]

    def to_prompt_messages(self) -> list[dict]:
        """Convert to LLM prompt format."""
        result = []

        # Add summary as system context if exists
        if self.summary:
            result.append({
                "role": "system",
                "content": f"Previous conversation summary:\n{self.summary}"
            })

        # Add messages
        for msg in self.messages:
            result.append({
                "role": msg.role,
                "content": msg.content
            })

        return result


class ContextEngine:
    """
    Manages conversation contexts with intelligent compaction.

    Features:
    - Token counting and management
    - Automatic compaction when context grows too large
    - Summary generation for older messages
    - Context persistence and restoration
    """

    # Compaction settings
    BASE_CHUNK_RATIO = 0.4  # Keep 40% of old messages
    MIN_CHUNK_RATIO = 0.15  # Keep at least 15%
    SAFETY_MARGIN = 1.2  # 20% buffer for token estimation

    def __init__(self, llm_client=None):
        self._contexts: dict[str, ConversationContext] = {}
        self._llm_client = llm_client

    def get_context(self, conversation_id: str) -> ConversationContext:
        """Get or create a conversation context."""
        if conversation_id not in self._contexts:
            self._contexts[conversation_id] = ConversationContext(
                conversation_id=conversation_id
            )
        return self._contexts[conversation_id]

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        **metadata
    ) -> Message:
        """Add a message and handle compaction if needed."""
        context = self.get_context(conversation_id)
        message = context.add_message(role, content, **metadata)

        # Check if compaction needed
        if context.needs_compaction:
            self._compact_context(context)

        return message

    async def _compact_context(self, context: ConversationContext) -> None:
        """
        Compact conversation context by summarizing older messages.

        Strategy:
        1. Split messages into old (to summarize) and recent (to keep)
        2. Generate summary of old messages
        3. Replace old messages with summary
        """
        if not self._llm_client:
            logger.warning("No LLM client - using simple truncation")
            self._simple_truncate(context)
            return

        # Determine split point (keep recent 40%)
        split_idx = int(len(context.messages) * (1 - self.BASE_CHUNK_RATIO))
        old_messages = context.messages[:split_idx]
        recent_messages = context.messages[split_idx:]

        if not old_messages:
            return

        # Generate summary
        try:
            summary = await self._generate_summary(old_messages, context.summary)
            context.summary = summary
            context.messages = recent_messages
            logger.info(
                f"Compacted context {context.conversation_id}: "
                f"{len(old_messages)} messages -> summary"
            )
        except Exception as e:
            logger.error(f"Compaction failed: {e}")
            self._simple_truncate(context)

    def _simple_truncate(self, context: ConversationContext) -> None:
        """Simple truncation fallback when LLM summarization unavailable."""
        keep_count = int(len(context.messages) * self.BASE_CHUNK_RATIO)
        context.messages = context.messages[-keep_count:]

    async def _generate_summary(
        self,
        messages: list[Message],
        existing_summary: Optional[str] = None
    ) -> str:
        """Generate a summary of messages using LLM."""
        # Build prompt for summarization
        prompt = self._build_summary_prompt(messages, existing_summary)

        response = await self._llm_client.generate(
            prompt=prompt,
            system_prompt=self.SUMMARIZATION_SYSTEM_PROMPT,
            max_tokens=500,
            temperature=0.3
        )

        return response.text

    def _build_summary_prompt(
        self,
        messages: list[Message],
        existing_summary: Optional[str]
    ) -> str:
        """Build the summarization prompt."""
        parts = []

        if existing_summary:
            parts.append(f"Previous summary:\n{existing_summary}\n")

        parts.append("New messages to incorporate:\n")
        for msg in messages:
            parts.append(f"[{msg.role}]: {msg.content[:500]}...")

        parts.append("\nCreate a coherent summary preserving key context.")

        return "\n".join(parts)

    SUMMARIZATION_SYSTEM_PROMPT = """You summarize conversations while preserving critical context.

MUST PRESERVE:
- Active tasks and their current status
- The last user request and what was being done
- Decisions made and rationale
- Open questions and constraints
- Any commitments or follow-ups

PRIORITIZE recent context over older history.
Keep summaries concise but complete."""

    # Persistence methods

    def save_context(self, conversation_id: str) -> dict:
        """Serialize context for storage."""
        context = self.get_context(conversation_id)
        return {
            "conversation_id": context.conversation_id,
            "summary": context.summary,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                    "metadata": m.metadata,
                }
                for m in context.messages
            ],
            "metadata": context.metadata,
        }

    def load_context(self, data: dict) -> ConversationContext:
        """Restore context from storage."""
        context = ConversationContext(
            conversation_id=data["conversation_id"],
            summary=data.get("summary"),
            metadata=data.get("metadata", {}),
        )

        for msg_data in data.get("messages", []):
            context.messages.append(Message(
                role=msg_data["role"],
                content=msg_data["content"],
                timestamp=datetime.fromisoformat(msg_data["timestamp"]),
                metadata=msg_data.get("metadata", {}),
            ))

        self._contexts[context.conversation_id] = context
        return context

    def clear_context(self, conversation_id: str) -> None:
        """Clear a conversation context."""
        if conversation_id in self._contexts:
            del self._contexts[conversation_id]


def estimate_tokens(text: str) -> int:
    """Estimate token count for text (rough approximation)."""
    # Average ~4 characters per token for English
    return len(text) // 4 + 1


def chunk_messages(
    messages: list[Message],
    max_tokens: int,
    preserve_recent: int = 5
) -> tuple[list[Message], list[Message]]:
    """
    Split messages into (to_summarize, to_keep) based on token limit.

    Always preserves at least `preserve_recent` recent messages.
    """
    if len(messages) <= preserve_recent:
        return [], messages

    # Work backwards to find split point
    keep_tokens = 0
    split_idx = len(messages)

    for i in range(len(messages) - 1, -1, -1):
        msg_tokens = messages[i].token_estimate
        if keep_tokens + msg_tokens > max_tokens * 0.6:  # Keep 60% for recent
            split_idx = i + 1
            break
        keep_tokens += msg_tokens

    # Ensure we keep at least preserve_recent
    split_idx = min(split_idx, len(messages) - preserve_recent)
    split_idx = max(split_idx, 0)

    return messages[:split_idx], messages[split_idx:]
