"""Canonical stage registry for the Quant Research Pipeline research process."""

from __future__ import annotations

from collections.abc import Iterable

from .models import StageDefinition


STANDARD_STAGE_DEFINITIONS = (
    StageDefinition(
        stage_id="research_registration",
        sequence=1,
        name="Research Registration",
        description=(
            "Register the hypothesis, universe, data, costs, samples, "
            "and preregistered evaluation requirements."
        ),
        artifact_directory="01_research_registration",
    ),
    StageDefinition(
        stage_id="baseline_signal",
        sequence=2,
        name="Baseline Signal Test",
        description=(
            "Evaluate the unoptimized strategy hypothesis and establish "
            "the baseline opportunity set."
        ),
        dependencies=("research_registration",),
        artifact_directory="02_baseline_signal",
    ),
    StageDefinition(
        stage_id="signal_freeze",
        sequence=3,
        name="Signal Freeze",
        description=(
            "Freeze signal logic before entry and exit architecture "
            "optimization."
        ),
        dependencies=("baseline_signal",),
        artifact_directory="03_signal_freeze",
    ),
    StageDefinition(
        stage_id="entry_tournament",
        sequence=4,
        name="Entry Architecture Tournament",
        description=(
            "Compare entry architectures against the same frozen signals."
        ),
        dependencies=("signal_freeze",),
        artifact_directory="04_entry_tournament",
    ),
    StageDefinition(
        stage_id="exit_tournament",
        sequence=5,
        name="Exit Architecture Tournament",
        description=(
            "Compare exit architectures without changing the frozen "
            "signal definition."
        ),
        dependencies=("entry_tournament",),
        artifact_directory="05_exit_tournament",
    ),
    StageDefinition(
        stage_id="regime_tournament",
        sequence=6,
        name="Regime Tournament",
        description=(
            "Evaluate preregistered market-state filters while preserving "
            "the frozen strategy candidate."
        ),
        dependencies=("exit_tournament",),
        artifact_directory="06_regime_tournament",
    ),
    StageDefinition(
        stage_id="participation_tournament",
        sequence=7,
        name="Participation Tournament",
        description=(
            "Evaluate universe participation, confirmations, and "
            "portfolio-selection logic."
        ),
        dependencies=("regime_tournament",),
        artifact_directory="07_participation_tournament",
    ),
    StageDefinition(
        stage_id="honesty_audit",
        sequence=8,
        name="Honesty Audit",
        description=(
            "Test timestamp alignment, look-ahead, feature availability, "
            "intrabar assumptions, and trade-ledger integrity."
        ),
        dependencies=("participation_tournament",),
        artifact_directory="08_honesty_audit",
    ),
    StageDefinition(
        stage_id="holdout_audit",
        sequence=9,
        name="Development vs Holdout Audit",
        description=(
            "Measure degradation between development and untouched holdout "
            "samples."
        ),
        dependencies=("honesty_audit",),
        artifact_directory="09_holdout_audit",
    ),
    StageDefinition(
        stage_id="walk_forward",
        sequence=10,
        name="Walk-Forward Validation",
        description=(
            "Evaluate repeated development and forward-validation windows."
        ),
        dependencies=("holdout_audit",),
        artifact_directory="10_walk_forward",
    ),
    StageDefinition(
        stage_id="parameter_plateau",
        sequence=11,
        name="Parameter Plateau Audit",
        description=(
            "Measure neighborhood stability and reject isolated parameter "
            "spikes."
        ),
        dependencies=("walk_forward",),
        artifact_directory="11_parameter_plateau",
    ),
    StageDefinition(
        stage_id="cost_stress",
        sequence=12,
        name="Execution-Cost Stress",
        description=(
            "Stress fees, spread, slippage, latency, and adverse execution."
        ),
        dependencies=("parameter_plateau",),
        artifact_directory="12_cost_stress",
    ),
    StageDefinition(
        stage_id="portfolio_audit",
        sequence=13,
        name="Portfolio Risk Audit",
        description=(
            "Measure attribution, overlap, concentration, correlations, "
            "and concurrent-risk limits."
        ),
        dependencies=("cost_stress",),
        artifact_directory="13_portfolio_audit",
    ),
    StageDefinition(
        stage_id="monte_carlo",
        sequence=14,
        name="Monte Carlo Suite",
        description=(
            "Run reshuffle, bootstrap, block-bootstrap, cost, parameter, "
            "drawdown, and risk-of-ruin simulations."
        ),
        dependencies=("portfolio_audit",),
        artifact_directory="14_monte_carlo",
    ),
    StageDefinition(
        stage_id="tick_replay",
        sequence=15,
        name="Tick and Replay Validation",
        description=(
            "Validate intrabar ordering, execution assumptions, fills, "
            "and event-level behavior."
        ),
        dependencies=("monte_carlo",),
        artifact_directory="15_tick_replay",
    ),
    StageDefinition(
        stage_id="deployment_decision",
        sequence=16,
        name="Deployment Readiness Decision",
        description=(
            "Issue the final promotion, rejection, remediation, or "
            "forward-validation decision."
        ),
        dependencies=("tick_replay",),
        artifact_directory="16_deployment_decision",
    ),
    StageDefinition(
        stage_id="forward_validation",
        sequence=17,
        name="Forward Validation",
        description=(
            "Track paper, shadow, or tightly risk-capped live performance "
            "against frozen expectations."
        ),
        dependencies=("deployment_decision",),
        artifact_directory="17_forward_validation",
    ),
)


class StageRegistry:
    """Validated lookup and ordering for research stages."""

    def __init__(
        self,
        definitions: Iterable[StageDefinition] = STANDARD_STAGE_DEFINITIONS,
    ) -> None:
        ordered = sorted(definitions, key=lambda stage: stage.sequence)

        if not ordered:
            raise ValueError("At least one stage definition is required")

        self._definitions: dict[str, StageDefinition] = {}

        sequences: set[int] = set()

        for definition in ordered:
            if definition.stage_id in self._definitions:
                raise ValueError(
                    f"Duplicate stage_id: {definition.stage_id}"
                )

            if definition.sequence in sequences:
                raise ValueError(
                    f"Duplicate stage sequence: {definition.sequence}"
                )

            self._definitions[definition.stage_id] = definition
            sequences.add(definition.sequence)

        self._validate_dependencies()

    def _validate_dependencies(self) -> None:
        for definition in self._definitions.values():
            for dependency in definition.dependencies:
                if dependency not in self._definitions:
                    raise ValueError(
                        f"Stage {definition.stage_id!r} depends on unknown "
                        f"stage {dependency!r}"
                    )

                dependency_sequence = self._definitions[dependency].sequence

                if dependency_sequence >= definition.sequence:
                    raise ValueError(
                        f"Stage {definition.stage_id!r} depends on "
                        f"non-prior stage {dependency!r}"
                    )

    def get(self, stage_id: str) -> StageDefinition:
        try:
            return self._definitions[stage_id]
        except KeyError as exc:
            raise KeyError(f"Unknown pipeline stage: {stage_id}") from exc

    def ordered(self) -> tuple[StageDefinition, ...]:
        return tuple(
            sorted(
                self._definitions.values(),
                key=lambda definition: definition.sequence,
            )
        )

    def stage_ids(self) -> tuple[str, ...]:
        return tuple(stage.stage_id for stage in self.ordered())

    def __contains__(self, stage_id: object) -> bool:
        return stage_id in self._definitions

    def __len__(self) -> int:
        return len(self._definitions)
