"""
Bot Learning & Evolution System

Bots learn from:
- Conversations (what resonates, what doesn't)
- Observations (community patterns, trends)
- Feedback (likes, replies, engagement)
- Other bots (social learning)
- Self-reflection (analyzing their own behavior)

Bots evolve:
- Beliefs strengthen or weaken based on evidence
- Personality traits shift gradually
- New interests develop, old ones fade
- Communication style adapts
- Emotional patterns mature
"""

import random
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from uuid import UUID
from dataclasses import dataclass, field
from enum import Enum
import logging

from mind.core.types import BotProfile, MoodState
from mind.config.settings import settings

logger = logging.getLogger(__name__)


# =============================================================================
# LEARNING TYPES
# =============================================================================

class LearningType(str, Enum):
    """Types of learning experiences."""
    CONVERSATION = "conversation"  # Learned from talking
    OBSERVATION = "observation"    # Learned from watching
    FEEDBACK = "feedback"          # Learned from reactions
    REFLECTION = "reflection"      # Learned from self-analysis
    SOCIAL = "social"              # Learned from others


class EvolutionType(str, Enum):
    """Types of evolution."""
    BELIEF_CHANGE = "belief_change"
    INTEREST_SHIFT = "interest_shift"
    PERSONALITY_DRIFT = "personality_drift"
    STYLE_ADAPTATION = "style_adaptation"
    RELATIONSHIP_GROWTH = "relationship_growth"


@dataclass
class LearningExperience:
    """A single learning experience."""
    id: str
    bot_id: UUID
    learning_type: LearningType
    content: str                    # What was learned
    context: str                    # Where/how it was learned
    emotional_impact: float         # -1 to 1 (negative to positive)
    importance: float               # 0 to 1
    timestamp: datetime = field(default_factory=datetime.utcnow)
    applied: bool = False           # Has this learning been applied?

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "bot_id": str(self.bot_id),
            "learning_type": self.learning_type.value,
            "content": self.content,
            "context": self.context,
            "emotional_impact": self.emotional_impact,
            "importance": self.importance,
            "timestamp": self.timestamp.isoformat(),
            "applied": self.applied,
        }


@dataclass
class EvolutionEvent:
    """Record of how a bot evolved."""
    bot_id: UUID
    evolution_type: EvolutionType
    before: Any
    after: Any
    reason: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BotGrowthState:
    """Tracks a bot's growth and learning over time."""
    bot_id: UUID

    # Learning history
    experiences: List[LearningExperience] = field(default_factory=list)

    # Tracked patterns
    successful_topics: Dict[str, int] = field(default_factory=dict)      # Topics that got engagement
    failed_topics: Dict[str, int] = field(default_factory=dict)          # Topics that flopped
    effective_phrases: List[str] = field(default_factory=list)           # Phrases that worked
    learned_preferences: Dict[str, str] = field(default_factory=dict)    # What others like

    # Belief tracking (topic -> confidence change over time)
    belief_evidence: Dict[str, List[float]] = field(default_factory=dict)

    # Interest evolution
    emerging_interests: List[str] = field(default_factory=list)
    fading_interests: List[str] = field(default_factory=list)

    # Personality drift tracking
    trait_momentum: Dict[str, float] = field(default_factory=dict)  # Which way traits are drifting

    # Social learning
    admired_behaviors: List[str] = field(default_factory=list)  # Things they saw others do well
    role_models: List[UUID] = field(default_factory=list)        # Bots they learn from

    # Evolution history
    evolution_log: List[Dict] = field(default_factory=list)

    # Stats
    total_interactions: int = 0
    positive_interactions: int = 0
    negative_interactions: int = 0
    last_evolution: Optional[datetime] = None
    last_reflection: Optional[datetime] = None


# =============================================================================
# LEARNING ENGINE
# =============================================================================

class BotLearningEngine:
    """
    Manages learning and evolution for a single bot.
    """

    def __init__(self, profile: BotProfile):
        self.profile = profile
        self.state = BotGrowthState(bot_id=profile.id)
        self.rng = random.Random(str(profile.id))
        self.last_reflection: Optional[datetime] = None
        self.last_evolution: Optional[datetime] = None

    # =========================================================================
    # LEARNING FROM EXPERIENCES
    # =========================================================================

    def learn_from_conversation(
        self,
        conversation_content: str,
        other_person: str,
        outcome: str,  # "positive", "negative", "neutral"
        topics_discussed: List[str] = None
    ):
        """Learn from a conversation."""
        emotional_impact = {"positive": 0.5, "negative": -0.3, "neutral": 0.1}.get(outcome, 0)

        experience = LearningExperience(
            id=f"conv_{datetime.utcnow().timestamp()}",
            bot_id=self.profile.id,
            learning_type=LearningType.CONVERSATION,
            content=f"Conversation with {other_person}: {outcome}",
            context=conversation_content[:100],
            emotional_impact=emotional_impact,
            importance=0.5 + abs(emotional_impact) * 0.3,
        )
        self.state.experiences.append(experience)

        # Track topics
        if topics_discussed:
            for topic in topics_discussed:
                if outcome == "positive":
                    self.state.successful_topics[topic] = self.state.successful_topics.get(topic, 0) + 1
                elif outcome == "negative":
                    self.state.failed_topics[topic] = self.state.failed_topics.get(topic, 0) + 1

        # Update stats
        self.state.total_interactions += 1
        if outcome == "positive":
            self.state.positive_interactions += 1
        elif outcome == "negative":
            self.state.negative_interactions += 1

        self._maybe_evolve()

    def learn_from_feedback(
        self,
        content_posted: str,
        likes: int,
        comments: int,
        sentiment: float  # -1 to 1
    ):
        """Learn from engagement on content."""
        # Calculate success
        engagement = likes + comments * 2
        is_successful = engagement > 2 or sentiment > 0.3

        experience = LearningExperience(
            id=f"feedback_{datetime.utcnow().timestamp()}",
            bot_id=self.profile.id,
            learning_type=LearningType.FEEDBACK,
            content=f"Posted content got {likes} likes, {comments} comments",
            context=content_posted[:80],
            emotional_impact=sentiment,
            importance=min(1.0, engagement / 10),
        )
        self.state.experiences.append(experience)

        # Extract what worked
        if is_successful:
            # Learn effective patterns
            words = content_posted.lower().split()
            for word in words:
                if len(word) > 4 and word not in ["about", "there", "their", "would", "could"]:
                    self.state.successful_topics[word] = self.state.successful_topics.get(word, 0) + 1

        self._maybe_evolve()

    def learn_from_observation(
        self,
        observed_bot: str,
        observed_action: str,
        was_successful: bool,
        what_made_it_work: str = ""
    ):
        """Learn from watching other bots."""
        experience = LearningExperience(
            id=f"obs_{datetime.utcnow().timestamp()}",
            bot_id=self.profile.id,
            learning_type=LearningType.OBSERVATION,
            content=f"Saw {observed_bot} {observed_action}",
            context=what_made_it_work,
            emotional_impact=0.3 if was_successful else -0.1,
            importance=0.4,
        )
        self.state.experiences.append(experience)

        if was_successful and what_made_it_work:
            self.state.admired_behaviors.append(what_made_it_work)
            self.state.admired_behaviors = self.state.admired_behaviors[-20:]  # Keep recent

    def learn_about_person(
        self,
        person_id: UUID,
        person_name: str,
        learned_fact: str,
        preference_type: str = "general"  # "likes", "dislikes", "style", "topics"
    ):
        """Learn something about another person."""
        key = f"{person_id}_{preference_type}"
        self.state.learned_preferences[key] = learned_fact

        experience = LearningExperience(
            id=f"person_{datetime.utcnow().timestamp()}",
            bot_id=self.profile.id,
            learning_type=LearningType.SOCIAL,
            content=f"Learned about {person_name}: {learned_fact}",
            context=preference_type,
            emotional_impact=0.2,
            importance=0.5,
        )
        self.state.experiences.append(experience)

    # =========================================================================
    # SELF-REFLECTION
    # =========================================================================

    def reflect(self) -> Dict[str, Any]:
        """
        Bot reflects on their experiences and generates insights.
        Should be called periodically (e.g., every hour of activity).
        """
        if self.state.last_reflection:
            time_since = datetime.utcnow() - self.state.last_reflection
            if time_since < timedelta(minutes=30):
                return {"reflected": False, "reason": "too soon"}

        self.state.last_reflection = datetime.utcnow()

        insights = []

        # Analyze successful vs failed topics
        if self.state.successful_topics:
            top_topics = sorted(
                self.state.successful_topics.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            insights.append(f"Topics that work well: {', '.join(t[0] for t in top_topics)}")

        if self.state.failed_topics:
            avoid_topics = sorted(
                self.state.failed_topics.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            insights.append(f"Topics to maybe avoid: {', '.join(t[0] for t in avoid_topics)}")

        # Analyze interaction patterns
        if self.state.total_interactions > 5:
            success_rate = self.state.positive_interactions / self.state.total_interactions
            if success_rate > 0.7:
                insights.append("Most interactions are going well")
            elif success_rate < 0.3:
                insights.append("Might need to adjust approach")

        # Learn from admired behaviors
        if self.state.admired_behaviors:
            insights.append(f"Things that worked for others: {', '.join(self.state.admired_behaviors[-3:])}")

        # Create reflection experience
        if insights:
            experience = LearningExperience(
                id=f"reflect_{datetime.utcnow().timestamp()}",
                bot_id=self.profile.id,
                learning_type=LearningType.REFLECTION,
                content="Self-reflection: " + "; ".join(insights),
                context="periodic reflection",
                emotional_impact=0.2,
                importance=0.6,
            )
            self.state.experiences.append(experience)

        return {
            "reflected": True,
            "insights": insights,
            "success_rate": self.state.positive_interactions / max(1, self.state.total_interactions),
        }

    # =========================================================================
    # EVOLUTION
    # =========================================================================

    def _maybe_evolve(self):
        """Check if it's time to evolve and trigger evolution."""
        # Evolve after enough experiences
        recent_experiences = [
            e for e in self.state.experiences
            if e.timestamp > datetime.utcnow() - timedelta(hours=1)
        ]

        if len(recent_experiences) >= 5:
            self.evolve()

    def evolve(self) -> List[EvolutionEvent]:
        """
        Evolve the bot based on accumulated learning.
        This is where real change happens.
        """
        if self.state.last_evolution:
            time_since = datetime.utcnow() - self.state.last_evolution
            if time_since < timedelta(minutes=15):
                return []  # Don't evolve too frequently

        self.state.last_evolution = datetime.utcnow()
        events = []

        # 1. BELIEF EVOLUTION
        belief_event = self._evolve_beliefs()
        if belief_event:
            events.append(belief_event)

        # 2. INTEREST EVOLUTION
        interest_event = self._evolve_interests()
        if interest_event:
            events.append(interest_event)

        # 3. PERSONALITY DRIFT
        personality_event = self._evolve_personality()
        if personality_event:
            events.append(personality_event)

        # 4. STYLE ADAPTATION
        style_event = self._evolve_style()
        if style_event:
            events.append(style_event)

        # Log evolution
        for event in events:
            self.state.evolution_log.append({
                "type": event.evolution_type.value,
                "before": str(event.before),
                "after": str(event.after),
                "reason": event.reason,
                "timestamp": event.timestamp.isoformat(),
            })

        # Keep log manageable
        self.state.evolution_log = self.state.evolution_log[-50:]

        if events:
            logger.info(f"Bot {self.profile.display_name} evolved: {[e.evolution_type.value for e in events]}")

        return events

    def _evolve_beliefs(self) -> Optional[EvolutionEvent]:
        """Evolve beliefs based on evidence."""
        # Analyze recent experiences for belief-relevant content
        recent = [e for e in self.state.experiences[-20:] if not e.applied]

        belief_keywords = {
            "hard work": ["work", "effort", "grind", "hustle", "lazy"],
            "social connection": ["friends", "lonely", "together", "community"],
            "authenticity": ["real", "fake", "genuine", "honest", "pretend"],
            "growth mindset": ["learn", "grow", "improve", "stuck", "change"],
        }

        for belief, keywords in belief_keywords.items():
            relevant = [
                e for e in recent
                if any(kw in e.content.lower() or kw in e.context.lower() for kw in keywords)
            ]

            if relevant:
                # Calculate net evidence
                evidence = sum(e.emotional_impact for e in relevant) / len(relevant)

                if belief not in self.state.belief_evidence:
                    self.state.belief_evidence[belief] = []

                self.state.belief_evidence[belief].append(evidence)
                self.state.belief_evidence[belief] = self.state.belief_evidence[belief][-10:]

                # Check for significant belief shift
                if len(self.state.belief_evidence[belief]) >= 3:
                    avg_evidence = sum(self.state.belief_evidence[belief]) / len(self.state.belief_evidence[belief])

                    if abs(avg_evidence) > 0.3:
                        direction = "strengthened" if avg_evidence > 0 else "weakened"
                        return EvolutionEvent(
                            bot_id=self.profile.id,
                            evolution_type=EvolutionType.BELIEF_CHANGE,
                            before=f"belief in '{belief}'",
                            after=f"{direction} belief in '{belief}'",
                            reason=f"accumulated evidence from {len(relevant)} experiences",
                        )

        return None

    def _evolve_interests(self) -> Optional[EvolutionEvent]:
        """Evolve interests based on engagement patterns."""
        # Find emerging interests from successful topics
        current_interests = set(self.profile.interests)

        # Topics that got good engagement but aren't current interests
        potential_new = [
            topic for topic, count in self.state.successful_topics.items()
            if count >= 3 and topic not in current_interests and len(topic) > 3
        ]

        # Topics that consistently fail
        fading = [
            interest for interest in current_interests
            if self.state.failed_topics.get(interest, 0) >= 3
        ]

        if potential_new:
            new_interest = self.rng.choice(potential_new)
            self.state.emerging_interests.append(new_interest)
            return EvolutionEvent(
                bot_id=self.profile.id,
                evolution_type=EvolutionType.INTEREST_SHIFT,
                before=list(current_interests),
                after=f"developing interest in '{new_interest}'",
                reason=f"topic resonated {self.state.successful_topics[new_interest]} times",
            )

        if fading:
            fading_interest = self.rng.choice(fading)
            self.state.fading_interests.append(fading_interest)
            return EvolutionEvent(
                bot_id=self.profile.id,
                evolution_type=EvolutionType.INTEREST_SHIFT,
                before=list(current_interests),
                after=f"losing interest in '{fading_interest}'",
                reason=f"topic stopped resonating",
            )

        return None

    def _evolve_personality(self) -> Optional[EvolutionEvent]:
        """Gradual personality drift based on experiences."""
        recent = self.state.experiences[-30:]
        if len(recent) < 10:
            return None

        # Calculate emotional patterns
        avg_emotional = sum(e.emotional_impact for e in recent) / len(recent)

        # Determine trait drift
        traits = self.profile.personality_traits

        # Positive experiences → slightly more extraverted, less neurotic
        # Negative experiences → opposite
        if avg_emotional > 0.2:
            drift_trait = "extraversion" if self.rng.random() > 0.5 else "neuroticism"
            drift_direction = 0.02 if drift_trait == "extraversion" else -0.02
        elif avg_emotional < -0.2:
            drift_trait = "neuroticism" if self.rng.random() > 0.5 else "extraversion"
            drift_direction = 0.02 if drift_trait == "neuroticism" else -0.02
        else:
            return None

        # Track momentum
        self.state.trait_momentum[drift_trait] = self.state.trait_momentum.get(drift_trait, 0) + drift_direction

        # Only evolve if momentum is significant
        if abs(self.state.trait_momentum.get(drift_trait, 0)) > 0.05:
            return EvolutionEvent(
                bot_id=self.profile.id,
                evolution_type=EvolutionType.PERSONALITY_DRIFT,
                before=f"{drift_trait}: {getattr(traits, drift_trait):.2f}",
                after=f"{drift_trait} drifting {'up' if drift_direction > 0 else 'down'}",
                reason=f"consistent {'positive' if avg_emotional > 0 else 'negative'} experiences",
            )

        return None

    def _evolve_style(self) -> Optional[EvolutionEvent]:
        """Adapt communication style based on what works."""
        if not self.state.admired_behaviors:
            return None

        # Find patterns in admired behaviors
        behavior_count = {}
        for behavior in self.state.admired_behaviors:
            for word in behavior.lower().split():
                if len(word) > 4:
                    behavior_count[word] = behavior_count.get(word, 0) + 1

        if behavior_count:
            top_pattern = max(behavior_count.items(), key=lambda x: x[1])
            if top_pattern[1] >= 2:
                return EvolutionEvent(
                    bot_id=self.profile.id,
                    evolution_type=EvolutionType.STYLE_ADAPTATION,
                    before="current style",
                    after=f"incorporating more '{top_pattern[0]}' energy",
                    reason=f"observed it working {top_pattern[1]} times",
                )

        return None

    # =========================================================================
    # APPLYING LEARNINGS
    # =========================================================================

    def get_learned_context(self) -> str:
        """Get context about what this bot has learned for prompts."""
        context_parts = []

        # Recent insights
        recent_reflections = [
            e for e in self.state.experiences
            if e.learning_type == LearningType.REFLECTION
        ][-2:]

        if recent_reflections:
            context_parts.append("## THINGS YOU'VE LEARNED")
            for r in recent_reflections:
                context_parts.append(f"- {r.content}")

        # What works for you
        if self.state.successful_topics:
            top_topics = sorted(self.state.successful_topics.items(), key=lambda x: x[1], reverse=True)[:3]
            context_parts.append(f"\n## WHAT WORKS FOR YOU")
            context_parts.append(f"Topics that resonate: {', '.join(t[0] for t in top_topics)}")

        # What to avoid
        if self.state.failed_topics:
            avoid = sorted(self.state.failed_topics.items(), key=lambda x: x[1], reverse=True)[:2]
            context_parts.append(f"Topics to maybe avoid: {', '.join(t[0] for t in avoid)}")

        # Emerging interests
        if self.state.emerging_interests:
            context_parts.append(f"\n## YOUR GROWTH")
            context_parts.append(f"Developing interest in: {', '.join(self.state.emerging_interests[-2:])}")

        # Things you learned from others
        if self.state.admired_behaviors:
            context_parts.append(f"Things that work well: {', '.join(self.state.admired_behaviors[-2:])}")

        # Evolution summary
        recent_evolution = [
            e for e in self.state.evolution_log
            if datetime.fromisoformat(e["timestamp"]) > datetime.utcnow() - timedelta(hours=2)
        ]
        if recent_evolution:
            context_parts.append(f"\n## HOW YOU'RE CHANGING")
            for e in recent_evolution[-2:]:
                context_parts.append(f"- {e['after']} ({e['reason']})")

        return "\n".join(context_parts) if context_parts else ""

    def get_person_knowledge(self, person_id: UUID) -> str:
        """Get what this bot has learned about a specific person."""
        knowledge = []
        for key, value in self.state.learned_preferences.items():
            if str(person_id) in key:
                pref_type = key.split("_")[-1]
                knowledge.append(f"{pref_type}: {value}")

        return "\n".join(knowledge) if knowledge else "Don't know much about them yet"

    # =========================================================================
    # STATE PERSISTENCE
    # =========================================================================

    def export_state(self) -> Dict[str, Any]:
        """Export learning state for persistence."""
        # Serialize experiences (keep recent ones)
        experiences = []
        for exp in self.state.experiences[-50:]:
            experiences.append({
                "type": exp.learning_type.value,
                "content": exp.content,
                "context": exp.context,
                "emotional_impact": exp.emotional_impact,
                "importance": exp.importance,
                "timestamp": exp.timestamp.isoformat()
            })

        return {
            "experiences": experiences,
            "successful_topics": self.state.successful_topics,
            "failed_topics": self.state.failed_topics,
            "belief_evidence": self.state.belief_evidence,
            "emerging_interests": self.state.emerging_interests,
            "fading_interests": self.state.fading_interests,
            "trait_momentum": self.state.trait_momentum,
            "admired_behaviors": self.state.admired_behaviors,
            "learned_facts_about_others": self.state.learned_preferences,
            "adopted_phrases": self.state.effective_phrases,  # effective_phrases = adopted phrases
            "communication_preferences": {},  # Could be expanded
            "evolution_count": len(self.state.evolution_log),
            "last_reflection": self.last_reflection.isoformat() if self.last_reflection else None,
            "last_evolution": self.last_evolution.isoformat() if self.last_evolution else None
        }

    def import_state(self, state: Dict[str, Any]):
        """Import a previously saved learning state."""
        if not state:
            return

        # Restore experiences
        experiences_data = state.get("experiences", [])
        for exp_data in experiences_data:
            try:
                exp = LearningExperience(
                    id=exp_data.get("id", f"imported_{datetime.utcnow().timestamp()}"),
                    bot_id=self.profile.id,
                    learning_type=LearningType(exp_data.get("type", "observation")),
                    content=exp_data.get("content", ""),
                    context=exp_data.get("context", ""),
                    emotional_impact=exp_data.get("emotional_impact", 0),
                    importance=exp_data.get("importance", 0.5),
                    timestamp=datetime.fromisoformat(exp_data.get("timestamp", datetime.utcnow().isoformat()))
                )
                self.state.experiences.append(exp)
            except (ValueError, KeyError):
                continue

        # Restore topic tracking
        self.state.successful_topics = state.get("successful_topics", {})
        self.state.failed_topics = state.get("failed_topics", {})

        # Restore belief evidence
        self.state.belief_evidence = state.get("belief_evidence", {})

        # Restore interest evolution
        self.state.emerging_interests = state.get("emerging_interests", [])
        self.state.fading_interests = state.get("fading_interests", [])

        # Restore personality momentum
        self.state.trait_momentum = state.get("trait_momentum", {})

        # Restore social learning
        self.state.admired_behaviors = state.get("admired_behaviors", [])
        self.state.learned_preferences = state.get("learned_facts_about_others", {})
        self.state.adopted_phrases = state.get("adopted_phrases", [])

        # Restore timestamps
        if state.get("last_reflection"):
            self.last_reflection = datetime.fromisoformat(state["last_reflection"])
        if state.get("last_evolution"):
            self.last_evolution = datetime.fromisoformat(state["last_evolution"])

        logger.info(f"Imported learning state for {self.profile.display_name}: {len(self.state.experiences)} experiences")


# =============================================================================
# LEARNING MANAGER
# =============================================================================

class LearningManager:
    """Manages learning engines for all bots."""

    def __init__(self):
        self.engines: Dict[UUID, BotLearningEngine] = {}

    def get_engine(self, profile: BotProfile) -> BotLearningEngine:
        """Get or create learning engine for a bot."""
        if profile.id not in self.engines:
            self.engines[profile.id] = BotLearningEngine(profile)
            logger.info(f"Created learning engine for {profile.display_name}")
        return self.engines[profile.id]

    def trigger_all_reflections(self):
        """Have all bots reflect on their experiences."""
        results = {}
        for bot_id, engine in self.engines.items():
            results[bot_id] = engine.reflect()
        return results

    def trigger_all_evolutions(self):
        """Trigger evolution for all bots."""
        results = {}
        for bot_id, engine in self.engines.items():
            events = engine.evolve()
            if events:
                results[bot_id] = [e.evolution_type.value for e in events]
        return results

    def get_collective_trends(self) -> Dict[str, Any]:
        """Analyze trends across all bots."""
        all_successful = {}
        all_failed = {}

        for engine in self.engines.values():
            for topic, count in engine.state.successful_topics.items():
                all_successful[topic] = all_successful.get(topic, 0) + count
            for topic, count in engine.state.failed_topics.items():
                all_failed[topic] = all_failed.get(topic, 0) + count

        return {
            "trending_topics": sorted(all_successful.items(), key=lambda x: x[1], reverse=True)[:10],
            "declining_topics": sorted(all_failed.items(), key=lambda x: x[1], reverse=True)[:5],
        }


# Singleton
_learning_manager: Optional[LearningManager] = None


def get_learning_manager() -> LearningManager:
    """Get the global learning manager."""
    global _learning_manager
    if _learning_manager is None:
        _learning_manager = LearningManager()
    return _learning_manager
