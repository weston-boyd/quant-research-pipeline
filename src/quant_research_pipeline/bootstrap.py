"""Initialization helpers for standardized research programs."""

from __future__ import annotations

from pathlib import Path

from .manifest import ResearchManifest
from .models import PipelineRun, StageStatus
from .orchestrator import ResearchOrchestrator
from .stage_registry import StageRegistry


def initialize_research_program(
    manifest: ResearchManifest,
    *,
    overwrite: bool = False,
) -> ResearchOrchestrator:
    """Create a standardized research directory and initial pipeline state."""

    registry = StageRegistry()
    manifest.validate_stage_requirements(registry)

    output_root = manifest.output_path
    manifest_path = output_root / "manifest.json"
    status_path = output_root / "pipeline_status.json"

    if output_root.exists() and not overwrite:
        existing = [
            path
            for path in (manifest_path, status_path)
            if path.exists()
        ]

        if existing:
            raise FileExistsError(
                "Research program already exists. Use overwrite=True "
                "only when replacement is intentional: "
                + ", ".join(str(path) for path in existing)
            )

    output_root.mkdir(parents=True, exist_ok=True)

    run = PipelineRun(
        research_id=manifest.research_id,
        strategy_family=manifest.strategy_family,
        output_root=str(output_root),
        metadata={
            "strategy_version": manifest.strategy_version,
            "universe": list(manifest.universe),
            "timeframe": manifest.timeframe,
            "development_period": {
                "start": manifest.development_period.start,
                "end": manifest.development_period.end,
            },
            "holdout_period": {
                "start": manifest.holdout_period.start,
                "end": manifest.holdout_period.end,
            },
            "data_source": manifest.data_source,
            "cost_model_id": manifest.cost_model_id,
            "directions": list(manifest.directions),
            "required_stages": list(manifest.required_stages),
        },
    )

    orchestrator = ResearchOrchestrator(
        run,
        stage_registry=registry,
    )

    manifest.write_json(manifest_path)

    registration = orchestrator.start_stage(
        "research_registration"
    )

    if registration.status == StageStatus.RUNNING:
        orchestrator.complete_stage(
            "research_registration",
            StageStatus.PASSED,
            message="Research manifest validated and program initialized.",
            metrics={
                "universe_size": len(manifest.universe),
                "required_stage_count": len(
                    manifest.required_stages
                ),
                "development_start": (
                    manifest.development_period.start
                ),
                "development_end": (
                    manifest.development_period.end
                ),
                "holdout_start": manifest.holdout_period.start,
                "holdout_end": manifest.holdout_period.end,
            },
            artifacts=["manifest.json"],
        )

    return orchestrator
