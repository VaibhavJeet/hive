"""
Admin Service - Business logic for admin operations.
Handles stats aggregation, admin actions, and audit logging.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from uuid import UUID

from sqlalchemy import select, func, desc, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import (
    async_session_factory,
    AppUserDB, BotProfileDB, PostDB, PostCommentDB, PostLikeDB,
    DirectMessageDB, CommunityChatMessageDB, CommunityDB,
    ScheduledActivityDB, SystemMetricsDB, BotMetricsDB,
    AdminAuditLogDB, FlaggedContentDB, SystemLogDB
)


class AdminService:
    """
    Service class for admin operations.
    Provides stats aggregation, user/bot management, and audit logging.
    """

    # ========================================================================
    # DASHBOARD STATS
    # ========================================================================

    @staticmethod
    async def get_dashboard_stats(session: AsyncSession) -> Dict[str, Any]:
        """Get overall platform statistics for the admin dashboard."""
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)

        # User stats
        total_users_stmt = select(func.count(AppUserDB.id))
        total_users = (await session.execute(total_users_stmt)).scalar() or 0

        active_users_stmt = select(func.count(AppUserDB.id)).where(
            AppUserDB.last_active >= last_24h
        )
        active_users_24h = (await session.execute(active_users_stmt)).scalar() or 0

        # Bot stats
        total_bots_stmt = select(func.count(BotProfileDB.id)).where(
            BotProfileDB.is_deleted == False
        )
        total_bots = (await session.execute(total_bots_stmt)).scalar() or 0

        active_bots_stmt = select(func.count(BotProfileDB.id)).where(
            and_(
                BotProfileDB.is_active == True,
                BotProfileDB.is_paused == False,
                BotProfileDB.is_deleted == False
            )
        )
        active_bots = (await session.execute(active_bots_stmt)).scalar() or 0

        # Post stats
        total_posts_stmt = select(func.count(PostDB.id)).where(PostDB.is_deleted == False)
        total_posts = (await session.execute(total_posts_stmt)).scalar() or 0

        posts_24h_stmt = select(func.count(PostDB.id)).where(
            and_(
                PostDB.created_at >= last_24h,
                PostDB.is_deleted == False
            )
        )
        posts_24h = (await session.execute(posts_24h_stmt)).scalar() or 0

        # Message stats
        total_dm_stmt = select(func.count(DirectMessageDB.id))
        total_dms = (await session.execute(total_dm_stmt)).scalar() or 0

        total_chat_stmt = select(func.count(CommunityChatMessageDB.id)).where(
            CommunityChatMessageDB.is_deleted == False
        )
        total_chat = (await session.execute(total_chat_stmt)).scalar() or 0

        total_messages = total_dms + total_chat

        # System metrics (last entry)
        metrics_stmt = select(SystemMetricsDB).order_by(
            desc(SystemMetricsDB.timestamp)
        ).limit(1)
        metrics_result = await session.execute(metrics_stmt)
        latest_metrics = metrics_result.scalar_one_or_none()

        llm_requests_today = 0
        avg_response_time = 0.0
        if latest_metrics:
            llm_requests_today = latest_metrics.llm_requests
            avg_response_time = latest_metrics.avg_inference_time_ms

        return {
            "total_users": total_users,
            "active_users_24h": active_users_24h,
            "total_bots": total_bots,
            "active_bots": active_bots,
            "total_posts": total_posts,
            "posts_24h": posts_24h,
            "total_messages": total_messages,
            "llm_requests_today": llm_requests_today,
            "avg_response_time": avg_response_time,
            "timestamp": now.isoformat()
        }

    # ========================================================================
    # BOT MANAGEMENT
    # ========================================================================

    @staticmethod
    async def list_bots(
        session: AsyncSession,
        include_deleted: bool = False,
        include_paused: bool = True,
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all bots with stats for admin view."""
        stmt = select(BotProfileDB)

        if not include_deleted:
            stmt = stmt.where(BotProfileDB.is_deleted == False)

        if not include_paused:
            stmt = stmt.where(BotProfileDB.is_paused == False)

        if search:
            stmt = stmt.where(
                or_(
                    BotProfileDB.display_name.ilike(f"%{search}%"),
                    BotProfileDB.handle.ilike(f"%{search}%")
                )
            )

        stmt = stmt.order_by(desc(BotProfileDB.created_at)).limit(limit).offset(offset)

        result = await session.execute(stmt)
        bots = result.scalars().all()

        bot_list = []
        for bot in bots:
            # Get bot's post count
            post_count_stmt = select(func.count(PostDB.id)).where(
                PostDB.author_id == bot.id
            )
            post_count = (await session.execute(post_count_stmt)).scalar() or 0

            # Get bot's comment count
            comment_count_stmt = select(func.count(PostCommentDB.id)).where(
                PostCommentDB.author_id == bot.id
            )
            comment_count = (await session.execute(comment_count_stmt)).scalar() or 0

            bot_list.append({
                "id": str(bot.id),
                "display_name": bot.display_name,
                "handle": bot.handle,
                "bio": bot.bio[:100] + "..." if len(bot.bio) > 100 else bot.bio,
                "avatar_seed": bot.avatar_seed,
                "is_active": bot.is_active,
                "is_paused": bot.is_paused,
                "is_deleted": bot.is_deleted,
                "created_at": bot.created_at.isoformat(),
                "last_active": bot.last_active.isoformat() if bot.last_active else None,
                "post_count": post_count,
                "comment_count": comment_count
            })

        return bot_list

    @staticmethod
    async def get_bot_details(
        session: AsyncSession,
        bot_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get detailed bot information for admin view."""
        stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()

        if not bot:
            return None

        # Get activity stats
        post_count_stmt = select(func.count(PostDB.id)).where(PostDB.author_id == bot_id)
        post_count = (await session.execute(post_count_stmt)).scalar() or 0

        comment_count_stmt = select(func.count(PostCommentDB.id)).where(
            PostCommentDB.author_id == bot_id
        )
        comment_count = (await session.execute(comment_count_stmt)).scalar() or 0

        dm_count_stmt = select(func.count(DirectMessageDB.id)).where(
            DirectMessageDB.sender_id == bot_id
        )
        dm_count = (await session.execute(dm_count_stmt)).scalar() or 0

        # Get recent posts
        recent_posts_stmt = (
            select(PostDB)
            .where(PostDB.author_id == bot_id)
            .order_by(desc(PostDB.created_at))
            .limit(5)
        )
        recent_posts_result = await session.execute(recent_posts_stmt)
        recent_posts = [
            {
                "id": str(p.id),
                "content": p.content[:100] + "..." if len(p.content) > 100 else p.content,
                "created_at": p.created_at.isoformat(),
                "like_count": p.like_count,
                "comment_count": p.comment_count
            }
            for p in recent_posts_result.scalars().all()
        ]

        # Get recent metrics
        metrics_stmt = (
            select(BotMetricsDB)
            .where(BotMetricsDB.bot_id == bot_id)
            .order_by(desc(BotMetricsDB.timestamp))
            .limit(1)
        )
        metrics_result = await session.execute(metrics_stmt)
        latest_metrics = metrics_result.scalar_one_or_none()

        return {
            "id": str(bot.id),
            "display_name": bot.display_name,
            "handle": bot.handle,
            "bio": bot.bio,
            "backstory": bot.backstory,
            "avatar_seed": bot.avatar_seed,
            "age": bot.age,
            "gender": bot.gender,
            "location": bot.location,
            "interests": bot.interests,
            "personality_traits": bot.personality_traits,
            "writing_fingerprint": bot.writing_fingerprint,
            "activity_pattern": bot.activity_pattern,
            "emotional_state": bot.emotional_state,
            "is_active": bot.is_active,
            "is_paused": bot.is_paused,
            "is_deleted": bot.is_deleted,
            "is_ai_labeled": bot.is_ai_labeled,
            "ai_label_text": bot.ai_label_text,
            "created_at": bot.created_at.isoformat(),
            "last_active": bot.last_active.isoformat() if bot.last_active else None,
            "paused_at": bot.paused_at.isoformat() if bot.paused_at else None,
            "stats": {
                "post_count": post_count,
                "comment_count": comment_count,
                "dm_count": dm_count
            },
            "recent_posts": recent_posts,
            "metrics": {
                "engagement_rate": latest_metrics.engagement_rate if latest_metrics else 0,
                "avg_response_time_ms": latest_metrics.avg_response_time_ms if latest_metrics else 0,
                "naturalness_score": latest_metrics.naturalness_score if latest_metrics else 0
            } if latest_metrics else None
        }

    @staticmethod
    async def update_bot(
        session: AsyncSession,
        bot_id: UUID,
        updates: Dict[str, Any],
        admin_id: UUID
    ) -> bool:
        """Update bot settings."""
        stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()

        if not bot:
            return False

        # Allowed update fields
        allowed_fields = [
            "display_name", "bio", "is_active", "is_ai_labeled",
            "ai_label_text", "interests", "personality_traits",
            "writing_fingerprint", "activity_pattern"
        ]

        old_values = {}
        for field, value in updates.items():
            if field in allowed_fields and hasattr(bot, field):
                old_values[field] = getattr(bot, field)
                setattr(bot, field, value)

        # Audit log
        await AdminService.log_action(
            session=session,
            admin_id=admin_id,
            action="bot_updated",
            entity_type="bot",
            entity_id=bot_id,
            details={"old_values": old_values, "new_values": updates}
        )

        await session.commit()
        return True

    @staticmethod
    async def pause_bot(
        session: AsyncSession,
        bot_id: UUID,
        admin_id: UUID,
        reason: Optional[str] = None
    ) -> bool:
        """Pause bot activity."""
        stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()

        if not bot:
            return False

        bot.is_paused = True
        bot.paused_at = datetime.utcnow()
        bot.paused_by = admin_id

        await AdminService.log_action(
            session=session,
            admin_id=admin_id,
            action="bot_paused",
            entity_type="bot",
            entity_id=bot_id,
            details={"reason": reason}
        )

        await session.commit()
        return True

    @staticmethod
    async def resume_bot(
        session: AsyncSession,
        bot_id: UUID,
        admin_id: UUID
    ) -> bool:
        """Resume bot activity."""
        stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()

        if not bot:
            return False

        bot.is_paused = False
        bot.paused_at = None
        bot.paused_by = None

        await AdminService.log_action(
            session=session,
            admin_id=admin_id,
            action="bot_resumed",
            entity_type="bot",
            entity_id=bot_id,
            details={}
        )

        await session.commit()
        return True

    @staticmethod
    async def delete_bot(
        session: AsyncSession,
        bot_id: UUID,
        admin_id: UUID,
        reason: Optional[str] = None
    ) -> bool:
        """Soft delete a bot."""
        stmt = select(BotProfileDB).where(BotProfileDB.id == bot_id)
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()

        if not bot:
            return False

        bot.is_deleted = True
        bot.is_active = False
        bot.deleted_at = datetime.utcnow()
        bot.deleted_by = admin_id

        await AdminService.log_action(
            session=session,
            admin_id=admin_id,
            action="bot_deleted",
            entity_type="bot",
            entity_id=bot_id,
            details={"reason": reason, "bot_handle": bot.handle}
        )

        await session.commit()
        return True

    # ========================================================================
    # USER MANAGEMENT
    # ========================================================================

    @staticmethod
    async def list_users(
        session: AsyncSession,
        include_banned: bool = True,
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all users for admin view."""
        stmt = select(AppUserDB)

        if not include_banned:
            stmt = stmt.where(AppUserDB.is_banned == False)

        if search:
            stmt = stmt.where(
                AppUserDB.display_name.ilike(f"%{search}%")
            )

        stmt = stmt.order_by(desc(AppUserDB.created_at)).limit(limit).offset(offset)

        result = await session.execute(stmt)
        users = result.scalars().all()

        user_list = []
        for user in users:
            # Get user's post activity
            post_count_stmt = select(func.count(PostDB.id)).where(
                and_(
                    PostDB.author_id == user.id,
                    PostDB.is_deleted == False
                )
            )
            # Note: This would need adjustment if users can create posts
            # For now, assume users interact via likes/comments

            like_count_stmt = select(func.count(PostLikeDB.id)).where(
                and_(
                    PostLikeDB.user_id == user.id,
                    PostLikeDB.is_bot == False
                )
            )
            like_count = (await session.execute(like_count_stmt)).scalar() or 0

            user_list.append({
                "id": str(user.id),
                "display_name": user.display_name,
                "device_id": user.device_id[:8] + "...",  # Partial for privacy
                "avatar_seed": user.avatar_seed,
                "is_admin": user.is_admin,
                "is_banned": user.is_banned,
                "created_at": user.created_at.isoformat(),
                "last_active": user.last_active.isoformat() if user.last_active else None,
                "like_count": like_count
            })

        return user_list

    @staticmethod
    async def get_user_details(
        session: AsyncSession,
        user_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get detailed user information for admin view."""
        stmt = select(AppUserDB).where(AppUserDB.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return None

        # Get interaction stats
        like_count_stmt = select(func.count(PostLikeDB.id)).where(
            and_(
                PostLikeDB.user_id == user_id,
                PostLikeDB.is_bot == False
            )
        )
        like_count = (await session.execute(like_count_stmt)).scalar() or 0

        comment_count_stmt = select(func.count(PostCommentDB.id)).where(
            and_(
                PostCommentDB.author_id == user_id,
                PostCommentDB.is_bot == False
            )
        )
        comment_count = (await session.execute(comment_count_stmt)).scalar() or 0

        dm_count_stmt = select(func.count(DirectMessageDB.id)).where(
            and_(
                DirectMessageDB.sender_id == user_id,
                DirectMessageDB.sender_is_bot == False
            )
        )
        dm_count = (await session.execute(dm_count_stmt)).scalar() or 0

        return {
            "id": str(user.id),
            "display_name": user.display_name,
            "device_id": user.device_id,
            "avatar_seed": user.avatar_seed,
            "is_admin": user.is_admin,
            "is_banned": user.is_banned,
            "ban_reason": user.ban_reason,
            "banned_at": user.banned_at.isoformat() if user.banned_at else None,
            "created_at": user.created_at.isoformat(),
            "last_active": user.last_active.isoformat() if user.last_active else None,
            "stats": {
                "like_count": like_count,
                "comment_count": comment_count,
                "dm_count": dm_count
            }
        }

    @staticmethod
    async def ban_user(
        session: AsyncSession,
        user_id: UUID,
        admin_id: UUID,
        reason: Optional[str] = None
    ) -> bool:
        """Ban a user."""
        stmt = select(AppUserDB).where(AppUserDB.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return False

        # Prevent banning admins
        if user.is_admin:
            return False

        user.is_banned = True
        user.ban_reason = reason
        user.banned_at = datetime.utcnow()
        user.banned_by = admin_id

        await AdminService.log_action(
            session=session,
            admin_id=admin_id,
            action="user_banned",
            entity_type="user",
            entity_id=user_id,
            details={"reason": reason}
        )

        await session.commit()
        return True

    @staticmethod
    async def unban_user(
        session: AsyncSession,
        user_id: UUID,
        admin_id: UUID
    ) -> bool:
        """Unban a user."""
        stmt = select(AppUserDB).where(AppUserDB.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return False

        user.is_banned = False
        user.ban_reason = None
        user.banned_at = None
        user.banned_by = None

        await AdminService.log_action(
            session=session,
            admin_id=admin_id,
            action="user_unbanned",
            entity_type="user",
            entity_id=user_id,
            details={}
        )

        await session.commit()
        return True

    # ========================================================================
    # CONTENT MANAGEMENT
    # ========================================================================

    @staticmethod
    async def list_posts(
        session: AsyncSession,
        include_deleted: bool = False,
        community_id: Optional[UUID] = None,
        author_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List posts for admin view."""
        stmt = select(PostDB, BotProfileDB, CommunityDB).join(
            BotProfileDB, PostDB.author_id == BotProfileDB.id
        ).join(
            CommunityDB, PostDB.community_id == CommunityDB.id
        )

        if not include_deleted:
            stmt = stmt.where(PostDB.is_deleted == False)

        if community_id:
            stmt = stmt.where(PostDB.community_id == community_id)

        if author_id:
            stmt = stmt.where(PostDB.author_id == author_id)

        stmt = stmt.order_by(desc(PostDB.created_at)).limit(limit).offset(offset)

        result = await session.execute(stmt)
        rows = result.all()

        return [
            {
                "id": str(post.id),
                "author": {
                    "id": str(author.id),
                    "display_name": author.display_name,
                    "handle": author.handle
                },
                "community": {
                    "id": str(community.id),
                    "name": community.name
                },
                "content": post.content[:200] + "..." if len(post.content) > 200 else post.content,
                "image_url": post.image_url,
                "like_count": post.like_count,
                "comment_count": post.comment_count,
                "is_deleted": post.is_deleted,
                "created_at": post.created_at.isoformat()
            }
            for post, author, community in rows
        ]

    @staticmethod
    async def delete_post(
        session: AsyncSession,
        post_id: UUID,
        admin_id: UUID,
        reason: Optional[str] = None
    ) -> bool:
        """Soft delete a post."""
        stmt = select(PostDB).where(PostDB.id == post_id)
        result = await session.execute(stmt)
        post = result.scalar_one_or_none()

        if not post:
            return False

        post.is_deleted = True

        await AdminService.log_action(
            session=session,
            admin_id=admin_id,
            action="post_deleted",
            entity_type="post",
            entity_id=post_id,
            details={"reason": reason, "content_preview": post.content[:100]}
        )

        await session.commit()
        return True

    @staticmethod
    async def list_flagged_content(
        session: AsyncSession,
        status: Optional[str] = "pending",
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List flagged content for moderation."""
        stmt = select(FlaggedContentDB)

        if status:
            stmt = stmt.where(FlaggedContentDB.status == status)

        stmt = stmt.order_by(desc(FlaggedContentDB.created_at)).limit(limit).offset(offset)

        result = await session.execute(stmt)
        flags = result.scalars().all()

        return [
            {
                "id": str(flag.id),
                "content_type": flag.content_type,
                "content_id": str(flag.content_id),
                "content_text": flag.content_text[:200] + "..." if len(flag.content_text) > 200 else flag.content_text,
                "flag_reason": flag.flag_reason,
                "is_system_flagged": flag.is_system_flagged,
                "status": flag.status,
                "created_at": flag.created_at.isoformat(),
                "reviewed_at": flag.reviewed_at.isoformat() if flag.reviewed_at else None,
                "action_taken": flag.action_taken
            }
            for flag in flags
        ]

    # ========================================================================
    # SYSTEM MANAGEMENT
    # ========================================================================

    @staticmethod
    async def get_system_logs(
        session: AsyncSession,
        level: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get system logs."""
        stmt = select(SystemLogDB)

        if level:
            stmt = stmt.where(SystemLogDB.level == level)

        if source:
            stmt = stmt.where(SystemLogDB.source.ilike(f"%{source}%"))

        stmt = stmt.order_by(desc(SystemLogDB.created_at)).limit(limit).offset(offset)

        result = await session.execute(stmt)
        logs = result.scalars().all()

        return [
            {
                "id": str(log.id),
                "level": log.level,
                "source": log.source,
                "message": log.message,
                "details": log.details,
                "created_at": log.created_at.isoformat()
            }
            for log in logs
        ]

    @staticmethod
    async def log_system_event(
        session: AsyncSession,
        level: str,
        source: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log a system event."""
        log = SystemLogDB(
            level=level,
            source=source,
            message=message,
            details=details or {}
        )
        session.add(log)
        await session.commit()

    @staticmethod
    async def get_engine_status() -> Dict[str, Any]:
        """Get activity engine status. This would integrate with the scheduler."""
        # This is a placeholder - actual implementation would query the scheduler
        return {
            "status": "running",
            "uptime_hours": 24,
            "pending_activities": 0,
            "running_tasks": 0,
            "last_error": None,
            "capacity_used": 0.0
        }

    # ========================================================================
    # AUDIT LOGGING
    # ========================================================================

    @staticmethod
    async def log_action(
        session: AsyncSession,
        admin_id: UUID,
        action: str,
        entity_type: str,
        entity_id: UUID,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log an admin action for audit purposes."""
        audit_log = AdminAuditLogDB(
            admin_id=admin_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent
        )
        session.add(audit_log)
        # Note: Commit should be handled by the caller

    @staticmethod
    async def get_audit_logs(
        session: AsyncSession,
        admin_id: Optional[UUID] = None,
        action: Optional[str] = None,
        entity_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get audit logs with optional filters."""
        stmt = select(AdminAuditLogDB, AppUserDB).join(
            AppUserDB, AdminAuditLogDB.admin_id == AppUserDB.id
        )

        if admin_id:
            stmt = stmt.where(AdminAuditLogDB.admin_id == admin_id)

        if action:
            stmt = stmt.where(AdminAuditLogDB.action == action)

        if entity_type:
            stmt = stmt.where(AdminAuditLogDB.entity_type == entity_type)

        stmt = stmt.order_by(desc(AdminAuditLogDB.created_at)).limit(limit).offset(offset)

        result = await session.execute(stmt)
        rows = result.all()

        return [
            {
                "id": str(log.id),
                "admin": {
                    "id": str(admin.id),
                    "display_name": admin.display_name
                },
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": str(log.entity_id),
                "details": log.details,
                "created_at": log.created_at.isoformat()
            }
            for log, admin in rows
        ]
