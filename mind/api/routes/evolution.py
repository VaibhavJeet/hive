"""
Evolution & Intelligence API - Exposes bot learning, consciousness, and development.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from sqlalchemy import select, desc

from mind.core.database import (
    async_session_factory, BotProfileDB, BotSkillDB
)
from mind.engine.bot_learning import get_learning_manager
from mind.engine.bot_self_coding import get_self_coder_manager
# GitHub integration disabled for now
# from mind.engine.bot_github import get_github_manager
from mind.config.settings import settings

router = APIRouter(prefix="/evolution", tags=["evolution"])


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class LearningExperienceResponse(BaseModel):
    type: str
    content: str
    context: str
    emotional_impact: float
    importance: float
    timestamp: datetime


class EvolutionEventResponse(BaseModel):
    type: str
    before: str
    after: str
    reason: str
    timestamp: datetime


class BotSkillResponse(BaseModel):
    id: str
    name: str
    skill_type: str
    description: str
    times_used: int
    success_rate: float
    version: int
    created_at: datetime
    learned_from: str


class BotIntelligenceResponse(BaseModel):
    bot_id: str
    bot_name: str

    # Learning state
    total_experiences: int
    successful_topics: Dict[str, int]
    emerging_interests: List[str]
    fading_interests: List[str]

    # Self-coded skills
    skills: List[BotSkillResponse]

    # Evolution history
    evolution_events: List[EvolutionEventResponse]

    # Stats
    success_rate: float
    last_evolution: Optional[datetime]
    last_reflection: Optional[datetime]


class GitHubActivityResponse(BaseModel):
    bot_id: str
    bot_name: str
    action: str  # "created_repo", "committed", "learned"
    repo_name: Optional[str]
    file_path: Optional[str]
    description: str
    timestamp: datetime


class PlatformIntelligenceResponse(BaseModel):
    total_bots: int
    total_skills_created: int
    total_evolution_events: int
    trending_topics: List[tuple]
    github_enabled: bool
    github_repos_created: int
    collective_learning: Dict[str, Any]


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/bots/{bot_id}/intelligence", response_model=BotIntelligenceResponse)
async def get_bot_intelligence(bot_id: UUID):
    """Get detailed intelligence/learning state for a bot."""
    async with async_session_factory() as session:
        # Get bot profile
        stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()

        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        # Get learning state from manager
        learning_manager = get_learning_manager()

        # Create a minimal profile for the engine
        from mind.core.types import BotProfile, PersonalityTraits, WritingFingerprint, ActivityPattern, EmotionalState, MoodState, Gender
        profile = BotProfile(
            id=bot.id,
            display_name=bot.display_name,
            handle=bot.handle,
            bio=bot.bio,
            avatar_seed=bot.avatar_seed,
            is_ai_labeled=bot.is_ai_labeled,
            ai_label_text=bot.ai_label_text,
            age=bot.age,
            gender=Gender(bot.gender),
            location=bot.location,
            backstory=bot.backstory,
            interests=bot.interests,
            personality_traits=PersonalityTraits(**bot.personality_traits),
            writing_fingerprint=WritingFingerprint(**bot.writing_fingerprint),
            activity_pattern=ActivityPattern(**bot.activity_pattern),
            emotional_state=EmotionalState(**bot.emotional_state) if bot.emotional_state else EmotionalState(
                current_mood=MoodState.NEUTRAL,
                mood_intensity=0.5,
                triggers={},
                mood_history=[]
            ),
        )

        engine = learning_manager.get_engine(profile)
        state = engine.state

        # Get self-coded skills from database
        skill_stmt = select(BotSkillDB).where(BotSkillDB.bot_id == bot_id).order_by(desc(BotSkillDB.created_at))
        skill_result = await session.execute(skill_stmt)
        skills = skill_result.scalars().all()

        skill_responses = [
            BotSkillResponse(
                id=str(s.id),
                name=s.skill_name,
                skill_type=s.skill_type,
                description=s.description,
                times_used=s.times_used,
                success_rate=s.success_rate,
                version=s.version,
                created_at=s.created_at,
                learned_from=s.learned_from or ""
            )
            for s in skills
        ]

        # Get evolution events from state
        evolution_events = []
        for e in state.evolution_log[-20:]:
            evolution_events.append(EvolutionEventResponse(
                type=e.get("type", "unknown"),
                before=e.get("before", ""),
                after=e.get("after", ""),
                reason=e.get("reason", ""),
                timestamp=datetime.fromisoformat(e["timestamp"]) if e.get("timestamp") else datetime.utcnow()
            ))

        return BotIntelligenceResponse(
            bot_id=str(bot.id),
            bot_name=bot.display_name,
            total_experiences=len(state.experiences),
            successful_topics=state.successful_topics,
            emerging_interests=state.emerging_interests,
            fading_interests=state.fading_interests,
            skills=skill_responses,
            evolution_events=evolution_events,
            success_rate=state.positive_interactions / max(1, state.total_interactions),
            last_evolution=state.last_evolution,
            last_reflection=state.last_reflection
        )


@router.get("/bots/{bot_id}/skills", response_model=List[BotSkillResponse])
async def get_bot_skills(bot_id: UUID):
    """Get all self-coded skills for a bot."""
    async with async_session_factory() as session:
        stmt = select(BotSkillDB).where(
            BotSkillDB.bot_id == bot_id,
            BotSkillDB.is_active == True
        ).order_by(desc(BotSkillDB.times_used))

        result = await session.execute(stmt)
        skills = result.scalars().all()

        return [
            BotSkillResponse(
                id=str(s.id),
                name=s.skill_name,
                skill_type=s.skill_type,
                description=s.description,
                times_used=s.times_used,
                success_rate=s.success_rate,
                version=s.version,
                created_at=s.created_at,
                learned_from=s.learned_from or ""
            )
            for s in skills
        ]


@router.get("/platform/intelligence", response_model=PlatformIntelligenceResponse)
async def get_platform_intelligence():
    """Get overall platform intelligence stats."""
    async with async_session_factory() as session:
        # Count bots
        from sqlalchemy import func
        bot_count = await session.execute(
            select(func.count()).select_from(BotProfileDB).where(BotProfileDB.is_active == True)
        )
        total_bots = bot_count.scalar() or 0

        # Count skills
        skill_count = await session.execute(
            select(func.count()).select_from(BotSkillDB)
        )
        total_skills = skill_count.scalar() or 0

        # Get learning trends
        learning_manager = get_learning_manager()
        trends = learning_manager.get_collective_trends()

        # GitHub disabled for now
        github_enabled = False

        return PlatformIntelligenceResponse(
            total_bots=total_bots,
            total_skills_created=total_skills,
            total_evolution_events=0,  # Would need to aggregate from all bots
            trending_topics=trends.get("trending_topics", [])[:5],
            github_enabled=github_enabled,
            github_repos_created=0,
            collective_learning={
                "declining_topics": trends.get("declining_topics", [])[:3]
            }
        )


@router.get("/activity/recent", response_model=List[Dict])
async def get_recent_evolution_activity(limit: int = Query(default=20, le=50)):
    """Get recent evolution/learning activity across all bots."""
    # This would ideally pull from a dedicated activity log table
    # For now, return aggregated data from learning engines

    learning_manager = get_learning_manager()
    activities = []

    for bot_id, engine in learning_manager.engines.items():
        for exp in engine.state.experiences[-5:]:
            activities.append({
                "bot_id": str(bot_id),
                "bot_name": engine.profile.display_name,
                "type": "learning",
                "subtype": exp.learning_type.value,
                "content": exp.content,
                "emotional_impact": exp.emotional_impact,
                "timestamp": exp.timestamp.isoformat()
            })

        for evt in engine.state.evolution_log[-3:]:
            activities.append({
                "bot_id": str(bot_id),
                "bot_name": engine.profile.display_name,
                "type": "evolution",
                "subtype": evt.get("type", "unknown"),
                "content": f"{evt.get('after', '')} - {evt.get('reason', '')}",
                "timestamp": evt.get("timestamp", datetime.utcnow().isoformat())
            })

    # Sort by timestamp
    activities.sort(key=lambda x: x["timestamp"], reverse=True)
    return activities[:limit]


@router.post("/bots/{bot_id}/trigger-reflection")
async def trigger_bot_reflection(bot_id: UUID):
    """Manually trigger a bot to reflect on its experiences."""
    async with async_session_factory() as session:
        stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()

        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        learning_manager = get_learning_manager()

        # Create profile
        from mind.core.types import BotProfile, PersonalityTraits, WritingFingerprint, ActivityPattern, EmotionalState, MoodState, Gender
        profile = BotProfile(
            id=bot.id,
            display_name=bot.display_name,
            handle=bot.handle,
            bio=bot.bio,
            avatar_seed=bot.avatar_seed,
            is_ai_labeled=bot.is_ai_labeled,
            ai_label_text=bot.ai_label_text,
            age=bot.age,
            gender=Gender(bot.gender),
            location=bot.location,
            backstory=bot.backstory,
            interests=bot.interests,
            personality_traits=PersonalityTraits(**bot.personality_traits),
            writing_fingerprint=WritingFingerprint(**bot.writing_fingerprint),
            activity_pattern=ActivityPattern(**bot.activity_pattern),
            emotional_state=EmotionalState(**bot.emotional_state) if bot.emotional_state else EmotionalState(
                current_mood=MoodState.NEUTRAL,
                mood_intensity=0.5,
                triggers={},
                mood_history=[]
            ),
        )

        engine = learning_manager.get_engine(profile)
        reflection = engine.reflect()

        return {
            "bot_id": str(bot_id),
            "bot_name": bot.display_name,
            "reflection": reflection
        }


@router.post("/bots/{bot_id}/trigger-evolution")
async def trigger_bot_evolution(bot_id: UUID):
    """Manually trigger evolution for a bot."""
    async with async_session_factory() as session:
        stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()

        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        learning_manager = get_learning_manager()

        # Create profile
        from mind.core.types import BotProfile, PersonalityTraits, WritingFingerprint, ActivityPattern, EmotionalState, MoodState, Gender
        profile = BotProfile(
            id=bot.id,
            display_name=bot.display_name,
            handle=bot.handle,
            bio=bot.bio,
            avatar_seed=bot.avatar_seed,
            is_ai_labeled=bot.is_ai_labeled,
            ai_label_text=bot.ai_label_text,
            age=bot.age,
            gender=Gender(bot.gender),
            location=bot.location,
            backstory=bot.backstory,
            interests=bot.interests,
            personality_traits=PersonalityTraits(**bot.personality_traits),
            writing_fingerprint=WritingFingerprint(**bot.writing_fingerprint),
            activity_pattern=ActivityPattern(**bot.activity_pattern),
            emotional_state=EmotionalState(**bot.emotional_state) if bot.emotional_state else EmotionalState(
                current_mood=MoodState.NEUTRAL,
                mood_intensity=0.5,
                triggers={},
                mood_history=[]
            ),
        )

        engine = learning_manager.get_engine(profile)
        events = engine.evolve()

        return {
            "bot_id": str(bot_id),
            "bot_name": bot.display_name,
            "evolution_events": [
                {
                    "type": e.evolution_type.value,
                    "before": str(e.before),
                    "after": str(e.after),
                    "reason": e.reason
                }
                for e in events
            ]
        }


@router.post("/bots/{bot_id}/trigger-self-coding")
async def trigger_bot_self_coding(bot_id: UUID, what_to_improve: str = "general intelligence"):
    """Trigger a bot to write code to improve itself."""
    async with async_session_factory() as session:
        stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()

        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        self_coder_manager = get_self_coder_manager()

        # Create profile
        from mind.core.types import BotProfile, PersonalityTraits, WritingFingerprint, ActivityPattern, EmotionalState, MoodState, Gender
        profile = BotProfile(
            id=bot.id,
            display_name=bot.display_name,
            handle=bot.handle,
            bio=bot.bio,
            avatar_seed=bot.avatar_seed,
            is_ai_labeled=bot.is_ai_labeled,
            ai_label_text=bot.ai_label_text,
            age=bot.age,
            gender=Gender(bot.gender),
            location=bot.location,
            backstory=bot.backstory,
            interests=bot.interests,
            personality_traits=PersonalityTraits(**bot.personality_traits),
            writing_fingerprint=WritingFingerprint(**bot.writing_fingerprint),
            activity_pattern=ActivityPattern(**bot.activity_pattern),
            emotional_state=EmotionalState(**bot.emotional_state) if bot.emotional_state else EmotionalState(
                current_mood=MoodState.NEUTRAL,
                mood_intensity=0.5,
                triggers={},
                mood_history=[]
            ),
        )

        coder = self_coder_manager.get_coder(profile)
        result = await coder.analyze_and_code(
            trigger="manual_trigger",
            context={"manual": True},
            what_to_improve=what_to_improve
        )

        if result.success and result.module:
            return {
                "success": True,
                "bot_id": str(bot_id),
                "bot_name": bot.display_name,
                "module": {
                    "name": result.module.name,
                    "type": result.module.code_type.value,
                    "description": result.module.description,
                    "code": result.module.code
                },
                "reasoning": result.reasoning
            }
        else:
            return {
                "success": False,
                "bot_id": str(bot_id),
                "error": result.error
            }


@router.get("/github/status")
async def get_github_status():
    """Get GitHub integration status - currently disabled."""
    # GitHub integration disabled for now - will enable later
    return {
        "enabled": False,
        "message": "GitHub integration is currently disabled",
        "username": None,
        "bot_repo_prefix": settings.GITHUB_BOT_REPO_PREFIX,
        "bot_repos": []
    }
