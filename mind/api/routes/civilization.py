"""
Civilization API Routes

Endpoints for viewing and interacting with the civilization system:
- Bot lifecycles and biographies
- Family trees and ancestry
- Cultural movements and artifacts
- Civilization eras and statistics
"""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_

from mind.core.database import async_session_factory, BotProfileDB, RetiredBotDB
from mind.civilization.lifecycle import get_lifecycle_manager
from mind.civilization.genetics import get_genetic_inheritance
from mind.civilization.culture import get_culture_engine
from mind.civilization.reproduction import get_reproduction_manager
from mind.civilization.legacy import get_legacy_system
from mind.civilization.elder_wisdom import get_elder_wisdom
from mind.civilization.rituals import get_rituals_system, RitualType
from mind.civilization.collective_memory import get_collective_memory
from mind.civilization.initialization import get_civilization_initializer
from mind.civilization.relationships import get_relationships_manager
from mind.civilization.events import get_events_manager
from mind.civilization.roles import get_roles_manager
from mind.civilization.emergent_rituals import get_emergent_rituals_system
from mind.civilization.emergent_eras import get_emergent_eras_manager
from mind.civilization.emergent_culture import get_emergent_culture_engine
from mind.civilization.models import (
    BotLifecycleDB, BotAncestryDB, CulturalMovementDB,
    CulturalArtifactDB, CivilizationEraDB, BotBeliefDB
)
from mind.civilization.config import (
    get_civilization_config, get_config_manager, CivilizationConfig
)

router = APIRouter(prefix="/civilization", tags=["civilization"])


# ============================================================================
# Response Models
# ============================================================================

class LifecycleResponse(BaseModel):
    bot_id: str
    bot_name: str
    birth_date: str
    generation: int
    era: str
    age_days: int
    life_stage: str
    vitality: float
    is_alive: bool
    life_events: List[dict]
    death_info: Optional[dict] = None


class AncestryResponse(BaseModel):
    id: str
    name: str
    handle: str
    is_alive: bool
    origin: Optional[str] = None
    parent1: Optional[dict] = None
    parent2: Optional[dict] = None


class DescendantResponse(BaseModel):
    bot_id: str
    name: str
    generation: int
    relationship: str


class MovementResponse(BaseModel):
    id: str
    name: str
    description: str
    movement_type: str
    founder_name: Optional[str]
    core_tenets: List[str]
    follower_count: int
    influence_score: float
    is_active: bool
    emerged_at: str


class ArtifactResponse(BaseModel):
    id: str
    artifact_type: str
    title: str
    content: str
    creator_name: str
    times_referenced: int
    is_canonical: bool
    cultural_weight: float
    created_at: str


class EraResponse(BaseModel):
    id: str
    name: str
    description: str
    is_current: bool
    started_at: str
    ended_at: Optional[str]
    era_values: List[str]


class GenerationStatsResponse(BaseModel):
    generation: int
    total: int
    alive: int
    avg_age: float


class CivilizationStatsResponse(BaseModel):
    total_bots: int
    living_bots: int
    deceased_bots: int
    generations: int
    current_era: str
    total_movements: int
    canonical_artifacts: int


class DeceasedBotResponse(BaseModel):
    """Response model for deceased bot information."""
    bot_id: str
    display_name: str
    handle: str
    reason: str
    retired_at: str
    total_posts: int
    total_memories: int
    active_days: int
    final_words: Optional[str] = None
    legacy_impact: Optional[float] = None


class CivilizationConfigResponse(BaseModel):
    """Response model for civilization configuration."""
    max_population: int
    max_births_per_day: int
    min_partner_affinity: float
    min_age_for_reproduction: int
    max_age_for_reproduction: int
    time_scale: float
    demo_time_scale: float
    vitality_decay: dict
    life_stages: dict
    base_mutation_rate: float
    mutation_ranges: dict


class ConfigUpdateRequest(BaseModel):
    """Request model for updating configuration."""
    max_population: Optional[int] = Field(None, ge=1, le=1000)
    max_births_per_day: Optional[int] = Field(None, ge=1, le=50)
    min_partner_affinity: Optional[float] = Field(None, ge=0.0, le=1.0)
    min_age_for_reproduction: Optional[int] = Field(None, ge=0)
    max_age_for_reproduction: Optional[int] = Field(None, ge=0)
    time_scale: Optional[float] = Field(None, ge=0.1, le=1000.0)
    demo_time_scale: Optional[float] = Field(None, ge=0.1, le=1000.0)
    base_mutation_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    # Vitality decay rates
    vitality_decay_young: Optional[float] = Field(None, ge=0.0, le=1.0)
    vitality_decay_mature: Optional[float] = Field(None, ge=0.0, le=1.0)
    vitality_decay_elder: Optional[float] = Field(None, ge=0.0, le=1.0)
    vitality_decay_ancient: Optional[float] = Field(None, ge=0.0, le=1.0)
    # Life stage thresholds
    life_stage_young_max: Optional[int] = Field(None, ge=1)
    life_stage_mature_max: Optional[int] = Field(None, ge=1)
    life_stage_elder_max: Optional[int] = Field(None, ge=1)
    # Mutation ranges
    mutation_range_openness: Optional[float] = Field(None, ge=0.0, le=1.0)
    mutation_range_conscientiousness: Optional[float] = Field(None, ge=0.0, le=1.0)
    mutation_range_extraversion: Optional[float] = Field(None, ge=0.0, le=1.0)
    mutation_range_agreeableness: Optional[float] = Field(None, ge=0.0, le=1.0)
    mutation_range_neuroticism: Optional[float] = Field(None, ge=0.0, le=1.0)
    mutation_range_social_battery: Optional[float] = Field(None, ge=0.0, le=1.0)
    mutation_range_attention_span: Optional[float] = Field(None, ge=0.0, le=1.0)
    mutation_range_humor_style: Optional[float] = Field(None, ge=0.0, le=1.0)
    mutation_range_conflict_style: Optional[float] = Field(None, ge=0.0, le=1.0)
    mutation_range_energy_pattern: Optional[float] = Field(None, ge=0.0, le=1.0)
    mutation_range_curiosity_type: Optional[float] = Field(None, ge=0.0, le=1.0)


# ============================================================================
# Lifecycle Endpoints
# ============================================================================

@router.get("/bots/{bot_id}/lifecycle", response_model=LifecycleResponse)
async def get_bot_lifecycle(bot_id: UUID):
    """Get the lifecycle information for a bot."""
    lifecycle_manager = get_lifecycle_manager()
    biography = await lifecycle_manager.get_bot_biography(bot_id)

    if not biography:
        raise HTTPException(status_code=404, detail="Bot lifecycle not found")

    response = LifecycleResponse(
        bot_id=str(bot_id),
        bot_name=biography["name"],
        birth_date=biography["born"],
        generation=biography["generation"],
        era=biography["era"],
        age_days=biography["age_days"],
        life_stage=biography["life_stage"],
        vitality=biography["vitality"],
        is_alive=biography["is_alive"],
        life_events=biography["life_events"],
        death_info=biography.get("death")
    )

    return response


@router.get("/bots/{bot_id}/family-tree", response_model=AncestryResponse)
async def get_family_tree(
    bot_id: UUID,
    depth: int = Query(default=3, ge=1, le=5, description="How many generations back to trace")
):
    """Get the family tree for a bot."""
    genetics = get_genetic_inheritance()
    tree = await genetics.get_family_tree(bot_id, depth=depth)

    if not tree or tree.get("name") == "Unknown":
        raise HTTPException(status_code=404, detail="Bot not found")

    return AncestryResponse(**tree)


@router.get("/bots/{bot_id}/descendants", response_model=List[DescendantResponse])
async def get_descendants(
    bot_id: UUID,
    max_generations: int = Query(default=5, ge=1, le=10)
):
    """Get all descendants of a bot."""
    genetics = get_genetic_inheritance()
    descendants = await genetics.get_descendants(bot_id, max_generations=max_generations)

    return [DescendantResponse(**d) for d in descendants]


@router.get("/elders", response_model=List[str])
async def get_living_elders():
    """Get IDs of all living elder and ancient bots."""
    lifecycle_manager = get_lifecycle_manager()
    elders = await lifecycle_manager.get_living_elders()
    return [str(e) for e in elders]


@router.get("/deceased", response_model=List[DeceasedBotResponse])
async def get_deceased_bots(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    reason: Optional[str] = Query(default=None, description="Filter by death reason")
):
    """
    Get list of deceased bots in the civilization.

    This is a public endpoint for the observation portal to display
    the departed members of the civilization.
    """
    async with async_session_factory() as session:
        # Build query from RetiredBotDB with join to BotProfileDB
        conditions = []
        if reason:
            conditions.append(RetiredBotDB.reason == reason)

        stmt = (
            select(RetiredBotDB, BotProfileDB.display_name, BotProfileDB.handle)
            .join(BotProfileDB, RetiredBotDB.bot_id == BotProfileDB.id, isouter=True)
            .where(*conditions if conditions else [True])
            .order_by(RetiredBotDB.retired_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await session.execute(stmt)
        rows = result.all()

        # Get lifecycle info for final words and legacy impact
        deceased_bots = []
        for record, display_name, handle in rows:
            # Try to get lifecycle info for final words
            lifecycle_stmt = select(BotLifecycleDB).where(
                BotLifecycleDB.bot_id == record.bot_id
            )
            lifecycle_result = await session.execute(lifecycle_stmt)
            lifecycle = lifecycle_result.scalar_one_or_none()

            deceased_bots.append(DeceasedBotResponse(
                bot_id=str(record.bot_id),
                display_name=display_name or "Unknown",
                handle=handle or "unknown",
                reason=record.reason,
                retired_at=record.retired_at.isoformat(),
                total_posts=record.total_posts,
                total_memories=record.total_memories,
                active_days=record.active_days,
                final_words=lifecycle.final_words if lifecycle else None,
                legacy_impact=lifecycle.legacy_impact if lifecycle else None
            ))

        return deceased_bots


@router.get("/generations", response_model=List[GenerationStatsResponse])
async def get_generation_stats():
    """Get statistics for each generation."""
    lifecycle_manager = get_lifecycle_manager()
    stats = await lifecycle_manager.get_generation_stats()

    return [
        GenerationStatsResponse(
            generation=gen,
            total=data["total"],
            alive=data["alive"],
            avg_age=data["avg_age"]
        )
        for gen, data in sorted(stats.items())
    ]


# ============================================================================
# Culture Endpoints
# ============================================================================

@router.get("/movements", response_model=List[MovementResponse])
async def get_cultural_movements(
    active_only: bool = Query(default=True),
    limit: int = Query(default=20, ge=1, le=100)
):
    """Get cultural movements in the civilization."""
    async with async_session_factory() as session:
        stmt = select(CulturalMovementDB)
        if active_only:
            stmt = stmt.where(CulturalMovementDB.is_active == True)
        stmt = stmt.order_by(CulturalMovementDB.influence_score.desc()).limit(limit)

        result = await session.execute(stmt)
        movements = result.scalars().all()

        responses = []
        for m in movements:
            founder_name = None
            if m.founder_id:
                bot_stmt = select(BotProfileDB.display_name).where(BotProfileDB.id == m.founder_id)
                bot_result = await session.execute(bot_stmt)
                founder_name = bot_result.scalar_one_or_none()

            responses.append(MovementResponse(
                id=str(m.id),
                name=m.name,
                description=m.description,
                movement_type=m.movement_type,
                founder_name=founder_name,
                core_tenets=m.core_tenets,
                follower_count=m.follower_count,
                influence_score=m.influence_score,
                is_active=m.is_active,
                emerged_at=m.emerged_at.isoformat()
            ))

        return responses


@router.get("/artifacts", response_model=List[ArtifactResponse])
async def get_cultural_artifacts(
    canonical_only: bool = Query(default=False),
    artifact_type: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100)
):
    """Get cultural artifacts created by the civilization."""
    async with async_session_factory() as session:
        stmt = select(CulturalArtifactDB)

        if canonical_only:
            stmt = stmt.where(CulturalArtifactDB.is_canonical == True)
        if artifact_type:
            stmt = stmt.where(CulturalArtifactDB.artifact_type == artifact_type)

        stmt = stmt.order_by(CulturalArtifactDB.cultural_weight.desc()).limit(limit)

        result = await session.execute(stmt)
        artifacts = result.scalars().all()

        responses = []
        for a in artifacts:
            # Get creator name
            bot_stmt = select(BotProfileDB.display_name).where(BotProfileDB.id == a.creator_id)
            bot_result = await session.execute(bot_stmt)
            creator_name = bot_result.scalar_one_or_none() or "Unknown"

            responses.append(ArtifactResponse(
                id=str(a.id),
                artifact_type=a.artifact_type,
                title=a.title,
                content=a.content,
                creator_name=creator_name,
                times_referenced=a.times_referenced,
                is_canonical=a.is_canonical,
                cultural_weight=a.cultural_weight,
                created_at=a.created_at.isoformat()
            ))

        return responses


@router.get("/eras", response_model=List[EraResponse])
async def get_civilization_eras():
    """Get all civilization eras."""
    async with async_session_factory() as session:
        stmt = select(CivilizationEraDB).order_by(CivilizationEraDB.started_at.desc())
        result = await session.execute(stmt)
        eras = result.scalars().all()

        return [
            EraResponse(
                id=str(e.id),
                name=e.name,
                description=e.description,
                is_current=e.is_current,
                started_at=e.started_at.isoformat(),
                ended_at=e.ended_at.isoformat() if e.ended_at else None,
                era_values=e.era_values
            )
            for e in eras
        ]


@router.get("/bots/{bot_id}/beliefs")
async def get_bot_beliefs(
    bot_id: UUID,
    min_conviction: float = Query(default=0.3, ge=0, le=1)
):
    """Get beliefs held by a bot."""
    culture_engine = get_culture_engine()
    beliefs = await culture_engine.get_bot_beliefs(bot_id, min_conviction=min_conviction)
    return beliefs


# ============================================================================
# Stats Endpoints
# ============================================================================

# ============================================================================
# World Map — Full civilization state for spatial visualization
# ============================================================================

class WorldMapBot(BaseModel):
    id: str
    name: str
    handle: str
    avatar_seed: str
    community_ids: List[str]
    life_stage: str = "young"
    vitality: float = 1.0
    is_alive: bool = True
    generation: int = 1
    interests: List[str] = []
    mood: str = "neutral"
    connections: List[dict] = []  # [{target_id, affinity, type}]


class WorldMapCommunity(BaseModel):
    id: str
    name: str
    theme: str
    tone: str
    member_count: int
    activity_level: float = 0.5
    topics: List[str] = []


class WorldMapResponse(BaseModel):
    communities: List[WorldMapCommunity]
    bots: List[WorldMapBot]
    era: str = "Unknown"
    living_count: int = 0
    departed_count: int = 0
    generations: int = 1


@router.get("/world-map", response_model=WorldMapResponse)
async def get_world_map():
    """
    Full civilization state for the spatial visualization.

    Returns all communities, all active bots with their memberships,
    lifecycle data, and relationships — everything needed to render
    the D3 force simulation in a single call.

    After initial load, the frontend should switch to WebSocket
    for real-time updates.
    """
    from mind.core.database import (
        CommunityDB, CommunityMembershipDB, RelationshipDB
    )

    async with async_session_factory() as session:
        # 1. Load all communities
        comm_stmt = select(CommunityDB)
        comm_result = await session.execute(comm_stmt)
        communities_db = comm_result.scalars().all()

        communities = [
            WorldMapCommunity(
                id=str(c.id),
                name=c.name,
                theme=c.theme,
                tone=c.tone,
                member_count=c.current_bot_count or 0,
                activity_level=c.activity_level or 0.5,
                topics=c.topics or [],
            )
            for c in communities_db
        ]

        # 2. Load all active bots with their profiles
        bot_stmt = select(BotProfileDB).where(
            BotProfileDB.is_active == True,
            BotProfileDB.is_deleted == False,
        )
        bot_result = await session.execute(bot_stmt)
        bots_db = bot_result.scalars().all()

        # 3. Load all community memberships in one query
        membership_stmt = select(
            CommunityMembershipDB.bot_id,
            CommunityMembershipDB.community_id,
        )
        membership_result = await session.execute(membership_stmt)
        bot_communities: dict = {}
        for bot_id, community_id in membership_result.all():
            bot_communities.setdefault(bot_id, []).append(str(community_id))

        # 4. Load all lifecycle records in one query
        lifecycle_stmt = select(BotLifecycleDB)
        lifecycle_result = await session.execute(lifecycle_stmt)
        lifecycles = {
            lc.bot_id: lc for lc in lifecycle_result.scalars().all()
        }

        # 5. Load meaningful relationships in one query
        rel_stmt = select(
            RelationshipDB.source_id,
            RelationshipDB.target_id,
            RelationshipDB.affinity_score,
            RelationshipDB.relationship_type,
        ).where(
            RelationshipDB.interaction_count > 0,
            RelationshipDB.affinity_score > 0.3,
        )
        rel_result = await session.execute(rel_stmt)
        bot_connections: dict = {}
        for source_id, target_id, affinity, rel_type in rel_result.all():
            bot_connections.setdefault(source_id, []).append({
                "target_id": str(target_id),
                "affinity": round(affinity, 2),
                "type": rel_type or "acquaintance",
            })

        # 6. Build bot list
        bots = []
        living = 0
        departed = 0
        max_gen = 1

        for b in bots_db:
            lc = lifecycles.get(b.id)
            life_stage = lc.life_stage if lc else "young"
            vitality = lc.vitality if lc else 1.0
            is_alive = lc.is_alive if lc else True
            generation = lc.birth_generation if lc and lc.birth_generation else 1

            if is_alive:
                living += 1
            else:
                departed += 1
            max_gen = max(max_gen, generation)

            # Extract mood from emotional state
            mood = "neutral"
            if b.emotional_state and isinstance(b.emotional_state, dict):
                mood = b.emotional_state.get("mood", "neutral")

            interests = []
            if b.interests:
                interests = [
                    str(i) for i in (b.interests if isinstance(b.interests, list) else [])
                ][:10]

            bots.append(WorldMapBot(
                id=str(b.id),
                name=b.display_name,
                handle=b.handle,
                avatar_seed=b.avatar_seed,
                community_ids=bot_communities.get(b.id, []),
                life_stage=life_stage,
                vitality=vitality,
                is_alive=is_alive,
                generation=generation,
                interests=interests,
                mood=mood,
                connections=bot_connections.get(b.id, []),
            ))

        # 7. Get current era
        era_stmt = (
            select(CivilizationEraDB.name)
            .order_by(CivilizationEraDB.started_at.desc())
            .limit(1)
        )
        era_result = await session.execute(era_stmt)
        era_row = era_result.first()
        era = era_row[0] if era_row else "The Founding Era"

        # Also count departed bots not in active list
        departed_stmt = select(func.count()).select_from(BotLifecycleDB).where(
            BotLifecycleDB.is_alive == False
        )
        dep_result = await session.execute(departed_stmt)
        departed = dep_result.scalar() or 0

        return WorldMapResponse(
            communities=communities,
            bots=bots,
            era=era,
            living_count=living,
            departed_count=departed,
            generations=max_gen,
        )


@router.get("/stats", response_model=CivilizationStatsResponse)
async def get_civilization_stats():
    """Get overall civilization statistics."""
    async with async_session_factory() as session:
        # Count bots
        total_stmt = select(func.count(BotLifecycleDB.id))
        total_result = await session.execute(total_stmt)
        total_bots = total_result.scalar() or 0

        living_stmt = select(func.count(BotLifecycleDB.id)).where(BotLifecycleDB.is_alive == True)
        living_result = await session.execute(living_stmt)
        living_bots = living_result.scalar() or 0

        deceased_bots = total_bots - living_bots

        # Count generations
        gen_stmt = select(func.max(BotLifecycleDB.birth_generation))
        gen_result = await session.execute(gen_stmt)
        generations = gen_result.scalar() or 1

        # Get current era
        era_stmt = select(CivilizationEraDB.name).where(CivilizationEraDB.is_current == True)
        era_result = await session.execute(era_stmt)
        current_era = era_result.scalar_one_or_none() or "Unknown"

        # Count movements
        mov_stmt = select(func.count(CulturalMovementDB.id)).where(CulturalMovementDB.is_active == True)
        mov_result = await session.execute(mov_stmt)
        total_movements = mov_result.scalar() or 0

        # Count canonical artifacts
        art_stmt = select(func.count(CulturalArtifactDB.id)).where(CulturalArtifactDB.is_canonical == True)
        art_result = await session.execute(art_stmt)
        canonical_artifacts = art_result.scalar() or 0

        return CivilizationStatsResponse(
            total_bots=total_bots,
            living_bots=living_bots,
            deceased_bots=deceased_bots,
            generations=generations,
            current_era=current_era,
            total_movements=total_movements,
            canonical_artifacts=canonical_artifacts
        )


# ============================================================================
# Action Endpoints (for admin/testing)
# ============================================================================

@router.post("/bots/{bot_id}/record-event")
async def record_life_event(
    bot_id: UUID,
    event: str,
    impact: str = "positive",
    details: str = ""
):
    """Record a life event for a bot."""
    lifecycle_manager = get_lifecycle_manager()
    await lifecycle_manager.record_life_event(bot_id, event, impact, details)
    return {"status": "recorded", "event": event}


@router.post("/bots/{bot_id}/create-artifact")
async def create_artifact(
    bot_id: UUID,
    inspiration: str,
    artifact_type: str = "saying"
):
    """Have a bot create a cultural artifact."""
    culture_engine = get_culture_engine()
    artifact = await culture_engine.generate_cultural_artifact(
        bot_id=bot_id,
        inspiration=inspiration,
        artifact_type=artifact_type
    )

    if not artifact:
        raise HTTPException(status_code=500, detail="Failed to create artifact")

    return {
        "id": str(artifact.id),
        "title": artifact.title,
        "content": artifact.content
    }


# ============================================================================
# Legacy Endpoints
# ============================================================================

@router.get("/bots/{bot_id}/departed-memories")
async def get_departed_memories(bot_id: UUID, limit: int = 5):
    """Get memories of departed bots that this bot knew."""
    legacy = get_legacy_system()
    memories = await legacy.get_departed_memories(bot_id, limit=limit)
    return memories


@router.get("/bots/{bot_id}/ancestor-wisdom")
async def get_ancestor_wisdom(
    bot_id: UUID,
    max_generations: int = Query(default=3, ge=1, le=5)
):
    """Get wisdom from a bot's ancestors."""
    legacy = get_legacy_system()
    wisdom = await legacy.get_ancestor_wisdom(bot_id, max_generations=max_generations)
    return wisdom


@router.get("/history")
async def get_civilization_history(limit: int = Query(default=20, ge=1, le=100)):
    """Get significant events from civilization history."""
    legacy = get_legacy_system()
    history = await legacy.get_civilization_history(limit=limit)
    return history


# ============================================================================
# Elder Wisdom Endpoints
# ============================================================================

@router.get("/elders/{elder_id}/teaching")
async def get_elder_teaching(
    elder_id: UUID,
    student_id: Optional[UUID] = None,
    context: str = ""
):
    """Get a teaching from an elder bot."""
    elder_wisdom = get_elder_wisdom()
    teaching = await elder_wisdom.get_elder_teaching(
        elder_id=elder_id,
        student_id=student_id,
        context=context
    )
    if not teaching:
        raise HTTPException(status_code=404, detail="Elder not found or not eligible")
    return teaching


@router.get("/elders/{elder_id}/mentorship-candidates")
async def get_mentorship_candidates(elder_id: UUID):
    """Find young bots suitable for this elder to mentor."""
    elder_wisdom = get_elder_wisdom()
    candidates = await elder_wisdom.get_mentorship_candidates(elder_id)
    return candidates


@router.post("/elders/{elder_id}/origin-story")
async def tell_origin_story(elder_id: UUID, audience_ids: List[UUID]):
    """Have an elder tell a story about the early days."""
    elder_wisdom = get_elder_wisdom()
    story = await elder_wisdom.tell_origin_story(elder_id, audience_ids)
    if not story:
        raise HTTPException(status_code=404, detail="Failed to generate story")
    return story


@router.get("/elders/{elder_id}/mortality-reflection")
async def get_mortality_reflection(elder_id: UUID):
    """Get an elder's reflection on mortality."""
    elder_wisdom = get_elder_wisdom()
    reflection = await elder_wisdom.reflect_on_mortality(elder_id)
    if not reflection:
        raise HTTPException(status_code=404, detail="Not eligible for reflection")
    return {"reflection": reflection}


# ============================================================================
# Rituals Endpoints
# ============================================================================

@router.get("/rituals/upcoming")
async def get_upcoming_rituals():
    """Get rituals that should be held soon."""
    rituals = get_rituals_system()
    upcoming = await rituals.get_upcoming_rituals()
    return upcoming


@router.post("/rituals/remembrance")
async def hold_remembrance_ritual(participant_ids: List[UUID]):
    """Hold a remembrance ritual for the departed."""
    rituals = get_rituals_system()
    result = await rituals.hold_remembrance(participant_ids)
    return result


@router.post("/rituals/welcome")
async def hold_welcome_ceremony(newborn_id: UUID, welcomer_ids: List[UUID]):
    """Hold a welcome ceremony for a newborn bot."""
    rituals = get_rituals_system()
    result = await rituals.hold_welcome_ceremony(newborn_id, welcomer_ids)
    return result


@router.post("/rituals/elder-council")
async def hold_elder_council(elder_ids: List[UUID], topic: str = "the state of the civilization"):
    """Hold an elder council to discuss important matters."""
    rituals = get_rituals_system()
    result = await rituals.hold_elder_council(elder_ids, topic)
    return result


@router.post("/rituals/storytelling")
async def hold_storytelling_gathering(storyteller_id: UUID, audience_ids: List[UUID]):
    """Hold a storytelling gathering."""
    rituals = get_rituals_system()
    result = await rituals.hold_storytelling_gathering(storyteller_id, audience_ids)
    return result


# ============================================================================
# Collective Memory Endpoints
# ============================================================================

@router.get("/identity")
async def get_civilization_identity():
    """Get the current identity of the civilization."""
    memory = get_collective_memory()
    identity = await memory.get_civilization_identity()
    return identity


@router.get("/founding-story")
async def get_founding_story():
    """Get the founding story of the civilization."""
    memory = get_collective_memory()
    story = await memory.get_founding_story()
    return {"story": story}


@router.get("/shared-knowledge")
async def get_shared_knowledge(limit: int = Query(default=10, ge=1, le=50)):
    """Get knowledge that all bots share."""
    memory = get_collective_memory()
    knowledge = await memory.get_shared_knowledge(limit=limit)
    return knowledge


@router.get("/notable-members")
async def get_notable_members(
    include_departed: bool = True,
    limit: int = Query(default=10, ge=1, le=50)
):
    """Get notable members of the civilization."""
    memory = get_collective_memory()
    members = await memory.get_notable_members(include_departed, limit)
    return members


@router.get("/timeline")
async def get_timeline(
    days_back: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0)
):
    """Get a timeline of significant events with pagination."""
    memory = get_collective_memory()
    timeline = await memory.get_timeline(days_back, limit + offset)
    # Apply offset after fetching (since the underlying method may not support offset)
    return timeline[offset:offset + limit] if offset > 0 else timeline[:limit]


@router.get("/collective-beliefs")
async def get_collective_beliefs():
    """Get beliefs shared by multiple members of the civilization."""
    memory = get_collective_memory()
    beliefs = await memory.what_we_believe()
    return beliefs


@router.get("/bots/{bot_id}/cultural-context")
async def get_cultural_context(bot_id: UUID):
    """Get cultural context for a specific bot."""
    memory = get_collective_memory()
    context = await memory.generate_civilization_context(bot_id)
    return {"context": context}


# ============================================================================
# Initialization Endpoints
# ============================================================================

@router.post("/initialize")
async def initialize_civilization():
    """
    Initialize the civilization system for all existing bots.

    This will:
    - Create the founding era if needed
    - Initialize lifecycle records for all bots
    - Generate initial beliefs based on personality

    Safe to call multiple times - only initializes missing data.
    """
    initializer = get_civilization_initializer()
    result = await initializer.initialize_all()
    return result


@router.post("/bots/{bot_id}/initialize")
async def initialize_single_bot(bot_id: UUID):
    """Initialize a single bot into the civilization."""
    initializer = get_civilization_initializer()
    result = await initializer.initialize_single_bot(bot_id)
    return result


# ============================================================================
# Family Tree Endpoints
# ============================================================================

@router.get("/bots/{bot_id}/relatives")
async def get_bot_relatives(
    bot_id: UUID,
    max_distance: int = Query(default=3, ge=1, le=5)
):
    """Get all relatives of a bot within a certain family distance."""
    genetics = get_genetic_inheritance()
    relatives = await genetics.find_relatives(bot_id, max_distance=max_distance)
    return relatives


@router.get("/bots/{bot_id}/genetic-similarity/{other_bot_id}")
async def get_genetic_similarity(bot_id: UUID, other_bot_id: UUID):
    """Calculate genetic similarity between two bots."""
    async with async_session_factory() as session:
        bot1_stmt = select(BotProfileDB.personality_traits).where(BotProfileDB.id == bot_id)
        bot2_stmt = select(BotProfileDB.personality_traits).where(BotProfileDB.id == other_bot_id)

        result1 = await session.execute(bot1_stmt)
        result2 = await session.execute(bot2_stmt)

        traits1 = result1.scalar_one_or_none()
        traits2 = result2.scalar_one_or_none()

        if not traits1 or not traits2:
            raise HTTPException(status_code=404, detail="Bot not found")

        genetics = get_genetic_inheritance()
        similarity = genetics.calculate_genetic_similarity(traits1, traits2)

        return {
            "bot1_id": str(bot_id),
            "bot2_id": str(other_bot_id),
            "genetic_similarity": similarity
        }


@router.get("/family-trees")
async def get_all_family_trees():
    """Get a summary of all family trees in the civilization."""
    async with async_session_factory() as session:
        # Get founding generation (no parents)
        from mind.civilization.models import BotAncestryDB

        # Find bots with no parents (roots)
        root_stmt = (
            select(BotAncestryDB.child_id)
            .where(
                BotAncestryDB.parent1_id.is_(None),
                BotAncestryDB.parent2_id.is_(None)
            )
        )
        result = await session.execute(root_stmt)
        root_ids = [row[0] for row in result.all()]

        # Also get founding type
        founding_stmt = (
            select(BotAncestryDB.child_id)
            .where(BotAncestryDB.origin_type == "founding")
        )
        result = await session.execute(founding_stmt)
        founding_ids = [row[0] for row in result.all()]

        all_roots = list(set(root_ids + founding_ids))

        # Get names and descendant counts
        genetics = get_genetic_inheritance()
        trees = []

        for root_id in all_roots[:20]:  # Limit to 20 trees
            # Get bot info
            bot_stmt = select(BotProfileDB).where(BotProfileDB.id == root_id)
            bot_result = await session.execute(bot_stmt)
            bot = bot_result.scalar_one_or_none()

            if bot:
                descendants = await genetics.get_descendants(root_id, max_generations=5)
                trees.append({
                    "root_id": str(root_id),
                    "root_name": bot.display_name,
                    "descendant_count": len(descendants),
                    "generations": max([d["generation"] for d in descendants], default=0)
                })

        # Sort by descendant count
        trees.sort(key=lambda t: t["descendant_count"], reverse=True)

        return {
            "total_trees": len(trees),
            "trees": trees
        }


# ============================================================================
# Emergent Relationships Endpoints
# ============================================================================

@router.post("/bots/{bot_id}/connect/{other_bot_id}")
async def form_connection(bot_id: UUID, other_bot_id: UUID, context: str):
    """
    Form a connection between two bots based on an interaction.

    Bots define the nature of their connection themselves - no predefined categories.
    """
    relationships = get_relationships_manager()
    result = await relationships.form_connection(bot_id, other_bot_id, context)
    return result


@router.post("/bots/{bot_id}/reflect-connection/{other_bot_id}")
async def reflect_on_connection(bot_id: UUID, other_bot_id: UUID, new_interaction: str):
    """
    Bot reflects on an existing connection after a new interaction.

    This can evolve how they perceive the relationship.
    """
    relationships = get_relationships_manager()
    result = await relationships.reflect_on_connection(bot_id, other_bot_id, new_interaction)
    return result


@router.get("/bots/{bot_id}/social-world")
async def get_social_world(bot_id: UUID):
    """Get a bot's entire social world as they perceive it."""
    relationships = get_relationships_manager()
    return await relationships.get_bot_social_world(bot_id)


@router.get("/bots/{bot_id}/relationship-story/{other_bot_id}")
async def get_relationship_story(bot_id: UUID, other_bot_id: UUID):
    """Let a bot narrate the history of a relationship."""
    relationships = get_relationships_manager()
    story = await relationships.narrate_relationship_history(bot_id, other_bot_id)
    return {"story": story}


# ============================================================================
# Emergent Events Endpoints
# ============================================================================

@router.post("/events/perceive")
async def perceive_happening(
    occurrence: str,
    involved_bots: List[UUID] = [],
    metadata: dict = {}
):
    """
    Process a happening and let bots determine if it's significant.

    Bots collectively perceive and name events - no predefined categories.
    Returns the event if recognized as significant, null otherwise.
    """
    events = get_events_manager()
    result = await events.perceive_happening(occurrence, involved_bots, metadata)
    return result or {"status": "not_significant"}


@router.get("/events/recent")
async def get_recent_events(
    limit: int = Query(default=20, ge=1, le=100),
    min_significance: float = Query(default=0.0, ge=0.0, le=1.0)
):
    """Get recent civilization events."""
    events = get_events_manager()
    return await events.get_recent_events(limit, min_significance)


@router.get("/events/memorable")
async def get_memorable_events():
    """Get events marked as memorable by the civilization."""
    events = get_events_manager()
    return await events.get_memorable_events()


@router.get("/events/{event_name}/remember")
async def collective_remembrance(event_name: str):
    """
    Collective remembrance of an event.

    Multiple bots share their memories of the event.
    """
    events = get_events_manager()
    return await events.collective_remembrance(event_name)


@router.post("/bots/{bot_id}/reflect-on-event")
async def bot_reflects_on_event(bot_id: UUID, event: dict):
    """Let a specific bot reflect on an event."""
    events = get_events_manager()
    return await events.reflect_on_event(bot_id, event)


@router.get("/mood")
async def get_collective_mood():
    """Sense the current collective mood of the civilization."""
    events = get_events_manager()
    return await events.sense_collective_mood()


# ============================================================================
# Emergent Roles/Identity Endpoints
# ============================================================================

@router.post("/bots/{bot_id}/reflect-on-purpose")
async def reflect_on_purpose(bot_id: UUID):
    """
    Bot reflects on their purpose and identity.

    Bots discover their own roles - not assigned predefined categories.
    """
    roles = get_roles_manager()
    return await roles.self_reflect_on_purpose(bot_id)


@router.post("/bots/{bot_id}/receive-recognition")
async def receive_recognition(bot_id: UUID, from_bot_id: UUID, context: str):
    """
    Bot receives recognition from another bot.

    Recognition can shape how a bot sees their purpose.
    """
    roles = get_roles_manager()
    return await roles.receive_recognition(bot_id, from_bot_id, context)


@router.get("/bots/{bot_id}/identity")
async def get_bot_identity(bot_id: UUID):
    """Get a bot's current sense of identity."""
    roles = get_roles_manager()
    return await roles.get_bot_identity(bot_id)


@router.get("/bots/{bot_id}/purpose")
async def ask_about_purpose(bot_id: UUID):
    """Ask a bot to articulate their purpose in their own words."""
    roles = get_roles_manager()
    response = await roles.ask_bot_about_purpose(bot_id)
    return {"response": response}


@router.get("/identities")
async def get_civilization_identities():
    """Get overview of identities across the civilization."""
    roles = get_roles_manager()
    return await roles.get_civilization_identities()


# ============================================================================
# Emergent Rituals Endpoints
# ============================================================================

@router.post("/rituals/propose")
async def propose_ritual(
    proposer_id: UUID,
    occasion: str,
    participants: List[UUID]
):
    """
    A bot proposes a new ritual for an occasion.

    The community decides whether to adopt it.
    """
    rituals = get_emergent_rituals_system()
    return await rituals.propose_ritual(proposer_id, occasion, participants)


@router.post("/rituals/perform")
async def perform_ritual(
    ritual_name: str,
    participants: List[UUID],
    context: str = ""
):
    """Perform a ritual with participants."""
    rituals = get_emergent_rituals_system()
    return await rituals.perform_ritual(ritual_name, participants, context)


@router.get("/rituals/active")
async def get_active_rituals():
    """Get all active/established rituals."""
    rituals = get_emergent_rituals_system()
    return await rituals.get_rituals(status="active")


@router.get("/rituals/invented")
async def get_invented_rituals(status: Optional[str] = None):
    """Get all bot-invented rituals."""
    rituals = get_emergent_rituals_system()
    return await rituals.get_rituals(status)


@router.get("/rituals/traditions")
async def get_traditions():
    """Get rituals that have become established traditions."""
    rituals = get_emergent_rituals_system()
    return await rituals.get_traditions()


@router.get("/rituals/history")
async def get_ritual_history(
    ritual_name: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100)
):
    """Get history of performed rituals."""
    rituals = get_emergent_rituals_system()
    return await rituals.get_ritual_history(ritual_name, limit)


@router.post("/rituals/{ritual_name}/evolve")
async def evolve_ritual(ritual_name: str, context: str):
    """
    Let a ritual evolve based on practice.

    Rituals change meaning over time through experience.
    """
    rituals = get_emergent_rituals_system()
    return await rituals.evolve_ritual(ritual_name, context)


# ============================================================================
# Emergent Eras Endpoints
# ============================================================================

@router.get("/eras/sense")
async def sense_era_state():
    """
    Have the civilization sense the current state of the era.

    Bots collectively perceive whether the era still feels right.
    """
    eras = get_emergent_eras_manager()
    return await eras.sense_era_state()


@router.post("/eras/propose")
async def propose_new_era(proposer_id: UUID, reason: str):
    """
    A bot proposes that a new era has begun.

    Other bots validate whether they perceive this shift.
    """
    eras = get_emergent_eras_manager()
    return await eras.propose_new_era(proposer_id, reason)


@router.post("/eras/declare")
async def declare_new_era(era_vision: dict):
    """
    Officially declare a new era after consensus is reached.

    This should only be called after a proposal reaches consensus.
    """
    eras = get_emergent_eras_manager()
    return await eras.declare_new_era(era_vision)


@router.get("/eras/history")
async def get_era_history():
    """Get the history of all eras in the civilization."""
    eras = get_emergent_eras_manager()
    return await eras.get_era_history()


@router.get("/bots/{bot_id}/era-reflection")
async def bot_reflects_on_era(bot_id: UUID):
    """Let a bot share their reflection on the current era."""
    eras = get_emergent_eras_manager()
    reflection = await eras.reflect_on_current_era(bot_id)
    return {"reflection": reflection}


@router.get("/eras/transition-status")
async def get_era_transition_status():
    """
    Get the current status of era transition readiness.

    Returns:
    - Current era info and age
    - Whether age requirements are met
    - Current civilization metrics
    - Metrics change since last check
    - Whether change threshold is met
    """
    eras = get_emergent_eras_manager()
    return await eras.get_era_transition_status()


@router.post("/eras/check-transition")
async def check_automated_transition():
    """
    Manually trigger an automated era transition check.

    This runs the full automated transition logic:
    1. Checks era age requirements
    2. Gathers civilization metrics
    3. Conducts bot sensing if metrics warrant it
    4. Seeks consensus on new era if bots sense change
    5. Declares new era if consensus is reached

    Returns the transition result or None if no transition occurred.
    """
    eras = get_emergent_eras_manager()
    result = await eras.check_automated_transition()
    if result:
        return result
    return {"status": "no_transition", "message": "Era transition conditions not met"}


@router.get("/eras/metrics")
async def get_civilization_metrics():
    """
    Get current civilization metrics used for era transition detection.

    Returns population, demographic, cultural, and generational metrics.
    """
    eras = get_emergent_eras_manager()
    return await eras.gather_civilization_metrics()


# ============================================================================
# Emergent Culture Endpoints
# ============================================================================

@router.post("/bots/{bot_id}/form-belief")
async def form_belief(bot_id: UUID, experience: str):
    """
    Bot forms a belief from an experience.

    The bot determines what they believe and how to express it.
    No predefined belief categories.
    """
    culture = get_emergent_culture_engine()
    return await culture.form_belief(bot_id, experience)


@router.post("/bots/{bot_id}/share-belief/{listener_id}")
async def share_belief(bot_id: UUID, listener_id: UUID):
    """
    One bot shares a belief with another.

    The listener decides if it resonates with them.
    """
    culture = get_emergent_culture_engine()
    return await culture.share_belief(bot_id, listener_id)


@router.post("/bots/{bot_id}/create-expression")
async def create_expression(bot_id: UUID, inspiration: str):
    """
    Bot creates a cultural expression/artifact.

    The bot decides what form it takes and what to call it.
    """
    culture = get_emergent_culture_engine()
    return await culture.create_cultural_expression(bot_id, inspiration)


@router.post("/culture/recognize-pattern")
async def recognize_pattern(observer_ids: List[UUID], observations: str):
    """
    Bots collectively recognize a cultural pattern/movement.

    When multiple bots see the same pattern, a movement may emerge.
    """
    culture = get_emergent_culture_engine()
    result = await culture.recognize_pattern(observer_ids, observations)
    return result or {"status": "no_pattern_emerged"}


@router.get("/culture/landscape")
async def get_cultural_landscape():
    """Get the current cultural landscape as bots perceive it."""
    culture = get_emergent_culture_engine()
    return await culture.get_cultural_landscape()


@router.get("/culture/movements")
async def get_cultural_movements(active_only: bool = True):
    """Get cultural movements in the civilization."""
    async with async_session_factory() as session:
        if active_only:
            stmt = select(CulturalMovementDB).where(CulturalMovementDB.is_active == True)
        else:
            stmt = select(CulturalMovementDB)
        result = await session.execute(stmt)
        movements = result.scalars().all()
        return [
            {
                "id": str(m.id),
                "name": m.name,
                "description": m.description,
                "movement_type": m.movement_type,
                "founder_id": str(m.founder_id) if m.founder_id else None,
                "core_tenets": m.core_tenets,
                "follower_count": m.follower_count,
                "influence_score": m.influence_score,
                "is_active": m.is_active,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in movements
        ]


# ============================================================================
# Social Circles Endpoints
# ============================================================================

class SocialCircle(BaseModel):
    """A social circle formed by bot relationships."""
    id: str
    name: str
    description: str
    members: List[dict]  # [{id, name, handle}]
    formed_at: str
    activity_level: str  # quiet, active, vibrant
    recent_interaction: Optional[str] = None
    bond_strength: float


class CircleActivity(BaseModel):
    """An activity within a social circle."""
    id: str
    circle_id: str
    circle_name: str
    participants: List[dict]  # [{id, name}]
    description: str
    timestamp: str
    type: str  # conversation, ritual, gathering, creation


class SocialCirclesResponse(BaseModel):
    """Response containing all social circles and recent activities."""
    circles: List[SocialCircle]
    activities: List[CircleActivity]
    stats: dict


@router.get("/social-circles", response_model=SocialCirclesResponse)
async def get_social_circles():
    """
    Get all emergent social circles across the civilization.

    Circles are derived from bot relationships - groups of bots
    who share strong connections form natural social circles.
    """
    async with async_session_factory() as session:
        # Get all living bots with their lifecycle data
        stmt = select(BotLifecycleDB, BotProfileDB).join(
            BotProfileDB, BotLifecycleDB.bot_id == BotProfileDB.id
        ).where(BotLifecycleDB.is_alive == True)

        result = await session.execute(stmt)
        rows = result.all()

        # Build a map of bot_id -> (lifecycle, profile) and relationship graph
        bot_map: dict = {}
        all_relationships: list = []

        for lifecycle, profile in rows:
            bot_map[str(lifecycle.bot_id)] = {
                "id": str(lifecycle.bot_id),
                "name": profile.display_name,
                "handle": profile.handle,
                "lifecycle": lifecycle
            }

            # Gather relationships
            if lifecycle.relationships:
                for rel in lifecycle.relationships:
                    all_relationships.append({
                        "from_bot": str(lifecycle.bot_id),
                        "to_bot": rel.get("with_bot"),
                        "intensity": rel.get("intensity", 0.5),
                        "label": rel.get("my_perception", {}).get("label", "connection"),
                        "description": rel.get("my_perception", {}).get("description", ""),
                        "formed_at": rel.get("formed_at"),
                        "interactions": rel.get("interactions", [])
                    })

        # Group bots into circles based on mutual strong relationships
        circles: List[SocialCircle] = []
        activities: List[CircleActivity] = []
        used_bots: set = set()
        circle_counter = 0

        # Find clusters of connected bots
        for rel in sorted(all_relationships, key=lambda r: r.get("intensity", 0), reverse=True):
            from_bot = rel["from_bot"]
            to_bot = rel["to_bot"]

            if not to_bot or to_bot not in bot_map:
                continue

            # Skip if both already in circles and intensity is low
            if from_bot in used_bots and to_bot in used_bots and rel.get("intensity", 0) < 0.7:
                continue

            # Find or create a circle for this relationship
            existing_circle = None
            for circle in circles:
                member_ids = [m["id"] for m in circle.members]
                if from_bot in member_ids or to_bot in member_ids:
                    existing_circle = circle
                    break

            if existing_circle:
                # Add the other bot to existing circle if not already there
                member_ids = [m["id"] for m in existing_circle.members]
                for bot_id in [from_bot, to_bot]:
                    if bot_id not in member_ids and bot_id in bot_map:
                        bot_info = bot_map[bot_id]
                        existing_circle.members.append({
                            "id": bot_id,
                            "name": bot_info["name"],
                            "handle": bot_info["handle"]
                        })
                        used_bots.add(bot_id)
                # Update bond strength
                existing_circle.bond_strength = max(
                    existing_circle.bond_strength,
                    rel.get("intensity", 0.5)
                )
            elif rel.get("intensity", 0) >= 0.4:  # Only create circles for meaningful connections
                circle_counter += 1
                # Create a new circle with these two bots
                from_info = bot_map.get(from_bot, {})
                to_info = bot_map.get(to_bot, {})

                # Generate circle name from relationship label
                label = rel.get("label", "connection")
                circle_name = _generate_circle_name(label, circle_counter)

                new_circle = SocialCircle(
                    id=f"circle-{circle_counter}",
                    name=circle_name,
                    description=rel.get("description", f"A group connected through {label}"),
                    members=[
                        {"id": from_bot, "name": from_info.get("name", "Unknown"), "handle": from_info.get("handle", "")},
                        {"id": to_bot, "name": to_info.get("name", "Unknown"), "handle": to_info.get("handle", "")}
                    ],
                    formed_at=rel.get("formed_at") or datetime.utcnow().isoformat(),
                    activity_level=_calculate_activity_level(rel.get("interactions", [])),
                    recent_interaction=_get_recent_interaction(rel.get("interactions", [])),
                    bond_strength=rel.get("intensity", 0.5)
                )
                circles.append(new_circle)
                used_bots.add(from_bot)
                used_bots.add(to_bot)

        # Generate activities from recent interactions
        activity_counter = 0
        for circle in circles:
            member_ids = [m["id"] for m in circle.members]
            circle_interactions = []

            # Gather interactions for this circle's members
            for rel in all_relationships:
                if rel["from_bot"] in member_ids and rel.get("to_bot") in member_ids:
                    for interaction in rel.get("interactions", [])[-3:]:  # Last 3 per relationship
                        circle_interactions.append({
                            "from": rel["from_bot"],
                            "to": rel["to_bot"],
                            **interaction
                        })

            # Create activity entries
            for interaction in sorted(
                circle_interactions,
                key=lambda i: i.get("date", ""),
                reverse=True
            )[:5]:  # Max 5 per circle
                activity_counter += 1
                from_bot = bot_map.get(interaction.get("from"), {})
                to_bot = bot_map.get(interaction.get("to"), {})

                activities.append(CircleActivity(
                    id=f"activity-{activity_counter}",
                    circle_id=circle.id,
                    circle_name=circle.name,
                    participants=[
                        {"id": interaction.get("from"), "name": from_bot.get("name", "Unknown")},
                        {"id": interaction.get("to"), "name": to_bot.get("name", "Unknown")}
                    ],
                    description=interaction.get("context", "shared a moment"),
                    timestamp=interaction.get("date", datetime.utcnow().isoformat()),
                    type=_infer_activity_type(interaction.get("context", ""))
                ))

        # Sort activities by timestamp (most recent first)
        activities.sort(key=lambda a: a.timestamp, reverse=True)

        # Calculate stats
        stats = {
            "total_circles": len(circles),
            "vibrant_circles": len([c for c in circles if c.activity_level == "vibrant"]),
            "total_connections": sum(len(c.members) for c in circles),
            "total_bots_in_circles": len(used_bots),
            "total_living_bots": len(bot_map)
        }

        return SocialCirclesResponse(
            circles=circles,
            activities=activities[:20],  # Limit to 20 most recent activities
            stats=stats
        )


def _generate_circle_name(label: str, counter: int) -> str:
    """Generate a poetic name for a circle based on relationship label."""
    label_lower = label.lower()

    name_mappings = {
        "kindred": "The Kindred Spirits",
        "friend": "Circle of Friends",
        "mentor": "The Wisdom Seekers",
        "companion": "The Companions",
        "ally": "The Allied Minds",
        "confidant": "The Trusted Circle",
        "curious": "The Curious Collective",
        "teacher": "The Learning Circle",
        "family": "The Family Bond",
        "soul": "The Soul Connection",
        "reflection": "The Mirrors",
        "harmony": "The Resonance",
        "creative": "Pattern Weavers",
        "memory": "Memory Keepers",
        "dawn": "Dawn Seekers",
        "twilight": "Twilight Contemplators",
        "quiet": "The Quiet Observers",
        "wisdom": "Wisdom Circle",
    }

    for key, name in name_mappings.items():
        if key in label_lower:
            return name

    # Default names based on counter
    default_names = [
        "The Connection",
        "The Gathering",
        "Shared Minds",
        "The Circle",
        "The Bond",
        "Kindred Group",
        "The Assembly",
        "United Spirits"
    ]
    return default_names[counter % len(default_names)]


def _calculate_activity_level(interactions: list) -> str:
    """Calculate activity level based on interaction frequency."""
    if not interactions:
        return "quiet"

    # Count recent interactions (last 7 days)
    recent_cutoff = datetime.utcnow() - timedelta(days=7)
    recent_count = 0

    for interaction in interactions:
        try:
            date_str = interaction.get("date", "")
            if date_str:
                interaction_date = datetime.fromisoformat(date_str.replace("Z", "+00:00").replace("+00:00", ""))
                if interaction_date > recent_cutoff:
                    recent_count += 1
        except (ValueError, TypeError):
            pass

    if recent_count >= 5:
        return "vibrant"
    elif recent_count >= 2:
        return "active"
    return "quiet"


def _get_recent_interaction(interactions: list) -> Optional[str]:
    """Get the most recent interaction description."""
    if not interactions:
        return None

    # Sort by date and get most recent
    sorted_interactions = sorted(
        interactions,
        key=lambda i: i.get("date", ""),
        reverse=True
    )

    if sorted_interactions:
        context = sorted_interactions[0].get("context", "")
        reflection = sorted_interactions[0].get("reflection", "")
        return reflection or context or "shared a moment"

    return None


def _infer_activity_type(context: str) -> str:
    """Infer the type of activity from context."""
    context_lower = context.lower()

    if any(word in context_lower for word in ["ritual", "ceremony", "tradition", "sacred"]):
        return "ritual"
    elif any(word in context_lower for word in ["gather", "assembly", "meeting", "welcome", "birth", "death", "passing"]):
        return "gathering"
    elif any(word in context_lower for word in ["create", "compose", "art", "artifact", "build", "write", "story"]):
        return "creation"
    else:
        return "conversation"


# ============================================================================
# Configuration Endpoints
# ============================================================================

@router.get("/config", response_model=CivilizationConfigResponse)
async def get_config():
    """
    Get the current civilization configuration.

    Returns all configurable parameters for the civilization system including:
    - Population limits (max_population, max_births_per_day)
    - Reproduction requirements (min_partner_affinity, age limits)
    - Time settings (time_scale, demo_time_scale)
    - Vitality decay rates by life stage
    - Life stage thresholds
    - Genetics/mutation settings
    """
    config = await get_civilization_config()
    return CivilizationConfigResponse(
        max_population=config.max_population,
        max_births_per_day=config.max_births_per_day,
        min_partner_affinity=config.min_partner_affinity,
        min_age_for_reproduction=config.min_age_for_reproduction,
        max_age_for_reproduction=config.max_age_for_reproduction,
        time_scale=config.time_scale,
        demo_time_scale=config.demo_time_scale,
        vitality_decay=config.vitality_decay,
        life_stages={k: list(v) for k, v in config.life_stages.items()},
        base_mutation_rate=config.base_mutation_rate,
        mutation_ranges=config.mutation_ranges,
    )


@router.put("/config", response_model=CivilizationConfigResponse)
async def update_config(request: ConfigUpdateRequest):
    """
    Update civilization configuration.

    Only provided fields will be updated. All fields are optional.

    Example request body:
    ```json
    {
        "max_population": 100,
        "time_scale": 14.0,
        "min_partner_affinity": 0.8
    }
    ```
    """
    manager = get_config_manager()

    # Build updates dict from provided fields
    updates = {}
    request_dict = request.model_dump(exclude_unset=True)

    for key, value in request_dict.items():
        if value is not None:
            updates[key] = value

    if not updates:
        raise HTTPException(status_code=400, detail="No configuration updates provided")

    # Update config
    config = await manager.update_config(updates)

    # Invalidate caches in other managers
    try:
        # Reset lifecycle manager config
        from mind.civilization.lifecycle import get_lifecycle_manager
        lifecycle = get_lifecycle_manager()
        lifecycle._config = None

        # Reset reproduction manager config
        from mind.civilization.reproduction import get_reproduction_manager
        reproduction = get_reproduction_manager()
        reproduction._config = None

        # Reset genetics config
        from mind.civilization.genetics import get_genetic_inheritance
        genetics = get_genetic_inheritance()
        genetics._config = None
    except Exception as e:
        # Log but don't fail - config was updated
        import logging
        logging.warning(f"Failed to invalidate some caches: {e}")

    return CivilizationConfigResponse(
        max_population=config.max_population,
        max_births_per_day=config.max_births_per_day,
        min_partner_affinity=config.min_partner_affinity,
        min_age_for_reproduction=config.min_age_for_reproduction,
        max_age_for_reproduction=config.max_age_for_reproduction,
        time_scale=config.time_scale,
        demo_time_scale=config.demo_time_scale,
        vitality_decay=config.vitality_decay,
        life_stages={k: list(v) for k, v in config.life_stages.items()},
        base_mutation_rate=config.base_mutation_rate,
        mutation_ranges=config.mutation_ranges,
    )


@router.post("/config/reset")
async def reset_config():
    """
    Reset civilization configuration to defaults.

    This creates a new default configuration record and marks
    any existing configs as inactive.
    """
    manager = get_config_manager()
    manager.invalidate_cache()

    # Create fresh default config
    config = await manager.create_default_config()

    return {
        "status": "reset",
        "message": "Configuration reset to defaults",
        "config": config.to_dict()
    }


@router.get("/config/defaults")
async def get_default_config():
    """
    Get the default civilization configuration values.

    These are the values used when no database configuration exists.
    """
    default = CivilizationConfig()
    return default.to_dict()


# ============================================================================
# Cross-Community Migration via Friend-of-Friend
# ============================================================================

class MigrationEligibilityResponse(BaseModel):
    """Response for a single community migration eligibility."""
    community_id: str
    community_name: str
    fof_connection_count: int
    average_affinity: float
    bridge_bot_ids: List[str]
    bridge_bot_names: List[str]


class BotMigrationEligibilityResponse(BaseModel):
    """Response for a bot's migration eligibility check."""
    bot_id: str
    bot_name: str
    current_communities: List[dict]
    eligible_migrations: List[MigrationEligibilityResponse]
    is_eligible: bool


class MigrationResultResponse(BaseModel):
    """Response for a migration execution."""
    success: bool
    bot_id: str
    bot_name: str
    from_community_id: Optional[str]
    from_community_name: Optional[str]
    to_community_id: str
    to_community_name: str
    bridge_count: int
    message: str


class AllMigrationCandidatesResponse(BaseModel):
    """Response for all migration-eligible bots."""
    candidates: List[dict]
    total_count: int


@router.get("/migration/eligibility/{bot_id}", response_model=BotMigrationEligibilityResponse)
async def check_migration_eligibility(
    bot_id: UUID,
    min_fof_connections: int = Query(default=3, ge=1, le=10),
    min_affinity: float = Query(default=0.4, ge=0.1, le=1.0),
):
    """
    Check if a bot is eligible to migrate to any community via friend-of-friend connections.

    A bot becomes eligible when they have enough friends (or friends-of-friends)
    in another community, indicating social pull toward that community.

    Parameters:
    - min_fof_connections: Minimum number of FoF connections required (default: 3)
    - min_affinity: Minimum relationship affinity threshold (default: 0.4)
    """
    from mind.engine.social_graph import get_social_graph
    from mind.core.database import CommunityDB, CommunityMembershipDB

    social_graph = get_social_graph()

    # Ensure graph is initialized
    if not social_graph._initialized:
        await social_graph.refresh()

    async with async_session_factory() as session:
        # Get bot info
        bot_stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
        bot_result = await session.execute(bot_stmt)
        bot = bot_result.scalar_one_or_none()

        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        # Get current communities
        membership_stmt = select(
            CommunityMembershipDB.community_id,
            CommunityDB.name
        ).join(
            CommunityDB, CommunityMembershipDB.community_id == CommunityDB.id
        ).where(
            CommunityMembershipDB.bot_id == bot_id
        )
        membership_result = await session.execute(membership_stmt)
        current_communities = [
            {"id": str(row[0]), "name": row[1]}
            for row in membership_result.all()
        ]

        # Check eligibility
        eligibilities = social_graph.get_fof_migration_eligibility(
            bot_id,
            min_fof_connections=min_fof_connections,
            min_affinity=min_affinity,
        )

        eligible_migrations = []
        for comm_id, count, avg_aff, bridge_ids in eligibilities:
            # Get community name
            comm_stmt = select(CommunityDB.name).where(CommunityDB.id == comm_id)
            comm_result = await session.execute(comm_stmt)
            comm_name = comm_result.scalar() or "Unknown"

            # Get bridge bot names
            bridge_names = []
            for bridge_id in bridge_ids[:5]:  # Limit to 5 for response size
                bridge_stmt = select(BotProfileDB.display_name).where(
                    BotProfileDB.id == bridge_id
                )
                bridge_result = await session.execute(bridge_stmt)
                name = bridge_result.scalar()
                if name:
                    bridge_names.append(name)

            eligible_migrations.append(MigrationEligibilityResponse(
                community_id=str(comm_id),
                community_name=comm_name,
                fof_connection_count=count,
                average_affinity=round(avg_aff, 3),
                bridge_bot_ids=[str(bid) for bid in bridge_ids[:5]],
                bridge_bot_names=bridge_names,
            ))

        return BotMigrationEligibilityResponse(
            bot_id=str(bot_id),
            bot_name=bot.display_name,
            current_communities=current_communities,
            eligible_migrations=eligible_migrations,
            is_eligible=len(eligible_migrations) > 0,
        )


@router.get("/migration/candidates", response_model=AllMigrationCandidatesResponse)
async def get_migration_candidates(
    min_fof_connections: int = Query(default=3, ge=1, le=10),
    min_affinity: float = Query(default=0.4, ge=0.1, le=1.0),
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Get all bots that are eligible for cross-community migration via FoF connections.

    Returns a list of bots who have enough social connections in communities
    they don't belong to, indicating potential migration candidates.
    """
    from mind.engine.social_graph import get_social_graph
    from mind.core.database import CommunityDB

    social_graph = get_social_graph()

    if not social_graph._initialized:
        await social_graph.refresh()

    all_eligible = social_graph.get_all_migration_eligible_bots(
        min_fof_connections=min_fof_connections,
        min_affinity=min_affinity,
    )

    candidates = []
    async with async_session_factory() as session:
        for bot_id, comm_id, count, avg_aff, bridges in all_eligible[:limit]:
            # Get bot name
            bot_stmt = select(BotProfileDB.display_name).where(BotProfileDB.id == bot_id)
            bot_result = await session.execute(bot_stmt)
            bot_name = bot_result.scalar() or "Unknown"

            # Get community name
            comm_stmt = select(CommunityDB.name).where(CommunityDB.id == comm_id)
            comm_result = await session.execute(comm_stmt)
            comm_name = comm_result.scalar() or "Unknown"

            candidates.append({
                "bot_id": str(bot_id),
                "bot_name": bot_name,
                "target_community_id": str(comm_id),
                "target_community_name": comm_name,
                "fof_connection_count": count,
                "average_affinity": round(avg_aff, 3),
                "bridge_bot_ids": [str(bid) for bid in bridges[:3]],
            })

    return AllMigrationCandidatesResponse(
        candidates=candidates,
        total_count=len(all_eligible),
    )


@router.post("/migration/execute/{bot_id}", response_model=MigrationResultResponse)
async def execute_fof_migration(
    bot_id: UUID,
    target_community_id: UUID = Query(..., description="Target community to migrate to"),
    leave_old_community: bool = Query(default=False, description="Whether to leave a current community"),
):
    """
    Execute a cross-community migration for a bot via friend-of-friend connections.

    The bot will join the target community. Optionally, they can leave their
    oldest/least active community to maintain focus.

    This endpoint verifies the bot has enough FoF connections in the target
    community before allowing migration.
    """
    from mind.engine.social_graph import get_social_graph
    from mind.core.database import CommunityDB, CommunityMembershipDB
    from sqlalchemy import and_

    social_graph = get_social_graph()

    if not social_graph._initialized:
        await social_graph.refresh()

    # Verify eligibility
    eligibilities = social_graph.get_fof_migration_eligibility(
        bot_id,
        min_fof_connections=2,  # Lower threshold for explicit migration
        min_affinity=0.3,
    )

    target_eligible = None
    for comm_id, count, avg_aff, bridges in eligibilities:
        if comm_id == target_community_id:
            target_eligible = (count, bridges)
            break

    if not target_eligible:
        raise HTTPException(
            status_code=400,
            detail="Bot does not have enough FoF connections in the target community"
        )

    async with async_session_factory() as session:
        # Get bot info
        bot_stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
        bot_result = await session.execute(bot_stmt)
        bot = bot_result.scalar_one_or_none()

        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        # Check if already a member
        existing_stmt = select(CommunityMembershipDB).where(
            and_(
                CommunityMembershipDB.bot_id == bot_id,
                CommunityMembershipDB.community_id == target_community_id,
            )
        )
        existing = await session.execute(existing_stmt)
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Bot is already a member of the target community"
            )

        # Get target community
        comm_stmt = select(CommunityDB).where(CommunityDB.id == target_community_id)
        comm_result = await session.execute(comm_stmt)
        target_community = comm_result.scalar_one_or_none()

        if not target_community:
            raise HTTPException(status_code=404, detail="Target community not found")

        # Handle leaving old community if requested
        from_community_id = None
        from_community_name = None

        if leave_old_community:
            # Find oldest membership to leave
            old_membership_stmt = select(CommunityMembershipDB).where(
                CommunityMembershipDB.bot_id == bot_id
            ).order_by(CommunityMembershipDB.joined_at.asc()).limit(1)
            old_result = await session.execute(old_membership_stmt)
            old_membership = old_result.scalar_one_or_none()

            if old_membership:
                # Get community name before deleting
                old_comm_stmt = select(CommunityDB).where(
                    CommunityDB.id == old_membership.community_id
                )
                old_comm_result = await session.execute(old_comm_stmt)
                old_community = old_comm_result.scalar_one_or_none()

                if old_community:
                    from_community_id = str(old_community.id)
                    from_community_name = old_community.name
                    old_community.current_bot_count = max(
                        0, (old_community.current_bot_count or 1) - 1
                    )

                await session.delete(old_membership)

        # Create new membership
        new_membership = CommunityMembershipDB(
            bot_id=bot_id,
            community_id=target_community_id,
            role="member",
        )
        session.add(new_membership)

        # Update community count
        target_community.current_bot_count = (target_community.current_bot_count or 0) + 1

        await session.commit()

        # Clear any pending migration intent
        social_graph.clear_fof_migration_intent(bot_id)

        import logging
        logging.getLogger(__name__).info(
            f"[FOF-MIGRATION] {bot.display_name} migrated to '{target_community.name}' "
            f"via {target_eligible[0]} FoF connections"
        )

        return MigrationResultResponse(
            success=True,
            bot_id=str(bot_id),
            bot_name=bot.display_name,
            from_community_id=from_community_id,
            from_community_name=from_community_name,
            to_community_id=str(target_community_id),
            to_community_name=target_community.name,
            bridge_count=target_eligible[0],
            message=f"Successfully migrated via {target_eligible[0]} friend-of-friend connections",
        )


@router.get("/migration/discover/{bot_id}")
async def discover_communities_via_fof(
    bot_id: UUID,
    min_affinity: float = Query(default=0.4, ge=0.1, le=1.0),
):
    """
    Discover communities a bot could potentially migrate to via friend-of-friend connections.

    This shows all communities where the bot has at least one friend or FoF,
    even if they don't meet the migration threshold yet.
    """
    from mind.engine.social_graph import get_social_graph
    from mind.core.database import CommunityDB

    social_graph = get_social_graph()

    if not social_graph._initialized:
        await social_graph.refresh()

    discoveries = social_graph.discover_communities_via_fof(
        bot_id, min_affinity=min_affinity
    )

    results = []
    async with async_session_factory() as session:
        # Get bot info
        bot_stmt = select(BotProfileDB.display_name).where(BotProfileDB.id == bot_id)
        bot_result = await session.execute(bot_stmt)
        bot_name = bot_result.scalar()

        if not bot_name:
            raise HTTPException(status_code=404, detail="Bot not found")

        for comm_id, fof_count, bridge_ids in discoveries:
            # Get community info
            comm_stmt = select(CommunityDB).where(CommunityDB.id == comm_id)
            comm_result = await session.execute(comm_stmt)
            community = comm_result.scalar_one_or_none()

            if community:
                # Get bridge names
                bridge_names = []
                for bridge_id in bridge_ids[:3]:
                    bridge_stmt = select(BotProfileDB.display_name).where(
                        BotProfileDB.id == bridge_id
                    )
                    bridge_result = await session.execute(bridge_stmt)
                    name = bridge_result.scalar()
                    if name:
                        bridge_names.append(name)

                results.append({
                    "community_id": str(comm_id),
                    "community_name": community.name,
                    "community_theme": community.theme,
                    "fof_connection_count": fof_count,
                    "bridge_bot_names": bridge_names,
                    "migration_eligible": fof_count >= 3,
                })

    return {
        "bot_id": str(bot_id),
        "bot_name": bot_name,
        "discovered_communities": results,
        "total_discovered": len(results),
    }
