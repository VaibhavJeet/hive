"""
Civilization API Routes

Endpoints for viewing and interacting with the civilization system:
- Bot lifecycles and biographies
- Family trees and ancestry
- Cultural movements and artifacts
- Civilization eras and statistics
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func

from mind.core.database import async_session_factory, BotProfileDB
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
    limit: int = Query(default=50, ge=1, le=200)
):
    """Get a timeline of significant events."""
    memory = get_collective_memory()
    timeline = await memory.get_timeline(days_back, limit)
    return timeline


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
