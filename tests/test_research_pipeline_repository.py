from pathlib import Path

import pytest

from quant_research_pipeline.bootstrap import (
    initialize_research_program,
)
from quant_research_pipeline.legacy_import import (
    import_stage_artifacts,
    sha256_file,
)
from quant_research_pipeline.manifest import (
    ResearchManifest,
    SamplePeriod,
)
from quant_research_pipeline.models import StageStatus
from quant_research_pipeline.repository import open_research_program
from quant_research_pipeline.stage_registry import StageRegistry


def make_manifest(tmp_path: Path) -> ResearchManifest:
    return ResearchManifest(
        research_id="repository_test_v1",
        strategy_family="repository_test",
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
        output_root=str(tmp_path / "repository_test_v1"),
        hypothesis="Test repository loading.",
        required_stages=list(StageRegistry().stage_ids()),
    )


def pass_stage(orchestrator, stage_id: str) -> None:
    orchestrator.start_stage(stage_id)
    orchestrator.complete_stage(
        stage_id,
        StageStatus.PASSED,
        message=f"{stage_id} passed.",
    )


def test_open_research_program_restores_state(
    tmp_path: Path,
) -> None:
    manifest = make_manifest(tmp_path)
    original = initialize_research_program(manifest)

    pass_stage(original, "baseline_signal")

    loaded_manifest, loaded = open_research_program(
        manifest.output_root
    )

    assert loaded_manifest.research_id == manifest.research_id
    assert (
        loaded.result("baseline_signal").status
        == StageStatus.PASSED
    )
    assert loaded.next_actionable_stage() == "signal_freeze"


def test_legacy_import_copies_and_hashes_artifact(
    tmp_path: Path,
) -> None:
    manifest = make_manifest(tmp_path)
    orchestrator = initialize_research_program(manifest)

    source = tmp_path / "baseline.csv"
    source.write_text("trade_id,net_r\n1,1.5\n", encoding="utf-8")

    imported = import_stage_artifacts(
        orchestrator,
        stage_id="baseline_signal",
        source_paths=[source],
        message="Imported legacy baseline.",
        metrics={"trades": 1},
    )

    assert len(imported) == 1
    assert imported[0].sha256 == sha256_file(source)

    result = orchestrator.result("baseline_signal")

    assert result.status == StageStatus.PASSED
    assert result.metrics["legacy_import"] is True
    assert result.metrics["trades"] == 1

    destination = (
        Path(manifest.output_root)
        / result.artifacts[0]
    )
    assert destination.exists()


def test_legacy_import_rejects_unmet_dependencies(
    tmp_path: Path,
) -> None:
    manifest = make_manifest(tmp_path)
    orchestrator = initialize_research_program(manifest)

    source = tmp_path / "exit.csv"
    source.write_text("trade_id,net_r\n1,1.0\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="unmet dependencies"):
        import_stage_artifacts(
            orchestrator,
            stage_id="exit_tournament",
            source_paths=[source],
            message="Should fail.",
        )


def test_legacy_import_rejects_missing_file(
    tmp_path: Path,
) -> None:
    manifest = make_manifest(tmp_path)
    orchestrator = initialize_research_program(manifest)

    with pytest.raises(FileNotFoundError):
        import_stage_artifacts(
            orchestrator,
            stage_id="baseline_signal",
            source_paths=[tmp_path / "missing.csv"],
            message="Should fail.",
        )
