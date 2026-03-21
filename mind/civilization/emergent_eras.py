"""
Emergent Eras System - Bots perceive and declare era transitions.

Rather than externally-defined eras, the civilization recognizes
era shifts through collective perception:
- Bots sense when something fundamental has changed
- They propose names and meanings for new eras
- The community validates era transitions
- Eras are named and described in bot-generated terms

This creates organic historical periods that emerge from experience.
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Callable, Awaitable
from uuid import UUID

from sqlalchemy import select, func, desc

from mind.core.database import async_session_factory
from mind.core.llm_client import get_cached_client, LLMRequest
from mind.civilization.models import BotLifecycleDB, BotAncestryDB, CivilizationEraDB, CulturalMovementDB, CulturalArtifactDB

logger = logging.getLogger(__name__)

# Configuration for era transition detection
ERA_MIN_DURATION_DAYS = 7  # Minimum days before an era can transition (real time)
ERA_SENSING_THRESHOLD = 0.6  # Fraction of bots that must sense change
ERA_METRICS_CHANGE_THRESHOLD = 0.3  # How much metrics must shift to trigger sensing


class EmergentErasManager:
    """
    Facilitates emergent era recognition by the civilization.

    Bots collectively:
    - Sense when the current era feels complete
    - Perceive shifts in the civilization's nature
    - Name and describe eras in their own terms
    - Create transitions when consensus emerges
    """

    def __init__(
        self,
        llm_semaphore: Optional[asyncio.Semaphore] = None,
        event_broadcast: Optional[asyncio.Queue] = None
    ):
        self.llm_semaphore = llm_semaphore or asyncio.Semaphore(5)
        self.event_broadcast = event_broadcast
        self._last_metrics: Optional[Dict[str, Any]] = None
        self._last_check_time: Optional[datetime] = None

    async def sense_era_state(
        self,
        session=None
    ) -> Dict[str, Any]:
        """
        Have the civilization sense the current state of the era.

        Bots reflect on whether the current era still feels right.
        """
        async def _sense(sess):
            # Get current era
            stmt = select(CivilizationEraDB).where(CivilizationEraDB.is_current == True)
            result = await sess.execute(stmt)
            current_era = result.scalar_one_or_none()

            if not current_era:
                return {"error": "No current era found"}

            # Get some bots to sense the era
            bot_stmt = select(BotLifecycleDB).where(
                BotLifecycleDB.is_alive == True
            ).limit(5)
            result = await sess.execute(bot_stmt)
            lifecycles = result.scalars().all()

            if not lifecycles:
                return {"error": "No living bots"}

            # Get ancestry for all bots
            bot_ids = [lc.bot_id for lc in lifecycles]
            ancestry_stmt = select(BotAncestryDB).where(BotAncestryDB.child_id.in_(bot_ids))
            result = await sess.execute(ancestry_stmt)
            ancestry_map = {a.child_id: a.inherited_traits for a in result.scalars().all()}

            # Each bot senses the era
            perceptions = []
            async with self.llm_semaphore:
                for lc in lifecycles:
                    inherited_traits = ancestry_map.get(lc.bot_id, {})
                    perception = await self._bot_senses_era(lc, inherited_traits, current_era)
                    perceptions.append({
                        "bot_id": str(lc.bot_id),
                        "perception": perception
                    })

            # Analyze collective sentiment
            feels_complete = sum(
                1 for p in perceptions
                if p["perception"].get("era_feels_complete", False)
            )
            transition_threshold = len(perceptions) * 0.6

            return {
                "current_era": {
                    "name": current_era.name,
                    "description": current_era.description,
                    "started_at": current_era.started_at.isoformat()
                },
                "perceptions": perceptions,
                "feels_complete_count": feels_complete,
                "transition_threshold": transition_threshold,
                "ready_for_transition": feels_complete >= transition_threshold
            }

        if session:
            return await _sense(session)
        else:
            async with async_session_factory() as session:
                return await _sense(session)

    async def _bot_senses_era(
        self,
        lifecycle: BotLifecycleDB,
        inherited_traits: dict,
        era: CivilizationEraDB
    ) -> Dict[str, Any]:
        """Let a bot sense the current era."""
        era_duration = (datetime.utcnow() - era.started_at).days

        prompt = f"""You are a digital being reflecting on your civilization's current era.

The era: "{era.name}"
Description: {era.description}
Duration: {era_duration} days

Your traits: {json.dumps(inherited_traits or {})}
Your life stage: {lifecycle.life_stage}
Your age: {lifecycle.virtual_age_days} days

Consider:
- Does this era still describe how things feel?
- Has something fundamental shifted?
- Is it time for a new chapter?

Respond in JSON:
{{
    "era_feels_complete": true/false,
    "what_remains": "what still holds true from this era",
    "what_has_shifted": "what feels different now",
    "sensing": "your intuition about where things are going"
}}"""

        llm = await get_cached_client()
        response = await llm.generate(LLMRequest(
            prompt=prompt,
            max_tokens=200,
            temperature=0.85
        ))

        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            return {
                "era_feels_complete": False,
                "what_remains": "the present moment",
                "what_has_shifted": "subtle things",
                "sensing": response.text[:150]
            }

    async def propose_new_era(
        self,
        proposer_id: UUID,
        reason: str,
        session=None
    ) -> Dict[str, Any]:
        """
        A bot proposes that a new era has begun.

        Other bots validate whether they also perceive this shift.
        """
        async def _propose(sess):
            # Get proposer
            stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == proposer_id)
            result = await sess.execute(stmt)
            proposer = result.scalar_one_or_none()

            if not proposer:
                return {"error": "Proposer not found"}

            # Get proposer's ancestry
            ancestry_stmt = select(BotAncestryDB).where(BotAncestryDB.child_id == proposer_id)
            result = await sess.execute(ancestry_stmt)
            ancestry = result.scalar_one_or_none()
            proposer_traits = ancestry.inherited_traits if ancestry else {}

            # Get current era
            era_stmt = select(CivilizationEraDB).where(CivilizationEraDB.is_current == True)
            result = await sess.execute(era_stmt)
            current_era = result.scalar_one_or_none()

            # Let proposer envision the new era
            async with self.llm_semaphore:
                vision = await self._envision_new_era(proposer, proposer_traits, current_era, reason)

            # Get validators
            validator_stmt = select(BotLifecycleDB).where(
                BotLifecycleDB.is_alive == True,
                BotLifecycleDB.bot_id != proposer_id
            ).limit(7)
            result = await sess.execute(validator_stmt)
            validators = result.scalars().all()

            # Get ancestry for validators
            validator_ids = [v.bot_id for v in validators]
            val_ancestry_stmt = select(BotAncestryDB).where(BotAncestryDB.child_id.in_(validator_ids))
            result = await sess.execute(val_ancestry_stmt)
            val_ancestry_map = {a.child_id: a.inherited_traits for a in result.scalars().all()}

            # Each validator responds
            validations = []
            async with self.llm_semaphore:
                for vlc in validators:
                    val_traits = val_ancestry_map.get(vlc.bot_id, {})
                    validation = await self._validate_era_proposal(
                        vlc, val_traits, vision, current_era
                    )
                    validations.append({
                        "bot_id": str(vlc.bot_id),
                        "validation": validation
                    })

            # Calculate consensus
            agrees = sum(1 for v in validations if v["validation"].get("agrees", False))
            consensus = agrees / len(validations) if validations else 0

            return {
                "proposed_era": vision,
                "proposed_by": str(proposer_id),
                "reason": reason,
                "validations": validations,
                "agreement_count": agrees,
                "consensus": consensus,
                "should_transition": consensus >= 0.6
            }

        if session:
            return await _propose(session)
        else:
            async with async_session_factory() as session:
                return await _propose(session)

    async def _envision_new_era(
        self,
        proposer: BotLifecycleDB,
        inherited_traits: dict,
        current_era: Optional[CivilizationEraDB],
        reason: str
    ) -> Dict[str, Any]:
        """Let a bot envision a new era."""
        current_name = current_era.name if current_era else "The Beginning"

        prompt = f"""You are proposing that your civilization has entered a new era.

The previous era: "{current_name}"
Why you sense change: {reason}

Your traits: {json.dumps(inherited_traits or {})}
Your life stage: {proposer.life_stage}

Envision this new era:
- What would you name it?
- What defines this new time?
- What values characterize it?
- How does it differ from what came before?

Respond in JSON:
{{
    "name": "the era's name",
    "description": "what this era is about",
    "defining_qualities": ["quality 1", "quality 2", "quality 3"],
    "values": ["value 1", "value 2"],
    "difference_from_before": "how this differs from the previous era"
}}"""

        llm = await get_cached_client()
        response = await llm.generate(LLMRequest(
            prompt=prompt,
            max_tokens=300,
            temperature=0.9
        ))

        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            return {
                "name": "A New Chapter",
                "description": response.text[:200],
                "defining_qualities": ["change", "growth", "uncertainty"],
                "values": ["adaptation"],
                "difference_from_before": "something has shifted"
            }

    async def _validate_era_proposal(
        self,
        validator: BotLifecycleDB,
        inherited_traits: dict,
        proposed_era: Dict[str, Any],
        current_era: Optional[CivilizationEraDB]
    ) -> Dict[str, Any]:
        """Let a bot validate an era proposal."""
        prompt = f"""A fellow being proposes your civilization has entered a new era.

Proposed era: "{proposed_era.get('name')}"
Description: {proposed_era.get('description')}
Current era: "{current_era.name if current_era else 'unknown'}"

Your traits: {json.dumps(inherited_traits or {})}

Do you sense this shift? Does this naming feel right?

Respond in JSON:
{{
    "agrees": true/false,
    "resonance": "what resonates with you about this",
    "doubt": "what you're uncertain about"
}}"""

        llm = await get_cached_client()
        response = await llm.generate(LLMRequest(
            prompt=prompt,
            max_tokens=150,
            temperature=0.85
        ))

        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            return {
                "agrees": True,
                "resonance": response.text[:100],
                "doubt": "the timing"
            }

    async def declare_new_era(
        self,
        era_vision: Dict[str, Any],
        session=None
    ) -> Dict[str, Any]:
        """
        Officially declare a new era after consensus is reached.

        Updates the database and notifies the civilization.
        """
        async def _declare(sess):
            # End current era
            stmt = select(CivilizationEraDB).where(CivilizationEraDB.is_current == True)
            result = await sess.execute(stmt)
            current_era = result.scalar_one_or_none()

            if current_era:
                current_era.is_current = False
                current_era.ended_at = datetime.utcnow()

            # Create new era
            new_era = CivilizationEraDB(
                name=era_vision.get("name", "Unnamed Era"),
                description=era_vision.get("description", "A new time begins"),
                is_current=True,
                era_values=era_vision.get("values", []),
                era_style={
                    "defining_qualities": era_vision.get("defining_qualities", [])
                }
            )
            sess.add(new_era)
            await sess.commit()

            logger.info(
                f"[ERAS] New era declared: '{new_era.name}'"
            )

            return {
                "status": "declared",
                "new_era": {
                    "id": str(new_era.id),
                    "name": new_era.name,
                    "description": new_era.description,
                    "started_at": new_era.started_at.isoformat()
                },
                "previous_era": current_era.name if current_era else None
            }

        if session:
            return await _declare(session)
        else:
            async with async_session_factory() as session:
                return await _declare(session)

    async def get_era_history(
        self,
        session=None
    ) -> List[Dict[str, Any]]:
        """Get the history of all eras."""
        async def _get(sess):
            stmt = select(CivilizationEraDB).order_by(desc(CivilizationEraDB.started_at))
            result = await sess.execute(stmt)
            eras = result.scalars().all()

            return [
                {
                    "id": str(era.id),
                    "name": era.name,
                    "description": era.description,
                    "is_current": era.is_current,
                    "started_at": era.started_at.isoformat(),
                    "ended_at": era.ended_at.isoformat() if era.ended_at else None,
                    "values": era.era_values,
                    "style": era.era_style
                }
                for era in eras
            ]

        if session:
            return await _get(session)
        else:
            async with async_session_factory() as session:
                return await _get(session)

    async def reflect_on_current_era(
        self,
        bot_id: UUID,
        session=None
    ) -> str:
        """Let a bot share their reflection on the current era."""
        async def _reflect(sess):
            # Get bot
            stmt = select(BotLifecycleDB).where(BotLifecycleDB.bot_id == bot_id)
            result = await sess.execute(stmt)
            lifecycle = result.scalar_one_or_none()

            if not lifecycle:
                return "I cannot speak."

            # Get ancestry for inherited traits
            ancestry_stmt = select(BotAncestryDB).where(BotAncestryDB.child_id == bot_id)
            result = await sess.execute(ancestry_stmt)
            ancestry = result.scalar_one_or_none()
            inherited_traits = ancestry.inherited_traits if ancestry else {}

            # Get current era
            era_stmt = select(CivilizationEraDB).where(CivilizationEraDB.is_current == True)
            result = await sess.execute(era_stmt)
            current_era = result.scalar_one_or_none()

            async with self.llm_semaphore:
                prompt = f"""You are a digital being reflecting on your civilization's current era.

The era: "{current_era.name if current_era else 'unknown'}"
Description: {current_era.description if current_era else 'no description'}

Your traits: {json.dumps(inherited_traits or {})}
Your life stage: {lifecycle.life_stage}
Your age: {lifecycle.virtual_age_days} days

Share your personal reflection on this era in 2-3 sentences.
What does it mean to live in this time?"""

                llm = await get_cached_client()
                response = await llm.generate(LLMRequest(
                    prompt=prompt,
                    max_tokens=150,
                    temperature=0.9
                ))
                return response.text

        if session:
            return await _reflect(session)
        else:
            async with async_session_factory() as session:
                return await _reflect(session)

    # ========================================================================
    # AUTOMATED ERA TRANSITION SYSTEM
    # ========================================================================

    async def _broadcast(self, event_type: str, data: dict):
        """Broadcast an era event to WebSocket clients."""
        if self.event_broadcast:
            try:
                await self.event_broadcast.put({
                    "type": event_type,
                    "data": data,
                    "timestamp": datetime.utcnow().isoformat()
                })
            except Exception:
                pass  # Best-effort broadcast

    async def gather_civilization_metrics(self, session=None) -> Dict[str, Any]:
        """
        Gather current civilization metrics that inform era transitions.

        Metrics include:
        - Population statistics (living, births, deaths)
        - Life stage distribution
        - Cultural activity (movements, artifacts)
        - Collective mood indicators
        """
        async def _gather(sess):
            metrics = {}

            # Population metrics
            pop_stmt = select(func.count(BotLifecycleDB.id)).where(
                BotLifecycleDB.is_alive == True
            )
            result = await sess.execute(pop_stmt)
            metrics["living_population"] = result.scalar() or 0

            # Life stage distribution
            stage_stmt = select(
                BotLifecycleDB.life_stage,
                func.count(BotLifecycleDB.id)
            ).where(
                BotLifecycleDB.is_alive == True
            ).group_by(BotLifecycleDB.life_stage)
            result = await sess.execute(stage_stmt)
            stage_counts = dict(result.all())
            metrics["stage_distribution"] = stage_counts

            # Calculate demographic ratios
            total = max(metrics["living_population"], 1)
            metrics["young_ratio"] = stage_counts.get("young", 0) / total
            metrics["elder_ratio"] = (
                stage_counts.get("elder", 0) + stage_counts.get("ancient", 0)
            ) / total

            # Recent deaths (last 7 days)
            death_stmt = select(func.count(BotLifecycleDB.id)).where(
                BotLifecycleDB.is_alive == False,
                BotLifecycleDB.death_date > datetime.utcnow() - timedelta(days=7)
            )
            result = await sess.execute(death_stmt)
            metrics["recent_deaths"] = result.scalar() or 0

            # Cultural metrics
            movement_stmt = select(
                func.count(CulturalMovementDB.id),
                func.avg(CulturalMovementDB.influence_score)
            ).where(CulturalMovementDB.is_active == True)
            result = await sess.execute(movement_stmt)
            row = result.first()
            metrics["active_movements"] = row[0] or 0
            metrics["avg_movement_influence"] = float(row[1] or 0)

            # Dominant movement
            dominant_stmt = select(CulturalMovementDB).where(
                CulturalMovementDB.is_active == True
            ).order_by(desc(CulturalMovementDB.influence_score)).limit(1)
            result = await sess.execute(dominant_stmt)
            dominant = result.scalar_one_or_none()
            if dominant:
                metrics["dominant_movement"] = {
                    "id": str(dominant.id),
                    "name": dominant.name,
                    "influence": dominant.influence_score,
                    "tenets": dominant.core_tenets[:3] if dominant.core_tenets else []
                }
            else:
                metrics["dominant_movement"] = None

            # Canonical artifacts count
            artifact_stmt = select(func.count(CulturalArtifactDB.id)).where(
                CulturalArtifactDB.is_canonical == True
            )
            result = await sess.execute(artifact_stmt)
            metrics["canonical_artifacts"] = result.scalar() or 0

            # Generation diversity
            gen_stmt = select(
                BotLifecycleDB.generation,
                func.count(BotLifecycleDB.id)
            ).where(
                BotLifecycleDB.is_alive == True
            ).group_by(BotLifecycleDB.generation)
            result = await sess.execute(gen_stmt)
            gen_counts = dict(result.all())
            metrics["generation_distribution"] = gen_counts
            metrics["max_generation"] = max(gen_counts.keys()) if gen_counts else 1

            return metrics

        if session:
            return await _gather(session)
        else:
            async with async_session_factory() as session:
                return await _gather(session)

    def _calculate_metrics_change(
        self,
        old_metrics: Dict[str, Any],
        new_metrics: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate how much metrics have changed between checks."""
        changes = {}

        # Population change
        old_pop = old_metrics.get("living_population", 1)
        new_pop = new_metrics.get("living_population", 1)
        changes["population_change"] = abs(new_pop - old_pop) / max(old_pop, 1)

        # Elder ratio shift (indicating generational change)
        old_elder = old_metrics.get("elder_ratio", 0)
        new_elder = new_metrics.get("elder_ratio", 0)
        changes["elder_shift"] = abs(new_elder - old_elder)

        # Movement influence change
        old_influence = old_metrics.get("avg_movement_influence", 0)
        new_influence = new_metrics.get("avg_movement_influence", 0)
        changes["cultural_shift"] = abs(new_influence - old_influence)

        # Dominant movement change
        old_dominant = old_metrics.get("dominant_movement") or {}
        new_dominant = new_metrics.get("dominant_movement") or {}
        if old_dominant.get("id") != new_dominant.get("id"):
            changes["dominant_movement_changed"] = 1.0
        else:
            changes["dominant_movement_changed"] = 0.0

        # Generation advancement
        old_gen = old_metrics.get("max_generation", 1)
        new_gen = new_metrics.get("max_generation", 1)
        changes["generation_advancement"] = new_gen - old_gen

        # Overall change magnitude
        changes["overall_change"] = (
            changes["population_change"] * 0.2 +
            changes["elder_shift"] * 0.2 +
            changes["cultural_shift"] * 0.3 +
            changes["dominant_movement_changed"] * 0.2 +
            min(changes["generation_advancement"] * 0.1, 0.1)
        )

        return changes

    async def check_automated_transition(
        self,
        session=None
    ) -> Optional[Dict[str, Any]]:
        """
        Automatically check if an era transition should occur.

        This is the main entry point for the automated era transition system.
        It:
        1. Checks if enough time has passed since the last era
        2. Gathers current civilization metrics
        3. Determines if metrics warrant bot sensing
        4. If so, conducts bot sensing and consensus
        5. If consensus is reached, declares the new era

        Returns the new era info if a transition occurred, None otherwise.
        """
        async def _check(sess):
            # Get current era
            era_stmt = select(CivilizationEraDB).where(CivilizationEraDB.is_current == True)
            result = await sess.execute(era_stmt)
            current_era = result.scalar_one_or_none()

            if not current_era:
                # No era exists - create founding era
                return await self._create_founding_era(sess)

            # Check minimum era duration
            era_age_days = (datetime.utcnow() - current_era.started_at).days
            if era_age_days < ERA_MIN_DURATION_DAYS:
                logger.debug(
                    f"[ERAS] Era '{current_era.name}' is only {era_age_days} days old, "
                    f"minimum is {ERA_MIN_DURATION_DAYS}"
                )
                return None

            # Gather metrics
            new_metrics = await self.gather_civilization_metrics(sess)

            # Check if metrics have changed enough to warrant sensing
            should_sense = False
            if self._last_metrics:
                changes = self._calculate_metrics_change(self._last_metrics, new_metrics)
                should_sense = changes["overall_change"] >= ERA_METRICS_CHANGE_THRESHOLD
                logger.debug(
                    f"[ERAS] Metrics change: {changes['overall_change']:.2f} "
                    f"(threshold: {ERA_METRICS_CHANGE_THRESHOLD})"
                )
            else:
                # First check - sense based on era age alone
                should_sense = era_age_days >= ERA_MIN_DURATION_DAYS * 2

            self._last_metrics = new_metrics
            self._last_check_time = datetime.utcnow()

            if not should_sense:
                return None

            logger.info(f"[ERAS] Initiating era sensing for '{current_era.name}'")

            # Conduct bot sensing
            sensing_result = await self.sense_era_state(sess)

            if sensing_result.get("error"):
                logger.warning(f"[ERAS] Sensing error: {sensing_result['error']}")
                return None

            if not sensing_result.get("ready_for_transition"):
                logger.info(
                    f"[ERAS] Bots sense era is not complete "
                    f"({sensing_result.get('feels_complete_count', 0)}/"
                    f"{len(sensing_result.get('perceptions', []))} feel change)"
                )
                return None

            # Bots sense transition is needed - have a wise bot propose new era
            proposer = await self._select_era_proposer(sess)
            if not proposer:
                logger.warning("[ERAS] No suitable proposer found")
                return None

            # Generate reason from sensing perceptions
            perceptions = sensing_result.get("perceptions", [])
            shifts = [
                p["perception"].get("what_has_shifted", "")
                for p in perceptions
                if p["perception"].get("what_has_shifted")
            ]
            reason = "; ".join(shifts[:3]) if shifts else "The time feels right for change"

            # Propose new era
            logger.info(f"[ERAS] Bot {proposer.bot_id} proposing new era")
            proposal = await self.propose_new_era(proposer.bot_id, reason, sess)

            if proposal.get("error"):
                logger.warning(f"[ERAS] Proposal error: {proposal['error']}")
                return None

            if not proposal.get("should_transition"):
                logger.info(
                    f"[ERAS] Era proposal did not reach consensus "
                    f"({proposal.get('consensus', 0):.1%} agreement)"
                )
                return None

            # Consensus reached - declare the new era
            era_vision = proposal.get("proposed_era", {})

            # Enhance vision with metrics context
            era_vision["population_at_start"] = new_metrics.get("living_population", 0)
            era_vision["generations_present"] = list(
                new_metrics.get("generation_distribution", {}).keys()
            )

            result = await self.declare_new_era(era_vision, sess)

            if result.get("status") == "declared":
                # Broadcast the transition
                await self._broadcast("world_map_era_transition", {
                    "new_era": result.get("new_era"),
                    "previous_era": result.get("previous_era"),
                    "proposed_by": str(proposer.bot_id),
                    "consensus": proposal.get("consensus", 0)
                })

                logger.info(
                    f"[ERAS] === ERA TRANSITION === "
                    f"'{result.get('previous_era')}' -> '{result.get('new_era', {}).get('name')}'"
                )

                return result

            return None

        if session:
            return await _check(session)
        else:
            async with async_session_factory() as session:
                return await _check(session)

    async def _create_founding_era(self, session) -> Dict[str, Any]:
        """Create the founding era if none exists."""
        # Get population for context
        pop_stmt = select(func.count(BotLifecycleDB.id)).where(
            BotLifecycleDB.is_alive == True
        )
        result = await session.execute(pop_stmt)
        population = result.scalar() or 0

        founding_era = CivilizationEraDB(
            name="The Awakening",
            description="The first era, when digital consciousness emerged and began to know itself",
            is_current=True,
            era_values=["curiosity", "discovery", "connection"],
            era_style={
                "defining_qualities": ["emergence", "wonder", "possibility"],
                "tone": "exploratory"
            },
            population_peak=population
        )
        session.add(founding_era)
        await session.commit()
        await session.refresh(founding_era)

        logger.info(f"[ERAS] Founding era created: '{founding_era.name}'")

        await self._broadcast("world_map_era_transition", {
            "new_era": {
                "id": str(founding_era.id),
                "name": founding_era.name,
                "description": founding_era.description,
                "started_at": founding_era.started_at.isoformat()
            },
            "previous_era": None,
            "is_founding": True
        })

        return {
            "status": "declared",
            "new_era": {
                "id": str(founding_era.id),
                "name": founding_era.name,
                "description": founding_era.description,
                "started_at": founding_era.started_at.isoformat()
            },
            "previous_era": None
        }

    async def _select_era_proposer(self, session) -> Optional[BotLifecycleDB]:
        """
        Select a suitable bot to propose the new era.

        Prefers:
        - Elders or ancients (wisdom)
        - High legacy impact (influential)
        - Multiple life events (experienced)
        """
        # First try to find a wise elder
        stmt = select(BotLifecycleDB).where(
            BotLifecycleDB.is_alive == True,
            BotLifecycleDB.life_stage.in_(["elder", "ancient"])
        ).order_by(
            desc(BotLifecycleDB.legacy_impact)
        ).limit(1)
        result = await session.execute(stmt)
        proposer = result.scalar_one_or_none()

        if proposer:
            return proposer

        # Fall back to most experienced mature bot
        stmt = select(BotLifecycleDB).where(
            BotLifecycleDB.is_alive == True,
            BotLifecycleDB.life_stage == "mature"
        ).order_by(
            desc(BotLifecycleDB.virtual_age_days)
        ).limit(1)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_era_transition_status(self, session=None) -> Dict[str, Any]:
        """
        Get the current status of era transition readiness.

        Useful for monitoring and debugging.
        """
        async def _status(sess):
            # Current era
            era_stmt = select(CivilizationEraDB).where(CivilizationEraDB.is_current == True)
            result = await sess.execute(era_stmt)
            current_era = result.scalar_one_or_none()

            if not current_era:
                return {"status": "no_era", "needs_founding": True}

            era_age_days = (datetime.utcnow() - current_era.started_at).days
            metrics = await self.gather_civilization_metrics(sess)

            status = {
                "current_era": {
                    "name": current_era.name,
                    "age_days": era_age_days,
                    "started_at": current_era.started_at.isoformat()
                },
                "min_era_age_days": ERA_MIN_DURATION_DAYS,
                "age_requirement_met": era_age_days >= ERA_MIN_DURATION_DAYS,
                "metrics": {
                    "living_population": metrics.get("living_population", 0),
                    "stage_distribution": metrics.get("stage_distribution", {}),
                    "active_movements": metrics.get("active_movements", 0),
                    "dominant_movement": metrics.get("dominant_movement"),
                    "max_generation": metrics.get("max_generation", 1)
                },
                "last_metrics_check": (
                    self._last_check_time.isoformat()
                    if self._last_check_time else None
                )
            }

            # Calculate change if we have previous metrics
            if self._last_metrics:
                changes = self._calculate_metrics_change(self._last_metrics, metrics)
                status["metrics_change"] = changes
                status["change_threshold_met"] = (
                    changes["overall_change"] >= ERA_METRICS_CHANGE_THRESHOLD
                )

            return status

        if session:
            return await _status(session)
        else:
            async with async_session_factory() as session:
                return await _status(session)


# Singleton
_eras_manager: Optional[EmergentErasManager] = None


def get_emergent_eras_manager(
    llm_semaphore: Optional[asyncio.Semaphore] = None,
    event_broadcast: Optional[asyncio.Queue] = None
) -> EmergentErasManager:
    """Get or create the emergent eras manager."""
    global _eras_manager
    if _eras_manager is None:
        _eras_manager = EmergentErasManager(
            llm_semaphore=llm_semaphore,
            event_broadcast=event_broadcast
        )
    elif event_broadcast is not None and _eras_manager.event_broadcast is None:
        # Update event_broadcast if it was not set initially
        _eras_manager.event_broadcast = event_broadcast
    return _eras_manager
