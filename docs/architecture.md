# Architecture

Quant Research Pipeline is an orchestration layer for systematic quantitative research.

It does not replace a backtest engine, market-data platform, execution simulator, portfolio optimizer, or broker interface. It coordinates the evidence those systems produce and records where each research program stands within a controlled validation lifecycle.

## Core components

### Research manifest

`ResearchManifest` defines the research program, including:

- research identifier;
- strategy family and version;
- instrument universe;
- timeframe;
- development and holdout periods;
- data source;
- cost model;
- output location;
- hypothesis;
- required stages;
- supported trade directions;
- optional metadata.

### Stage registry

`StageRegistry` provides validated stage lookup and canonical ordering.

It rejects duplicate identifiers, duplicate sequence numbers, unknown dependencies, and invalid dependency ordering.

### Persistent pipeline state

Each research program stores stage state so work can stop and resume without losing validation history.

### Artifact registry

Artifacts are associated with their research stages and can be inspected through the command-line interface.

### Evidence system

The evidence layer discovers reusable research outputs and creates an index for formal review.

Discovery does not automatically approve evidence. Evidence must pass an explicit review step.

### Migration system

Migration utilities allow legacy research outputs to enter the standardized directory model through a declared specification.

## Canonical lifecycle

1. Research Registration
2. Baseline Signal Test
3. Signal Freeze
4. Entry Architecture Tournament
5. Exit Architecture Tournament
6. Regime Tournament
7. Participation Tournament
8. Honesty Audit
9. Development vs Holdout Audit
10. Walk-Forward Validation
11. Parameter Plateau Audit
12. Execution-Cost Stress
13. Portfolio Risk Audit
14. Monte Carlo Suite
15. Tick and Replay Validation
16. Deployment Readiness Decision
17. Forward Validation

## Dependency model

The default lifecycle is sequential. Each stage depends on the immediately preceding stage.

This prevents later robustness results from being treated as valid when earlier methodological controls remain incomplete.

## Directory model

```text
research/<research-id>/
├── manifest.json
├── pipeline_state.json
├── 01_research_registration/
├── 02_baseline_signal/
├── 03_signal_freeze/
├── 04_entry_tournament/
├── 05_exit_tournament/
├── 06_regime_tournament/
├── 07_participation_tournament/
├── 08_honesty_audit/
├── 09_holdout_audit/
├── 10_walk_forward/
├── 11_parameter_plateau/
├── 12_cost_stress/
├── 13_portfolio_audit/
├── 14_monte_carlo/
├── 15_tick_replay/
├── 16_deployment_decision/
└── 17_forward_validation/
```

## Intended integrations

The pipeline can sit above:

- vectorized backtest engines;
- event-driven simulators;
- tick-replay systems;
- notebooks;
- distributed research jobs;
- portfolio construction tools;
- execution-cost models;
- paper and live trading platforms.

Those systems produce evidence. Quant Research Pipeline organizes, validates, and tracks that evidence.
