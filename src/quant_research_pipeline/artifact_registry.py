"""Persistence helpers for research-pipeline state and artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import PipelineRun
from .stage_registry import StageRegistry


class ArtifactRegistry:
    """Create standard output directories and persist pipeline state."""

    def __init__(
        self,
        pipeline_run: PipelineRun,
        stage_registry: StageRegistry,
    ) -> None:
        self.pipeline_run = pipeline_run
        self.stage_registry = stage_registry

    @property
    def root(self) -> Path:
        return self.pipeline_run.output_path

    @property
    def status_path(self) -> Path:
        return self.root / "pipeline_status.json"

    def initialize_directories(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

        for definition in self.stage_registry.ordered():
            directory_name = (
                definition.artifact_directory or definition.stage_id
            )
            (self.root / directory_name).mkdir(
                parents=True,
                exist_ok=True,
            )

    def stage_directory(self, stage_id: str) -> Path:
        definition = self.stage_registry.get(stage_id)
        directory_name = (
            definition.artifact_directory or definition.stage_id
        )
        path = self.root / directory_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_json(
        self,
        path: Path,
        payload: dict[str, Any],
    ) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(path.suffix + ".tmp")

        temporary_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary_path.replace(path)
        return path

    def save_pipeline_status(self) -> Path:
        self.pipeline_run.touch()
        return self.write_json(
            self.status_path,
            self.pipeline_run.to_dict(),
        )
