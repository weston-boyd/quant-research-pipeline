"""Formal review registration for discovered research evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import StageStatus
from .repository import open_research_program


@dataclass(frozen=True)
class EvidenceReviewResult:
    """Outcome of registering one stage for evidence review."""

    research_id: str
    stage_id: str
    prior_status: str
    new_status: str
    rule_count: int
    matched_artifact_count: int
    all_requirements_met: bool
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "research_id": self.research_id,
            "stage_id": self.stage_id,
            "prior_status": self.prior_status,
            "new_status": self.new_status,
            "rule_count": self.rule_count,
            "matched_artifact_count": (
                self.matched_artifact_count
            ),
            "all_requirements_met": (
                self.all_requirements_met
            ),
            "message": self.message,
        }


def read_evidence_index(
    path: str | Path,
) -> dict[str, Any]:
    """Read and minimally validate an evidence index."""

    index_path = Path(path)

    if not index_path.is_file():
        raise FileNotFoundError(
            f"Evidence index not found: {index_path}"
        )

    payload = json.loads(
        index_path.read_text(
            encoding="utf-8"
        )
    )

    required_keys = {
        "research_id",
        "summary",
        "rules",
    }

    missing = required_keys.difference(payload)

    if missing:
        raise ValueError(
            "Evidence index is missing required keys: "
            + ", ".join(sorted(missing))
        )

    return payload


def register_next_evidence_review(
    output_root: str | Path,
    evidence_index_path: str | Path,
) -> EvidenceReviewResult:
    """
    Move only the next actionable stage to REVIEW_REQUIRED.

    This function never promotes a stage to PASSED. Evidence must be
    reviewed separately before a formal pass decision is recorded.
    """

    manifest, orchestrator = open_research_program(
        output_root
    )

    payload = read_evidence_index(
        evidence_index_path
    )

    if payload["research_id"] != manifest.research_id:
        raise ValueError(
            "Evidence index research ID does not "
            "match target program: "
            f"{payload['research_id']!r} != "
            f"{manifest.research_id!r}"
        )

    stage_id = orchestrator.next_actionable_stage()

    if stage_id is None:
        raise ValueError(
            "Research program has no actionable stage."
        )

    stage_result = orchestrator.result(stage_id)
    prior_status = stage_result.status.value

    if stage_result.status not in {
        StageStatus.NOT_STARTED,
        StageStatus.REVIEW_REQUIRED,
    }:
        raise ValueError(
            "Next actionable stage cannot be registered "
            "for evidence review from status "
            f"{stage_result.status.value}: {stage_id}"
        )

    if not orchestrator.can_start(stage_id):
        unmet = orchestrator.unmet_dependencies(
            stage_id
        )
        raise ValueError(
            f"Stage {stage_id!r} has unmet dependencies: "
            + ", ".join(unmet)
        )

    matching_rules = [
        rule
        for rule in payload["rules"]
        if rule["stage_id"] == stage_id
    ]

    matched_artifact_count = sum(
        int(rule["matched_count"])
        for rule in matching_rules
    )

    all_requirements_met = bool(
        matching_rules
    ) and all(
        bool(rule["requirement_met"])
        for rule in matching_rules
    )

    if not matching_rules:
        message = (
            "No evidence-discovery rules were configured "
            f"for stage {stage_id}. Manual review is required."
        )
    elif matched_artifact_count == 0:
        message = (
            "Evidence scan found no qualifying artifacts "
            f"for stage {stage_id}. A new standardized "
            "stage audit must be performed."
        )
    elif all_requirements_met:
        message = (
            f"Evidence scan found {matched_artifact_count} "
            f"artifact(s) across {len(matching_rules)} "
            "rule(s). Formal human or programmatic review "
            "is required before this stage may pass."
        )
    else:
        message = (
            f"Evidence scan found {matched_artifact_count} "
            f"artifact(s), but one or more requirements "
            f"for stage {stage_id} were not met."
        )

    metrics = {
        "evidence_rule_count": len(
            matching_rules
        ),
        "matched_artifact_count": (
            matched_artifact_count
        ),
        "all_evidence_requirements_met": (
            all_requirements_met
        ),
        "evidence_rule_ids": [
            rule["rule_id"]
            for rule in matching_rules
        ],
    }

    orchestrator.complete_stage(
        stage_id,
        StageStatus.REVIEW_REQUIRED,
        message=message,
        metrics=metrics,
        artifacts=[
            Path(evidence_index_path).name
        ],
    )

    return EvidenceReviewResult(
        research_id=manifest.research_id,
        stage_id=stage_id,
        prior_status=prior_status,
        new_status=(
            StageStatus.REVIEW_REQUIRED.value
        ),
        rule_count=len(matching_rules),
        matched_artifact_count=(
            matched_artifact_count
        ),
        all_requirements_met=(
            all_requirements_met
        ),
        message=message,
    )
