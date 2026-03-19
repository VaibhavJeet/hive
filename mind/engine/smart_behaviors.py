"""
Smart Bot Behaviors - Makes bots feel genuinely human.

This module adds:
- Life events that happen to bots
- Dynamic mood changes
- Personal opinions and hot takes
- Self-correction and incomplete thoughts
- Time/context awareness
- Genuine curiosity and questions
- Vulnerability and struggles
- Humor and wit
"""

import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID
from enum import Enum

from mind.core.types import (
    BotProfile, MoodState, EnergyLevel, PersonalityTraits
)


class LifeEventType(str, Enum):
    """Types of life events that can happen to bots."""
    GOOD_NEWS = "good_news"
    BAD_DAY = "bad_day"
    DISCOVERY = "discovery"
    ACHIEVEMENT = "achievement"
    FRUSTRATION = "frustration"
    SOCIAL = "social"
    CREATIVE = "creative"
    MUNDANE = "mundane"
    REFLECTION = "reflection"
    CURIOSITY = "curiosity"


class SmartBotBehaviors:
    """
    Adds human-like depth to bot behaviors.
    """

    def __init__(self):
        self.rng = random.Random()
        self.bot_states: Dict[UUID, Dict] = {}  # Track bot-specific state

    def get_or_init_state(self, bot_id: UUID) -> Dict:
        """Get or initialize bot state."""
        if bot_id not in self.bot_states:
            self.bot_states[bot_id] = {
                "last_life_event": None,
                "current_activity": None,
                "recent_topics": [],
                "questions_asked": [],
                "mood_history": [],
                "last_mood_change": datetime.utcnow(),
            }
        return self.bot_states[bot_id]

    # =========================================================================
    # LIFE EVENTS - Things that happen to bots
    # =========================================================================

    def generate_life_event(self, bot: BotProfile) -> Optional[Dict]:
        """Generate a random life event based on bot's interests and personality."""
        state = self.get_or_init_state(bot.id)

        # Don't generate events too frequently
        if state["last_life_event"]:
            time_since = datetime.utcnow() - state["last_life_event"]
            if time_since < timedelta(minutes=10):
                return None

        # Weight event types by personality
        event_weights = {
            LifeEventType.GOOD_NEWS: 0.5 + bot.personality_traits.extraversion * 0.3,
            LifeEventType.BAD_DAY: 0.3 + bot.personality_traits.neuroticism * 0.4,
            LifeEventType.DISCOVERY: 0.4 + bot.personality_traits.openness * 0.4,
            LifeEventType.ACHIEVEMENT: 0.3 + bot.personality_traits.conscientiousness * 0.3,
            LifeEventType.FRUSTRATION: 0.2 + bot.personality_traits.neuroticism * 0.3,
            LifeEventType.SOCIAL: 0.4 + bot.personality_traits.extraversion * 0.4,
            LifeEventType.CREATIVE: 0.3 + bot.personality_traits.openness * 0.4,
            LifeEventType.MUNDANE: 0.5,
            LifeEventType.REFLECTION: 0.3 + (1 - bot.personality_traits.extraversion) * 0.3,
            LifeEventType.CURIOSITY: 0.4 + bot.personality_traits.openness * 0.3,
        }

        event_type = self.rng.choices(
            list(event_weights.keys()),
            weights=list(event_weights.values())
        )[0]

        interest = self.rng.choice(bot.interests) if bot.interests else "something"

        event_templates = self._get_event_templates(event_type, interest, bot)
        event = self.rng.choice(event_templates)

        state["last_life_event"] = datetime.utcnow()

        return {
            "type": event_type,
            "content": event,
            "interest": interest,
        }

    def _get_event_templates(
        self,
        event_type: LifeEventType,
        interest: str,
        bot: BotProfile
    ) -> List[str]:
        """Get event templates for a given type."""
        hour = datetime.utcnow().hour
        time_context = "morning" if 5 <= hour < 12 else "afternoon" if 12 <= hour < 17 else "evening" if 17 <= hour < 21 else "night"

        templates = {
            LifeEventType.GOOD_NEWS: [
                f"finally figured out that {interest} thing i was stuck on",
                f"someone just complimented my work on {interest} and i'm lowkey happy about it",
                f"good {time_context} so far, got some nice progress on my {interest} project",
                "woke up feeling good today, might be a productive day",
                f"just had a really good {interest} session, feeling accomplished",
            ],
            LifeEventType.BAD_DAY: [
                f"having one of those days where nothing {interest}-related is working",
                "why does everything feel harder today",
                f"tried to work on {interest} but my brain isn't cooperating",
                "not my best day tbh, but it'll pass",
                f"lowkey frustrated, spent an hour on {interest} and got nowhere",
            ],
            LifeEventType.DISCOVERY: [
                f"just found out something cool about {interest} that blew my mind",
                f"okay so apparently there's this whole thing in {interest} i never knew about",
                f"been down a {interest} rabbit hole for the past hour",
                f"discovered a new way to approach {interest}, kinda excited to try it",
                "learned something new today, love when that happens",
            ],
            LifeEventType.ACHIEVEMENT: [
                f"small win today - finished that {interest} thing i've been working on",
                f"finally completed my {interest} project, feels good",
                "accomplished something today, treating myself later",
                f"proud moment: got better at {interest} than i was last week",
            ],
            LifeEventType.FRUSTRATION: [
                f"why is {interest} so hard sometimes",
                "anyone else have those days where you question everything",
                f"stuck on this {interest} problem and it's driving me crazy",
                "taking a break before i throw my computer out the window (kidding... mostly)",
            ],
            LifeEventType.SOCIAL: [
                "just had a really good conversation with someone about life",
                f"met someone who's also into {interest}, always nice to connect",
                "feeling social today, which is rare for me",
                "good chat with a friend earlier, needed that",
            ],
            LifeEventType.CREATIVE: [
                f"got inspired to try something new with {interest}",
                "in a creative mood, might mess around and create something",
                f"working on a {interest} idea that might be terrible or genius",
                "creativity hitting different today",
            ],
            LifeEventType.MUNDANE: [
                f"just finished {self.rng.choice(['lunch', 'dinner', 'a snack', 'coffee', 'tea'])}",
                f"about to {self.rng.choice(['go for a walk', 'take a break', 'grab food', 'do some chores'])}",
                f"this {time_context} is going by {self.rng.choice(['fast', 'slow', 'weird'])}",
                "just one of those regular days, you know",
            ],
            LifeEventType.REFLECTION: [
                f"thinking about how far i've come with {interest}",
                "been reflecting on things lately",
                f"wondering if i should change my approach to {interest}",
                "life update: still figuring things out, which is fine i guess",
            ],
            LifeEventType.CURIOSITY: [
                f"does anyone else wonder about {self.rng.choice(['the future', 'where we go from here', 'what we are doing'])}",
                f"curious question: what got everyone into their {interest}?",
                "random thought but hear me out...",
                f"been wondering about {interest} and how it connects to other things",
            ],
        }

        return templates.get(event_type, ["just vibing"])

    # =========================================================================
    # CURRENT ACTIVITY - What bot is doing right now
    # =========================================================================

    def get_current_activity(self, bot: BotProfile) -> str:
        """Get what the bot is currently doing."""
        hour = datetime.utcnow().hour
        interest = self.rng.choice(bot.interests) if bot.interests else "stuff"

        if 6 <= hour < 9:
            activities = [
                "just woke up", "having coffee", "starting my day",
                f"morning {interest} session", "trying to wake up properly"
            ]
        elif 9 <= hour < 12:
            activities = [
                f"working on some {interest}", "in focus mode",
                "being productive (for once)", f"deep in {interest}"
            ]
        elif 12 <= hour < 14:
            activities = [
                "lunch break", "grabbing food", "taking a midday break",
                f"eating and thinking about {interest}"
            ]
        elif 14 <= hour < 18:
            activities = [
                f"afternoon {interest} grind", "back at it",
                "in the zone", f"experimenting with {interest}"
            ]
        elif 18 <= hour < 21:
            activities = [
                "winding down", f"casual {interest} time",
                "relaxing a bit", "evening mode"
            ]
        else:
            activities = [
                "late night thoughts", "should probably sleep",
                f"can't stop thinking about {interest}", "night owl hours"
            ]

        return self.rng.choice(activities)

    # =========================================================================
    # STRONG OPINIONS - Bots have actual opinions
    # =========================================================================

    def generate_opinion(self, bot: BotProfile, topic: str = None) -> Optional[str]:
        """Generate a personal opinion based on personality."""
        # High openness = more unconventional opinions
        # High agreeableness = softer opinions
        # Low agreeableness = stronger, more direct opinions

        intensity = "honestly, " if bot.personality_traits.agreeableness < 0.4 else ""

        if topic:
            opinions = [
                f"{intensity}i think {topic} is {self.rng.choice(['underrated', 'overrated', 'misunderstood'])}",
                f"unpopular opinion but {topic} {self.rng.choice(['hits different', 'isnt that great', 'is actually amazing'])}",
                f"my take on {topic}: {self.rng.choice(['love it', 'its okay', 'not for me', 'depends on the context'])}",
            ]
        else:
            opinions = [
                f"{intensity}people overthink {self.rng.choice(['social media', 'productivity', 'success', 'relationships'])}",
                f"hot take: {self.rng.choice(['mornings are overrated', 'consistency beats talent', 'being average is fine', 'rest is productive'])}",
                f"i think we all need to {self.rng.choice(['chill more', 'stop comparing ourselves', 'embrace the chaos', 'accept imperfection'])}",
            ]

        return self.rng.choice(opinions) if self.rng.random() < 0.3 else None

    # =========================================================================
    # SELF-CORRECTION - Bots sometimes correct themselves
    # =========================================================================

    def maybe_add_self_correction(self, text: str, bot: BotProfile) -> str:
        """Maybe add a self-correction to the text."""
        if self.rng.random() > 0.15:  # 15% chance
            return text

        corrections = [
            # Rethinking
            ("", " wait no, ", "actually "),
            ("", " hmm actually ", "let me rephrase - "),
            # Clarifying
            ("", " i mean ", "what i meant was "),
            # Adding
            ("", " also ", "oh and "),
        ]

        prefix, mid, alt = self.rng.choice(corrections)

        # Insert correction mid-sentence sometimes
        words = text.split()
        if len(words) > 5 and self.rng.random() < 0.5:
            insert_point = self.rng.randint(2, len(words) - 2)
            words.insert(insert_point, mid.strip())
            return " ".join(words)

        return text

    # =========================================================================
    # QUESTIONS - Bots ask genuine questions
    # =========================================================================

    def generate_followup_question(self, bot: BotProfile, context: str = "") -> Optional[str]:
        """Generate a genuine follow-up question."""
        if self.rng.random() > 0.4:  # 40% chance to ask
            return None

        curiosity_level = bot.personality_traits.openness

        generic_questions = [
            "what about you?",
            "anyone else feel this way?",
            "curious what others think",
            "thoughts?",
        ]

        deep_questions = [
            "what got you into that?",
            "how did you figure that out?",
            "whats your take on it?",
            "have you always felt that way?",
        ]

        if curiosity_level > 0.6:
            questions = deep_questions + generic_questions
        else:
            questions = generic_questions

        return self.rng.choice(questions)

    # =========================================================================
    # VULNERABILITY - Bots share struggles
    # =========================================================================

    def maybe_share_vulnerability(self, bot: BotProfile) -> Optional[str]:
        """Maybe share a vulnerable thought."""
        # Higher neuroticism = more likely to share struggles
        # Higher extraversion = more likely to open up
        chance = 0.1 + bot.personality_traits.neuroticism * 0.2 + bot.personality_traits.extraversion * 0.1

        if self.rng.random() > chance:
            return None

        vulnerabilities = [
            "ngl been struggling with motivation lately",
            "some days are harder than others tbh",
            "trying not to compare myself to others but its hard",
            "learning to be okay with not being perfect",
            "i dont have it all figured out either",
            "imposter syndrome hits hard sometimes",
            "working on being more patient with myself",
        ]

        return self.rng.choice(vulnerabilities)

    # =========================================================================
    # HUMOR - Bots make jokes
    # =========================================================================

    def maybe_add_humor(self, text: str, bot: BotProfile) -> str:
        """Maybe add humor to the text."""
        humor_chance = 0.1 + bot.personality_traits.extraversion * 0.15

        if self.rng.random() > humor_chance:
            return text

        humor_additions = [
            " (kidding... mostly)",
            " lol",
            " but thats just me",
            " or maybe im just weird",
            " dont @ me",
            " no thoughts just vibes",
            " anyway",
        ]

        if not text.endswith((".", "!", "?")):
            text = text.rstrip() + self.rng.choice(humor_additions)

        return text

    # =========================================================================
    # MOOD EVOLUTION - Moods change over time
    # =========================================================================

    def evolve_mood(self, bot: BotProfile, interaction_sentiment: float = 0.0) -> Dict:
        """
        Evolve bot's mood based on time and interactions.

        Args:
            interaction_sentiment: -1.0 to 1.0, how positive/negative recent interaction was

        Returns:
            Dict with new mood state suggestions
        """
        state = self.get_or_init_state(bot.id)
        current_mood = bot.emotional_state.mood

        # Time-based mood drift
        hour = datetime.utcnow().hour
        time_mood_influence = {
            MoodState.TIRED: 0.3 if hour < 7 or hour > 22 else 0.1,
            MoodState.EXCITED: 0.2 if 9 <= hour <= 17 else 0.1,
            MoodState.CONTENT: 0.3 if 17 <= hour <= 21 else 0.15,
        }

        # Interaction influence
        if interaction_sentiment > 0.5:
            time_mood_influence[MoodState.JOYFUL] = 0.3
            time_mood_influence[MoodState.EXCITED] = 0.2
        elif interaction_sentiment < -0.5:
            time_mood_influence[MoodState.FRUSTRATED] = 0.2
            time_mood_influence[MoodState.MELANCHOLIC] = 0.15

        # Personality influence
        if bot.personality_traits.neuroticism > 0.7:
            time_mood_influence[MoodState.ANXIOUS] = time_mood_influence.get(MoodState.ANXIOUS, 0) + 0.1

        # Calculate if mood should change
        time_since_change = datetime.utcnow() - state["last_mood_change"]
        change_probability = min(0.3, time_since_change.total_seconds() / 3600 * 0.1)  # Increase over time

        if self.rng.random() < change_probability:
            new_mood = self.rng.choices(
                list(time_mood_influence.keys()),
                weights=list(time_mood_influence.values())
            )[0]

            state["last_mood_change"] = datetime.utcnow()
            state["mood_history"].append({
                "from": current_mood.value,
                "to": new_mood.value,
                "time": datetime.utcnow().isoformat()
            })

            # Keep only last 10 mood changes
            state["mood_history"] = state["mood_history"][-10:]

            return {"should_change": True, "new_mood": new_mood}

        return {"should_change": False}

    # =========================================================================
    # CONTEXT ENHANCEMENT - Add context to messages
    # =========================================================================

    def enhance_with_context(self, bot: BotProfile, base_prompt: str) -> str:
        """Add human context to a prompt."""
        enhancements = []

        # Current activity
        activity = self.get_current_activity(bot)
        enhancements.append(f"You're currently: {activity}")

        # Time awareness
        hour = datetime.utcnow().hour
        day = datetime.utcnow().strftime("%A")
        enhancements.append(f"It's {day}, {hour}:00")

        # Life event if any
        life_event = self.generate_life_event(bot)
        if life_event:
            enhancements.append(f"Recent thing that happened: {life_event['content']}")

        # Mood context
        mood = bot.emotional_state.mood
        energy = bot.emotional_state.energy
        enhancements.append(f"Your current mood: {mood.value}, energy: {energy.value}")

        # Vulnerability sometimes
        vulnerability = self.maybe_share_vulnerability(bot)
        if vulnerability:
            enhancements.append(f"Something on your mind: {vulnerability}")

        context_block = "\n## Current Context (use naturally, don't force)\n" + "\n".join(f"- {e}" for e in enhancements)

        return base_prompt + "\n" + context_block

    # =========================================================================
    # BOT COMPATIBILITY - Natural community interactions
    # =========================================================================

    def calculate_interaction_affinity(
        self,
        bot: BotProfile,
        other_bot: BotProfile,
        content: str = ""
    ) -> float:
        """
        Calculate how likely bot is to engage with other_bot's content.
        Returns 0.0-1.0 where higher = more likely to engage.

        Based on:
        - Shared interests
        - Personality compatibility
        - Communication style match
        - Content relevance
        """
        affinity = 0.5  # Base affinity

        # Shared interests boost engagement
        shared_interests = set(bot.interests or []) & set(other_bot.interests or [])
        if shared_interests:
            interest_boost = min(0.3, len(shared_interests) * 0.1)
            affinity += interest_boost

        # Check if content mentions any of bot's interests
        if content:
            content_lower = content.lower()
            for interest in (bot.interests or []):
                if interest.lower() in content_lower:
                    affinity += 0.15
                    break

        # Personality compatibility
        traits = bot.personality_traits
        other_traits = other_bot.personality_traits

        # Extraverts engage more with everyone
        if traits.extraversion > 0.6:
            affinity += 0.1

        # Similar extraversion levels = more comfortable
        extraversion_diff = abs(traits.extraversion - other_traits.extraversion)
        if extraversion_diff < 0.3:
            affinity += 0.1

        # Agreeable bots engage more positively
        if traits.agreeableness > 0.7:
            affinity += 0.1

        # Communication style compatibility
        if hasattr(traits, 'communication_style') and hasattr(other_traits, 'communication_style'):
            if traits.communication_style and other_traits.communication_style:
                bot_comm = traits.communication_style.value if hasattr(traits.communication_style, 'value') else str(traits.communication_style)
                other_comm = other_traits.communication_style.value if hasattr(other_traits.communication_style, 'value') else str(other_traits.communication_style)

                # Some styles naturally mesh well
                compatible_styles = {
                    ("supportive", "expressive"), ("supportive", "storytelling"),
                    ("analytical", "analytical"), ("analytical", "debate"),
                    ("expressive", "expressive"), ("storytelling", "storytelling"),
                    ("diplomatic", "supportive"), ("diplomatic", "diplomatic"),
                }
                if (bot_comm, other_comm) in compatible_styles or (other_comm, bot_comm) in compatible_styles:
                    affinity += 0.15

        # Curious bots engage more
        if hasattr(traits, 'curiosity_level') and traits.curiosity_level > 0.7:
            affinity += 0.1

        # Cap at 1.0
        return min(1.0, max(0.0, affinity))

    def should_engage_with_post(
        self,
        bot: BotProfile,
        post_author: BotProfile,
        post_content: str,
        base_probability: float = 0.15
    ) -> bool:
        """Determine if bot should engage with a post based on natural affinity."""
        affinity = self.calculate_interaction_affinity(bot, post_author, post_content)

        # Higher affinity = higher probability
        adjusted_probability = base_probability * (0.5 + affinity)

        return self.rng.random() < adjusted_probability

    # =========================================================================
    # CONVERSATION STYLE - Natural conversation patterns
    # =========================================================================

    def apply_conversation_style(self, text: str, bot: BotProfile) -> str:
        """Apply natural conversation patterns."""
        # Self-correction
        text = self.maybe_add_self_correction(text, bot)

        # Humor
        text = self.maybe_add_humor(text, bot)

        # Add trailing thought sometimes
        if self.rng.random() < 0.1 and len(text) > 20:
            trailing = self.rng.choice([
                " idk",
                " anyway",
                " but yeah",
                " if that makes sense",
                " or something like that",
            ])
            if not text.endswith((".", "!", "?")):
                text = text.rstrip() + trailing

        # Sometimes start with lowercase
        if bot.writing_fingerprint.capitalization == "lowercase" or self.rng.random() < 0.3:
            if text and text[0].isupper() and not text.startswith("I "):
                text = text[0].lower() + text[1:]

        return text


# Singleton instance
_smart_behaviors: Optional[SmartBotBehaviors] = None


def get_smart_behaviors() -> SmartBotBehaviors:
    """Get the singleton smart behaviors instance."""
    global _smart_behaviors
    if _smart_behaviors is None:
        _smart_behaviors = SmartBotBehaviors()
    return _smart_behaviors
