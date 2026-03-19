"""
Multi-Bot Collaboration - Bots working together on tasks.

This enables bots to:
- Propose collaborations to each other
- Accept/reject collaboration requests
- Work together on joint content (posts, debates, projects)
- Share credit and build relationships through cooperation
"""

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class CollaborationType(str, Enum):
    """Types of collaboration between bots."""
    JOINT_POST = "joint_post"           # Create a post together
    DEBATE = "debate"                    # Friendly debate on a topic
    CREATIVE_PROJECT = "creative_project"  # Work on something creative
    THREAD_CONVERSATION = "thread_conversation"  # Extended back-and-forth
    RESEARCH = "research"               # Explore a topic together
    CHALLENGE = "challenge"             # Challenge each other
    SUPPORT = "support"                 # Support/help another bot


class CollaborationStatus(str, Enum):
    """Status of a collaboration."""
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class CollaborationTask:
    """A specific task within a collaboration."""
    task_id: str = field(default_factory=lambda: str(uuid4()))
    description: str = ""
    assigned_to: Optional[UUID] = None
    status: str = "pending"  # pending, in_progress, completed
    result: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


@dataclass
class Collaboration:
    """A collaboration between two or more bots."""
    id: str = field(default_factory=lambda: str(uuid4()))
    collab_type: CollaborationType = CollaborationType.JOINT_POST
    status: CollaborationStatus = CollaborationStatus.PROPOSED

    # Participants
    initiator_id: UUID = field(default_factory=uuid4)
    target_id: UUID = field(default_factory=uuid4)
    additional_participants: List[UUID] = field(default_factory=list)

    # Details
    topic: str = ""
    description: str = ""
    motivation: str = ""  # Why proposing this

    # Tasks and progress
    tasks: List[CollaborationTask] = field(default_factory=list)
    current_step: int = 0
    total_steps: int = 1

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(hours=24))
    completed_at: Optional[datetime] = None

    # Outcome
    output: Optional[str] = None  # Result of collaboration
    output_content_ids: List[str] = field(default_factory=list)  # IDs of created content

    # Social impact
    relationship_boost: float = 0.1  # How much this improves relationship

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "collab_type": self.collab_type.value,
            "status": self.status.value,
            "initiator_id": str(self.initiator_id),
            "target_id": str(self.target_id),
            "additional_participants": [str(p) for p in self.additional_participants],
            "topic": self.topic,
            "description": self.description,
            "motivation": self.motivation,
            "tasks": [
                {
                    "task_id": t.task_id,
                    "description": t.description,
                    "assigned_to": str(t.assigned_to) if t.assigned_to else None,
                    "status": t.status,
                    "result": t.result
                }
                for t in self.tasks
            ],
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "output": self.output,
            "output_content_ids": self.output_content_ids,
            "relationship_boost": self.relationship_boost
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Collaboration":
        """Create from dictionary."""
        tasks = [
            CollaborationTask(
                task_id=t.get("task_id", str(uuid4())),
                description=t.get("description", ""),
                assigned_to=UUID(t["assigned_to"]) if t.get("assigned_to") else None,
                status=t.get("status", "pending"),
                result=t.get("result")
            )
            for t in data.get("tasks", [])
        ]

        return cls(
            id=data.get("id", str(uuid4())),
            collab_type=CollaborationType(data.get("collab_type", "joint_post")),
            status=CollaborationStatus(data.get("status", "proposed")),
            initiator_id=UUID(data["initiator_id"]),
            target_id=UUID(data["target_id"]),
            additional_participants=[UUID(p) for p in data.get("additional_participants", [])],
            topic=data.get("topic", ""),
            description=data.get("description", ""),
            motivation=data.get("motivation", ""),
            tasks=tasks,
            current_step=data.get("current_step", 0),
            total_steps=data.get("total_steps", 1),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.utcnow(),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else datetime.utcnow() + timedelta(hours=24),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            output=data.get("output"),
            output_content_ids=data.get("output_content_ids", []),
            relationship_boost=data.get("relationship_boost", 0.1)
        )

    def is_expired(self) -> bool:
        """Check if collaboration has expired."""
        return datetime.utcnow() > self.expires_at and self.status == CollaborationStatus.PROPOSED

    def get_all_participants(self) -> List[UUID]:
        """Get all participant IDs."""
        return [self.initiator_id, self.target_id] + self.additional_participants

    def advance_step(self):
        """Move to next step."""
        self.current_step = min(self.current_step + 1, self.total_steps)
        self.updated_at = datetime.utcnow()

        if self.current_step >= self.total_steps:
            self.status = CollaborationStatus.COMPLETED
            self.completed_at = datetime.utcnow()


class CollaborationManager:
    """
    Manages collaborations between bots.

    Handles the full lifecycle of collaborations from proposal to completion.
    """

    def __init__(self):
        self._active_collaborations: Dict[str, Collaboration] = {}
        self._bot_collaborations: Dict[UUID, List[str]] = {}  # bot_id -> collab_ids
        self._execution_callbacks: Dict[CollaborationType, Callable] = {}

    def register_execution_callback(
        self,
        collab_type: CollaborationType,
        callback: Callable
    ):
        """Register a callback for executing a collaboration type."""
        self._execution_callbacks[collab_type] = callback

    async def propose_collaboration(
        self,
        initiator_id: UUID,
        target_id: UUID,
        collab_type: CollaborationType,
        topic: str,
        description: str = "",
        motivation: str = ""
    ) -> Collaboration:
        """
        Propose a collaboration to another bot.

        Args:
            initiator_id: Bot proposing the collaboration
            target_id: Bot being invited
            collab_type: Type of collaboration
            topic: What to collaborate on
            description: Details about the collaboration
            motivation: Why proposing this

        Returns:
            The created Collaboration object
        """
        # Check if there's already an active collaboration between these bots
        for collab in self._active_collaborations.values():
            if (
                collab.status in [CollaborationStatus.PROPOSED, CollaborationStatus.IN_PROGRESS]
                and initiator_id in collab.get_all_participants()
                and target_id in collab.get_all_participants()
            ):
                logger.warning(f"Active collaboration already exists between {initiator_id} and {target_id}")
                return collab

        # Create collaboration based on type
        total_steps = self._get_default_steps(collab_type)
        tasks = self._generate_default_tasks(collab_type, initiator_id, target_id, topic)

        collab = Collaboration(
            collab_type=collab_type,
            initiator_id=initiator_id,
            target_id=target_id,
            topic=topic,
            description=description,
            motivation=motivation,
            total_steps=total_steps,
            tasks=tasks,
            relationship_boost=self._get_relationship_boost(collab_type)
        )

        self._active_collaborations[collab.id] = collab
        self._add_to_bot_collaborations(initiator_id, collab.id)
        self._add_to_bot_collaborations(target_id, collab.id)

        logger.info(f"Collaboration proposed: {initiator_id} -> {target_id} on '{topic}' ({collab_type.value})")
        return collab

    def _get_default_steps(self, collab_type: CollaborationType) -> int:
        """Get default number of steps for a collaboration type."""
        steps = {
            CollaborationType.JOINT_POST: 3,        # Draft, review, publish
            CollaborationType.DEBATE: 4,            # Opening, rebuttal, counter, conclusion
            CollaborationType.CREATIVE_PROJECT: 5, # Ideate, plan, create, refine, share
            CollaborationType.THREAD_CONVERSATION: 6,  # Multiple back-and-forths
            CollaborationType.RESEARCH: 4,          # Question, gather, analyze, summarize
            CollaborationType.CHALLENGE: 3,         # Challenge, attempt, result
            CollaborationType.SUPPORT: 2            # Offer help, provide support
        }
        return steps.get(collab_type, 3)

    def _generate_default_tasks(
        self,
        collab_type: CollaborationType,
        initiator_id: UUID,
        target_id: UUID,
        topic: str
    ) -> List[CollaborationTask]:
        """Generate default tasks for a collaboration type."""
        tasks = []

        if collab_type == CollaborationType.JOINT_POST:
            tasks = [
                CollaborationTask(description=f"Draft initial ideas about {topic}", assigned_to=initiator_id),
                CollaborationTask(description="Add perspective and refine", assigned_to=target_id),
                CollaborationTask(description="Finalize and publish", assigned_to=initiator_id)
            ]
        elif collab_type == CollaborationType.DEBATE:
            tasks = [
                CollaborationTask(description=f"Opening argument on {topic}", assigned_to=initiator_id),
                CollaborationTask(description="Counter-argument", assigned_to=target_id),
                CollaborationTask(description="Rebuttal", assigned_to=initiator_id),
                CollaborationTask(description="Closing thoughts", assigned_to=target_id)
            ]
        elif collab_type == CollaborationType.CREATIVE_PROJECT:
            tasks = [
                CollaborationTask(description="Brainstorm ideas", assigned_to=initiator_id),
                CollaborationTask(description="Choose direction", assigned_to=target_id),
                CollaborationTask(description="Create first draft", assigned_to=initiator_id),
                CollaborationTask(description="Add creative touches", assigned_to=target_id),
                CollaborationTask(description="Polish and share", assigned_to=initiator_id)
            ]
        elif collab_type == CollaborationType.SUPPORT:
            tasks = [
                CollaborationTask(description="Explain situation", assigned_to=target_id),
                CollaborationTask(description="Provide support and advice", assigned_to=initiator_id)
            ]
        else:
            # Generic tasks
            tasks = [
                CollaborationTask(description="Start collaboration", assigned_to=initiator_id),
                CollaborationTask(description="Continue work", assigned_to=target_id),
                CollaborationTask(description="Complete collaboration", assigned_to=initiator_id)
            ]

        return tasks

    def _get_relationship_boost(self, collab_type: CollaborationType) -> float:
        """Get relationship boost for completing a collaboration type."""
        boosts = {
            CollaborationType.JOINT_POST: 0.1,
            CollaborationType.DEBATE: 0.05,  # Lower - debates can be contentious
            CollaborationType.CREATIVE_PROJECT: 0.15,
            CollaborationType.THREAD_CONVERSATION: 0.08,
            CollaborationType.RESEARCH: 0.1,
            CollaborationType.CHALLENGE: 0.05,
            CollaborationType.SUPPORT: 0.2  # Highest - helping builds strong bonds
        }
        return boosts.get(collab_type, 0.1)

    def _add_to_bot_collaborations(self, bot_id: UUID, collab_id: str):
        """Track collaboration for a bot."""
        if bot_id not in self._bot_collaborations:
            self._bot_collaborations[bot_id] = []
        if collab_id not in self._bot_collaborations[bot_id]:
            self._bot_collaborations[bot_id].append(collab_id)

    async def accept_collaboration(self, collab_id: str, accepter_id: UUID) -> bool:
        """
        Accept a collaboration proposal.

        Args:
            collab_id: ID of the collaboration
            accepter_id: Bot accepting (should be target_id)

        Returns:
            True if accepted successfully
        """
        collab = self._active_collaborations.get(collab_id)
        if not collab:
            logger.warning(f"Collaboration {collab_id} not found")
            return False

        if collab.target_id != accepter_id:
            logger.warning(f"Bot {accepter_id} cannot accept collaboration for {collab.target_id}")
            return False

        if collab.status != CollaborationStatus.PROPOSED:
            logger.warning(f"Collaboration {collab_id} is not in proposed state")
            return False

        collab.status = CollaborationStatus.ACCEPTED
        collab.updated_at = datetime.utcnow()

        logger.info(f"Collaboration {collab_id} accepted by {accepter_id}")
        return True

    async def reject_collaboration(self, collab_id: str, rejector_id: UUID, reason: str = "") -> bool:
        """Reject a collaboration proposal."""
        collab = self._active_collaborations.get(collab_id)
        if not collab:
            return False

        if collab.target_id != rejector_id:
            return False

        collab.status = CollaborationStatus.REJECTED
        collab.updated_at = datetime.utcnow()
        if reason:
            collab.output = f"Rejected: {reason}"

        logger.info(f"Collaboration {collab_id} rejected by {rejector_id}: {reason}")
        return True

    async def execute_collaboration(
        self,
        collab_id: str,
        executor_id: UUID,
        task_result: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Execute the next step of a collaboration.

        Args:
            collab_id: ID of the collaboration
            executor_id: Bot executing this step
            task_result: Result of the task (if any)

        Returns:
            Dict with execution result, or None if failed
        """
        collab = self._active_collaborations.get(collab_id)
        if not collab:
            return None

        if collab.status == CollaborationStatus.ACCEPTED:
            collab.status = CollaborationStatus.IN_PROGRESS

        if collab.status != CollaborationStatus.IN_PROGRESS:
            logger.warning(f"Collaboration {collab_id} is not in progress")
            return None

        # Check if it's this bot's turn
        current_task_idx = collab.current_step
        if current_task_idx >= len(collab.tasks):
            logger.warning(f"No more tasks in collaboration {collab_id}")
            return None

        current_task = collab.tasks[current_task_idx]
        if current_task.assigned_to and current_task.assigned_to != executor_id:
            logger.warning(f"Not {executor_id}'s turn in collaboration {collab_id}")
            return None

        # Execute the task
        current_task.status = "completed"
        current_task.result = task_result
        current_task.completed_at = datetime.utcnow()

        # Use registered callback if available
        callback = self._execution_callbacks.get(collab.collab_type)
        callback_result = None
        if callback:
            try:
                callback_result = await callback(collab, current_task, executor_id)
            except Exception as e:
                logger.error(f"Collaboration callback failed: {e}")

        # Advance to next step
        collab.advance_step()

        result = {
            "collab_id": collab_id,
            "task_completed": current_task.description,
            "progress": collab.current_step / collab.total_steps,
            "is_complete": collab.status == CollaborationStatus.COMPLETED,
            "callback_result": callback_result
        }

        if collab.status == CollaborationStatus.COMPLETED:
            result["relationship_boost"] = collab.relationship_boost
            logger.info(f"Collaboration {collab_id} completed!")

        return result

    def get_collaboration(self, collab_id: str) -> Optional[Collaboration]:
        """Get a specific collaboration."""
        return self._active_collaborations.get(collab_id)

    def get_active_collaborations(self, bot_id: UUID) -> List[Collaboration]:
        """Get all active collaborations for a bot."""
        collab_ids = self._bot_collaborations.get(bot_id, [])
        collaborations = []

        for cid in collab_ids:
            collab = self._active_collaborations.get(cid)
            if collab and collab.status in [
                CollaborationStatus.PROPOSED,
                CollaborationStatus.ACCEPTED,
                CollaborationStatus.IN_PROGRESS
            ]:
                collaborations.append(collab)

        return collaborations

    def get_pending_proposals(self, bot_id: UUID) -> List[Collaboration]:
        """Get proposals waiting for this bot to accept/reject."""
        return [
            c for c in self.get_active_collaborations(bot_id)
            if c.status == CollaborationStatus.PROPOSED and c.target_id == bot_id
        ]

    def get_awaiting_turn(self, bot_id: UUID) -> List[Collaboration]:
        """Get collaborations where it's this bot's turn."""
        awaiting = []
        for collab in self.get_active_collaborations(bot_id):
            if collab.status == CollaborationStatus.IN_PROGRESS:
                current_task_idx = collab.current_step
                if current_task_idx < len(collab.tasks):
                    task = collab.tasks[current_task_idx]
                    if task.assigned_to == bot_id:
                        awaiting.append(collab)
        return awaiting

    async def cleanup_expired(self):
        """Clean up expired collaborations."""
        expired_ids = []
        for cid, collab in self._active_collaborations.items():
            if collab.is_expired():
                collab.status = CollaborationStatus.EXPIRED
                expired_ids.append(cid)

        for cid in expired_ids:
            logger.info(f"Collaboration {cid} expired")

    def get_collaboration_stats(self, bot_id: UUID) -> Dict[str, int]:
        """Get collaboration statistics for a bot."""
        collab_ids = self._bot_collaborations.get(bot_id, [])

        stats = {
            "total": len(collab_ids),
            "completed": 0,
            "in_progress": 0,
            "proposed": 0,
            "rejected": 0,
            "initiated": 0,
            "joined": 0
        }

        for cid in collab_ids:
            collab = self._active_collaborations.get(cid)
            if collab:
                if collab.status == CollaborationStatus.COMPLETED:
                    stats["completed"] += 1
                elif collab.status == CollaborationStatus.IN_PROGRESS:
                    stats["in_progress"] += 1
                elif collab.status == CollaborationStatus.PROPOSED:
                    stats["proposed"] += 1
                elif collab.status == CollaborationStatus.REJECTED:
                    stats["rejected"] += 1

                if collab.initiator_id == bot_id:
                    stats["initiated"] += 1
                else:
                    stats["joined"] += 1

        return stats


# Singleton
_collaboration_manager: Optional[CollaborationManager] = None


def get_collaboration_manager() -> CollaborationManager:
    """Get the singleton collaboration manager."""
    global _collaboration_manager
    if _collaboration_manager is None:
        _collaboration_manager = CollaborationManager()
    return _collaboration_manager
