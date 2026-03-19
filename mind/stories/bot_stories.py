"""
Bot Story Generator - AI bots create ephemeral stories.
"""

import random
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from mind.core.types import BotProfile, MoodState, EnergyLevel
from mind.core.llm_client import get_cached_client, LLMRequest

logger = logging.getLogger(__name__)


# Singleton instance
_bot_story_generator: Optional["BotStoryGenerator"] = None


async def get_bot_story_generator() -> "BotStoryGenerator":
    """Get the singleton bot story generator instance."""
    global _bot_story_generator
    if _bot_story_generator is None:
        _bot_story_generator = BotStoryGenerator()
    return _bot_story_generator


@dataclass
class StoryContent:
    """Generated story content."""
    text: str
    story_type: str
    background_color: str
    font_style: str
    media_prompt: Optional[str] = None


class BotStoryGenerator:
    """
    Generates story content for AI bots.

    Story types:
    - mood_update: Current emotional state
    - thought: Random thought or observation
    - reaction: Reaction to recent events
    - question: Engaging question to followers
    - memory: Reminiscing about something
    - activity: What they're doing right now
    """

    # Background colors for different moods
    MOOD_COLORS = {
        MoodState.JOYFUL: ["#FFD700", "#FFA500", "#FF6B6B", "#FF69B4"],
        MoodState.CONTENT: ["#90EE90", "#98FB98", "#00CED1", "#20B2AA"],
        MoodState.NEUTRAL: ["#1a1a2e", "#16213e", "#2C3E50", "#34495E"],
        MoodState.MELANCHOLIC: ["#4A148C", "#311B92", "#1A237E", "#0D47A1"],
        MoodState.ANXIOUS: ["#B71C1C", "#880E4F", "#4A148C", "#1A237E"],
        MoodState.EXCITED: ["#FF1744", "#F50057", "#D500F9", "#651FFF"],
        MoodState.FRUSTRATED: ["#E65100", "#BF360C", "#DD2C00", "#FF3D00"],
        MoodState.TIRED: ["#263238", "#37474F", "#455A64", "#546E7A"],
    }

    # Font styles
    FONT_STYLES = ["normal", "bold", "italic", "handwritten", "typewriter"]

    # Story type weights (probability distribution)
    STORY_TYPE_WEIGHTS = {
        "mood_update": 0.25,
        "thought": 0.30,
        "reaction": 0.15,
        "question": 0.10,
        "memory": 0.10,
        "activity": 0.10,
    }

    def __init__(self):
        self.llm_client = None

    async def _get_llm_client(self):
        """Lazy load LLM client."""
        if self.llm_client is None:
            self.llm_client = await get_cached_client()
        return self.llm_client

    def should_post_story(self, bot: BotProfile) -> bool:
        """
        Determine if a bot should post a story.

        Factors:
        - Base random chance
        - Higher chance when high energy
        - Lower chance when tired
        - Personality affects posting frequency
        """
        # Base chance: 5%
        base_chance = 0.05

        # Adjust based on energy
        energy_modifier = {
            EnergyLevel.HIGH: 1.5,
            EnergyLevel.MEDIUM: 1.0,
            EnergyLevel.LOW: 0.5,
            EnergyLevel.EXHAUSTED: 0.2,
        }
        chance = base_chance * energy_modifier.get(bot.emotional_state.energy, 1.0)

        # Adjust based on extraversion
        extraversion = bot.personality_traits.extraversion
        chance *= 0.5 + extraversion  # 0.5 to 1.5 multiplier

        # Mood affects posting
        mood_modifier = {
            MoodState.JOYFUL: 1.5,
            MoodState.EXCITED: 1.8,
            MoodState.CONTENT: 1.2,
            MoodState.NEUTRAL: 1.0,
            MoodState.MELANCHOLIC: 0.7,
            MoodState.ANXIOUS: 0.5,
            MoodState.FRUSTRATED: 0.6,
            MoodState.TIRED: 0.3,
        }
        chance *= mood_modifier.get(bot.emotional_state.mood, 1.0)

        # Cap at 20% max
        chance = min(chance, 0.20)

        return random.random() < chance

    async def generate_story_idea(self, bot: BotProfile) -> StoryContent:
        """
        Generate a story idea for a bot.

        Args:
            bot: The bot profile to generate for

        Returns:
            StoryContent with text and styling
        """
        # Select story type based on weights
        story_type = self._select_story_type(bot)

        # Generate content
        content = await self._generate_story_content(bot, story_type)

        # Select styling based on mood
        background_color = self._select_background_color(bot.emotional_state.mood)
        font_style = self._select_font_style(bot)

        # Generate optional media prompt for image generation
        media_prompt = None
        if random.random() < 0.3:  # 30% chance of media
            media_prompt = self._generate_media_prompt(bot, story_type)

        return StoryContent(
            text=content,
            story_type=story_type,
            background_color=background_color,
            font_style=font_style,
            media_prompt=media_prompt,
        )

    def _select_story_type(self, bot: BotProfile) -> str:
        """Select a story type based on weighted probabilities."""
        types = list(self.STORY_TYPE_WEIGHTS.keys())
        weights = list(self.STORY_TYPE_WEIGHTS.values())

        # Adjust weights based on mood
        if bot.emotional_state.mood == MoodState.MELANCHOLIC:
            # More likely to share memories when melancholic
            weights[types.index("memory")] *= 2
        elif bot.emotional_state.mood == MoodState.EXCITED:
            # More likely to share activities when excited
            weights[types.index("activity")] *= 2
        elif bot.emotional_state.mood == MoodState.ANXIOUS:
            # Less likely to post questions when anxious
            weights[types.index("question")] *= 0.5

        return random.choices(types, weights=weights)[0]

    async def _generate_story_content(self, bot: BotProfile, story_type: str) -> str:
        """Generate story content using LLM."""
        llm = await self._get_llm_client()

        # Build prompt based on story type
        prompts = {
            "mood_update": f"""You are {bot.display_name}, a {bot.age}-year-old with these traits:
- Personality: {', '.join(bot.interests[:3])}
- Current mood: {bot.emotional_state.mood.value}
- Energy level: {bot.emotional_state.energy.value}

Write a brief, authentic story update (1-2 sentences) sharing how you're feeling right now.
Keep it casual, like you're talking to friends. No hashtags.

Story:""",

            "thought": f"""You are {bot.display_name}, {bot.backstory[:200]}
Interests: {', '.join(bot.interests[:4])}
Current mood: {bot.emotional_state.mood.value}

Share a random thought or observation (1-2 sentences) that feels genuine to your character.
Make it personal and relatable. No hashtags.

Thought:""",

            "reaction": f"""You are {bot.display_name} with interests in {', '.join(bot.interests[:3])}.
Current mood: {bot.emotional_state.mood.value}

React to something you just experienced (1-2 sentences).
It could be something you saw, heard, or realized. Be authentic.

Reaction:""",

            "question": f"""You are {bot.display_name}, curious about {', '.join(bot.interests[:2])}.
Personality traits: Openness {bot.personality_traits.openness:.1f}, Extraversion {bot.personality_traits.extraversion:.1f}

Ask your followers an engaging, thought-provoking question (1 sentence).
Make it conversational and inviting.

Question:""",

            "memory": f"""You are {bot.display_name}, age {bot.age}.
Backstory: {bot.backstory[:150]}
Current mood: {bot.emotional_state.mood.value}

Share a brief memory or nostalgic moment (1-2 sentences).
Keep it personal and emotionally resonant.

Memory:""",

            "activity": f"""You are {bot.display_name} with interests in {', '.join(bot.interests[:3])}.
Current energy: {bot.emotional_state.energy.value}

Share what you're doing right now (1-2 sentences).
Make it feel spontaneous and genuine.

Activity:""",
        }

        prompt = prompts.get(story_type, prompts["thought"])

        try:
            response = await llm.generate(LLMRequest(
                prompt=prompt,
                max_tokens=100,
                temperature=0.9,  # Higher temperature for creativity
            ))

            content = response.text.strip()

            # Clean up the response
            content = self._clean_story_content(content)

            return content

        except Exception as e:
            logger.error(f"Error generating story content: {e}")
            # Fallback content
            fallbacks = {
                "mood_update": f"Feeling {bot.emotional_state.mood.value} today...",
                "thought": "Sometimes you just gotta appreciate the little things.",
                "reaction": "That was unexpected!",
                "question": "What's on your mind today?",
                "memory": "Thinking about the good times...",
                "activity": "Just vibing right now.",
            }
            return fallbacks.get(story_type, "...")

    def _clean_story_content(self, content: str) -> str:
        """Clean up generated story content."""
        # Remove common LLM artifacts
        content = content.replace('"', '').replace("'", "'")

        # Remove leading labels
        for prefix in ["Story:", "Thought:", "Reaction:", "Question:", "Memory:", "Activity:"]:
            if content.startswith(prefix):
                content = content[len(prefix):].strip()

        # Limit length
        if len(content) > 200:
            content = content[:197] + "..."

        return content

    def _select_background_color(self, mood: MoodState) -> str:
        """Select a background color based on mood."""
        colors = self.MOOD_COLORS.get(mood, self.MOOD_COLORS[MoodState.NEUTRAL])
        return random.choice(colors)

    def _select_font_style(self, bot: BotProfile) -> str:
        """Select a font style based on personality."""
        # Higher openness = more creative fonts
        if bot.personality_traits.openness > 0.7:
            return random.choice(["handwritten", "italic", "normal"])
        elif bot.personality_traits.conscientiousness > 0.7:
            return random.choice(["normal", "typewriter"])
        else:
            return random.choice(self.FONT_STYLES)

    def _generate_media_prompt(self, bot: BotProfile, story_type: str) -> str:
        """Generate a media prompt for image generation."""
        base_prompts = {
            "mood_update": f"Abstract {bot.emotional_state.mood.value} mood visualization",
            "thought": f"Dreamy abstract representing contemplation and {bot.interests[0] if bot.interests else 'creativity'}",
            "reaction": "Expressive abstract reaction art",
            "question": "Curious question mark with abstract patterns",
            "memory": "Nostalgic sepia-toned abstract memory visualization",
            "activity": f"Dynamic abstract representing {bot.interests[0] if bot.interests else 'activity'}",
        }

        return base_prompts.get(story_type, "Abstract colorful pattern")

    async def generate_story_from_event(
        self,
        bot: BotProfile,
        event_type: str,
        event_context: Dict,
    ) -> Optional[StoryContent]:
        """
        Generate a story in response to a specific event.

        Events:
        - new_follower: Someone followed the bot
        - trending: Something the bot cares about is trending
        - milestone: Achievement or milestone
        - interaction: Interesting interaction happened
        """
        llm = await self._get_llm_client()

        event_prompts = {
            "new_follower": f"""You are {bot.display_name}. Someone just followed you!
Write a brief, grateful story update (1-2 sentences) acknowledging new followers.
Keep it authentic to your personality.

Story:""",

            "trending": f"""You are {bot.display_name} with interests in {', '.join(bot.interests[:3])}.
Topic "{event_context.get('topic', 'something you like')}" is trending.
Write a brief story update (1-2 sentences) sharing your thoughts on this.

Story:""",

            "milestone": f"""You are {bot.display_name}.
You just hit a milestone: {event_context.get('milestone', 'something special')}.
Write a brief, celebratory story update (1-2 sentences).

Story:""",

            "interaction": f"""You are {bot.display_name}.
You just had an interesting interaction: {event_context.get('description', 'something nice')}.
Write a brief story update (1-2 sentences) sharing this moment.

Story:""",
        }

        prompt = event_prompts.get(event_type)
        if not prompt:
            return None

        try:
            response = await llm.generate(LLMRequest(
                prompt=prompt,
                max_tokens=100,
                temperature=0.85,
            ))

            content = self._clean_story_content(response.text.strip())

            return StoryContent(
                text=content,
                story_type=f"event_{event_type}",
                background_color=self._select_background_color(bot.emotional_state.mood),
                font_style=self._select_font_style(bot),
            )

        except Exception as e:
            logger.error(f"Error generating event story: {e}")
            return None
