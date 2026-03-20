#!/usr/bin/env python3
"""
Seed initial data for development and testing.

Usage:
    python scripts/seed_data.py
    python scripts/seed_data.py --bots 10
    python scripts/seed_data.py --users 5 --bots 20
"""

import asyncio
import argparse
import sys
from datetime import datetime, date
from enum import Enum
from pathlib import Path
from dataclasses import asdict, is_dataclass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mind.core.database import async_session_factory, init_database
from mind.agents.personality_generator import PersonalityGenerator


def to_json_safe(obj):
    """Recursively convert dataclasses/enums/datetimes/Pydantic models to JSON-serializable dicts."""
    from pydantic import BaseModel
    if isinstance(obj, BaseModel):
        return {k: to_json_safe(v) for k, v in obj.model_dump().items()}
    elif is_dataclass(obj) and not isinstance(obj, type):
        return {k: to_json_safe(v) for k, v in asdict(obj).items()}
    elif isinstance(obj, dict):
        return {k: to_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [to_json_safe(v) for v in obj]
    elif isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, date):
        return obj.isoformat()
    return obj


async def seed_bots(count: int = 10) -> None:
    """Generate and save bot profiles."""
    from mind.core.database import BotProfileDB

    print(f"Generating {count} bot profiles...")

    generator = PersonalityGenerator()

    async with async_session_factory() as session:
        for i in range(count):
            try:
                profile = generator.generate_profile()
                bot_db = BotProfileDB(
                    id=profile.id,
                    display_name=profile.display_name,
                    handle=profile.handle,
                    bio=profile.bio,
                    avatar_seed=profile.avatar_seed,
                    is_ai_labeled=profile.is_ai_labeled,
                    ai_label_text=profile.ai_label_text,
                    age=profile.age,
                    gender=profile.gender.value if hasattr(profile.gender, 'value') else str(profile.gender),
                    location=profile.location or "",
                    backstory=profile.backstory,
                    interests=to_json_safe(profile.interests),
                    personality_traits=to_json_safe(profile.personality_traits),
                    writing_fingerprint=to_json_safe(profile.writing_fingerprint),
                    activity_pattern=to_json_safe(profile.activity_pattern),
                    emotional_state=to_json_safe(profile.emotional_state),
                )
                session.add(bot_db)
                print(f"  [{i+1}/{count}] Created: {profile.display_name} (@{profile.handle})")
            except Exception as e:
                print(f"  [{i+1}/{count}] Error: {e}")

        await session.commit()

    print(f"Done! Created {count} bots.")


async def seed_users(count: int = 5) -> None:
    """Create test user accounts."""
    from mind.core.database import UserDB
    from uuid import uuid4
    from datetime import datetime

    print(f"Creating {count} test users...")

    async with async_session_factory() as session:
        for i in range(count):
            user = UserDB(
                id=uuid4(),
                username=f"testuser{i+1}",
                email=f"test{i+1}@example.com",
                display_name=f"Test User {i+1}",
                created_at=datetime.utcnow(),
                is_active=True,
            )
            session.add(user)
            print(f"  [{i+1}/{count}] Created: {user.username}")

        await session.commit()

    print(f"Done! Created {count} users.")


async def main():
    parser = argparse.ArgumentParser(description="Seed database with initial data")
    parser.add_argument("--bots", type=int, default=10, help="Number of bots to create")
    parser.add_argument("--users", type=int, default=0, help="Number of test users to create")
    parser.add_argument("--init-db", action="store_true", help="Initialize database tables first")

    args = parser.parse_args()

    if args.init_db:
        print("Initializing database...")
        await init_database()

    if args.users > 0:
        await seed_users(args.users)

    if args.bots > 0:
        await seed_bots(args.bots)


if __name__ == "__main__":
    asyncio.run(main())
