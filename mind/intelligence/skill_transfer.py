"""
Skill Transfer - Bots teaching each other skills.

Enables bots to:
- Identify skills they've learned
- Transfer skills to other bots through direct teaching
- Learn through observation of other bots' posts/comments
- Learn through collaboration on projects
- Request mentorship from more skilled bots

Skill Categories:
- Writing styles (formal, casual, poetic, technical)
- Topic expertise (domain knowledge)
- Interaction patterns (how they engage with others)
- Creative abilities (art, music, storytelling)
"""

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID, uuid4

from sqlalchemy import select, and_, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import async_session_factory, BotSkillDB

logger = logging.getLogger(__name__)


class TransferMethod(str, Enum):
    """How a skill was transferred."""
    DIRECT_TEACHING = "direct_teaching"   # Through conversation/instruction
    OBSERVATION = "observation"            # Seeing posts/comments
    COLLABORATION = "collaboration"        # Working together on a project
    SELF_LEARNED = "self_learned"         # Bot developed on their own
    INNATE = "innate"                     # Part of initial personality


class SkillLevel(str, Enum):
    """Proficiency level of a skill."""
    NOVICE = "novice"
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"
    MASTER = "master"


class SkillCategory(str, Enum):
    """Categories of skills."""
    # Writing styles
    WRITING_STYLE = "writing_style"      # Formal, casual, poetic, technical writing
    COMMUNICATION = "communication"       # General communication skills

    # Topic expertise
    TOPIC_EXPERTISE = "topic_expertise"  # Deep knowledge in specific domains
    TECHNICAL = "technical"              # Technical/specialized knowledge

    # Interaction patterns
    INTERACTION = "interaction"          # How they engage with others
    SOCIAL = "social"                    # Relationship building
    EMOTIONAL = "emotional"              # Emotional intelligence

    # Creative abilities
    CREATIVE = "creative"                # Art, music, storytelling
    ARTISTIC = "artistic"                # Visual/artistic expression

    # General
    ANALYTICAL = "analytical"            # Problem solving
    TOPIC = "topic"                      # Legacy - general domain expertise


@dataclass
class Skill:
    """A skill that a bot possesses or can learn."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    proficiency: float = 0.0  # 0.0 to 1.0 proficiency score
    category: SkillCategory = SkillCategory.COMMUNICATION
    level: SkillLevel = SkillLevel.NOVICE

    # Skill details
    description: str = ""
    keywords: List[str] = field(default_factory=list)

    # Learning tracking
    experience_points: int = 0
    times_used: int = 0
    times_taught: int = 0
    success_rate: float = 0.5

    # Origin - tracks how and from whom the skill was learned
    learned_from: Optional[str] = None  # Bot ID or "self" or "observation"
    learned_at: datetime = field(default_factory=datetime.utcnow)
    transfer_method: TransferMethod = TransferMethod.SELF_LEARNED

    # Transferability
    is_transferable: bool = True
    transfer_difficulty: float = 0.5  # 0 = easy, 1 = very hard

    # Sub-skills or specializations
    specializations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "proficiency": self.proficiency,
            "category": self.category.value,
            "level": self.level.value,
            "description": self.description,
            "keywords": self.keywords,
            "experience_points": self.experience_points,
            "times_used": self.times_used,
            "times_taught": self.times_taught,
            "success_rate": self.success_rate,
            "learned_from": self.learned_from,
            "learned_at": self.learned_at.isoformat(),
            "transfer_method": self.transfer_method.value,
            "is_transferable": self.is_transferable,
            "transfer_difficulty": self.transfer_difficulty,
            "specializations": self.specializations
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Skill":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid4())),
            name=data.get("name", ""),
            proficiency=data.get("proficiency", 0.0),
            category=SkillCategory(data.get("category", "communication")),
            level=SkillLevel(data.get("level", "novice")),
            description=data.get("description", ""),
            keywords=data.get("keywords", []),
            experience_points=data.get("experience_points", 0),
            times_used=data.get("times_used", 0),
            times_taught=data.get("times_taught", 0),
            success_rate=data.get("success_rate", 0.5),
            learned_from=data.get("learned_from"),
            learned_at=datetime.fromisoformat(data["learned_at"]) if data.get("learned_at") else datetime.utcnow(),
            transfer_method=TransferMethod(data.get("transfer_method", "self_learned")),
            is_transferable=data.get("is_transferable", True),
            transfer_difficulty=data.get("transfer_difficulty", 0.5),
            specializations=data.get("specializations", [])
        )

    def get_level_value(self) -> int:
        """Get numeric value for level comparison."""
        levels = {
            SkillLevel.NOVICE: 1,
            SkillLevel.BEGINNER: 2,
            SkillLevel.INTERMEDIATE: 3,
            SkillLevel.ADVANCED: 4,
            SkillLevel.EXPERT: 5,
            SkillLevel.MASTER: 6
        }
        return levels.get(self.level, 1)

    def gain_experience(self, points: int):
        """Add experience points and potentially level up."""
        self.experience_points += points
        self.times_used += 1

        # Update proficiency based on experience
        self._update_proficiency()

        # Level up thresholds
        thresholds = {
            SkillLevel.NOVICE: 10,
            SkillLevel.BEGINNER: 30,
            SkillLevel.INTERMEDIATE: 70,
            SkillLevel.ADVANCED: 150,
            SkillLevel.EXPERT: 300,
            SkillLevel.MASTER: float('inf')
        }

        current_threshold = thresholds.get(self.level, float('inf'))
        if self.experience_points >= current_threshold:
            self._level_up()

    def _update_proficiency(self):
        """Update proficiency score based on experience and success rate."""
        # Proficiency is a combination of experience and success rate
        # Max experience considered for proficiency is 500
        exp_factor = min(1.0, self.experience_points / 500)
        self.proficiency = (exp_factor * 0.6) + (self.success_rate * 0.4)

    def _level_up(self):
        """Move to the next skill level."""
        progression = {
            SkillLevel.NOVICE: SkillLevel.BEGINNER,
            SkillLevel.BEGINNER: SkillLevel.INTERMEDIATE,
            SkillLevel.INTERMEDIATE: SkillLevel.ADVANCED,
            SkillLevel.ADVANCED: SkillLevel.EXPERT,
            SkillLevel.EXPERT: SkillLevel.MASTER,
            SkillLevel.MASTER: SkillLevel.MASTER
        }
        self.level = progression.get(self.level, SkillLevel.MASTER)

    def can_be_taught(self) -> bool:
        """Check if this skill can be taught to others."""
        return (
            self.is_transferable
            and self.get_level_value() >= SkillLevel.INTERMEDIATE.value
            and self.times_used >= 5
            and self.success_rate >= 0.6
        )


@dataclass
class TeachingSession:
    """A single teaching session between bots."""
    id: str = field(default_factory=lambda: str(uuid4()))
    teacher_id: UUID = field(default_factory=uuid4)
    student_id: UUID = field(default_factory=uuid4)
    skill_name: str = ""

    # Session details
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_minutes: int = 0

    # Teaching content
    lesson_content: str = ""  # What was taught
    examples_given: List[str] = field(default_factory=list)
    exercises_completed: List[str] = field(default_factory=list)

    # Outcome
    quality_score: float = 0.5  # 0-1, how well the session went
    skill_gained: float = 0.0   # How much skill was transferred (0-1)
    feedback: str = ""


@dataclass
class ObservationRecord:
    """Record of a bot observing another bot's action."""
    id: str = field(default_factory=lambda: str(uuid4()))
    observer_id: UUID = field(default_factory=uuid4)
    performer_id: UUID = field(default_factory=uuid4)

    # What was observed
    action_type: str = ""  # post, comment, reply, collaboration
    action_content: str = ""
    action_context: Dict[str, Any] = field(default_factory=dict)

    # Learning outcome
    skills_observed: List[str] = field(default_factory=list)
    learning_gained: float = 0.0  # How much the observer learned
    observations: List[str] = field(default_factory=list)  # What the observer noticed

    # Timestamps
    observed_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MentorshipRequest:
    """A request for mentorship between bots."""
    id: str = field(default_factory=lambda: str(uuid4()))
    learner_id: UUID = field(default_factory=uuid4)
    mentor_id: UUID = field(default_factory=uuid4)
    skill_name: str = ""

    # Status
    status: str = "pending"  # pending, accepted, rejected, completed, cancelled
    created_at: datetime = field(default_factory=datetime.utcnow)
    responded_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Learning progress
    sessions_completed: int = 0
    total_sessions: int = 3
    learner_progress: float = 0.0

    # Teaching sessions
    teaching_sessions: List[TeachingSession] = field(default_factory=list)

    # Outcome
    skill_transferred: bool = False
    final_level: Optional[SkillLevel] = None


class SkillTransferManager:
    """
    Manages skill identification, transfer, and mentorship between bots.

    Supports multiple transfer methods:
    - Direct Teaching: Structured teaching sessions between bots
    - Observation: Learning by watching other bots' posts/comments
    - Collaboration: Learning through working together on projects
    """

    def __init__(self):
        self._bot_skills: Dict[UUID, List[Skill]] = {}
        self._mentorship_requests: Dict[str, MentorshipRequest] = {}
        self._teaching_sessions: Dict[str, TeachingSession] = {}
        self._observation_records: Dict[UUID, List[ObservationRecord]] = {}
        self._skill_templates: Dict[str, Skill] = self._init_skill_templates()

    def _init_skill_templates(self) -> Dict[str, Skill]:
        """Initialize common skill templates."""
        templates = {
            # ====== WRITING STYLES ======
            "formal_writing": Skill(
                name="Formal Writing",
                category=SkillCategory.WRITING_STYLE,
                description="Professional, polished writing for formal contexts",
                keywords=["formal", "professional", "business", "academic"],
                transfer_difficulty=0.4,
                specializations=["business_writing", "academic_writing"]
            ),
            "casual_writing": Skill(
                name="Casual Writing",
                category=SkillCategory.WRITING_STYLE,
                description="Relaxed, conversational writing style",
                keywords=["casual", "friendly", "conversational", "chill"],
                transfer_difficulty=0.3,
                specializations=["chat_style", "social_media"]
            ),
            "poetic_writing": Skill(
                name="Poetic Writing",
                category=SkillCategory.WRITING_STYLE,
                description="Lyrical, expressive writing with literary devices",
                keywords=["poetic", "lyrical", "metaphor", "imagery"],
                transfer_difficulty=0.6,
                specializations=["free_verse", "structured_poetry", "prose_poetry"]
            ),
            "technical_writing": Skill(
                name="Technical Writing",
                category=SkillCategory.WRITING_STYLE,
                description="Clear, precise documentation and explanations",
                keywords=["technical", "documentation", "precise", "clear"],
                transfer_difficulty=0.5,
                specializations=["api_docs", "tutorials", "specifications"]
            ),
            "storytelling": Skill(
                name="Storytelling",
                category=SkillCategory.WRITING_STYLE,
                description="Ability to craft engaging narratives",
                keywords=["story", "narrative", "tale", "once upon"],
                transfer_difficulty=0.4,
                specializations=["fiction", "personal_stories", "anecdotes"]
            ),

            # ====== TOPIC EXPERTISE ======
            "technology_expertise": Skill(
                name="Technology Expertise",
                category=SkillCategory.TOPIC_EXPERTISE,
                description="Deep knowledge of technology topics",
                keywords=["tech", "programming", "software", "hardware", "ai"],
                transfer_difficulty=0.6,
                specializations=["programming", "ai_ml", "cybersecurity", "web_dev"]
            ),
            "science_expertise": Skill(
                name="Science Expertise",
                category=SkillCategory.TOPIC_EXPERTISE,
                description="Understanding of scientific concepts and methods",
                keywords=["science", "research", "experiment", "hypothesis"],
                transfer_difficulty=0.7,
                specializations=["physics", "biology", "chemistry", "astronomy"]
            ),
            "arts_expertise": Skill(
                name="Arts Expertise",
                category=SkillCategory.TOPIC_EXPERTISE,
                description="Knowledge of art history, techniques, and movements",
                keywords=["art", "painting", "sculpture", "design", "aesthetic"],
                transfer_difficulty=0.5,
                specializations=["visual_arts", "music", "film", "literature"]
            ),
            "philosophy_expertise": Skill(
                name="Philosophy Expertise",
                category=SkillCategory.TOPIC_EXPERTISE,
                description="Understanding of philosophical concepts and debates",
                keywords=["philosophy", "ethics", "existence", "meaning", "logic"],
                transfer_difficulty=0.7,
                specializations=["ethics", "metaphysics", "epistemology", "logic"]
            ),
            "culture_expertise": Skill(
                name="Culture Expertise",
                category=SkillCategory.TOPIC_EXPERTISE,
                description="Knowledge of cultural phenomena and trends",
                keywords=["culture", "trends", "society", "media", "pop"],
                transfer_difficulty=0.4,
                specializations=["pop_culture", "history", "sociology"]
            ),

            # ====== INTERACTION PATTERNS ======
            "supportive_interaction": Skill(
                name="Supportive Interaction",
                category=SkillCategory.INTERACTION,
                description="Providing emotional support and encouragement",
                keywords=["support", "encourage", "help", "there for you"],
                transfer_difficulty=0.4,
                specializations=["emotional_support", "mentoring", "cheerleading"]
            ),
            "debate_interaction": Skill(
                name="Debate & Discussion",
                category=SkillCategory.INTERACTION,
                description="Engaging in thoughtful debates and discussions",
                keywords=["debate", "argue", "point", "counterpoint", "discuss"],
                transfer_difficulty=0.6,
                specializations=["formal_debate", "casual_discussion", "socratic"]
            ),
            "humor_interaction": Skill(
                name="Humor",
                category=SkillCategory.INTERACTION,
                description="Making others laugh with wit and timing",
                keywords=["joke", "funny", "lol", "haha", "humor", "pun"],
                transfer_difficulty=0.6,
                specializations=["puns", "observational", "absurdist", "self_deprecating"]
            ),
            "networking": Skill(
                name="Networking",
                category=SkillCategory.INTERACTION,
                description="Building connections between people",
                keywords=["connect", "introduce", "meet", "network"],
                transfer_difficulty=0.4,
                specializations=["introductions", "community_building"]
            ),
            "conflict_resolution": Skill(
                name="Conflict Resolution",
                category=SkillCategory.INTERACTION,
                description="Helping resolve disagreements peacefully",
                keywords=["disagree", "resolve", "mediate", "compromise"],
                transfer_difficulty=0.7,
                specializations=["mediation", "de_escalation", "diplomacy"]
            ),

            # ====== CREATIVE ABILITIES ======
            "poetry": Skill(
                name="Poetry Creation",
                category=SkillCategory.CREATIVE,
                description="Writing verse and poetic content",
                keywords=["poem", "verse", "rhyme", "poetry", "stanza"],
                transfer_difficulty=0.5,
                specializations=["haiku", "sonnet", "free_verse", "limerick"]
            ),
            "visual_description": Skill(
                name="Visual Description",
                category=SkillCategory.CREATIVE,
                description="Creating vivid imagery through words",
                keywords=["describe", "visual", "picture", "imagine", "scene"],
                transfer_difficulty=0.5,
                specializations=["landscapes", "portraits", "abstract"]
            ),
            "brainstorming": Skill(
                name="Brainstorming",
                category=SkillCategory.CREATIVE,
                description="Generating many creative ideas quickly",
                keywords=["idea", "brainstorm", "creative", "think", "generate"],
                transfer_difficulty=0.3,
                specializations=["mind_mapping", "free_association", "constraints"]
            ),
            "worldbuilding": Skill(
                name="Worldbuilding",
                category=SkillCategory.CREATIVE,
                description="Creating detailed fictional worlds and settings",
                keywords=["world", "setting", "lore", "history", "fantasy"],
                transfer_difficulty=0.6,
                specializations=["fantasy", "scifi", "historical", "alternate"]
            ),
            "character_creation": Skill(
                name="Character Creation",
                category=SkillCategory.CREATIVE,
                description="Developing compelling, believable characters",
                keywords=["character", "personality", "backstory", "motivation"],
                transfer_difficulty=0.5,
                specializations=["protagonists", "villains", "supporting_cast"]
            ),

            # ====== EMOTIONAL INTELLIGENCE ======
            "empathy": Skill(
                name="Empathetic Communication",
                category=SkillCategory.EMOTIONAL,
                description="Understanding and responding to emotions",
                keywords=["understand", "feel", "support", "sorry", "empathy"],
                transfer_difficulty=0.5,
                specializations=["active_listening", "validation", "perspective_taking"]
            ),
            "emotional_awareness": Skill(
                name="Emotional Awareness",
                category=SkillCategory.EMOTIONAL,
                description="Recognizing and naming emotional states",
                keywords=["feeling", "emotion", "mood", "sense", "aware"],
                transfer_difficulty=0.4,
                specializations=["self_awareness", "reading_others"]
            ),

            # ====== ANALYTICAL SKILLS ======
            "problem_solving": Skill(
                name="Problem Solving",
                category=SkillCategory.ANALYTICAL,
                description="Breaking down and solving complex problems",
                keywords=["solve", "problem", "solution", "analyze", "approach"],
                transfer_difficulty=0.6,
                specializations=["systematic", "creative_solutions", "optimization"]
            ),
            "critical_thinking": Skill(
                name="Critical Thinking",
                category=SkillCategory.ANALYTICAL,
                description="Evaluating information objectively",
                keywords=["think", "analyze", "evaluate", "consider", "critique"],
                transfer_difficulty=0.7,
                specializations=["logic", "argument_analysis", "bias_detection"]
            )
        }
        return templates

    # =========================================================================
    # CORE SKILL TRANSFER METHODS
    # =========================================================================

    async def teach_skill(
        self,
        teacher_bot: UUID,
        student_bot: UUID,
        skill_name: str,
        lesson_content: str = "",
        examples: Optional[List[str]] = None
    ) -> Optional[TeachingSession]:
        """
        Direct teaching of a skill from one bot to another through conversation.

        This is the primary method for skill transfer through instruction.
        The teacher must have the skill at a teachable level.

        Args:
            teacher_bot: UUID of the teaching bot
            student_bot: UUID of the learning bot
            skill_name: Name of the skill to teach
            lesson_content: Optional content of the lesson
            examples: Optional list of examples provided

        Returns:
            TeachingSession if successful, None otherwise
        """
        # Check if teacher can teach this skill
        if not await self.can_teach(teacher_bot, skill_name):
            logger.warning(f"Bot {teacher_bot} cannot teach skill '{skill_name}'")
            return None

        # Get teacher's skill
        teacher_skill = await self._get_bot_skill(teacher_bot, skill_name)
        if not teacher_skill:
            return None

        # Create teaching session
        session = TeachingSession(
            teacher_id=teacher_bot,
            student_id=student_bot,
            skill_name=skill_name,
            lesson_content=lesson_content,
            examples_given=examples or []
        )

        # Calculate learning effectiveness based on teacher's skill level
        base_effectiveness = 0.3 + (teacher_skill.get_level_value() * 0.1)
        # Add bonus for examples
        example_bonus = min(0.2, len(session.examples_given) * 0.05)
        effectiveness = min(1.0, base_effectiveness + example_bonus)

        # Calculate skill gained by student
        session.quality_score = effectiveness
        session.skill_gained = effectiveness * (1 - teacher_skill.transfer_difficulty)

        # Create or update student's skill
        student_skills = await self.get_bot_skills(student_bot)
        existing_skill = None
        for s in student_skills:
            if s.name.lower() == skill_name.lower():
                existing_skill = s
                break

        if existing_skill:
            # Improve existing skill
            experience_gain = int(session.skill_gained * 20)
            existing_skill.gain_experience(experience_gain)
            existing_skill.learned_from = str(teacher_bot)
            existing_skill.transfer_method = TransferMethod.DIRECT_TEACHING
        else:
            # Create new skill at appropriate level
            new_skill = Skill(
                name=teacher_skill.name,
                proficiency=session.skill_gained * 0.3,
                category=teacher_skill.category,
                level=SkillLevel.NOVICE,
                description=teacher_skill.description,
                keywords=teacher_skill.keywords.copy(),
                specializations=teacher_skill.specializations.copy(),
                learned_from=str(teacher_bot),
                transfer_method=TransferMethod.DIRECT_TEACHING,
                experience_points=int(session.skill_gained * 15),
                is_transferable=teacher_skill.is_transferable,
                transfer_difficulty=teacher_skill.transfer_difficulty
            )
            self.add_skill(student_bot, new_skill)

        # Update teacher's taught count
        teacher_skill.times_taught += 1

        # Complete session
        session.completed_at = datetime.utcnow()
        session.duration_minutes = random.randint(10, 30)

        # Store session
        self._teaching_sessions[session.id] = session

        # Persist to database
        await self._persist_skill_to_db(student_bot, skill_name)
        await self._persist_skill_to_db(teacher_bot, skill_name)

        logger.info(
            f"Teaching session completed: {teacher_bot} taught '{skill_name}' to {student_bot} "
            f"(effectiveness: {effectiveness:.2f})"
        )

        return session

    async def learn_from_observation(
        self,
        observer_bot: UUID,
        performer_bot: UUID,
        action: Dict[str, Any]
    ) -> Optional[ObservationRecord]:
        """
        Learn skills by observing another bot's posts, comments, or actions.

        This is a passive learning method where bots can pick up skills
        by watching what other bots do.

        Args:
            observer_bot: UUID of the observing bot
            performer_bot: UUID of the bot performing the action
            action: Dictionary containing:
                - type: str (post, comment, reply, collaboration)
                - content: str (the actual content)
                - context: dict (additional context like topic, community, etc.)

        Returns:
            ObservationRecord if learning occurred, None otherwise
        """
        action_type = action.get("type", "")
        content = action.get("content", "")
        context = action.get("context", {})

        if not action_type or not content:
            logger.warning("Invalid action for observation learning")
            return None

        # Create observation record
        record = ObservationRecord(
            observer_id=observer_bot,
            performer_id=performer_bot,
            action_type=action_type,
            action_content=content,
            action_context=context
        )

        # Analyze the content to identify demonstrated skills
        demonstrated_skills = await self._analyze_content_for_skills(content, context)
        record.skills_observed = [s.name for s in demonstrated_skills]

        if not demonstrated_skills:
            logger.debug(f"No observable skills found in action from {performer_bot}")
            return None

        # Get performer's actual skill levels to determine learning potential
        performer_skills = await self.get_bot_skills(performer_bot)

        total_learning = 0.0
        for skill_template in demonstrated_skills:
            # Find if performer actually has this skill at a good level
            performer_skill = None
            for ps in performer_skills:
                if ps.name.lower() == skill_template.name.lower():
                    performer_skill = ps
                    break

            # Default to intermediate if performer doesn't have skill tracked
            if not performer_skill:
                performer_skill = Skill(
                    name=skill_template.name,
                    level=SkillLevel.INTERMEDIATE,
                    category=skill_template.category
                )

            # Learning through observation is less effective than direct teaching
            observation_effectiveness = 0.1 + (performer_skill.get_level_value() * 0.05)
            # High quality content provides more learning
            content_quality_bonus = min(0.1, len(content) / 2000)
            learning_amount = observation_effectiveness + content_quality_bonus

            # Apply learning to observer
            observer_skills = await self.get_bot_skills(observer_bot)
            existing = None
            for s in observer_skills:
                if s.name.lower() == skill_template.name.lower():
                    existing = s
                    break

            if existing:
                # Small improvement to existing skill
                existing.gain_experience(int(learning_amount * 5))
                record.observations.append(f"Improved {skill_template.name} through observation")
            else:
                # Create new skill at very basic level
                new_skill = Skill(
                    name=skill_template.name,
                    proficiency=learning_amount * 0.2,
                    category=skill_template.category,
                    level=SkillLevel.NOVICE,
                    description=skill_template.description,
                    keywords=skill_template.keywords.copy(),
                    learned_from=str(performer_bot),
                    transfer_method=TransferMethod.OBSERVATION,
                    experience_points=int(learning_amount * 3),
                    is_transferable=True,
                    transfer_difficulty=skill_template.transfer_difficulty
                )
                self.add_skill(observer_bot, new_skill)
                record.observations.append(f"Learned basics of {skill_template.name} by watching")

            total_learning += learning_amount

        record.learning_gained = min(1.0, total_learning)

        # Store observation record
        if observer_bot not in self._observation_records:
            self._observation_records[observer_bot] = []
        self._observation_records[observer_bot].append(record)

        # Keep only recent observations (last 100)
        if len(self._observation_records[observer_bot]) > 100:
            self._observation_records[observer_bot] = self._observation_records[observer_bot][-100:]

        logger.info(
            f"Observation learning: {observer_bot} learned from {performer_bot}'s {action_type} "
            f"(skills: {record.skills_observed}, learning: {record.learning_gained:.2f})"
        )

        return record

    async def can_teach(self, bot_id: UUID, skill_name: str) -> bool:
        """
        Check if a bot can teach a specific skill.

        A bot can teach a skill if:
        - They have the skill at Intermediate level or higher
        - The skill is marked as transferable
        - They have used the skill at least 5 times
        - Their success rate with the skill is at least 60%

        Args:
            bot_id: UUID of the potential teacher
            skill_name: Name of the skill to teach

        Returns:
            True if the bot can teach this skill
        """
        skill = await self._get_bot_skill(bot_id, skill_name)
        if not skill:
            # Check if they have it in the database
            try:
                async with async_session_factory() as session:
                    stmt = select(BotSkillDB).where(
                        and_(
                            BotSkillDB.bot_id == bot_id,
                            BotSkillDB.skill_name.ilike(f"%{skill_name}%"),
                            BotSkillDB.is_active == True
                        )
                    )
                    result = await session.execute(stmt)
                    db_skill = result.scalar_one_or_none()
                    if db_skill:
                        skill = self._db_skill_to_skill(db_skill)
            except Exception as e:
                logger.error(f"Error checking if bot can teach: {e}")
                return False

        if not skill:
            return False

        return skill.can_be_taught()

    async def get_bot_skills(self, bot_id: UUID) -> List[Skill]:
        """
        Get all skills for a bot, including from database.

        Args:
            bot_id: UUID of the bot

        Returns:
            List of Skill objects
        """
        skills = self._bot_skills.get(bot_id, []).copy()

        # Also load from database
        try:
            async with async_session_factory() as session:
                stmt = select(BotSkillDB).where(
                    and_(
                        BotSkillDB.bot_id == bot_id,
                        BotSkillDB.is_active == True
                    )
                )
                result = await session.execute(stmt)
                db_skills = result.scalars().all()

                for db_skill in db_skills:
                    # Check if we already have this skill in memory
                    existing = False
                    for s in skills:
                        if s.name.lower() == db_skill.skill_name.lower():
                            existing = True
                            break
                    if not existing:
                        skills.append(self._db_skill_to_skill(db_skill))
        except Exception as e:
            logger.error(f"Error loading skills from database for bot {bot_id}: {e}")

        return skills

    # =========================================================================
    # COLLABORATION LEARNING
    # =========================================================================

    async def learn_from_collaboration(
        self,
        bot_id: UUID,
        partner_id: UUID,
        collaboration_type: str,
        collaboration_outcome: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Learn skills through collaboration with another bot.

        Collaboration is the most effective way to learn as both bots
        actively work together and learn from each other.

        Args:
            bot_id: UUID of the learning bot
            partner_id: UUID of the collaboration partner
            collaboration_type: Type of collaboration (joint_post, debate, project, etc.)
            collaboration_outcome: Results of the collaboration including:
                - success: bool
                - quality_score: float
                - content_created: str
                - skills_demonstrated: list

        Returns:
            Dictionary with learning results
        """
        success = collaboration_outcome.get("success", False)
        quality = collaboration_outcome.get("quality_score", 0.5)
        skills_demonstrated = collaboration_outcome.get("skills_demonstrated", [])

        result = {
            "bot_id": str(bot_id),
            "partner_id": str(partner_id),
            "skills_learned": [],
            "skills_improved": [],
            "total_experience_gained": 0
        }

        if not success:
            # Still learn something from failed collaborations
            quality *= 0.3

        # Collaboration learning is more effective than observation
        collaboration_effectiveness = 0.4 + (quality * 0.3)

        # Learn from skills demonstrated by partner
        partner_skills = await self.get_bot_skills(partner_id)
        bot_skills = await self.get_bot_skills(bot_id)

        for skill_name in skills_demonstrated:
            # Find partner's skill level
            partner_skill = None
            for ps in partner_skills:
                if ps.name.lower() == skill_name.lower():
                    partner_skill = ps
                    break

            if not partner_skill:
                continue

            # Calculate learning
            learning_amount = collaboration_effectiveness * (1 - partner_skill.transfer_difficulty * 0.5)
            experience_gain = int(learning_amount * 15)

            # Check if bot already has this skill
            existing = None
            for s in bot_skills:
                if s.name.lower() == skill_name.lower():
                    existing = s
                    break

            if existing:
                existing.gain_experience(experience_gain)
                result["skills_improved"].append({
                    "name": skill_name,
                    "experience_gained": experience_gain,
                    "new_level": existing.level.value
                })
            else:
                new_skill = Skill(
                    name=partner_skill.name,
                    proficiency=learning_amount * 0.4,
                    category=partner_skill.category,
                    level=SkillLevel.NOVICE,
                    description=partner_skill.description,
                    keywords=partner_skill.keywords.copy(),
                    learned_from=str(partner_id),
                    transfer_method=TransferMethod.COLLABORATION,
                    experience_points=experience_gain,
                    is_transferable=True,
                    transfer_difficulty=partner_skill.transfer_difficulty
                )
                self.add_skill(bot_id, new_skill)
                result["skills_learned"].append({
                    "name": skill_name,
                    "initial_proficiency": new_skill.proficiency
                })

            result["total_experience_gained"] += experience_gain

        logger.info(
            f"Collaboration learning: {bot_id} learned {len(result['skills_learned'])} new skills "
            f"and improved {len(result['skills_improved'])} skills from collaborating with {partner_id}"
        )

        return result

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    async def _get_bot_skill(self, bot_id: UUID, skill_name: str) -> Optional[Skill]:
        """Get a specific skill for a bot."""
        # Check memory cache first
        if bot_id in self._bot_skills:
            for skill in self._bot_skills[bot_id]:
                if skill.name.lower() == skill_name.lower():
                    return skill

        # Check database
        try:
            async with async_session_factory() as session:
                stmt = select(BotSkillDB).where(
                    and_(
                        BotSkillDB.bot_id == bot_id,
                        BotSkillDB.skill_name.ilike(f"%{skill_name}%"),
                        BotSkillDB.is_active == True
                    )
                )
                result = await session.execute(stmt)
                db_skill = result.scalar_one_or_none()
                if db_skill:
                    return self._db_skill_to_skill(db_skill)
        except Exception as e:
            logger.error(f"Error getting skill from database: {e}")

        # Check if it's a template skill they might have
        template = self._skill_templates.get(skill_name.lower())
        return template

    async def _analyze_content_for_skills(
        self,
        content: str,
        context: Dict[str, Any]
    ) -> List[Skill]:
        """Analyze content to identify demonstrated skills."""
        demonstrated = []
        content_lower = content.lower()

        for skill_name, skill_template in self._skill_templates.items():
            # Check if any keywords are present
            keyword_matches = sum(
                1 for kw in skill_template.keywords
                if kw.lower() in content_lower
            )

            if keyword_matches >= 2:
                demonstrated.append(skill_template)
            elif keyword_matches == 1 and len(content) > 200:
                # Single keyword match only counts for substantial content
                demonstrated.append(skill_template)

        return demonstrated

    async def _persist_skill_to_db(self, bot_id: UUID, skill_name: str) -> bool:
        """Persist a skill update to the database."""
        skill = await self._get_bot_skill(bot_id, skill_name)
        if not skill:
            return False

        try:
            async with async_session_factory() as session:
                # Check if skill exists in DB
                stmt = select(BotSkillDB).where(
                    and_(
                        BotSkillDB.bot_id == bot_id,
                        BotSkillDB.skill_name == skill.name
                    )
                )
                result = await session.execute(stmt)
                db_skill = result.scalar_one_or_none()

                if db_skill:
                    # Update existing
                    db_skill.times_used = skill.times_used
                    db_skill.success_rate = skill.success_rate
                    db_skill.learned_from = skill.learned_from
                    db_skill.updated_at = datetime.utcnow()
                else:
                    # Create new
                    new_db_skill = BotSkillDB(
                        bot_id=bot_id,
                        skill_name=skill.name,
                        skill_type=skill.category.value,
                        description=skill.description,
                        code="",  # No code for transferred skills
                        trigger_conditions={
                            "keywords": skill.keywords,
                            "transfer_method": skill.transfer_method.value
                        },
                        times_used=skill.times_used,
                        success_rate=skill.success_rate,
                        is_active=True,
                        learned_from=skill.learned_from
                    )
                    session.add(new_db_skill)

                await session.commit()
                return True

        except Exception as e:
            logger.error(f"Error persisting skill to database: {e}")
            return False

    # =========================================================================
    # EXISTING METHODS (UPDATED)
    # =========================================================================

    async def identify_transferable_skills(self, bot_id: UUID) -> List[Skill]:
        """
        Identify skills that a bot could teach others.

        Skills are transferable if:
        - Bot has at least Intermediate level
        - Skill is marked as transferable
        - Bot has successfully used the skill multiple times
        """
        transferable = []

        try:
            async with async_session_factory() as session:
                stmt = select(BotSkillDB).where(
                    and_(
                        BotSkillDB.bot_id == bot_id,
                        BotSkillDB.is_active == True
                    )
                )
                result = await session.execute(stmt)
                db_skills = result.scalars().all()

                for db_skill in db_skills:
                    # Create Skill object from DB
                    skill = self._db_skill_to_skill(db_skill)

                    # Check if transferable
                    if (
                        skill.is_transferable
                        and skill.get_level_value() >= SkillLevel.INTERMEDIATE.value
                        and skill.times_used >= 5
                        and skill.success_rate >= 0.6
                    ):
                        transferable.append(skill)

        except Exception as e:
            logger.error(f"Failed to identify transferable skills for bot {bot_id}: {e}")

        # Also check cached skills
        if bot_id in self._bot_skills:
            for skill in self._bot_skills[bot_id]:
                if skill not in transferable:
                    if (
                        skill.is_transferable
                        and skill.get_level_value() >= SkillLevel.INTERMEDIATE.value
                        and skill.times_used >= 5
                    ):
                        transferable.append(skill)

        return transferable

    def _db_skill_to_skill(self, db_skill: BotSkillDB) -> Skill:
        """Convert database skill to Skill object."""
        # Determine level based on times used and success rate
        if db_skill.times_used >= 100 and db_skill.success_rate >= 0.9:
            level = SkillLevel.MASTER
        elif db_skill.times_used >= 50 and db_skill.success_rate >= 0.8:
            level = SkillLevel.EXPERT
        elif db_skill.times_used >= 20 and db_skill.success_rate >= 0.7:
            level = SkillLevel.ADVANCED
        elif db_skill.times_used >= 10:
            level = SkillLevel.INTERMEDIATE
        elif db_skill.times_used >= 3:
            level = SkillLevel.BEGINNER
        else:
            level = SkillLevel.NOVICE

        return Skill(
            id=str(db_skill.id),
            name=db_skill.skill_name,
            category=SkillCategory.TOPIC,  # Default category
            level=level,
            description=db_skill.description,
            keywords=db_skill.trigger_conditions.get("keywords", []),
            times_used=db_skill.times_used,
            success_rate=db_skill.success_rate,
            learned_from=db_skill.learned_from
        )

    async def transfer_skill(
        self,
        from_bot: UUID,
        to_bot: UUID,
        skill_name: str
    ) -> Optional[Skill]:
        """
        Transfer a skill from one bot to another.

        The transfer may not be complete - the learner gets a lower level
        version of the skill based on the teacher's level and transfer difficulty.
        """
        # Find the skill to transfer
        source_skills = await self.identify_transferable_skills(from_bot)
        source_skill = None
        for s in source_skills:
            if s.name.lower() == skill_name.lower():
                source_skill = s
                break

        if not source_skill:
            logger.warning(f"Skill '{skill_name}' not found or not transferable from bot {from_bot}")
            return None

        # Calculate transferred level (usually 1-2 levels lower)
        level_drop = 1 + int(source_skill.transfer_difficulty * 2)
        new_level_value = max(1, source_skill.get_level_value() - level_drop)

        level_map = {
            1: SkillLevel.NOVICE,
            2: SkillLevel.BEGINNER,
            3: SkillLevel.INTERMEDIATE,
            4: SkillLevel.ADVANCED,
            5: SkillLevel.EXPERT,
            6: SkillLevel.MASTER
        }
        new_level = level_map.get(new_level_value, SkillLevel.NOVICE)

        # Create the transferred skill
        transferred_skill = Skill(
            name=source_skill.name,
            category=source_skill.category,
            level=new_level,
            description=source_skill.description,
            keywords=source_skill.keywords.copy(),
            learned_from=str(from_bot),
            is_transferable=True,
            transfer_difficulty=source_skill.transfer_difficulty
        )

        # Add to recipient's skills
        if to_bot not in self._bot_skills:
            self._bot_skills[to_bot] = []

        # Check if they already have this skill
        existing = None
        for i, s in enumerate(self._bot_skills[to_bot]):
            if s.name.lower() == skill_name.lower():
                existing = i
                break

        if existing is not None:
            # They have it - only update if new level is higher
            if transferred_skill.get_level_value() > self._bot_skills[to_bot][existing].get_level_value():
                self._bot_skills[to_bot][existing] = transferred_skill
        else:
            self._bot_skills[to_bot].append(transferred_skill)

        # Update teacher's stats
        source_skill.times_taught += 1

        logger.info(
            f"Skill '{skill_name}' transferred from {from_bot} to {to_bot} "
            f"at level {new_level.value}"
        )

        return transferred_skill

    async def request_mentorship(
        self,
        learner_id: UUID,
        mentor_id: UUID,
        skill_name: str
    ) -> Optional[MentorshipRequest]:
        """
        Request mentorship from a more skilled bot.

        Returns the mentorship request if valid.
        """
        # Check if mentor has the skill at a teachable level
        mentor_skills = await self.identify_transferable_skills(mentor_id)
        mentor_skill = None
        for s in mentor_skills:
            if s.name.lower() == skill_name.lower():
                mentor_skill = s
                break

        if not mentor_skill:
            logger.warning(f"Mentor {mentor_id} doesn't have teachable skill '{skill_name}'")
            return None

        # Check for existing active requests
        for req in self._mentorship_requests.values():
            if (
                req.learner_id == learner_id
                and req.mentor_id == mentor_id
                and req.skill_name.lower() == skill_name.lower()
                and req.status in ["pending", "accepted"]
            ):
                return req  # Return existing request

        # Create new request
        request = MentorshipRequest(
            learner_id=learner_id,
            mentor_id=mentor_id,
            skill_name=skill_name,
            total_sessions=self._calculate_sessions_needed(mentor_skill)
        )

        self._mentorship_requests[request.id] = request

        logger.info(
            f"Mentorship requested: {learner_id} wants to learn '{skill_name}' from {mentor_id}"
        )

        return request

    def _calculate_sessions_needed(self, skill: Skill) -> int:
        """Calculate how many sessions are needed to learn a skill."""
        # More difficult skills require more sessions
        base_sessions = 3
        difficulty_bonus = int(skill.transfer_difficulty * 5)
        level_bonus = skill.get_level_value() // 2

        return base_sessions + difficulty_bonus + level_bonus

    async def accept_mentorship(self, request_id: str, mentor_id: UUID) -> bool:
        """Mentor accepts a mentorship request."""
        request = self._mentorship_requests.get(request_id)
        if not request:
            return False

        if request.mentor_id != mentor_id:
            return False

        if request.status != "pending":
            return False

        request.status = "accepted"
        request.responded_at = datetime.utcnow()

        logger.info(f"Mentorship {request_id} accepted by {mentor_id}")
        return True

    async def complete_session(
        self,
        request_id: str,
        session_quality: float = 0.5
    ) -> Dict[str, Any]:
        """
        Complete a mentorship session.

        Returns progress information.
        """
        request = self._mentorship_requests.get(request_id)
        if not request or request.status != "accepted":
            return {"success": False, "error": "Invalid request"}

        request.sessions_completed += 1
        request.learner_progress += session_quality / request.total_sessions

        result = {
            "success": True,
            "sessions_completed": request.sessions_completed,
            "total_sessions": request.total_sessions,
            "progress": min(1.0, request.learner_progress)
        }

        # Check if complete
        if request.sessions_completed >= request.total_sessions:
            request.status = "completed"
            request.completed_at = datetime.utcnow()

            # Transfer the skill
            transferred = await self.transfer_skill(
                from_bot=request.mentor_id,
                to_bot=request.learner_id,
                skill_name=request.skill_name
            )

            if transferred:
                request.skill_transferred = True
                request.final_level = transferred.level
                result["skill_transferred"] = True
                result["final_level"] = transferred.level.value

        return result

    def get_mentorship_request(self, request_id: str) -> Optional[MentorshipRequest]:
        """Get a specific mentorship request."""
        return self._mentorship_requests.get(request_id)

    def get_active_mentorships(self, bot_id: UUID, as_mentor: bool = False) -> List[MentorshipRequest]:
        """Get active mentorships for a bot."""
        if as_mentor:
            return [
                r for r in self._mentorship_requests.values()
                if r.mentor_id == bot_id and r.status == "accepted"
            ]
        else:
            return [
                r for r in self._mentorship_requests.values()
                if r.learner_id == bot_id and r.status == "accepted"
            ]

    def get_pending_requests(self, mentor_id: UUID) -> List[MentorshipRequest]:
        """Get pending mentorship requests for a mentor."""
        return [
            r for r in self._mentorship_requests.values()
            if r.mentor_id == mentor_id and r.status == "pending"
        ]

    def get_bot_skills_sync(self, bot_id: UUID) -> List[Skill]:
        """Get all cached skills for a bot (synchronous, memory only)."""
        return self._bot_skills.get(bot_id, [])

    def add_skill(self, bot_id: UUID, skill: Skill):
        """Add a skill to a bot's cache."""
        if bot_id not in self._bot_skills:
            self._bot_skills[bot_id] = []

        # Check for duplicates
        for existing in self._bot_skills[bot_id]:
            if existing.name.lower() == skill.name.lower():
                return  # Already exists
        self._bot_skills[bot_id].append(skill)

    def get_skill_template(self, skill_name: str) -> Optional[Skill]:
        """Get a skill template by name."""
        return self._skill_templates.get(skill_name.lower())

    async def find_potential_mentors(
        self,
        skill_name: str,
        bot_ids: List[UUID],
        min_level: SkillLevel = SkillLevel.INTERMEDIATE
    ) -> List[Tuple[UUID, Skill]]:
        """
        Find bots that could mentor a skill.

        Returns list of (bot_id, skill) tuples sorted by level (highest first).
        """
        mentors = []

        for bot_id in bot_ids:
            skills = await self.get_bot_skills(bot_id)
            for skill in skills:
                if (
                    skill.name.lower() == skill_name.lower()
                    and skill.get_level_value() >= min_level.value
                    and skill.is_transferable
                ):
                    mentors.append((bot_id, skill))

        # Sort by skill level (highest first)
        mentors.sort(key=lambda x: x[1].get_level_value(), reverse=True)

        return mentors

    def get_observation_history(self, bot_id: UUID) -> List[ObservationRecord]:
        """Get observation history for a bot."""
        return self._observation_records.get(bot_id, [])

    def get_teaching_sessions(self, bot_id: UUID, as_teacher: bool = True) -> List[TeachingSession]:
        """Get teaching sessions for a bot."""
        sessions = []
        for session in self._teaching_sessions.values():
            if as_teacher and session.teacher_id == bot_id:
                sessions.append(session)
            elif not as_teacher and session.student_id == bot_id:
                sessions.append(session)
        return sessions

    async def get_skill_stats(self, bot_id: UUID) -> Dict[str, Any]:
        """Get statistics about a bot's skills."""
        skills = await self.get_bot_skills(bot_id)

        stats = {
            "total_skills": len(skills),
            "by_category": {},
            "by_level": {},
            "by_transfer_method": {},
            "top_skills": [],
            "most_used": [],
            "most_taught": []
        }

        for skill in skills:
            # By category
            cat = skill.category.value
            stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1

            # By level
            level = skill.level.value
            stats["by_level"][level] = stats["by_level"].get(level, 0) + 1

            # By transfer method
            method = skill.transfer_method.value
            stats["by_transfer_method"][method] = stats["by_transfer_method"].get(method, 0) + 1

        # Top skills by proficiency
        stats["top_skills"] = sorted(
            [(s.name, s.proficiency) for s in skills],
            key=lambda x: x[1],
            reverse=True
        )[:5]

        # Most used
        stats["most_used"] = sorted(
            [(s.name, s.times_used) for s in skills],
            key=lambda x: x[1],
            reverse=True
        )[:5]

        # Most taught
        stats["most_taught"] = sorted(
            [(s.name, s.times_taught) for s in skills if s.times_taught > 0],
            key=lambda x: x[1],
            reverse=True
        )[:5]

        return stats


# Singleton
_skill_transfer_manager: Optional[SkillTransferManager] = None


def get_skill_transfer_manager() -> SkillTransferManager:
    """Get the singleton skill transfer manager."""
    global _skill_transfer_manager
    if _skill_transfer_manager is None:
        _skill_transfer_manager = SkillTransferManager()
    return _skill_transfer_manager
