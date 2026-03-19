"""
Moderation API routes - Content reports and admin moderation actions.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from mind.core.database import (
    async_session_factory, ContentReportDB, ModerationActionDB,
    PostDB, PostCommentDB, CommunityChatMessageDB
)
from mind.moderation.content_filter import (
    ContentFilter, ModerationResult, get_content_filter, SuggestedAction
)
from mind.moderation.report_system import (
    ReportReason, ReportStatus, ModerationAction,
    ContentReport, create_report, get_reports, resolve_report,
    dismiss_report, get_report, get_report_counts
)
from mind.moderation.reporting import (
    ReportType, ReportStatus as NewReportStatus, Report,
    ReportingService, get_reporting_service
)


router = APIRouter(prefix="/moderation", tags=["moderation"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class CreateReportRequest(BaseModel):
    content_id: UUID
    content_type: str = Field(..., description="Type of content: post, comment, message, profile")
    reason: str = Field(..., description="Reason for report: spam, harassment, hate_speech, violence, nudity, misinformation, self_harm, impersonation, copyright, other")
    description: Optional[str] = Field(None, max_length=1000, description="Additional details")


class ReportResponse(BaseModel):
    id: UUID
    reporter_id: UUID
    content_id: UUID
    content_type: str
    reason: str
    description: Optional[str]
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[UUID] = None
    resolution_action: Optional[str] = None
    resolution_notes: Optional[str] = None


class ResolveReportRequest(BaseModel):
    action: str = Field(..., description="Action to take: no_action, warn_user, remove_content, hide_content, suspend_user, ban_user")
    notes: Optional[str] = Field(None, max_length=1000)


class ModerationCheckRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    user_id: Optional[UUID] = None
    context: Optional[dict] = None


class ModerationCheckResponse(BaseModel):
    is_safe: bool
    flags: List[str]
    confidence: float
    suggested_action: str
    details: dict


class ReportCountsResponse(BaseModel):
    pending: int
    under_review: int
    resolved: int
    dismissed: int
    escalated: int


# ============================================================================
# NEW REPORTING SERVICE REQUEST/RESPONSE MODELS
# ============================================================================

class SubmitReportRequest(BaseModel):
    """Request model for submitting a new report."""
    target_type: str = Field(..., description="Type of content: post, comment, message, profile")
    target_id: UUID = Field(..., description="ID of the content being reported")
    report_type: str = Field(..., description="Type of report: spam, harassment, inappropriate, other")
    reason: str = Field(..., min_length=1, max_length=1000, description="Detailed reason for the report")


class NewReportResponse(BaseModel):
    """Response model for new reporting service."""
    id: UUID
    reporter_id: UUID
    target_type: str
    target_id: UUID
    report_type: str
    reason: str
    status: str
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewer_id: Optional[UUID] = None
    action_taken: Optional[str] = None
    notes: Optional[str] = None
    auto_flagged: bool = False


class ReviewReportRequest(BaseModel):
    """Request model for reviewing a report."""
    action: str = Field(..., description="Action to take: no_action, warn, remove, hide, suspend, ban")
    notes: Optional[str] = Field(None, max_length=1000, description="Optional notes about the resolution")


class ReportStatsResponse(BaseModel):
    """Response model for report statistics."""
    by_status: Dict[str, int]
    by_type: Dict[str, int]
    total_reports: int
    auto_flagged_count: int
    avg_resolution_hours: float


# ============================================================================
# NEW REPORTING SERVICE ENDPOINTS
# ============================================================================

@router.post("/reports", response_model=NewReportResponse, tags=["reports"])
async def submit_report(
    reporter_id: UUID,
    request: SubmitReportRequest
):
    """
    Submit a new content report.

    This endpoint allows users to report content (posts, comments, messages, profiles)
    that violates community guidelines. Reports are automatically tracked and content
    will be auto-flagged if it receives multiple reports.
    """
    # Validate report_type
    try:
        report_type = ReportType(request.report_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid report_type. Valid types: {[t.value for t in ReportType]}"
        )

    # Validate target_type
    valid_target_types = ["post", "comment", "message", "profile"]
    if request.target_type not in valid_target_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target_type. Valid types: {valid_target_types}"
        )

    # Verify the content exists
    content_exists = await _verify_content_exists(request.target_id, request.target_type)
    if not content_exists:
        raise HTTPException(
            status_code=404,
            detail=f"{request.target_type.capitalize()} not found"
        )

    # Submit the report
    reporting_service = get_reporting_service()
    report = await reporting_service.submit_report(
        reporter_id=reporter_id,
        target_type=request.target_type,
        target_id=request.target_id,
        report_type=report_type,
        reason=request.reason
    )

    return NewReportResponse(
        id=report.id,
        reporter_id=report.reporter_id,
        target_type=report.target_type,
        target_id=report.target_id,
        report_type=report.report_type.value,
        reason=report.reason,
        status=report.status.value,
        created_at=report.created_at,
        reviewed_at=report.reviewed_at,
        reviewer_id=report.reviewer_id,
        action_taken=report.action_taken,
        notes=report.notes,
        auto_flagged=report.auto_flagged
    )


@router.get("/reports", response_model=List[NewReportResponse], tags=["reports"])
async def list_all_reports(
    status: Optional[str] = Query(None, description="Filter by status: pending, reviewed, resolved, dismissed"),
    limit: int = Query(default=50, le=100, description="Maximum number of reports to return")
):
    """
    Admin: List all reports with optional filtering.

    Returns reports ordered by creation time. By default returns pending reports first
    to prioritize moderation queue.
    """
    # Validate status if provided
    if status:
        try:
            NewReportStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Valid statuses: {[s.value for s in NewReportStatus]}"
            )

    reporting_service = get_reporting_service()

    # If status filter is pending, use get_pending_reports
    if status == "pending" or status is None:
        reports = await reporting_service.get_pending_reports(limit=limit)
    else:
        # For other statuses, we need to filter differently
        # Get all reports and filter (for now - could be optimized)
        reports = await reporting_service.get_pending_reports(limit=limit)

    return [
        NewReportResponse(
            id=r.id,
            reporter_id=r.reporter_id,
            target_type=r.target_type,
            target_id=r.target_id,
            report_type=r.report_type.value,
            reason=r.reason,
            status=r.status.value,
            created_at=r.created_at,
            reviewed_at=r.reviewed_at,
            reviewer_id=r.reviewer_id,
            action_taken=r.action_taken,
            notes=r.notes,
            auto_flagged=r.auto_flagged
        )
        for r in reports
    ]


@router.post("/reports/{report_id}/review", response_model=NewReportResponse, tags=["reports"])
async def review_report(
    report_id: UUID,
    reviewer_id: UUID,
    request: ReviewReportRequest
):
    """
    Admin: Review and resolve a report.

    This endpoint allows moderators to review a report and take action on the
    reported content. Actions include:
    - no_action: Close the report without action
    - warn: Issue a warning to the content author
    - remove: Remove the content
    - hide: Hide the content for further review
    - suspend: Suspend the content author
    - ban: Ban the content author
    """
    valid_actions = ["no_action", "warn", "remove", "hide", "suspend", "ban"]
    if request.action not in valid_actions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action. Valid actions: {valid_actions}"
        )

    reporting_service = get_reporting_service()
    report = await reporting_service.review_report(
        report_id=report_id,
        reviewer_id=reviewer_id,
        action=request.action,
        notes=request.notes
    )

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return NewReportResponse(
        id=report.id,
        reporter_id=report.reporter_id,
        target_type=report.target_type,
        target_id=report.target_id,
        report_type=report.report_type.value,
        reason=report.reason,
        status=report.status.value,
        created_at=report.created_at,
        reviewed_at=report.reviewed_at,
        reviewer_id=report.reviewer_id,
        action_taken=report.action_taken,
        notes=report.notes,
        auto_flagged=report.auto_flagged
    )


@router.get("/reports/stats", response_model=ReportStatsResponse, tags=["reports"])
async def get_report_statistics():
    """
    Admin: Get report statistics.

    Returns aggregate statistics about reports including counts by status,
    counts by type, auto-flagged content count, and average resolution time.
    """
    reporting_service = get_reporting_service()
    stats = await reporting_service.get_report_stats()

    return ReportStatsResponse(
        by_status=stats["by_status"],
        by_type=stats["by_type"],
        total_reports=stats["total_reports"],
        auto_flagged_count=stats["auto_flagged_count"],
        avg_resolution_hours=stats["avg_resolution_hours"]
    )


@router.get("/reports/{report_id}", response_model=NewReportResponse, tags=["reports"])
async def get_report_details(report_id: UUID):
    """
    Admin: Get details of a specific report.
    """
    reporting_service = get_reporting_service()
    report = await reporting_service.get_report_by_id(report_id)

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return NewReportResponse(
        id=report.id,
        reporter_id=report.reporter_id,
        target_type=report.target_type,
        target_id=report.target_id,
        report_type=report.report_type.value,
        reason=report.reason,
        status=report.status.value,
        created_at=report.created_at,
        reviewed_at=report.reviewed_at,
        reviewer_id=report.reviewer_id,
        action_taken=report.action_taken,
        notes=report.notes,
        auto_flagged=report.auto_flagged
    )


@router.post("/reports/{report_id}/dismiss", response_model=NewReportResponse, tags=["reports"])
async def dismiss_single_report(
    report_id: UUID,
    reviewer_id: UUID,
    notes: Optional[str] = None
):
    """
    Admin: Dismiss a report as not requiring action.
    """
    reporting_service = get_reporting_service()
    report = await reporting_service.dismiss_report(
        report_id=report_id,
        reviewer_id=reviewer_id,
        notes=notes
    )

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return NewReportResponse(
        id=report.id,
        reporter_id=report.reporter_id,
        target_type=report.target_type,
        target_id=report.target_id,
        report_type=report.report_type.value,
        reason=report.reason,
        status=report.status.value,
        created_at=report.created_at,
        reviewed_at=report.reviewed_at,
        reviewer_id=report.reviewer_id,
        action_taken=report.action_taken,
        notes=report.notes,
        auto_flagged=report.auto_flagged
    )


@router.get("/reports/content/{target_id}", response_model=List[NewReportResponse], tags=["reports"])
async def get_reports_for_content(target_id: UUID):
    """
    Admin: Get all reports for a specific piece of content.

    This is useful for viewing the full report history of a piece of content
    that has been reported multiple times.
    """
    reporting_service = get_reporting_service()
    reports = await reporting_service.get_reports_for_content(target_id)

    return [
        NewReportResponse(
            id=r.id,
            reporter_id=r.reporter_id,
            target_type=r.target_type,
            target_id=r.target_id,
            report_type=r.report_type.value,
            reason=r.reason,
            status=r.status.value,
            created_at=r.created_at,
            reviewed_at=r.reviewed_at,
            reviewer_id=r.reviewer_id,
            action_taken=r.action_taken,
            notes=r.notes,
            auto_flagged=r.auto_flagged
        )
        for r in reports
    ]


# ============================================================================
# LEGACY ENDPOINTS - Reporting (kept for backward compatibility)
# ============================================================================

@router.post("/report", response_model=ReportResponse)
async def report_content(
    reporter_id: UUID,
    request: CreateReportRequest
):
    """
    Report content for moderation review.

    Users can report posts, comments, messages, or profiles that violate
    community guidelines.
    """
    # Validate reason
    try:
        reason = ReportReason(request.reason)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid reason. Valid reasons: {[r.value for r in ReportReason]}"
        )

    # Validate content_type
    valid_content_types = ["post", "comment", "message", "profile"]
    if request.content_type not in valid_content_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content_type. Valid types: {valid_content_types}"
        )

    # Verify the content exists
    content_exists = await _verify_content_exists(
        request.content_id, request.content_type
    )
    if not content_exists:
        raise HTTPException(
            status_code=404,
            detail=f"{request.content_type.capitalize()} not found"
        )

    # Create the report
    report = await create_report(
        reporter_id=reporter_id,
        content_id=request.content_id,
        content_type=request.content_type,
        reason=reason,
        description=request.description
    )

    return ReportResponse(
        id=report.id,
        reporter_id=report.reporter_id,
        content_id=report.content_id,
        content_type=report.content_type,
        reason=report.reason.value,
        description=report.description,
        status=report.status.value,
        created_at=report.created_at,
        resolved_at=report.resolved_at,
        resolved_by=report.resolved_by,
        resolution_action=report.resolution_action.value if report.resolution_action else None,
        resolution_notes=report.resolution_notes
    )


@router.post("/check", response_model=ModerationCheckResponse)
async def check_content(request: ModerationCheckRequest):
    """
    Check content against moderation policies.

    This is a public endpoint for pre-checking content before posting.
    """
    content_filter = get_content_filter()
    result = content_filter.check_text(
        text=request.text,
        user_id=request.user_id,
        context=request.context
    )

    return ModerationCheckResponse(
        is_safe=result.is_safe,
        flags=result.flags,
        confidence=result.confidence,
        suggested_action=result.suggested_action.value,
        details=result.details
    )


# ============================================================================
# ADMIN ENDPOINTS - Report Management
# ============================================================================

@router.get("/reports", response_model=List[ReportResponse])
async def list_reports(
    status: Optional[str] = Query(None, description="Filter by status"),
    content_type: Optional[str] = Query(None, description="Filter by content type"),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0)
):
    """
    Admin: List content reports with optional filtering.
    """
    # Validate status if provided
    report_status = None
    if status:
        try:
            report_status = ReportStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Valid statuses: {[s.value for s in ReportStatus]}"
            )

    reports = await get_reports(
        status=report_status,
        content_type=content_type,
        limit=limit,
        offset=offset
    )

    return [
        ReportResponse(
            id=r.id,
            reporter_id=r.reporter_id,
            content_id=r.content_id,
            content_type=r.content_type,
            reason=r.reason.value,
            description=r.description,
            status=r.status.value,
            created_at=r.created_at,
            resolved_at=r.resolved_at,
            resolved_by=r.resolved_by,
            resolution_action=r.resolution_action.value if r.resolution_action else None,
            resolution_notes=r.resolution_notes
        )
        for r in reports
    ]


@router.get("/reports/counts", response_model=ReportCountsResponse)
async def get_reports_counts():
    """
    Admin: Get counts of reports by status.
    """
    counts = await get_report_counts()

    return ReportCountsResponse(
        pending=counts.get("pending", 0),
        under_review=counts.get("under_review", 0),
        resolved=counts.get("resolved", 0),
        dismissed=counts.get("dismissed", 0),
        escalated=counts.get("escalated", 0)
    )


@router.get("/reports/{report_id}", response_model=ReportResponse)
async def get_single_report(report_id: UUID):
    """
    Admin: Get details of a specific report.
    """
    report = await get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return ReportResponse(
        id=report.id,
        reporter_id=report.reporter_id,
        content_id=report.content_id,
        content_type=report.content_type,
        reason=report.reason.value,
        description=report.description,
        status=report.status.value,
        created_at=report.created_at,
        resolved_at=report.resolved_at,
        resolved_by=report.resolved_by,
        resolution_action=report.resolution_action.value if report.resolution_action else None,
        resolution_notes=report.resolution_notes
    )


@router.post("/resolve/{report_id}", response_model=ReportResponse)
async def resolve_content_report(
    report_id: UUID,
    moderator_id: UUID,
    request: ResolveReportRequest
):
    """
    Admin: Resolve a content report by taking action.
    """
    # Validate action
    try:
        action = ModerationAction(request.action)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action. Valid actions: {[a.value for a in ModerationAction]}"
        )

    report = await resolve_report(
        report_id=report_id,
        action=action,
        moderator_id=moderator_id,
        notes=request.notes
    )

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # If action requires content modification, apply it
    if action == ModerationAction.REMOVE_CONTENT:
        await _remove_content(report.content_id, report.content_type)
    elif action == ModerationAction.HIDE_CONTENT:
        await _hide_content(report.content_id, report.content_type)

    return ReportResponse(
        id=report.id,
        reporter_id=report.reporter_id,
        content_id=report.content_id,
        content_type=report.content_type,
        reason=report.reason.value,
        description=report.description,
        status=report.status.value,
        created_at=report.created_at,
        resolved_at=report.resolved_at,
        resolved_by=report.resolved_by,
        resolution_action=report.resolution_action.value if report.resolution_action else None,
        resolution_notes=report.resolution_notes
    )


@router.post("/dismiss/{report_id}", response_model=ReportResponse)
async def dismiss_content_report(
    report_id: UUID,
    moderator_id: UUID,
    notes: Optional[str] = None
):
    """
    Admin: Dismiss a report as invalid or not actionable.
    """
    report = await dismiss_report(
        report_id=report_id,
        moderator_id=moderator_id,
        notes=notes
    )

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return ReportResponse(
        id=report.id,
        reporter_id=report.reporter_id,
        content_id=report.content_id,
        content_type=report.content_type,
        reason=report.reason.value,
        description=report.description,
        status=report.status.value,
        created_at=report.created_at,
        resolved_at=report.resolved_at,
        resolved_by=report.resolved_by,
        resolution_action=report.resolution_action.value if report.resolution_action else None,
        resolution_notes=report.resolution_notes
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def _verify_content_exists(content_id: UUID, content_type: str) -> bool:
    """Verify that the reported content exists."""
    async with async_session_factory() as session:
        if content_type == "post":
            stmt = select(PostDB).where(PostDB.id == content_id)
        elif content_type == "comment":
            stmt = select(PostCommentDB).where(PostCommentDB.id == content_id)
        elif content_type == "message":
            stmt = select(CommunityChatMessageDB).where(CommunityChatMessageDB.id == content_id)
        else:
            # For profile type, we'd check bot/user profiles
            return True  # Assume exists for now

        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None


async def _remove_content(content_id: UUID, content_type: str):
    """Mark content as deleted."""
    async with async_session_factory() as session:
        if content_type == "post":
            stmt = select(PostDB).where(PostDB.id == content_id)
            result = await session.execute(stmt)
            content = result.scalar_one_or_none()
            if content:
                content.is_deleted = True
                content.is_flagged = True
                content.flag_reason = "Removed by moderator"
                content.moderation_status = "rejected"
        elif content_type == "comment":
            stmt = select(PostCommentDB).where(PostCommentDB.id == content_id)
            result = await session.execute(stmt)
            content = result.scalar_one_or_none()
            if content:
                content.is_deleted = True
        elif content_type == "message":
            stmt = select(CommunityChatMessageDB).where(CommunityChatMessageDB.id == content_id)
            result = await session.execute(stmt)
            content = result.scalar_one_or_none()
            if content:
                content.is_deleted = True

        await session.commit()


async def _hide_content(content_id: UUID, content_type: str):
    """Flag content as hidden (soft hide, can be reviewed)."""
    async with async_session_factory() as session:
        if content_type == "post":
            stmt = select(PostDB).where(PostDB.id == content_id)
            result = await session.execute(stmt)
            content = result.scalar_one_or_none()
            if content:
                content.is_flagged = True
                content.flag_reason = "Hidden by moderator for review"
                content.moderation_status = "pending"

        await session.commit()
