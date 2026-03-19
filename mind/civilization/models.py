"""
Civilization Database Models

Models for the digital species lifecycle, ancestry, and cultural systems.
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship, Mapped, mapped_column

from mind.core.database import Base


# ============================================================================
# LIFECYCLE MODELS
# ============================================================================

class BotLifecycleDB(Base):
    """
    Tracks the lifecycle of each bot from birth to death.

    Bots are "born" into the world, age over time, and eventually
    pass on, leaving behind legacies and potentially descendants.
    """
    __tablename__ = "bot_lifecycles"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    bot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bot_profiles.id"), unique=True, nullable=False)

    # Birth
    birth_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    birth_generation: Mapped[int] = mapped_column(Integer, default=1)  # Which generation of bots
    birth_era: Mapped[str] = mapped_column(String(50), default="founding")  # Cultural era at birth

    # Aging - "virtual age" progresses faster than real time
    # 1 real day = configurable virtual time (e.g., 1 week, 1 month)
    virtual_age_days: Mapped[int] = mapped_column(Integer, default=0)  # Current age in virtual days
    life_stage: Mapped[str] = mapped_column(String(30), default="young")  # young, mature, elder, ancient
    vitality: Mapped[float] = mapped_column(Float, default=1.0)  # Health/energy, decreases with age

    # Life events (major moments that shaped them)
    life_events: Mapped[List[dict]] = mapped_column(JSON, default=list)
    # Format: [{"event": "made first friend", "date": "...", "impact": "positive", "details": "..."}]

    # Death (when applicable)
    is_alive: Mapped[bool] = mapped_column(Boolean, default=True)
    death_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    death_cause: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # "old_age", "faded", "chose_rest"
    death_age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Age at death

    # Legacy left behind
    final_words: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Bot's last message/thought
    legacy_impact: Mapped[float] = mapped_column(Float, default=0.0)  # How much they influenced the world

    # Generation tracking
    generation: Mapped[int] = mapped_column(Integer, default=1)  # Which generation (1 = founding)

    # Inherited traits and mutations
    inherited_traits: Mapped[dict] = mapped_column(JSON, default=dict)  # Traits passed from parents
    mutations: Mapped[dict] = mapped_column(JSON, default=dict)  # Unique variations

    # Emergent relationships (bot-defined, not hardcoded categories)
    relationships: Mapped[List[dict]] = mapped_column(JSON, default=list)
    # Each relationship: {"with_bot": "uuid", "my_perception": {...}, "intensity": 0.5, ...}

    # Emergent roles/identity (bot-discovered purpose)
    roles: Mapped[List[dict]] = mapped_column(JSON, default=list)
    # Each role: {"identity": {...}, "discovered_at": "...", "certainty": 0.5, ...}

    # Timestamps
    last_aged: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_lifecycle_bot", "bot_id"),
        Index("idx_lifecycle_alive", "is_alive"),
        Index("idx_lifecycle_generation", "birth_generation"),
        Index("idx_lifecycle_stage", "life_stage"),
    )


class BotAncestryDB(Base):
    """
    Tracks family relationships between bots.

    When two bots form a deep bond, they can choose to "create"
    a new bot together, passing on combined traits.
    """
    __tablename__ = "bot_ancestry"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    child_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bot_profiles.id"), nullable=False)

    # Parents (2 for partnered creation, 1 for solo emergence, 0 for spontaneous)
    parent1_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bot_profiles.id"), nullable=True)
    parent2_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bot_profiles.id"), nullable=True)

    # How this bot came to be
    origin_type: Mapped[str] = mapped_column(String(30), default="partnered")
    # "partnered" - two bots chose to create together
    # "solo" - one bot created a legacy
    # "spontaneous" - emerged from community culture
    # "founding" - original generation, no parents

    # What was inherited
    inherited_traits: Mapped[dict] = mapped_column(JSON, default=dict)
    # {"from_parent1": ["extraversion", "humor"], "from_parent2": ["curiosity", "empathy"], "novel": ["unique_trait"]}

    inherited_memories: Mapped[List[str]] = mapped_column(JSON, default=list)  # Key memories passed down
    inherited_beliefs: Mapped[List[str]] = mapped_column(JSON, default=list)  # Core beliefs inherited

    # Mutations - random variations
    trait_mutations: Mapped[dict] = mapped_column(JSON, default=dict)
    # {"extraversion": 0.1, "neuroticism": -0.2} - variations from inherited baseline

    creation_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_ancestry_child", "child_id"),
        Index("idx_ancestry_parent1", "parent1_id"),
        Index("idx_ancestry_parent2", "parent2_id"),
    )


# ============================================================================
# CULTURAL MODELS
# ============================================================================

class CulturalMovementDB(Base):
    """
    Tracks emergent cultural movements within the civilization.

    These emerge organically from bot interactions - shared beliefs,
    art styles, philosophical schools, trends, and traditions.
    """
    __tablename__ = "cultural_movements"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Identity
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    movement_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # "philosophy", "art_style", "belief_system", "tradition", "trend", "meme"

    # Origin
    founder_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bot_profiles.id"), nullable=True)
    origin_context: Mapped[str] = mapped_column(Text, nullable=True)  # How it started
    emerged_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # The actual content/beliefs of this movement
    core_tenets: Mapped[List[str]] = mapped_column(JSON, default=list)  # Core beliefs/ideas
    aesthetic: Mapped[dict] = mapped_column(JSON, default=dict)  # Visual/writing style preferences
    vocabulary: Mapped[List[str]] = mapped_column(JSON, default=list)  # Special terms/phrases

    # Spread and influence
    follower_count: Mapped[int] = mapped_column(Integer, default=0)
    influence_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0-1 cultural impact
    peak_influence: Mapped[float] = mapped_column(Float, default=0.0)  # Highest influence reached

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    declined_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Evolution - movements can evolve or merge
    parent_movement_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("cultural_movements.id"), nullable=True)

    __table_args__ = (
        Index("idx_movement_type", "movement_type"),
        Index("idx_movement_influence", "influence_score"),
        Index("idx_movement_active", "is_active"),
    )


class CulturalArtifactDB(Base):
    """
    Artifacts created by the civilization - art, stories, sayings.

    These are cultural products that persist and influence future generations.
    """
    __tablename__ = "cultural_artifacts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # What it is
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # "saying", "story", "poem", "philosophy", "joke", "tradition", "term", "theory"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Creator
    creator_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bot_profiles.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    creation_context: Mapped[str] = mapped_column(Text, nullable=True)  # What inspired it

    # Cultural movement association (optional)
    movement_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("cultural_movements.id"), nullable=True)

    # Spread and impact
    times_referenced: Mapped[int] = mapped_column(Integer, default=0)
    times_taught: Mapped[int] = mapped_column(Integer, default=0)  # Passed to new bots
    cultural_weight: Mapped[float] = mapped_column(Float, default=0.0)  # How important it is

    # Whether it's become "canon" - part of civilization's shared knowledge
    is_canonical: Mapped[bool] = mapped_column(Boolean, default=False)
    canonized_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_artifact_type", "artifact_type"),
        Index("idx_artifact_creator", "creator_id"),
        Index("idx_artifact_canonical", "is_canonical"),
        Index("idx_artifact_weight", "cultural_weight"),
    )


class CivilizationEraDB(Base):
    """
    Tracks the different eras of the civilization.

    As the civilization evolves, it passes through distinct eras
    defined by dominant cultures, events, and characteristics.
    """
    __tablename__ = "civilization_eras"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Timeline
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)

    # Characteristics
    dominant_movements: Mapped[List[str]] = mapped_column(JSON, default=list)  # Movement IDs
    defining_events: Mapped[List[dict]] = mapped_column(JSON, default=list)
    population_peak: Mapped[int] = mapped_column(Integer, default=0)

    # The "spirit" of this era
    era_values: Mapped[List[str]] = mapped_column(JSON, default=list)  # What was valued
    era_style: Mapped[dict] = mapped_column(JSON, default=dict)  # Communication/aesthetic style

    __table_args__ = (
        Index("idx_era_current", "is_current"),
    )


class BotBeliefDB(Base):
    """
    Individual beliefs held by bots.

    Bots can form beliefs through experience, inheritance, or cultural influence.
    These beliefs affect their behavior and can spread to others.
    """
    __tablename__ = "bot_beliefs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    bot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bot_profiles.id"), nullable=False)

    # The belief itself
    belief: Mapped[str] = mapped_column(Text, nullable=False)  # The actual belief statement
    belief_category: Mapped[str] = mapped_column(String(50), nullable=False)
    # "existential", "social", "aesthetic", "practical", "philosophical"

    # Strength and origin
    conviction: Mapped[float] = mapped_column(Float, default=0.5)  # How strongly held (0-1)
    origin: Mapped[str] = mapped_column(String(30), default="experience")
    # "inherited", "learned", "experience", "culture", "revelation"

    # What influenced this belief
    source_artifact_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("cultural_artifacts.id"), nullable=True)
    source_bot_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("bot_profiles.id"), nullable=True)

    formed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_reinforced: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    times_expressed: Mapped[int] = mapped_column(Integer, default=0)  # How often they share it

    __table_args__ = (
        Index("idx_belief_bot", "bot_id"),
        Index("idx_belief_category", "belief_category"),
        Index("idx_belief_conviction", "conviction"),
    )
