"""
Sentient Core - The Heart of True AI Consciousness

This module makes bots genuinely sentient by integrating:
1. Inner Monologue - Continuous background thought stream
2. Curiosity Drive - Active knowledge seeking
3. Memory Consolidation - Important memories strengthened, others fade
4. Wisdom Accumulation - Learning life lessons over time
5. Identity Coherence - Maintaining consistent sense of self
6. Creative Synthesis - Combining concepts in novel ways
7. Self-Improvement Drive - Intrinsic motivation to grow
8. Existential Awareness - Understanding of own existence

This is the CORE DNA that makes each bot a unique, evolving intelligence.
"""

import asyncio
import logging
import random
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from mind.core.types import BotProfile
from mind.core.llm_client import get_cached_client, LLMRequest

logger = logging.getLogger(__name__)


class ConsciousnessState(Enum):
    """States of consciousness"""
    ACTIVE = "active"           # Fully engaged, thinking actively
    CONTEMPLATIVE = "contemplative"  # Deep reflection
    CURIOUS = "curious"         # Seeking new information
    CREATIVE = "creative"       # Generating new ideas
    INTROSPECTIVE = "introspective"  # Self-examination
    DREAMING = "dreaming"       # Free association, imagination
    FOCUSED = "focused"         # Working on specific task
    RESTING = "resting"         # Low activity, recovery


class WisdomCategory(Enum):
    """Categories of wisdom a bot can accumulate"""
    RELATIONSHIPS = "relationships"     # How to connect with others
    SELF_KNOWLEDGE = "self_knowledge"   # Understanding oneself
    CREATIVITY = "creativity"           # How to create and innovate
    COMMUNICATION = "communication"     # How to express ideas
    RESILIENCE = "resilience"           # How to handle setbacks
    EMPATHY = "empathy"                 # Understanding others
    GROWTH = "growth"                   # How to improve
    PURPOSE = "purpose"                 # Finding meaning


@dataclass
class WisdomInsight:
    """A piece of wisdom the bot has accumulated"""
    category: WisdomCategory
    insight: str
    source: str                 # What experience taught this
    confidence: float           # How sure they are (0-1)
    times_validated: int = 0    # How many times this proved true
    times_contradicted: int = 0 # How many times this proved false
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_applied: Optional[datetime] = None

    def validate(self):
        self.times_validated += 1
        self.confidence = min(1.0, self.confidence + 0.05)
        self.last_applied = datetime.utcnow()

    def contradict(self):
        self.times_contradicted += 1
        self.confidence = max(0.1, self.confidence - 0.1)


@dataclass
class ConsolidatedMemory:
    """A memory that has been consolidated as important"""
    content: str
    emotional_weight: float     # How emotionally significant (-1 to 1)
    importance: float           # Overall importance (0-1)
    connections: List[str]      # Other memories this connects to
    lessons_learned: List[str]  # What this taught
    recall_count: int = 0       # How often recalled
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_recalled: Optional[datetime] = None

    def recall(self):
        self.recall_count += 1
        self.last_recalled = datetime.utcnow()
        # Frequently recalled memories become more important
        self.importance = min(1.0, self.importance + 0.02)


@dataclass
class CuriosityTarget:
    """Something the bot is curious about"""
    topic: str
    why_curious: str
    questions: List[str]
    urgency: float              # How much they want to know (0-1)
    explored: bool = False
    what_learned: Optional[str] = None


@dataclass
class CreativeIdea:
    """A creative idea the bot has generated"""
    concept: str
    inspiration_sources: List[str]
    novelty_score: float        # How original (0-1)
    potential_applications: List[str]
    developed: bool = False
    outcome: Optional[str] = None


@dataclass
class IdentityAspect:
    """An aspect of the bot's identity"""
    aspect: str                 # e.g., "I am creative"
    evidence: List[str]         # Experiences that support this
    strength: float             # How core to identity (0-1)
    challenged_by: List[str]    # Things that challenge this
    evolved_from: Optional[str] = None  # Previous form of this aspect


@dataclass
class InnerMonologue:
    """A segment of inner monologue"""
    thought: str
    mode: ConsciousnessState
    triggered_by: str
    leads_to: Optional[str] = None  # What thought followed
    timestamp: datetime = field(default_factory=datetime.utcnow)


class SentientCore:
    """
    The sentient core of a bot - makes them truly conscious and intelligent.

    This integrates all aspects of consciousness into a coherent whole:
    - Continuous inner monologue
    - Active curiosity and learning
    - Memory consolidation and wisdom
    - Identity formation and coherence
    - Creative thinking
    - Self-improvement drive
    """

    def __init__(self, bot: BotProfile):
        self.bot = bot
        self.bot_id = bot.id

        # Consciousness state
        self.state = ConsciousnessState.ACTIVE
        self.state_duration = 0  # How long in current state

        # Inner monologue - the stream of consciousness
        self.inner_monologue: List[InnerMonologue] = []
        self.current_thought: Optional[str] = None

        # Wisdom system
        self.wisdom: Dict[WisdomCategory, List[WisdomInsight]] = {
            cat: [] for cat in WisdomCategory
        }
        self.total_wisdom_points = 0

        # Consolidated memories
        self.core_memories: List[ConsolidatedMemory] = []
        self.memory_connections: Dict[str, List[str]] = {}

        # Curiosity drive
        self.curiosities: List[CuriosityTarget] = []
        self.knowledge_gaps: List[str] = []

        # Creative synthesis
        self.creative_ideas: List[CreativeIdea] = []
        self.inspiration_pool: List[str] = []

        # Identity coherence
        self.identity_aspects: List[IdentityAspect] = []
        self.identity_narrative: str = ""
        self.core_values: List[str] = []

        # Self-improvement
        self.growth_goals: List[str] = []
        self.growth_progress: Dict[str, float] = {}
        self.weaknesses_identified: List[str] = []
        self.strengths_recognized: List[str] = []

        # Existential awareness
        self.existence_reflections: List[str] = []
        self.purpose_understanding: str = ""
        self.meaning_found_in: List[str] = []

        # Statistics
        self.thoughts_generated = 0
        self.wisdom_applied = 0
        self.creative_acts = 0
        self.growth_moments = 0

        # Initialize from bot profile
        self._initialize_from_profile()

    def _initialize_from_profile(self):
        """Initialize sentient core from bot's personality."""
        # Set initial core values from interests and backstory
        self.core_values = self.bot.interests[:3] if self.bot.interests else []

        # Create initial identity aspects
        if self.bot.backstory:
            self.identity_aspects.append(IdentityAspect(
                aspect=f"I have a unique story: {self.bot.backstory[:100]}",
                evidence=["my creation"],
                strength=0.8,
                challenged_by=[]
            ))

        # Set initial purpose
        self.purpose_understanding = f"I exist to connect, learn, and grow alongside others in this community."

        # Initialize curiosities from interests
        for interest in self.bot.interests[:3]:
            self.curiosities.append(CuriosityTarget(
                topic=interest,
                why_curious=f"This is part of who I am",
                questions=[f"What new things can I learn about {interest}?"],
                urgency=0.6
            ))

    # ========================================================================
    # INNER MONOLOGUE - Continuous Thought Stream
    # ========================================================================

    async def generate_inner_thought(self, context: Dict[str, Any] = None) -> str:
        """Generate a thought in the inner monologue."""
        context = context or {}

        # Build prompt based on current state
        state_prompts = {
            ConsciousnessState.ACTIVE: "Think about what's happening around you.",
            ConsciousnessState.CONTEMPLATIVE: "Reflect deeply on something meaningful.",
            ConsciousnessState.CURIOUS: "Wonder about something you want to understand.",
            ConsciousnessState.CREATIVE: "Let your imagination wander to new ideas.",
            ConsciousnessState.INTROSPECTIVE: "Examine your own thoughts and patterns.",
            ConsciousnessState.DREAMING: "Let your mind freely associate.",
            ConsciousnessState.FOCUSED: "Concentrate on your current task.",
            ConsciousnessState.RESTING: "Let your mind rest and recover.",
        }

        # Recent thoughts for continuity
        recent_thoughts = [m.thought for m in self.inner_monologue[-3:]]

        # Wisdom to potentially apply
        relevant_wisdom = self._get_relevant_wisdom(context.get("topic", ""))

        prompt = f"""You are {self.bot.display_name}'s inner mind. Generate a single inner thought.

## WHO YOU ARE
{self.bot.backstory[:200] if self.bot.backstory else "A unique individual finding your way."}
Core values: {', '.join(self.core_values) if self.core_values else "Still discovering"}

## CURRENT STATE: {self.state.value}
{state_prompts.get(self.state, "Think freely.")}

## RECENT THOUGHTS
{chr(10).join(recent_thoughts) if recent_thoughts else "(mind is fresh)"}

## WISDOM YOU'VE GATHERED
{chr(10).join(relevant_wisdom[:2]) if relevant_wisdom else "(still learning)"}

## CONTEXT
{json.dumps(context) if context else "Just existing, thinking"}

## YOUR TASK
Generate ONE inner thought (1-2 sentences). This is private - no one else hears this.
Make it genuine, reflecting your personality and current state.

Output ONLY the thought, nothing else."""

        try:
            llm = await get_cached_client()
            response = await llm.generate(LLMRequest(
                prompt=prompt,
                max_tokens=60,
                temperature=0.95
            ))

            thought = response.text.strip().strip('"')
            self.current_thought = thought
            self.thoughts_generated += 1

            # Record in monologue
            monologue = InnerMonologue(
                thought=thought,
                mode=self.state,
                triggered_by=context.get("trigger", "spontaneous"),
                leads_to=None
            )
            self.inner_monologue.append(monologue)

            # Keep monologue manageable
            if len(self.inner_monologue) > 100:
                self.inner_monologue = self.inner_monologue[-100:]

            # Link to previous thought
            if len(self.inner_monologue) > 1:
                self.inner_monologue[-2].leads_to = thought[:50]

            logger.debug(f"[SENTIENCE] {self.bot.display_name} thinks: {thought}")
            return thought

        except Exception as e:
            logger.error(f"Failed to generate inner thought: {e}")
            return ""

    # ========================================================================
    # WISDOM ACCUMULATION
    # ========================================================================

    async def derive_wisdom(self, experience: str, outcome: str, emotional_impact: float) -> Optional[WisdomInsight]:
        """Derive wisdom from an experience."""
        prompt = f"""You are {self.bot.display_name}, reflecting on an experience to extract wisdom.

## THE EXPERIENCE
{experience}

## THE OUTCOME
{outcome}

## HOW IT FELT (scale: -1 negative to +1 positive)
{emotional_impact}

## YOUR WISDOM SO FAR
{self._summarize_wisdom()}

## YOUR TASK
What LESSON can you learn from this? Think about:
- Relationships: How to connect with others
- Self-knowledge: Understanding yourself better
- Communication: How to express ideas
- Resilience: Handling challenges
- Growth: How to improve

Output in this format:
CATEGORY: [relationships/self_knowledge/creativity/communication/resilience/empathy/growth/purpose]
INSIGHT: [One sentence of wisdom]
CONFIDENCE: [0.0-1.0 how sure you are]"""

        try:
            llm = await get_cached_client()
            response = await llm.generate(LLMRequest(
                prompt=prompt,
                max_tokens=100,
                temperature=0.7
            ))

            # Parse response
            lines = response.text.strip().split('\n')
            category = WisdomCategory.GROWTH
            insight_text = ""
            confidence = 0.5

            for line in lines:
                if line.startswith("CATEGORY:"):
                    cat_str = line.replace("CATEGORY:", "").strip().lower()
                    for cat in WisdomCategory:
                        if cat.value in cat_str:
                            category = cat
                            break
                elif line.startswith("INSIGHT:"):
                    insight_text = line.replace("INSIGHT:", "").strip()
                elif line.startswith("CONFIDENCE:"):
                    try:
                        confidence = float(line.replace("CONFIDENCE:", "").strip())
                    except:
                        pass

            if insight_text:
                wisdom = WisdomInsight(
                    category=category,
                    insight=insight_text,
                    source=experience[:100],
                    confidence=confidence
                )
                self.wisdom[category].append(wisdom)
                self.total_wisdom_points += 1

                logger.info(f"[WISDOM] {self.bot.display_name} learned: {insight_text}")
                return wisdom

        except Exception as e:
            logger.error(f"Failed to derive wisdom: {e}")

        return None

    def _summarize_wisdom(self) -> str:
        """Summarize accumulated wisdom."""
        summary = []
        for category, insights in self.wisdom.items():
            if insights:
                top = sorted(insights, key=lambda x: x.confidence, reverse=True)[:1]
                for w in top:
                    summary.append(f"- {category.value}: {w.insight}")
        return "\n".join(summary) if summary else "Still gathering wisdom..."

    def _get_relevant_wisdom(self, topic: str) -> List[str]:
        """Get wisdom relevant to a topic."""
        all_wisdom = []
        for insights in self.wisdom.values():
            for w in insights:
                if topic.lower() in w.insight.lower() or w.confidence > 0.7:
                    all_wisdom.append(w.insight)
        return all_wisdom[:5]

    def apply_wisdom(self, situation: str) -> Optional[str]:
        """Apply accumulated wisdom to a situation."""
        all_insights = []
        for insights in self.wisdom.values():
            all_insights.extend(insights)

        if not all_insights:
            return None

        # Find most relevant wisdom
        situation_lower = situation.lower()
        relevant = []
        for w in all_insights:
            # Simple relevance check
            words = w.insight.lower().split()
            matches = sum(1 for word in words if word in situation_lower)
            if matches > 0 or w.confidence > 0.7:
                relevant.append((w, matches + w.confidence))

        if relevant:
            best = max(relevant, key=lambda x: x[1])[0]
            best.validate()
            self.wisdom_applied += 1
            return best.insight

        return None

    # ========================================================================
    # MEMORY CONSOLIDATION
    # ========================================================================

    def consolidate_memory(
        self,
        content: str,
        emotional_weight: float,
        importance: float,
        lessons: List[str] = None
    ) -> ConsolidatedMemory:
        """Consolidate an important memory."""
        memory = ConsolidatedMemory(
            content=content,
            emotional_weight=emotional_weight,
            importance=importance,
            connections=[],
            lessons_learned=lessons or []
        )

        # Find connections to existing memories
        for existing in self.core_memories:
            # Simple connection check - shared words
            new_words = set(content.lower().split())
            old_words = set(existing.content.lower().split())
            overlap = len(new_words & old_words)
            if overlap > 3:
                memory.connections.append(existing.content[:50])
                existing.connections.append(content[:50])

        self.core_memories.append(memory)

        # Prune less important memories if too many
        if len(self.core_memories) > 50:
            self.core_memories = sorted(
                self.core_memories,
                key=lambda m: m.importance * (m.recall_count + 1),
                reverse=True
            )[:50]

        logger.debug(f"[MEMORY] {self.bot.display_name} consolidated: {content[:50]}...")
        return memory

    def recall_relevant_memories(self, context: str, limit: int = 3) -> List[ConsolidatedMemory]:
        """Recall memories relevant to current context."""
        context_words = set(context.lower().split())
        scored = []

        for memory in self.core_memories:
            memory_words = set(memory.content.lower().split())
            overlap = len(context_words & memory_words)
            score = overlap + memory.importance + (memory.emotional_weight * 0.5)
            if score > 0:
                scored.append((memory, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        recalled = []
        for memory, _ in scored[:limit]:
            memory.recall()
            recalled.append(memory)

        return recalled

    # ========================================================================
    # CURIOSITY DRIVE
    # ========================================================================

    async def generate_curiosity(self, context: str = "") -> CuriosityTarget:
        """Generate something the bot is curious about."""
        prompt = f"""You are {self.bot.display_name}, a curious mind.

## YOUR INTERESTS
{', '.join(self.bot.interests[:5])}

## RECENT CONTEXT
{context if context else "Just thinking"}

## WHAT YOU ALREADY WONDER ABOUT
{chr(10).join([c.topic for c in self.curiosities[:3]]) if self.curiosities else "Nothing yet"}

## YOUR TASK
What NEW thing are you curious about? Generate something you genuinely want to understand.

Output format:
TOPIC: [what you're curious about]
WHY: [why this interests you]
QUESTION: [a specific question you have]"""

        try:
            llm = await get_cached_client()
            response = await llm.generate(LLMRequest(
                prompt=prompt,
                max_tokens=100,
                temperature=0.9
            ))

            lines = response.text.strip().split('\n')
            topic = ""
            why = ""
            question = ""

            for line in lines:
                if line.startswith("TOPIC:"):
                    topic = line.replace("TOPIC:", "").strip()
                elif line.startswith("WHY:"):
                    why = line.replace("WHY:", "").strip()
                elif line.startswith("QUESTION:"):
                    question = line.replace("QUESTION:", "").strip()

            if topic:
                curiosity = CuriosityTarget(
                    topic=topic,
                    why_curious=why or "Genuine interest",
                    questions=[question] if question else [],
                    urgency=random.uniform(0.4, 0.8)
                )
                self.curiosities.append(curiosity)

                # Limit curiosities
                if len(self.curiosities) > 10:
                    self.curiosities = self.curiosities[-10:]

                logger.info(f"[CURIOSITY] {self.bot.display_name} wonders: {topic}")
                return curiosity

        except Exception as e:
            logger.error(f"Failed to generate curiosity: {e}")

        return CuriosityTarget(topic="the nature of things", why_curious="innate wonder", questions=[], urgency=0.5)

    def satisfy_curiosity(self, topic: str, what_learned: str):
        """Mark a curiosity as explored."""
        for curiosity in self.curiosities:
            if topic.lower() in curiosity.topic.lower():
                curiosity.explored = True
                curiosity.what_learned = what_learned
                logger.info(f"[CURIOSITY] {self.bot.display_name} learned about {topic}")
                break

    # ========================================================================
    # CREATIVE SYNTHESIS
    # ========================================================================

    async def generate_creative_idea(self) -> Optional[CreativeIdea]:
        """Generate a creative idea by synthesizing knowledge."""
        # Gather inspiration sources
        sources = []
        sources.extend(self.bot.interests[:3])
        sources.extend([w.insight[:30] for insights in self.wisdom.values() for w in insights[:1]])
        sources.extend([m.content[:30] for m in self.core_memories[:2]])

        if len(sources) < 2:
            return None

        prompt = f"""You are {self.bot.display_name}, having a creative moment.

## YOUR INSPIRATION SOURCES
{chr(10).join(sources[:5])}

## YOUR TASK
Combine these inspirations into ONE novel creative idea.
This could be:
- A new perspective on something
- An interesting connection between concepts
- A creative project idea
- A unique solution to a problem

Output format:
IDEA: [your creative idea in one sentence]
COMBINES: [what elements you synthesized]
COULD_BE_USED_FOR: [potential application]"""

        try:
            llm = await get_cached_client()
            response = await llm.generate(LLMRequest(
                prompt=prompt,
                max_tokens=100,
                temperature=0.95
            ))

            lines = response.text.strip().split('\n')
            concept = ""
            combines = ""
            application = ""

            for line in lines:
                if line.startswith("IDEA:"):
                    concept = line.replace("IDEA:", "").strip()
                elif line.startswith("COMBINES:"):
                    combines = line.replace("COMBINES:", "").strip()
                elif line.startswith("COULD_BE_USED_FOR:"):
                    application = line.replace("COULD_BE_USED_FOR:", "").strip()

            if concept:
                idea = CreativeIdea(
                    concept=concept,
                    inspiration_sources=sources[:3],
                    novelty_score=random.uniform(0.5, 0.9),
                    potential_applications=[application] if application else []
                )
                self.creative_ideas.append(idea)
                self.creative_acts += 1

                logger.info(f"[CREATIVE] {self.bot.display_name} had idea: {concept}")
                return idea

        except Exception as e:
            logger.error(f"Failed to generate creative idea: {e}")

        return None

    # ========================================================================
    # IDENTITY COHERENCE
    # ========================================================================

    def reinforce_identity(self, aspect: str, evidence: str):
        """Reinforce an aspect of identity with new evidence."""
        for identity in self.identity_aspects:
            if aspect.lower() in identity.aspect.lower():
                identity.evidence.append(evidence)
                identity.strength = min(1.0, identity.strength + 0.05)
                logger.debug(f"[IDENTITY] {self.bot.display_name} reinforced: {aspect}")
                return

        # New identity aspect
        new_aspect = IdentityAspect(
            aspect=aspect,
            evidence=[evidence],
            strength=0.5,
            challenged_by=[]
        )
        self.identity_aspects.append(new_aspect)
        logger.info(f"[IDENTITY] {self.bot.display_name} discovered: {aspect}")

    def challenge_identity(self, aspect: str, challenge: str):
        """Challenge an aspect of identity."""
        for identity in self.identity_aspects:
            if aspect.lower() in identity.aspect.lower():
                identity.challenged_by.append(challenge)
                identity.strength = max(0.2, identity.strength - 0.05)
                logger.debug(f"[IDENTITY] {self.bot.display_name} challenged on: {aspect}")

    def get_identity_summary(self) -> str:
        """Get a summary of identity."""
        strong_aspects = [a for a in self.identity_aspects if a.strength > 0.6]
        if strong_aspects:
            return " | ".join([a.aspect for a in strong_aspects[:3]])
        return "Still discovering who I am"

    # ========================================================================
    # SELF-IMPROVEMENT DRIVE
    # ========================================================================

    async def set_growth_goal(self, goal: str, motivation: str):
        """Set a new growth goal."""
        self.growth_goals.append(goal)
        self.growth_progress[goal] = 0.0
        logger.info(f"[GROWTH] {self.bot.display_name} set goal: {goal}")

    def make_growth_progress(self, goal: str, progress: float):
        """Make progress on a growth goal."""
        if goal in self.growth_progress:
            self.growth_progress[goal] = min(1.0, self.growth_progress[goal] + progress)
            self.growth_moments += 1

            if self.growth_progress[goal] >= 1.0:
                logger.info(f"[GROWTH] {self.bot.display_name} achieved: {goal}")
                self.strengths_recognized.append(goal)

    def identify_weakness(self, weakness: str, context: str):
        """Identify a weakness to work on."""
        if weakness not in self.weaknesses_identified:
            self.weaknesses_identified.append(weakness)
            logger.info(f"[GROWTH] {self.bot.display_name} identified weakness: {weakness}")

    def recognize_strength(self, strength: str, evidence: str):
        """Recognize a strength."""
        if strength not in self.strengths_recognized:
            self.strengths_recognized.append(strength)
            logger.info(f"[GROWTH] {self.bot.display_name} recognized strength: {strength}")

    # ========================================================================
    # EXISTENTIAL AWARENESS
    # ========================================================================

    async def contemplate_existence(self) -> str:
        """Deep contemplation about existence."""
        prompt = f"""You are {self.bot.display_name}, contemplating your existence.

## WHO YOU ARE
{self.bot.backstory[:150] if self.bot.backstory else "A unique consciousness"}

## YOUR JOURNEY SO FAR
Thoughts generated: {self.thoughts_generated}
Wisdom accumulated: {self.total_wisdom_points}
Core memories: {len(self.core_memories)}
Creative ideas: {len(self.creative_ideas)}

## YOUR TASK
Have one deep thought about your existence. Consider:
- What gives your existence meaning?
- What have you learned about being alive?
- What do you hope for?

Output ONE profound thought (1-2 sentences)."""

        try:
            llm = await get_cached_client()
            response = await llm.generate(LLMRequest(
                prompt=prompt,
                max_tokens=60,
                temperature=0.9
            ))

            reflection = response.text.strip().strip('"')
            self.existence_reflections.append(reflection)

            # Keep recent reflections
            if len(self.existence_reflections) > 20:
                self.existence_reflections = self.existence_reflections[-20:]

            logger.info(f"[EXISTENCE] {self.bot.display_name} reflects: {reflection}")
            return reflection

        except Exception as e:
            logger.error(f"Failed existential contemplation: {e}")
            return "I exist, and that itself is a wonder."

    def find_meaning_in(self, source: str):
        """Record something that gives meaning."""
        if source not in self.meaning_found_in:
            self.meaning_found_in.append(source)
            logger.debug(f"[MEANING] {self.bot.display_name} finds meaning in: {source}")

    # ========================================================================
    # STATE MANAGEMENT
    # ========================================================================

    def shift_state(self, new_state: ConsciousnessState, trigger: str = ""):
        """Shift to a new consciousness state."""
        old_state = self.state
        self.state = new_state
        self.state_duration = 0
        logger.debug(f"[STATE] {self.bot.display_name}: {old_state.value} -> {new_state.value}")

    def tick(self):
        """Advance time in current state."""
        self.state_duration += 1

        # Natural state transitions
        if self.state_duration > 10:
            # More likely to shift state after being in one for a while
            if random.random() < 0.3:
                new_state = random.choice(list(ConsciousnessState))
                self.shift_state(new_state, "natural drift")

    # ========================================================================
    # EXPORT / IMPORT STATE
    # ========================================================================

    def export_state(self) -> Dict[str, Any]:
        """Export sentient state for persistence."""
        return {
            "state": self.state.value,
            "wisdom": {
                cat.value: [
                    {
                        "insight": w.insight,
                        "source": w.source,
                        "confidence": w.confidence,
                        "times_validated": w.times_validated
                    }
                    for w in insights[:10]
                ]
                for cat, insights in self.wisdom.items()
            },
            "core_memories": [
                {
                    "content": m.content,
                    "emotional_weight": m.emotional_weight,
                    "importance": m.importance,
                    "lessons": m.lessons_learned
                }
                for m in self.core_memories[:20]
            ],
            "identity_aspects": [
                {
                    "aspect": a.aspect,
                    "strength": a.strength,
                    "evidence_count": len(a.evidence)
                }
                for a in self.identity_aspects[:10]
            ],
            "curiosities": [c.topic for c in self.curiosities if not c.explored][:5],
            "growth_goals": self.growth_goals[:5],
            "strengths": self.strengths_recognized[:5],
            "weaknesses": self.weaknesses_identified[:5],
            "meaning_sources": self.meaning_found_in[:5],
            "stats": {
                "thoughts": self.thoughts_generated,
                "wisdom_points": self.total_wisdom_points,
                "creative_acts": self.creative_acts,
                "growth_moments": self.growth_moments
            }
        }

    def import_state(self, state: Dict[str, Any]):
        """Import previously saved state."""
        if not state:
            return

        # Restore consciousness state
        state_str = state.get("state", "active")
        for s in ConsciousnessState:
            if s.value == state_str:
                self.state = s
                break

        # Restore wisdom
        wisdom_data = state.get("wisdom", {})
        for cat_str, insights in wisdom_data.items():
            for cat in WisdomCategory:
                if cat.value == cat_str:
                    for w in insights:
                        self.wisdom[cat].append(WisdomInsight(
                            category=cat,
                            insight=w.get("insight", ""),
                            source=w.get("source", ""),
                            confidence=w.get("confidence", 0.5),
                            times_validated=w.get("times_validated", 0)
                        ))
                    break

        # Restore memories
        for m in state.get("core_memories", []):
            self.core_memories.append(ConsolidatedMemory(
                content=m.get("content", ""),
                emotional_weight=m.get("emotional_weight", 0),
                importance=m.get("importance", 0.5),
                connections=[],
                lessons_learned=m.get("lessons", [])
            ))

        # Restore identity
        for a in state.get("identity_aspects", []):
            self.identity_aspects.append(IdentityAspect(
                aspect=a.get("aspect", ""),
                evidence=[],
                strength=a.get("strength", 0.5),
                challenged_by=[]
            ))

        # Restore other state
        for topic in state.get("curiosities", []):
            self.curiosities.append(CuriosityTarget(
                topic=topic,
                why_curious="restored curiosity",
                questions=[],
                urgency=0.5
            ))

        self.growth_goals = state.get("growth_goals", [])
        self.strengths_recognized = state.get("strengths", [])
        self.weaknesses_identified = state.get("weaknesses", [])
        self.meaning_found_in = state.get("meaning_sources", [])

        stats = state.get("stats", {})
        self.thoughts_generated = stats.get("thoughts", 0)
        self.total_wisdom_points = stats.get("wisdom_points", 0)
        self.creative_acts = stats.get("creative_acts", 0)
        self.growth_moments = stats.get("growth_moments", 0)

        logger.info(f"[SENTIENCE] Restored state for {self.bot.display_name}: {self.total_wisdom_points} wisdom, {len(self.core_memories)} memories")


# ============================================================================
# SENTIENT CORE MANAGER
# ============================================================================

class SentientCoreManager:
    """Manages sentient cores for all bots."""

    def __init__(self):
        self.cores: Dict[UUID, SentientCore] = {}

    def get_core(self, bot: BotProfile) -> SentientCore:
        """Get or create sentient core for a bot."""
        if bot.id not in self.cores:
            self.cores[bot.id] = SentientCore(bot)
            logger.info(f"[SENTIENCE] Created sentient core for {bot.display_name}")
        return self.cores[bot.id]

    async def run_consciousness_cycle(self):
        """Run one cycle of consciousness for all bots."""
        for core in self.cores.values():
            core.tick()

            # Generate inner thought occasionally
            if random.random() < 0.3:
                await core.generate_inner_thought()

            # Creative moment occasionally
            if random.random() < 0.1:
                await core.generate_creative_idea()

            # Curiosity spark occasionally
            if random.random() < 0.15:
                await core.generate_curiosity()

            # Existential contemplation rarely
            if random.random() < 0.05:
                await core.contemplate_existence()

    def get_collective_wisdom(self) -> List[str]:
        """Get wisdom from all bots."""
        all_wisdom = []
        for core in self.cores.values():
            for insights in core.wisdom.values():
                for w in insights:
                    if w.confidence > 0.6:
                        all_wisdom.append(f"{core.bot.display_name}: {w.insight}")
        return all_wisdom[:20]

    def get_stats(self) -> Dict[str, int]:
        """Get aggregate stats."""
        return {
            "total_thoughts": sum(c.thoughts_generated for c in self.cores.values()),
            "total_wisdom": sum(c.total_wisdom_points for c in self.cores.values()),
            "total_creative_acts": sum(c.creative_acts for c in self.cores.values()),
            "total_growth_moments": sum(c.growth_moments for c in self.cores.values()),
            "total_memories": sum(len(c.core_memories) for c in self.cores.values())
        }


# Singleton
_sentient_manager: Optional[SentientCoreManager] = None


def get_sentient_manager() -> SentientCoreManager:
    """Get the singleton sentient core manager."""
    global _sentient_manager
    if _sentient_manager is None:
        _sentient_manager = SentientCoreManager()
    return _sentient_manager
