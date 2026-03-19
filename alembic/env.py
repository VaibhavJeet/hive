"""
Alembic Environment Configuration for AI Community Companions.

This module configures Alembic for async SQLAlchemy with PostgreSQL.
It imports all models from the database module and reads the database URL
from environment variables.
"""

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Add the project root to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Import the Base and all models from our database module
# This ensures all models are registered with the metadata
from mind.core.database import (
    Base,
    # Bot models
    BotProfileDB,
    MemoryItemDB,
    RelationshipDB,
    # Community models
    CommunityDB,
    CommunityMembershipDB,
    # Activity models
    ScheduledActivityDB,
    GeneratedContentDB,
    # Analytics tracking models
    PostViewDB,
    SessionDB,
    DailyMetricsDB,
    # Media models
    MediaDB,
    # Social feed models
    PostDB,
    PostLikeDB,
    PostCommentDB,
    # Community chat models
    CommunityChatMessageDB,
    # Direct message models
    DirectMessageDB,
    # User models
    AppUserDB,
    RefreshTokenDB,
    # Analytics models
    BotMetricsDB,
    SystemMetricsDB,
    # Bot mind & learning persistence
    BotMindStateDB,
    BotLearningStateDB,
    BotSkillDB,
    # Scaling & retirement models
    RetiredBotDB,
    ArchivedMemoryDB,
    CommunityLimitsDB,
    # Story models
    StoryDB,
    StoryViewDB,
    # Blocking & flagging models
    UserBlockDB,
    BotBehaviorFlagDB,
    # Admin & moderation models
    AdminAuditLogDB,
    FlaggedContentDB,
    SystemLogDB,
    # Notification models
    NotificationDB,
    PushSubscriptionDB,
    # Content report & moderation action models
    ContentReportDB,
    ModerationActionDB,
    # Hashtag models
    HashtagDB,
    PostHashtagDB,
    HashtagFollowDB,
)

# Import civilization models
from mind.civilization.models import (
    BotLifecycleDB,
    BotAncestryDB,
    CulturalMovementDB,
    CulturalArtifactDB,
    CivilizationEraDB,
    BotBeliefDB,
)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the target metadata for autogenerate support
target_metadata = Base.metadata

# Get database URL from environment variable
# The env var uses the AIC_ prefix as defined in settings
def get_database_url() -> str:
    """
    Get the database URL from environment variables.

    Returns the async URL for SQLAlchemy async operations.
    Falls back to a default localhost URL if not set.
    """
    url = os.getenv(
        "AIC_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/mind"
    )

    # Ensure we're using asyncpg driver for async operations
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif not url.startswith("postgresql+asyncpg://"):
        # If it has another driver, replace it with asyncpg
        if "+psycopg2" in url:
            url = url.replace("+psycopg2", "+asyncpg")

    return url


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        # Include schemas if needed
        include_schemas=True,
        # Render as batch for SQLite compatibility (optional)
        # render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode using async engine.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    # Create configuration dictionary for the async engine
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    This wraps the async migration runner.
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
