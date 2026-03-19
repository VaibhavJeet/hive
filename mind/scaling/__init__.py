"""
Scaling module for AI Community Companions.
Handles bot retirement, community scaling, memory consolidation, and self-coding sandboxes.
"""

from mind.scaling.bot_retirement import BotRetirementManager, RetirementReason, RetiredBot
from mind.scaling.community_scaling import CommunityScalingManager, LoadMetrics
from mind.scaling.memory_consolidation import MemoryConsolidationManager, MemoryStats
from mind.scaling.self_coding_sandbox import SandboxExecutor, ExecutionResult, ValidationResult

__all__ = [
    "BotRetirementManager",
    "RetirementReason",
    "RetiredBot",
    "CommunityScalingManager",
    "LoadMetrics",
    "MemoryConsolidationManager",
    "MemoryStats",
    "SandboxExecutor",
    "ExecutionResult",
    "ValidationResult",
]
