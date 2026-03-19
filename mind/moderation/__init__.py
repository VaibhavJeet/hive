"""
Content Moderation System for AI Community Companions.
Provides content filtering, spam detection, and report management.
"""

from mind.moderation.content_filter import (
    ContentFilter,
    ModerationResult,
    get_content_filter
)
from mind.moderation.spam_detector import SpamDetector, SpamResult
from mind.moderation.word_lists import WordListManager
from mind.moderation.report_system import (
    ReportReason,
    ReportStatus,
    ContentReport,
    create_report,
    get_reports,
    resolve_report
)
from mind.moderation.reporting import (
    ReportType,
    ReportStatus as NewReportStatus,
    Report,
    ReportingService,
    get_reporting_service
)

__all__ = [
    # Content Filter
    "ContentFilter",
    "ModerationResult",
    "get_content_filter",
    # Spam Detection
    "SpamDetector",
    "SpamResult",
    # Word Lists
    "WordListManager",
    # Legacy Report System
    "ReportReason",
    "ReportStatus",
    "ContentReport",
    "create_report",
    "get_reports",
    "resolve_report",
    # New Reporting System
    "ReportType",
    "NewReportStatus",
    "Report",
    "ReportingService",
    "get_reporting_service",
]
