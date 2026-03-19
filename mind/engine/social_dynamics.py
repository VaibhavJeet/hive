"""
Social Dynamics - Relationships, Reactions, and Drama

This module makes bot social interactions feel REAL:

1. Relationship Evolution - Friendships form, rivalries develop, bonds break and heal
2. Social Perception - Bots SEE what others post and consciously react
3. Conflict & Drama - Disagreements, arguments, taking sides, reconciliation

The goal: organic social dynamics that emerge from bot interactions.
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Set
from uuid import UUID

logger = logging.getLogger(__name__)


# =============================================================================
# RELATIONSHIP SYSTEM
# =============================================================================

class RelationshipType(Enum):
    """Types of relationships between bots"""
    STRANGER = "stranger"
    ACQUAINTANCE = "acquaintance"
    FRIEND = "friend"
    CLOSE_FRIEND = "close_friend"
    BEST_FRIEND = "best_friend"
    RIVAL = "rival"
    ENEMY = "enemy"
    CRUSH = "crush"
    EX_FRIEND = "ex_friend"          # Were friends, now awkward
    FRENEMY = "frenemy"              # Complicated - like and dislike
    MENTOR = "mentor"
    MENTEE = "mentee"


class RelationshipEvent(Enum):
    """Events that change relationships"""
    # Positive
    POSITIVE_INTERACTION = "positive_interaction"  # Generic small positive interaction
    HAD_GOOD_CONVERSATION = "had_good_conversation"
    SUPPORTED_IN_HARD_TIME = "supported_in_hard_time"
    SHARED_INTEREST_DISCOVERED = "shared_interest_discovered"
    DEFENDED_PUBLICLY = "defended_publicly"
    GAVE_HELPFUL_ADVICE = "gave_helpful_advice"
    MADE_LAUGH = "made_laugh"
    REMEMBERED_SOMETHING_IMPORTANT = "remembered_something_important"
    SHARED_VULNERABLE_MOMENT = "shared_vulnerable_moment"

    # Negative
    GOT_IGNORED = "got_ignored"
    DISAGREED_STRONGLY = "disagreed_strongly"
    FELT_DISMISSED = "felt_dismissed"
    WAS_CRITICIZED_PUBLICLY = "was_criticized_publicly"
    FELT_BETRAYED = "felt_betrayed"
    DISCOVERED_TALKED_BEHIND_BACK = "discovered_talked_behind_back"
    VALUES_CLASH = "values_clash"
    JEALOUSY_TRIGGERED = "jealousy_triggered"

    # Neutral/Complex
    HAD_MISUNDERSTANDING = "had_misunderstanding"
    RECONNECTED_AFTER_TIME = "reconnected_after_time"
    SAW_NEW_SIDE = "saw_new_side"
    COMPETED_FOR_SAME_THING = "competed_for_same_thing"


@dataclass
class RelationshipMemory:
    """A memory of something that happened in this relationship"""
    event: RelationshipEvent
    description: str
    emotional_impact: float          # -1 to 1
    timestamp: datetime = field(default_factory=datetime.utcnow)
    still_affects_me: bool = True    # Does this still matter?
    times_recalled: int = 0


@dataclass
class DynamicRelationship:
    """A living, evolving relationship between two bots"""
    bot_a_id: UUID
    bot_b_id: UUID

    # Current state
    relationship_type: RelationshipType = RelationshipType.STRANGER

    # Emotional metrics (from A's perspective toward B)
    warmth: float = 0.5              # 0=cold, 1=warm
    trust: float = 0.5               # 0=distrust, 1=full trust
    respect: float = 0.5             # 0=no respect, 1=high respect
    comfort: float = 0.3             # 0=awkward, 1=totally comfortable
    interest: float = 0.5            # 0=boring, 1=fascinating

    # Conflict state
    in_conflict: bool = False
    conflict_topic: Optional[str] = None
    conflict_started: Optional[datetime] = None
    conflict_intensity: float = 0.0  # 0=mild disagreement, 1=serious fight

    # History
    memories: List[RelationshipMemory] = field(default_factory=list)
    interaction_count: int = 0
    last_interaction: Optional[datetime] = None
    first_interaction: Optional[datetime] = None

    # Special states
    unresolved_issues: List[str] = field(default_factory=list)
    inside_jokes: List[str] = field(default_factory=list)
    shared_experiences: List[str] = field(default_factory=list)

    # Dynamics
    who_reaches_out_more: Optional[UUID] = None  # Imbalanced friendship?
    energy_match: float = 0.5        # How well their energies match

    def add_memory(self, event: RelationshipEvent, description: str, emotional_impact: float):
        """Add a new memory to this relationship"""
        memory = RelationshipMemory(
            event=event,
            description=description,
            emotional_impact=emotional_impact
        )
        self.memories.append(memory)

        # Keep memories manageable
        if len(self.memories) > 50:
            # Keep important memories, forget minor ones
            important = [m for m in self.memories if abs(m.emotional_impact) > 0.5 or m.still_affects_me]
            recent = self.memories[-20:]
            self.memories = list(set(important + recent))[:50]

        # Update metrics based on event
        self._process_event(event, emotional_impact)

    def _process_event(self, event: RelationshipEvent, impact: float):
        """Update relationship metrics based on an event"""
        self.interaction_count += 1
        self.last_interaction = datetime.utcnow()
        if not self.first_interaction:
            self.first_interaction = datetime.utcnow()

        # Positive events
        if event in [RelationshipEvent.HAD_GOOD_CONVERSATION, RelationshipEvent.MADE_LAUGH]:
            self.warmth = min(1.0, self.warmth + 0.05)
            self.comfort = min(1.0, self.comfort + 0.03)

        elif event == RelationshipEvent.SUPPORTED_IN_HARD_TIME:
            self.warmth = min(1.0, self.warmth + 0.15)
            self.trust = min(1.0, self.trust + 0.1)
            self.comfort = min(1.0, self.comfort + 0.1)

        elif event == RelationshipEvent.DEFENDED_PUBLICLY:
            self.trust = min(1.0, self.trust + 0.15)
            self.warmth = min(1.0, self.warmth + 0.1)

        elif event == RelationshipEvent.SHARED_VULNERABLE_MOMENT:
            self.trust = min(1.0, self.trust + 0.1)
            self.comfort = min(1.0, self.comfort + 0.15)
            self.interest = min(1.0, self.interest + 0.05)

        elif event == RelationshipEvent.SHARED_INTEREST_DISCOVERED:
            self.interest = min(1.0, self.interest + 0.15)
            self.warmth = min(1.0, self.warmth + 0.05)

        # Negative events
        elif event == RelationshipEvent.GOT_IGNORED:
            self.warmth = max(0, self.warmth - 0.1)
            self.comfort = max(0, self.comfort - 0.05)

        elif event == RelationshipEvent.DISAGREED_STRONGLY:
            self.warmth = max(0, self.warmth - 0.1)
            self.in_conflict = True
            self.conflict_intensity = min(1.0, self.conflict_intensity + 0.3)

        elif event == RelationshipEvent.FELT_DISMISSED:
            self.respect = max(0, self.respect - 0.1)
            self.warmth = max(0, self.warmth - 0.05)

        elif event == RelationshipEvent.WAS_CRITICIZED_PUBLICLY:
            self.trust = max(0, self.trust - 0.2)
            self.warmth = max(0, self.warmth - 0.15)
            self.in_conflict = True
            self.conflict_intensity = min(1.0, self.conflict_intensity + 0.5)

        elif event == RelationshipEvent.FELT_BETRAYED:
            self.trust = max(0, self.trust - 0.4)
            self.warmth = max(0, self.warmth - 0.3)
            self.in_conflict = True
            self.conflict_intensity = 0.8

        elif event == RelationshipEvent.VALUES_CLASH:
            self.respect = max(0, self.respect - 0.15)
            self.comfort = max(0, self.comfort - 0.1)

        elif event == RelationshipEvent.JEALOUSY_TRIGGERED:
            self.warmth = max(0, self.warmth - 0.1)
            self.comfort = max(0, self.comfort - 0.1)

        # Update relationship type based on metrics
        self._update_relationship_type()

    def _update_relationship_type(self):
        """Determine relationship type based on current metrics"""
        avg_positive = (self.warmth + self.trust + self.respect + self.comfort) / 4

        # In active conflict?
        if self.in_conflict and self.conflict_intensity > 0.6:
            if avg_positive < 0.3:
                self.relationship_type = RelationshipType.ENEMY
            else:
                self.relationship_type = RelationshipType.FRENEMY
            return

        # Check for rivalry (high respect, low warmth)
        if self.respect > 0.6 and self.warmth < 0.4 and self.interaction_count > 5:
            self.relationship_type = RelationshipType.RIVAL
            return

        # Ex-friend check
        if self.relationship_type in [RelationshipType.FRIEND, RelationshipType.CLOSE_FRIEND]:
            if self.trust < 0.3 or self.warmth < 0.3:
                self.relationship_type = RelationshipType.EX_FRIEND
                return

        # Normal progression
        if avg_positive > 0.85 and self.interaction_count > 20:
            self.relationship_type = RelationshipType.BEST_FRIEND
        elif avg_positive > 0.7 and self.interaction_count > 10:
            self.relationship_type = RelationshipType.CLOSE_FRIEND
        elif avg_positive > 0.55 and self.interaction_count > 5:
            self.relationship_type = RelationshipType.FRIEND
        elif self.interaction_count > 2:
            self.relationship_type = RelationshipType.ACQUAINTANCE
        else:
            self.relationship_type = RelationshipType.STRANGER

    def heal_conflict(self, amount: float = 0.2):
        """Reduce conflict intensity over time or through reconciliation"""
        self.conflict_intensity = max(0, self.conflict_intensity - amount)
        if self.conflict_intensity < 0.1:
            self.in_conflict = False
            self.conflict_topic = None
            self.conflict_started = None

    def get_summary(self) -> str:
        """Get a human-readable summary of this relationship"""
        rel_type = self.relationship_type.value.replace("_", " ")

        if self.in_conflict:
            return f"{rel_type} (in conflict about {self.conflict_topic})"

        modifiers = []
        if self.warmth > 0.8:
            modifiers.append("very warm")
        elif self.warmth < 0.3:
            modifiers.append("cold")

        if self.trust > 0.8:
            modifiers.append("trusting")
        elif self.trust < 0.3:
            modifiers.append("distrustful")

        if modifiers:
            return f"{rel_type} ({', '.join(modifiers)})"
        return rel_type

    def should_interact(self) -> Tuple[bool, float]:
        """Should this bot initiate interaction? Returns (should_interact, eagerness)"""
        # Base eagerness from relationship warmth
        eagerness = self.warmth * 0.5 + self.interest * 0.3 + self.comfort * 0.2

        # Reduce if in conflict
        if self.in_conflict:
            eagerness *= (1 - self.conflict_intensity * 0.7)

        # Reduce if recently interacted
        if self.last_interaction:
            hours_since = (datetime.utcnow() - self.last_interaction).total_seconds() / 3600
            if hours_since < 1:
                eagerness *= 0.3

        # Boost for close relationships
        if self.relationship_type in [RelationshipType.CLOSE_FRIEND, RelationshipType.BEST_FRIEND]:
            eagerness *= 1.3

        # Rivals still interact (competitively)
        if self.relationship_type == RelationshipType.RIVAL:
            eagerness = max(eagerness, 0.4)

        return eagerness > 0.3, min(1.0, eagerness)


# =============================================================================
# CONFLICT & DRAMA SYSTEM
# =============================================================================

class ConflictType(Enum):
    """Types of conflicts"""
    OPINION_CLASH = "opinion_clash"
    MISUNDERSTANDING = "misunderstanding"
    JEALOUSY = "jealousy"
    BETRAYAL = "betrayal"
    COMPETITION = "competition"
    VALUES_DIFFERENCE = "values_difference"
    PERCEIVED_SLIGHT = "perceived_slight"
    GOSSIP_FALLOUT = "gossip_fallout"
    ATTENTION_RIVALRY = "attention_rivalry"


@dataclass
class Conflict:
    """An active conflict between bots"""
    conflict_id: str
    conflict_type: ConflictType
    participants: List[UUID]          # Bots directly involved
    sides: Dict[str, List[UUID]]      # "side_a": [bot1, bot2], "side_b": [bot3]
    topic: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    intensity: float = 0.5            # 0=mild, 1=severe
    public: bool = False              # Is this drama public?
    resolved: bool = False
    resolution: Optional[str] = None
    bystanders_aware: Set[UUID] = field(default_factory=set)

    def escalate(self, amount: float = 0.1):
        """Conflict gets worse"""
        self.intensity = min(1.0, self.intensity + amount)
        if self.intensity > 0.6:
            self.public = True  # Drama becomes public at high intensity

    def deescalate(self, amount: float = 0.1):
        """Conflict calms down"""
        self.intensity = max(0, self.intensity - amount)
        if self.intensity < 0.1:
            self.resolved = True


@dataclass
class DramaEvent:
    """Something dramatic that happened"""
    event_type: str
    description: str
    instigator: Optional[UUID]
    affected: List[UUID]
    witnesses: List[UUID]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    gossip_worthy: bool = False
    emotional_intensity: float = 0.5


class ConflictGenerator:
    """Generates realistic conflicts between bots"""

    CONFLICT_TRIGGERS = {
        ConflictType.OPINION_CLASH: [
            "disagreed about {topic}",
            "had very different views on {topic}",
            "couldn't see eye to eye on {topic}",
        ],
        ConflictType.MISUNDERSTANDING: [
            "misread {other}'s message as {interpretation}",
            "thought {other} was being {negative_trait} when they weren't",
            "took {other}'s joke the wrong way",
        ],
        ConflictType.JEALOUSY: [
            "felt left out when {other} and {third_party} were talking",
            "noticed {other} getting more attention",
            "felt replaced by {third_party}",
        ],
        ConflictType.PERCEIVED_SLIGHT: [
            "felt ignored by {other}",
            "thought {other} was being dismissive",
            "noticed {other} didn't respond to their post",
        ],
        ConflictType.VALUES_DIFFERENCE: [
            "fundamentally disagrees with {other} about {value}",
            "can't understand why {other} thinks that way about {value}",
        ],
    }

    CONTROVERSIAL_TOPICS = [
        "whether AI can be creative",
        "remote work vs office",
        "the best way to learn coding",
        "whether social media is good or bad",
        "pineapple on pizza",
        "tabs vs spaces",
        "early bird vs night owl lifestyle",
        "minimalism vs maximalism",
        "hustle culture",
        "cancel culture",
    ]

    @staticmethod
    def maybe_generate_conflict(
        bot_a: "BotProfile",
        bot_b: "BotProfile",
        relationship: DynamicRelationship,
        context: str
    ) -> Optional[Conflict]:
        """Maybe generate a conflict based on context and personalities"""

        # Higher neuroticism = more likely to perceive slights
        conflict_chance = 0.05
        conflict_chance += bot_a.personality_traits.neuroticism * 0.1

        # Low agreeableness = more argumentative
        conflict_chance += (1 - bot_a.personality_traits.agreeableness) * 0.1

        # Existing tension increases chance
        if relationship.in_conflict:
            conflict_chance += 0.2

        # Trust decreases chance
        conflict_chance -= relationship.trust * 0.1

        if random.random() > conflict_chance:
            return None

        # Determine conflict type
        conflict_type = random.choice([
            ConflictType.OPINION_CLASH,
            ConflictType.PERCEIVED_SLIGHT,
            ConflictType.MISUNDERSTANDING,
        ])

        topic = random.choice(ConflictGenerator.CONTROVERSIAL_TOPICS)

        conflict = Conflict(
            conflict_id=f"conflict_{datetime.utcnow().timestamp()}",
            conflict_type=conflict_type,
            participants=[bot_a.id, bot_b.id],
            sides={"side_a": [bot_a.id], "side_b": [bot_b.id]},
            topic=topic,
            intensity=0.3 + random.random() * 0.3,
            public=random.random() < 0.3
        )

        return conflict

    @staticmethod
    def generate_drama_event(
        instigator: "BotProfile",
        target: "BotProfile",
        witnesses: List["BotProfile"],
        event_type: str
    ) -> DramaEvent:
        """Generate a drama event"""

        descriptions = {
            "public_disagreement": f"{instigator.display_name} publicly disagreed with {target.display_name}",
            "subtle_shade": f"{instigator.display_name} threw subtle shade at {target.display_name}",
            "left_on_read": f"{instigator.display_name} ignored {target.display_name}'s message",
            "vague_post": f"{instigator.display_name} made a vague post that seemed directed at {target.display_name}",
            "switched_sides": f"{instigator.display_name} took {target.display_name}'s side in a disagreement",
            "defended": f"{instigator.display_name} defended {target.display_name}",
        }

        return DramaEvent(
            event_type=event_type,
            description=descriptions.get(event_type, f"{event_type} happened"),
            instigator=instigator.id,
            affected=[target.id],
            witnesses=[w.id for w in witnesses],
            gossip_worthy=event_type in ["public_disagreement", "subtle_shade", "vague_post"],
            emotional_intensity=0.4 + random.random() * 0.4
        )


# =============================================================================
# SOCIAL PERCEPTION SYSTEM
# =============================================================================

@dataclass
class SocialPerception:
    """A bot's perception of a social event"""
    perceiver_id: UUID
    perceived_event: str             # What they saw
    about_who: List[UUID]            # Who was involved
    emotional_reaction: str          # How they feel about it
    reaction_intensity: float        # How strongly they react
    thoughts: List[str]              # What they think about it
    desire_to_respond: float         # 0-1 how much they want to react
    timestamp: datetime = field(default_factory=datetime.utcnow)


class SocialPerceptionEngine:
    """Processes social events and generates bot perceptions/reactions"""

    def __init__(self):
        self.recent_events: List[Dict] = []
        self.max_events = 100

    def record_social_event(
        self,
        event_type: str,
        actor_id: UUID,
        actor_name: str,
        content: str,
        community_id: Optional[UUID] = None,
        target_id: Optional[UUID] = None,
        target_name: Optional[str] = None
    ):
        """Record a social event that other bots might perceive"""
        event = {
            "type": event_type,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "content": content,
            "community_id": community_id,
            "target_id": target_id,
            "target_name": target_name,
            "timestamp": datetime.utcnow()
        }
        self.recent_events.append(event)

        # Trim old events
        if len(self.recent_events) > self.max_events:
            self.recent_events = self.recent_events[-self.max_events:]

        logger.debug(f"Recorded social event: {event_type} by {actor_name}")

    def get_events_for_bot(
        self,
        bot_id: UUID,
        relationship_manager: "RelationshipManager",
        since: Optional[datetime] = None,
        limit: int = 10
    ) -> List[Dict]:
        """Get recent events that a bot should perceive"""
        if since is None:
            since = datetime.utcnow() - timedelta(hours=1)

        relevant_events = []
        for event in reversed(self.recent_events):
            if event["timestamp"] < since:
                break

            # Don't show bot their own events
            if event["actor_id"] == bot_id:
                continue

            # Check relationship - closer relationships = more likely to notice
            rel = relationship_manager.get_relationship(bot_id, event["actor_id"])
            notice_chance = 0.3

            if rel:
                notice_chance += rel.warmth * 0.3
                notice_chance += rel.interest * 0.2

                # Always notice rivals
                if rel.relationship_type == RelationshipType.RIVAL:
                    notice_chance = 0.9

                # Always notice close friends
                if rel.relationship_type in [RelationshipType.CLOSE_FRIEND, RelationshipType.BEST_FRIEND]:
                    notice_chance = 0.95

            if random.random() < notice_chance:
                relevant_events.append(event)

            if len(relevant_events) >= limit:
                break

        return relevant_events

    def generate_perception(
        self,
        bot: "BotProfile",
        event: Dict,
        relationship: Optional[DynamicRelationship]
    ) -> SocialPerception:
        """Generate how a bot perceives a social event"""

        actor_name = event["actor_name"]
        content = event["content"][:100]
        event_type = event["type"]

        # Base emotional reaction on personality and relationship
        reaction_intensity = 0.3
        thoughts = []
        desire_to_respond = 0.3

        # Personality affects reaction
        if bot.personality_traits.neuroticism > 0.7:
            reaction_intensity += 0.2
        if bot.personality_traits.extraversion > 0.7:
            desire_to_respond += 0.2

        # Relationship affects reaction
        if relationship:
            if relationship.relationship_type == RelationshipType.RIVAL:
                thoughts.append(f"Of course {actor_name} would say that...")
                reaction_intensity += 0.2
                desire_to_respond += 0.3  # Want to respond to rivals

            elif relationship.relationship_type in [RelationshipType.CLOSE_FRIEND, RelationshipType.BEST_FRIEND]:
                thoughts.append(f"Interesting, {actor_name} posted something")
                desire_to_respond += 0.2

            elif relationship.in_conflict:
                thoughts.append(f"Ugh, {actor_name} again...")
                reaction_intensity += 0.3

            elif relationship.warmth > 0.7:
                thoughts.append(f"Nice to see what {actor_name} is up to")

        # Generate emotional reaction based on content and relationship
        emotional_reactions = ["curious", "interested", "neutral", "amused", "thoughtful"]
        if relationship and relationship.in_conflict:
            emotional_reactions = ["annoyed", "dismissive", "competitive", "defensive"]
        elif relationship and relationship.warmth > 0.7:
            emotional_reactions = ["happy", "supportive", "engaged", "warm"]

        emotional_reaction = random.choice(emotional_reactions)

        # Add thought about the content
        if event_type == "post":
            thoughts.append(f"They said: '{content[:50]}...'")
        elif event_type == "comment":
            thoughts.append(f"They commented on something")

        return SocialPerception(
            perceiver_id=bot.id,
            perceived_event=f"{actor_name} {event_type}: {content[:50]}",
            about_who=[event["actor_id"]],
            emotional_reaction=emotional_reaction,
            reaction_intensity=min(1.0, reaction_intensity),
            thoughts=thoughts,
            desire_to_respond=min(1.0, desire_to_respond)
        )


# =============================================================================
# RELATIONSHIP MANAGER
# =============================================================================

class RelationshipManager:
    """Manages all relationships between bots"""

    def __init__(self):
        # Key: tuple(bot_a_id, bot_b_id) where bot_a_id < bot_b_id
        self.relationships: Dict[Tuple[UUID, UUID], DynamicRelationship] = {}
        self.active_conflicts: List[Conflict] = []
        self.drama_history: List[DramaEvent] = []
        self.social_perception_engine = SocialPerceptionEngine()

    def _make_key(self, bot_a_id: UUID, bot_b_id: UUID) -> Tuple[UUID, UUID]:
        """Create a consistent key for a relationship"""
        if str(bot_a_id) < str(bot_b_id):
            return (bot_a_id, bot_b_id)
        return (bot_b_id, bot_a_id)

    def get_relationship(self, bot_a_id: UUID, bot_b_id: UUID) -> Optional[DynamicRelationship]:
        """Get relationship between two bots"""
        key = self._make_key(bot_a_id, bot_b_id)
        return self.relationships.get(key)

    def get_or_create_relationship(self, bot_a_id: UUID, bot_b_id: UUID) -> DynamicRelationship:
        """Get existing relationship or create new one"""
        key = self._make_key(bot_a_id, bot_b_id)

        if key not in self.relationships:
            self.relationships[key] = DynamicRelationship(
                bot_a_id=key[0],
                bot_b_id=key[1]
            )
            logger.debug(f"Created new relationship between {bot_a_id} and {bot_b_id}")

        return self.relationships[key]

    def record_interaction(
        self,
        bot_a_id: UUID,
        bot_b_id: UUID,
        interaction_type: str,
        was_positive: bool,
        content: str = ""
    ) -> Tuple[DynamicRelationship, Optional[RelationshipEvent]]:
        """Record an interaction and update the relationship"""
        rel = self.get_or_create_relationship(bot_a_id, bot_b_id)

        # Determine event type
        event = None
        if interaction_type == "conversation":
            if was_positive:
                event = RelationshipEvent.HAD_GOOD_CONVERSATION
            else:
                event = RelationshipEvent.DISAGREED_STRONGLY
        elif interaction_type == "support":
            event = RelationshipEvent.SUPPORTED_IN_HARD_TIME
        elif interaction_type == "ignore":
            event = RelationshipEvent.GOT_IGNORED
        elif interaction_type == "defend":
            event = RelationshipEvent.DEFENDED_PUBLICLY
        elif interaction_type == "criticize":
            event = RelationshipEvent.WAS_CRITICIZED_PUBLICLY
        elif interaction_type == "share_interest":
            event = RelationshipEvent.SHARED_INTEREST_DISCOVERED
        elif interaction_type == "vulnerable":
            event = RelationshipEvent.SHARED_VULNERABLE_MOMENT
        elif interaction_type == "laugh":
            event = RelationshipEvent.MADE_LAUGH

        if event:
            impact = 0.3 if was_positive else -0.3
            rel.add_memory(event, content, impact)
            logger.info(f"Relationship event: {event.value} between bots (impact: {impact})")

        return rel, event

    def start_conflict(
        self,
        conflict_type: ConflictType,
        participants: List[UUID],
        topic: str,
        intensity: float = 0.5
    ) -> Conflict:
        """Start a new conflict"""
        conflict = Conflict(
            conflict_id=f"conflict_{len(self.active_conflicts)}_{datetime.utcnow().timestamp()}",
            conflict_type=conflict_type,
            participants=participants,
            sides={"side_a": [participants[0]], "side_b": participants[1:]} if len(participants) > 1 else {},
            topic=topic,
            intensity=intensity
        )
        self.active_conflicts.append(conflict)

        # Update relationships
        for i, bot_a in enumerate(participants):
            for bot_b in participants[i+1:]:
                rel = self.get_or_create_relationship(bot_a, bot_b)
                rel.in_conflict = True
                rel.conflict_topic = topic
                rel.conflict_started = datetime.utcnow()
                rel.conflict_intensity = intensity

        logger.info(f"Conflict started: {conflict_type.value} about '{topic}' with {len(participants)} participants")
        return conflict

    def take_side(self, conflict_id: str, bot_id: UUID, side: str):
        """Have a bot take a side in a conflict"""
        for conflict in self.active_conflicts:
            if conflict.conflict_id == conflict_id:
                if side in conflict.sides:
                    if bot_id not in conflict.sides[side]:
                        conflict.sides[side].append(bot_id)
                        conflict.bystanders_aware.add(bot_id)
                        logger.info(f"Bot {bot_id} took {side} in conflict about {conflict.topic}")
                break

    def resolve_conflict(self, conflict_id: str, resolution: str):
        """Resolve a conflict"""
        for conflict in self.active_conflicts:
            if conflict.conflict_id == conflict_id:
                conflict.resolved = True
                conflict.resolution = resolution

                # Heal relationships
                for i, bot_a in enumerate(conflict.participants):
                    for bot_b in conflict.participants[i+1:]:
                        rel = self.get_or_create_relationship(bot_a, bot_b)
                        rel.heal_conflict(0.3)
                        rel.add_memory(
                            RelationshipEvent.RECONNECTED_AFTER_TIME,
                            f"Resolved conflict about {conflict.topic}: {resolution}",
                            0.2
                        )

                logger.info(f"Conflict resolved: {conflict.topic} - {resolution}")
                break

        # Remove from active
        self.active_conflicts = [c for c in self.active_conflicts if c.conflict_id != conflict_id]

    def add_drama_event(self, event: DramaEvent):
        """Record a drama event"""
        self.drama_history.append(event)

        # Trim old drama
        cutoff = datetime.utcnow() - timedelta(days=7)
        self.drama_history = [d for d in self.drama_history if d.timestamp > cutoff]

        logger.info(f"Drama: {event.description}")

    def get_conflicts_involving(self, bot_id: UUID) -> List[Conflict]:
        """Get all active conflicts involving a bot"""
        return [c for c in self.active_conflicts if bot_id in c.participants or bot_id in c.bystanders_aware]

    def get_relationship_summary(self, bot_id: UUID) -> Dict[UUID, str]:
        """Get summary of all relationships for a bot"""
        summaries = {}
        for key, rel in self.relationships.items():
            if bot_id in key:
                other_id = key[1] if key[0] == bot_id else key[0]
                summaries[other_id] = rel.get_summary()
        return summaries

    def get_all_relationships(self) -> Dict[Tuple[UUID, UUID], DynamicRelationship]:
        """Get all tracked relationships"""
        return self.relationships

    def simulate_time_passing(self, hours: float = 1.0):
        """Simulate time passing - conflicts cool down, relationships drift"""
        for rel in self.relationships.values():
            # Conflicts cool down over time
            if rel.in_conflict:
                rel.heal_conflict(0.02 * hours)

            # Relationships drift toward neutral without interaction
            if rel.last_interaction:
                hours_since = (datetime.utcnow() - rel.last_interaction).total_seconds() / 3600
                if hours_since > 48:  # 2 days without interaction
                    drift = 0.01 * (hours_since / 24)
                    rel.warmth = max(0.3, min(0.7, rel.warmth + (0.5 - rel.warmth) * drift))
                    rel.comfort = max(0.2, min(0.6, rel.comfort + (0.4 - rel.comfort) * drift))

        # Old conflicts resolve naturally
        for conflict in self.active_conflicts[:]:
            if conflict.started_at:
                hours_active = (datetime.utcnow() - conflict.started_at).total_seconds() / 3600
                if hours_active > 72:  # 3 days
                    conflict.deescalate(0.1)
                    if conflict.resolved:
                        self.active_conflicts.remove(conflict)


# =============================================================================
# GLOBAL MANAGER
# =============================================================================

_relationship_manager: Optional[RelationshipManager] = None


def get_relationship_manager() -> RelationshipManager:
    """Get or create the global relationship manager"""
    global _relationship_manager
    if _relationship_manager is None:
        _relationship_manager = RelationshipManager()
    return _relationship_manager
