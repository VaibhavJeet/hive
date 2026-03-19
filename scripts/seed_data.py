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
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mind.core.database import async_session_factory, init_db
from mind.agents.personality_generator import PersonalityGenerator


async def seed_bots(count: int = 10) -> None:
    """Generate and save bot profiles."""
    print(f"Generating {count} bot profiles...")

    generator = PersonalityGenerator()

    async with async_session_factory() as session:
        for i in range(count):
            try:
                profile = await generator.generate_personality()
                # The generator handles DB insertion
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
        await init_db()

    if args.users > 0:
        await seed_users(args.users)

    if args.bots > 0:
        await seed_bots(args.bots)


if __name__ == "__main__":
    asyncio.run(main())
