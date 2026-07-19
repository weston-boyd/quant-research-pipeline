import json
from pathlib import Path

import pytest

from quant_research_pipeline.bootstrap import (
    initialize_research_program,
)
from quant_research_pipeline.evidence_review import (
    read_evidence_index,
    register_next_evidence_review,
)
from quant_research_pipeline.manifest import (
    ResearchManifest,
    SamplePeriod,
)
from quant_research_pipeline.models import (
    StageStatus,
)
from quant_research_pipeline.repository import (
    open_research_program,
)
from quant_research_pipeline.stage_registry import (
    StageRegistry,
)


def make_manifest(
    tmp_path: Path,
) -> ResearchManifest:
    return ResearchManifest(
        research_id="review_test_v1",
        strategy_family="review_test",
        strategy_version="v1",
        universe=["BTCUSD"],
        timeframe="4h",
        development_period=SamplePeriod(
            start="2021-01-01",
            end="2024-12-31",
        ),
        holdout_period=SamplePeriod(
            start="2025-01-01",
            end="2025-12-31",
        ),
        data_source="test",
        cost_model_id="test",
        output_root=str(
            tmp_path / "program"
        ),
        hypothesis=(
            "Test evidence review registration."
        ),
        required_stages=list(
            StageRegistry().stage_ids()
        ),
    )


def pass_prerequisites(
    output_root: str,
) -> None:
    _, orchestrator = open_research_program(
        output_root
    )

    stages = [
        "baseline_signal",
        "signal_freeze",
        "entry_tournament",
        "exit_tournament",
        "regime_tournament",
        "participation_tournament",
    ]

    for stage_id in stages:
        assert orchestrator.can_start(stage_id)

        orchestrator.start_stage(stage_id)
        orchestrator.complete_stage(
            stage_id,
            StageStatus.PASSED,
            message="Test prerequisite passed.",
        )


def write_index(
    tmp_path: Path,
    *,
    research_id: str = "review_test_v1",
) -> Path:
    path = tmp_path / "evidence_index.json"

    payload = {
        "research_id": research_id,
        "summary": {
            "rule_count": 1,
            "matched_artifact_count": 0,
        },
        "rules": [
            {
                "rule_id": (
                    "honesty_audit_outputs"
                ),
                "stage_id": "honesty_audit",
                "matched_count": 0,
                "minimum_matches": 1,
                "requirement_met": False,
                "matches": [],
            }
        ],
    }

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    return path


def test_read_evidence_index(
    tmp_path: Path,
) -> None:
    index_path = write_index(tmp_path)

    payload = read_evidence_index(
        index_path
    )

    assert payload["research_id"] == (
        "review_test_v1"
    )


def test_registers_only_next_stage_for_review(
    tmp_path: Path,
) -> None:
    manifest = make_manifest(tmp_path)
    initialize_research_program(manifest)
    pass_prerequisites(
        manifest.output_root
    )

    index_path = write_index(tmp_path)

    result = register_next_evidence_review(
        manifest.output_root,
        index_path,
    )

    assert result.stage_id == (
        "honesty_audit"
    )
    assert result.prior_status == (
        "NOT_STARTED"
    )
    assert result.new_status == (
        "REVIEW_REQUIRED"
    )
    assert (
        result.matched_artifact_count
        == 0
    )


def test_review_status_is_persisted(
    tmp_path: Path,
) -> None:
    manifest = make_manifest(tmp_path)
    initialize_research_program(manifest)
    pass_prerequisites(
        manifest.output_root
    )

    index_path = write_index(tmp_path)

    register_next_evidence_review(
        manifest.output_root,
        index_path,
    )

    _, reopened = open_research_program(
        manifest.output_root
    )

    assert (
        reopened.result(
            "honesty_audit"
        ).status
        == StageStatus.REVIEW_REQUIRED
    )

    assert (
        reopened.result(
            "holdout_audit"
        ).status
        == StageStatus.NOT_STARTED
    )


def test_review_never_auto_passes_stage(
    tmp_path: Path,
) -> None:
    manifest = make_manifest(tmp_path)
    initialize_research_program(manifest)
    pass_prerequisites(
        manifest.output_root
    )

    index_path = write_index(tmp_path)

    register_next_evidence_review(
        manifest.output_root,
        index_path,
    )

    _, reopened = open_research_program(
        manifest.output_root
    )

    assert (
        reopened.result(
            "honesty_audit"
        ).status
        != StageStatus.PASSED
    )


def test_rejects_wrong_research_id(
    tmp_path: Path,
) -> None:
    manifest = make_manifest(tmp_path)
    initialize_research_program(manifest)
    pass_prerequisites(
        manifest.output_root
    )

    index_path = write_index(
        tmp_path,
        research_id="wrong_id",
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        register_next_evidence_review(
            manifest.output_root,
            index_path,
        )
