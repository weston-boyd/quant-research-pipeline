import json
from pathlib import Path

import pytest

from quant_research_pipeline.bootstrap import (
    initialize_research_program,
)
from quant_research_pipeline.evidence import (
    scan_research_evidence,
    sha256_file,
    write_evidence_index,
)
from quant_research_pipeline.manifest import (
    ResearchManifest,
    SamplePeriod,
)
from quant_research_pipeline.stage_registry import (
    StageRegistry,
)


def make_manifest(
    tmp_path: Path,
) -> ResearchManifest:
    return ResearchManifest(
        research_id="evidence_test_v1",
        strategy_family="evidence_test",
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
            "Test evidence scanning."
        ),
        required_stages=list(
            StageRegistry().stage_ids()
        ),
    )


def write_spec(
    tmp_path: Path,
) -> Path:
    legacy = tmp_path / "legacy"
    legacy.mkdir()

    (
        legacy
        / "family_plateau_ranking.csv"
    ).write_text(
        "candidate,score\ncontrol,1.0\n",
        encoding="utf-8",
    )

    spec = {
        "research_id": (
            "evidence_test_v1"
        ),
        "source_root": ".",
        "rules": [
            {
                "rule_id": "plateau",
                "stage_id": (
                    "parameter_plateau"
                ),
                "description": (
                    "Plateau evidence."
                ),
                "include_globs": [
                    "legacy/*plateau*.csv"
                ],
                "minimum_matches": 1,
            }
        ],
    }

    path = tmp_path / "evidence.json"
    path.write_text(
        json.dumps(spec),
        encoding="utf-8",
    )

    return path


def test_sha256_file_is_stable(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sample.txt"
    path.write_text(
        "quant-research-pipeline\n",
        encoding="utf-8",
    )

    first = sha256_file(path)
    second = sha256_file(path)

    assert first == second
    assert len(first) == 64


def test_scan_discovers_and_hashes_evidence(
    tmp_path: Path,
) -> None:
    manifest = make_manifest(tmp_path)
    initialize_research_program(manifest)
    spec_path = write_spec(tmp_path)

    payload = scan_research_evidence(
        manifest.output_root,
        spec_path,
    )

    assert (
        payload["summary"]["rule_count"]
        == 1
    )
    assert (
        payload["summary"][
            "matched_artifact_count"
        ]
        == 1
    )

    rule = payload["rules"][0]
    match = rule["matches"][0]

    assert (
        rule["requirement_met"]
        is True
    )
    assert match["filename"] == (
        "family_plateau_ranking.csv"
    )
    assert len(match["sha256"]) == 64


def test_scan_does_not_change_stage_status(
    tmp_path: Path,
) -> None:
    manifest = make_manifest(tmp_path)
    initialize_research_program(manifest)
    spec_path = write_spec(tmp_path)

    payload = scan_research_evidence(
        manifest.output_root,
        spec_path,
    )

    stage = payload["stages"][0]

    assert stage["stage_id"] == (
        "parameter_plateau"
    )
    assert stage["current_status"] == (
        "NOT_STARTED"
    )
    assert (
        stage["all_requirements_met"]
        is True
    )


def test_write_evidence_index(
    tmp_path: Path,
) -> None:
    manifest = make_manifest(tmp_path)
    initialize_research_program(manifest)
    spec_path = write_spec(tmp_path)

    payload = scan_research_evidence(
        manifest.output_root,
        spec_path,
    )

    index_path = write_evidence_index(
        manifest.output_root,
        payload,
    )

    assert index_path.is_file()

    written = json.loads(
        index_path.read_text(
            encoding="utf-8"
        )
    )

    assert written["research_id"] == (
        "evidence_test_v1"
    )


def test_scan_rejects_wrong_research_id(
    tmp_path: Path,
) -> None:
    manifest = make_manifest(tmp_path)
    initialize_research_program(manifest)
    spec_path = write_spec(tmp_path)

    payload = json.loads(
        spec_path.read_text(
            encoding="utf-8"
        )
    )

    payload["research_id"] = "wrong_id"

    spec_path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        scan_research_evidence(
            manifest.output_root,
            spec_path,
        )
