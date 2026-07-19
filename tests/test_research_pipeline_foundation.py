import json
from pathlib import Path

import pytest

from quant_research_pipeline.artifact_registry import ArtifactRegistry
from quant_research_pipeline.models import (
    PipelineRun,
    StageDefinition,
    StageResult,
    StageStatus,
)
from quant_research_pipeline.orchestrator import ResearchOrchestrator
from quant_research_pipeline.stage_registry import StageRegistry


def test_standard_registry_has_expected_order() -> None:
    registry = StageRegistry()

    assert len(registry) == 17
    assert registry.stage_ids()[0] == "research_registration"
    assert registry.stage_ids()[-1] == "forward_validation"
    assert (
        registry.get("portfolio_audit").dependencies
        == ("cost_stress",)
    )


def test_registry_rejects_unknown_dependency() -> None:
    definitions = (
        StageDefinition(
            stage_id="first",
            sequence=1,
            name="First",
            description="First stage",
            dependencies=("missing",),
        ),
    )

    with pytest.raises(ValueError, match="unknown stage"):
        StageRegistry(definitions)


def test_registry_rejects_forward_dependency() -> None:
    definitions = (
        StageDefinition(
            stage_id="first",
            sequence=1,
            name="First",
            description="First stage",
            dependencies=("second",),
        ),
        StageDefinition(
            stage_id="second",
            sequence=2,
            name="Second",
            description="Second stage",
        ),
    )

    with pytest.raises(ValueError, match="non-prior stage"):
        StageRegistry(definitions)


def test_waived_stage_requires_reason() -> None:
    result = StageResult(stage_id="test")

    with pytest.raises(ValueError, match="waiver reason"):
        result.mark_complete(StageStatus.WAIVED)


def test_artifact_registry_initializes_standard_directories(
    tmp_path: Path,
) -> None:
    run = PipelineRun(
        research_id="test_research",
        strategy_family="test_strategy",
        output_root=str(tmp_path / "test_research"),
    )
    registry = StageRegistry()
    artifacts = ArtifactRegistry(run, registry)

    artifacts.initialize_directories()
    status_path = artifacts.save_pipeline_status()

    assert status_path.exists()
    assert (
        tmp_path
        / "test_research"
        / "13_portfolio_audit"
    ).is_dir()

    payload = json.loads(status_path.read_text(encoding="utf-8"))
    assert payload["research_id"] == "test_research"


def test_orchestrator_blocks_stage_with_unmet_dependency(
    tmp_path: Path,
) -> None:
    run = PipelineRun(
        research_id="blocked_test",
        strategy_family="test_strategy",
        output_root=str(tmp_path / "blocked_test"),
    )
    orchestrator = ResearchOrchestrator(run)

    result = orchestrator.start_stage("baseline_signal")

    assert result.status == StageStatus.BLOCKED
    assert "research_registration" in result.message


def test_orchestrator_advances_after_pass(
    tmp_path: Path,
) -> None:
    run = PipelineRun(
        research_id="advance_test",
        strategy_family="test_strategy",
        output_root=str(tmp_path / "advance_test"),
    )
    orchestrator = ResearchOrchestrator(run)

    started = orchestrator.start_stage("research_registration")
    assert started.status == StageStatus.RUNNING

    completed = orchestrator.complete_stage(
        "research_registration",
        StageStatus.PASSED,
        metrics={"registered": True},
    )
    assert completed.status == StageStatus.PASSED

    assert orchestrator.can_start("baseline_signal")
    assert orchestrator.next_actionable_stage() == "baseline_signal"
