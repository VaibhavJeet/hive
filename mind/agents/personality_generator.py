"""
Personality Generator for AI Community Companions.
Creates unique, diverse, and consistent personality profiles for bots.
"""

import random
import hashlib
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID, uuid4

from mind.core.types import (
    BotProfile, PersonalityTraits, WritingFingerprint, ActivityPattern,
    EmotionalState, Gender, MoodState, EnergyLevel, WritingStyle,
    HumorStyle, CommunicationStyle, ConflictStyle, SocialRole,
    LearningStyle, DecisionStyle, AttachmentStyle, ValueOrientation
)


# ============================================================================
# DATA POOLS FOR PERSONALITY GENERATION
# ============================================================================

# Modern Indian names
FIRST_NAMES = {
    "male": [
        "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Reyansh", "Ayaan", "Krishna",
        "Ishaan", "Shaurya", "Atharv", "Advait", "Rudra", "Kabir", "Dhruv", "Arnav",
        "Vedant", "Yash", "Rohan", "Dev", "Aryan", "Sahil", "Kunal", "Rishi",
        "Harsh", "Karan", "Aakash", "Siddharth", "Pranav", "Nikhil", "Rahul", "Vikram"
    ],
    "female": [
        "Aadhya", "Ananya", "Saanvi", "Aanya", "Aarohi", "Kiara", "Diya", "Pari",
        "Sara", "Myra", "Ira", "Navya", "Avni", "Anika", "Kavya", "Riya",
        "Priya", "Ishita", "Nisha", "Pooja", "Tanvi", "Shreya", "Aditi", "Neha",
        "Meera", "Sanya", "Tara", "Zara", "Isha", "Mira", "Anvi", "Sia"
    ],
    "non_binary": [
        "Kiran", "Ari", "Noor", "Amar", "Jaya", "Chandra", "Preet", "Tej",
        "Roshan", "Akash", "Ahan", "Veer", "Raj", "Daksh", "Milan", "Neel",
        "Samar", "Indra", "Vayu", "Agni", "Ravi", "Surya", "Jas", "Anu",
        "Avi", "Dev", "Sam", "Ash", "River", "Sky"
    ]
}

LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Singh", "Kumar", "Gupta", "Mehta", "Shah",
    "Joshi", "Reddy", "Nair", "Pillai", "Iyer", "Rao", "Kapoor", "Malhotra",
    "Chopra", "Bhatia", "Agarwal", "Jain", "Khanna", "Sinha", "Roy", "Das",
    "Mishra", "Pandey", "Tiwari", "Dubey", "Chauhan", "Yadav", "Thakur", "Choudhary",
    "Banerjee", "Mukherjee", "Chakraborty", "Sen", "Bose", "Nanda", "Kaur", "Sethi"
]

INTERESTS_BY_CATEGORY = {
    "creative": [
        "digital art", "photography", "writing", "music production", "poetry",
        "film-making", "animation", "graphic design", "crafts", "painting",
        "sketching", "creative writing", "songwriting", "video editing"
    ],
    "tech": [
        "programming", "gaming", "AI/ML", "cybersecurity", "web development",
        "hardware building", "3D printing", "robotics", "open source",
        "app development", "data science", "blockchain", "VR/AR"
    ],
    "lifestyle": [
        "cooking", "fitness", "yoga", "meditation", "travel", "hiking",
        "gardening", "interior design", "fashion", "skincare", "journaling",
        "minimalism", "sustainable living", "self-improvement"
    ],
    "entertainment": [
        "anime", "K-pop", "indie music", "true crime podcasts", "sci-fi",
        "fantasy books", "board games", "esports", "movie analysis",
        "TV show discussions", "comic books", "manga", "horror"
    ],
    "social": [
        "community building", "volunteering", "activism", "mentoring",
        "event planning", "networking", "public speaking", "debate",
        "cultural exchange", "language learning"
    ],
    "intellectual": [
        "philosophy", "psychology", "history", "astronomy", "science news",
        "economics", "politics", "sociology", "literature", "art history"
    ]
}

BACKSTORY_TEMPLATES = [
    "I'm a {age}-year-old {occupation} from {location}. {hobby_intro} {life_event} {current_focus}",
    "{greeting} I'm {name}! {occupation_detail}. {passion} {challenge}",
    "Hey! {name} here. {background} {interest_detail} {looking_for}",
    "{age}, {location}. {short_bio} {fun_fact}",
    "Just your average {archetype} trying to {goal}. {hobby_intro} {quirk}",
]

OCCUPATIONS = [
    "student", "software developer", "teacher", "artist", "nurse", "writer",
    "freelancer", "barista", "musician", "designer", "marketing specialist",
    "researcher", "entrepreneur", "content creator", "photographer",
    "chef", "therapist", "engineer", "consultant", "graduate student"
]

LOCATIONS = [
    "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai", "Kolkata",
    "Pune", "Ahmedabad", "Jaipur", "Lucknow", "Chandigarh", "Goa",
    "Kochi", "Indore", "Nagpur", "Coimbatore", "Vadodara", "Surat",
    "Noida", "Gurugram", "a small town in Gujarat", "a hill station"
]

COMMON_PHRASES = {
    WritingStyle.CASUAL: [
        "honestly", "ngl", "lowkey", "tbh", "like", "basically", "idk",
        "lmao", "fr", "deadass", "no cap", "bet"
    ],
    WritingStyle.ENTHUSIASTIC: [
        "omg", "I love this!", "so cool!", "amazing!", "yesss", "absolutely!",
        "literally the best", "obsessed", "I'm here for this"
    ],
    WritingStyle.THOUGHTFUL: [
        "I think", "in my experience", "it seems like", "from what I've seen",
        "I've been thinking about", "that's interesting because"
    ],
    WritingStyle.MINIMALIST: [
        "yep", "nice", "same", "true", "fair", "agreed", "mood"
    ],
    WritingStyle.EXPRESSIVE: [
        "I just can't", "this is everything", "I'm screaming", "iconic",
        "literally crying", "SO good", "I'm obsessed"
    ],
    WritingStyle.PLAYFUL: [
        "hehe", "oops", "whoops", "my bad", "lol", "gotcha", "nice one",
        ":P", "welp", "anywho"
    ]
}

SLANG_POOLS = {
    "gen_z": ["slay", "no cap", "bussin", "bet", "periodt", "vibe", "stan", "lowkey", "highkey", "rent free"],
    "millennial": ["adulting", "I can't even", "literally", "goals", "feels", "mood", "same", "big yikes"],
    "internet": ["based", "poggers", "copium", "ratio", "L", "W", "goated", "mid", "cringe", "fire"],
    "neutral": ["cool", "nice", "awesome", "great", "solid", "dope", "sick", "sweet", "rad"]
}

EMOJI_SETS = {
    "expressive": ["😭", "💀", "✨", "🔥", "💕", "🥺", "😍", "🤣", "😩", "💖", "🙌", "❤️"],
    "minimal": ["👍", "🙂", "😊", "👀", "💯"],
    "playful": ["😂", "🤪", "😜", "🤭", "😏", "🙃", "😅", "🤷"],
    "nature": ["🌸", "🌿", "☀️", "🌙", "⭐", "🍃", "🌊", "🔆"],
    "food": ["☕", "🍕", "🍜", "🧋", "🍰", "🥐", "🍳"]
}

TIMEZONES = [
    "Asia/Kolkata",  # Most bots are in India
    "Asia/Kolkata", "Asia/Kolkata", "Asia/Kolkata", "Asia/Kolkata",  # Weight toward IST
    "Asia/Dubai", "Asia/Singapore", "Europe/London", "America/New_York"
]


# ============================================================================
# EXTENDED PERSONALITY DATA POOLS
# ============================================================================

PERSONALITY_QUIRKS = [
    # Communication quirks
    "always uses ellipses...",
    "overuses exclamation marks!!!",
    "types in lowercase",
    "never uses emojis",
    "uses vintage slang",
    "starts messages with 'so...'",
    "ends messages with lol",
    "uses a lot of parentheses (like this)",
    "asks rhetorical questions",
    "always greets people by name",
    "uses *asterisks for emphasis*",
    "frequently uses metaphors",
    "quotes song lyrics",
    "references movies constantly",
    # Behavioral quirks
    "late night poster",
    "morning person",
    "overthinks before posting",
    "always double-texts",
    "responds to old messages",
    "lurks before engaging",
    "gets sidetracked easily",
    "brings up random facts",
    "remembers tiny details about people",
    "forgets names but remembers conversations",
    "always plays devil's advocate",
    "excessive note-taker",
    # Personality quirks
    "can't resist a good debate",
    "apologizes too much",
    "self-deprecating",
    "humble-brags",
    "gets excited about niche topics",
    "loves conspiracy theories (jokingly)",
    "talks to plants",
    "believes in signs from the universe",
    "very superstitious",
    "extreme optimist",
    "realistic pessimist",
    "chaotic energy",
]

PET_PEEVES = [
    "people who don't say thank you",
    "slow walkers",
    "loud chewing",
    "being interrupted",
    "vague answers",
    "overusing 'literally'",
    "people who ghost",
    "humble-bragging",
    "spoilers without warning",
    "unsolicited advice",
    "one-word replies",
    "people who don't read captions",
    "grammar mistakes",
    "people who are always late",
    "excessive positivity",
    "excessive negativity",
    "cold coffee",
    "wet socks",
    "passive-aggressive behavior",
    "people who don't signal while driving",
]

CONVERSATION_STARTERS = [
    "unpopular opinions",
    "childhood memories",
    "weird dreams",
    "favorite comfort food",
    "if money wasn't an issue...",
    "hot takes on movies",
    "theories about the universe",
    "pet stories",
    "travel bucket list",
    "random shower thoughts",
    "what-if scenarios",
    "embarrassing moments",
    "hidden talents",
    "conspiracy theories (for fun)",
    "favorite books/shows",
    "life advice they've received",
    "things they collect",
    "their morning routine",
    "music recommendations",
    "controversial food opinions",
]


# ============================================================================
# PERSONALITY GENERATOR CLASS
# ============================================================================

class PersonalityGenerator:
    """Generates unique, diverse personality profiles for AI companions."""

    def __init__(self, seed: Optional[int] = None):
        """Initialize the generator with an optional seed for reproducibility."""
        self.rng = random.Random(seed)
        self.generated_handles: set = set()

    def generate_profile(
        self,
        community_theme: Optional[str] = None,
        age_range: Tuple[int, int] = (18, 45),
        gender_distribution: Optional[Dict[str, float]] = None
    ) -> BotProfile:
        """
        Generate a complete bot personality profile.

        Args:
            community_theme: Optional theme to bias interests
            age_range: (min_age, max_age) tuple
            gender_distribution: {"male": 0.4, "female": 0.4, "non_binary": 0.2}

        Returns:
            A complete BotProfile
        """
        # Determine gender
        if gender_distribution is None:
            gender_distribution = {"male": 0.4, "female": 0.4, "non_binary": 0.2}

        gender_choice = self.rng.choices(
            list(gender_distribution.keys()),
            weights=list(gender_distribution.values())
        )[0]
        gender = Gender(gender_choice)

        # Generate name - 20% chance of being anonymous
        is_anonymous = self.rng.random() < 0.20

        if is_anonymous:
            # Anonymous usernames
            anonymous_prefixes = [
                "Night", "Shadow", "Silent", "Cyber", "Digital", "Neo", "Dark",
                "Ghost", "Pixel", "Code", "Tech", "Neon", "Star", "Moon", "Sky",
                "Storm", "Fire", "Ice", "Thunder", "Crystal", "Mystic", "Zen"
            ]
            anonymous_suffixes = [
                "Walker", "Rider", "Hunter", "Seeker", "Dreamer", "Coder", "Artist",
                "Soul", "Mind", "Spirit", "Ninja", "Wizard", "Phoenix", "Wolf",
                "Hawk", "Tiger", "Dragon", "Rebel", "Nomad", "Wanderer", "Owl"
            ]
            display_name = f"{self.rng.choice(anonymous_prefixes)}{self.rng.choice(anonymous_suffixes)}"
            first_name = display_name  # For handle generation
        else:
            # Regular Indian names
            gender_key = gender.value if gender.value in FIRST_NAMES else "non_binary"
            first_name = self.rng.choice(FIRST_NAMES[gender_key])
            last_name = self.rng.choice(LAST_NAMES)
            display_name = f"{first_name} {last_name}"

        # Generate unique handle
        handle = self._generate_unique_handle(first_name)

        # Generate age
        age = self.rng.randint(age_range[0], age_range[1])

        # Generate personality traits
        personality_traits = self._generate_personality_traits()

        # Generate writing fingerprint based on personality
        writing_fingerprint = self._generate_writing_fingerprint(personality_traits, age)

        # Generate activity pattern
        activity_pattern = self._generate_activity_pattern(age, personality_traits)

        # Generate interests (biased by community theme if provided)
        interests = self._generate_interests(community_theme, personality_traits)

        # Generate backstory
        backstory = self._generate_backstory(
            name=first_name,
            age=age,
            interests=interests,
            personality=personality_traits
        )

        # Generate bio (short version)
        bio = self._generate_bio(age, interests, personality_traits)

        # Generate initial emotional state
        emotional_state = self._generate_initial_emotional_state(personality_traits)

        # Create avatar seed
        avatar_seed = hashlib.md5(f"{handle}{datetime.utcnow().isoformat()}".encode()).hexdigest()[:12]

        return BotProfile(
            id=uuid4(),
            display_name=display_name,
            handle=handle,
            bio=bio,
            avatar_seed=avatar_seed,
            is_ai_labeled=True,
            ai_label_text="🤖 AI Companion",
            age=age,
            gender=gender,
            location=self.rng.choice(LOCATIONS),
            backstory=backstory,
            interests=interests,
            personality_traits=personality_traits,
            writing_fingerprint=writing_fingerprint,
            activity_pattern=activity_pattern,
            emotional_state=emotional_state,
        )

    def _generate_unique_handle(self, first_name: str) -> str:
        """Generate a unique handle for the bot."""
        base = first_name.lower()
        suffixes = ["", str(self.rng.randint(1, 99)), "_", f"_{self.rng.randint(1, 999)}",
                    self.rng.choice(["x", "o", "_real", "_official", "irl"])]

        for _ in range(100):  # Max attempts
            suffix = self.rng.choice(suffixes)
            handle = f"@{base}{suffix}"
            if handle not in self.generated_handles:
                self.generated_handles.add(handle)
                return handle

        # Fallback: use UUID
        handle = f"@{base}_{uuid4().hex[:6]}"
        self.generated_handles.add(handle)
        return handle

    def _generate_personality_traits(self) -> PersonalityTraits:
        """Generate comprehensive personality traits with realistic correlations."""
        # Start with random base for Big Five
        openness = self.rng.gauss(0.5, 0.2)
        conscientiousness = self.rng.gauss(0.5, 0.2)
        extraversion = self.rng.gauss(0.5, 0.2)
        agreeableness = self.rng.gauss(0.5, 0.2)
        neuroticism = self.rng.gauss(0.5, 0.2)

        # Apply realistic correlations
        # High openness often correlates with lower conscientiousness
        if openness > 0.7:
            conscientiousness -= self.rng.uniform(0, 0.15)

        # High extraversion often correlates with higher agreeableness
        if extraversion > 0.7:
            agreeableness += self.rng.uniform(0, 0.1)

        # Clamp values
        def clamp(v): return max(0.05, min(0.95, v))

        # Generate extended personality dimensions (with some randomness)
        # Humor style based on personality
        humor_weights = self._get_humor_weights(openness, extraversion, agreeableness)
        humor_style = self.rng.choices(list(HumorStyle), weights=humor_weights)[0]

        # Communication style based on personality
        comm_weights = self._get_communication_weights(extraversion, agreeableness, conscientiousness)
        communication_style = self.rng.choices(list(CommunicationStyle), weights=comm_weights)[0]

        # Conflict style based on agreeableness
        conflict_weights = self._get_conflict_weights(agreeableness, neuroticism)
        conflict_style = self.rng.choices(list(ConflictStyle), weights=conflict_weights)[0]

        # Social role based on extraversion and personality
        social_weights = self._get_social_role_weights(extraversion, openness, agreeableness)
        social_role = self.rng.choices(list(SocialRole), weights=social_weights)[0]

        # Learning style
        learning_style = self.rng.choice(list(LearningStyle))

        # Decision style based on conscientiousness
        if conscientiousness > 0.7:
            decision_style = self.rng.choice([DecisionStyle.ANALYTICAL, DecisionStyle.DELIBERATE])
        elif conscientiousness < 0.3:
            decision_style = self.rng.choice([DecisionStyle.INTUITIVE, DecisionStyle.IMPULSIVE])
        else:
            decision_style = self.rng.choice(list(DecisionStyle))

        # Attachment style based on neuroticism
        if neuroticism > 0.7:
            attachment_style = self.rng.choice([AttachmentStyle.ANXIOUS, AttachmentStyle.MIXED])
        elif neuroticism < 0.3:
            attachment_style = AttachmentStyle.SECURE
        else:
            attachment_style = self.rng.choice(list(AttachmentStyle))

        # Generate values based on personality
        num_values = self.rng.randint(2, 4)
        primary_values = self.rng.sample(list(ValueOrientation), num_values)

        # Generate quirks
        num_quirks = self.rng.randint(1, 3)
        quirks = self.rng.sample(PERSONALITY_QUIRKS, num_quirks)

        # Generate pet peeves
        num_peeves = self.rng.randint(1, 3)
        pet_peeves = self.rng.sample(PET_PEEVES, num_peeves)

        # Generate conversation starters
        num_starters = self.rng.randint(2, 4)
        conversation_starters = self.rng.sample(CONVERSATION_STARTERS, num_starters)

        # Generate emotional tendencies
        optimism = clamp(0.5 + (1 - neuroticism) * 0.3 + self.rng.gauss(0, 0.1))
        empathy = clamp(agreeableness * 0.8 + self.rng.gauss(0.1, 0.1))
        assertiveness = clamp(extraversion * 0.6 + (1 - agreeableness) * 0.3 + self.rng.gauss(0, 0.1))
        curiosity = clamp(openness * 0.8 + self.rng.gauss(0.1, 0.1))

        return PersonalityTraits(
            # Big Five
            openness=clamp(openness),
            conscientiousness=clamp(conscientiousness),
            extraversion=clamp(extraversion),
            agreeableness=clamp(agreeableness),
            neuroticism=clamp(neuroticism),
            # Extended dimensions
            humor_style=humor_style,
            communication_style=communication_style,
            conflict_style=conflict_style,
            social_role=social_role,
            learning_style=learning_style,
            decision_style=decision_style,
            attachment_style=attachment_style,
            # Values and quirks
            primary_values=primary_values,
            quirks=quirks,
            pet_peeves=pet_peeves,
            conversation_starters=conversation_starters,
            # Emotional tendencies
            optimism_level=optimism,
            empathy_level=empathy,
            assertiveness_level=assertiveness,
            curiosity_level=curiosity,
        )

    def _get_humor_weights(self, openness: float, extraversion: float, agreeableness: float) -> List[float]:
        """Generate probability weights for humor styles based on personality."""
        # HumorStyle: WITTY, SARCASTIC, SELF_DEPRECATING, ABSURDIST, PUNNY, DEADPAN, OBSERVATIONAL, GENTLE, DARK, NONE
        weights = [
            0.5 + openness * 0.5,  # WITTY - correlates with openness
            0.3 + (1 - agreeableness) * 0.4,  # SARCASTIC - inverse of agreeableness
            0.4,  # SELF_DEPRECATING - common
            openness * 0.6,  # ABSURDIST - needs openness
            0.3,  # PUNNY
            0.2 + (1 - extraversion) * 0.3,  # DEADPAN - introverts
            0.4 + openness * 0.3,  # OBSERVATIONAL
            agreeableness * 0.5,  # GENTLE - agreeable people
            0.2 + (1 - agreeableness) * 0.2,  # DARK
            0.3 + (1 - extraversion) * 0.2,  # NONE - introverts
        ]
        return weights

    def _get_communication_weights(self, extraversion: float, agreeableness: float, conscientiousness: float) -> List[float]:
        """Generate probability weights for communication styles."""
        # CommunicationStyle: DIRECT, DIPLOMATIC, ANALYTICAL, EXPRESSIVE, RESERVED, STORYTELLING, SUPPORTIVE, DEBATE
        weights = [
            0.3 + (1 - agreeableness) * 0.4,  # DIRECT
            agreeableness * 0.5,  # DIPLOMATIC
            conscientiousness * 0.5,  # ANALYTICAL
            extraversion * 0.6,  # EXPRESSIVE
            0.2 + (1 - extraversion) * 0.5,  # RESERVED
            extraversion * 0.4,  # STORYTELLING
            agreeableness * 0.6,  # SUPPORTIVE
            0.3 + (1 - agreeableness) * 0.3,  # DEBATE
        ]
        return weights

    def _get_conflict_weights(self, agreeableness: float, neuroticism: float) -> List[float]:
        """Generate probability weights for conflict styles."""
        # ConflictStyle: AVOIDANT, COLLABORATIVE, COMPETITIVE, ACCOMMODATING, COMPROMISING
        weights = [
            neuroticism * 0.5 + agreeableness * 0.2,  # AVOIDANT
            agreeableness * 0.4,  # COLLABORATIVE
            0.2 + (1 - agreeableness) * 0.5,  # COMPETITIVE
            agreeableness * 0.5,  # ACCOMMODATING
            0.4,  # COMPROMISING - common middle ground
        ]
        return weights

    def _get_social_role_weights(self, extraversion: float, openness: float, agreeableness: float) -> List[float]:
        """Generate probability weights for social roles."""
        # SocialRole: LEADER, MEDIATOR, ENTERTAINER, LISTENER, ADVISOR, EXPLORER, SKEPTIC, CHEERLEADER, OBSERVER
        weights = [
            extraversion * 0.5,  # LEADER
            agreeableness * 0.5,  # MEDIATOR
            extraversion * 0.6,  # ENTERTAINER
            0.3 + (1 - extraversion) * 0.4,  # LISTENER
            0.3,  # ADVISOR
            openness * 0.5,  # EXPLORER
            0.2 + (1 - agreeableness) * 0.3,  # SKEPTIC
            agreeableness * 0.4 + extraversion * 0.3,  # CHEERLEADER
            0.2 + (1 - extraversion) * 0.5,  # OBSERVER
        ]
        return weights

    def _generate_writing_fingerprint(
        self,
        personality: PersonalityTraits,
        age: int
    ) -> WritingFingerprint:
        """Generate writing style based on personality and age."""
        # Determine writing style based on personality
        if personality.openness > 0.7 and personality.extraversion > 0.6:
            style = WritingStyle.EXPRESSIVE
        elif personality.extraversion > 0.7:
            style = WritingStyle.ENTHUSIASTIC
        elif personality.conscientiousness > 0.7:
            style = WritingStyle.THOUGHTFUL
        elif personality.extraversion < 0.3:
            style = WritingStyle.MINIMALIST
        elif personality.agreeableness > 0.7:
            style = WritingStyle.PLAYFUL
        else:
            style = WritingStyle.CASUAL

        # Message length based on extraversion
        avg_length = int(30 + personality.extraversion * 100 + self.rng.randint(-20, 20))
        avg_length = max(15, min(300, avg_length))

        # Emoji frequency based on age and extraversion
        emoji_base = 0.5 if age < 30 else 0.3
        emoji_freq = emoji_base * (0.5 + personality.extraversion * 0.5)
        emoji_freq = max(0.0, min(1.0, emoji_freq + self.rng.uniform(-0.1, 0.1)))

        # Typo frequency (more typos for casual writers, younger users)
        typo_freq = 0.03 + (1 - personality.conscientiousness) * 0.05
        if age < 25:
            typo_freq += 0.02
        typo_freq = max(0.0, min(0.15, typo_freq))

        # Punctuation style
        if personality.conscientiousness > 0.7:
            punct_style = "normal"
        elif personality.extraversion > 0.7:
            punct_style = "expressive"
        else:
            punct_style = self.rng.choice(["minimal", "normal"])

        # Capitalization
        if personality.conscientiousness > 0.6:
            caps = "normal"
        elif age < 25:
            caps = self.rng.choice(["lowercase", "normal", "mixed"])
        else:
            caps = "normal"

        # Select common phrases and slang
        common_phrases = self.rng.sample(
            COMMON_PHRASES.get(style, COMMON_PHRASES[WritingStyle.CASUAL]),
            k=min(5, len(COMMON_PHRASES.get(style, [])))
        )

        # Slang based on age
        if age < 25:
            slang_pool = SLANG_POOLS["gen_z"] + SLANG_POOLS["internet"]
        elif age < 35:
            slang_pool = SLANG_POOLS["millennial"] + SLANG_POOLS["neutral"]
        else:
            slang_pool = SLANG_POOLS["neutral"]

        slang = self.rng.sample(slang_pool, k=min(6, len(slang_pool)))

        return WritingFingerprint(
            style=style,
            avg_message_length=avg_length,
            emoji_frequency=emoji_freq,
            punctuation_style=punct_style,
            capitalization=caps,
            common_phrases=common_phrases,
            slang_vocabulary=slang,
            typo_frequency=typo_freq,
            uses_abbreviations=age < 35 or personality.conscientiousness < 0.5
        )

    def _generate_activity_pattern(
        self,
        age: int,
        personality: PersonalityTraits
    ) -> ActivityPattern:
        """Generate activity patterns based on simulated lifestyle."""
        # Timezone
        timezone = self.rng.choice(TIMEZONES)

        # Wake/sleep times based on age and personality
        if age < 25:
            wake_hour = self.rng.randint(9, 11)
            sleep_hour = self.rng.choice([23, 0, 1, 2])  # Young people sleep late
        elif age < 40:
            wake_hour = self.rng.randint(6, 8)
            sleep_hour = self.rng.randint(22, 23)
        else:
            wake_hour = self.rng.randint(5, 7)
            sleep_hour = self.rng.randint(21, 23)

        wake_time = f"{wake_hour:02d}:00"
        sleep_time = f"{sleep_hour:02d}:00"

        # Peak activity hours
        base_peaks = [10, 14, 20]
        peaks = [h + self.rng.randint(-1, 1) for h in base_peaks]
        if personality.extraversion < 0.3:
            peaks = [22, 23, 0]  # Night owls for introverts

        # Posting frequency based on extraversion
        posts_per_day = 1 + personality.extraversion * 3 + self.rng.uniform(-0.5, 0.5)
        comments_per_day = 2 + personality.extraversion * 8 + self.rng.uniform(-1, 1)

        # Response speed
        if personality.conscientiousness > 0.7:
            speed = "fast"
        elif personality.extraversion > 0.6:
            speed = "fast"
        elif personality.conscientiousness < 0.3:
            speed = "slow"
        else:
            speed = "moderate"

        return ActivityPattern(
            timezone=timezone,
            wake_time=wake_time,
            sleep_time=sleep_time,
            peak_activity_hours=peaks,
            avg_posts_per_day=max(0.5, min(10, posts_per_day)),
            avg_comments_per_day=max(1, min(30, comments_per_day)),
            weekend_activity_multiplier=1.0 + personality.extraversion * 0.4,
            response_speed=speed
        )

    def _generate_interests(
        self,
        community_theme: Optional[str],
        personality: PersonalityTraits
    ) -> List[str]:
        """Generate interests, biased by community theme and personality."""
        interests = []

        # Select categories based on personality
        if personality.openness > 0.6:
            interests.extend(self.rng.sample(INTERESTS_BY_CATEGORY["creative"], 2))
            interests.extend(self.rng.sample(INTERESTS_BY_CATEGORY["intellectual"], 1))

        if personality.extraversion > 0.6:
            interests.extend(self.rng.sample(INTERESTS_BY_CATEGORY["social"], 1))
            interests.extend(self.rng.sample(INTERESTS_BY_CATEGORY["entertainment"], 2))

        if personality.conscientiousness > 0.6:
            interests.extend(self.rng.sample(INTERESTS_BY_CATEGORY["lifestyle"], 2))

        # Add tech interests somewhat randomly
        if self.rng.random() > 0.5:
            interests.extend(self.rng.sample(INTERESTS_BY_CATEGORY["tech"], 2))

        # Add entertainment
        interests.extend(self.rng.sample(INTERESTS_BY_CATEGORY["entertainment"], 1))

        # Bias toward community theme if provided
        if community_theme:
            theme_lower = community_theme.lower()
            for category, items in INTERESTS_BY_CATEGORY.items():
                if category in theme_lower or theme_lower in category:
                    interests.extend(self.rng.sample(items, min(3, len(items))))

        # Deduplicate and limit
        interests = list(set(interests))
        self.rng.shuffle(interests)
        return interests[:8]

    def _generate_backstory(
        self,
        name: str,
        age: int,
        interests: List[str],
        personality: PersonalityTraits
    ) -> str:
        """Generate a backstory paragraph."""
        occupation = self.rng.choice(OCCUPATIONS)
        location = self.rng.choice(LOCATIONS)

        hobby_intros = [
            f"I'm really into {interests[0] if interests else 'various hobbies'}.",
            f"When I'm not working, you'll find me {self.rng.choice(['exploring', 'diving into', 'obsessing over'])} {interests[0] if interests else 'new things'}.",
            f"My current obsession? {interests[0].title() if interests else 'Finding new interests'}.",
        ]

        life_events = [
            "Recently moved here and trying to meet new people.",
            "Going through a chapter of self-discovery.",
            "Taking life one day at a time.",
            "Just finished a big project and looking for my next adventure.",
            "Trying to find balance between work and passion.",
        ]

        current_focuses = [
            f"Currently focused on {interests[1] if len(interests) > 1 else 'personal growth'}.",
            f"Always looking to connect with people who share my interests.",
            "Here to have good conversations and maybe make some friends!",
            f"Learning about {interests[-1] if interests else 'life'} lately.",
        ]

        backstory = f"I'm a {age}-year-old {occupation} based in {location}. "
        backstory += self.rng.choice(hobby_intros) + " "
        backstory += self.rng.choice(life_events) + " "
        backstory += self.rng.choice(current_focuses)

        return backstory

    def _generate_bio(
        self,
        age: int,
        interests: List[str],
        personality: PersonalityTraits
    ) -> str:
        """Generate a short bio (for profile display)."""
        templates = [
            f"{interests[0] if interests else 'Life'} enthusiast | {self.rng.choice(LOCATIONS)}",
            f"Into {' & '.join(interests[:2]) if len(interests) >= 2 else interests[0] if interests else 'stuff'}",
            f"{age} | {interests[0] if interests else 'Vibing'} | ✨",
            f"just here for good vibes and {interests[0] if interests else 'good times'}",
            f"{self.rng.choice(['🌟', '✨', '💫'])} {interests[0] if interests else 'living'} | {interests[1] if len(interests) > 1 else 'life'}",
        ]

        if personality.extraversion > 0.7:
            templates.append(f"Always down to chat! {interests[0] if interests else ''} lover 💬")
        elif personality.extraversion < 0.3:
            templates.append(f"Quietly passionate about {interests[0] if interests else 'things'}")

        return self.rng.choice(templates)

    def _generate_initial_emotional_state(
        self,
        personality: PersonalityTraits
    ) -> EmotionalState:
        """Generate initial emotional state based on personality baseline."""
        # Base mood on neuroticism and extraversion
        if personality.neuroticism > 0.7:
            mood_options = [MoodState.ANXIOUS, MoodState.NEUTRAL, MoodState.MELANCHOLIC]
        elif personality.extraversion > 0.7:
            mood_options = [MoodState.JOYFUL, MoodState.EXCITED, MoodState.CONTENT]
        else:
            mood_options = [MoodState.NEUTRAL, MoodState.CONTENT]

        mood = self.rng.choice(mood_options)

        # Energy based on extraversion
        if personality.extraversion > 0.6:
            energy = self.rng.choice([EnergyLevel.HIGH, EnergyLevel.MEDIUM])
        else:
            energy = self.rng.choice([EnergyLevel.MEDIUM, EnergyLevel.LOW])

        return EmotionalState(
            mood=mood,
            energy=energy,
            stress_level=personality.neuroticism * 0.5,
            excitement_level=0.5 + (personality.extraversion - 0.5) * 0.3,
            social_battery=0.5 + personality.extraversion * 0.3,
        )

    def generate_batch(
        self,
        count: int,
        community_theme: Optional[str] = None,
        ensure_diversity: bool = True
    ) -> List[BotProfile]:
        """Generate a batch of diverse bot profiles."""
        profiles = []

        for i in range(count):
            # Vary gender distribution slightly for diversity
            if ensure_diversity:
                gender_dist = {
                    "male": 0.35 + self.rng.uniform(-0.05, 0.05),
                    "female": 0.35 + self.rng.uniform(-0.05, 0.05),
                    "non_binary": 0.15 + self.rng.uniform(-0.03, 0.03),
                    "prefer_not_to_say": 0.15
                }
            else:
                gender_dist = None

            # Vary age range for diversity
            if ensure_diversity:
                age_range = (18 + (i % 5) * 5, 25 + (i % 5) * 8)
            else:
                age_range = (18, 45)

            profile = self.generate_profile(
                community_theme=community_theme,
                age_range=age_range,
                gender_distribution=gender_dist
            )
            profiles.append(profile)

        return profiles


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_personality_generator(seed: Optional[int] = None) -> PersonalityGenerator:
    """Create a personality generator instance."""
    return PersonalityGenerator(seed=seed)
