"""Reusable Quant Research Pipeline research-pipeline infrastructure."""

from .bootstrap import initialize_research_program
from .manifest import ResearchManifest, SamplePeriod
from .repository import open_research_program
from .models import (
    PipelineRun,
    StageDefinition,
    StageResult,
    StageStatus,
)
from .stage_registry import StageRegistry

__all__ = [
    "PipelineRun",
    "ResearchManifest",
    "SamplePeriod",
    "StageDefinition",
    "StageRegistry",
    "StageResult",
    "StageStatus",
    "initialize_research_program",
    "open_research_program",
]
