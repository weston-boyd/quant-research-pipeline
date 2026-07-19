"""Controlled import of legacy research artifacts."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .models import StageStatus
from .orchestrator import ResearchOrchestrator


@dataclass(frozen=True)
class ImportedArtifact:
    """Metadata for one artifact copied into the standard pipeline."""

    source_path: str
    destination_path: str
    sha256: str
    size_bytes: int


def sha256_file(path: Path) -> str:
    """Calculate a SHA-256 digest without loading the whole file."""

    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def import_stage_artifacts(
    orchestrator: ResearchOrchestrator,
    *,
    stage_id: str,
    source_paths: Iterable[str | Path],
    message: str,
    metrics: dict | None = None,
    overwrite: bool = False,
) -> list[ImportedArtifact]:
    """Copy verified legacy artifacts and mark their stage as passed."""

    orchestrator.stage_registry.get(stage_id)

    unmet = orchestrator.unmet_dependencies(stage_id)

    if unmet:
        raise RuntimeError(
            f"Cannot import stage {stage_id!r}; unmet dependencies: "
            + ", ".join(unmet)
        )

    sources = [Path(path) for path in source_paths]

    if not sources:
        raise ValueError("At least one source artifact is required")

    missing = [path for path in sources if not path.is_file()]

    if missing:
        raise FileNotFoundError(
            "Legacy artifacts were not found: "
            + ", ".join(str(path) for path in missing)
        )

    destination_directory = (
        orchestrator.artifacts.stage_directory(stage_id)
        / "legacy_import"
    )
    destination_directory.mkdir(parents=True, exist_ok=True)

    imported: list[ImportedArtifact] = []

    for source in sources:
        destination = destination_directory / source.name

        if destination.exists() and not overwrite:
            source_hash = sha256_file(source)
            destination_hash = sha256_file(destination)

            if source_hash != destination_hash:
                raise FileExistsError(
                    "Destination artifact already exists with different "
                    f"content: {destination}"
                )
        else:
            shutil.copy2(source, destination)

        imported.append(
            ImportedArtifact(
                source_path=str(source),
                destination_path=str(destination),
                sha256=sha256_file(destination),
                size_bytes=destination.stat().st_size,
            )
        )

    stage_metrics = dict(metrics or {})
    stage_metrics.update(
        {
            "legacy_import": True,
            "artifact_count": len(imported),
            "artifact_bytes": sum(
                item.size_bytes for item in imported
            ),
        }
    )

    artifact_paths = [
        str(
            Path(item.destination_path).relative_to(
                orchestrator.artifacts.root
            )
        )
        for item in imported
    ]

    orchestrator.complete_stage(
        stage_id,
        StageStatus.PASSED,
        message=message,
        metrics=stage_metrics,
        artifacts=artifact_paths,
    )

    return imported
