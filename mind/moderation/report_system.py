"""
Content Report System for Moderation.
Allows users to report content and moderators to review and resolve reports.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from mind.core.database import async_session_factory, ContentReportDB, ModerationActionDB


class ReportReason(Enum):
    """Reasons for reporting content."""
    SPAM = "spam"
    HARASSMENT = "harassment"
    HATE_SPEECH = "hate_speech"
    VIOLENCE = "violence"
    NUDITY = "nudity"
    MISINFORMATION = "misinformation"
    SELF_HARM = "self_harm"
    IMPERSONATION = "impersonation"
    COPYRIGHT = "copyright"
    OTHER = "other"


class ReportStatus(Enum):
    """Status of a content report."""
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
    ESCALATED = "escalated"


class ModerationAction(Enum):
    """Actions that can be taken on reported content."""
    NO_ACTION = "no_action"
    WARN_USER = "warn_user"
    REMOVE_CONTENT = "remove_content"
    HIDE_CONTENT = "hide_content"
    SUSPEND_USER = "suspend_user"
    BAN_USER = "ban_user"


@dataclass
class ContentReport:
    """A content report from a user."""
    id: UUID
    reporter_id: UUID
    content_id: UUID
    content_type: str  # "post", "comment", "message", "profile"
    reason: ReportReason
    description: Optional[str]
    status: ReportStatus
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[UUID] = None
    resolution_action: Optional[ModerationAction] = None
    resolution_notes: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "reporter_id": str(self.reporter_id),
            "content_id": str(self.content_id),
            "content_type": self.content_type,
            "reason": self.reason.value,
            "description": self.description,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": str(self.resolved_by) if self.resolved_by else None,
            "resolution_action": self.resolution_action.value if self.resolution_action else None,
            "resolution_notes": self.resolution_notes
        }


async def create_report(
    reporter_id: UUID,
    content_id: UUID,
    content_type: str,
    reason: ReportReason,
    description: Optional[str] = None
) -> ContentReport:
    """
    Create a new content report.

    Args:
        reporter_id: ID of the user making the report
        content_id: ID of the content being reported
        content_type: Type of content ("post", "comment", "message", "profile")
        reason: Reason for the report
        description: Optional additional description

    Returns:
        The created ContentReport
    """
    async with async_session_factory() as session:
        # Check for duplicate reports from same user
        existing_stmt = select(ContentReportDB).where(
            and_(
                ContentReportDB.reporter_id == reporter_id,
                ContentReportDB.content_id == content_id,
                ContentReportDB.status.in_([
                    ReportStatus.PENDING.value,
                    ReportStatus.UNDER_REVIEW.value
                ])
            )
        )
        existing_result = await session.execute(existing_stmt)
        existing = existing_result.scalar_one_or_none()

        if existing:
            # Return existing report
            return ContentReport(
                id=existing.id,
                reporter_id=existing.reporter_id,
                content_id=existing.content_id,
                content_type=existing.content_type,
                reason=ReportReason(existing.reason),
                description=existing.description,
                status=ReportStatus(existing.status),
                created_at=existing.created_at,
                resolved_at=existing.resolved_at,
                resolved_by=existing.resolved_by,
                resolution_action=ModerationAction(existing.resolution_action) if existing.resolution_action else None,
                resolution_notes=existing.resolution_notes
            )

        # Create new report
        report_db = ContentReportDB(
            id=uuid4(),
            reporter_id=reporter_id,
            content_id=content_id,
            content_type=content_type,
            reason=reason.value,
            description=description,
            status=ReportStatus.PENDING.value
        )

        session.add(report_db)
        await session.commit()
        await session.refresh(report_db)

        return ContentReport(
            id=report_db.id,
            reporter_id=report_db.reporter_id,
            content_id=report_db.content_id,
            content_type=report_db.content_type,
            reason=ReportReason(report_db.reason),
            description=report_db.description,
            status=ReportStatus(report_db.status),
            created_at=report_db.created_at
        )


async def get_reports(
    status: Optional[ReportStatus] = None,
    content_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[ContentReport]:
    """
    Get content reports with optional filtering.

    Args:
        status: Filter by report status
        content_type: Filter by content type
        limit: Maximum number of reports to return
        offset: Number of reports to skip

    Returns:
        List of ContentReport objects
    """
    async with async_session_factory() as session:
        stmt = select(ContentReportDB).order_by(
            ContentReportDB.created_at.desc()
        )

        if status:
            stmt = stmt.where(ContentReportDB.status == status.value)

        if content_type:
            stmt = stmt.where(ContentReportDB.content_type == content_type)

        stmt = stmt.limit(limit).offset(offset)

        result = await session.execute(stmt)
        reports_db = result.scalars().all()

        return [
            ContentReport(
                id=r.id,
                reporter_id=r.reporter_id,
                content_id=r.content_id,
                content_type=r.content_type,
                reason=ReportReason(r.reason),
                description=r.description,
                status=ReportStatus(r.status),
                created_at=r.created_at,
                resolved_at=r.resolved_at,
                resolved_by=r.resolved_by,
                resolution_action=ModerationAction(r.resolution_action) if r.resolution_action else None,
                resolution_notes=r.resolution_notes
            )
            for r in reports_db
        ]


async def get_report(report_id: UUID) -> Optional[ContentReport]:
    """Get a specific report by ID."""
    async with async_session_factory() as session:
        stmt = select(ContentReportDB).where(ContentReportDB.id == report_id)
        result = await session.execute(stmt)
        r = result.scalar_one_or_none()

        if not r:
            return None

        return ContentReport(
            id=r.id,
            reporter_id=r.reporter_id,
            content_id=r.content_id,
            content_type=r.content_type,
            reason=ReportReason(r.reason),
            description=r.description,
            status=ReportStatus(r.status),
            created_at=r.created_at,
            resolved_at=r.resolved_at,
            resolved_by=r.resolved_by,
            resolution_action=ModerationAction(r.resolution_action) if r.resolution_action else None,
            resolution_notes=r.resolution_notes
        )


async def resolve_report(
    report_id: UUID,
    action: ModerationAction,
    moderator_id: UUID,
    notes: Optional[str] = None
) -> Optional[ContentReport]:
    """
    Resolve a content report.

    Args:
        report_id: ID of the report to resolve
        action: The action taken
        moderator_id: ID of the moderator resolving
        notes: Optional notes about the resolution

    Returns:
        The updated ContentReport or None if not found
    """
    async with async_session_factory() as session:
        # Get the report
        stmt = select(ContentReportDB).where(ContentReportDB.id == report_id)
        result = await session.execute(stmt)
        report_db = result.scalar_one_or_none()

        if not report_db:
            return None

        # Update the report
        now = datetime.utcnow()
        report_db.status = ReportStatus.RESOLVED.value
        report_db.resolved_at = now
        report_db.resolved_by = moderator_id
        report_db.resolution_action = action.value
        report_db.resolution_notes = notes

        # Log the moderation action
        action_log = ModerationActionDB(
            id=uuid4(),
            report_id=report_id,
            moderator_id=moderator_id,
            action=action.value,
            content_id=report_db.content_id,
            content_type=report_db.content_type,
            notes=notes
        )
        session.add(action_log)

        await session.commit()
        await session.refresh(report_db)

        return ContentReport(
            id=report_db.id,
            reporter_id=report_db.reporter_id,
            content_id=report_db.content_id,
            content_type=report_db.content_type,
            reason=ReportReason(report_db.reason),
            description=report_db.description,
            status=ReportStatus(report_db.status),
            created_at=report_db.created_at,
            resolved_at=report_db.resolved_at,
            resolved_by=report_db.resolved_by,
            resolution_action=ModerationAction(report_db.resolution_action),
            resolution_notes=report_db.resolution_notes
        )


async def dismiss_report(
    report_id: UUID,
    moderator_id: UUID,
    notes: Optional[str] = None
) -> Optional[ContentReport]:
    """
    Dismiss a report as invalid or not actionable.

    Args:
        report_id: ID of the report to dismiss
        moderator_id: ID of the moderator
        notes: Optional notes

    Returns:
        The updated ContentReport or None if not found
    """
    async with async_session_factory() as session:
        stmt = select(ContentReportDB).where(ContentReportDB.id == report_id)
        result = await session.execute(stmt)
        report_db = result.scalar_one_or_none()

        if not report_db:
            return None

        report_db.status = ReportStatus.DISMISSED.value
        report_db.resolved_at = datetime.utcnow()
        report_db.resolved_by = moderator_id
        report_db.resolution_action = ModerationAction.NO_ACTION.value
        report_db.resolution_notes = notes

        await session.commit()
        await session.refresh(report_db)

        return ContentReport(
            id=report_db.id,
            reporter_id=report_db.reporter_id,
            content_id=report_db.content_id,
            content_type=report_db.content_type,
            reason=ReportReason(report_db.reason),
            description=report_db.description,
            status=ReportStatus(report_db.status),
            created_at=report_db.created_at,
            resolved_at=report_db.resolved_at,
            resolved_by=report_db.resolved_by,
            resolution_action=ModerationAction.NO_ACTION,
            resolution_notes=report_db.resolution_notes
        )


async def get_report_counts() -> dict:
    """Get counts of reports by status."""
    async with async_session_factory() as session:
        counts = {}

        for status in ReportStatus:
            stmt = select(ContentReportDB).where(
                ContentReportDB.status == status.value
            )
            result = await session.execute(stmt)
            counts[status.value] = len(result.scalars().all())

        return counts


async def get_content_reports(content_id: UUID) -> List[ContentReport]:
    """Get all reports for a specific piece of content."""
    async with async_session_factory() as session:
        stmt = select(ContentReportDB).where(
            ContentReportDB.content_id == content_id
        ).order_by(ContentReportDB.created_at.desc())

        result = await session.execute(stmt)
        reports_db = result.scalars().all()

        return [
            ContentReport(
                id=r.id,
                reporter_id=r.reporter_id,
                content_id=r.content_id,
                content_type=r.content_type,
                reason=ReportReason(r.reason),
                description=r.description,
                status=ReportStatus(r.status),
                created_at=r.created_at,
                resolved_at=r.resolved_at,
                resolved_by=r.resolved_by,
                resolution_action=ModerationAction(r.resolution_action) if r.resolution_action else None,
                resolution_notes=r.resolution_notes
            )
            for r in reports_db
        ]
