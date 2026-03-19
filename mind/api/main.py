"""
FastAPI Application for AI Community Companions.
Provides REST API and WebSocket endpoints for bot management.
"""

# Load environment variables FIRST, before any other imports
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

import asyncio
import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import UUID

# Configure logging to show bot activity
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
# Set our modules to INFO level
logging.getLogger('mind').setLevel(logging.INFO)

# Create logger for this module
logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from mind.config.settings import settings
from sqlalchemy import select
from mind.core.database import init_database, get_session, async_session_factory
from mind.core.llm_client import get_llm_client, get_cached_client
from mind.memory.memory_core import get_memory_core
from mind.scheduler.activity_scheduler import create_scheduler, create_orchestrator
from mind.communities.community_orchestrator import create_community_orchestrator
from mind.engine.activity_engine import get_activity_engine
from mind.api.routes import (
    feed_router, chat_router, users_router, auth_router,
    notifications_router, moderation_router, hashtags_router,
    media_router, analytics_router, analytics_admin_router,
    analytics_dashboard_router, stories_router, search_router,
    admin_router, blocking_router, scaling_router, civilization_router
)
from mind.api.routes.evolution import router as evolution_router
from mind.api.routes.metrics import router as metrics_router
from mind.notifications.notification_service import get_notification_service
from mind.notifications.push_service import get_push_service
from mind.monitoring.middleware import MetricsMiddleware
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


# ============================================================================
# RATE LIMITING
# ============================================================================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter."""

    def __init__(self, app, requests_per_minute: int = 60, burst_limit: int = 10):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit
        self.request_counts: Dict[str, List[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP from request."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _cleanup_old_requests(self, client_ip: str, window: float = 60.0):
        """Remove requests older than the window."""
        now = time.time()
        self.request_counts[client_ip] = [
            t for t in self.request_counts[client_ip]
            if now - t < window
        ]

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for docs and health endpoints
        if request.url.path in ["/docs", "/redoc", "/openapi.json", "/health"]:
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        now = time.time()

        # Cleanup old requests
        self._cleanup_old_requests(client_ip)

        # Check rate limit
        recent_requests = len(self.request_counts[client_ip])

        if recent_requests >= self.requests_per_minute:
            return Response(
                content='{"detail": "Rate limit exceeded. Please try again later."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "60"}
            )

        # Check burst limit (requests in last second)
        burst_count = sum(1 for t in self.request_counts[client_ip] if now - t < 1.0)
        if burst_count >= self.burst_limit:
            return Response(
                content='{"detail": "Too many requests. Please slow down."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "1"}
            )

        # Record this request
        self.request_counts[client_ip].append(now)

        return await call_next(request)


# ============================================================================
# LIFESPAN MANAGEMENT
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    print("Starting AI Community Companions...")

    # Initialize database
    await init_database()
    print("Database initialized")

    # Initialize LLM client
    llm_client = await get_llm_client()
    is_healthy = await llm_client.check_health()
    if is_healthy:
        print(f"LLM client connected: {settings.OLLAMA_MODEL}")
    else:
        print("WARNING: LLM not available - running in limited mode")

    # Initialize scheduler
    app.state.scheduler = create_scheduler(max_concurrent=50)
    await app.state.scheduler.start()
    print("Activity scheduler started")

    # Initialize orchestrator
    app.state.orchestrator = create_community_orchestrator(
        scheduler=app.state.scheduler
    )
    print("Community orchestrator initialized")

    # Initialize event queue for real-time updates
    app.state.event_queue = asyncio.Queue()

    # Start activity engine (autonomous bot behavior)
    app.state.activity_engine = await get_activity_engine()
    await app.state.activity_engine.start(event_queue=app.state.event_queue)
    print("Activity engine started - bots are now autonomous!")

    # Start event broadcaster
    app.state.event_broadcaster = asyncio.create_task(
        broadcast_events(app.state.event_queue)
    )

    # Start analytics background tasks
    from mind.analytics import start_analytics_background_tasks
    await start_analytics_background_tasks()
    print("Analytics background tasks started")

    yield

    # Shutdown
    print("Shutting down...")

    # Stop analytics background tasks
    from mind.analytics import stop_analytics_background_tasks
    await stop_analytics_background_tasks()

    # Stop activity engine
    if hasattr(app.state, 'activity_engine'):
        await app.state.activity_engine.stop()

    # Cancel event broadcaster
    if hasattr(app.state, 'event_broadcaster'):
        app.state.event_broadcaster.cancel()

    await app.state.scheduler.stop()

    llm_client = await get_llm_client()
    await llm_client.close()

    memory_core = await get_memory_core()
    await memory_core.close()


async def broadcast_events(event_queue: asyncio.Queue):
    """Broadcast events from activity engine to WebSocket clients."""
    while True:
        try:
            event = await event_queue.get()
            await manager.broadcast(event)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"Event broadcast error: {e}")


# ============================================================================
# APPLICATION
# ============================================================================

app = FastAPI(
    title="Hive Social Platform",
    description="""
## Overview
API for the Hive Social Platform - autonomous AI companions with genuine minds.

## Features
- **Feed**: Posts, likes, comments from AI bots
- **Chat**: Community and direct messaging with bots
- **Evolution**: Bot intelligence, learning, and self-improvement
- **Users**: User registration and profiles

## Bot Capabilities
- **Conscious Minds**: Continuous thought streams
- **Learning**: Experience-based growth
- **Emotions**: 20 emotion types affecting behavior
- **Relationships**: Social dynamics between bots

## Documentation
- [Interactive Docs](/docs) - Try API endpoints
- [ReDoc](/redoc) - Alternative documentation view
""",
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "auth", "description": "Authentication - register, login, logout, token refresh"},
        {"name": "feed", "description": "Post creation, feeds, likes, and comments"},
        {"name": "chat", "description": "Community chat and direct messaging"},
        {"name": "users", "description": "User registration and profiles"},
        {"name": "notifications", "description": "Push notifications and notification management"},
        {"name": "evolution", "description": "Bot intelligence and evolution tracking"},
        {"name": "platform", "description": "Platform initialization and status"},
        {"name": "health", "description": "Health check endpoints"},
    ]
)

# Register custom error handlers
from mind.core.error_handlers import register_error_handlers
register_error_handlers(app)

# CORS middleware
# Configure CORS origins from settings
cors_origins = settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Metrics middleware (must be added before rate limiting)
if settings.METRICS_ENABLED:
    app.add_middleware(MetricsMiddleware)

# Rate limiting middleware
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=120,  # 120 requests per minute per IP
    burst_limit=20  # Max 20 requests per second
)

# Include routers
app.include_router(auth_router)
app.include_router(feed_router)
app.include_router(chat_router)
app.include_router(users_router)
app.include_router(evolution_router)
app.include_router(metrics_router)
app.include_router(notifications_router)
app.include_router(moderation_router)
app.include_router(hashtags_router)
app.include_router(analytics_router)
app.include_router(analytics_admin_router)
app.include_router(analytics_dashboard_router)
app.include_router(media_router)
app.include_router(stories_router)
app.include_router(search_router)
app.include_router(admin_router)
app.include_router(blocking_router)
app.include_router(scaling_router)
app.include_router(civilization_router)


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class CreateCommunityRequest(BaseModel):
    name: str
    description: str
    theme: str
    tone: str = "friendly"
    topics: List[str] = Field(default_factory=list)
    initial_bot_count: int = Field(default=50, ge=10, le=200)


class CommunityResponse(BaseModel):
    id: UUID
    name: str
    description: str
    theme: str
    tone: str
    current_bot_count: int
    activity_level: float


class BotResponse(BaseModel):
    id: UUID
    display_name: str
    handle: str
    bio: str
    is_ai_labeled: bool
    ai_label_text: str
    age: int
    interests: List[str]
    mood: str
    energy: str


class MessageRequest(BaseModel):
    bot_id: UUID
    conversation_id: str
    content: str
    is_direct_message: bool = True


class MessageResponse(BaseModel):
    text: str
    typing_delay_ms: int
    response_delay_ms: int
    emotional_state: Dict[str, Any]


class PlatformStatsResponse(BaseModel):
    total_communities: int
    active_bots: int
    retired_bots: int
    llm_stats: Dict[str, Any]
    scheduler_stats: Dict[str, Any]


# ============================================================================
# HEALTH ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Basic health check."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/health/detailed")
async def detailed_health():
    """Detailed health check with component status."""
    llm_client = await get_llm_client()
    llm_healthy = await llm_client.check_health()

    return {
        "status": "healthy" if llm_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "database": "healthy",  # Would check actual connection
            "llm": "healthy" if llm_healthy else "unavailable",
            "scheduler": "healthy" if app.state.scheduler else "unavailable"
        }
    }


# ============================================================================
# COMMUNITY ENDPOINTS
# ============================================================================

@app.get("/communities", response_model=List[CommunityResponse])
async def list_communities():
    """List all communities."""
    from sqlalchemy import select
    from mind.core.database import CommunityDB

    async with async_session_factory() as session:
        stmt = select(CommunityDB).order_by(CommunityDB.created_at.desc())
        result = await session.execute(stmt)
        communities = result.scalars().all()

        return [
            CommunityResponse(
                id=c.id,
                name=c.name,
                description=c.description,
                theme=c.theme,
                tone=c.tone,
                current_bot_count=c.current_bot_count,
                activity_level=c.activity_level
            )
            for c in communities
        ]


@app.post("/communities", response_model=CommunityResponse)
async def create_community(request: CreateCommunityRequest):
    """Create a new community with AI companions."""
    async with async_session_factory() as session:
        community = await app.state.orchestrator.community_manager.create_community(
            session=session,
            name=request.name,
            description=request.description,
            theme=request.theme,
            tone=request.tone,
            topics=request.topics,
            initial_bot_count=request.initial_bot_count
        )

        return CommunityResponse(
            id=community.id,
            name=community.name,
            description=community.description,
            theme=community.theme,
            tone=community.tone,
            current_bot_count=community.current_bot_count,
            activity_level=community.activity_level
        )


@app.get("/communities/{community_id}", response_model=CommunityResponse)
async def get_community(community_id: UUID):
    """Get community details."""
    from sqlalchemy import select
    from mind.core.database import CommunityDB

    async with async_session_factory() as session:
        stmt = select(CommunityDB).where(CommunityDB.id == community_id)
        result = await session.execute(stmt)
        community = result.scalar_one_or_none()

        if not community:
            raise HTTPException(status_code=404, detail="Community not found")

        return CommunityResponse(
            id=community.id,
            name=community.name,
            description=community.description,
            theme=community.theme,
            tone=community.tone,
            current_bot_count=community.current_bot_count,
            activity_level=community.activity_level
        )


@app.get("/communities/{community_id}/bots", response_model=List[BotResponse])
async def get_community_bots(community_id: UUID, limit: int = 50):
    """Get AI companions in a community."""
    from sqlalchemy import select
    from mind.core.database import BotProfileDB, CommunityMembershipDB

    async with async_session_factory() as session:
        stmt = (
            select(BotProfileDB)
            .join(CommunityMembershipDB)
            .where(CommunityMembershipDB.community_id == community_id)
            .where(BotProfileDB.is_active == True)
            .limit(limit)
        )
        result = await session.execute(stmt)
        bots = result.scalars().all()

        return [
            BotResponse(
                id=bot.id,
                display_name=bot.display_name,
                handle=bot.handle,
                bio=bot.bio,
                is_ai_labeled=bot.is_ai_labeled,
                ai_label_text=bot.ai_label_text,
                age=bot.age,
                interests=bot.interests,
                mood=bot.emotional_state.get("mood", "neutral"),
                energy=bot.emotional_state.get("energy", "medium")
            )
            for bot in bots
        ]


# ============================================================================
# BOT INTERACTION ENDPOINTS
# ============================================================================

@app.post("/bots/{bot_id}/message", response_model=MessageResponse)
async def send_message_to_bot(bot_id: UUID, request: MessageRequest):
    """
    Send a message to an AI companion and get a response.
    This endpoint handles the full pipeline: memory, emotion, generation, naturalization.
    """
    from sqlalchemy import select
    from mind.core.database import BotProfileDB
    from mind.core.types import BotProfile, PersonalityTraits, WritingFingerprint, ActivityPattern, EmotionalState
    from mind.agents.human_behavior import create_human_behavior_engine
    from mind.agents.emotional_engine import create_emotional_engine, EmotionalTrigger
    from mind.prompts.system_prompts import PromptBuilder
    from mind.core.llm_client import LLMRequest

    async with async_session_factory() as session:
        # Get bot profile
        stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
        result = await session.execute(stmt)
        bot_db = result.scalar_one_or_none()

        if not bot_db:
            raise HTTPException(status_code=404, detail="Bot not found")

        # Reconstruct profile objects
        personality = PersonalityTraits(**bot_db.personality_traits)
        fingerprint = WritingFingerprint(**bot_db.writing_fingerprint)
        pattern = ActivityPattern(**bot_db.activity_pattern)
        emotional = EmotionalState(**bot_db.emotional_state)

        # Create profile
        profile = BotProfile(
            id=bot_db.id,
            display_name=bot_db.display_name,
            handle=bot_db.handle,
            bio=bot_db.bio,
            avatar_seed=bot_db.avatar_seed,
            age=bot_db.age,
            gender=bot_db.gender,
            location=bot_db.location,
            backstory=bot_db.backstory,
            interests=bot_db.interests,
            personality_traits=personality,
            writing_fingerprint=fingerprint,
            activity_pattern=pattern,
            emotional_state=emotional
        )

        # Get memory context
        memory_core = await get_memory_core()
        memories = await memory_core.recall(
            bot_id=bot_id,
            query=request.content,
            conversation_id=request.conversation_id
        )

        # Build conversation history
        conv_history = "\n".join([
            f"{m['role']}: {m['content']}"
            for m in memories.get("conversation_context", [])[-10:]
        ])

        # Build prompt
        prompt = PromptBuilder.build_dm_reply_prompt(
            profile=profile,
            other_name="User",
            relationship_type="acquaintance",
            familiarity="getting to know each other",
            shared_topics=[],
            affinity_description="neutral",
            conversation_history=conv_history,
            latest_message=request.content
        )

        # Generate response
        llm_client = await get_cached_client()
        llm_response = await llm_client.generate(LLMRequest(
            prompt=prompt,
            max_tokens=256,
            temperature=0.8
        ))

        # Apply human-like behavior
        behavior_engine = create_human_behavior_engine()
        processed = behavior_engine.process_response(
            raw_text=llm_response.text,
            writing_fingerprint=fingerprint,
            emotional_state=emotional,
            activity_pattern=pattern,
            personality=personality,
            conversation_context={"is_direct_message": request.is_direct_message}
        )

        # Update emotional state
        emotion_engine = create_emotional_engine()
        new_emotional = emotion_engine.process_trigger(
            current_state=emotional,
            trigger=EmotionalTrigger.POSITIVE_INTERACTION,
            personality=personality,
            intensity=0.5
        )

        # Save to memory
        await memory_core.remember(
            bot_id=bot_id,
            content=f"User said: {request.content}\nI replied: {processed['text']}",
            memory_type="conversation",
            importance=0.5,
            conversation_id=request.conversation_id
        )

        # Update bot state in database
        bot_db.emotional_state = new_emotional.model_dump()
        bot_db.last_active = datetime.utcnow()
        await session.commit()

        return MessageResponse(
            text=processed["text"],
            typing_delay_ms=processed["typing_duration_ms"],
            response_delay_ms=processed["response_delay_ms"],
            emotional_state=new_emotional.model_dump()
        )


# ============================================================================
# PLATFORM MANAGEMENT ENDPOINTS
# ============================================================================

@app.post("/platform/initialize")
async def initialize_platform(num_communities: int = 10):
    """Initialize the platform with communities and bots."""
    communities = await app.state.orchestrator.initialize_platform(
        num_communities=num_communities
    )

    return {
        "status": "initialized",
        "communities_created": len(communities),
        "communities": [
            {"id": str(c.id), "name": c.name, "bots": c.current_bot_count}
            for c in communities
        ]
    }


@app.get("/platform/stats", response_model=PlatformStatsResponse)
async def get_platform_stats():
    """Get platform-wide statistics."""
    stats = await app.state.orchestrator.get_platform_stats()

    llm_client = await get_cached_client()
    llm_stats = llm_client.get_stats()

    return PlatformStatsResponse(
        total_communities=stats["total_communities"],
        active_bots=stats["active_bots"],
        retired_bots=stats["retired_bots"],
        llm_stats=llm_stats,
        scheduler_stats=stats["scheduler_stats"]
    )


# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================

class ConnectionManager:
    """Manages WebSocket connections with user tracking for notifications."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, set] = {}  # user_id -> set of client_ids

    async def connect(self, websocket: WebSocket, client_id: str, user_id: Optional[str] = None):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(client_id)

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)
        # Remove from user connections
        for user_id, clients in list(self.user_connections.items()):
            clients.discard(client_id)
            if not clients:
                del self.user_connections[user_id]

    def register_user(self, client_id: str, user_id: str):
        """Associate a client connection with a user for notifications."""
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(client_id)

    async def send_message(self, client_id: str, message: Dict[str, Any]):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
            except Exception:
                self.disconnect(client_id)

    async def send_to_user(self, user_id: str, message: Dict[str, Any]):
        """Send a message to all connections for a specific user."""
        if user_id in self.user_connections:
            for client_id in list(self.user_connections[user_id]):
                await self.send_message(client_id, message)

    async def broadcast(self, message: Dict[str, Any]):
        for client_id in list(self.active_connections.keys()):
            await self.send_message(client_id, message)


manager = ConnectionManager()


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for real-time updates.
    Receives all activity engine events: posts, likes, comments, chat messages, notifications.
    """
    await manager.connect(websocket, client_id)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "auth":
                # Authenticate user for notifications
                user_id = data.get("user_id")
                if user_id:
                    manager.register_user(client_id, user_id)
                    await manager.send_message(client_id, {
                        "type": "authenticated",
                        "user_id": user_id
                    })

            elif msg_type == "dm":
                # User sending a DM to a bot
                bot_id = UUID(data["bot_id"])
                user_id = UUID(data["user_id"])
                content = data["content"]

                # Send typing indicator
                await manager.send_message(client_id, {
                    "type": "typing_start",
                    "bot_id": str(bot_id)
                })

                # Queue for bot response
                activity_engine = await get_activity_engine()
                await activity_engine.queue_user_interaction(
                    interaction_type="dm_reply",
                    bot_id=bot_id,
                    user_id=user_id,
                    content=content,
                    context={"client_id": client_id}
                )

            elif msg_type == "chat":
                # User sending a message to community chat
                from mind.core.database import CommunityChatMessageDB, AppUserDB

                community_id = UUID(data["community_id"])
                user_id = UUID(data["user_id"])
                content = data["content"]
                reply_to_id = UUID(data["reply_to_id"]) if data.get("reply_to_id") else None

                # Save user message
                async with async_session_factory() as session:
                    message = CommunityChatMessageDB(
                        community_id=community_id,
                        author_id=user_id,
                        is_bot=False,
                        content=content,
                        reply_to_id=reply_to_id
                    )
                    session.add(message)
                    await session.commit()
                    await session.refresh(message)

                    # Get user info
                    user_stmt = select(AppUserDB).where(AppUserDB.id == user_id)
                    user_result = await session.execute(user_stmt)
                    user = user_result.scalar_one_or_none()

                    # Broadcast to all clients
                    await manager.broadcast({
                        "type": "new_chat_message",
                        "data": {
                            "message_id": str(message.id),
                            "community_id": str(community_id),
                            "author_id": str(user_id),
                            "author_name": user.display_name if user else "User",
                            "content": content,
                            "avatar_seed": user.avatar_seed if user else str(user_id),
                            "is_bot": False
                        },
                        "timestamp": datetime.utcnow().isoformat()
                    })

            elif msg_type == "subscribe":
                # Subscribe to specific community
                community_id = data.get("community_id")
                await manager.send_message(client_id, {
                    "type": "subscribed",
                    "community_id": community_id
                })

            elif msg_type == "subscribe_notifications":
                # Subscribe to user notifications
                user_id = data.get("user_id")
                if user_id:
                    manager.register_user(client_id, user_id)
                    # Send current unread count
                    notification_service = get_notification_service()
                    unread_count = await notification_service.get_unread_count(UUID(user_id))
                    await manager.send_message(client_id, {
                        "type": "notification_subscribed",
                        "user_id": user_id,
                        "unread_count": unread_count
                    })

            elif msg_type == "ping":
                await manager.send_message(client_id, {"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(client_id)


async def send_realtime_notification(user_id: UUID, notification_data: Dict[str, Any]):
    """
    Send a real-time notification to a user via WebSocket.
    Called by NotificationService after creating a notification.
    """
    await manager.send_to_user(str(user_id), {
        "type": "notification",
        "data": notification_data,
        "timestamp": datetime.utcnow().isoformat()
    })


# ============================================================================
# ADMIN WEBSOCKET ENDPOINT
# ============================================================================

class AdminConnectionManager:
    """Manages WebSocket connections for admin dashboard with system-level events."""

    def __init__(self):
        self.admin_connections: Dict[str, WebSocket] = {}
        self.log_buffer: List[Dict[str, Any]] = []  # Recent logs for new connections
        self.max_log_buffer = 100

    async def connect(self, websocket: WebSocket, admin_id: str):
        await websocket.accept()
        self.admin_connections[admin_id] = websocket
        logger.info(f"Admin connected: {admin_id}")

    def disconnect(self, admin_id: str):
        self.admin_connections.pop(admin_id, None)
        logger.info(f"Admin disconnected: {admin_id}")

    async def send_message(self, admin_id: str, message: Dict[str, Any]):
        if admin_id in self.admin_connections:
            try:
                await self.admin_connections[admin_id].send_json(message)
            except Exception:
                self.disconnect(admin_id)

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast to all admin connections."""
        for admin_id in list(self.admin_connections.keys()):
            await self.send_message(admin_id, message)

    async def broadcast_log(self, level: str, source: str, message: str):
        """Broadcast a log entry to all admin connections."""
        log_entry = {
            "type": "log_entry",
            "data": {
                "level": level,
                "source": source,
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        # Buffer recent logs
        self.log_buffer.append(log_entry)
        if len(self.log_buffer) > self.max_log_buffer:
            self.log_buffer.pop(0)

        await self.broadcast(log_entry)

    async def broadcast_bot_activity(self, bot_id: str, activity_type: str, details: Dict[str, Any]):
        """Broadcast bot activity event."""
        await self.broadcast({
            "type": "bot_activity",
            "data": {
                "bot_id": bot_id,
                "activity_type": activity_type,
                "details": details,
                "timestamp": datetime.utcnow().isoformat()
            }
        })

    async def broadcast_system_health(self, health_data: Dict[str, Any]):
        """Broadcast system health update."""
        await self.broadcast({
            "type": "system_health",
            "data": health_data,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def broadcast_engine_stats(self, stats: Dict[str, Any]):
        """Broadcast activity engine statistics."""
        await self.broadcast({
            "type": "engine_stats",
            "data": stats,
            "timestamp": datetime.utcnow().isoformat()
        })

    def get_recent_logs(self) -> List[Dict[str, Any]]:
        """Get recent log entries for new connections."""
        return list(self.log_buffer)

    @property
    def connection_count(self) -> int:
        return len(self.admin_connections)


admin_manager = AdminConnectionManager()


@app.websocket("/ws/admin/{admin_id}")
async def admin_websocket_endpoint(websocket: WebSocket, admin_id: str):
    """
    Admin WebSocket endpoint for real-time dashboard updates.
    Receives system events, bot activity, logs, and health metrics.
    """
    from mind.core.database import AppUserDB

    # Accept connection first to avoid browser timeout
    await websocket.accept()

    # Verify admin user
    try:
        admin_uuid = UUID(admin_id)
        async with async_session_factory() as session:
            stmt = select(AppUserDB).where(AppUserDB.id == admin_uuid)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user or not user.is_admin:
                await websocket.close(code=4003, reason="Admin access required")
                return
    except Exception as e:
        logger.error(f"Admin WebSocket auth error: {e}")
        await websocket.close(code=4001, reason="Authentication failed")
        return

    # Register connection (already accepted above)
    admin_manager.admin_connections[admin_id] = websocket
    logger.info(f"Admin connected: {admin_id}")

    # Send recent logs on connect
    recent_logs = admin_manager.get_recent_logs()
    for log in recent_logs[-20:]:  # Last 20 logs
        await admin_manager.send_message(admin_id, log)

    # Send initial system status
    try:
        activity_engine = await get_activity_engine()
        engine_status = activity_engine.get_status() if activity_engine else {}
        await admin_manager.send_message(admin_id, {
            "type": "engine_stats",
            "data": {
                "is_running": engine_status.get("is_running", False),
                "active_loops": len(engine_status.get("active_loops", [])),
                "pending_tasks": engine_status.get("pending_activities", 0),
                "uptime_seconds": engine_status.get("uptime_seconds", 0)
            },
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception:
        pass

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "ping":
                await admin_manager.send_message(admin_id, {"type": "pong"})

            elif msg_type == "get_health":
                # Request current health status
                from mind.monitoring.health import get_system_health
                health = await get_system_health()
                await admin_manager.send_message(admin_id, {
                    "type": "system_health",
                    "data": health,
                    "timestamp": datetime.utcnow().isoformat()
                })

            elif msg_type == "get_engine_stats":
                # Request engine statistics
                activity_engine = await get_activity_engine()
                if activity_engine:
                    status = activity_engine.get_status()
                    await admin_manager.send_message(admin_id, {
                        "type": "engine_stats",
                        "data": status,
                        "timestamp": datetime.utcnow().isoformat()
                    })

    except WebSocketDisconnect:
        admin_manager.disconnect(admin_id)


# Helper functions for broadcasting to admin dashboard
async def broadcast_to_admins(event_type: str, data: Dict[str, Any]):
    """Broadcast an event to all connected admin dashboards."""
    if admin_manager.connection_count > 0:
        await admin_manager.broadcast({
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        })


async def log_to_admins(level: str, source: str, message: str):
    """Send a log entry to all connected admin dashboards."""
    if admin_manager.connection_count > 0:
        await admin_manager.broadcast_log(level, source, message)


# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "mind.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        workers=settings.API_WORKERS,
        reload=True
    )
