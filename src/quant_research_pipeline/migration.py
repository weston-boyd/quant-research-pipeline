"""Declarative migration of legacy research into standardized programs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .legacy_import import import_stage_artifacts
from .models import StageStatus
from .repository import open_research_program


@dataclass(frozen=True)
class MigrationStage:
    """One legacy stage import specification."""

    stage_id: str
    source_paths: tuple[str, ...]
    message: str
    metrics: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MigrationStage":
        return cls(
            stage_id=str(payload["stage_id"]),
            source_paths=tuple(
                str(path)
                for path in payload.get("source_paths", [])
            ),
            message=str(payload["message"]),
            metrics=dict(payload.get("metrics", {})),
        )


@dataclass(frozen=True)
class MigrationSpec:
    """Declarative legacy research migration specification."""

    research_id: str
    source_root: str
    stages: tuple[MigrationStage, ...]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MigrationSpec":
        return cls(
            research_id=str(payload["research_id"]),
            source_root=str(payload.get("source_root", ".")),
            stages=tuple(
                MigrationStage.from_dict(stage)
                for stage in payload.get("stages", [])
            ),
        )

    @classmethod
    def read_json(cls, path: str | Path) -> "MigrationSpec":
        payload = json.loads(
            Path(path).read_text(encoding="utf-8")
        )
        return cls.from_dict(payload)


@dataclass(frozen=True)
class MigrationResult:
    """Outcome for one requested stage migration."""

    stage_id: str
    action: str
    artifact_count: int
    message: str


def _resolve_source_paths(
    spec: MigrationSpec,
    spec_path: Path,
    stage: MigrationStage,
) -> list[Path]:
    source_root = Path(spec.source_root)

    if not source_root.is_absolute():
        source_root = (
            spec_path.parent / source_root
        ).resolve()

    return [
        (
            path
            if path.is_absolute()
            else source_root / path
        ).resolve()
        for path in map(Path, stage.source_paths)
    ]


def migrate_research_program(
    output_root: str | Path,
    migration_spec_path: str | Path,
    *,
    dry_run: bool = False,
    overwrite: bool = False,
) -> list[MigrationResult]:
    """Apply a declarative migration to an existing research program."""

    spec_path = Path(migration_spec_path).resolve()
    spec = MigrationSpec.read_json(spec_path)

    manifest, orchestrator = open_research_program(output_root)

    if manifest.research_id != spec.research_id:
        raise ValueError(
            "Migration research ID does not match target program: "
            f"{spec.research_id!r} != {manifest.research_id!r}"
        )

    if not spec.stages:
        raise ValueError(
            "Migration specification contains no stages"
        )

    seen_stage_ids: set[str] = set()
    previous_sequence = 0
    results: list[MigrationResult] = []

    for stage in spec.stages:
        definition = orchestrator.stage_registry.get(stage.stage_id)

        if stage.stage_id in seen_stage_ids:
            raise ValueError(
                f"Duplicate migration stage: {stage.stage_id}"
            )

        seen_stage_ids.add(stage.stage_id)

        if definition.sequence <= previous_sequence:
            raise ValueError(
                "Migration stages must follow pipeline order"
            )

        previous_sequence = definition.sequence

        if not stage.source_paths:
            raise ValueError(
                f"Migration stage {stage.stage_id!r} "
                "contains no source artifacts"
            )

        source_paths = _resolve_source_paths(
            spec,
            spec_path,
            stage,
        )

        missing = [
            path
            for path in source_paths
            if not path.is_file()
        ]

        if missing:
            raise FileNotFoundError(
                f"Missing artifacts for stage "
                f"{stage.stage_id!r}: "
                + ", ".join(str(path) for path in missing)
            )

        current = orchestrator.result(stage.stage_id)

        if current.status != StageStatus.NOT_STARTED:
            results.append(
                MigrationResult(
                    stage_id=stage.stage_id,
                    action="SKIPPED",
                    artifact_count=len(current.artifacts),
                    message=(
                        "Stage already has status "
                        f"{current.status.value}"
                    ),
                )
            )
            continue

        if dry_run:
            results.append(
                MigrationResult(
                    stage_id=stage.stage_id,
                    action="WOULD_IMPORT",
                    artifact_count=len(source_paths),
                    message=stage.message,
                )
            )
            continue

        imported = import_stage_artifacts(
            orchestrator,
            stage_id=stage.stage_id,
            source_paths=source_paths,
            message=stage.message,
            metrics=stage.metrics,
            overwrite=overwrite,
        )

        results.append(
            MigrationResult(
                stage_id=stage.stage_id,
                action="IMPORTED",
                artifact_count=len(imported),
                message=stage.message,
            )
        )

    return results
