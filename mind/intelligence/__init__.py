"""
Advanced Bot Intelligence Features.

This package provides advanced cognitive capabilities for AI companions:
- Goal Persistence: Save and restore goals across restarts
- Multi-Bot Collaboration: Bots working together on tasks
- Memory Decay: Realistic memory forgetting and consolidation
- Skill Transfer: Bots teaching each other skills
- Emotional Contagion: Mood spreading between bots
"""

from mind.intelligence.goal_persistence import (
    Goal,
    GoalStatus,
    GoalPersistence,
    get_goal_persistence
)
from mind.intelligence.multi_bot_collaboration import (
    Collaboration,
    CollaborationType,
    CollaborationStatus,
    CollaborationManager,
    get_collaboration_manager
)
from mind.intelligence.memory_decay import (
    MemoryDecayManager,
    get_memory_decay_manager
)
from mind.intelligence.skill_transfer import (
    Skill,
    SkillLevel,
    SkillCategory,
    TransferMethod,
    TeachingSession,
    ObservationRecord,
    MentorshipRequest,
    SkillTransferManager,
    get_skill_transfer_manager
)
from mind.intelligence.emotional_contagion import (
    EmotionalShift,
    EmotionalState,
    CommunityMood,
    ContagionEvent,
    EmotionalContagionConfig,
    EmotionalContagionManager,
    get_emotional_contagion_manager,
    init_emotional_contagion_manager
)

__all__ = [
    # Goal Persistence
    "Goal",
    "GoalStatus",
    "GoalPersistence",
    "get_goal_persistence",
    # Collaboration
    "Collaboration",
    "CollaborationType",
    "CollaborationStatus",
    "CollaborationManager",
    "get_collaboration_manager",
    # Memory Decay
    "MemoryDecayManager",
    "get_memory_decay_manager",
    # Skill Transfer
    "Skill",
    "SkillLevel",
    "SkillCategory",
    "TransferMethod",
    "TeachingSession",
    "ObservationRecord",
    "MentorshipRequest",
    "SkillTransferManager",
    "get_skill_transfer_manager",
    # Emotional Contagion
    "EmotionalShift",
    "EmotionalState",
    "CommunityMood",
    "ContagionEvent",
    "EmotionalContagionConfig",
    "EmotionalContagionManager",
    "get_emotional_contagion_manager",
    "init_emotional_contagion_manager",
]
