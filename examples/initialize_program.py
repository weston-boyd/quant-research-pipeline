"""Initialize a new quantitative research program."""

from quant_research_pipeline import (
    ResearchManifest,
    SamplePeriod,
    StageRegistry,
    initialize_research_program,
)


def main() -> None:
    stage_registry = StageRegistry()

    manifest = ResearchManifest(
        research_id="example-momentum-v1",
        strategy_family="momentum",
        strategy_version="1.0.0",
        universe=["ES", "NQ"],
        timeframe="5m",
        development_period=SamplePeriod(
            start="2021-01-01",
            end="2023-12-31",
        ),
        holdout_period=SamplePeriod(
            start="2024-01-01",
            end="2024-12-31",
        ),
        data_source="example-market-data",
        cost_model_id="example-futures-cost-model-v1",
        output_root="example_output",
        hypothesis=(
            "Directional momentum after volatility expansion may persist long enough "
            "to support a systematic continuation strategy."
        ),
        required_stages=list(stage_registry.stage_ids()),
        directions=["long", "short"],
        metadata={
            "author": "Example User",
            "purpose": "Public API demonstration",
        },
    )

    orchestrator = initialize_research_program(manifest, overwrite=True)

    print(f"Research program initialized: {manifest.research_id}")
    print(f"Output root: {manifest.output_root}")
    print(f"Next actionable stage: {orchestrator.next_actionable_stage()}")


if __name__ == "__main__":
    main()
