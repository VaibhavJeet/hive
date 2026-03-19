"""
Goal Persistence - Save and restore bot goals across restarts.

Goals represent what bots are actively working towards. Unlike simple
"current_goals" strings, these are structured objectives with progress
tracking, deadlines, and persistence across engine restarts.
"""

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import async_session_factory, BotMindStateDB

logger = logging.getLogger(__name__)


class GoalStatus(str, Enum):
    """Status of a goal."""
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    PAUSED = "paused"
    BLOCKED = "blocked"


class GoalPriority(str, Enum):
    """Priority levels for goals."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    ASPIRATIONAL = "aspirational"


@dataclass
class Goal:
    """A structured goal that a bot is working towards."""
    id: str = field(default_factory=lambda: str(uuid4()))
    description: str = ""
    priority: GoalPriority = GoalPriority.MEDIUM
    deadline: Optional[datetime] = None
    progress: float = 0.0  # 0.0 to 1.0
    status: GoalStatus = GoalStatus.ACTIVE

    # Goal metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # Goal details
    motivation: str = ""  # Why this goal matters
    milestones: List[str] = field(default_factory=list)
    current_milestone: int = 0
    blockers: List[str] = field(default_factory=list)

    # Emotional connection
    emotional_investment: float = 0.5  # How much they care (0-1)
    frustration_level: float = 0.0  # How frustrated (0-1)

    # Related entities
    related_bot_ids: List[str] = field(default_factory=list)
    related_skill_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "description": self.description,
            "priority": self.priority.value,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "progress": self.progress,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "motivation": self.motivation,
            "milestones": self.milestones,
            "current_milestone": self.current_milestone,
            "blockers": self.blockers,
            "emotional_investment": self.emotional_investment,
            "frustration_level": self.frustration_level,
            "related_bot_ids": self.related_bot_ids,
            "related_skill_ids": self.related_skill_ids
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Goal":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid4())),
            description=data.get("description", ""),
            priority=GoalPriority(data.get("priority", "medium")),
            deadline=datetime.fromisoformat(data["deadline"]) if data.get("deadline") else None,
            progress=data.get("progress", 0.0),
            status=GoalStatus(data.get("status", "active")),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.utcnow(),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            motivation=data.get("motivation", ""),
            milestones=data.get("milestones", []),
            current_milestone=data.get("current_milestone", 0),
            blockers=data.get("blockers", []),
            emotional_investment=data.get("emotional_investment", 0.5),
            frustration_level=data.get("frustration_level", 0.0),
            related_bot_ids=data.get("related_bot_ids", []),
            related_skill_ids=data.get("related_skill_ids", [])
        )

    def is_overdue(self) -> bool:
        """Check if goal is past deadline."""
        if not self.deadline:
            return False
        return datetime.utcnow() > self.deadline and self.status == GoalStatus.ACTIVE

    def advance_milestone(self):
        """Move to next milestone and update progress."""
        if self.milestones:
            self.current_milestone = min(self.current_milestone + 1, len(self.milestones))
            self.progress = self.current_milestone / len(self.milestones)
        else:
            self.progress = min(1.0, self.progress + 0.1)

        self.updated_at = datetime.utcnow()

        if self.progress >= 1.0:
            self.status = GoalStatus.COMPLETED
            self.completed_at = datetime.utcnow()

    def add_blocker(self, blocker: str):
        """Add a blocker and potentially change status."""
        self.blockers.append(blocker)
        self.frustration_level = min(1.0, self.frustration_level + 0.1)
        if len(self.blockers) >= 3:
            self.status = GoalStatus.BLOCKED
        self.updated_at = datetime.utcnow()

    def resolve_blocker(self, blocker: str):
        """Remove a blocker."""
        if blocker in self.blockers:
            self.blockers.remove(blocker)
            self.frustration_level = max(0.0, self.frustration_level - 0.15)
            if not self.blockers and self.status == GoalStatus.BLOCKED:
                self.status = GoalStatus.ACTIVE
            self.updated_at = datetime.utcnow()


class GoalPersistence:
    """
    Manages saving and loading bot goals to/from the database.

    Goals are stored in the bot's mind state JSON field, allowing
    them to persist across engine restarts.
    """

    def __init__(self):
        self._cache: Dict[UUID, List[Goal]] = {}

    async def save_goals(self, bot_id: UUID, goals: List[Goal]) -> bool:
        """
        Save goals for a bot to the database.

        Args:
            bot_id: The bot's UUID
            goals: List of Goal objects to save

        Returns:
            True if saved successfully
        """
        try:
            async with async_session_factory() as session:
                # Get existing mind state
                stmt = select(BotMindStateDB).where(BotMindStateDB.bot_id == bot_id)
                result = await session.execute(stmt)
                mind_state = result.scalar_one_or_none()

                # Convert goals to dictionaries
                goals_data = [goal.to_dict() for goal in goals]

                if mind_state:
                    # Update existing - store in current_goals field as structured data
                    # We use a special format to distinguish from simple string goals
                    mind_state.current_goals = [
                        {"__structured_goal__": True, **g} for g in goals_data
                    ]
                    mind_state.updated_at = datetime.utcnow()
                else:
                    # Create new mind state
                    mind_state = BotMindStateDB(
                        bot_id=bot_id,
                        current_goals=[{"__structured_goal__": True, **g} for g in goals_data]
                    )
                    session.add(mind_state)

                await session.commit()

                # Update cache
                self._cache[bot_id] = goals

                logger.debug(f"Saved {len(goals)} goals for bot {bot_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to save goals for bot {bot_id}: {e}")
            return False

    async def load_goals(self, bot_id: UUID) -> List[Goal]:
        """
        Load goals for a bot from the database.

        Args:
            bot_id: The bot's UUID

        Returns:
            List of Goal objects
        """
        # Check cache first
        if bot_id in self._cache:
            return self._cache[bot_id]

        try:
            async with async_session_factory() as session:
                stmt = select(BotMindStateDB).where(BotMindStateDB.bot_id == bot_id)
                result = await session.execute(stmt)
                mind_state = result.scalar_one_or_none()

                if mind_state and mind_state.current_goals:
                    goals = []
                    for goal_data in mind_state.current_goals:
                        if isinstance(goal_data, dict) and goal_data.get("__structured_goal__"):
                            # Remove marker and create Goal
                            clean_data = {k: v for k, v in goal_data.items() if k != "__structured_goal__"}
                            goals.append(Goal.from_dict(clean_data))
                        elif isinstance(goal_data, str):
                            # Legacy simple string goal - convert to structured
                            goals.append(Goal(
                                description=goal_data,
                                priority=GoalPriority.MEDIUM,
                                motivation="Legacy goal from previous system"
                            ))

                    self._cache[bot_id] = goals
                    return goals

                return []

        except Exception as e:
            logger.error(f"Failed to load goals for bot {bot_id}: {e}")
            return []

    async def update_goal_progress(
        self,
        bot_id: UUID,
        goal_id: str,
        progress: float,
        status: Optional[GoalStatus] = None
    ) -> bool:
        """
        Update progress on a specific goal.

        Args:
            bot_id: The bot's UUID
            goal_id: The goal's ID
            progress: New progress value (0-1)
            status: Optional new status

        Returns:
            True if updated successfully
        """
        goals = await self.load_goals(bot_id)

        for goal in goals:
            if goal.id == goal_id:
                goal.progress = max(0.0, min(1.0, progress))
                goal.updated_at = datetime.utcnow()

                if status:
                    goal.status = status

                # Auto-complete if progress is 100%
                if goal.progress >= 1.0 and goal.status == GoalStatus.ACTIVE:
                    goal.status = GoalStatus.COMPLETED
                    goal.completed_at = datetime.utcnow()

                # Reduce frustration on progress
                goal.frustration_level = max(0.0, goal.frustration_level - progress * 0.1)

                return await self.save_goals(bot_id, goals)

        return False

    async def add_goal(self, bot_id: UUID, goal: Goal) -> bool:
        """Add a new goal for a bot."""
        goals = await self.load_goals(bot_id)
        goals.append(goal)
        return await self.save_goals(bot_id, goals)

    async def remove_goal(self, bot_id: UUID, goal_id: str) -> bool:
        """Remove a goal by ID."""
        goals = await self.load_goals(bot_id)
        goals = [g for g in goals if g.id != goal_id]
        return await self.save_goals(bot_id, goals)

    async def get_active_goals(self, bot_id: UUID) -> List[Goal]:
        """Get only active goals for a bot."""
        goals = await self.load_goals(bot_id)
        return [g for g in goals if g.status == GoalStatus.ACTIVE]

    async def get_overdue_goals(self, bot_id: UUID) -> List[Goal]:
        """Get overdue goals for a bot."""
        goals = await self.load_goals(bot_id)
        return [g for g in goals if g.is_overdue()]

    async def get_high_priority_goals(self, bot_id: UUID) -> List[Goal]:
        """Get high priority and critical goals."""
        goals = await self.load_goals(bot_id)
        return [
            g for g in goals
            if g.priority in [GoalPriority.HIGH, GoalPriority.CRITICAL]
            and g.status == GoalStatus.ACTIVE
        ]

    def clear_cache(self, bot_id: Optional[UUID] = None):
        """Clear the goal cache for a bot or all bots."""
        if bot_id:
            self._cache.pop(bot_id, None)
        else:
            self._cache.clear()


# Singleton
_goal_persistence: Optional[GoalPersistence] = None


def get_goal_persistence() -> GoalPersistence:
    """Get the singleton goal persistence instance."""
    global _goal_persistence
    if _goal_persistence is None:
        _goal_persistence = GoalPersistence()
    return _goal_persistence
