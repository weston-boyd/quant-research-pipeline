"""Dependency-aware orchestration for standardized research stages."""

from __future__ import annotations

from .artifact_registry import ArtifactRegistry
from .models import PipelineRun, StageResult, StageStatus
from .stage_registry import StageRegistry


DEPENDENCY_PASS_STATUSES = {
    StageStatus.PASSED,
    StageStatus.WAIVED,
}


class ResearchOrchestrator:
    """Manage pipeline stage state without executing strategy code yet."""

    def __init__(
        self,
        pipeline_run: PipelineRun,
        *,
        stage_registry: StageRegistry | None = None,
    ) -> None:
        self.pipeline_run = pipeline_run
        self.stage_registry = stage_registry or StageRegistry()
        self.artifacts = ArtifactRegistry(
            pipeline_run,
            self.stage_registry,
        )

        for stage_id in self.stage_registry.stage_ids():
            self.pipeline_run.ensure_stage(stage_id)

        self.artifacts.initialize_directories()
        self.artifacts.save_pipeline_status()

    def result(self, stage_id: str) -> StageResult:
        self.stage_registry.get(stage_id)
        return self.pipeline_run.ensure_stage(stage_id)

    def unmet_dependencies(self, stage_id: str) -> tuple[str, ...]:
        definition = self.stage_registry.get(stage_id)

        return tuple(
            dependency
            for dependency in definition.dependencies
            if self.result(dependency).status
            not in DEPENDENCY_PASS_STATUSES
        )

    def can_start(self, stage_id: str) -> bool:
        current_status = self.result(stage_id).status

        if current_status == StageStatus.RUNNING:
            return False

        return not self.unmet_dependencies(stage_id)

    def start_stage(self, stage_id: str) -> StageResult:
        unmet = self.unmet_dependencies(stage_id)

        if unmet:
            result = self.result(stage_id)
            result.mark_complete(
                StageStatus.BLOCKED,
                message=(
                    "Stage cannot start because required dependencies "
                    f"have not passed: {', '.join(unmet)}"
                ),
            )
            self.artifacts.save_pipeline_status()
            return result

        result = self.result(stage_id)
        result.mark_running()
        self.artifacts.save_pipeline_status()
        return result

    def complete_stage(
        self,
        stage_id: str,
        status: StageStatus,
        *,
        message: str | None = None,
        metrics: dict | None = None,
        artifacts: list[str] | None = None,
        waiver_reason: str | None = None,
    ) -> StageResult:
        result = self.result(stage_id)
        result.mark_complete(
            status,
            message=message,
            metrics=metrics,
            artifacts=artifacts,
            waiver_reason=waiver_reason,
        )
        self.artifacts.save_pipeline_status()
        return result

    def next_actionable_stage(self) -> str | None:
        for definition in self.stage_registry.ordered():
            result = self.result(definition.stage_id)

            if result.status == StageStatus.NOT_STARTED:
                if self.can_start(definition.stage_id):
                    return definition.stage_id

            if result.status in {
                StageStatus.FAILED,
                StageStatus.REVIEW_REQUIRED,
                StageStatus.BLOCKED,
            }:
                return definition.stage_id

        return None
