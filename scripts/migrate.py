#!/usr/bin/env python3
"""
Database Migration Helper Script for AI Community Companions.

This script provides convenient wrappers around Alembic migration commands
with environment setup and validation.

Usage:
    python scripts/migrate.py upgrade          # Apply all pending migrations
    python scripts/migrate.py downgrade        # Rollback last migration
    python scripts/migrate.py current          # Show current revision
    python scripts/migrate.py history          # Show migration history
    python scripts/migrate.py generate "msg"   # Generate new migration
    python scripts/migrate.py heads            # Show latest migrations
    python scripts/migrate.py check            # Verify database connection

Examples:
    # Apply all pending migrations
    python scripts/migrate.py upgrade

    # Generate a new migration after model changes
    python scripts/migrate.py generate "add user preferences table"

    # Rollback to a specific revision
    python scripts/migrate.py downgrade abc123

    # Show migration history
    python scripts/migrate.py history --verbose
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(project_root / ".env")


def run_alembic_command(args: list[str]) -> int:
    """Run an alembic command with the given arguments."""
    import subprocess

    # Ensure we're in the project root
    os.chdir(project_root)

    # Build command
    cmd = ["alembic"] + args

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode


def check_database_connection() -> bool:
    """Test database connection."""
    import asyncio

    async def test_connection():
        try:
            from sqlalchemy.ext.asyncio import create_async_engine
            from sqlalchemy import text

            db_url = os.getenv(
                "AIC_DATABASE_URL",
                "postgresql+asyncpg://postgres:postgres@localhost:5432/mind"
            )

            # Ensure async driver
            if not db_url.startswith("postgresql+asyncpg://"):
                db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
                db_url = db_url.replace("+psycopg2", "+asyncpg")

            engine = create_async_engine(db_url, echo=False)

            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                result.fetchone()

            await engine.dispose()
            return True

        except Exception as e:
            print(f"Database connection failed: {e}")
            return False

    return asyncio.run(test_connection())


def cmd_upgrade(args: argparse.Namespace) -> int:
    """Apply migrations."""
    revision = args.revision if hasattr(args, 'revision') and args.revision else "head"
    return run_alembic_command(["upgrade", revision])


def cmd_downgrade(args: argparse.Namespace) -> int:
    """Rollback migrations."""
    revision = args.revision if hasattr(args, 'revision') and args.revision else "-1"
    return run_alembic_command(["downgrade", revision])


def cmd_current(args: argparse.Namespace) -> int:
    """Show current revision."""
    return run_alembic_command(["current"])


def cmd_history(args: argparse.Namespace) -> int:
    """Show migration history."""
    cmd = ["history"]
    if hasattr(args, 'verbose') and args.verbose:
        cmd.append("--verbose")
    return run_alembic_command(cmd)


def cmd_heads(args: argparse.Namespace) -> int:
    """Show latest revisions."""
    return run_alembic_command(["heads"])


def cmd_generate(args: argparse.Namespace) -> int:
    """Generate a new migration."""
    if not args.message:
        print("Error: Migration message required")
        return 1

    return run_alembic_command([
        "revision",
        "--autogenerate",
        "-m", args.message
    ])


def cmd_check(args: argparse.Namespace) -> int:
    """Check database connection and configuration."""
    print("Checking database connection...")

    db_url = os.getenv("AIC_DATABASE_URL", "")
    if not db_url:
        print("Warning: AIC_DATABASE_URL not set, using default")

    # Mask password in output
    display_url = db_url
    if "@" in display_url and ":" in display_url:
        parts = display_url.split("@")
        user_pass = parts[0].split("//")[-1]
        if ":" in user_pass:
            user = user_pass.split(":")[0]
            display_url = display_url.replace(user_pass, f"{user}:****")

    print(f"Database URL: {display_url}")

    if check_database_connection():
        print("Database connection successful!")
        return 0
    else:
        print("Database connection failed!")
        return 1


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize the database with the initial schema."""
    print("Initializing database...")
    print("Running: alembic upgrade head")
    return run_alembic_command(["upgrade", "head"])


def main():
    parser = argparse.ArgumentParser(
        description="Database migration helper for AI Community Companions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Common workflows:

  First-time setup:
    python scripts/migrate.py check    # Verify database connection
    python scripts/migrate.py init     # Apply all migrations

  After modifying models:
    python scripts/migrate.py generate "description of changes"
    python scripts/migrate.py upgrade  # Apply the new migration

  Rollback changes:
    python scripts/migrate.py downgrade       # Rollback one migration
    python scripts/migrate.py downgrade -1    # Same as above
    python scripts/migrate.py downgrade abc123  # Rollback to specific revision
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # upgrade command
    upgrade_parser = subparsers.add_parser("upgrade", help="Apply migrations")
    upgrade_parser.add_argument("revision", nargs="?", default="head",
                                 help="Revision to upgrade to (default: head)")
    upgrade_parser.set_defaults(func=cmd_upgrade)

    # downgrade command
    downgrade_parser = subparsers.add_parser("downgrade", help="Rollback migrations")
    downgrade_parser.add_argument("revision", nargs="?", default="-1",
                                   help="Revision to downgrade to (default: -1)")
    downgrade_parser.set_defaults(func=cmd_downgrade)

    # current command
    current_parser = subparsers.add_parser("current", help="Show current revision")
    current_parser.set_defaults(func=cmd_current)

    # history command
    history_parser = subparsers.add_parser("history", help="Show migration history")
    history_parser.add_argument("-v", "--verbose", action="store_true",
                                 help="Show detailed history")
    history_parser.set_defaults(func=cmd_history)

    # heads command
    heads_parser = subparsers.add_parser("heads", help="Show latest revisions")
    heads_parser.set_defaults(func=cmd_heads)

    # generate command
    generate_parser = subparsers.add_parser("generate", help="Generate new migration")
    generate_parser.add_argument("message", help="Migration message/description")
    generate_parser.set_defaults(func=cmd_generate)

    # check command
    check_parser = subparsers.add_parser("check", help="Check database connection")
    check_parser.set_defaults(func=cmd_check)

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize database with migrations")
    init_parser.set_defaults(func=cmd_init)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
