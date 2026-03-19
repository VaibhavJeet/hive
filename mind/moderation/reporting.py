"""
Flagging/Reporting System for Content Moderation.
Provides a ReportingService for submitting, reviewing, and managing user reports.
Includes auto-flagging for content with multiple reports.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4

from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import (
    async_session_factory,
    ContentReportDB,
    ModerationActionDB,
    PostDB,
    PostCommentDB,
    CommunityChatMessageDB,
    FlaggedContentDB
)


# ============================================================================
# ENUMS
# ============================================================================

class ReportType(str, Enum):
    """Types of content reports."""
    SPAM = "spam"
    HARASSMENT = "harassment"
    INAPPROPRIATE = "inappropriate"
    OTHER = "other"


class ReportStatus(str, Enum):
    """Status of a report."""
    PENDING = "pending"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


# ============================================================================
# DATACLASS
# ============================================================================

@dataclass
class Report:
    """A content report from a user."""
    id: UUID
    reporter_id: UUID
    target_type: str  # "post", "comment", "message", "profile"
    target_id: UUID
    report_type: ReportType
    reason: str
    status: ReportStatus
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewer_id: Optional[UUID] = None
    action_taken: Optional[str] = None
    notes: Optional[str] = None
    auto_flagged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "id": str(self.id),
            "reporter_id": str(self.reporter_id),
            "target_type": self.target_type,
            "target_id": str(self.target_id),
            "report_type": self.report_type.value,
            "reason": self.reason,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewer_id": str(self.reviewer_id) if self.reviewer_id else None,
            "action_taken": self.action_taken,
            "notes": self.notes,
            "auto_flagged": self.auto_flagged
        }


# ============================================================================
# REPORTING SERVICE
# ============================================================================

class ReportingService:
    """
    Service for managing content reports and flagging.

    Provides methods for:
    - Submitting reports
    - Retrieving pending reports
    - Reviewing and resolving reports
    - Generating report statistics
    - Auto-flagging content with multiple reports
    """

    # Configuration for auto-flagging
    AUTO_FLAG_THRESHOLD = 3  # Number of reports before auto-flagging
    HIGH_PRIORITY_TYPES = [ReportType.HARASSMENT, ReportType.INAPPROPRIATE]

    def __init__(self):
        """Initialize the reporting service."""
        pass

    async def submit_report(
        self,
        reporter_id: UUID,
        target_type: str,
        target_id: UUID,
        report_type: ReportType,
        reason: str
    ) -> Report:
        """
        Submit a new content report.

        Args:
            reporter_id: ID of the user making the report
            target_type: Type of content ("post", "comment", "message", "profile")
            target_id: ID of the content being reported
            report_type: Type of report (SPAM, HARASSMENT, INAPPROPRIATE, OTHER)
            reason: Detailed reason for the report

        Returns:
            The created Report object
        """
        async with async_session_factory() as session:
            # Check for existing report from same user for same content
            existing_stmt = select(ContentReportDB).where(
                and_(
                    ContentReportDB.reporter_id == reporter_id,
                    ContentReportDB.content_id == target_id,
                    ContentReportDB.status.in_([
                        ReportStatus.PENDING.value,
                        ReportStatus.REVIEWED.value
                    ])
                )
            )
            existing_result = await session.execute(existing_stmt)
            existing = existing_result.scalar_one_or_none()

            if existing:
                # Return existing report instead of creating duplicate
                return self._db_to_report(existing)

            # Create new report in database
            report_db = ContentReportDB(
                id=uuid4(),
                reporter_id=reporter_id,
                content_id=target_id,
                content_type=target_type,
                reason=report_type.value,  # Store report type in reason field
                description=reason,  # Store detailed reason in description
                status=ReportStatus.PENDING.value
            )

            session.add(report_db)
            await session.commit()
            await session.refresh(report_db)

            # Check if we need to auto-flag the content
            await self._check_auto_flag(session, target_id, target_type)

            return self._db_to_report(report_db)

    async def get_pending_reports(self, limit: int = 50) -> List[Report]:
        """
        Get pending reports for moderation review.

        Args:
            limit: Maximum number of reports to return

        Returns:
            List of pending Report objects, ordered by creation time (oldest first)
        """
        async with async_session_factory() as session:
            stmt = select(ContentReportDB).where(
                ContentReportDB.status == ReportStatus.PENDING.value
            ).order_by(
                ContentReportDB.created_at.asc()
            ).limit(limit)

            result = await session.execute(stmt)
            reports_db = result.scalars().all()

            return [self._db_to_report(r) for r in reports_db]

    async def review_report(
        self,
        report_id: UUID,
        reviewer_id: UUID,
        action: str,
        notes: Optional[str] = None
    ) -> Optional[Report]:
        """
        Review and resolve a report.

        Args:
            report_id: ID of the report to review
            reviewer_id: ID of the moderator reviewing
            action: Action taken ("no_action", "warn", "remove", "hide", "suspend", "ban")
            notes: Optional notes about the resolution

        Returns:
            The updated Report object or None if not found
        """
        async with async_session_factory() as session:
            stmt = select(ContentReportDB).where(ContentReportDB.id == report_id)
            result = await session.execute(stmt)
            report_db = result.scalar_one_or_none()

            if not report_db:
                return None

            # Update report status
            now = datetime.utcnow()
            report_db.status = ReportStatus.RESOLVED.value
            report_db.resolved_at = now
            report_db.resolved_by = reviewer_id
            report_db.resolution_action = action
            report_db.resolution_notes = notes

            # Log the moderation action
            action_log = ModerationActionDB(
                id=uuid4(),
                report_id=report_id,
                moderator_id=reviewer_id,
                action=action,
                content_id=report_db.content_id,
                content_type=report_db.content_type,
                notes=notes
            )
            session.add(action_log)

            # Apply the action to the content if needed
            await self._apply_action(session, report_db.content_id, report_db.content_type, action)

            await session.commit()
            await session.refresh(report_db)

            return self._db_to_report(report_db)

    async def get_report_stats(self) -> Dict[str, Any]:
        """
        Get statistics about reports.

        Returns:
            Dictionary with report statistics including:
            - counts by status
            - counts by type
            - auto-flagged content count
            - average resolution time
        """
        async with async_session_factory() as session:
            stats = {
                "by_status": {},
                "by_type": {},
                "total_reports": 0,
                "auto_flagged_count": 0,
                "avg_resolution_hours": 0.0
            }

            # Count by status
            for status in ReportStatus:
                count_stmt = select(func.count(ContentReportDB.id)).where(
                    ContentReportDB.status == status.value
                )
                result = await session.execute(count_stmt)
                count = result.scalar() or 0
                stats["by_status"][status.value] = count
                stats["total_reports"] += count

            # Count by report type (stored in reason field)
            for report_type in ReportType:
                count_stmt = select(func.count(ContentReportDB.id)).where(
                    ContentReportDB.reason == report_type.value
                )
                result = await session.execute(count_stmt)
                count = result.scalar() or 0
                stats["by_type"][report_type.value] = count

            # Count auto-flagged content
            flagged_stmt = select(func.count(FlaggedContentDB.id)).where(
                FlaggedContentDB.is_system_flagged == True
            )
            result = await session.execute(flagged_stmt)
            stats["auto_flagged_count"] = result.scalar() or 0

            # Calculate average resolution time for resolved reports
            resolved_stmt = select(ContentReportDB).where(
                and_(
                    ContentReportDB.status == ReportStatus.RESOLVED.value,
                    ContentReportDB.resolved_at.isnot(None)
                )
            )
            result = await session.execute(resolved_stmt)
            resolved_reports = result.scalars().all()

            if resolved_reports:
                total_hours = 0.0
                for r in resolved_reports:
                    if r.resolved_at and r.created_at:
                        delta = r.resolved_at - r.created_at
                        total_hours += delta.total_seconds() / 3600
                stats["avg_resolution_hours"] = round(total_hours / len(resolved_reports), 2)

            return stats

    async def get_report_by_id(self, report_id: UUID) -> Optional[Report]:
        """Get a specific report by ID."""
        async with async_session_factory() as session:
            stmt = select(ContentReportDB).where(ContentReportDB.id == report_id)
            result = await session.execute(stmt)
            report_db = result.scalar_one_or_none()

            if not report_db:
                return None

            return self._db_to_report(report_db)

    async def get_reports_for_content(self, target_id: UUID) -> List[Report]:
        """Get all reports for a specific piece of content."""
        async with async_session_factory() as session:
            stmt = select(ContentReportDB).where(
                ContentReportDB.content_id == target_id
            ).order_by(ContentReportDB.created_at.desc())

            result = await session.execute(stmt)
            reports_db = result.scalars().all()

            return [self._db_to_report(r) for r in reports_db]

    async def dismiss_report(
        self,
        report_id: UUID,
        reviewer_id: UUID,
        notes: Optional[str] = None
    ) -> Optional[Report]:
        """
        Dismiss a report as not requiring action.

        Args:
            report_id: ID of the report to dismiss
            reviewer_id: ID of the moderator dismissing
            notes: Optional notes about the dismissal

        Returns:
            The updated Report object or None if not found
        """
        async with async_session_factory() as session:
            stmt = select(ContentReportDB).where(ContentReportDB.id == report_id)
            result = await session.execute(stmt)
            report_db = result.scalar_one_or_none()

            if not report_db:
                return None

            report_db.status = ReportStatus.DISMISSED.value
            report_db.resolved_at = datetime.utcnow()
            report_db.resolved_by = reviewer_id
            report_db.resolution_action = "no_action"
            report_db.resolution_notes = notes

            await session.commit()
            await session.refresh(report_db)

            return self._db_to_report(report_db)

    # ========================================================================
    # AUTO-FLAGGING SYSTEM
    # ========================================================================

    async def _check_auto_flag(
        self,
        session: AsyncSession,
        content_id: UUID,
        content_type: str
    ) -> bool:
        """
        Check if content should be auto-flagged based on report count.

        Args:
            session: Database session
            content_id: ID of the content
            content_type: Type of content

        Returns:
            True if content was auto-flagged
        """
        # Count pending reports for this content
        count_stmt = select(func.count(ContentReportDB.id)).where(
            and_(
                ContentReportDB.content_id == content_id,
                ContentReportDB.status.in_([
                    ReportStatus.PENDING.value,
                    ReportStatus.REVIEWED.value
                ])
            )
        )
        result = await session.execute(count_stmt)
        report_count = result.scalar() or 0

        # Check if threshold is met
        if report_count >= self.AUTO_FLAG_THRESHOLD:
            # Check if already flagged
            existing_flag_stmt = select(FlaggedContentDB).where(
                and_(
                    FlaggedContentDB.content_id == content_id,
                    FlaggedContentDB.is_system_flagged == True
                )
            )
            existing_flag_result = await session.execute(existing_flag_stmt)
            existing_flag = existing_flag_result.scalar_one_or_none()

            if not existing_flag:
                # Get content text for flagging record
                content_text = await self._get_content_text(session, content_id, content_type)

                # Create flagged content record
                flagged = FlaggedContentDB(
                    id=uuid4(),
                    content_type=content_type,
                    content_id=content_id,
                    content_text=content_text or "[Content not found]",
                    flag_reason=f"Auto-flagged: {report_count} reports received",
                    flagged_by=None,
                    is_system_flagged=True,
                    status="pending"
                )
                session.add(flagged)

                # Also flag the content directly if it's a post
                if content_type == "post":
                    post_stmt = select(PostDB).where(PostDB.id == content_id)
                    post_result = await session.execute(post_stmt)
                    post = post_result.scalar_one_or_none()
                    if post:
                        post.is_flagged = True
                        post.flag_reason = f"Auto-flagged: {report_count} reports"
                        post.moderation_status = "pending"

                await session.commit()
                return True

        return False

    async def _get_content_text(
        self,
        session: AsyncSession,
        content_id: UUID,
        content_type: str
    ) -> Optional[str]:
        """Get the text content for a piece of content."""
        if content_type == "post":
            stmt = select(PostDB).where(PostDB.id == content_id)
            result = await session.execute(stmt)
            content = result.scalar_one_or_none()
            return content.content if content else None
        elif content_type == "comment":
            stmt = select(PostCommentDB).where(PostCommentDB.id == content_id)
            result = await session.execute(stmt)
            content = result.scalar_one_or_none()
            return content.content if content else None
        elif content_type == "message":
            stmt = select(CommunityChatMessageDB).where(CommunityChatMessageDB.id == content_id)
            result = await session.execute(stmt)
            content = result.scalar_one_or_none()
            return content.content if content else None
        return None

    async def _apply_action(
        self,
        session: AsyncSession,
        content_id: UUID,
        content_type: str,
        action: str
    ):
        """Apply a moderation action to content."""
        if action == "no_action" or action == "warn":
            return

        if content_type == "post":
            stmt = select(PostDB).where(PostDB.id == content_id)
            result = await session.execute(stmt)
            post = result.scalar_one_or_none()
            if post:
                if action in ["remove", "ban"]:
                    post.is_deleted = True
                    post.is_flagged = True
                    post.flag_reason = f"Removed by moderator: {action}"
                    post.moderation_status = "rejected"
                elif action == "hide":
                    post.is_flagged = True
                    post.flag_reason = "Hidden by moderator for review"
                    post.moderation_status = "pending"

        elif content_type == "comment":
            stmt = select(PostCommentDB).where(PostCommentDB.id == content_id)
            result = await session.execute(stmt)
            comment = result.scalar_one_or_none()
            if comment and action in ["remove", "ban", "hide"]:
                comment.is_deleted = True

        elif content_type == "message":
            stmt = select(CommunityChatMessageDB).where(CommunityChatMessageDB.id == content_id)
            result = await session.execute(stmt)
            message = result.scalar_one_or_none()
            if message and action in ["remove", "ban", "hide"]:
                message.is_deleted = True

    def _db_to_report(self, db_report: ContentReportDB) -> Report:
        """Convert database model to Report dataclass."""
        # Parse report type from reason field
        try:
            report_type = ReportType(db_report.reason)
        except ValueError:
            # Map old reason values to new report types
            reason_mapping = {
                "spam": ReportType.SPAM,
                "harassment": ReportType.HARASSMENT,
                "hate_speech": ReportType.HARASSMENT,
                "violence": ReportType.INAPPROPRIATE,
                "nudity": ReportType.INAPPROPRIATE,
                "misinformation": ReportType.OTHER,
                "self_harm": ReportType.INAPPROPRIATE,
                "impersonation": ReportType.OTHER,
                "copyright": ReportType.OTHER,
                "other": ReportType.OTHER
            }
            report_type = reason_mapping.get(db_report.reason, ReportType.OTHER)

        # Parse status
        try:
            status = ReportStatus(db_report.status)
        except ValueError:
            # Map old status values
            status_mapping = {
                "pending": ReportStatus.PENDING,
                "under_review": ReportStatus.REVIEWED,
                "resolved": ReportStatus.RESOLVED,
                "dismissed": ReportStatus.DISMISSED,
                "escalated": ReportStatus.REVIEWED
            }
            status = status_mapping.get(db_report.status, ReportStatus.PENDING)

        return Report(
            id=db_report.id,
            reporter_id=db_report.reporter_id,
            target_type=db_report.content_type,
            target_id=db_report.content_id,
            report_type=report_type,
            reason=db_report.description or db_report.reason,
            status=status,
            created_at=db_report.created_at,
            reviewed_at=db_report.resolved_at,
            reviewer_id=db_report.resolved_by,
            action_taken=db_report.resolution_action,
            notes=db_report.resolution_notes
        )


# ============================================================================
# MODULE-LEVEL INSTANCE
# ============================================================================

# Singleton instance for convenience
_reporting_service: Optional[ReportingService] = None


def get_reporting_service() -> ReportingService:
    """Get the global ReportingService instance."""
    global _reporting_service
    if _reporting_service is None:
        _reporting_service = ReportingService()
    return _reporting_service
