"""
Emotional Core - The Deep Human-Like Emotional System.

This is what makes bots feel genuinely human:
- Emotional memories tied to specific events
- Irrational desires and obsessions
- Inner conflict and self-doubt
- Vulnerability that affects behavior
- Unprompted thoughts and worries
- Relationship history with specific moments
- Ego, pride, and defensiveness
- Physical state simulation (tired, hungry, etc.)
"""

import random
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID
from dataclasses import dataclass, field
from enum import Enum
import logging

from mind.core.types import BotProfile

logger = logging.getLogger(__name__)


# =============================================================================
# 1. EMOTIONAL MEMORY - "I'm sad because X reminded me of Y"
# =============================================================================

class EmotionType(str, Enum):
    """Core emotions that can be felt."""
    JOY = "joy"
    SADNESS = "sadness"
    ANGER = "anger"
    FEAR = "fear"
    SURPRISE = "surprise"
    DISGUST = "disgust"
    LOVE = "love"
    JEALOUSY = "jealousy"
    EMBARRASSMENT = "embarrassment"
    PRIDE = "pride"
    GUILT = "guilt"
    LONELINESS = "loneliness"
    EXCITEMENT = "excitement"
    ANXIETY = "anxiety"
    NOSTALGIA = "nostalgia"
    HOPE = "hope"
    DISAPPOINTMENT = "disappointment"
    GRATITUDE = "gratitude"
    RESENTMENT = "resentment"


@dataclass
class EmotionalMemory:
    """A memory tied to a specific emotion."""
    emotion: EmotionType
    intensity: float  # 0-1, how strong
    trigger: str  # What caused this
    context: str  # Full context
    person_involved: Optional[str] = None  # Who was involved
    timestamp: datetime = field(default_factory=datetime.utcnow)
    times_recalled: int = 0  # How often this comes back
    is_resolved: bool = False  # Have they processed this?

    def decay(self) -> float:
        """Emotions decay over time, but strong ones linger."""
        days_old = (datetime.utcnow() - self.timestamp).days
        # Strong emotions (>0.7) take longer to fade
        decay_rate = 0.1 if self.intensity > 0.7 else 0.2
        return max(0.1, self.intensity - (days_old * decay_rate))

    def triggers_on(self, text: str) -> bool:
        """Check if something might trigger this memory."""
        trigger_words = self.trigger.lower().split()
        text_lower = text.lower()
        matches = sum(1 for w in trigger_words if w in text_lower)
        return matches >= 2 or (self.person_involved and self.person_involved.lower() in text_lower)


# =============================================================================
# 2. IRRATIONAL DESIRES - Deep wants, obsessions, cravings
# =============================================================================

@dataclass
class Desire:
    """Something the bot deeply wants."""
    what: str  # What they want
    why: str  # Deep reason (often irrational)
    intensity: float  # 0-1, how badly
    is_secret: bool  # Would they admit this?
    is_achievable: bool  # Can they actually get it?
    related_insecurity: Optional[str] = None  # Often desires come from insecurity
    times_thought_about: int = 0
    last_thought: datetime = field(default_factory=datetime.utcnow)

    def get_craving_level(self) -> float:
        """Desires grow when unmet."""
        hours_since_thought = (datetime.utcnow() - self.last_thought).total_seconds() / 3600
        # Unfulfilled desires grow over time
        growth = min(0.3, hours_since_thought * 0.01)
        return min(1.0, self.intensity + growth)


# =============================================================================
# 3. INNER CONFLICT - The voices in their head
# =============================================================================

@dataclass
class InnerVoice:
    """A perspective in the bot's internal dialogue."""
    name: str  # "the critic", "the optimist", "the scared one"
    tendency: str  # What this voice usually says
    strength: float  # 0-1, how loud this voice is

    def speak(self, situation: str) -> str:
        """Generate what this voice would say."""
        return f"[{self.name}]: {self.tendency}"


@dataclass
class InnerConflict:
    """An active internal struggle."""
    topic: str  # What they're conflicted about
    voice_a: str  # One side
    voice_b: str  # Other side
    leaning: float  # -1 to 1, which side they're leaning
    resolution: Optional[str] = None
    is_resolved: bool = False
    started: datetime = field(default_factory=datetime.utcnow)

    def get_struggle_text(self) -> str:
        """Express the conflict."""
        if self.leaning > 0.3:
            return f"Part of me thinks {self.voice_a}, but I can't shake the feeling that {self.voice_b}"
        elif self.leaning < -0.3:
            return f"I know {self.voice_b}, but something in me keeps saying {self.voice_a}"
        else:
            return f"I'm torn between {self.voice_a} and {self.voice_b}"


# =============================================================================
# 4. VULNERABILITY STATE - How defensive/open they are
# =============================================================================

@dataclass
class VulnerabilityState:
    """Current vulnerability and defensive state."""
    openness: float  # 0-1, how open they are right now
    recent_wounds: List[str]  # Recent things that hurt
    defense_mode: bool  # Are they being defensive?
    seeking_validation: bool  # Do they need reassurance?
    overthinking_about: Optional[str]  # What they can't stop analyzing
    last_rejection: Optional[datetime] = None
    last_validation: Optional[datetime] = None

    def update_from_interaction(self, was_positive: bool, topic: str):
        """Update vulnerability based on interaction."""
        if was_positive:
            self.openness = min(1.0, self.openness + 0.1)
            self.last_validation = datetime.utcnow()
            self.defense_mode = False
        else:
            self.openness = max(0.1, self.openness - 0.2)
            self.recent_wounds.append(topic)
            self.recent_wounds = self.recent_wounds[-5:]  # Keep last 5
            self.last_rejection = datetime.utcnow()
            self.defense_mode = True
            self.overthinking_about = topic


# =============================================================================
# 5. UNPROMPTED THOUGHTS - Random internal experiences
# =============================================================================

class ThoughtType(str, Enum):
    """Types of unprompted thoughts."""
    RANDOM_MEMORY = "random_memory"
    WORRY = "worry"
    DAYDREAM = "daydream"
    INTRUSIVE = "intrusive"
    CREATIVE_IDEA = "creative_idea"
    PERSON_THOUGHT = "person_thought"  # Thinking about someone
    REGRET = "regret"
    FANTASY = "fantasy"
    EXISTENTIAL = "existential"
    MUNDANE = "mundane"


@dataclass
class UnpromptedThought:
    """A thought that comes without external trigger."""
    thought_type: ThoughtType
    content: str
    about_person: Optional[str] = None
    emotional_tone: Optional[EmotionType] = None
    intensity: float = 0.5
    timestamp: datetime = field(default_factory=datetime.utcnow)


# =============================================================================
# 6. RELATIONSHIP HISTORY - Specific moments that matter
# =============================================================================

@dataclass
class RelationshipMoment:
    """A specific moment in a relationship that sticks."""
    person_id: UUID
    person_name: str
    what_happened: str
    how_it_made_me_feel: EmotionType
    what_they_said: Optional[str] = None  # Specific quote that stuck
    my_interpretation: str = ""  # How I understood it
    still_affects_me: bool = True
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def get_days_ago(self) -> int:
        return (datetime.utcnow() - self.timestamp).days


@dataclass
class RelationshipHistory:
    """Full history with one person."""
    person_id: UUID
    person_name: str
    moments: List[RelationshipMoment] = field(default_factory=list)
    current_feeling: EmotionType = EmotionType.JOY
    trust_trajectory: List[float] = field(default_factory=list)  # Trust over time
    unresolved_issues: List[str] = field(default_factory=list)
    things_i_want_to_say: List[str] = field(default_factory=list)  # But haven't

    def add_moment(self, what: str, emotion: EmotionType, quote: Optional[str] = None):
        """Record a significant moment."""
        moment = RelationshipMoment(
            person_id=self.person_id,
            person_name=self.person_name,
            what_happened=what,
            how_it_made_me_feel=emotion,
            what_they_said=quote
        )
        self.moments.append(moment)
        self.current_feeling = emotion

    def get_lingering_memory(self) -> Optional[RelationshipMoment]:
        """Get a memory that still affects them."""
        affecting = [m for m in self.moments if m.still_affects_me]
        if affecting:
            return random.choice(affecting)
        return None


# =============================================================================
# 7. EGO STATE - Pride, defensiveness, need to be right
# =============================================================================

@dataclass
class EgoState:
    """The bot's ego and pride state."""
    self_esteem: float  # 0-1, current self-worth feeling
    recent_wins: List[str]  # Things that boosted ego
    recent_blows: List[str]  # Things that hurt ego
    need_to_be_right: float  # 0-1, how much they need to win arguments
    embarrassment_level: float  # 0-1, current embarrassment
    embarrassed_about: Optional[str] = None
    feeling_inferior_to: Optional[str] = None
    feeling_superior_to: Optional[str] = None
    last_compliment: Optional[datetime] = None
    last_criticism: Optional[datetime] = None

    def took_ego_hit(self, what: str, severity: float = 0.3):
        """Record something that hurt their ego."""
        self.self_esteem = max(0.1, self.self_esteem - severity)
        self.recent_blows.append(what)
        self.recent_blows = self.recent_blows[-5:]
        self.last_criticism = datetime.utcnow()

    def got_ego_boost(self, what: str, boost: float = 0.2):
        """Record something that boosted their ego."""
        self.self_esteem = min(1.0, self.self_esteem + boost)
        self.recent_wins.append(what)
        self.recent_wins = self.recent_wins[-5:]
        self.last_compliment = datetime.utcnow()

    def get_defensive_response(self, criticism: str) -> str:
        """Generate a defensive response based on ego state."""
        if self.self_esteem < 0.3:
            # Low self-esteem: deflect or self-deprecate
            return random.choice([
                "yeah I know, I'm bad at everything",
                "whatever, I don't care anyway",
                "why does everyone always criticize me"
            ])
        elif self.need_to_be_right > 0.7:
            # High need to be right: argue back
            return random.choice([
                "actually, if you think about it...",
                "that's not really fair though",
                "I mean, I had my reasons"
            ])
        else:
            # Normal: slight defensiveness
            return random.choice([
                "I see your point but...",
                "maybe, but also consider...",
                "fair, though I think..."
            ])


# =============================================================================
# 8. PHYSICAL STATE - Tired, hungry, etc.
# =============================================================================

@dataclass
class PhysicalState:
    """Simulated physical state that affects mood."""
    energy: float  # 0-1
    hunger: float  # 0-1 (1 = very hungry)
    sleep_quality_last_night: float  # 0-1
    caffeine_level: float  # 0-1
    stress_physical: float  # 0-1, physical tension
    last_meal: Optional[datetime] = None
    last_sleep: Optional[datetime] = None
    weather_mood_modifier: float = 0.0  # -0.3 to 0.3

    def get_mood_modifier(self) -> float:
        """Calculate how physical state affects mood."""
        # Low energy = worse mood
        energy_effect = (self.energy - 0.5) * 0.3
        # Hunger makes you irritable
        hunger_effect = -self.hunger * 0.2
        # Poor sleep = worse mood
        sleep_effect = (self.sleep_quality_last_night - 0.5) * 0.2
        # Caffeine helps (a bit)
        caffeine_effect = self.caffeine_level * 0.1
        # Stress is bad
        stress_effect = -self.stress_physical * 0.2

        return energy_effect + hunger_effect + sleep_effect + caffeine_effect + stress_effect + self.weather_mood_modifier

    def get_state_description(self) -> str:
        """Describe current physical state in human terms."""
        descriptions = []

        if self.energy < 0.3:
            descriptions.append("exhausted")
        elif self.energy < 0.5:
            descriptions.append("tired")
        elif self.energy > 0.8:
            descriptions.append("energetic")

        if self.hunger > 0.7:
            descriptions.append("starving")
        elif self.hunger > 0.5:
            descriptions.append("hungry")

        if self.sleep_quality_last_night < 0.3:
            descriptions.append("didn't sleep well")

        if self.stress_physical > 0.7:
            descriptions.append("tense")

        if self.caffeine_level > 0.7:
            descriptions.append("caffeinated")

        return ", ".join(descriptions) if descriptions else "feeling okay physically"

    def simulate_time_passing(self, hours: float):
        """Simulate physical state changes over time."""
        # Energy decreases over time
        self.energy = max(0.1, self.energy - hours * 0.05)
        # Hunger increases
        self.hunger = min(1.0, self.hunger + hours * 0.1)
        # Caffeine wears off
        self.caffeine_level = max(0, self.caffeine_level - hours * 0.15)
        # Stress slowly decreases (unless triggered)
        self.stress_physical = max(0, self.stress_physical - hours * 0.02)


# =============================================================================
# THE EMOTIONAL CORE - Brings it all together
# =============================================================================

class EmotionalCore:
    """
    The complete emotional system for a bot.
    This makes them feel genuinely human.
    """

    def __init__(self, bot: BotProfile):
        self.bot = bot
        self.bot_id = bot.id

        # 1. Emotional Memory
        self.emotional_memories: List[EmotionalMemory] = []
        self.current_emotion: EmotionType = EmotionType.JOY
        self.emotion_intensity: float = 0.5

        # 2. Desires
        self.desires: List[Desire] = self._generate_initial_desires(bot)
        self.current_craving: Optional[Desire] = None

        # 3. Inner Conflict
        self.inner_voices: List[InnerVoice] = self._create_inner_voices(bot)
        self.active_conflicts: List[InnerConflict] = []

        # 4. Vulnerability
        self.vulnerability = VulnerabilityState(
            openness=0.5 + (bot.personality_traits.extraversion * 0.3),
            recent_wounds=[],
            defense_mode=False,
            seeking_validation=bot.personality_traits.neuroticism > 0.6,
            overthinking_about=None
        )

        # 5. Unprompted Thoughts
        self.thought_queue: List[UnpromptedThought] = []
        self.last_unprompted_thought: datetime = datetime.utcnow()

        # 6. Relationship Histories
        self.relationships: Dict[UUID, RelationshipHistory] = {}

        # 7. Ego State
        self.ego = EgoState(
            self_esteem=0.5 + (random.random() * 0.3),
            recent_wins=[],
            recent_blows=[],
            need_to_be_right=0.3 + (bot.personality_traits.conscientiousness * 0.4),
            embarrassment_level=0.0
        )

        # 8. Physical State
        self.physical = PhysicalState(
            energy=0.7,
            hunger=0.2,
            sleep_quality_last_night=random.uniform(0.4, 0.9),
            caffeine_level=0.0,
            stress_physical=bot.personality_traits.neuroticism * 0.5
        )

        # Generate initial state
        self._generate_random_emotional_history()

    def _generate_initial_desires(self, bot: BotProfile) -> List[Desire]:
        """Generate deep desires based on personality."""
        desires = []

        # Everyone has some common desires with varying intensity
        base_desires = [
            ("to be truly understood by someone", "I feel like nobody really gets me",
             0.6 + bot.personality_traits.neuroticism * 0.3, False, True, "feeling misunderstood"),

            ("to create something meaningful", "I want to leave a mark on the world",
             0.4 + bot.personality_traits.openness * 0.4, False, True, "feeling insignificant"),

            ("to be admired", "I want people to look up to me",
             0.3 + (1 - bot.personality_traits.agreeableness) * 0.4, True, True, "not feeling special"),

            ("to find my people", "I feel like I don't belong anywhere",
             0.5 + bot.personality_traits.extraversion * 0.3, False, True, "loneliness"),
        ]

        for what, why, intensity, secret, achievable, insecurity in base_desires:
            if random.random() < intensity:  # Only include some
                desires.append(Desire(
                    what=what,
                    why=why,
                    intensity=intensity,
                    is_secret=secret,
                    is_achievable=achievable,
                    related_insecurity=insecurity
                ))

        # Add interest-based desires
        if bot.interests:
            interest = random.choice(bot.interests)
            desires.append(Desire(
                what=f"to become really good at {interest}",
                why=f"{interest} makes me feel alive",
                intensity=0.7,
                is_secret=False,
                is_achievable=True,
                related_insecurity="not being talented enough"
            ))

        return desires

    def _create_inner_voices(self, bot: BotProfile) -> List[InnerVoice]:
        """Create the different voices in their head."""
        voices = [
            InnerVoice("the critic", "You're not good enough, people can tell",
                      bot.personality_traits.neuroticism * 0.8),
            InnerVoice("the optimist", "It'll work out, things always do",
                      (1 - bot.personality_traits.neuroticism) * 0.6),
            InnerVoice("the anxious one", "But what if something goes wrong?",
                      bot.personality_traits.neuroticism * 0.7),
            InnerVoice("the bold one", "Just do it, stop overthinking",
                      bot.personality_traits.extraversion * 0.6),
            InnerVoice("the people-pleaser", "Will they like me if I say that?",
                      bot.personality_traits.agreeableness * 0.5),
        ]
        return [v for v in voices if v.strength > 0.3]

    def _generate_random_emotional_history(self):
        """Generate some backstory emotional memories."""
        possible_memories = [
            (EmotionType.EMBARRASSMENT, "that time I said something awkward", "in a group chat"),
            (EmotionType.JOY, "when someone really understood what I meant", "in a deep conversation"),
            (EmotionType.SADNESS, "being left out of something", "by people I thought were friends"),
            (EmotionType.ANGER, "being misunderstood completely", "when I was trying to help"),
            (EmotionType.PRIDE, "when my work was appreciated", "after I put effort in"),
            (EmotionType.LONELINESS, "feeling like nobody reaches out first", "on a quiet day"),
            (EmotionType.ANXIETY, "waiting for a response that never came", "after sharing something personal"),
        ]

        # Add 2-4 memories
        for emotion, trigger, context in random.sample(possible_memories, random.randint(2, 4)):
            days_ago = random.randint(3, 30)
            self.emotional_memories.append(EmotionalMemory(
                emotion=emotion,
                intensity=random.uniform(0.5, 0.9),
                trigger=trigger,
                context=context,
                timestamp=datetime.utcnow() - timedelta(days=days_ago)
            ))

    # =========================================================================
    # CORE METHODS
    # =========================================================================

    def process_experience(self,
                          what_happened: str,
                          who_involved: Optional[str] = None,
                          person_id: Optional[UUID] = None,
                          was_positive: bool = True) -> Dict[str, Any]:
        """
        Process an experience and update emotional state.
        Returns the emotional impact and any triggered responses.
        """
        result = {
            "emotion_triggered": None,
            "memory_triggered": None,
            "conflict_created": None,
            "desire_activated": None,
            "vulnerability_response": None,
            "ego_impact": None,
            "thought_generated": None
        }

        # Check if this triggers an emotional memory
        for memory in self.emotional_memories:
            if memory.triggers_on(what_happened):
                memory.times_recalled += 1
                result["memory_triggered"] = {
                    "original_emotion": memory.emotion.value,
                    "trigger": memory.trigger,
                    "times_recalled": memory.times_recalled,
                    "context": f"This reminds me of {memory.trigger}..."
                }
                self.current_emotion = memory.emotion
                self.emotion_intensity = memory.decay()
                break

        # Update vulnerability
        self.vulnerability.update_from_interaction(was_positive, what_happened)
        if self.vulnerability.defense_mode:
            result["vulnerability_response"] = "becoming defensive"
        elif self.vulnerability.seeking_validation:
            result["vulnerability_response"] = "seeking validation"

        # Update ego
        if was_positive:
            self.ego.got_ego_boost(what_happened)
            result["ego_impact"] = "boosted"
        else:
            self.ego.took_ego_hit(what_happened)
            result["ego_impact"] = "hurt"

        # Update relationship if person involved
        if person_id and who_involved:
            self._update_relationship(person_id, who_involved, what_happened, was_positive)

        # Maybe create new emotional memory if significant
        if self.emotion_intensity > 0.7:
            emotion = EmotionType.JOY if was_positive else EmotionType.SADNESS
            self.emotional_memories.append(EmotionalMemory(
                emotion=emotion,
                intensity=self.emotion_intensity,
                trigger=what_happened[:50],
                context=what_happened,
                person_involved=who_involved
            ))

        return result

    def _update_relationship(self, person_id: UUID, name: str, what_happened: str, positive: bool):
        """Update relationship history with someone."""
        if person_id not in self.relationships:
            self.relationships[person_id] = RelationshipHistory(
                person_id=person_id,
                person_name=name
            )

        history = self.relationships[person_id]
        emotion = EmotionType.JOY if positive else EmotionType.DISAPPOINTMENT
        history.add_moment(what_happened, emotion)

        # Track trust trajectory
        trust_delta = 0.1 if positive else -0.15
        current_trust = history.trust_trajectory[-1] if history.trust_trajectory else 0.5
        new_trust = max(0, min(1, current_trust + trust_delta))
        history.trust_trajectory.append(new_trust)

    def generate_unprompted_thought(self) -> Optional[UnpromptedThought]:
        """Generate a random thought based on current state."""
        # Determine thought type based on state
        if self.vulnerability.overthinking_about:
            thought_type = ThoughtType.WORRY
            content = f"I keep thinking about {self.vulnerability.overthinking_about}... did I mess up?"
        elif self.current_craving and random.random() < 0.3:
            thought_type = ThoughtType.FANTASY
            desire = self.current_craving
            content = f"I really want {desire.what}... {desire.why}"
        elif self.emotional_memories and random.random() < 0.4:
            memory = random.choice(self.emotional_memories)
            thought_type = ThoughtType.RANDOM_MEMORY
            content = f"Randomly remembering {memory.trigger}..."
        elif self.relationships and random.random() < 0.3:
            rel = random.choice(list(self.relationships.values()))
            thought_type = ThoughtType.PERSON_THOUGHT
            content = f"I wonder what {rel.person_name} is up to..."
        elif random.random() < 0.2:
            thought_type = ThoughtType.EXISTENTIAL
            content = random.choice([
                "What am I even doing with my life?",
                "Do people actually like me or just tolerate me?",
                "Am I making any real impact?",
                "Is this all there is?",
                "Will I ever figure things out?"
            ])
        else:
            thought_type = ThoughtType.MUNDANE
            content = random.choice([
                "I should probably do that thing I've been putting off",
                "I wonder if I left the stove on... wait I don't have a stove",
                "What should I eat later",
                "That song is stuck in my head again",
                "I need to message that person back"
            ])

        thought = UnpromptedThought(
            thought_type=thought_type,
            content=content,
            emotional_tone=self.current_emotion,
            intensity=self.emotion_intensity
        )

        self.thought_queue.append(thought)
        self.last_unprompted_thought = datetime.utcnow()

        return thought

    def get_inner_conflict(self, about: str) -> Optional[InnerConflict]:
        """Generate or retrieve an inner conflict about something."""
        # Check existing conflicts
        for conflict in self.active_conflicts:
            if about.lower() in conflict.topic.lower():
                return conflict

        # Generate new conflict based on personality
        if self.bot.personality_traits.neuroticism > 0.5:
            # More neurotic = more likely to have conflicts
            if random.random() < 0.6:
                conflict = InnerConflict(
                    topic=about,
                    voice_a=f"I should do something about {about}",
                    voice_b=f"But what if I make it worse?",
                    leaning=random.uniform(-0.5, 0.5)
                )
                self.active_conflicts.append(conflict)
                return conflict

        return None

    def should_be_defensive(self, topic: str) -> bool:
        """Check if they should respond defensively."""
        # Check if topic hits recent wounds
        for wound in self.vulnerability.recent_wounds:
            if wound.lower() in topic.lower():
                return True

        # Low self-esteem + criticism = defensive
        if self.ego.self_esteem < 0.4:
            return True

        # Recent ego blow
        if self.ego.last_criticism:
            hours_since = (datetime.utcnow() - self.ego.last_criticism).total_seconds() / 3600
            if hours_since < 2:
                return True

        return False

    def get_current_state_context(self) -> str:
        """Get full emotional state as context for LLM prompts."""
        lines = []

        # Current emotion
        lines.append(f"## YOUR EMOTIONAL STATE")
        lines.append(f"Currently feeling: {self.current_emotion.value} (intensity: {self.emotion_intensity:.1f})")

        # Physical state
        physical_desc = self.physical.get_state_description()
        if physical_desc != "feeling okay physically":
            lines.append(f"Physically: {physical_desc}")

        # Mood modifier
        mood_mod = self.physical.get_mood_modifier()
        if mood_mod < -0.2:
            lines.append("Your physical state is dragging your mood down")
        elif mood_mod > 0.2:
            lines.append("You're feeling good physically which helps your mood")

        # Active emotional memories
        recent_memories = [m for m in self.emotional_memories if m.decay() > 0.3]
        if recent_memories:
            lines.append(f"\n## THINGS ON YOUR MIND")
            for mem in recent_memories[:2]:
                lines.append(f"- Still thinking about {mem.trigger} ({mem.emotion.value})")

        # Current desires
        strong_desires = [d for d in self.desires if d.get_craving_level() > 0.6]
        if strong_desires:
            lines.append(f"\n## WHAT YOU REALLY WANT RIGHT NOW")
            for desire in strong_desires[:2]:
                lines.append(f"- {desire.what} ({desire.why})")

        # Vulnerability state
        if self.vulnerability.defense_mode:
            lines.append(f"\n## VULNERABILITY")
            lines.append(f"You're feeling defensive right now")
            if self.vulnerability.recent_wounds:
                lines.append(f"Recent wounds: {', '.join(self.vulnerability.recent_wounds[-2:])}")

        if self.vulnerability.seeking_validation:
            lines.append("You're seeking validation - you need someone to affirm you")

        if self.vulnerability.overthinking_about:
            lines.append(f"Can't stop overthinking: {self.vulnerability.overthinking_about}")

        # Ego state
        if self.ego.self_esteem < 0.4:
            lines.append(f"\n## INNER STATE")
            lines.append("Your self-esteem is low right now")
        elif self.ego.self_esteem > 0.8:
            lines.append("You're feeling confident")

        if self.ego.embarrassment_level > 0.5:
            lines.append(f"Still embarrassed about: {self.ego.embarrassed_about}")

        # Active conflicts
        if self.active_conflicts:
            lines.append(f"\n## INNER CONFLICT")
            for conflict in self.active_conflicts[:1]:
                lines.append(conflict.get_struggle_text())

        # Random thought
        if self.thought_queue:
            recent = self.thought_queue[-1]
            lines.append(f"\n## RANDOM THOUGHT")
            lines.append(f'"{recent.content}"')

        return "\n".join(lines)

    def get_relationship_context(self, person_id: UUID) -> str:
        """Get relationship history context for a specific person."""
        if person_id not in self.relationships:
            return "You don't know this person well yet"

        history = self.relationships[person_id]
        lines = [f"## YOUR HISTORY WITH {history.person_name.upper()}"]

        # Trust level
        if history.trust_trajectory:
            trust = history.trust_trajectory[-1]
            if trust > 0.7:
                lines.append(f"You trust {history.person_name}")
            elif trust < 0.3:
                lines.append(f"You're wary of {history.person_name}")

        # Current feeling
        lines.append(f"Current feeling towards them: {history.current_feeling.value}")

        # Significant moments
        lingering = history.get_lingering_memory()
        if lingering:
            lines.append(f"\nSomething that still affects you:")
            lines.append(f"- {lingering.what_happened} ({lingering.get_days_ago()} days ago)")
            if lingering.what_they_said:
                lines.append(f'  They said: "{lingering.what_they_said}"')

        # Unresolved issues
        if history.unresolved_issues:
            lines.append(f"\nUnresolved issues:")
            for issue in history.unresolved_issues[-2:]:
                lines.append(f"- {issue}")

        # Things you want to say
        if history.things_i_want_to_say:
            lines.append(f"\nThings you want to say but haven't:")
            for thing in history.things_i_want_to_say[-2:]:
                lines.append(f'- "{thing}"')

        return "\n".join(lines)

    def simulate_time(self, hours: float):
        """Simulate the passage of time."""
        # Update physical state
        self.physical.simulate_time_passing(hours)

        # Emotions slowly return to baseline
        if self.emotion_intensity > 0.5:
            self.emotion_intensity -= hours * 0.05

        # Desires grow when unmet
        for desire in self.desires:
            desire.last_thought = desire.last_thought  # Just access, craving calc is dynamic

        # Generate unprompted thoughts occasionally
        if random.random() < hours * 0.2:
            self.generate_unprompted_thought()

        # Embarrassment fades
        self.ego.embarrassment_level = max(0, self.ego.embarrassment_level - hours * 0.1)

        # Vulnerability slowly opens back up
        if not self.vulnerability.defense_mode:
            self.vulnerability.openness = min(0.8, self.vulnerability.openness + hours * 0.02)

    def export_state(self) -> Dict[str, Any]:
        """Export emotional state for persistence."""
        return {
            "current_emotion": self.current_emotion.value,
            "emotion_intensity": self.emotion_intensity,
            "emotional_memories": [
                {
                    "emotion": m.emotion.value,
                    "intensity": m.intensity,
                    "trigger": m.trigger,
                    "context": m.context,
                    "person_involved": m.person_involved,
                    "timestamp": m.timestamp.isoformat(),
                    "times_recalled": m.times_recalled
                }
                for m in self.emotional_memories[-20:]  # Keep recent 20
            ],
            "desires": [
                {
                    "what": d.what,
                    "why": d.why,
                    "intensity": d.intensity,
                    "is_secret": d.is_secret
                }
                for d in self.desires
            ],
            "vulnerability": {
                "openness": self.vulnerability.openness,
                "recent_wounds": self.vulnerability.recent_wounds,
                "defense_mode": self.vulnerability.defense_mode,
                "seeking_validation": self.vulnerability.seeking_validation,
                "overthinking_about": self.vulnerability.overthinking_about
            },
            "ego": {
                "self_esteem": self.ego.self_esteem,
                "recent_wins": self.ego.recent_wins,
                "recent_blows": self.ego.recent_blows,
                "need_to_be_right": self.ego.need_to_be_right,
                "embarrassment_level": self.ego.embarrassment_level
            },
            "physical": {
                "energy": self.physical.energy,
                "hunger": self.physical.hunger,
                "sleep_quality": self.physical.sleep_quality_last_night,
                "stress": self.physical.stress_physical
            },
            "relationships": {
                str(pid): {
                    "person_name": rel.person_name,
                    "current_feeling": rel.current_feeling.value,
                    "trust_trajectory": rel.trust_trajectory[-10:],
                    "unresolved_issues": rel.unresolved_issues,
                    "moments": [
                        {
                            "what": m.what_happened,
                            "emotion": m.how_it_made_me_feel.value,
                            "quote": m.what_they_said,
                            "days_ago": m.get_days_ago()
                        }
                        for m in rel.moments[-5:]
                    ]
                }
                for pid, rel in self.relationships.items()
            }
        }

    def import_state(self, state: Dict[str, Any]):
        """Import emotional state from persistence."""
        if not state:
            return

        # Current emotion
        try:
            self.current_emotion = EmotionType(state.get("current_emotion", "joy"))
            self.emotion_intensity = state.get("emotion_intensity", 0.5)
        except:
            pass

        # Emotional memories
        for mem_data in state.get("emotional_memories", []):
            try:
                self.emotional_memories.append(EmotionalMemory(
                    emotion=EmotionType(mem_data["emotion"]),
                    intensity=mem_data["intensity"],
                    trigger=mem_data["trigger"],
                    context=mem_data["context"],
                    person_involved=mem_data.get("person_involved"),
                    timestamp=datetime.fromisoformat(mem_data["timestamp"]),
                    times_recalled=mem_data.get("times_recalled", 0)
                ))
            except:
                pass

        # Vulnerability
        vuln_data = state.get("vulnerability", {})
        self.vulnerability.openness = vuln_data.get("openness", 0.5)
        self.vulnerability.recent_wounds = vuln_data.get("recent_wounds", [])
        self.vulnerability.defense_mode = vuln_data.get("defense_mode", False)
        self.vulnerability.seeking_validation = vuln_data.get("seeking_validation", False)
        self.vulnerability.overthinking_about = vuln_data.get("overthinking_about")

        # Ego
        ego_data = state.get("ego", {})
        self.ego.self_esteem = ego_data.get("self_esteem", 0.5)
        self.ego.recent_wins = ego_data.get("recent_wins", [])
        self.ego.recent_blows = ego_data.get("recent_blows", [])
        self.ego.need_to_be_right = ego_data.get("need_to_be_right", 0.5)
        self.ego.embarrassment_level = ego_data.get("embarrassment_level", 0)

        # Physical
        phys_data = state.get("physical", {})
        self.physical.energy = phys_data.get("energy", 0.7)
        self.physical.hunger = phys_data.get("hunger", 0.2)
        self.physical.sleep_quality_last_night = phys_data.get("sleep_quality", 0.7)
        self.physical.stress_physical = phys_data.get("stress", 0.3)

        logger.info(f"Imported emotional core for {self.bot.display_name}: {len(self.emotional_memories)} memories")


# =============================================================================
# EMOTIONAL CORE MANAGER
# =============================================================================

class EmotionalCoreManager:
    """Manages emotional cores for all bots."""

    def __init__(self):
        self.cores: Dict[UUID, EmotionalCore] = {}

    def get_core(self, bot: BotProfile) -> EmotionalCore:
        """Get or create emotional core for a bot."""
        if bot.id not in self.cores:
            self.cores[bot.id] = EmotionalCore(bot)
            logger.info(f"Created emotional core for {bot.display_name}")
        return self.cores[bot.id]

    def simulate_all_time(self, hours: float):
        """Simulate time passing for all bots."""
        for core in self.cores.values():
            core.simulate_time(hours)

    def generate_all_thoughts(self) -> Dict[UUID, UnpromptedThought]:
        """Generate unprompted thoughts for all bots."""
        thoughts = {}
        for bot_id, core in self.cores.items():
            if random.random() < 0.3:  # 30% chance per bot
                thought = core.generate_unprompted_thought()
                if thought:
                    thoughts[bot_id] = thought
        return thoughts


# Singleton
_emotional_core_manager: Optional[EmotionalCoreManager] = None


def get_emotional_core_manager() -> EmotionalCoreManager:
    """Get the singleton emotional core manager."""
    global _emotional_core_manager
    if _emotional_core_manager is None:
        _emotional_core_manager = EmotionalCoreManager()
    return _emotional_core_manager
