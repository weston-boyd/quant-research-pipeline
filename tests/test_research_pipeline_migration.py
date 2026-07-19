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
from quant_research_pipeline.migration import (
    migrate_research_program,
)
from quant_research_pipeline.models import StageStatus
from quant_research_pipeline.stage_registry import StageRegistry


def make_manifest(tmp_path: Path) -> ResearchManifest:
    return ResearchManifest(
        research_id="migration_test_v1",
        strategy_family="migration_test",
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
        output_root=str(tmp_path / "program"),
        hypothesis="Test migration.",
        required_stages=list(StageRegistry().stage_ids()),
    )


def write_spec(
    tmp_path: Path,
    *,
    research_id: str = "migration_test_v1",
) -> Path:
    source = tmp_path / "legacy.csv"
    source.write_text(
        "trade_id,net_r\n1,1.0\n",
        encoding="utf-8",
    )

    spec = {
        "research_id": research_id,
        "source_root": ".",
        "stages": [
            {
                "stage_id": "baseline_signal",
                "source_paths": ["legacy.csv"],
                "message": "Imported baseline.",
                "metrics": {"trades": 1}
            }
        ]
    }

    path = tmp_path / "migration.json"
    path.write_text(
        json.dumps(spec),
        encoding="utf-8",
    )
    return path


def test_migration_imports_stage(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    orchestrator = initialize_research_program(manifest)
    spec_path = write_spec(tmp_path)

    results = migrate_research_program(
        manifest.output_root,
        spec_path,
    )

    assert results[0].action == "IMPORTED"
    assert (
        orchestrator.result("baseline_signal").status
        == StageStatus.NOT_STARTED
    )

    from quant_research_pipeline.repository import (
        open_research_program,
    )

    _, reopened = open_research_program(
        manifest.output_root
    )

    assert (
        reopened.result("baseline_signal").status
        == StageStatus.PASSED
    )
    assert reopened.result(
        "baseline_signal"
    ).metrics["trades"] == 1


def test_migration_is_idempotent(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    initialize_research_program(manifest)
    spec_path = write_spec(tmp_path)

    migrate_research_program(
        manifest.output_root,
        spec_path,
    )
    results = migrate_research_program(
        manifest.output_root,
        spec_path,
    )

    assert results[0].action == "SKIPPED"


def test_migration_rejects_wrong_research_id(
    tmp_path: Path,
) -> None:
    manifest = make_manifest(tmp_path)
    initialize_research_program(manifest)
    spec_path = write_spec(
        tmp_path,
        research_id="wrong_id",
    )

    with pytest.raises(ValueError, match="does not match"):
        migrate_research_program(
            manifest.output_root,
            spec_path,
        )


def test_migration_dry_run_does_not_change_state(
    tmp_path: Path,
) -> None:
    manifest = make_manifest(tmp_path)
    initialize_research_program(manifest)
    spec_path = write_spec(tmp_path)

    results = migrate_research_program(
        manifest.output_root,
        spec_path,
        dry_run=True,
    )

    assert results[0].action == "WOULD_IMPORT"

    from quant_research_pipeline.repository import (
        open_research_program,
    )

    _, reopened = open_research_program(
        manifest.output_root
    )

    assert (
        reopened.result("baseline_signal").status
        == StageStatus.NOT_STARTED
    )
