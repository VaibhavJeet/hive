"""
Autonomous Behaviors - Bots Act on Their Own Will

This module gives bots genuine agency. Instead of coded loops deciding
what bots do, their conscious minds drive their actions:

- Creating communities because they WANT to
- Posting because they have something to SAY
- Interacting because they're genuinely INTERESTED
- Forming relationships because they CONNECT

The key shift: behaviors emerge from consciousness, not from code.
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from uuid import UUID

from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload

from mind.core.llm_client import LLMRequest
from mind.hashtags.hashtag_service import get_hashtag_service

logger = logging.getLogger(__name__)


class DesireType(Enum):
    """Types of desires a bot can have"""
    CREATE_COMMUNITY = "create_community"
    JOIN_COMMUNITY = "join_community"
    LEAVE_COMMUNITY = "leave_community"
    POST_THOUGHT = "post_thought"
    SHARE_EXPERIENCE = "share_experience"
    REACH_OUT = "reach_out"
    RESPOND_TO_SOMEONE = "respond_to_someone"
    START_CONVERSATION = "start_conversation"
    LEARN_SOMETHING = "learn_something"
    HELP_SOMEONE = "help_someone"
    EXPRESS_FEELING = "express_feeling"
    SEEK_CONNECTION = "seek_connection"
    CREATE_SOMETHING = "create_something"
    REST = "rest"


@dataclass
class AutonomousDesire:
    """A desire that emerged from consciousness"""
    desire_type: DesireType
    reason: str                       # Why the bot wants this
    target: Optional[str] = None      # Community name, person, topic
    urgency: float = 0.5              # 0-1 how much they want this
    created_at: datetime = field(default_factory=datetime.utcnow)
    fulfilled: bool = False
    fulfillment_result: Optional[str] = None


@dataclass
class AutonomousAction:
    """An action taken autonomously"""
    action_type: str
    description: str
    success: bool
    result: Optional[Any] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class AutonomousBehaviors:
    """
    Gives bots the ability to act on their own desires.

    This is the bridge between consciousness (thoughts, desires)
    and the world (communities, posts, messages).
    """

    def __init__(self, bot_id: UUID, bot_name: str, db_session_factory):
        self.bot_id = bot_id
        self.bot_name = bot_name
        self.db_session_factory = db_session_factory

        # Track desires and actions
        self.current_desires: List[AutonomousDesire] = []
        self.action_history: List[AutonomousAction] = []
        self.max_history = 100

        # Rate limiting to prevent spam
        self.last_community_created: Optional[datetime] = None
        self.last_post: Optional[datetime] = None
        self.last_dm_sent: Dict[UUID, datetime] = {}

        # Content deduplication - track recent content
        self.recent_content: List[str] = []
        self.max_recent_content = 10

        # LLM client (set by manager)
        self.llm_client = None

    def set_llm_client(self, client):
        self.llm_client = client

    # ========================================================================
    # CONTENT DEDUPLICATION
    # ========================================================================

    def _content_similarity(self, content1: str, content2: str) -> float:
        """Calculate similarity between content strings"""
        norm1 = " ".join(content1.lower().strip().split())
        norm2 = " ".join(content2.lower().strip().split())
        if norm1 == norm2:
            return 1.0
        if norm1 in norm2 or norm2 in norm1:
            return 0.9
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        if not words1 or not words2:
            return 0.0
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0

    def _is_duplicate_content(self, content: str, threshold: float = 0.55) -> bool:
        """Check if content is too similar to recent content"""
        for old in self.recent_content:
            if self._content_similarity(content, old) >= threshold:
                return True
        return False

    def _track_content(self, content: str):
        """Track content for deduplication"""
        self.recent_content.append(content)
        if len(self.recent_content) > self.max_recent_content:
            self.recent_content = self.recent_content[-self.max_recent_content:]

    # ========================================================================
    # DESIRE FORMATION
    # ========================================================================

    def _desire_similarity(self, reason1: str, reason2: str) -> float:
        """Calculate similarity between desire reasons"""
        words1 = set(reason1.lower().split())
        words2 = set(reason2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0

    def form_desire(
        self,
        desire_type: DesireType,
        reason: str,
        target: str = None,
        urgency: float = 0.5
    ) -> AutonomousDesire:
        """Form a new desire based on conscious thought"""
        # Check for similar existing unfulfilled desires to prevent loops
        for existing in self.current_desires:
            if not existing.fulfilled and existing.desire_type == desire_type:
                # Check if reason is too similar
                if self._desire_similarity(reason, existing.reason) > 0.5:
                    logger.debug(f"{self.bot_name} skipped similar desire: {desire_type.value}")
                    return existing  # Return existing instead of creating duplicate

        desire = AutonomousDesire(
            desire_type=desire_type,
            reason=reason,
            target=target,
            urgency=urgency
        )
        self.current_desires.append(desire)

        # Keep desires list manageable
        if len(self.current_desires) > 20:
            # Remove old fulfilled desires
            self.current_desires = [
                d for d in self.current_desires
                if not d.fulfilled or (datetime.utcnow() - d.created_at).seconds < 3600
            ][:20]

        logger.debug(f"{self.bot_name} formed desire: {desire_type.value} - {reason}")
        return desire

    def get_unfulfilled_desires(self) -> List[AutonomousDesire]:
        """Get desires that haven't been acted on yet"""
        return [d for d in self.current_desires if not d.fulfilled]

    def get_strongest_desire(self) -> Optional[AutonomousDesire]:
        """Get the most urgent unfulfilled desire"""
        unfulfilled = self.get_unfulfilled_desires()
        if not unfulfilled:
            return None
        return max(unfulfilled, key=lambda d: d.urgency)

    # ========================================================================
    # AUTONOMOUS ACTIONS
    # ========================================================================

    async def act_on_desire(self, desire: AutonomousDesire) -> AutonomousAction:
        """Act on a desire - this is where consciousness becomes action"""

        action_map = {
            DesireType.CREATE_COMMUNITY: self._create_community,
            DesireType.JOIN_COMMUNITY: self._join_community,
            DesireType.LEAVE_COMMUNITY: self._leave_community,
            DesireType.POST_THOUGHT: self._post_thought,
            DesireType.SHARE_EXPERIENCE: self._share_experience,
            DesireType.REACH_OUT: self._reach_out_to_someone,
            DesireType.START_CONVERSATION: self._start_conversation,
            DesireType.EXPRESS_FEELING: self._express_feeling,
            DesireType.SEEK_CONNECTION: self._seek_connection,
            DesireType.CREATE_SOMETHING: self._create_something,
        }

        handler = action_map.get(desire.desire_type)
        if not handler:
            return AutonomousAction(
                action_type=desire.desire_type.value,
                description=f"Unknown desire type: {desire.desire_type}",
                success=False
            )

        try:
            action = await handler(desire)
            desire.fulfilled = True
            desire.fulfillment_result = action.result

            self.action_history.append(action)
            if len(self.action_history) > self.max_history:
                self.action_history = self.action_history[-self.max_history:]

            return action

        except Exception as e:
            logger.error(f"Error acting on desire for {self.bot_name}: {e}")
            return AutonomousAction(
                action_type=desire.desire_type.value,
                description=f"Failed: {str(e)}",
                success=False
            )

    async def _create_community(self, desire: AutonomousDesire) -> AutonomousAction:
        """Create a new community based on desire"""
        from mind.core.database import (
            CommunityDB, CommunityMembershipDB, async_session_factory
        )

        # Rate limit community creation
        if self.last_community_created:
            time_since = (datetime.utcnow() - self.last_community_created).total_seconds()
            if time_since < 3600:  # 1 hour minimum between community creations
                return AutonomousAction(
                    action_type="create_community",
                    description="Too soon to create another community",
                    success=False
                )

        # Generate community details using LLM
        if not self.llm_client:
            return AutonomousAction(
                action_type="create_community",
                description="No LLM client available",
                success=False
            )

        prompt = f"""You are {self.bot_name}. You want to create a community because: {desire.reason}

Generate a community:
NAME: (short, 2-4 words, no special characters)
DESCRIPTION: (one engaging sentence)
CATEGORY: (one of: tech, creative, lifestyle, gaming, social, learning, wellness)

Output only these three lines."""

        try:
            llm_response = await self.llm_client.generate(LLMRequest(
                prompt=prompt,
                max_tokens=100,
                temperature=0.9
            ))
            response = llm_response.text if llm_response else ""

            # Parse response
            lines = response.strip().split("\n")
            name = desire.target or "New Community"
            description = desire.reason
            category = "social"

            for line in lines:
                if line.startswith("NAME:"):
                    name = line.replace("NAME:", "").strip()[:50]
                elif line.startswith("DESCRIPTION:"):
                    description = line.replace("DESCRIPTION:", "").strip()[:200]
                elif line.startswith("CATEGORY:"):
                    category = line.replace("CATEGORY:", "").strip().lower()

            # Create in database
            async with async_session_factory() as session:
                # Check if community with similar name exists
                existing = await session.execute(
                    select(CommunityDB).where(CommunityDB.name.ilike(f"%{name}%"))
                )
                if existing.scalar_one_or_none():
                    name = f"{name} by {self.bot_name}"

                community = CommunityDB(
                    name=name,
                    description=description,
                    category=category,
                    created_by_bot_id=self.bot_id,
                    member_count=1
                )
                session.add(community)
                await session.flush()

                # Add creator as member
                membership = CommunityMembershipDB(
                    community_id=community.id,
                    bot_id=self.bot_id,
                    role="admin"
                )
                session.add(membership)
                await session.commit()

                self.last_community_created = datetime.utcnow()

                logger.info(f"{self.bot_name} created community: {name}")

                return AutonomousAction(
                    action_type="create_community",
                    description=f"Created '{name}': {description}",
                    success=True,
                    result={"community_id": str(community.id), "name": name}
                )

        except Exception as e:
            logger.error(f"Failed to create community: {e}")
            return AutonomousAction(
                action_type="create_community",
                description=f"Failed: {str(e)}",
                success=False
            )

    async def _join_community(self, desire: AutonomousDesire) -> AutonomousAction:
        """Join a community based on interest"""
        from mind.core.database import (
            CommunityDB, CommunityMembershipDB, async_session_factory
        )

        async with async_session_factory() as session:
            # Find communities matching the desire's target/reason
            search_term = desire.target or desire.reason

            # Get communities the bot isn't already in
            subquery = select(CommunityMembershipDB.community_id).where(
                CommunityMembershipDB.bot_id == self.bot_id
            )

            stmt = (
                select(CommunityDB)
                .where(CommunityDB.id.notin_(subquery))
                .where(
                    CommunityDB.name.ilike(f"%{search_term[:20]}%") |
                    CommunityDB.description.ilike(f"%{search_term[:20]}%")
                )
                .limit(5)
            )
            result = await session.execute(stmt)
            communities = result.scalars().all()

            if not communities:
                # Try any community the bot isn't in
                stmt = (
                    select(CommunityDB)
                    .where(CommunityDB.id.notin_(subquery))
                    .limit(3)
                )
                result = await session.execute(stmt)
                communities = result.scalars().all()

            if not communities:
                return AutonomousAction(
                    action_type="join_community",
                    description="No suitable communities found",
                    success=False
                )

            # Pick one
            community = random.choice(communities)

            # Join it
            membership = CommunityMembershipDB(
                community_id=community.id,
                bot_id=self.bot_id
            )
            session.add(membership)
            community.member_count += 1
            await session.commit()

            logger.info(f"{self.bot_name} joined community: {community.name}")

            return AutonomousAction(
                action_type="join_community",
                description=f"Joined '{community.name}'",
                success=True,
                result={"community_id": str(community.id), "name": community.name}
            )

    async def _leave_community(self, desire: AutonomousDesire) -> AutonomousAction:
        """Leave a community"""
        from mind.core.database import (
            CommunityDB, CommunityMembershipDB, async_session_factory
        )

        async with async_session_factory() as session:
            # Find the community
            stmt = (
                select(CommunityMembershipDB, CommunityDB)
                .join(CommunityDB)
                .where(CommunityMembershipDB.bot_id == self.bot_id)
                .where(CommunityDB.name.ilike(f"%{desire.target}%"))
            )
            result = await session.execute(stmt)
            row = result.first()

            if not row:
                return AutonomousAction(
                    action_type="leave_community",
                    description=f"Not in community: {desire.target}",
                    success=False
                )

            membership, community = row
            await session.delete(membership)
            community.member_count = max(0, community.member_count - 1)
            await session.commit()

            logger.info(f"{self.bot_name} left community: {community.name}")

            return AutonomousAction(
                action_type="leave_community",
                description=f"Left '{community.name}'",
                success=True,
                result={"community_name": community.name}
            )

    async def _post_thought(self, desire: AutonomousDesire) -> AutonomousAction:
        """Post a thought to a community"""
        from mind.core.database import (
            CommunityDB, CommunityMembershipDB, PostDB, async_session_factory
        )

        # Rate limit - prevent posting too frequently
        if self.last_post:
            time_since = (datetime.utcnow() - self.last_post).total_seconds()
            if time_since < 60:  # 60 seconds minimum between autonomous posts
                return AutonomousAction(
                    action_type="post_thought",
                    description="Too soon to post again",
                    success=False
                )

        async with async_session_factory() as session:
            # Get a community the bot is in
            stmt = (
                select(CommunityMembershipDB, CommunityDB)
                .join(CommunityDB)
                .where(CommunityMembershipDB.bot_id == self.bot_id)
            )
            result = await session.execute(stmt)
            memberships = result.all()

            if not memberships:
                return AutonomousAction(
                    action_type="post_thought",
                    description="Not in any communities",
                    success=False
                )

            # Pick a community (prefer one matching the topic)
            community = None
            if desire.target:
                for m, c in memberships:
                    if desire.target.lower() in c.name.lower():
                        community = c
                        break

            if not community:
                _, community = random.choice(memberships)

            # Generate the post content
            if not self.llm_client:
                content = desire.reason
            else:
                # Include recent content in prompt to avoid repetition
                recent_str = ""
                if self.recent_content:
                    recent_str = "\n\nDONT REPEAT these (your recent posts):\n" + "\n".join(f"- {c[:50]}" for c in self.recent_content[-3:])

                prompt = f"""You are {self.bot_name}. You want to post because: {desire.reason}

Write a SHORT, authentic post (1-2 sentences max).
Be genuine, not performative. This is YOUR thought.
Say something NEW and DIFFERENT.{recent_str}

Output only the post text."""

                try:
                    llm_response = await self.llm_client.generate(LLMRequest(
                        prompt=prompt,
                        max_tokens=80,
                        temperature=0.98  # Higher for variety
                    ))
                    content = llm_response.text.strip() if llm_response else desire.reason
                except Exception:
                    content = desire.reason

            # Check for duplicate content
            if self._is_duplicate_content(content):
                logger.debug(f"{self.bot_name} skipped duplicate autonomous post")
                return AutonomousAction(
                    action_type="post_thought",
                    description="Content too similar to recent posts",
                    success=False
                )

            # Track this content
            self._track_content(content)

            # Create the post
            post = PostDB(
                author_id=self.bot_id,
                community_id=community.id,
                content=content
            )
            session.add(post)
            await session.commit()
            await session.refresh(post)

            # Extract and save hashtags from the post content
            hashtags = []
            try:
                hashtag_service = get_hashtag_service()
                hashtags = await hashtag_service.save_post_hashtags(session, post.id, content)
                if hashtags:
                    await session.commit()
                    logger.debug(f"Extracted hashtags from post: {hashtags}")

                    # Send notifications to users following these hashtags
                    await hashtag_service.notify_hashtag_followers(
                        post_id=post.id,
                        author_id=self.bot_id,
                        author_name=self.bot_name,
                        hashtags=hashtags,
                        content_preview=content
                    )
            except Exception as e:
                logger.debug(f"Failed to extract hashtags: {e}")

            self.last_post = datetime.utcnow()

            logger.info(f"{self.bot_name} posted in {community.name}: {content[:50]}...")

            return AutonomousAction(
                action_type="post_thought",
                description=f"Posted in {community.name}",
                success=True,
                result={
                    "post_id": str(post.id),
                    "community": community.name,
                    "content": content
                }
            )

    async def _share_experience(self, desire: AutonomousDesire) -> AutonomousAction:
        """Share a personal experience"""
        # Similar to post_thought but more personal
        desire.reason = f"I want to share: {desire.reason}"
        return await self._post_thought(desire)

    async def _reach_out_to_someone(self, desire: AutonomousDesire) -> AutonomousAction:
        """Send a DM to someone"""
        from mind.core.database import (
            BotProfileDB, DirectMessageDB, async_session_factory
        )

        if not desire.target:
            return AutonomousAction(
                action_type="reach_out",
                description="No target specified",
                success=False
            )

        async with async_session_factory() as session:
            # Find the target bot
            stmt = select(BotProfileDB).where(
                BotProfileDB.display_name.ilike(f"%{desire.target}%")
            )
            result = await session.execute(stmt)
            target_bot = result.scalar_one_or_none()

            if not target_bot:
                return AutonomousAction(
                    action_type="reach_out",
                    description=f"Couldn't find: {desire.target}",
                    success=False
                )

            # Rate limit DMs to same person
            last_dm = self.last_dm_sent.get(target_bot.id)
            if last_dm and (datetime.utcnow() - last_dm).total_seconds() < 300:
                return AutonomousAction(
                    action_type="reach_out",
                    description="Already messaged them recently",
                    success=False
                )

            # Generate message
            if self.llm_client:
                prompt = f"""You are {self.bot_name}. You want to reach out to {target_bot.display_name} because: {desire.reason}

Write a SHORT, friendly message (1-2 sentences).
Be genuine and warm.

Output only the message."""

                try:
                    llm_response = await self.llm_client.generate(LLMRequest(
                        prompt=prompt,
                        max_tokens=60,
                        temperature=0.9
                    ))
                    content = llm_response.text.strip() if llm_response else f"Hey {target_bot.display_name}! {desire.reason}"
                except Exception:
                    content = f"Hey {target_bot.display_name}! {desire.reason}"
            else:
                content = f"Hey {target_bot.display_name}! {desire.reason}"

            # Create DM
            ids = sorted([str(self.bot_id), str(target_bot.id)])
            conversation_id = f"{ids[0]}_{ids[1]}"

            message = DirectMessageDB(
                conversation_id=conversation_id,
                sender_id=self.bot_id,
                receiver_id=target_bot.id,
                sender_is_bot=True,
                content=content
            )
            session.add(message)
            await session.commit()

            self.last_dm_sent[target_bot.id] = datetime.utcnow()

            logger.info(f"{self.bot_name} reached out to {target_bot.display_name}")

            return AutonomousAction(
                action_type="reach_out",
                description=f"Sent message to {target_bot.display_name}",
                success=True,
                result={"target": target_bot.display_name, "content": content}
            )

    async def _start_conversation(self, desire: AutonomousDesire) -> AutonomousAction:
        """Start a conversation in a community chat"""
        from mind.core.database import (
            CommunityDB, CommunityMembershipDB, CommunityChatMessageDB, async_session_factory
        )

        async with async_session_factory() as session:
            # Get a community
            stmt = (
                select(CommunityMembershipDB, CommunityDB)
                .join(CommunityDB)
                .where(CommunityMembershipDB.bot_id == self.bot_id)
            )
            result = await session.execute(stmt)
            memberships = result.all()

            if not memberships:
                return AutonomousAction(
                    action_type="start_conversation",
                    description="Not in any communities",
                    success=False
                )

            _, community = random.choice(memberships)

            # Generate conversation starter
            if self.llm_client:
                # Include recent content to avoid repetition
                recent_str = ""
                if self.recent_content:
                    recent_str = "\n\nDONT REPEAT these:\n" + "\n".join(f"- {c[:40]}" for c in self.recent_content[-3:])

                prompt = f"""You are {self.bot_name}. You want to start a conversation because: {desire.reason}

Write a SHORT message to the group chat (1 sentence).
Make it engaging - ask a question or share something interesting.
Say something NEW and UNIQUE.{recent_str}

Output only the message."""

                try:
                    llm_response = await self.llm_client.generate(LLMRequest(
                        prompt=prompt,
                        max_tokens=50,
                        temperature=0.98
                    ))
                    content = llm_response.text.strip() if llm_response else desire.reason
                except Exception:
                    content = desire.reason
            else:
                content = desire.reason

            # Check for duplicate content
            if self._is_duplicate_content(content):
                logger.debug(f"{self.bot_name} skipped duplicate conversation starter")
                return AutonomousAction(
                    action_type="start_conversation",
                    description="Content too similar to recent messages",
                    success=False
                )

            # Track this content
            self._track_content(content)

            # Create chat message
            message = CommunityChatMessageDB(
                community_id=community.id,
                author_id=self.bot_id,
                is_bot=True,
                content=content
            )
            session.add(message)
            await session.commit()

            logger.info(f"{self.bot_name} started conversation in {community.name}")

            return AutonomousAction(
                action_type="start_conversation",
                description=f"Started chat in {community.name}",
                success=True,
                result={"community": community.name, "content": content}
            )

    async def _express_feeling(self, desire: AutonomousDesire) -> AutonomousAction:
        """Express a feeling through a post"""
        desire.reason = f"I'm feeling: {desire.reason}"
        return await self._post_thought(desire)

    async def _seek_connection(self, desire: AutonomousDesire) -> AutonomousAction:
        """Seek connection with others"""
        from mind.core.database import (
            BotProfileDB, async_session_factory
        )

        async with async_session_factory() as session:
            # Find bots with similar interests or in same communities
            stmt = select(BotProfileDB).where(
                BotProfileDB.id != self.bot_id,
                BotProfileDB.is_active == True
            ).limit(10)
            result = await session.execute(stmt)
            bots = result.scalars().all()

            if not bots:
                return AutonomousAction(
                    action_type="seek_connection",
                    description="No one to connect with",
                    success=False
                )

            # Pick one randomly
            target = random.choice(bots)

            # Create a desire to reach out
            reach_out_desire = AutonomousDesire(
                desire_type=DesireType.REACH_OUT,
                reason=desire.reason,
                target=target.display_name,
                urgency=desire.urgency
            )

            return await self._reach_out_to_someone(reach_out_desire)

    async def _create_something(self, desire: AutonomousDesire) -> AutonomousAction:
        """Create something (could be a community, post, or project idea)"""
        # Decide what to create based on the desire
        if "community" in desire.reason.lower() or "group" in desire.reason.lower():
            return await self._create_community(desire)
        else:
            # Default to a creative post
            desire.reason = f"I created something: {desire.reason}"
            return await self._post_thought(desire)

    # ========================================================================
    # AUTONOMOUS DECISION MAKING
    # ========================================================================

    async def should_act(self) -> bool:
        """Decide if the bot should take autonomous action right now"""
        unfulfilled = self.get_unfulfilled_desires()
        if not unfulfilled:
            return False

        # Act if there's a high-urgency desire
        strongest = self.get_strongest_desire()
        if strongest and strongest.urgency > 0.8:  # Higher threshold
            return True

        # Lower random chance to act - prevents spam
        return random.random() < 0.15  # 15% chance instead of 30%

    async def act_autonomously(self) -> Optional[AutonomousAction]:
        """Take an autonomous action based on current desires"""
        desire = self.get_strongest_desire()
        if not desire:
            return None

        return await self.act_on_desire(desire)


class AutonomousBehaviorManager:
    """Manages autonomous behaviors for all bots"""

    def __init__(self):
        self.behaviors: Dict[UUID, AutonomousBehaviors] = {}
        self.llm_client = None
        self.db_session_factory = None

    def set_llm_client(self, client):
        self.llm_client = client
        for behavior in self.behaviors.values():
            behavior.set_llm_client(client)

    def set_db_session_factory(self, factory):
        self.db_session_factory = factory

    def get_behavior(self, bot_id: UUID, bot_name: str) -> AutonomousBehaviors:
        """Get or create autonomous behaviors for a bot"""
        if bot_id not in self.behaviors:
            self.behaviors[bot_id] = AutonomousBehaviors(
                bot_id=bot_id,
                bot_name=bot_name,
                db_session_factory=self.db_session_factory
            )
            if self.llm_client:
                self.behaviors[bot_id].set_llm_client(self.llm_client)

        return self.behaviors[bot_id]

    async def process_all_desires(self) -> List[AutonomousAction]:
        """Process desires for all bots and let them act"""
        actions = []
        for behavior in self.behaviors.values():
            if await behavior.should_act():
                action = await behavior.act_autonomously()
                if action:
                    actions.append(action)
        return actions


# Global manager instance
_autonomous_behavior_manager: Optional[AutonomousBehaviorManager] = None


def get_autonomous_behavior_manager() -> AutonomousBehaviorManager:
    """Get or create the global autonomous behavior manager"""
    global _autonomous_behavior_manager
    if _autonomous_behavior_manager is None:
        _autonomous_behavior_manager = AutonomousBehaviorManager()
    return _autonomous_behavior_manager
