"""
Civilization Configuration System

Provides centralized, database-backed configuration for all civilization
parameters. Supports loading from database with sensible defaults, caching,
and runtime updates.

Usage:
    from mind.civilization.config import get_civilization_config

    config = await get_civilization_config()
    max_pop = config.max_population
    min_affinity = config.min_partner_affinity
"""

import logging
from datetime import datetime

from mind.core.time import utcnow
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from dataclasses import dataclass, field

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from mind.core.database import Base, async_session_factory

logger = logging.getLogger(__name__)


# ============================================================================
# DATABASE MODEL
# ============================================================================

class CivilizationConfigDB(Base):
    """
    Stores civilization configuration settings in the database.

    Settings are stored as key-value pairs with type information,
    allowing for dynamic configuration without schema changes.
    """
    __tablename__ = "civilization_config"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Population Settings
    max_population: Mapped[int] = mapped_column(Integer, default=50)
    max_births_per_day: Mapped[int] = mapped_column(Integer, default=3)

    # Reproduction Settings
    min_partner_affinity: Mapped[float] = mapped_column(Float, default=0.75)
    min_age_for_reproduction: Mapped[int] = mapped_column(Integer, default=180)
    max_age_for_reproduction: Mapped[int] = mapped_column(Integer, default=2500)

    # Time Settings
    time_scale: Mapped[float] = mapped_column(Float, default=7.0)  # 1 real day = N virtual days
    demo_time_scale: Mapped[float] = mapped_column(Float, default=365.0)  # Demo mode: 1 real day = 1 virtual year

    # Vitality Decay Rates (per virtual day)
    vitality_decay_young: Mapped[float] = mapped_column(Float, default=0.0)
    vitality_decay_mature: Mapped[float] = mapped_column(Float, default=0.001)
    vitality_decay_elder: Mapped[float] = mapped_column(Float, default=0.003)
    vitality_decay_ancient: Mapped[float] = mapped_column(Float, default=0.008)

    # Life Stage Thresholds (in virtual days)
    life_stage_young_max: Mapped[int] = mapped_column(Integer, default=365)
    life_stage_mature_max: Mapped[int] = mapped_column(Integer, default=1825)
    life_stage_elder_max: Mapped[int] = mapped_column(Integer, default=3650)

    # Genetics / Mutation Settings
    base_mutation_rate: Mapped[float] = mapped_column(Float, default=0.1)
    mutation_range_openness: Mapped[float] = mapped_column(Float, default=0.15)
    mutation_range_conscientiousness: Mapped[float] = mapped_column(Float, default=0.15)
    mutation_range_extraversion: Mapped[float] = mapped_column(Float, default=0.2)
    mutation_range_agreeableness: Mapped[float] = mapped_column(Float, default=0.15)
    mutation_range_neuroticism: Mapped[float] = mapped_column(Float, default=0.2)
    mutation_range_social_battery: Mapped[float] = mapped_column(Float, default=0.15)
    mutation_range_attention_span: Mapped[float] = mapped_column(Float, default=0.15)
    mutation_range_humor_style: Mapped[float] = mapped_column(Float, default=0.2)
    mutation_range_conflict_style: Mapped[float] = mapped_column(Float, default=0.25)
    mutation_range_energy_pattern: Mapped[float] = mapped_column(Float, default=0.15)
    mutation_range_curiosity_type: Mapped[float] = mapped_column(Float, default=0.2)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str] = mapped_column(String(500), default="Default civilization configuration")


# ============================================================================
# CONFIGURATION DATACLASS
# ============================================================================

@dataclass
class CivilizationConfig:
    """
    Runtime configuration for civilization systems.

    This dataclass provides type-safe access to all configuration values
    with sensible defaults. Values are loaded from the database when available.
    """

    # Population Settings
    max_population: int = 50
    max_births_per_day: int = 3

    # Reproduction Settings
    min_partner_affinity: float = 0.75
    min_age_for_reproduction: int = 180  # virtual days
    max_age_for_reproduction: int = 2500  # virtual days

    # Time Settings
    time_scale: float = 7.0  # 1 real day = 7 virtual days
    demo_time_scale: float = 365.0  # Demo mode: 1 real day = 1 virtual year

    # Vitality Decay Rates (stored as dict for compatibility)
    vitality_decay: Dict[str, float] = field(default_factory=lambda: {
        "young": 0.0,
        "mature": 0.001,
        "elder": 0.003,
        "ancient": 0.008
    })

    # Life Stage Thresholds (stored as dict for compatibility)
    life_stages: Dict[str, tuple] = field(default_factory=lambda: {
        "young": (0, 365),
        "mature": (365, 1825),
        "elder": (1825, 3650),
        "ancient": (3650, float('inf'))
    })

    # Genetics / Mutation Settings
    base_mutation_rate: float = 0.1
    mutation_ranges: Dict[str, float] = field(default_factory=lambda: {
        "openness": 0.15,
        "conscientiousness": 0.15,
        "extraversion": 0.2,
        "agreeableness": 0.15,
        "neuroticism": 0.2,
        "social_battery_capacity": 0.15,
        "attention_span": 0.15,
        "humor_style": 0.2,
        "conflict_style": 0.25,
        "energy_pattern": 0.15,
        "curiosity_type": 0.2,
    })

    # Database tracking
    _db_id: Optional[UUID] = field(default=None, repr=False)
    _loaded_from_db: bool = field(default=False, repr=False)

    def get_vitality_decay(self, life_stage: str) -> float:
        """Get vitality decay rate for a life stage."""
        return self.vitality_decay.get(life_stage, 0.001)

    def get_life_stage(self, virtual_age_days: float) -> str:
        """Determine life stage based on virtual age."""
        for stage, (min_days, max_days) in self.life_stages.items():
            if min_days <= virtual_age_days < max_days:
                return stage
        return "ancient"

    def get_mutation_range(self, trait: str) -> float:
        """Get mutation range for a specific trait."""
        return self.mutation_ranges.get(trait, 0.1)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for API responses."""
        return {
            "max_population": self.max_population,
            "max_births_per_day": self.max_births_per_day,
            "min_partner_affinity": self.min_partner_affinity,
            "min_age_for_reproduction": self.min_age_for_reproduction,
            "max_age_for_reproduction": self.max_age_for_reproduction,
            "time_scale": self.time_scale,
            "demo_time_scale": self.demo_time_scale,
            "vitality_decay": self.vitality_decay,
            "life_stages": {k: list(v) for k, v in self.life_stages.items()},
            "base_mutation_rate": self.base_mutation_rate,
            "mutation_ranges": self.mutation_ranges,
        }

    @classmethod
    def from_db(cls, db_record: CivilizationConfigDB) -> "CivilizationConfig":
        """Create config from database record."""
        return cls(
            max_population=db_record.max_population,
            max_births_per_day=db_record.max_births_per_day,
            min_partner_affinity=db_record.min_partner_affinity,
            min_age_for_reproduction=db_record.min_age_for_reproduction,
            max_age_for_reproduction=db_record.max_age_for_reproduction,
            time_scale=db_record.time_scale,
            demo_time_scale=db_record.demo_time_scale,
            vitality_decay={
                "young": db_record.vitality_decay_young,
                "mature": db_record.vitality_decay_mature,
                "elder": db_record.vitality_decay_elder,
                "ancient": db_record.vitality_decay_ancient,
            },
            life_stages={
                "young": (0, db_record.life_stage_young_max),
                "mature": (db_record.life_stage_young_max, db_record.life_stage_mature_max),
                "elder": (db_record.life_stage_mature_max, db_record.life_stage_elder_max),
                "ancient": (db_record.life_stage_elder_max, float('inf')),
            },
            base_mutation_rate=db_record.base_mutation_rate,
            mutation_ranges={
                "openness": db_record.mutation_range_openness,
                "conscientiousness": db_record.mutation_range_conscientiousness,
                "extraversion": db_record.mutation_range_extraversion,
                "agreeableness": db_record.mutation_range_agreeableness,
                "neuroticism": db_record.mutation_range_neuroticism,
                "social_battery_capacity": db_record.mutation_range_social_battery,
                "attention_span": db_record.mutation_range_attention_span,
                "humor_style": db_record.mutation_range_humor_style,
                "conflict_style": db_record.mutation_range_conflict_style,
                "energy_pattern": db_record.mutation_range_energy_pattern,
                "curiosity_type": db_record.mutation_range_curiosity_type,
            },
            _db_id=db_record.id,
            _loaded_from_db=True,
        )


# ============================================================================
# CONFIG MANAGER
# ============================================================================

class CivilizationConfigManager:
    """
    Manages civilization configuration with database persistence and caching.
    """

    def __init__(self):
        self._cached_config: Optional[CivilizationConfig] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl_seconds: int = 60  # Re-check DB every minute

    async def get_config(self, force_reload: bool = False) -> CivilizationConfig:
        """
        Get the civilization configuration.

        Loads from database if available, otherwise returns defaults.
        Results are cached for performance.
        """
        # Check cache
        if not force_reload and self._cached_config is not None:
            if self._cache_time is not None:
                cache_age = (utcnow() - self._cache_time).total_seconds()
                if cache_age < self._cache_ttl_seconds:
                    return self._cached_config

        # Load from database
        try:
            async with async_session_factory() as session:
                stmt = select(CivilizationConfigDB).where(
                    CivilizationConfigDB.is_active == True
                ).order_by(CivilizationConfigDB.updated_at.desc()).limit(1)
                result = await session.execute(stmt)
                db_config = result.scalar_one_or_none()

                if db_config:
                    self._cached_config = CivilizationConfig.from_db(db_config)
                    self._cache_time = utcnow()
                    logger.debug("[CONFIG] Loaded civilization config from database")
                    return self._cached_config
        except Exception as e:
            logger.warning(f"[CONFIG] Failed to load config from database: {e}")

        # Return defaults if no DB config
        if self._cached_config is None:
            self._cached_config = CivilizationConfig()
            self._cache_time = utcnow()
            logger.info("[CONFIG] Using default civilization config")

        return self._cached_config

    async def update_config(
        self,
        updates: Dict[str, Any],
        session: Optional[AsyncSession] = None
    ) -> CivilizationConfig:
        """
        Update civilization configuration.

        Args:
            updates: Dictionary of config values to update
            session: Optional existing database session

        Returns:
            Updated configuration
        """
        should_close = session is None
        if session is None:
            session = async_session_factory()
            await session.__aenter__()

        try:
            # Get existing config or create new
            stmt = select(CivilizationConfigDB).where(
                CivilizationConfigDB.is_active == True
            ).limit(1)
            result = await session.execute(stmt)
            db_config = result.scalar_one_or_none()

            if db_config is None:
                db_config = CivilizationConfigDB()
                session.add(db_config)

            # Apply updates
            for key, value in updates.items():
                if hasattr(db_config, key):
                    setattr(db_config, key, value)
                else:
                    # Handle nested config updates
                    if key.startswith("vitality_decay_"):
                        setattr(db_config, key, value)
                    elif key.startswith("life_stage_"):
                        setattr(db_config, key, value)
                    elif key.startswith("mutation_range_"):
                        setattr(db_config, key, value)
                    else:
                        logger.warning(f"[CONFIG] Unknown config key: {key}")

            db_config.updated_at = utcnow()
            await session.commit()
            await session.refresh(db_config)

            # Clear cache
            self._cached_config = CivilizationConfig.from_db(db_config)
            self._cache_time = utcnow()

            logger.info(f"[CONFIG] Updated civilization config: {list(updates.keys())}")
            return self._cached_config

        finally:
            if should_close:
                await session.__aexit__(None, None, None)

    async def create_default_config(self) -> CivilizationConfig:
        """
        Create a default configuration in the database.

        Only creates if no active config exists.
        """
        async with async_session_factory() as session:
            # Check if config exists
            stmt = select(CivilizationConfigDB).where(
                CivilizationConfigDB.is_active == True
            ).limit(1)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                logger.debug("[CONFIG] Default config already exists")
                return CivilizationConfig.from_db(existing)

            # Create default
            db_config = CivilizationConfigDB(
                description="Default civilization configuration"
            )
            session.add(db_config)
            await session.commit()
            await session.refresh(db_config)

            self._cached_config = CivilizationConfig.from_db(db_config)
            self._cache_time = utcnow()

            logger.info("[CONFIG] Created default civilization config")
            return self._cached_config

    def invalidate_cache(self):
        """Invalidate the cached configuration."""
        self._cached_config = None
        self._cache_time = None


# ============================================================================
# SINGLETON
# ============================================================================

_config_manager: Optional[CivilizationConfigManager] = None


def get_config_manager() -> CivilizationConfigManager:
    """Get or create the civilization config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = CivilizationConfigManager()
    return _config_manager


async def get_civilization_config(force_reload: bool = False) -> CivilizationConfig:
    """
    Convenience function to get the civilization configuration.

    Usage:
        config = await get_civilization_config()
        max_pop = config.max_population
    """
    manager = get_config_manager()
    return await manager.get_config(force_reload=force_reload)
