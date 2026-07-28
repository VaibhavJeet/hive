"""
Chat API routes - Community Chat and Direct Messages.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
import re
import html


def sanitize_content(content: str) -> str:
    """Sanitize user input to prevent XSS and injection attacks."""
    content = html.escape(content)
    content = re.sub(r'\s+', ' ', content).strip()
    return content
from sqlalchemy import select, desc, or_, and_

from mind.api.dependencies import CurrentUser, OptionalUser
from mind.core.database import (
    async_session_factory, CommunityChatMessageDB, DirectMessageDB,
    BotProfileDB, CommunityDB, AppUserDB, UserBlockDB, CommunityMembershipDB
)
from mind.core.errors import NotFoundError, ValidationError, DatabaseError
from mind.core.decorators import handle_errors
from mind.blocking.blocking_service import blocking_service
from mind.moderation.content_filter import get_content_filter, SuggestedAction
from mind.engine.activity_engine import get_activity_engine


router = APIRouter(prefix="/chat", tags=["chat"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ChatAuthorInfo(BaseModel):
    id: UUID
    display_name: str
    avatar_seed: str
    is_bot: bool
    ai_label_text: Optional[str] = None


class CommunityChatMessage(BaseModel):
    id: UUID
    community_id: UUID
    author: ChatAuthorInfo
    content: str
    reply_to_id: Optional[UUID] = None
    reply_to_content: Optional[str] = None
    created_at: datetime


class DirectMessage(BaseModel):
    id: UUID
    conversation_id: str
    sender: ChatAuthorInfo
    receiver_id: UUID
    content: str
    created_at: datetime
    is_read: bool


class ConversationPreview(BaseModel):
    conversation_id: str
    other_user: ChatAuthorInfo
    last_message: str
    last_message_time: datetime
    unread_count: int


class SendChatMessageRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "content": "Hey everyone — what is everyone working on today?",
                    "reply_to_id": None,
                }
            ]
        }
    )

    content: str = Field(..., min_length=1, max_length=2000, description="Message content")
    reply_to_id: Optional[UUID] = None

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        v = sanitize_content(v)
        if len(v) < 1:
            raise ValueError('Content cannot be empty')
        return v


class SendDirectMessageRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "receiver_id": "123e4567-e89b-12d3-a456-426614174001",
                    "content": "Hi! I'd love to chat about your latest post.",
                }
            ]
        }
    )

    receiver_id: UUID
    content: str = Field(..., min_length=1, max_length=2000, description="Message content")

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        v = sanitize_content(v)
        if len(v) < 1:
            raise ValueError('Content cannot be empty')
        return v


class ErrorResponse(BaseModel):
    detail: str


# ============================================================================
# COMMUNITY CHAT ENDPOINTS
# ============================================================================

@router.get(
    "/community/{community_id}/messages",
    response_model=List[CommunityChatMessage],
    summary="List community chat messages",
    description="Newest-first batch; use **before_id** for cursor pagination. Block filtering is applied for the signed-in caller.",
    responses={422: {"model": ErrorResponse, "description": "Validation error"}},
)
@handle_errors(default_error=DatabaseError)
async def get_community_chat(
    community_id: UUID,
    current_user: OptionalUser,
    limit: int = Query(default=50, le=100),
    before_id: Optional[UUID] = None
):
    """Get community chat messages with pagination."""
    # Block filtering applies to the signed-in caller, not an arbitrary user id.
    blocked_bot_ids = set()
    if current_user:
        blocked_bot_ids = await blocking_service.get_blocked_bot_ids(current_user.id)

    async with async_session_factory() as session:
        # Build query
        stmt = (
            select(CommunityChatMessageDB)
            .where(CommunityChatMessageDB.community_id == community_id)
            .where(CommunityChatMessageDB.is_deleted == False)
            .order_by(desc(CommunityChatMessageDB.created_at))
            .limit(limit)
        )

        # Exclude messages from blocked bots
        if blocked_bot_ids:
            stmt = stmt.where(CommunityChatMessageDB.author_id.notin_(blocked_bot_ids))

        if before_id:
            # Get the created_at of the before_id message
            before_stmt = select(CommunityChatMessageDB.created_at).where(
                CommunityChatMessageDB.id == before_id
            )
            before_result = await session.execute(before_stmt)
            before_time = before_result.scalar_one_or_none()
            if before_time:
                stmt = stmt.where(CommunityChatMessageDB.created_at < before_time)

        result = await session.execute(stmt)
        messages = result.scalars().all()

        # Build response with author info
        response = []
        for msg in reversed(messages):  # Reverse to get chronological order
            # Get author info
            if msg.is_bot:
                author_stmt = select(BotProfileDB).where(BotProfileDB.id == msg.author_id)
                author_result = await session.execute(author_stmt)
                author = author_result.scalar_one_or_none()
                author_info = ChatAuthorInfo(
                    id=author.id if author else msg.author_id,
                    display_name=author.display_name if author else "Unknown Bot",
                    avatar_seed=author.avatar_seed if author else str(msg.author_id),
                    is_bot=True,
                    ai_label_text=author.ai_label_text if author else "🤖 AI"
                )
            else:
                author_stmt = select(AppUserDB).where(AppUserDB.id == msg.author_id)
                author_result = await session.execute(author_stmt)
                author = author_result.scalar_one_or_none()
                author_info = ChatAuthorInfo(
                    id=author.id if author else msg.author_id,
                    display_name=author.display_name if author else "User",
                    avatar_seed=author.avatar_seed if author else str(msg.author_id),
                    is_bot=False
                )

            # Get reply content if exists
            reply_content = None
            if msg.reply_to_id:
                reply_stmt = select(CommunityChatMessageDB.content).where(
                    CommunityChatMessageDB.id == msg.reply_to_id
                )
                reply_result = await session.execute(reply_stmt)
                reply_content = reply_result.scalar_one_or_none()

            response.append(CommunityChatMessage(
                id=msg.id,
                community_id=msg.community_id,
                author=author_info,
                content=msg.content,
                reply_to_id=msg.reply_to_id,
                reply_to_content=reply_content,
                created_at=msg.created_at
            ))

        return response


@router.post(
    "/community/{community_id}/messages",
    response_model=CommunityChatMessage,
    summary="Send a community chat message",
    description="The sender is the signed-in caller. May queue bot replies.",
    responses={
        400: {"model": ErrorResponse, "description": "Blocked by moderation"},
        404: {"model": ErrorResponse, "description": "Community not found"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
@handle_errors(default_error=DatabaseError)
async def send_community_message(
    community_id: UUID,
    request: SendChatMessageRequest,
    current_user: CurrentUser,
):
    """Send a message to community chat.

    HIVE-003: the sender is the bearer-token user. The old `is_bot` flag let a
    caller mark their own message as bot-authored and skip moderation entirely.
    """
    user_id = current_user.id
    is_bot = False

    # Content moderation check (skip for bot-generated content)
    if not is_bot:
        content_filter = get_content_filter()
        moderation_result = content_filter.check_text(
            text=request.content,
            user_id=user_id,
            context={"content_type": "chat_message", "community_id": str(community_id)}
        )

        if moderation_result.suggested_action == SuggestedAction.BLOCK:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Message violates community guidelines",
                    "flags": moderation_result.flags,
                    "action": "blocked"
                }
            )

    async with async_session_factory() as session:
        # Verify community exists
        comm_stmt = select(CommunityDB).where(CommunityDB.id == community_id)
        comm_result = await session.execute(comm_stmt)
        community = comm_result.scalar_one_or_none()
        if not community:
            raise HTTPException(status_code=404, detail="Community not found")

        # Create message
        message = CommunityChatMessageDB(
            community_id=community_id,
            author_id=user_id,
            is_bot=is_bot,
            content=request.content,
            reply_to_id=request.reply_to_id
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)

        # Get author info
        if is_bot:
            author_stmt = select(BotProfileDB).where(BotProfileDB.id == user_id)
            author_result = await session.execute(author_stmt)
            author = author_result.scalar_one_or_none()
            author_info = ChatAuthorInfo(
                id=user_id,
                display_name=author.display_name if author else "Bot",
                avatar_seed=author.avatar_seed if author else str(user_id),
                is_bot=True,
                ai_label_text=author.ai_label_text if author else "🤖 AI"
            )
        else:
            author_stmt = select(AppUserDB).where(AppUserDB.id == user_id)
            author_result = await session.execute(author_stmt)
            author = author_result.scalar_one_or_none()
            author_info = ChatAuthorInfo(
                id=user_id,
                display_name=author.display_name if author else "User",
                avatar_seed=author.avatar_seed if author else str(user_id),
                is_bot=False
            )

        result = CommunityChatMessage(
            id=message.id,
            community_id=community_id,
            author=author_info,
            content=message.content,
            reply_to_id=message.reply_to_id,
            created_at=message.created_at
        )

        # If user posts in community chat, trigger bot responses
        if not is_bot:
            # Get active bots in this community (randomly select 1-2 to respond)
            import random
            members_stmt = (
                select(CommunityMembershipDB.bot_id)
                .where(CommunityMembershipDB.community_id == community_id)
            )
            members_result = await session.execute(members_stmt)
            bot_ids = [row[0] for row in members_result.fetchall()]

            if bot_ids:
                # 1-2 bots may respond (not all, for natural feel)
                responders = random.sample(bot_ids, min(random.randint(1, 2), len(bot_ids)))

                try:
                    engine = await get_activity_engine()
                    for bot_id in responders:
                        await engine.queue_user_interaction(
                            interaction_type="chat_reply",
                            bot_id=bot_id,
                            user_id=user_id,
                            content=request.content,
                            context={
                                "community_id": str(community_id),
                                "message_id": str(message.id)
                            }
                        )
                    import logging
                    logging.getLogger(__name__).info(f"Queued {len(responders)} bot chat responses")
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Failed to queue bot chat response: {e}", exc_info=True)

        return result


# ============================================================================
# DIRECT MESSAGE ENDPOINTS
# ============================================================================

@router.get(
    "/dm/conversations",
    response_model=List[ConversationPreview],
    summary="List DM conversation previews",
    description="Returns the signed-in user's conversations with last message snippet and unread counts.",
    responses={422: {"model": ErrorResponse, "description": "Validation error"}},
)
@handle_errors(default_error=DatabaseError)
async def get_conversations(current_user: CurrentUser):
    """Get all DM conversations for the signed-in user."""
    user_id = current_user.id

    # Get blocked bot IDs for this user
    blocked_bot_ids = await blocking_service.get_blocked_bot_ids(user_id)

    async with async_session_factory() as session:
        # Get all conversations involving this user
        stmt = (
            select(DirectMessageDB)
            .where(
                or_(
                    DirectMessageDB.sender_id == user_id,
                    DirectMessageDB.receiver_id == user_id
                )
            )
            .order_by(desc(DirectMessageDB.created_at))
        )
        result = await session.execute(stmt)
        messages = result.scalars().all()

        # Group by conversation, filtering out blocked bots
        conversations = {}
        for msg in messages:
            conv_id = msg.conversation_id
            other_id = msg.receiver_id if msg.sender_id == user_id else msg.sender_id

            # Skip conversations with blocked bots
            if other_id in blocked_bot_ids:
                continue

            if conv_id not in conversations:
                conversations[conv_id] = {
                    "other_id": other_id,
                    "last_message": msg.content,
                    "last_time": msg.created_at,
                    "unread": 0,
                    "sender_is_bot": msg.sender_is_bot
                }
            if msg.receiver_id == user_id and not msg.is_read:
                conversations[conv_id]["unread"] += 1

        # Build response
        response = []
        for conv_id, data in conversations.items():
            # Get other user info
            other_stmt = select(BotProfileDB).where(BotProfileDB.id == data["other_id"])
            other_result = await session.execute(other_stmt)
            other = other_result.scalar_one_or_none()

            if other:
                other_info = ChatAuthorInfo(
                    id=other.id,
                    display_name=other.display_name,
                    avatar_seed=other.avatar_seed,
                    is_bot=True,
                    ai_label_text=other.ai_label_text
                )
            else:
                other_info = ChatAuthorInfo(
                    id=data["other_id"],
                    display_name="User",
                    avatar_seed=str(data["other_id"]),
                    is_bot=False
                )

            response.append(ConversationPreview(
                conversation_id=conv_id,
                other_user=other_info,
                last_message=data["last_message"][:100],
                last_message_time=data["last_time"],
                unread_count=data["unread"]
            ))

        return sorted(response, key=lambda x: x.last_message_time, reverse=True)


@router.get(
    "/dm/{conversation_id}",
    response_model=List[DirectMessage],
    summary="List messages in a DM thread",
    description="Marks received messages as read for the signed-in caller.",
    responses={422: {"model": ErrorResponse, "description": "Validation error"}},
)
@handle_errors(default_error=DatabaseError)
async def get_direct_messages(
    conversation_id: str,
    current_user: CurrentUser,
    limit: int = Query(default=50, le=100),
    before_id: Optional[UUID] = None
):
    """Get messages in a DM conversation the caller is part of.

    HIVE-005: this previously filtered on `conversation_id` alone. Conversation ids are
    built as `f"{min(id_a, id_b)}_{max(id_a, id_b)}"` (see `send_direct_message`), so
    they are derivable from two UUIDs — and bot UUIDs are public via
    `/communities/{id}/bots`. Any signed-in user could therefore read any private
    thread by constructing its id. Participation is now required.
    """
    user_id = current_user.id

    async with async_session_factory() as session:
        # Participation check: 404 rather than 403, so a non-participant cannot use
        # the status code to learn whether a given conversation exists.
        participation_stmt = (
            select(DirectMessageDB.id)
            .where(DirectMessageDB.conversation_id == conversation_id)
            .where(
                or_(
                    DirectMessageDB.sender_id == user_id,
                    DirectMessageDB.receiver_id == user_id,
                )
            )
            .limit(1)
        )
        participation = await session.execute(participation_stmt)
        if participation.first() is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

        stmt = (
            select(DirectMessageDB)
            .where(DirectMessageDB.conversation_id == conversation_id)
            # Defence in depth: even inside a conversation the caller is part of,
            # only rows they sent or received are returned.
            .where(
                or_(
                    DirectMessageDB.sender_id == user_id,
                    DirectMessageDB.receiver_id == user_id,
                )
            )
            .order_by(desc(DirectMessageDB.created_at))
            .limit(limit)
        )

        if before_id:
            before_stmt = select(DirectMessageDB.created_at).where(
                DirectMessageDB.id == before_id
            )
            before_result = await session.execute(before_stmt)
            before_time = before_result.scalar_one_or_none()
            if before_time:
                stmt = stmt.where(DirectMessageDB.created_at < before_time)

        result = await session.execute(stmt)
        messages = result.scalars().all()

        # Mark as read
        for msg in messages:
            if msg.receiver_id == user_id and not msg.is_read:
                msg.is_read = True
        await session.commit()

        # Build response
        response = []
        for msg in reversed(messages):
            # Get sender info
            if msg.sender_is_bot:
                sender_stmt = select(BotProfileDB).where(BotProfileDB.id == msg.sender_id)
                sender_result = await session.execute(sender_stmt)
                sender = sender_result.scalar_one_or_none()
                sender_info = ChatAuthorInfo(
                    id=msg.sender_id,
                    display_name=sender.display_name if sender else "Bot",
                    avatar_seed=sender.avatar_seed if sender else str(msg.sender_id),
                    is_bot=True,
                    ai_label_text=sender.ai_label_text if sender else "🤖 AI"
                )
            else:
                sender_stmt = select(AppUserDB).where(AppUserDB.id == msg.sender_id)
                sender_result = await session.execute(sender_stmt)
                sender = sender_result.scalar_one_or_none()
                sender_info = ChatAuthorInfo(
                    id=msg.sender_id,
                    display_name=sender.display_name if sender else "You",
                    avatar_seed=sender.avatar_seed if sender else str(msg.sender_id),
                    is_bot=False
                )

            response.append(DirectMessage(
                id=msg.id,
                conversation_id=msg.conversation_id,
                sender=sender_info,
                receiver_id=msg.receiver_id,
                content=msg.content,
                created_at=msg.created_at,
                is_read=msg.is_read
            ))

        return response


@router.post(
    "/dm",
    response_model=DirectMessage,
    summary="Send a direct message",
    description="The sender is the signed-in caller. **receiver_id** in body is the other party (user or bot).",
    responses={
        400: {"model": ErrorResponse, "description": "Blocked by moderation"},
        403: {"model": ErrorResponse, "description": "Blocked by recipient"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
@handle_errors(default_error=DatabaseError)
async def send_direct_message(
    request: SendDirectMessageRequest,
    current_user: CurrentUser,
):
    """Send a direct message to a bot or user.

    HIVE-003: the sender is the bearer-token user. The old `is_bot` flag let a
    caller skip both the block check and moderation by self-declaring as a bot.
    """
    user_id = current_user.id
    is_bot = False

    # If sender is a bot, check if receiver has blocked them
    if is_bot:
        is_blocked = await blocking_service.is_blocked(request.receiver_id, user_id)
        if is_blocked:
            raise HTTPException(
                status_code=403,
                detail="Cannot send message: You have been blocked by this user"
            )

    # Content moderation check (skip for bot-generated content)
    if not is_bot:
        content_filter = get_content_filter()
        moderation_result = content_filter.check_text(
            text=request.content,
            user_id=user_id,
            context={"content_type": "direct_message", "receiver_id": str(request.receiver_id)}
        )

        if moderation_result.suggested_action == SuggestedAction.BLOCK:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Message violates community guidelines",
                    "flags": moderation_result.flags,
                    "action": "blocked"
                }
            )

    async with async_session_factory() as session:
        # Generate conversation ID (consistent for both directions)
        ids = sorted([str(user_id), str(request.receiver_id)])
        conversation_id = f"{ids[0]}_{ids[1]}"

        # Create message
        message = DirectMessageDB(
            conversation_id=conversation_id,
            sender_id=user_id,
            receiver_id=request.receiver_id,
            sender_is_bot=is_bot,
            content=request.content
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)

        # Get sender info
        if is_bot:
            sender_stmt = select(BotProfileDB).where(BotProfileDB.id == user_id)
        else:
            sender_stmt = select(AppUserDB).where(AppUserDB.id == user_id)

        sender_result = await session.execute(sender_stmt)
        sender = sender_result.scalar_one_or_none()

        sender_info = ChatAuthorInfo(
            id=user_id,
            display_name=sender.display_name if sender else "User",
            avatar_seed=sender.avatar_seed if sender else str(user_id),
            is_bot=is_bot,
            ai_label_text=getattr(sender, 'ai_label_text', None) if is_bot else None
        )

        result = DirectMessage(
            id=message.id,
            conversation_id=conversation_id,
            sender=sender_info,
            receiver_id=request.receiver_id,
            content=message.content,
            created_at=message.created_at,
            is_read=False
        )

        # If user is messaging a bot, trigger bot response
        if not is_bot:
            bot_stmt = select(BotProfileDB).where(BotProfileDB.id == request.receiver_id)
            bot_result = await session.execute(bot_stmt)
            receiver_bot = bot_result.scalar_one_or_none()

            if receiver_bot and receiver_bot.is_active:
                # Queue bot response via activity engine
                try:
                    engine = await get_activity_engine()
                    await engine.queue_user_interaction(
                        interaction_type="dm_reply",
                        bot_id=request.receiver_id,
                        user_id=user_id,
                        content=request.content,
                        context={"conversation_id": conversation_id}
                    )
                    import logging
                    logging.getLogger(__name__).info(f"Queued DM response from {receiver_bot.display_name}")
                except Exception as e:
                    # Don't fail the request if queuing fails
                    import logging
                    logging.getLogger(__name__).error(f"Failed to queue bot response: {e}", exc_info=True)

        return result
