from pathlib import Path

from quant_research_pipeline.bootstrap import (
    initialize_research_program,
)
from quant_research_pipeline.cli import (
    collect_artifacts,
    main,
    status_payload,
    validate_program,
)
from quant_research_pipeline.manifest import (
    ResearchManifest,
    SamplePeriod,
)
from quant_research_pipeline.models import StageStatus
from quant_research_pipeline.stage_registry import StageRegistry


def make_manifest(tmp_path: Path) -> ResearchManifest:
    return ResearchManifest(
        research_id="cli_test_v1",
        strategy_family="cli_test",
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
        data_source="test_data",
        cost_model_id="test_costs",
        output_root=str(tmp_path / "cli_test_v1"),
        hypothesis="Test the research CLI.",
        required_stages=list(StageRegistry().stage_ids()),
    )


def test_status_payload_reports_next_stage(
    tmp_path: Path,
) -> None:
    manifest = make_manifest(tmp_path)
    initialize_research_program(manifest)

    payload = status_payload(manifest.output_root)

    assert payload["research_id"] == "cli_test_v1"
    assert payload["next_actionable_stage"] == "baseline_signal"
    assert payload["stages"][0]["status"] == "PASSED"


def test_validate_program_passes_valid_program(
    tmp_path: Path,
) -> None:
    manifest = make_manifest(tmp_path)
    initialize_research_program(manifest)

    assert validate_program(manifest.output_root) == []


def test_validate_program_detects_missing_artifact(
    tmp_path: Path,
) -> None:
    manifest = make_manifest(tmp_path)
    orchestrator = initialize_research_program(manifest)

    orchestrator.start_stage("baseline_signal")
    orchestrator.complete_stage(
        "baseline_signal",
        StageStatus.PASSED,
        message="Baseline passed.",
        artifacts=["02_baseline_signal/missing.csv"],
    )

    errors = validate_program(manifest.output_root)

    assert len(errors) == 1
    assert "Missing artifact" in errors[0]


def test_collect_artifacts_reports_existing_file(
    tmp_path: Path,
) -> None:
    manifest = make_manifest(tmp_path)
    orchestrator = initialize_research_program(manifest)

    stage_directory = (
        orchestrator.artifacts.stage_directory(
            "baseline_signal"
        )
    )
    artifact_path = stage_directory / "baseline.csv"
    artifact_path.write_text(
        "trade_id,net_r\n1,1.0\n",
        encoding="utf-8",
    )

    relative_path = artifact_path.relative_to(
        Path(manifest.output_root)
    )

    orchestrator.start_stage("baseline_signal")
    orchestrator.complete_stage(
        "baseline_signal",
        StageStatus.PASSED,
        artifacts=[str(relative_path)],
    )

    rows = collect_artifacts(
        manifest.output_root,
        stage_id="baseline_signal",
    )

    assert len(rows) == 1
    assert rows[0]["exists"] is True
    assert rows[0]["size_bytes"] > 0


def test_cli_next_command_returns_success(
    tmp_path: Path,
    capsys,
) -> None:
    manifest = make_manifest(tmp_path)
    initialize_research_program(manifest)

    exit_code = main(
        ["next", manifest.output_root]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "baseline_signal" in output


def test_cli_validate_returns_failure_for_missing_root(
    tmp_path: Path,
    capsys,
) -> None:
    exit_code = main(
        ["validate", str(tmp_path / "missing")]
    )
    output = capsys.readouterr().out

    assert exit_code == 1
    assert "FAIL" in output
