"""Load and resume persisted research-pipeline programs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .manifest import ResearchManifest
from .models import PipelineRun, StageResult, StageStatus
from .orchestrator import ResearchOrchestrator
from .stage_registry import StageRegistry


def load_pipeline_run(path: Path) -> PipelineRun:
    """Load a PipelineRun from a persisted pipeline_status.json file."""

    payload: dict[str, Any] = json.loads(
        path.read_text(encoding="utf-8")
    )

    run = PipelineRun(
        research_id=payload["research_id"],
        strategy_family=payload["strategy_family"],
        output_root=payload["output_root"],
        created_at=payload["created_at"],
        updated_at=payload["updated_at"],
        metadata=dict(payload.get("metadata", {})),
    )

    for stage_id, stage_payload in payload.get("stages", {}).items():
        run.stages[stage_id] = StageResult(
            stage_id=stage_id,
            status=StageStatus(stage_payload["status"]),
            started_at=stage_payload.get("started_at"),
            completed_at=stage_payload.get("completed_at"),
            message=stage_payload.get("message"),
            waiver_reason=stage_payload.get("waiver_reason"),
            metrics=dict(stage_payload.get("metrics", {})),
            artifacts=list(stage_payload.get("artifacts", [])),
        )

    return run


def open_research_program(
    output_root: str | Path,
) -> tuple[ResearchManifest, ResearchOrchestrator]:
    """Open an existing standardized research program."""

    root = Path(output_root)
    manifest_path = root / "manifest.json"
    status_path = root / "pipeline_status.json"

    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Research manifest does not exist: {manifest_path}"
        )

    if not status_path.exists():
        raise FileNotFoundError(
            f"Pipeline status does not exist: {status_path}"
        )

    manifest = ResearchManifest.read_json(manifest_path)
    run = load_pipeline_run(status_path)

    if run.research_id != manifest.research_id:
        raise ValueError(
            "Manifest and pipeline status research IDs do not match"
        )

    if run.strategy_family != manifest.strategy_family:
        raise ValueError(
            "Manifest and pipeline status strategy families do not match"
        )

    orchestrator = ResearchOrchestrator(
        run,
        stage_registry=StageRegistry(),
    )

    return manifest, orchestrator
