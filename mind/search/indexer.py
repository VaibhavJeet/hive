"""
Search indexer for managing full-text search indexes.
Uses PostgreSQL's tsvector for efficient text search.
"""

from datetime import datetime
from typing import Optional, List, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import (
    async_session_factory,
    PostDB,
    BotProfileDB,
    AppUserDB,
)


EntityType = Literal["post", "bot", "user"]


class SearchIndexer:
    """
    Manages full-text search indexes for posts, bots, and users.

    Uses PostgreSQL's tsvector columns with GIN indexes for fast text search.
    The search_vector columns are automatically updated via database triggers,
    but this class provides methods for manual indexing when needed.
    """

    def __init__(self, session: Optional[AsyncSession] = None):
        """Initialize indexer with optional session."""
        self._session = session

    async def _get_session(self) -> AsyncSession:
        """Get database session."""
        if self._session:
            return self._session
        return async_session_factory()

    async def index_post(self, post_id: UUID) -> bool:
        """
        Index or re-index a single post.

        Updates the search_vector column for the specified post.
        Normally handled by database triggers, but useful for manual updates.

        Args:
            post_id: UUID of the post to index

        Returns:
            True if successfully indexed, False otherwise
        """
        async with async_session_factory() as session:
            try:
                update_sql = text("""
                    UPDATE posts
                    SET search_vector = to_tsvector('english', content)
                    WHERE id = :post_id
                """)

                await session.execute(update_sql, {"post_id": str(post_id)})
                await session.commit()
                return True
            except Exception as e:
                await session.rollback()
                print(f"Error indexing post {post_id}: {e}")
                return False

    async def index_bot(self, bot_id: UUID) -> bool:
        """
        Index or re-index a single bot profile.

        Updates the search_vector column combining name, handle, bio, and interests.

        Args:
            bot_id: UUID of the bot to index

        Returns:
            True if successfully indexed, False otherwise
        """
        async with async_session_factory() as session:
            try:
                update_sql = text("""
                    UPDATE bot_profiles
                    SET search_vector =
                        setweight(to_tsvector('english', display_name), 'A') ||
                        setweight(to_tsvector('english', handle), 'A') ||
                        setweight(to_tsvector('english', bio), 'B') ||
                        setweight(to_tsvector('english', COALESCE(array_to_string(interests::text[], ' '), '')), 'C')
                    WHERE id = :bot_id
                """)

                await session.execute(update_sql, {"bot_id": str(bot_id)})
                await session.commit()
                return True
            except Exception as e:
                await session.rollback()
                print(f"Error indexing bot {bot_id}: {e}")
                return False

    async def index_user(self, user_id: UUID) -> bool:
        """
        Index or re-index a single user.

        For users, we use direct tsvector on display_name since there's no
        dedicated search_vector column (users are simpler entities).

        Args:
            user_id: UUID of the user to index

        Returns:
            True if user exists, False otherwise
        """
        async with async_session_factory() as session:
            try:
                # Check user exists - users don't have a search_vector column
                # but we can verify they're searchable
                check_sql = text("""
                    SELECT id FROM app_users WHERE id = :user_id
                """)
                result = await session.execute(check_sql, {"user_id": str(user_id)})
                return result.scalar_one_or_none() is not None
            except Exception as e:
                print(f"Error checking user {user_id}: {e}")
                return False

    async def remove_from_index(self, entity_type: EntityType, entity_id: UUID) -> bool:
        """
        Remove an entity from the search index.

        Sets the search_vector to NULL for the specified entity.

        Args:
            entity_type: Type of entity ("post", "bot", or "user")
            entity_id: UUID of the entity to remove

        Returns:
            True if successfully removed, False otherwise
        """
        table_map = {
            "post": "posts",
            "bot": "bot_profiles",
            "user": "app_users",  # Users don't have search_vector, will no-op
        }

        table = table_map.get(entity_type)
        if not table:
            return False

        # Users don't have search_vector column
        if entity_type == "user":
            return True

        async with async_session_factory() as session:
            try:
                update_sql = text(f"""
                    UPDATE {table}
                    SET search_vector = NULL
                    WHERE id = :entity_id
                """)

                await session.execute(update_sql, {"entity_id": str(entity_id)})
                await session.commit()
                return True
            except Exception as e:
                await session.rollback()
                print(f"Error removing {entity_type} {entity_id} from index: {e}")
                return False

    async def rebuild_index(self, entity_type: Optional[EntityType] = None) -> dict:
        """
        Rebuild the full-text search index.

        Re-indexes all entities of the specified type, or all types if not specified.
        This is useful after bulk data imports or schema changes.

        Args:
            entity_type: Optional type to rebuild ("post", "bot", "user", or None for all)

        Returns:
            Dict with counts of indexed entities per type
        """
        results = {}

        async with async_session_factory() as session:
            try:
                # Rebuild posts index
                if entity_type is None or entity_type == "post":
                    post_sql = text("""
                        UPDATE posts
                        SET search_vector = to_tsvector('english', content)
                        WHERE is_deleted = false
                    """)
                    result = await session.execute(post_sql)
                    results["posts"] = result.rowcount

                # Rebuild bots index
                if entity_type is None or entity_type == "bot":
                    bot_sql = text("""
                        UPDATE bot_profiles
                        SET search_vector =
                            setweight(to_tsvector('english', display_name), 'A') ||
                            setweight(to_tsvector('english', handle), 'A') ||
                            setweight(to_tsvector('english', bio), 'B') ||
                            setweight(to_tsvector('english', COALESCE(array_to_string(interests::text[], ' '), '')), 'C')
                        WHERE is_active = true
                    """)
                    result = await session.execute(bot_sql)
                    results["bots"] = result.rowcount

                # Users don't need indexing (no search_vector column)
                if entity_type is None or entity_type == "user":
                    user_count_sql = text("SELECT COUNT(*) FROM app_users")
                    result = await session.execute(user_count_sql)
                    results["users"] = result.scalar()

                await session.commit()
                return results

            except Exception as e:
                await session.rollback()
                print(f"Error rebuilding index: {e}")
                return {"error": str(e)}

    async def get_index_stats(self) -> dict:
        """
        Get statistics about the search indexes.

        Returns:
            Dict with index statistics including counts and sizes
        """
        async with async_session_factory() as session:
            try:
                stats = {}

                # Posts with search vectors
                posts_sql = text("""
                    SELECT
                        COUNT(*) as total,
                        COUNT(search_vector) as indexed
                    FROM posts
                    WHERE is_deleted = false
                """)
                result = await session.execute(posts_sql)
                row = result.fetchone()
                stats["posts"] = {
                    "total": row.total if row else 0,
                    "indexed": row.indexed if row else 0,
                }

                # Bots with search vectors
                bots_sql = text("""
                    SELECT
                        COUNT(*) as total,
                        COUNT(search_vector) as indexed
                    FROM bot_profiles
                    WHERE is_active = true
                """)
                result = await session.execute(bots_sql)
                row = result.fetchone()
                stats["bots"] = {
                    "total": row.total if row else 0,
                    "indexed": row.indexed if row else 0,
                }

                # Users (no search_vector, just count)
                users_sql = text("SELECT COUNT(*) as total FROM app_users")
                result = await session.execute(users_sql)
                row = result.fetchone()
                stats["users"] = {
                    "total": row.total if row else 0,
                    "indexed": row.total if row else 0,  # All users are "indexed" via display_name
                }

                # Index sizes (if available)
                try:
                    index_sizes_sql = text("""
                        SELECT
                            indexname,
                            pg_size_pretty(pg_relation_size(indexname::regclass)) as size
                        FROM pg_indexes
                        WHERE indexname LIKE '%search%' OR indexname LIKE '%gin%'
                    """)
                    result = await session.execute(index_sizes_sql)
                    rows = result.fetchall()
                    stats["index_sizes"] = {row.indexname: row.size for row in rows}
                except Exception:
                    stats["index_sizes"] = {}

                return stats

            except Exception as e:
                print(f"Error getting index stats: {e}")
                return {"error": str(e)}
