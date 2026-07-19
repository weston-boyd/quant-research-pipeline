"""Evidence discovery and provenance indexing for research programs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .repository import open_research_program


def utc_now_iso() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    """Calculate the SHA-256 digest of a file."""

    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


@dataclass(frozen=True)
class EvidenceRule:
    """One reusable evidence-discovery rule."""

    rule_id: str
    stage_id: str
    description: str
    include_globs: tuple[str, ...]
    exclude_globs: tuple[str, ...] = ()
    minimum_matches: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> "EvidenceRule":
        return cls(
            rule_id=str(payload["rule_id"]),
            stage_id=str(payload["stage_id"]),
            description=str(payload["description"]),
            include_globs=tuple(
                str(value)
                for value in payload.get(
                    "include_globs",
                    [],
                )
            ),
            exclude_globs=tuple(
                str(value)
                for value in payload.get(
                    "exclude_globs",
                    [],
                )
            ),
            minimum_matches=int(
                payload.get("minimum_matches", 1)
            ),
            metadata=dict(
                payload.get("metadata", {})
            ),
        )


@dataclass(frozen=True)
class EvidenceScanSpec:
    """Declarative evidence-scan configuration."""

    research_id: str
    source_root: str
    rules: tuple[EvidenceRule, ...]
    specification_version: str = "1"

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> "EvidenceScanSpec":
        return cls(
            research_id=str(payload["research_id"]),
            source_root=str(
                payload.get("source_root", ".")
            ),
            rules=tuple(
                EvidenceRule.from_dict(rule)
                for rule in payload.get("rules", [])
            ),
            specification_version=str(
                payload.get(
                    "specification_version",
                    "1",
                )
            ),
        )

    @classmethod
    def read_json(
        cls,
        path: str | Path,
    ) -> "EvidenceScanSpec":
        payload = json.loads(
            Path(path).read_text(
                encoding="utf-8"
            )
        )
        return cls.from_dict(payload)


@dataclass(frozen=True)
class EvidenceMatch:
    """One discovered evidence artifact."""

    rule_id: str
    stage_id: str
    description: str
    source_path: str
    relative_path: str
    filename: str
    size_bytes: int
    sha256: str
    modified_utc: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "stage_id": self.stage_id,
            "description": self.description,
            "source_path": self.source_path,
            "relative_path": self.relative_path,
            "filename": self.filename,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "modified_utc": self.modified_utc,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class EvidenceRuleResult:
    """Evidence-discovery outcome for one rule."""

    rule_id: str
    stage_id: str
    description: str
    minimum_matches: int
    matched_count: int
    requirement_met: bool
    matches: tuple[EvidenceMatch, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "stage_id": self.stage_id,
            "description": self.description,
            "minimum_matches": self.minimum_matches,
            "matched_count": self.matched_count,
            "requirement_met": self.requirement_met,
            "matches": [
                match.to_dict()
                for match in self.matches
            ],
        }


def _resolve_source_root(
    spec_path: Path,
    source_root: str,
) -> Path:
    root = Path(source_root)

    if not root.is_absolute():
        root = spec_path.parent / root

    root = root.resolve()

    if not root.is_dir():
        raise FileNotFoundError(
            "Evidence source root does not exist: "
            f"{root}"
        )

    return root


def _collect_excluded_paths(
    source_root: Path,
    patterns: Iterable[str],
) -> set[Path]:
    excluded: set[Path] = set()

    for pattern in patterns:
        excluded.update(
            path.resolve()
            for path in source_root.glob(pattern)
            if path.is_file()
        )

    return excluded


def _collect_rule_paths(
    source_root: Path,
    rule: EvidenceRule,
) -> list[Path]:
    if not rule.include_globs:
        raise ValueError(
            f"Evidence rule {rule.rule_id!r} "
            "contains no include globs"
        )

    excluded = _collect_excluded_paths(
        source_root,
        rule.exclude_globs,
    )

    matched: set[Path] = set()

    for pattern in rule.include_globs:
        for path in source_root.glob(pattern):
            resolved = path.resolve()

            if (
                resolved.is_file()
                and resolved not in excluded
            ):
                matched.add(resolved)

    return sorted(
        matched,
        key=lambda item: str(item).lower(),
    )


def scan_research_evidence(
    output_root: str | Path,
    evidence_spec_path: str | Path,
) -> dict[str, Any]:
    """Scan legacy outputs for reusable research evidence."""

    spec_path = Path(
        evidence_spec_path
    ).resolve()

    spec = EvidenceScanSpec.read_json(
        spec_path
    )

    manifest, orchestrator = open_research_program(
        output_root
    )

    if manifest.research_id != spec.research_id:
        raise ValueError(
            "Evidence specification research ID "
            "does not match target program: "
            f"{spec.research_id!r} != "
            f"{manifest.research_id!r}"
        )

    if not spec.rules:
        raise ValueError(
            "Evidence specification contains no rules"
        )

    source_root = _resolve_source_root(
        spec_path,
        spec.source_root,
    )

    seen_rule_ids: set[str] = set()
    rule_results: list[EvidenceRuleResult] = []

    for rule in spec.rules:
        if rule.rule_id in seen_rule_ids:
            raise ValueError(
                "Duplicate evidence rule: "
                f"{rule.rule_id}"
            )

        seen_rule_ids.add(rule.rule_id)

        orchestrator.stage_registry.get(
            rule.stage_id
        )

        paths = _collect_rule_paths(
            source_root,
            rule,
        )

        matches: list[EvidenceMatch] = []

        for path in paths:
            stat = path.stat()

            matches.append(
                EvidenceMatch(
                    rule_id=rule.rule_id,
                    stage_id=rule.stage_id,
                    description=rule.description,
                    source_path=str(path),
                    relative_path=str(
                        path.relative_to(
                            source_root
                        )
                    ),
                    filename=path.name,
                    size_bytes=stat.st_size,
                    sha256=sha256_file(path),
                    modified_utc=(
                        datetime.fromtimestamp(
                            stat.st_mtime,
                            tz=timezone.utc,
                        ).isoformat()
                    ),
                    metadata=dict(rule.metadata),
                )
            )

        rule_results.append(
            EvidenceRuleResult(
                rule_id=rule.rule_id,
                stage_id=rule.stage_id,
                description=rule.description,
                minimum_matches=(
                    rule.minimum_matches
                ),
                matched_count=len(matches),
                requirement_met=(
                    len(matches)
                    >= rule.minimum_matches
                ),
                matches=tuple(matches),
            )
        )

    all_matches = [
        match
        for result in rule_results
        for match in result.matches
    ]

    stages: dict[str, dict[str, Any]] = {}

    for result in rule_results:
        stage = stages.setdefault(
            result.stage_id,
            {
                "stage_id": result.stage_id,
                "current_status": (
                    orchestrator.result(
                        result.stage_id
                    ).status.value
                ),
                "rule_count": 0,
                "matched_artifact_count": 0,
                "all_requirements_met": True,
            },
        )

        stage["rule_count"] += 1
        stage["matched_artifact_count"] += (
            result.matched_count
        )
        stage["all_requirements_met"] = (
            stage["all_requirements_met"]
            and result.requirement_met
        )

    return {
        "schema_version": "1",
        "research_id": manifest.research_id,
        "strategy_family": (
            manifest.strategy_family
        ),
        "strategy_version": (
            manifest.strategy_version
        ),
        "specification_version": (
            spec.specification_version
        ),
        "specification_path": str(spec_path),
        "source_root": str(source_root),
        "scanned_at_utc": utc_now_iso(),
        "summary": {
            "rule_count": len(rule_results),
            "matched_artifact_count": len(
                all_matches
            ),
            "requirements_met": sum(
                1
                for result in rule_results
                if result.requirement_met
            ),
            "requirements_not_met": sum(
                1
                for result in rule_results
                if not result.requirement_met
            ),
        },
        "stages": list(stages.values()),
        "rules": [
            result.to_dict()
            for result in rule_results
        ],
    }


def write_evidence_index(
    output_root: str | Path,
    payload: dict[str, Any],
) -> Path:
    """Atomically persist evidence_index.json."""

    root = Path(output_root)
    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    target = root / "evidence_index.json"
    temporary = (
        root / "evidence_index.json.tmp"
    )

    temporary.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    temporary.replace(target)

    return target
