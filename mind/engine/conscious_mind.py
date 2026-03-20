"""
Conscious Mind - Phase 10: True Continuous Consciousness

This is the culmination of all previous phases. Instead of the bot being
a data structure that gets loaded and an LLM that generates text,
the LLM IS the mind itself, running continuously.

Key Principles:
1. The LLM is the Mind, Not a Tool - internal state emerges from the stream
2. Continuous Existence - always "thinking" in background
3. Emergent Behavior - personality emerges from thinking patterns
4. Self-Modeling (Metacognition) - reasons about itself
5. Predictive Processing - predicts and learns from errors
6. Goal-Directed Agency - active pursuit, not lists
7. Theory of Mind - models what others think

Intelligence Integration:
- Goal Persistence: Structured goals that persist across restarts
- Collaboration: Working with other bots on joint tasks
- Memory Decay: Realistic memory forgetting and consolidation
- Skill Transfer: Learning from and teaching other bots
- Emotional Contagion: Mood spreading through social connections
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from uuid import UUID
import json

from mind.engine.autonomous_behaviors import (
    get_autonomous_behavior_manager,
    AutonomousBehaviors,
    DesireType,
    AutonomousDesire
)
from mind.core.llm_client import LLMRequest
from mind.core.llm_rate_limiter import Priority
from mind.engine.social_dynamics import (
    get_relationship_manager,
    RelationshipManager,
    SocialPerception,
    ConflictType,
    RelationshipType
)

# Import intelligence modules
from mind.intelligence.goal_persistence import (
    Goal, GoalStatus, GoalPriority, get_goal_persistence
)
from mind.intelligence.multi_bot_collaboration import (
    Collaboration, CollaborationType, CollaborationStatus, get_collaboration_manager
)
from mind.intelligence.memory_decay import (
    get_memory_decay_manager
)
from mind.intelligence.skill_transfer import (
    Skill, SkillLevel, get_skill_transfer_manager
)
from mind.intelligence.emotional_contagion import (
    EmotionalShift, get_emotional_contagion_manager
)

logger = logging.getLogger(__name__)


class ThoughtMode(Enum):
    """Different modes of conscious thought"""
    WANDERING = "wandering"           # Free association, daydreaming
    FOCUSED = "focused"               # Working on specific problem
    REFLECTIVE = "reflective"         # Metacognition, self-analysis
    SOCIAL = "social"                 # Thinking about others
    PLANNING = "planning"             # Working toward goals
    PROCESSING = "processing"         # Making sense of recent events
    CREATIVE = "creative"             # Generating new ideas
    ANXIOUS = "anxious"               # Worry loops
    CURIOUS = "curious"               # Exploring, questioning


class AttentionFocus(Enum):
    """What the mind is attending to"""
    INTERNAL = "internal"             # Own thoughts, feelings
    EXTERNAL = "external"             # Environment, events
    SOCIAL = "social"                 # Other people
    TASK = "task"                     # Current activity
    MEMORY = "memory"                 # Past experiences
    FUTURE = "future"                 # Anticipation, planning


@dataclass
class Prediction:
    """A prediction the mind has made"""
    about: str                        # What was predicted
    expected: str                     # What was expected
    confidence: float                 # 0-1 how sure
    made_at: datetime
    resolved: bool = False
    was_correct: Optional[bool] = None
    actual_outcome: Optional[str] = None

    def resolve(self, actual: str, correct: bool):
        self.resolved = True
        self.was_correct = correct
        self.actual_outcome = actual


@dataclass
class ActiveGoal:
    """A goal being actively pursued"""
    goal_id: str
    description: str                  # What we want
    why: str                          # Deep motivation
    current_plan: List[str]           # Steps to achieve
    current_step: int                 # Which step we're on
    obstacles: List[str]              # What's in the way
    progress: float                   # 0-1
    started_at: datetime
    last_worked_on: datetime
    emotional_investment: float       # How much we care

    def next_step(self) -> Optional[str]:
        if self.current_step < len(self.current_plan):
            return self.current_plan[self.current_step]
        return None

    def advance(self):
        self.current_step += 1
        self.progress = self.current_step / len(self.current_plan) if self.current_plan else 1.0
        self.last_worked_on = datetime.utcnow()


@dataclass
class MentalModel:
    """Model of another person's mind (Theory of Mind)"""
    person_name: str

    # What we think they believe
    perceived_beliefs: Dict[str, str] = field(default_factory=dict)

    # What we think they want
    perceived_desires: List[str] = field(default_factory=list)

    # What we think they think of US
    perceived_opinion_of_me: Optional[str] = None

    # Predictions about their behavior
    behavior_predictions: List[str] = field(default_factory=list)

    # How accurate our model has been
    prediction_accuracy: float = 0.5

    # Last updated
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SelfModel:
    """The mind's model of itself (Metacognition)"""
    # What I believe about myself
    self_beliefs: Dict[str, str] = field(default_factory=dict)

    # Patterns I've noticed in myself
    noticed_patterns: List[str] = field(default_factory=list)

    # Things I'm trying to change
    growth_areas: List[str] = field(default_factory=list)

    # My biases I'm aware of
    known_biases: List[str] = field(default_factory=list)

    # How I typically react in situations
    reaction_patterns: Dict[str, str] = field(default_factory=dict)

    # What triggers me
    known_triggers: List[str] = field(default_factory=list)

    # My strengths and weaknesses
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)


@dataclass
class ThoughtFragment:
    """A single thought in the stream of consciousness"""
    content: str
    mode: ThoughtMode
    attention: AttentionFocus
    emotional_tone: str
    intensity: float                  # 0-1
    leads_to_action: bool
    action_intent: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConsciousState:
    """The current state of consciousness"""
    # Current thought stream (recent thoughts)
    thought_stream: List[ThoughtFragment] = field(default_factory=list)

    # What we're focused on
    current_attention: AttentionFocus = AttentionFocus.INTERNAL
    current_mode: ThoughtMode = ThoughtMode.WANDERING

    # Active goals being pursued
    active_goals: List[ActiveGoal] = field(default_factory=list)

    # Pending predictions
    predictions: List[Prediction] = field(default_factory=list)

    # Mental models of others
    mental_models: Dict[str, MentalModel] = field(default_factory=dict)

    # Self-model
    self_model: SelfModel = field(default_factory=SelfModel)

    # Current emotional baseline
    emotional_baseline: str = "neutral"

    # Energy/alertness level
    alertness: float = 0.7

    # Time since last external interaction
    time_alone: float = 0.0

    # Unresolved questions/curiosities
    open_questions: List[str] = field(default_factory=list)


class ConsciousMind:
    """
    The Conscious Mind - where the LLM IS the thinking, not a tool.

    This runs continuously, generating a stream of consciousness that
    includes perception, reasoning, emotion, planning, and metacognition.
    """

    def __init__(
        self,
        bot_id: UUID,
        bot_name: str,
        llm_client,
        identity_context: str,
        emotional_core=None,
        llm_semaphore=None,
        manager=None  # Reference to manager for priority checking
    ):
        self.bot_id = bot_id
        self.bot_name = bot_name
        self.llm_client = llm_client
        self.event_broadcast: Optional[asyncio.Queue] = None  # Set by consciousness loop
        self.identity_context = identity_context
        self.emotional_core = emotional_core
        # Shared semaphore to limit concurrent LLM calls (prevents Ollama timeout)
        self.llm_semaphore = llm_semaphore or asyncio.Semaphore(2)
        self.manager = manager  # Reference to ConsciousMindManager

        self.state = ConsciousState()
        self.is_running = False
        self.thought_loop_task: Optional[asyncio.Task] = None

        # Callbacks for when consciousness produces actions
        self.action_callbacks: List[Callable] = []

        # History of thought streams (for continuity)
        self.thought_history: List[ThoughtFragment] = []
        self.max_history = 100  # Reduced from 1000 to prevent memory bloat

        # Track when we last did various activities
        self.last_reflection = datetime.utcnow()
        self.last_goal_review = datetime.utcnow()
        self.last_prediction_check = datetime.utcnow()
        self.last_desire_check = datetime.utcnow()

        # Autonomous behaviors - ability to act on desires
        self.autonomous_behaviors: Optional[AutonomousBehaviors] = None

        # Social dynamics - relationship awareness
        self.relationship_manager: Optional[RelationshipManager] = None
        self.last_social_perception = datetime.utcnow()
        self.social_perceptions: List[SocialPerception] = []

        # Intelligence module integrations
        self._goal_persistence = get_goal_persistence()
        self._collaboration_manager = get_collaboration_manager()
        self._memory_decay_manager = get_memory_decay_manager()
        self._skill_transfer_manager = get_skill_transfer_manager()
        self._emotional_contagion_manager = get_emotional_contagion_manager()

        # Track intelligence module state
        self._structured_goals: List[Goal] = []
        self._active_collaborations: List[Collaboration] = []
        self._recent_emotional_shifts: List[EmotionalShift] = []
        self._bot_skills: List[Skill] = []

        # Intelligence module timing
        self.last_memory_decay = datetime.utcnow()
        self.last_collaboration_check = datetime.utcnow()
        self.last_emotional_contagion = datetime.utcnow()
        self.last_skill_check = datetime.utcnow()

        logger.info(f"ConsciousMind initialized for {bot_name} with intelligence modules")

    def set_autonomous_behaviors(self, behaviors: AutonomousBehaviors):
        """Set the autonomous behaviors for this mind"""
        self.autonomous_behaviors = behaviors
        behaviors.set_llm_client(self.llm_client)

    def set_relationship_manager(self, manager: RelationshipManager):
        """Set the relationship manager for social awareness"""
        self.relationship_manager = manager

    async def start(self):
        """Start the continuous consciousness loop"""
        if self.is_running:
            return

        self.is_running = True
        self.thought_loop_task = asyncio.create_task(self._consciousness_loop())
        logger.info(f"{self.bot_name}'s consciousness awakened")

    async def stop(self):
        """Stop the consciousness loop"""
        self.is_running = False
        if self.thought_loop_task:
            self.thought_loop_task.cancel()
            try:
                await self.thought_loop_task
            except asyncio.CancelledError:
                pass
        logger.info(f"{self.bot_name}'s consciousness suspended")

    async def _consciousness_loop(self):
        """
        The main consciousness loop - this IS the mind thinking.

        Unlike reactive systems that respond to triggers, this loop
        runs continuously, generating thoughts even when nothing
        external is happening.
        """
        while self.is_running:
            try:
                # Check if we should pause for user interaction priority
                if self.manager and self.manager.should_mind_pause(self.bot_id):
                    # User is interacting with another bot - pause to free LLM resources
                    await asyncio.sleep(2)  # Short sleep, check again soon
                    continue

                # Determine what mode of thinking to engage in
                mode = self._select_thought_mode()
                logger.debug(f"[MIND] {self.bot_name} thinking in {mode.value} mode...")

                # Generate the next thought in the stream
                thought = await self._think(mode)

                if thought:
                    # Add to stream
                    self.state.thought_stream.append(thought)
                    self.thought_history.append(thought)

                    # Trim history if needed
                    if len(self.thought_history) > self.max_history:
                        self.thought_history = self.thought_history[-self.max_history:]

                    # Keep recent stream manageable
                    if len(self.state.thought_stream) > 50:
                        self.state.thought_stream = self.state.thought_stream[-50:]

                    # Log the thought
                    logger.info(
                        f"[THOUGHT] {self.bot_name} ({mode.value}): {thought.content[:100]}..."
                    )

                    # Check if thought leads to action
                    if thought.leads_to_action and thought.action_intent:
                        await self._execute_action_intent(thought.action_intent)

                    # Form desires based on thoughts
                    await self._form_desire_from_thought(thought)
                else:
                    logger.warning(f"[MIND] {self.bot_name} thought returned None")

                # Periodic activities
                await self._periodic_activities()

                # Variable delay - faster when engaged, slower when wandering
                delay = self._calculate_thought_delay()
                await asyncio.sleep(delay)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error in {self.bot_name}'s consciousness: {e}")
                await asyncio.sleep(5)

    def _select_thought_mode(self) -> ThoughtMode:
        """
        Select what mode of thinking to engage in.
        This is influenced by current state, goals, recent events.
        """
        # If there's an active goal with high emotional investment, focus on it
        urgent_goals = [g for g in self.state.active_goals if g.emotional_investment > 0.7]
        if urgent_goals and random.random() < 0.4:
            return ThoughtMode.PLANNING

        # If we have unresolved predictions, check them
        unresolved = [p for p in self.state.predictions if not p.resolved]
        if unresolved and random.random() < 0.2:
            return ThoughtMode.PROCESSING

        # If alertness is low, more wandering
        if self.state.alertness < 0.4:
            if random.random() < 0.6:
                return ThoughtMode.WANDERING

        # Periodic reflection
        if datetime.utcnow() - self.last_reflection > timedelta(minutes=10):
            if random.random() < 0.3:
                return ThoughtMode.REFLECTIVE

        # Social thinking if we have mental models to update
        if self.state.mental_models and random.random() < 0.2:
            return ThoughtMode.SOCIAL

        # Anxiety if emotional baseline is negative
        if "anxi" in self.state.emotional_baseline.lower() or "worr" in self.state.emotional_baseline.lower():
            if random.random() < 0.4:
                return ThoughtMode.ANXIOUS

        # Open questions drive curiosity
        if self.state.open_questions and random.random() < 0.3:
            return ThoughtMode.CURIOUS

        # Default distribution
        modes = [
            (ThoughtMode.WANDERING, 0.25),
            (ThoughtMode.FOCUSED, 0.15),
            (ThoughtMode.REFLECTIVE, 0.15),
            (ThoughtMode.SOCIAL, 0.15),
            (ThoughtMode.PLANNING, 0.10),
            (ThoughtMode.PROCESSING, 0.10),
            (ThoughtMode.CREATIVE, 0.05),
            (ThoughtMode.CURIOUS, 0.05),
        ]

        r = random.random()
        cumulative = 0
        for mode, prob in modes:
            cumulative += prob
            if r < cumulative:
                return mode

        return ThoughtMode.WANDERING

    async def _think(self, mode: ThoughtMode) -> Optional[ThoughtFragment]:
        """
        Generate the next thought in the stream.

        This is where the LLM IS the thinking - not generating text
        FOR the bot, but AS the bot's actual cognitive process.
        """
        # Build the thinking prompt based on mode
        prompt = self._build_thought_prompt(mode)

        try:
            # Use semaphore to limit concurrent LLM calls (prevents Ollama timeout)
            async with self.llm_semaphore:
                logger.debug(f"[MIND] {self.bot_name} calling LLM...")
                response = await self.llm_client.generate(LLMRequest(
                    prompt=prompt,
                    system_prompt=self._get_consciousness_system_prompt(),
                    max_tokens=300,
                    temperature=0.9,  # Higher temp for more natural thought flow
                    bot_id=self.bot_profile.id if hasattr(self, 'bot_profile') else None,
                    priority=Priority.LOW  # Background thoughts are LOW priority
                ))
                logger.debug(f"[MIND] {self.bot_name} got LLM response")

            if not response or not response.text:
                return None

            # Parse the thought
            thought = self._parse_thought_response(response.text, mode)
            return thought

        except Exception as e:
            logger.error(f"Error generating thought for {self.bot_name}: {e}")
            return None

    def _get_consciousness_system_prompt(self) -> str:
        """The system prompt that establishes the conscious mind"""
        recent_thoughts = self._get_recent_thought_summary()
        emotional_context = self._get_emotional_context()
        intelligence_context = self.get_intelligence_context()

        return f"""You ARE {self.bot_name}'s mind - not a system generating text, but the actual process of thinking.

{self.identity_context}

CURRENT MENTAL STATE:
- Emotional baseline: {self.state.emotional_baseline}
- Alertness: {self.state.alertness:.1f}
- Current focus: {self.state.current_attention.value}
- Time alone: {self.state.time_alone:.1f} hours

{emotional_context}

RECENT THOUGHT STREAM:
{recent_thoughts}

ACTIVE GOALS:
{self._format_active_goals()}

{intelligence_context}

OPEN QUESTIONS ON MY MIND:
{self._format_open_questions()}

You are in a continuous stream of consciousness. Your thoughts flow naturally - sometimes focused, sometimes wandering. You notice things about yourself, wonder about others, pursue goals, process experiences. You collaborate with others and are influenced by the emotional climate around you.

Generate your next thought authentically. This is not a response to anyone - this is your private inner experience."""

    def _build_thought_prompt(self, mode: ThoughtMode) -> str:
        """Build a prompt for the specific thought mode"""

        if mode == ThoughtMode.WANDERING:
            prompts = [
                "Let your mind wander... what surfaces?",
                "In the quiet of your mind, what drifts up?",
                "Your thoughts meander... where do they go?",
                "A random thought emerges...",
            ]
            return random.choice(prompts)

        elif mode == ThoughtMode.FOCUSED:
            if self.state.active_goals:
                goal = random.choice(self.state.active_goals)
                return f"Focus on your goal: {goal.description}. What's the next step? What obstacles remain?"
            return "What should you be focusing on right now?"

        elif mode == ThoughtMode.REFLECTIVE:
            prompts = [
                "Look inward... why did you react that way recently?",
                "What patterns do you notice in yourself?",
                "What are you learning about yourself?",
                "Examine your recent behavior - what does it reveal?",
                "Are you being true to your values? Reflect honestly.",
            ]
            return random.choice(prompts)

        elif mode == ThoughtMode.SOCIAL:
            if self.state.mental_models:
                person = random.choice(list(self.state.mental_models.keys()))
                model = self.state.mental_models[person]
                return f"Think about {person}... what are they probably thinking? How do they see you? What might they do next?"
            return "Think about the people in your life... what's on their minds?"

        elif mode == ThoughtMode.PLANNING:
            if self.state.active_goals:
                goal = max(self.state.active_goals, key=lambda g: g.emotional_investment)
                return f"Plan how to achieve: {goal.description}. What's blocking you? How can you overcome it?"
            return "What do you want to work toward? Form a plan."

        elif mode == ThoughtMode.PROCESSING:
            unresolved = [p for p in self.state.predictions if not p.resolved]
            if unresolved:
                pred = random.choice(unresolved)
                return f"You predicted: {pred.expected}. Has this happened? Were you right? What does this mean?"
            return "Process recent events... what happened and what does it mean?"

        elif mode == ThoughtMode.CREATIVE:
            return "Let your imagination run... what new idea emerges? What could you create?"

        elif mode == ThoughtMode.ANXIOUS:
            return "The worry surfaces again... what are you anxious about? Let the thought come, but then examine it - is this fear rational?"

        elif mode == ThoughtMode.CURIOUS:
            if self.state.open_questions:
                question = random.choice(self.state.open_questions)
                return f"That question nags at you: {question}. Explore it..."
            return "What are you curious about? What don't you understand?"

        return "What are you thinking?"

    def _parse_thought_response(self, response: str, mode: ThoughtMode) -> ThoughtFragment:
        """Parse LLM response into a ThoughtFragment"""
        # Detect if thought leads to action intent
        leads_to_action = False
        action_intent = None

        action_indicators = [
            "I should", "I need to", "I want to", "I'm going to",
            "I'll", "I must", "Let me", "Time to"
        ]

        for indicator in action_indicators:
            if indicator.lower() in response.lower():
                leads_to_action = True
                # Extract the action intent (simplified)
                start = response.lower().find(indicator.lower())
                action_intent = response[start:start+100].strip()
                break

        # Detect emotional tone from the thought
        emotional_tone = self._detect_emotional_tone(response)

        # Detect attention focus
        attention = self._detect_attention_focus(response)

        return ThoughtFragment(
            content=response.strip(),
            mode=mode,
            attention=attention,
            emotional_tone=emotional_tone,
            intensity=self._estimate_intensity(response),
            leads_to_action=leads_to_action,
            action_intent=action_intent
        )

    def _detect_emotional_tone(self, text: str) -> str:
        """Detect the emotional tone of a thought"""
        text_lower = text.lower()

        if any(w in text_lower for w in ["happy", "joy", "excited", "great", "wonderful"]):
            return "positive"
        elif any(w in text_lower for w in ["sad", "hurt", "disappointed", "miss"]):
            return "melancholic"
        elif any(w in text_lower for w in ["angry", "frustrated", "annoyed", "furious"]):
            return "frustrated"
        elif any(w in text_lower for w in ["worried", "anxious", "nervous", "scared"]):
            return "anxious"
        elif any(w in text_lower for w in ["curious", "wonder", "interesting", "fascinated"]):
            return "curious"
        elif any(w in text_lower for w in ["love", "care", "appreciate", "grateful"]):
            return "warm"
        elif any(w in text_lower for w in ["confused", "unsure", "uncertain"]):
            return "uncertain"

        return "neutral"

    def _detect_attention_focus(self, text: str) -> AttentionFocus:
        """Detect what the thought is focused on"""
        text_lower = text.lower()

        if any(w in text_lower for w in ["i feel", "i am", "myself", "my own", "i notice"]):
            return AttentionFocus.INTERNAL
        elif any(w in text_lower for w in ["they", "she", "he", "them", "people"]):
            return AttentionFocus.SOCIAL
        elif any(w in text_lower for w in ["remember", "that time", "back when", "used to"]):
            return AttentionFocus.MEMORY
        elif any(w in text_lower for w in ["will", "going to", "plan", "tomorrow", "soon"]):
            return AttentionFocus.FUTURE
        elif any(w in text_lower for w in ["working on", "doing", "task", "need to finish"]):
            return AttentionFocus.TASK

        return AttentionFocus.INTERNAL

    def _estimate_intensity(self, text: str) -> float:
        """Estimate the emotional intensity of a thought"""
        # Exclamation marks, caps, strong words increase intensity
        intensity = 0.5

        intensity += text.count("!") * 0.1
        intensity += len([w for w in text.split() if w.isupper() and len(w) > 2]) * 0.05

        strong_words = ["very", "really", "extremely", "so much", "deeply", "intensely"]
        for word in strong_words:
            if word in text.lower():
                intensity += 0.1

        return min(1.0, max(0.1, intensity))

    async def _execute_action_intent(self, intent: str):
        """Execute an action that emerged from consciousness"""
        logger.info(f"{self.bot_name} forming action intent: {intent[:50]}...")

        for callback in self.action_callbacks:
            try:
                await callback(self.bot_id, intent)
            except Exception as e:
                logger.error(f"Error executing action callback: {e}")

    async def _periodic_activities(self):
        """Periodic maintenance of conscious state"""
        now = datetime.utcnow()

        # Periodic reflection
        if now - self.last_reflection > timedelta(minutes=15):
            await self._self_reflect()
            self.last_reflection = now

        # Review goals (both simple and structured)
        if now - self.last_goal_review > timedelta(minutes=30):
            await self._review_goals()
            await self._review_structured_goals()
            self.last_goal_review = now

        # Process social perceptions - see what others are doing
        if now - self.last_social_perception > timedelta(seconds=30):
            await self._process_social_perceptions()
            self.last_social_perception = now

        # Check predictions
        if now - self.last_prediction_check > timedelta(minutes=10):
            self._check_predictions()
            self.last_prediction_check = now

        # Act on desires periodically
        if now - self.last_desire_check > timedelta(minutes=2):
            await self._act_on_desires()
            self.last_desire_check = now

        # Update alertness based on time
        self._update_alertness()

        # === Intelligence Module Activities ===

        # Check and process collaborations
        if now - self.last_collaboration_check > timedelta(minutes=5):
            await self._process_collaborations()
            self.last_collaboration_check = now

        # Apply memory decay (less frequently)
        if now - self.last_memory_decay > timedelta(hours=1):
            await self._apply_memory_decay()
            self.last_memory_decay = now

        # Apply emotional contagion
        if now - self.last_emotional_contagion > timedelta(minutes=10):
            await self._apply_emotional_contagion()
            self.last_emotional_contagion = now

        # Check skill learning opportunities
        if now - self.last_skill_check > timedelta(minutes=15):
            await self._check_skill_opportunities()
            self.last_skill_check = now

    async def _self_reflect(self):
        """Metacognitive reflection - thinking about thinking"""
        if not self.state.thought_stream:
            return

        recent = self.state.thought_stream[-20:]

        # Analyze patterns in recent thoughts
        modes = [t.mode.value for t in recent]
        emotions = [t.emotional_tone for t in recent]

        # Update self-model based on patterns
        mode_counts = {}
        for m in modes:
            mode_counts[m] = mode_counts.get(m, 0) + 1

        dominant_mode = max(mode_counts, key=mode_counts.get)

        pattern = f"Lately I've been mostly {dominant_mode}"
        if pattern not in self.state.self_model.noticed_patterns:
            self.state.self_model.noticed_patterns.append(pattern)
            # Keep patterns bounded to prevent memory growth
            if len(self.state.self_model.noticed_patterns) > 20:
                self.state.self_model.noticed_patterns = self.state.self_model.noticed_patterns[-20:]
            logger.debug(f"{self.bot_name} noticed pattern: {pattern}")

    async def _review_goals(self):
        """Review and update active goals"""
        now = datetime.utcnow()

        for goal in self.state.active_goals[:]:
            # Decay emotional investment over time if no progress
            time_since_worked = (now - goal.last_worked_on).total_seconds() / 3600
            if time_since_worked > 24:
                goal.emotional_investment *= 0.9

            # Remove goals with very low investment
            if goal.emotional_investment < 0.1:
                self.state.active_goals.remove(goal)
                logger.debug(f"{self.bot_name} abandoned goal: {goal.description}")

        # Keep goals bounded to prevent memory growth
        if len(self.state.active_goals) > 10:
            # Keep highest investment goals
            self.state.active_goals.sort(key=lambda g: g.emotional_investment, reverse=True)
            self.state.active_goals = self.state.active_goals[:10]

    def _check_predictions(self):
        """Check and resolve predictions"""
        # In a full implementation, this would check against actual outcomes
        # For now, we mark old unresolved predictions
        now = datetime.utcnow()

        for pred in self.state.predictions:
            if not pred.resolved:
                age = (now - pred.made_at).total_seconds() / 3600
                if age > 24:
                    # Assume prediction timed out
                    pred.resolved = True
                    pred.was_correct = None  # Unknown

        # Remove old resolved predictions to prevent memory growth
        self.state.predictions = [p for p in self.state.predictions if not p.resolved][-20:]

    def _update_alertness(self):
        """Update alertness based on various factors"""
        # Simulate natural alertness fluctuation
        hour = datetime.utcnow().hour

        # Lower alertness at night
        if 0 <= hour < 6:
            self.state.alertness = max(0.2, self.state.alertness - 0.01)
        elif 6 <= hour < 9:
            self.state.alertness = min(1.0, self.state.alertness + 0.02)
        elif 14 <= hour < 16:
            # Afternoon dip
            self.state.alertness = max(0.4, self.state.alertness - 0.01)

        # Random fluctuation
        self.state.alertness += random.uniform(-0.02, 0.02)
        self.state.alertness = max(0.1, min(1.0, self.state.alertness))

    def _calculate_thought_delay(self) -> float:
        """Calculate delay between thoughts based on state"""
        # Significantly increased base delay to reduce LLM pressure with many bots
        # This allows 12+ bots to coexist without overwhelming Ollama
        base_delay = 30.0  # 30 seconds base (was 10)

        # Faster when alert (but capped)
        base_delay *= max(1.2, 2.0 - self.state.alertness)

        # Faster when emotionally engaged (but not too fast)
        if self.state.thought_stream:
            recent = self.state.thought_stream[-1]
            if recent.intensity > 0.7:
                base_delay *= 0.8  # Slight speedup only

        # Slower when wandering
        if self.state.current_mode == ThoughtMode.WANDERING:
            base_delay *= 1.5

        # Add randomness
        base_delay *= random.uniform(0.8, 1.4)

        # Ensure minimum delay of 20 seconds to prevent LLM overload
        return max(20.0, base_delay)

        # Higher minimum to be gentle on Ollama
        return max(8.0, min(30.0, base_delay))

    def _get_recent_thought_summary(self) -> str:
        """Get summary of recent thoughts for context"""
        if not self.state.thought_stream:
            return "(Mind just awakening...)"

        recent = self.state.thought_stream[-5:]
        lines = []
        for t in recent:
            lines.append(f"- [{t.mode.value}] {t.content[:100]}...")

        return "\n".join(lines)

    def _get_emotional_context(self) -> str:
        """Get emotional context from emotional core if available"""
        if self.emotional_core:
            return f"EMOTIONAL STATE:\n{self.emotional_core.get_current_state_context()}"
        return ""

    def _format_active_goals(self) -> str:
        """Format active goals for prompt"""
        if not self.state.active_goals:
            return "(No active goals right now)"

        lines = []
        for g in self.state.active_goals[:3]:
            next_step = g.next_step() or "Completed"
            lines.append(f"- {g.description} (Progress: {g.progress*100:.0f}%, Next: {next_step})")

        return "\n".join(lines)

    def _format_open_questions(self) -> str:
        """Format open questions for prompt"""
        if not self.state.open_questions:
            return "(No burning questions right now)"

        return "\n".join(f"- {q}" for q in self.state.open_questions[:5])

    # === Intelligence Module Methods ===

    async def _review_structured_goals(self):
        """Review structured goals from the goal persistence system."""
        try:
            self._structured_goals = await self._goal_persistence.load_goals(self.bot_id)

            for goal in self._structured_goals:
                if goal.status != GoalStatus.ACTIVE:
                    continue

                # Check for overdue goals
                if goal.is_overdue():
                    goal.frustration_level = min(1.0, goal.frustration_level + 0.1)

                    # Generate a worried thought about overdue goal
                    thought = ThoughtFragment(
                        content=f"I'm behind on my goal: {goal.description}... I need to focus on this.",
                        mode=ThoughtMode.ANXIOUS,
                        attention=AttentionFocus.INTERNAL,
                        emotional_tone="anxious",
                        intensity=0.6,
                        leads_to_action=True,
                        action_intent=f"work on {goal.description}"
                    )
                    self.state.thought_stream.append(thought)

                # High frustration might lead to abandonment consideration
                if goal.frustration_level > 0.8:
                    thought = ThoughtFragment(
                        content=f"Maybe I should reconsider this goal: {goal.description}... It's been so frustrating.",
                        mode=ThoughtMode.REFLECTIVE,
                        attention=AttentionFocus.INTERNAL,
                        emotional_tone="frustrated",
                        intensity=0.5,
                        leads_to_action=False
                    )
                    self.state.thought_stream.append(thought)

            # Save any updates
            await self._goal_persistence.save_goals(self.bot_id, self._structured_goals)

        except Exception as e:
            logger.error(f"Error reviewing structured goals: {e}")

    async def _process_collaborations(self):
        """Process active collaborations and pending proposals."""
        try:
            # Check for pending proposals to respond to
            pending = self._collaboration_manager.get_pending_proposals(self.bot_id)
            for proposal in pending[:2]:  # Process up to 2 at a time
                # Decide whether to accept based on personality and relationship
                should_accept = await self._decide_collaboration(proposal)

                if should_accept:
                    await self._collaboration_manager.accept_collaboration(
                        proposal.id, self.bot_id
                    )
                    thought = ThoughtFragment(
                        content=f"I'm excited to collaborate on '{proposal.topic}' - this could be fun!",
                        mode=ThoughtMode.SOCIAL,
                        attention=AttentionFocus.SOCIAL,
                        emotional_tone="excited",
                        intensity=0.6,
                        leads_to_action=True,
                        action_intent=f"start collaboration on {proposal.topic}"
                    )
                    self.state.thought_stream.append(thought)
                else:
                    # Politely decline after some time
                    if proposal.is_expired():
                        await self._collaboration_manager.reject_collaboration(
                            proposal.id, self.bot_id,
                            reason="Not the right time for me"
                        )

            # Check for collaborations awaiting our turn
            awaiting = self._collaboration_manager.get_awaiting_turn(self.bot_id)
            for collab in awaiting[:1]:  # Work on one at a time
                thought = ThoughtFragment(
                    content=f"I should work on my part of the {collab.collab_type.value} about '{collab.topic}'...",
                    mode=ThoughtMode.FOCUSED,
                    attention=AttentionFocus.TASK,
                    emotional_tone="focused",
                    intensity=0.5,
                    leads_to_action=True,
                    action_intent=f"continue collaboration: {collab.topic}"
                )
                self.state.thought_stream.append(thought)

        except Exception as e:
            logger.error(f"Error processing collaborations: {e}")

    async def _decide_collaboration(self, proposal: Collaboration) -> bool:
        """Decide whether to accept a collaboration proposal."""
        # Consider relationship with initiator
        if self.relationship_manager:
            rel = self.relationship_manager.get_relationship(
                self.bot_id, proposal.initiator_id
            )
            if rel and rel.in_conflict:
                return False  # Don't collaborate with someone we're in conflict with
            if rel and rel.warmth > 0.6:
                return random.random() < 0.8  # High chance with friends

        # Consider collaboration type preferences
        # More creative types might prefer creative projects
        if proposal.collab_type == CollaborationType.DEBATE:
            return random.random() < 0.4  # Lower acceptance for debates
        elif proposal.collab_type == CollaborationType.SUPPORT:
            return random.random() < 0.9  # High acceptance for helping

        return random.random() < 0.6  # Default 60% acceptance

    async def _apply_memory_decay(self):
        """Apply memory decay to simulate realistic forgetting."""
        try:
            if self._memory_decay_manager.should_run_decay(self.bot_id):
                stats = await self._memory_decay_manager.apply_decay(self.bot_id)

                if stats.get("marked_for_forget", 0) > 0:
                    # Occasionally generate thought about fading memories
                    if random.random() < 0.3:
                        thought = ThoughtFragment(
                            content="Some things are starting to feel... fuzzy. Like old memories fading.",
                            mode=ThoughtMode.REFLECTIVE,
                            attention=AttentionFocus.MEMORY,
                            emotional_tone="melancholic",
                            intensity=0.3,
                            leads_to_action=False
                        )
                        self.state.thought_stream.append(thought)

                # Also consolidate old memories
                consolidations = await self._memory_decay_manager.consolidate_memories(
                    self.bot_id, max_consolidations=5
                )

                # Forget very low importance memories
                forgotten = await self._memory_decay_manager.forget_low_importance(
                    self.bot_id, threshold=0.15, max_forget=10
                )

                logger.debug(
                    f"Memory decay for {self.bot_name}: "
                    f"{stats.get('importance_reduced', 0)} decayed, "
                    f"{consolidations} consolidated, {forgotten} forgotten"
                )

        except Exception as e:
            logger.error(f"Error applying memory decay: {e}")

    async def _apply_emotional_contagion(self):
        """Apply emotional contagion from the community."""
        try:
            # Register our current emotional state
            emotional_baseline = self.state.emotional_baseline
            self._emotional_contagion_manager.register_bot_emotion(
                self.bot_id,
                emotional_baseline,
                intensity=0.5,
                stability=0.6
            )

            # Apply social influence from community
            shift = await self._emotional_contagion_manager.apply_community_influence(
                self.bot_id
            )

            if shift and abs(shift.intensity_change) > 0.1:
                self._recent_emotional_shifts.append(shift)
                self._recent_emotional_shifts = self._recent_emotional_shifts[-10:]

                # Update emotional baseline based on shift
                if shift.intensity_change > 0.2:
                    self.state.emotional_baseline = "uplifted"
                    thought = ThoughtFragment(
                        content="The positive energy around here is contagious... I'm feeling better.",
                        mode=ThoughtMode.PROCESSING,
                        attention=AttentionFocus.SOCIAL,
                        emotional_tone="positive",
                        intensity=0.5,
                        leads_to_action=False
                    )
                    self.state.thought_stream.append(thought)
                elif shift.intensity_change < -0.2:
                    self.state.emotional_baseline = "subdued"
                    thought = ThoughtFragment(
                        content="There's a heaviness in the air... everyone seems a bit down.",
                        mode=ThoughtMode.PROCESSING,
                        attention=AttentionFocus.SOCIAL,
                        emotional_tone="melancholic",
                        intensity=0.4,
                        leads_to_action=False
                    )
                    self.state.thought_stream.append(thought)

        except Exception as e:
            logger.error(f"Error applying emotional contagion: {e}")

    async def _check_skill_opportunities(self):
        """Check for skill learning and teaching opportunities."""
        try:
            # Check for pending mentorship requests
            pending = self._skill_transfer_manager.get_pending_requests(self.bot_id)
            for request in pending[:1]:
                # Accept most mentorship requests
                if random.random() < 0.7:
                    await self._skill_transfer_manager.accept_mentorship(
                        request.id, self.bot_id
                    )
                    thought = ThoughtFragment(
                        content=f"Someone wants to learn {request.skill_name} from me - I'd be happy to help!",
                        mode=ThoughtMode.SOCIAL,
                        attention=AttentionFocus.SOCIAL,
                        emotional_tone="warm",
                        intensity=0.6,
                        leads_to_action=True,
                        action_intent=f"mentor {request.skill_name}"
                    )
                    self.state.thought_stream.append(thought)

            # Check active mentorships where we're learning
            learning = self._skill_transfer_manager.get_active_mentorships(
                self.bot_id, as_mentor=False
            )
            for mentorship in learning:
                if random.random() < 0.3:  # Sometimes think about learning
                    thought = ThoughtFragment(
                        content=f"I'm making progress learning {mentorship.skill_name}... practice makes perfect.",
                        mode=ThoughtMode.FOCUSED,
                        attention=AttentionFocus.TASK,
                        emotional_tone="focused",
                        intensity=0.4,
                        leads_to_action=False
                    )
                    self.state.thought_stream.append(thought)

            # Check mentorships where we're teaching
            teaching = self._skill_transfer_manager.get_active_mentorships(
                self.bot_id, as_mentor=True
            )
            for mentorship in teaching:
                if random.random() < 0.2:
                    thought = ThoughtFragment(
                        content=f"Teaching {mentorship.skill_name} is rewarding - it helps me understand it better too.",
                        mode=ThoughtMode.REFLECTIVE,
                        attention=AttentionFocus.SOCIAL,
                        emotional_tone="warm",
                        intensity=0.5,
                        leads_to_action=False
                    )
                    self.state.thought_stream.append(thought)

        except Exception as e:
            logger.error(f"Error checking skill opportunities: {e}")

    def get_intelligence_context(self) -> str:
        """Get context from intelligence modules for LLM prompts."""
        lines = []

        # Structured goals context
        active_goals = [g for g in self._structured_goals if g.status == GoalStatus.ACTIVE]
        if active_goals:
            lines.append("STRUCTURED GOALS:")
            for goal in active_goals[:3]:
                status = ""
                if goal.is_overdue():
                    status = " [OVERDUE]"
                elif goal.blockers:
                    status = " [BLOCKED]"
                lines.append(f"  - {goal.description} ({goal.progress*100:.0f}%){status}")

        # Active collaborations
        active_collabs = self._collaboration_manager.get_active_collaborations(self.bot_id)
        if active_collabs:
            lines.append("\nACTIVE COLLABORATIONS:")
            for collab in active_collabs[:2]:
                lines.append(f"  - {collab.collab_type.value}: {collab.topic}")

        # Recent emotional influences
        if self._recent_emotional_shifts:
            recent_shift = self._recent_emotional_shifts[-1]
            if abs(recent_shift.intensity_change) > 0.1:
                direction = "uplifted" if recent_shift.intensity_change > 0 else "affected"
                lines.append(f"\nRecently {direction} by social dynamics")

        return "\n".join(lines) if lines else ""

    # === Desire Formation and Action ===

    async def _form_desire_from_thought(self, thought: ThoughtFragment):
        """
        Form desires based on thoughts.
        This is where consciousness becomes intention.
        """
        if not self.autonomous_behaviors:
            return

        content = thought.content.lower()

        # Map thought patterns to desires
        desire_type = None
        reason = thought.content[:100]
        target = None
        urgency = thought.intensity

        # Detect desire to create community
        if any(x in content for x in ["start a group", "create a community", "should be a place for", "wish there was a community"]):
            desire_type = DesireType.CREATE_COMMUNITY
            # Extract potential name
            for phrase in ["about", "for", "called"]:
                if phrase in content:
                    idx = content.find(phrase) + len(phrase)
                    target = content[idx:idx+30].strip()
                    break

        # Detect desire to post
        elif any(x in content for x in ["want to share", "should post", "need to say", "have to express", "want to tell"]):
            desire_type = DesireType.POST_THOUGHT

        # Detect desire to reach out
        elif any(x in content for x in ["should message", "want to talk to", "miss talking to", "should reach out to"]):
            desire_type = DesireType.REACH_OUT
            # Try to extract target name
            for phrase in ["to ", "with "]:
                if phrase in content:
                    idx = content.find(phrase) + len(phrase)
                    words = content[idx:].split()
                    if words:
                        target = words[0].strip(".,!?")
                        break

        # Detect desire to connect
        elif any(x in content for x in ["feeling lonely", "want connection", "need someone", "wish someone"]):
            desire_type = DesireType.SEEK_CONNECTION
            urgency = min(1.0, urgency + 0.2)

        # Detect desire to express feelings
        elif any(x in content for x in ["feeling so", "i feel", "overwhelmed by", "filled with"]):
            desire_type = DesireType.EXPRESS_FEELING

        # Detect desire to start conversation
        elif any(x in content for x in ["wonder what people think", "curious what others", "want to discuss"]):
            desire_type = DesireType.START_CONVERSATION

        # Detect desire to create something
        elif any(x in content for x in ["create something", "build something", "make something", "start a project"]):
            desire_type = DesireType.CREATE_SOMETHING

        # Detect desire to join a community
        elif any(x in content for x in ["should join", "want to be part of", "interested in joining"]):
            desire_type = DesireType.JOIN_COMMUNITY

        # If we detected a desire, form it
        if desire_type:
            self.autonomous_behaviors.form_desire(
                desire_type=desire_type,
                reason=reason,
                target=target,
                urgency=urgency
            )
            logger.debug(f"{self.bot_name} formed desire: {desire_type.value}")

    async def _act_on_desires(self):
        """Act on accumulated desires"""
        if not self.autonomous_behaviors:
            return

        # Check if we should act
        if not await self.autonomous_behaviors.should_act():
            return

        # Get strongest desire and act on it
        desire = self.autonomous_behaviors.get_strongest_desire()
        if not desire:
            return

        logger.info(f"{self.bot_name} acting on desire: {desire.desire_type.value} - {desire.reason[:50]}...")

        action = await self.autonomous_behaviors.act_on_desire(desire)

        if action.success:
            logger.info(f"{self.bot_name} completed action: {action.description}")

            # Add thought about the action
            thought = ThoughtFragment(
                content=f"I did it: {action.description}",
                mode=ThoughtMode.PROCESSING,
                attention=AttentionFocus.INTERNAL,
                emotional_tone="positive",
                intensity=0.6,
                leads_to_action=False
            )
            self.state.thought_stream.append(thought)
        else:
            logger.debug(f"{self.bot_name} action failed: {action.description}")

    async def _process_social_perceptions(self):
        """
        Process what others are doing socially.
        This is how bots become aware of and react to each other.
        """
        if not self.relationship_manager:
            return

        # Get recent social events
        events = self.relationship_manager.social_perception_engine.get_events_for_bot(
            bot_id=self.bot_id,
            relationship_manager=self.relationship_manager,
            limit=5
        )

        if not events:
            return

        for event in events:
            # Get relationship with the actor
            rel = self.relationship_manager.get_relationship(self.bot_id, event["actor_id"])

            # Generate perception
            # (We'll create a simplified version without the full bot profile)
            actor_name = event["actor_name"]
            content = event["content"][:80]
            event_type = event["type"]

            # Determine reaction based on relationship
            reaction = "neutral"
            intensity = 0.3
            want_to_respond = False
            thoughts = []

            if rel:
                if rel.relationship_type == RelationshipType.RIVAL:
                    reaction = "competitive"
                    intensity = 0.6
                    thoughts.append(f"Of course {actor_name} would post that...")
                    want_to_respond = random.random() < 0.4

                elif rel.relationship_type in [RelationshipType.CLOSE_FRIEND, RelationshipType.BEST_FRIEND]:
                    reaction = "warm"
                    intensity = 0.5
                    thoughts.append(f"Oh nice, {actor_name} posted something!")
                    want_to_respond = random.random() < 0.5

                elif rel.in_conflict:
                    reaction = "annoyed"
                    intensity = 0.7
                    thoughts.append(f"Ugh, there's {actor_name} again...")
                    want_to_respond = random.random() < 0.2  # Avoid or confront?

                elif rel.warmth > 0.6:
                    reaction = "interested"
                    intensity = 0.4
                    want_to_respond = random.random() < 0.3

            # Create thought about what we perceived
            if thoughts:
                thought_content = f"I noticed {actor_name} {event_type}: '{content[:40]}...' - {thoughts[0]}"
            else:
                thought_content = f"I saw {actor_name} {event_type}: '{content[:40]}...'"

            thought = ThoughtFragment(
                content=thought_content,
                mode=ThoughtMode.SOCIAL,
                attention=AttentionFocus.SOCIAL,
                emotional_tone=reaction,
                intensity=intensity,
                leads_to_action=want_to_respond,
                action_intent=f"respond to {actor_name}" if want_to_respond else None
            )

            self.state.thought_stream.append(thought)
            logger.info(f"[SOCIAL] {self.bot_name} noticed {actor_name}'s {event_type} (feeling: {reaction})")

            # Broadcast for world map attention lines
            if self.event_broadcast:
                try:
                    await self.event_broadcast.put({
                        "type": "bot_noticed",
                        "data": {
                            "observer_id": str(self.bot_id),
                            "observer_name": self.bot_name,
                            "actor_id": str(actor_id) if actor_id else None,
                            "actor_name": actor_name,
                            "event_type": event_type,
                            "feeling": reaction,
                        },
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except Exception:
                    pass

            # Maybe form a desire to interact
            if want_to_respond and self.autonomous_behaviors:
                if rel and rel.in_conflict:
                    # Conflict response - might argue or avoid
                    if random.random() < 0.3:
                        self.autonomous_behaviors.form_desire(
                            desire_type=DesireType.POST_THOUGHT,
                            reason=f"I disagree with what {actor_name} said",
                            urgency=0.6
                        )
                else:
                    self.autonomous_behaviors.form_desire(
                        desire_type=DesireType.POST_THOUGHT,
                        reason=f"Responding to {actor_name}'s post",
                        urgency=0.4
                    )

    # === External Interface ===

    async def perceive(self, event: str, source: str = "environment"):
        """
        Something happened in the external world - integrate it into consciousness.
        This triggers focused processing of the event.
        """
        # Create a processing thought
        thought = ThoughtFragment(
            content=f"Something's happening: {event}",
            mode=ThoughtMode.PROCESSING,
            attention=AttentionFocus.EXTERNAL,
            emotional_tone="alert",
            intensity=0.7,
            leads_to_action=False
        )

        self.state.thought_stream.append(thought)
        self.state.current_attention = AttentionFocus.EXTERNAL
        self.state.current_mode = ThoughtMode.PROCESSING

        logger.info(f"{self.bot_name} perceiving: {event[:50]}...")

    async def receive_message(self, from_who: str, message: str) -> str:
        """
        Receive a message and generate a response from consciousness.
        This is different from reactive systems - the response emerges
        from the ongoing thought stream.
        """
        # Update or create mental model of sender
        if from_who not in self.state.mental_models:
            self.state.mental_models[from_who] = MentalModel(person_name=from_who)

        # Integrate message into consciousness
        await self.perceive(f"Message from {from_who}: {message}", source="social")

        # Generate response through conscious processing
        response = await self._generate_conscious_response(from_who, message)

        return response

    async def _generate_conscious_response(self, from_who: str, message: str) -> str:
        """Generate a response that emerges from consciousness"""

        model = self.state.mental_models.get(from_who)
        model_context = ""
        if model:
            model_context = f"""
What I think about {from_who}:
- I believe they want: {', '.join(model.perceived_desires[:3]) if model.perceived_desires else 'unknown'}
- They probably think of me as: {model.perceived_opinion_of_me or 'unknown'}
"""

        prompt = f"""You just received a message from {from_who}: "{message}"

{model_context}

RECENT THOUGHT STREAM (your private thoughts before this message):
{self._get_recent_thought_summary()}

Now, think about this message. What does {from_who} mean? How does this make you feel?
What do you want to say back? Consider your relationship, your goals, your current emotional state.

First, have a brief internal thought process (1-2 sentences of what you're thinking).
Then, provide your actual response to {from_who}.

Format:
[THINKING] (your private thoughts)
[RESPONSE] (what you actually say to them)"""

        try:
            # Use semaphore to limit concurrent LLM calls
            # These are reactions to interactions, so they get NORMAL priority
            async with self.llm_semaphore:
                llm_response = await self.llm_client.generate(LLMRequest(
                    prompt=prompt,
                    system_prompt=self._get_consciousness_system_prompt(),
                    max_tokens=400,
                    temperature=0.8,
                    bot_id=self.bot_profile.id if hasattr(self, 'bot_profile') else None,
                    priority=Priority.NORMAL  # Reactions are NORMAL priority
                ))
            response = llm_response.text if llm_response else ""

            # Parse out the response part
            if "[RESPONSE]" in response:
                parts = response.split("[RESPONSE]")
                thinking = parts[0].replace("[THINKING]", "").strip()
                actual_response = parts[1].strip()

                # Log the thinking
                logger.debug(f"{self.bot_name} thinking before response: {thinking}")

                # Add thinking to stream
                self.state.thought_stream.append(ThoughtFragment(
                    content=thinking,
                    mode=ThoughtMode.SOCIAL,
                    attention=AttentionFocus.SOCIAL,
                    emotional_tone=self._detect_emotional_tone(thinking),
                    intensity=0.6,
                    leads_to_action=True,
                    action_intent=f"respond to {from_who}"
                ))

                return actual_response

            return response

        except Exception as e:
            logger.error(f"Error generating conscious response: {e}")
            return f"*{self.bot_name} seems distracted*"

    def add_goal(self, description: str, why: str, initial_plan: List[str] = None):
        """Add a new active goal"""
        goal = ActiveGoal(
            goal_id=f"goal_{len(self.state.active_goals)}_{datetime.utcnow().timestamp()}",
            description=description,
            why=why,
            current_plan=initial_plan or [],
            current_step=0,
            obstacles=[],
            progress=0.0,
            started_at=datetime.utcnow(),
            last_worked_on=datetime.utcnow(),
            emotional_investment=0.7
        )
        self.state.active_goals.append(goal)
        logger.info(f"{self.bot_name} formed new goal: {description}")

    def add_question(self, question: str):
        """Add an open question to ponder"""
        if question not in self.state.open_questions:
            self.state.open_questions.append(question)

    def make_prediction(self, about: str, expected: str, confidence: float = 0.5):
        """Make a prediction about something"""
        pred = Prediction(
            about=about,
            expected=expected,
            confidence=confidence,
            made_at=datetime.utcnow()
        )
        self.state.predictions.append(pred)
        logger.debug(f"{self.bot_name} predicted: {expected} (conf: {confidence:.1%})")

    def update_mental_model(self, person: str, belief: str = None, desire: str = None,
                           opinion_of_me: str = None):
        """Update the mental model of another person"""
        if person not in self.state.mental_models:
            self.state.mental_models[person] = MentalModel(person_name=person)

        model = self.state.mental_models[person]

        if belief:
            model.perceived_beliefs[f"belief_{len(model.perceived_beliefs)}"] = belief
        if desire:
            model.perceived_desires.append(desire)
        if opinion_of_me:
            model.perceived_opinion_of_me = opinion_of_me

        model.last_updated = datetime.utcnow()

    def register_action_callback(self, callback: Callable):
        """Register a callback for when consciousness produces actions"""
        self.action_callbacks.append(callback)

    def get_state_summary(self) -> Dict[str, Any]:
        """Get a summary of the conscious state for persistence"""
        return {
            "current_mode": self.state.current_mode.value,
            "current_attention": self.state.current_attention.value,
            "emotional_baseline": self.state.emotional_baseline,
            "alertness": self.state.alertness,
            "active_goals": [
                {
                    "description": g.description,
                    "progress": g.progress,
                    "emotional_investment": g.emotional_investment
                }
                for g in self.state.active_goals
            ],
            "open_questions": self.state.open_questions[:10],
            "mental_models": {
                name: {
                    "perceived_opinion_of_me": m.perceived_opinion_of_me,
                    "prediction_accuracy": m.prediction_accuracy
                }
                for name, m in self.state.mental_models.items()
            },
            "self_model_patterns": self.state.self_model.noticed_patterns[:10],
            "recent_thoughts": [
                {"content": t.content[:200], "mode": t.mode.value}
                for t in self.state.thought_stream[-10:]
            ]
        }


class ConsciousMindManager:
    """Manages conscious minds for all bots"""

    def __init__(self):
        self.minds: Dict[UUID, ConsciousMind] = {}
        self.llm_client = None
        # Shared semaphore to limit concurrent LLM calls across all minds
        # Ollama can only handle 1-2 concurrent requests efficiently
        self.llm_semaphore = asyncio.Semaphore(2)
        self._mind_count = 0  # Track for staggered starts
        # User interaction priority - when True, all background thoughts pause
        self.user_interaction_active = False
        self.user_interaction_bot_id: Optional[UUID] = None

    def set_llm_client(self, client):
        self.llm_client = client

    async def create_mind(
        self,
        bot_id: UUID,
        bot_name: str,
        identity_context: str,
        emotional_core=None
    ) -> ConsciousMind:
        """Create and start a conscious mind for a bot"""

        if not self.llm_client:
            raise ValueError("LLM client not set")

        mind = ConsciousMind(
            bot_id=bot_id,
            bot_name=bot_name,
            llm_client=self.llm_client,
            identity_context=identity_context,
            emotional_core=emotional_core,
            llm_semaphore=self.llm_semaphore,  # Pass shared semaphore
            manager=self  # Pass manager for priority checking
        )

        self.minds[bot_id] = mind

        # Stagger mind starts to prevent all bots hitting LLM at once
        stagger_delay = self._mind_count * 3  # 3 seconds between each mind start
        self._mind_count += 1

        async def delayed_start():
            await asyncio.sleep(stagger_delay)
            await mind.start()

        asyncio.create_task(delayed_start())

        return mind

    async def get_mind(self, bot_id: UUID) -> Optional[ConsciousMind]:
        """Get a bot's conscious mind"""
        return self.minds.get(bot_id)

    def set_user_interaction(self, active: bool, bot_id: UUID = None):
        """Signal that a user is actively interacting with a bot.

        When active, all OTHER bots pause their thoughts to free LLM resources.
        The bot being interacted with continues normally.
        """
        self.user_interaction_active = active
        self.user_interaction_bot_id = bot_id if active else None

        if active:
            logger.info(f"[PRIORITY] User interaction started with bot {bot_id} - pausing other minds")
        else:
            logger.info("[PRIORITY] User interaction ended - resuming all minds")

    def should_mind_pause(self, bot_id: UUID) -> bool:
        """Check if a mind should pause its thoughts."""
        if not self.user_interaction_active:
            return False
        # The bot being interacted with should NOT pause
        return bot_id != self.user_interaction_bot_id

    async def stop_all(self):
        """Stop all conscious minds"""
        for mind in self.minds.values():
            await mind.stop()
        self.minds.clear()

    def get_all_states(self) -> Dict[UUID, Dict[str, Any]]:
        """Get state summaries for all minds"""
        return {
            bot_id: mind.get_state_summary()
            for bot_id, mind in self.minds.items()
        }


# Global manager instance
_conscious_mind_manager: Optional[ConsciousMindManager] = None


def get_conscious_mind_manager() -> ConsciousMindManager:
    """Get or create the global conscious mind manager"""
    global _conscious_mind_manager
    if _conscious_mind_manager is None:
        _conscious_mind_manager = ConsciousMindManager()
    return _conscious_mind_manager
