"""Core models for the standardized quant research pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    """Return a timezone-aware UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


class StageStatus(StrEnum):
    """Permitted lifecycle states for a research-pipeline stage."""

    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    WAIVED = "WAIVED"


TERMINAL_STAGE_STATUSES = {
    StageStatus.PASSED,
    StageStatus.FAILED,
    StageStatus.BLOCKED,
    StageStatus.REVIEW_REQUIRED,
    StageStatus.WAIVED,
}


@dataclass(frozen=True)
class StageDefinition:
    """Static definition of one pipeline stage."""

    stage_id: str
    sequence: int
    name: str
    description: str
    required: bool = True
    dependencies: tuple[str, ...] = ()
    artifact_directory: str | None = None

    def __post_init__(self) -> None:
        if not self.stage_id.strip():
            raise ValueError("stage_id cannot be empty")

        if self.sequence < 1:
            raise ValueError("sequence must be at least 1")

        if self.stage_id in self.dependencies:
            raise ValueError(
                f"Stage {self.stage_id!r} cannot depend on itself"
            )


@dataclass
class StageResult:
    """Mutable execution record for a pipeline stage."""

    stage_id: str
    status: StageStatus = StageStatus.NOT_STARTED
    started_at: str | None = None
    completed_at: str | None = None
    message: str | None = None
    waiver_reason: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)

    def mark_running(self) -> None:
        self.status = StageStatus.RUNNING
        self.started_at = utc_now_iso()
        self.completed_at = None
        self.message = None

    def mark_complete(
        self,
        status: StageStatus,
        *,
        message: str | None = None,
        metrics: dict[str, Any] | None = None,
        artifacts: list[str] | None = None,
        waiver_reason: str | None = None,
    ) -> None:
        if status not in TERMINAL_STAGE_STATUSES:
            raise ValueError(
                f"Completion status must be terminal, received {status}"
            )

        if status == StageStatus.WAIVED and not waiver_reason:
            raise ValueError("A waived stage requires a waiver reason")

        if status != StageStatus.WAIVED and waiver_reason:
            raise ValueError(
                "waiver_reason is only valid when status is WAIVED"
            )

        if self.started_at is None:
            self.started_at = utc_now_iso()

        self.status = status
        self.completed_at = utc_now_iso()
        self.message = message
        self.waiver_reason = waiver_reason

        if metrics is not None:
            self.metrics = dict(metrics)

        if artifacts is not None:
            self.artifacts = list(artifacts)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PipelineRun:
    """State for one strategy-family research pipeline."""

    research_id: str
    strategy_family: str
    output_root: str
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)
    stages: dict[str, StageResult] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.research_id.strip():
            raise ValueError("research_id cannot be empty")

        if not self.strategy_family.strip():
            raise ValueError("strategy_family cannot be empty")

        if not self.output_root.strip():
            raise ValueError("output_root cannot be empty")

    @property
    def output_path(self) -> Path:
        return Path(self.output_root)

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def ensure_stage(self, stage_id: str) -> StageResult:
        result = self.stages.get(stage_id)

        if result is None:
            result = StageResult(stage_id=stage_id)
            self.stages[stage_id] = result
            self.touch()

        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "research_id": self.research_id,
            "strategy_family": self.strategy_family,
            "output_root": self.output_root,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
            "stages": {
                stage_id: result.to_dict()
                for stage_id, result in self.stages.items()
            },
        }
