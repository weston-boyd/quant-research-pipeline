import json
from pathlib import Path

import pytest

from quant_research_pipeline.bootstrap import (
    initialize_research_program,
)
from quant_research_pipeline.manifest import (
    ResearchManifest,
    SamplePeriod,
)
from quant_research_pipeline.models import StageStatus
from quant_research_pipeline.stage_registry import StageRegistry


def make_manifest(tmp_path: Path) -> ResearchManifest:
    registry = StageRegistry()

    return ResearchManifest(
        research_id="test_strategy_v1",
        strategy_family="test_strategy",
        strategy_version="v1",
        universe=["btcusd", "ETHUSD", "btcusd"],
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
        output_root=str(tmp_path / "test_strategy_v1"),
        hypothesis="Test hypothesis.",
        required_stages=list(registry.stage_ids()),
        directions=["LONG", "short"],
    )


def test_manifest_normalizes_universe_and_directions(
    tmp_path: Path,
) -> None:
    manifest = make_manifest(tmp_path)

    assert manifest.universe == ["BTCUSD", "ETHUSD"]
    assert manifest.directions == ["long", "short"]


def test_manifest_rejects_overlapping_samples(
    tmp_path: Path,
) -> None:
    registry = StageRegistry()

    with pytest.raises(
        ValueError,
        match="Development period must end",
    ):
        ResearchManifest(
            research_id="bad_samples",
            strategy_family="test",
            strategy_version="v1",
            universe=["BTCUSD"],
            timeframe="4h",
            development_period=SamplePeriod(
                start="2021-01-01",
                end="2025-01-01",
            ),
            holdout_period=SamplePeriod(
                start="2025-01-01",
                end="2025-12-31",
            ),
            data_source="test",
            cost_model_id="test",
            output_root=str(tmp_path / "bad"),
            hypothesis="Test.",
            required_stages=list(registry.stage_ids()),
        )


def test_manifest_rejects_missing_stage_dependency(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="missing required dependencies",
    ):
        ResearchManifest(
            research_id="bad_stages",
            strategy_family="test",
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
            output_root=str(tmp_path / "bad_stages"),
            hypothesis="Test.",
            required_stages=[
                "research_registration",
                "baseline_signal",
                "exit_tournament",
            ],
        )


def test_manifest_round_trip_json(
    tmp_path: Path,
) -> None:
    manifest = make_manifest(tmp_path)
    path = tmp_path / "manifest.json"

    manifest.write_json(path)
    loaded = ResearchManifest.read_json(path)

    assert loaded.to_dict() == manifest.to_dict()


def test_bootstrap_initializes_program_and_registration(
    tmp_path: Path,
) -> None:
    manifest = make_manifest(tmp_path)
    orchestrator = initialize_research_program(manifest)

    root = Path(manifest.output_root)

    assert (root / "manifest.json").exists()
    assert (root / "pipeline_status.json").exists()
    assert (root / "05_exit_tournament").is_dir()

    registration = orchestrator.result(
        "research_registration"
    )

    assert registration.status == StageStatus.PASSED
    assert orchestrator.next_actionable_stage() == "baseline_signal"

    payload = json.loads(
        (root / "pipeline_status.json").read_text(
            encoding="utf-8"
        )
    )

    assert (
        payload["stages"]["research_registration"]["status"]
        == "PASSED"
    )


def test_bootstrap_refuses_accidental_overwrite(
    tmp_path: Path,
) -> None:
    manifest = make_manifest(tmp_path)

    initialize_research_program(manifest)

    with pytest.raises(
        FileExistsError,
        match="already exists",
    ):
        initialize_research_program(manifest)
