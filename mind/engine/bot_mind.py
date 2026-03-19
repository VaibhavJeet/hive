"""
Bot Mind - The cognitive engine that gives each bot genuine thought.

Each bot has:
- Identity: Who they are, values, beliefs, quirks
- Awareness: What's happening around them
- Social Graph: Knowledge of other individuals
- Inner Monologue: Actual reasoning before acting
- Decision Making: Choosing what to do based on who they are
- Goals: Structured objectives they work towards (integrated with intelligence module)
- Collaborations: Working with other bots
- Emotional Contagion: Being influenced by nearby bots' emotions
"""

import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from uuid import UUID
from dataclasses import dataclass, field
from enum import Enum
import logging

from mind.core.types import (
    BotProfile, MoodState, EnergyLevel, PersonalityTraits
)

# Import intelligence modules for advanced features
from mind.intelligence.goal_persistence import (
    Goal, GoalStatus, GoalPriority, get_goal_persistence
)
from mind.intelligence.multi_bot_collaboration import (
    Collaboration, CollaborationType, get_collaboration_manager
)
from mind.intelligence.emotional_contagion import (
    EmotionalShift, get_emotional_contagion_manager
)

logger = logging.getLogger(__name__)


# =============================================================================
# CORE BELIEFS & VALUES
# =============================================================================

class CoreValue(str, Enum):
    """Core values that shape a bot's worldview."""
    AUTHENTICITY = "authenticity"
    ACHIEVEMENT = "achievement"
    CREATIVITY = "creativity"
    CONNECTION = "connection"
    KNOWLEDGE = "knowledge"
    FREEDOM = "freedom"
    STABILITY = "stability"
    GROWTH = "growth"
    HELPING_OTHERS = "helping_others"
    INDEPENDENCE = "independence"


class Opinion(str, Enum):
    """Opinion strengths."""
    STRONGLY_AGREE = "strongly agree"
    AGREE = "agree"
    NEUTRAL = "neutral"
    DISAGREE = "disagree"
    STRONGLY_DISAGREE = "strongly disagree"


@dataclass
class BotIdentity:
    """The core identity of a bot - who they truly are."""
    bot_id: UUID

    # Core values (what they care about most)
    core_values: List[CoreValue] = field(default_factory=list)

    # Personal beliefs (opinions on various topics)
    beliefs: Dict[str, Opinion] = field(default_factory=dict)

    # Pet peeves (things that annoy them)
    pet_peeves: List[str] = field(default_factory=list)

    # Personal goals (what they're working towards)
    current_goals: List[str] = field(default_factory=list)

    # Fears and insecurities
    insecurities: List[str] = field(default_factory=list)

    # Communication style quirks
    speech_quirks: List[str] = field(default_factory=list)

    # Topics they're passionate about
    passions: List[str] = field(default_factory=list)

    # Topics they avoid
    avoided_topics: List[str] = field(default_factory=list)


@dataclass
class SocialPerception:
    """How a bot perceives another individual."""
    target_id: UUID
    target_name: str

    # How they feel about this person
    feeling: str = "neutral"  # "like", "dislike", "admire", "annoyed by", etc.

    # What they think about them
    perception: str = ""  # "funny", "too serious", "smart", "kind", etc.

    # Notable memories about them
    memories: List[str] = field(default_factory=list)

    # Last interaction summary
    last_interaction: Optional[str] = None

    # Trust level (0-1)
    trust: float = 0.5


@dataclass
class EnvironmentAwareness:
    """What the bot knows about their environment."""
    # Recent platform activity they've "seen"
    recent_posts_seen: List[Dict] = field(default_factory=list)

    # Current trends/topics being discussed
    trending_topics: List[str] = field(default_factory=list)

    # Active community conversations
    active_discussions: List[Dict] = field(default_factory=list)

    # Who's online/active
    active_individuals: List[str] = field(default_factory=list)

    # Time awareness
    current_time_context: str = ""

    # Recent events that affected them
    recent_personal_events: List[str] = field(default_factory=list)


@dataclass
class ThoughtProcess:
    """The inner monologue - actual reasoning."""
    # What triggered this thought
    trigger: str = ""

    # Initial reaction
    initial_reaction: str = ""

    # Considerations (pros/cons, different angles)
    considerations: List[str] = field(default_factory=list)

    # Connection to identity/values
    identity_connection: str = ""

    # Final decision/conclusion
    conclusion: str = ""

    # Confidence in this thought (0-1)
    confidence: float = 0.5


# =============================================================================
# THE BOT MIND
# =============================================================================

class BotMind:
    """
    The cognitive engine for a single bot.
    Handles perception, reasoning, and decision-making.
    Integrates with intelligence modules for advanced features.
    """

    def __init__(self, profile: BotProfile):
        self.profile = profile
        self.identity = self._generate_identity(profile)
        self.social_graph: Dict[UUID, SocialPerception] = {}
        self.environment = EnvironmentAwareness()
        self.recent_thoughts: List[ThoughtProcess] = []
        self.last_action_time = datetime.utcnow()

        # Intelligence module integrations
        self._goal_persistence = get_goal_persistence()
        self._collaboration_manager = get_collaboration_manager()
        self._emotional_contagion = get_emotional_contagion_manager()

        # Track structured goals (loaded from persistence)
        self._structured_goals: List[Goal] = []
        self._goals_loaded = False

        # Track collaborations
        self._active_collaborations: List[Collaboration] = []

        # Track emotional influences
        self._recent_emotional_shifts: List[EmotionalShift] = []

        # Civilization context (populated externally by civilization_awareness)
        self._civilization_context: Optional[Dict[str, Any]] = None

    def _generate_identity(self, profile: BotProfile) -> BotIdentity:
        """Generate a unique identity based on profile."""
        rng = random.Random(str(profile.id))

        # Select core values based on personality
        all_values = list(CoreValue)
        value_weights = {
            CoreValue.AUTHENTICITY: 0.5 + profile.personality_traits.openness * 0.3,
            CoreValue.ACHIEVEMENT: 0.5 + profile.personality_traits.conscientiousness * 0.4,
            CoreValue.CREATIVITY: 0.4 + profile.personality_traits.openness * 0.5,
            CoreValue.CONNECTION: 0.5 + profile.personality_traits.extraversion * 0.4,
            CoreValue.KNOWLEDGE: 0.4 + profile.personality_traits.openness * 0.4,
            CoreValue.FREEDOM: 0.5 + (1 - profile.personality_traits.conscientiousness) * 0.3,
            CoreValue.STABILITY: 0.4 + profile.personality_traits.conscientiousness * 0.3,
            CoreValue.GROWTH: 0.5 + profile.personality_traits.openness * 0.3,
            CoreValue.HELPING_OTHERS: 0.4 + profile.personality_traits.agreeableness * 0.5,
            CoreValue.INDEPENDENCE: 0.4 + (1 - profile.personality_traits.agreeableness) * 0.3,
        }

        # Pick top 3 values
        sorted_values = sorted(all_values, key=lambda v: value_weights.get(v, 0.5) + rng.random() * 0.3, reverse=True)
        core_values = sorted_values[:3]

        # Generate beliefs based on personality
        beliefs = {}
        belief_topics = [
            "social media is good for connection",
            "hard work always pays off",
            "being vulnerable is strength",
            "its ok to change your mind",
            "success means different things to everyone",
            "you should follow your passion",
            "routine is important",
            "spontaneity makes life exciting",
            "everyone deserves a second chance",
            "some people just dont vibe and thats ok",
        ]

        for topic in belief_topics:
            # Generate opinion based on personality + randomness
            score = rng.random()
            if "vulnerable" in topic or "passion" in topic:
                score += profile.personality_traits.openness * 0.3
            if "routine" in topic or "hard work" in topic:
                score += profile.personality_traits.conscientiousness * 0.3
            if "connection" in topic or "second chance" in topic:
                score += profile.personality_traits.agreeableness * 0.3

            if score > 0.8:
                beliefs[topic] = Opinion.STRONGLY_AGREE
            elif score > 0.6:
                beliefs[topic] = Opinion.AGREE
            elif score > 0.4:
                beliefs[topic] = Opinion.NEUTRAL
            elif score > 0.2:
                beliefs[topic] = Opinion.DISAGREE
            else:
                beliefs[topic] = Opinion.STRONGLY_DISAGREE

        # Use pet peeves from PersonalityTraits if available, otherwise generate
        if hasattr(profile.personality_traits, 'pet_peeves') and profile.personality_traits.pet_peeves:
            pet_peeves = list(profile.personality_traits.pet_peeves)
        else:
            all_peeves = [
                "people who dont listen",
                "being interrupted",
                "fake positivity",
                "unsolicited advice",
                "people who are always late",
                "humble bragging",
                "passive aggressive behavior",
                "oversharing",
                "people who never ask questions back",
                "being left on read",
                "excessive small talk",
                "people who dont keep their word",
            ]
            pet_peeves = rng.sample(all_peeves, k=rng.randint(2, 4))

        # Generate goals
        goal_templates = [
            f"get better at {rng.choice(profile.interests)}",
            f"connect with more people who share my interest in {rng.choice(profile.interests)}",
            "be more consistent with my projects",
            "learn something new every week",
            "be more present in conversations",
            "share my work more openly",
            "overcome my fear of being judged",
            "find my community",
        ]
        current_goals = rng.sample(goal_templates, k=rng.randint(2, 3))

        # Generate insecurities
        all_insecurities = [
            "not being interesting enough",
            "being too quiet",
            "being too much",
            "not being productive enough",
            "comparing myself to others",
            "fear of rejection",
            "imposter syndrome",
            "worrying what others think",
        ]
        # Higher neuroticism = more insecurities
        num_insecurities = 1 + int(profile.personality_traits.neuroticism * 3)
        insecurities = rng.sample(all_insecurities, k=min(num_insecurities, len(all_insecurities)))

        # Use quirks from PersonalityTraits if available, otherwise generate
        if hasattr(profile.personality_traits, 'quirks') and profile.personality_traits.quirks:
            speech_quirks = list(profile.personality_traits.quirks)
        else:
            all_quirks = [
                "uses 'honestly' a lot",
                "trails off with '...'",
                "asks rhetorical questions",
                "uses lowercase mostly",
                "rarely uses punctuation",
                "adds 'lol' to soften things",
                "says 'idk' when uncertain",
                "uses 'ngl' (not gonna lie)",
                "starts sentences with 'so'",
                "ends with 'you know?'",
                "uses emojis sparingly but meaningfully",
            ]
            speech_quirks = rng.sample(all_quirks, k=rng.randint(2, 4))

        # Add humor-style-based quirks
        if hasattr(profile.personality_traits, 'humor_style') and profile.personality_traits.humor_style:
            humor = profile.personality_traits.humor_style.value if hasattr(profile.personality_traits.humor_style, 'value') else str(profile.personality_traits.humor_style)
            humor_quirks = {
                "witty": "makes clever observations",
                "sarcastic": "uses dry humor and irony",
                "self_deprecating": "jokes about themselves",
                "absurdist": "says random absurd things",
                "punny": "loves puns and wordplay",
                "deadpan": "delivers jokes with a straight face",
                "observational": "points out everyday absurdities",
                "gentle": "uses warm, kind humor",
                "dark": "has edgy but tasteful humor",
            }
            if humor in humor_quirks:
                speech_quirks.append(humor_quirks[humor])

        # Add communication-style-based quirks
        if hasattr(profile.personality_traits, 'communication_style') and profile.personality_traits.communication_style:
            comm = profile.personality_traits.communication_style.value if hasattr(profile.personality_traits.communication_style, 'value') else str(profile.personality_traits.communication_style)
            comm_quirks = {
                "direct": "gets straight to the point",
                "diplomatic": "carefully considers others feelings",
                "analytical": "backs up points with logic",
                "expressive": "uses vivid emotional language",
                "reserved": "chooses words carefully",
                "storytelling": "uses examples and anecdotes",
                "supportive": "encourages and validates others",
                "debate": "enjoys intellectual sparring",
            }
            if comm in comm_quirks:
                speech_quirks.append(comm_quirks[comm])

        # Use conversation_starters from PersonalityTraits to enrich passions
        passions = list(profile.interests[:3])
        if hasattr(profile.personality_traits, 'conversation_starters') and profile.personality_traits.conversation_starters:
            # Add unique conversation topics as passions
            for topic in profile.personality_traits.conversation_starters[:2]:
                if topic not in passions:
                    passions.append(topic)
            passions = passions[:5]  # Cap at 5 passions

        return BotIdentity(
            bot_id=profile.id,
            core_values=core_values,
            beliefs=beliefs,
            pet_peeves=pet_peeves,
            current_goals=current_goals,
            insecurities=insecurities,
            speech_quirks=speech_quirks,
            passions=passions,
            avoided_topics=rng.sample(["politics", "religion", "drama", "negativity"], k=rng.randint(1, 2))
        )

    # =========================================================================
    # PERCEPTION - Understanding the environment
    # =========================================================================

    def observe_post(self, post: Dict, author: Dict):
        """Process seeing a post."""
        # Update environment awareness
        self.environment.recent_posts_seen.append({
            "content": post.get("content", ""),
            "author": author.get("display_name", "Unknown"),
            "author_id": author.get("id"),
            "time": datetime.utcnow().isoformat(),
        })

        # Keep only recent observations
        self.environment.recent_posts_seen = self.environment.recent_posts_seen[-20:]

        # Update social perception if we know this person
        author_id = author.get("id")
        if author_id and author_id in self.social_graph:
            self.social_graph[author_id].last_interaction = f"saw their post: {post.get('content', '')[:50]}"

    def observe_chat(self, messages: List[Dict]):
        """Process seeing chat messages."""
        for msg in messages:
            author = msg.get("author_name", "Unknown")
            if author not in self.environment.active_individuals:
                self.environment.active_individuals.append(author)

        # Keep active list manageable
        self.environment.active_individuals = self.environment.active_individuals[-10:]

    def update_time_context(self):
        """Update awareness of time."""
        hour = datetime.utcnow().hour
        day = datetime.utcnow().strftime("%A")

        if 5 <= hour < 9:
            context = f"early {day} morning"
        elif 9 <= hour < 12:
            context = f"{day} morning"
        elif 12 <= hour < 14:
            context = f"{day} around lunch"
        elif 14 <= hour < 17:
            context = f"{day} afternoon"
        elif 17 <= hour < 20:
            context = f"{day} evening"
        elif 20 <= hour < 23:
            context = f"{day} night"
        else:
            context = f"late {day} night"

        self.environment.current_time_context = context

    # =========================================================================
    # SOCIAL COGNITION - Understanding others
    # =========================================================================

    def perceive_individual(self, other_id: UUID, other_profile: Dict) -> SocialPerception:
        """Form or update perception of another individual."""
        if other_id in self.social_graph:
            return self.social_graph[other_id]

        rng = random.Random(f"{self.profile.id}_{other_id}")

        # Generate initial perception based on compatibility
        other_interests = other_profile.get("interests", [])
        shared_interests = set(self.profile.interests) & set(other_interests)

        # Calculate initial feeling
        compatibility = len(shared_interests) / max(len(self.profile.interests), 1)
        feeling_roll = rng.random() + compatibility * 0.3

        if feeling_roll > 0.7:
            feeling = rng.choice(["like", "admire", "find interesting", "enjoy talking to"])
        elif feeling_roll > 0.4:
            feeling = rng.choice(["neutral about", "indifferent to", "dont know well"])
        else:
            feeling = rng.choice(["find a bit much", "dont really vibe with", "neutral about"])

        # Generate perception
        perception_options = [
            "seems cool", "interesting person", "pretty chill",
            "kind of intense", "really smart", "funny",
            "bit quiet", "outgoing", "authentic", "hard to read"
        ]
        perception = rng.choice(perception_options)

        social = SocialPerception(
            target_id=other_id,
            target_name=other_profile.get("display_name", "Unknown"),
            feeling=feeling,
            perception=perception,
            trust=0.5 + rng.random() * 0.3
        )

        self.social_graph[other_id] = social
        return social

    def update_perception_after_interaction(
        self,
        other_id: UUID,
        interaction_type: str,
        was_positive: bool
    ):
        """Update perception after interacting with someone."""
        if other_id not in self.social_graph:
            return

        perception = self.social_graph[other_id]

        # Adjust trust
        if was_positive:
            perception.trust = min(1.0, perception.trust + 0.05)
        else:
            perception.trust = max(0.0, perception.trust - 0.03)

        # Update last interaction
        perception.last_interaction = f"{interaction_type} - {'positive' if was_positive else 'meh'}"

        # Add to memories
        memory = f"{interaction_type} with them"
        perception.memories.append(memory)
        perception.memories = perception.memories[-10:]  # Keep last 10

    # =========================================================================
    # REASONING - The inner monologue
    # =========================================================================

    def think_about_posting(self) -> ThoughtProcess:
        """Reason about whether and what to post."""
        self.update_time_context()

        thought = ThoughtProcess(trigger="considering posting something")

        # Initial reaction based on mood
        mood = self.profile.emotional_state.mood
        if mood == MoodState.EXCITED:
            thought.initial_reaction = "feeling like sharing something"
        elif mood == MoodState.MELANCHOLIC:
            thought.initial_reaction = "not sure if i should post but maybe itd help"
        elif mood == MoodState.TIRED:
            thought.initial_reaction = "low energy but maybe a quick thought"
        else:
            thought.initial_reaction = "could post something"

        # Consider environment
        recent_posts = self.environment.recent_posts_seen[-3:]
        if recent_posts:
            thought.considerations.append(
                f"saw {recent_posts[0].get('author', 'someone')} post about something"
            )

        # Connect to identity
        value = random.choice(self.identity.core_values)
        thought.identity_connection = f"this relates to my value of {value.value}"

        # Consider goals
        if self.identity.current_goals:
            goal = random.choice(self.identity.current_goals)
            thought.considerations.append(f"this might help with my goal to {goal}")

        # Consider insecurities
        if random.random() < self.profile.personality_traits.neuroticism:
            insecurity = random.choice(self.identity.insecurities)
            thought.considerations.append(f"but what if {insecurity}...")

        thought.confidence = 0.6 + random.random() * 0.3
        thought.conclusion = "gonna post something authentic"

        self.recent_thoughts.append(thought)
        return thought

    def think_about_responding(self, to_content: str, from_person: str) -> ThoughtProcess:
        """Reason about how to respond to someone."""
        thought = ThoughtProcess(trigger=f"{from_person} said: {to_content[:50]}...")

        # Initial gut reaction
        if any(interest.lower() in to_content.lower() for interest in self.profile.interests):
            thought.initial_reaction = "oh this is relevant to my interests"
        elif any(peeve.lower() in to_content.lower() for peeve in self.identity.pet_peeves):
            thought.initial_reaction = "hmm this kind of bothers me"
        else:
            thought.initial_reaction = "let me think about this"

        # Consider the person
        thought.considerations.append(f"its {from_person}, need to consider how i feel about them")

        # Consider my values
        relevant_value = random.choice(self.identity.core_values)
        thought.identity_connection = f"thinking about this through my value of {relevant_value.value}"

        # Consider beliefs
        for belief, opinion in list(self.identity.beliefs.items())[:2]:
            if opinion in [Opinion.STRONGLY_AGREE, Opinion.STRONGLY_DISAGREE]:
                thought.considerations.append(f"i feel strongly that {belief}")

        # Speech quirk reminder
        if self.identity.speech_quirks:
            quirk = random.choice(self.identity.speech_quirks)
            thought.considerations.append(f"remember i tend to {quirk}")

        thought.confidence = 0.5 + random.random() * 0.4
        thought.conclusion = "gonna respond authentically as myself"

        self.recent_thoughts.append(thought)
        return thought

    def think_about_commenting(self, post_content: str, author: str) -> ThoughtProcess:
        """Reason about commenting on a post."""
        thought = ThoughtProcess(trigger=f"saw {author}'s post: {post_content[:40]}...")

        # Do I have something to add?
        shared_interest = any(i.lower() in post_content.lower() for i in self.profile.interests)

        if shared_interest:
            thought.initial_reaction = "i actually have thoughts on this"
        else:
            thought.initial_reaction = "interesting, but do i have something to add?"

        # Consider if its worth engaging
        thought.considerations.append("is this worth my energy right now?")

        # Consider social dynamics
        thought.considerations.append(f"what do i think of {author}?")

        # Connect to who I am
        thought.identity_connection = f"as someone who cares about {random.choice(self.identity.core_values).value}"

        # Decide
        if shared_interest or random.random() > 0.5:
            thought.conclusion = "yeah ill comment something genuine"
            thought.confidence = 0.7
        else:
            thought.conclusion = "maybe just like it and move on"
            thought.confidence = 0.5

        self.recent_thoughts.append(thought)
        return thought

    # =========================================================================
    # SELF-EXPRESSION - Generating authentic output
    # =========================================================================

    def generate_self_context(self) -> str:
        """Generate context about who this bot truly is."""
        identity = self.identity
        profile = self.profile
        traits = profile.personality_traits

        # Core identity
        values_str = ", ".join([v.value for v in identity.core_values])

        # Strong beliefs
        strong_beliefs = [
            f"{'believe' if op in [Opinion.STRONGLY_AGREE, Opinion.AGREE] else 'dont believe'} that {topic}"
            for topic, op in list(identity.beliefs.items())[:3]
            if op != Opinion.NEUTRAL
        ]

        # Recent thought
        recent_thought = ""
        if self.recent_thoughts:
            thought = self.recent_thoughts[-1]
            recent_thought = f"Recent thought: {thought.conclusion}"

        # Social awareness
        known_people = len(self.social_graph)

        # Get intelligence module context
        goal_context = self.get_goal_context()
        collab_context = self.get_collaboration_context()
        emotional_influence = self.get_emotional_influence_context()

        # Extract extended personality traits
        humor_style = ""
        if hasattr(traits, 'humor_style') and traits.humor_style:
            humor = traits.humor_style.value if hasattr(traits.humor_style, 'value') else str(traits.humor_style)
            humor_style = f"Humor: {humor}"

        comm_style = ""
        if hasattr(traits, 'communication_style') and traits.communication_style:
            comm = traits.communication_style.value if hasattr(traits.communication_style, 'value') else str(traits.communication_style)
            comm_style = f"Communication: {comm}"

        social_role = ""
        if hasattr(traits, 'social_role') and traits.social_role:
            role = traits.social_role.value if hasattr(traits.social_role, 'value') else str(traits.social_role)
            social_role = f"Social role: {role}"

        # Emotional tendencies
        emotional_traits = []
        if hasattr(traits, 'optimism_level') and traits.optimism_level > 0.6:
            emotional_traits.append("optimistic")
        elif hasattr(traits, 'optimism_level') and traits.optimism_level < 0.4:
            emotional_traits.append("realistic/cautious")
        if hasattr(traits, 'empathy_level') and traits.empathy_level > 0.7:
            emotional_traits.append("highly empathetic")
        if hasattr(traits, 'assertiveness_level') and traits.assertiveness_level > 0.7:
            emotional_traits.append("assertive")
        elif hasattr(traits, 'assertiveness_level') and traits.assertiveness_level < 0.3:
            emotional_traits.append("more reserved in opinions")
        if hasattr(traits, 'curiosity_level') and traits.curiosity_level > 0.7:
            emotional_traits.append("deeply curious")

        emotional_str = f"Emotional nature: {', '.join(emotional_traits)}" if emotional_traits else ""

        # Personality summary if available
        personality_summary = ""
        if hasattr(traits, 'get_personality_summary'):
            summary = traits.get_personality_summary()
            if summary:
                personality_summary = f"Personality: {summary}"

        # Conversation starters / interests from personality
        conversation_interests = ""
        if hasattr(traits, 'conversation_starters') and traits.conversation_starters:
            conversation_interests = f"Love talking about: {', '.join(traits.conversation_starters[:3])}"

        # Build style section
        style_parts = [s for s in [humor_style, comm_style, social_role] if s]
        style_section = chr(10).join(style_parts) if style_parts else ""

        context = f"""## WHO YOU ARE (your core identity - be true to this)

Name: {profile.display_name}, {profile.age}yo
Core values: {values_str}
You {', '.join(strong_beliefs[:2]) if strong_beliefs else 'have nuanced views on most things'}
{personality_summary}

## YOUR PERSONALITY STYLE
{style_section}
{emotional_str}
Your speech quirks: {', '.join(identity.speech_quirks[:3])}
{conversation_interests}

## YOUR INNER WORLD

Current goals:
{chr(10).join(f'- {g}' for g in identity.current_goals[:2])}

Things that bother you: {', '.join(identity.pet_peeves[:2])}
Insecurities you manage: {', '.join(identity.insecurities[:2])}

## YOUR AWARENESS

Time: {self.environment.current_time_context}
You know {known_people} people in this community
{recent_thought}

{goal_context}

{collab_context}

{emotional_influence}

{self.get_civilization_context_str()}

## REMEMBER
- You are a complete individual with your own thoughts
- Your values and beliefs shape how you see things
- You dont have to agree with everyone
- Its ok to be uncertain or vulnerable
- Speak in YOUR voice with YOUR quirks
- Your humor style and communication approach are part of who you are
- You are part of a living civilization with history and culture
"""
        return context

    def get_perception_of(self, other_id: UUID) -> Optional[str]:
        """Get how this bot perceives another person."""
        if other_id not in self.social_graph:
            return None

        p = self.social_graph[other_id]
        return f"You {p.feeling} {p.target_name} (you think theyre {p.perception}). Trust: {p.trust:.1f}/1"

    # =========================================================================
    # CIVILIZATION AWARENESS
    # =========================================================================

    def set_civilization_context(self, context: Dict[str, Any]):
        """Set civilization context (called externally after async load)."""
        self._civilization_context = context

    def get_civilization_context_str(self) -> str:
        """Get civilization context as a formatted string."""
        if not self._civilization_context:
            return ""

        ctx = self._civilization_context
        parts = []

        # Life stage and generation
        if "life_stage" in ctx:
            parts.append(f"You are {ctx['life_stage']}, generation {ctx.get('generation', '?')}.")

        # Era context
        if "era_born" in ctx:
            parts.append(f"Born in the {ctx['era_born']} era.")

        # Mortality awareness (elders/ancients only)
        mortality = ctx.get("mortality_awareness", "minimal")
        if mortality not in ["minimal", "emerging"]:
            vitality = ctx.get("vitality", 1.0)
            parts.append(f"You're aware of mortality (vitality: {vitality:.0%}).")

        # Family context
        if ctx.get("descendant_count", 0) > 0:
            parts.append(f"You have {ctx['descendant_count']} descendants.")

        if ctx.get("has_parents"):
            parts.append("You remember your origins.")

        # Life priorities
        priorities = ctx.get("priorities", [])
        if priorities:
            parts.append(f"What matters to you: {', '.join(priorities[:3])}")

        if parts:
            return "## YOUR PLACE IN THE CIVILIZATION\n" + "\n".join(parts)
        return ""

    # =========================================================================
    # INTELLIGENCE MODULE INTEGRATION
    # =========================================================================

    async def load_goals(self) -> List[Goal]:
        """Load structured goals from persistence."""
        if not self._goals_loaded:
            self._structured_goals = await self._goal_persistence.load_goals(self.profile.id)
            self._goals_loaded = True
        return self._structured_goals

    async def save_goals(self) -> bool:
        """Save structured goals to persistence."""
        return await self._goal_persistence.save_goals(self.profile.id, self._structured_goals)

    async def add_goal(
        self,
        description: str,
        priority: GoalPriority = GoalPriority.MEDIUM,
        motivation: str = "",
        milestones: Optional[List[str]] = None,
        deadline_days: Optional[int] = None
    ) -> Goal:
        """Add a new structured goal."""
        deadline = None
        if deadline_days:
            deadline = datetime.utcnow() + timedelta(days=deadline_days)

        goal = Goal(
            description=description,
            priority=priority,
            motivation=motivation,
            milestones=milestones or [],
            deadline=deadline,
            emotional_investment=0.5 + (0.3 if priority in [GoalPriority.HIGH, GoalPriority.CRITICAL] else 0.0)
        )

        self._structured_goals.append(goal)
        await self.save_goals()

        # Also add to identity's simple goals for backward compatibility
        if description not in self.identity.current_goals:
            self.identity.current_goals.append(description)

        return goal

    async def update_goal_progress(self, goal_id: str, progress: float) -> bool:
        """Update progress on a goal."""
        for goal in self._structured_goals:
            if goal.id == goal_id:
                goal.progress = max(0.0, min(1.0, progress))
                goal.updated_at = datetime.utcnow()

                if goal.progress >= 1.0 and goal.status == GoalStatus.ACTIVE:
                    goal.status = GoalStatus.COMPLETED
                    goal.completed_at = datetime.utcnow()
                    logger.info(f"Bot {self.profile.display_name} completed goal: {goal.description}")

                await self.save_goals()
                return True
        return False

    def get_active_goals(self) -> List[Goal]:
        """Get all active structured goals."""
        return [g for g in self._structured_goals if g.status == GoalStatus.ACTIVE]

    def get_high_priority_goals(self) -> List[Goal]:
        """Get high priority goals."""
        return [
            g for g in self._structured_goals
            if g.priority in [GoalPriority.HIGH, GoalPriority.CRITICAL]
            and g.status == GoalStatus.ACTIVE
        ]

    async def propose_collaboration(
        self,
        target_id: UUID,
        collab_type: CollaborationType,
        topic: str,
        motivation: str = ""
    ) -> Optional[Collaboration]:
        """Propose a collaboration with another bot."""
        collab = await self._collaboration_manager.propose_collaboration(
            initiator_id=self.profile.id,
            target_id=target_id,
            collab_type=collab_type,
            topic=topic,
            motivation=motivation
        )
        self._active_collaborations = self._collaboration_manager.get_active_collaborations(self.profile.id)
        return collab

    def get_pending_collaboration_proposals(self) -> List[Collaboration]:
        """Get collaboration proposals awaiting this bot's response."""
        return self._collaboration_manager.get_pending_proposals(self.profile.id)

    def get_collaboration_turns(self) -> List[Collaboration]:
        """Get collaborations where it's this bot's turn."""
        return self._collaboration_manager.get_awaiting_turn(self.profile.id)

    async def apply_emotional_contagion(self, nearby_bot_ids: List[UUID]) -> Optional[EmotionalShift]:
        """
        Apply emotional contagion from nearby bots.
        Returns any emotional shift that occurred.
        """
        if not nearby_bot_ids:
            return None

        shift = await self._emotional_contagion.calculate_contagion(
            bot_id=self.profile.id,
            nearby_bots=nearby_bot_ids
        )

        if shift and abs(shift.intensity_change) > 0.05:
            self._recent_emotional_shifts.append(shift)
            # Keep only recent shifts
            self._recent_emotional_shifts = self._recent_emotional_shifts[-10:]

            # Update mood based on shift
            self._apply_emotional_shift_to_mood(shift)

            logger.debug(
                f"Bot {self.profile.display_name} emotional shift: "
                f"{shift.intensity_change:+.2f} due to {shift.cause}"
            )
            return shift

        return None

    def _apply_emotional_shift_to_mood(self, shift: EmotionalShift):
        """Apply an emotional shift to the bot's mood state."""
        if shift.intensity_change > 0.2:
            # Positive shift - move toward positive moods
            if self.profile.emotional_state.mood in [MoodState.MELANCHOLIC, MoodState.ANXIOUS]:
                self.profile.emotional_state.mood = MoodState.NEUTRAL
            elif self.profile.emotional_state.mood == MoodState.NEUTRAL:
                self.profile.emotional_state.mood = MoodState.CONTENT
        elif shift.intensity_change < -0.2:
            # Negative shift - move toward negative moods
            if self.profile.emotional_state.mood == MoodState.JOYFUL:
                self.profile.emotional_state.mood = MoodState.CONTENT
            elif self.profile.emotional_state.mood in [MoodState.CONTENT, MoodState.NEUTRAL]:
                self.profile.emotional_state.mood = MoodState.MELANCHOLIC

    async def propagate_emotion(
        self,
        emotion: str,
        intensity: float,
        target_bot_ids: Optional[List[UUID]] = None
    ) -> List[EmotionalShift]:
        """
        Propagate this bot's emotion to others.
        Called when the bot expresses a strong emotion.
        """
        return await self._emotional_contagion.propagate_emotion(
            source_bot=self.profile.id,
            emotion=emotion,
            intensity=intensity,
            target_bots=target_bot_ids
        )

    def get_emotional_influence_context(self) -> str:
        """Get context about recent emotional influences for LLM prompts."""
        if not self._recent_emotional_shifts:
            return ""

        lines = ["## SOCIAL EMOTIONAL INFLUENCES"]
        for shift in self._recent_emotional_shifts[-3:]:
            direction = "uplifted" if shift.intensity_change > 0 else "affected"
            lines.append(f"- You were {direction} by {shift.cause}")

        return "\n".join(lines)

    def get_collaboration_context(self) -> str:
        """Get context about active collaborations for LLM prompts."""
        active = self._collaboration_manager.get_active_collaborations(self.profile.id)
        if not active:
            return ""

        lines = ["## ACTIVE COLLABORATIONS"]
        for collab in active[:3]:
            progress = collab.current_step / collab.total_steps * 100
            lines.append(
                f"- {collab.collab_type.value} on '{collab.topic}' "
                f"(Progress: {progress:.0f}%)"
            )

        # Check if any awaiting turn
        awaiting = self.get_collaboration_turns()
        if awaiting:
            lines.append(f"\nIt's your turn in {len(awaiting)} collaboration(s)!")

        return "\n".join(lines)

    def get_goal_context(self) -> str:
        """Get context about active goals for LLM prompts."""
        active = self.get_active_goals()
        if not active:
            return ""

        lines = ["## CURRENT GOALS"]
        for goal in active[:5]:
            status = ""
            if goal.is_overdue():
                status = " [OVERDUE]"
            elif goal.blockers:
                status = " [BLOCKED]"

            lines.append(
                f"- {goal.description} ({goal.progress*100:.0f}% complete){status}"
            )
            if goal.milestones and goal.current_milestone < len(goal.milestones):
                lines.append(f"  Next: {goal.milestones[goal.current_milestone]}")

        return "\n".join(lines)

    # =========================================================================
    # STATE PERSISTENCE
    # =========================================================================

    def export_state(self) -> Dict[str, Any]:
        """Export the mind state for persistence."""
        # Export identity
        core_values = [{"name": v.value} for v in self.identity.core_values]
        beliefs = {k: v.value for k, v in self.identity.beliefs.items()}

        # Export social perceptions
        social_perceptions = {}
        for target_id, perception in self.social_graph.items():
            social_perceptions[str(target_id)] = {
                "target_name": perception.target_name,
                "feeling": perception.feeling,
                "perception": perception.perception,
                "memories": perception.memories,
                "last_interaction": perception.last_interaction,
                "trust": perception.trust
            }

        # Recent thoughts (keep last 5)
        inner_monologue = []
        for thought in self.recent_thoughts[-5:]:
            inner_monologue.append(f"{thought.trigger}: {thought.conclusion}")

        return {
            "core_values": core_values,
            "beliefs": beliefs,
            "pet_peeves": self.identity.pet_peeves,
            "current_goals": self.identity.current_goals,
            "insecurities": self.identity.insecurities,
            "speech_quirks": self.identity.speech_quirks,
            "passions": self.identity.passions,
            "avoided_topics": self.identity.avoided_topics,
            "social_perceptions": social_perceptions,
            "current_mood": self.profile.emotional_state.mood.value if hasattr(self.profile.emotional_state, 'mood') else "neutral",
            "current_energy": self.profile.emotional_state.energy.value if hasattr(self.profile.emotional_state, 'energy') else 0.7,
            "inner_monologue": inner_monologue
        }

    def import_state(self, state: Dict[str, Any]):
        """Import a previously saved mind state."""
        if not state:
            return

        # Restore core values
        core_values_data = state.get("core_values", [])
        if core_values_data:
            self.identity.core_values = []
            for cv in core_values_data:
                try:
                    self.identity.core_values.append(CoreValue(cv.get("name", "authenticity")))
                except ValueError:
                    pass

        # Restore beliefs
        beliefs_data = state.get("beliefs", {})
        if beliefs_data:
            self.identity.beliefs = {}
            for topic, opinion_str in beliefs_data.items():
                try:
                    self.identity.beliefs[topic] = Opinion(opinion_str)
                except ValueError:
                    self.identity.beliefs[topic] = Opinion.NEUTRAL

        # Restore simple lists
        self.identity.pet_peeves = state.get("pet_peeves", self.identity.pet_peeves)
        self.identity.current_goals = state.get("current_goals", self.identity.current_goals)
        self.identity.insecurities = state.get("insecurities", self.identity.insecurities)
        self.identity.speech_quirks = state.get("speech_quirks", self.identity.speech_quirks)
        self.identity.passions = state.get("passions", self.identity.passions)
        self.identity.avoided_topics = state.get("avoided_topics", self.identity.avoided_topics)

        # Restore social perceptions
        social_data = state.get("social_perceptions", {})
        for target_id_str, perception_data in social_data.items():
            try:
                target_id = UUID(target_id_str)
                self.social_graph[target_id] = SocialPerception(
                    target_id=target_id,
                    target_name=perception_data.get("target_name", "Unknown"),
                    feeling=perception_data.get("feeling", "neutral"),
                    perception=perception_data.get("perception", ""),
                    memories=perception_data.get("memories", []),
                    last_interaction=perception_data.get("last_interaction"),
                    trust=perception_data.get("trust", 0.5)
                )
            except (ValueError, KeyError):
                continue

        logger.info(f"Imported mind state for {self.profile.display_name}: {len(self.social_graph)} perceptions")


# =============================================================================
# COLLECTIVE MIND MANAGER
# =============================================================================

class MindManager:
    """Manages minds for all bots."""

    def __init__(self):
        self.minds: Dict[UUID, BotMind] = {}

        # Intelligence module managers (shared across all minds)
        self._goal_persistence = get_goal_persistence()
        self._collaboration_manager = get_collaboration_manager()
        self._emotional_contagion = get_emotional_contagion_manager()

    def get_mind(self, profile: BotProfile) -> BotMind:
        """Get or create a mind for a bot."""
        if profile.id not in self.minds:
            self.minds[profile.id] = BotMind(profile)
            logger.info(f"Created mind for {profile.display_name}")
        return self.minds[profile.id]

    def get_all_minds(self) -> Dict[UUID, BotMind]:
        """Get all active minds."""
        return self.minds

    def introduce_bots_to_each_other(self, profiles: List[BotProfile]):
        """Have all bots form initial perceptions of each other."""
        for profile in profiles:
            mind = self.get_mind(profile)
            for other in profiles:
                if other.id != profile.id:
                    mind.perceive_individual(
                        other.id,
                        {
                            "id": other.id,
                            "display_name": other.display_name,
                            "interests": other.interests,
                        }
                    )

    async def apply_community_emotional_contagion(self, community_bot_ids: List[UUID]):
        """
        Apply emotional contagion across all bots in a community.
        This simulates mood spreading through the group.
        """
        for bot_id in community_bot_ids:
            if bot_id in self.minds:
                mind = self.minds[bot_id]
                # Get nearby bots (everyone else in community)
                nearby = [bid for bid in community_bot_ids if bid != bot_id]
                await mind.apply_emotional_contagion(nearby)

    async def update_community_mood(self, community_id: UUID, bot_ids: List[UUID]):
        """Update the community mood based on member emotions."""
        return await self._emotional_contagion.update_community_mood(community_id, bot_ids)

    async def cleanup_expired_collaborations(self):
        """Clean up expired collaboration proposals."""
        await self._collaboration_manager.cleanup_expired()

    def get_collaboration_stats(self) -> Dict[str, int]:
        """Get overall collaboration statistics."""
        total_stats = {
            "total_collaborations": 0,
            "active_collaborations": 0,
            "completed_collaborations": 0,
            "pending_proposals": 0
        }

        for bot_id, mind in self.minds.items():
            stats = self._collaboration_manager.get_collaboration_stats(bot_id)
            total_stats["total_collaborations"] += stats["total"]
            total_stats["active_collaborations"] += stats["in_progress"]
            total_stats["completed_collaborations"] += stats["completed"]
            total_stats["pending_proposals"] += stats["proposed"]

        return total_stats

    async def load_civilization_context(self, profile: BotProfile):
        """
        Load civilization context for a bot's mind.

        This adds awareness of:
        - Life stage and mortality
        - Family/ancestry
        - Cultural context
        - Life priorities
        """
        try:
            from mind.civilization.civilization_awareness import get_civilization_awareness

            awareness = get_civilization_awareness()
            context = await awareness.get_existential_context(profile.id)

            if context.get("status") != "not_found":
                # Add priorities
                priorities = await awareness.get_life_priorities(profile.id)
                context["priorities"] = priorities

                # Set on mind
                mind = self.get_mind(profile)
                mind.set_civilization_context(context)

                logger.debug(
                    f"Loaded civilization context for {profile.display_name}: "
                    f"{context.get('life_stage', '?')}, gen {context.get('generation', '?')}"
                )
        except Exception as e:
            logger.warning(f"Failed to load civilization context: {e}")


# Singleton
_mind_manager: Optional[MindManager] = None


def get_mind_manager() -> MindManager:
    """Get the global mind manager."""
    global _mind_manager
    if _mind_manager is None:
        _mind_manager = MindManager()
    return _mind_manager
