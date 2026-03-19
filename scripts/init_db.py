"""Initialize database tables."""
import asyncio
import sys
sys.path.insert(0, ".")

from mind.core.database import init_database

async def main():
    print("Initializing database tables...")
    await init_database()
    print("Database tables created successfully!")

if __name__ == "__main__":
    asyncio.run(main())
