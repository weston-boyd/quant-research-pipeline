"""Research-manifest models and validation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .stage_registry import StageRegistry


@dataclass(frozen=True)
class SamplePeriod:
    """Inclusive research sample boundaries."""

    start: str
    end: str

    def __post_init__(self) -> None:
        if not self.start.strip():
            raise ValueError("Sample start cannot be empty")

        if not self.end.strip():
            raise ValueError("Sample end cannot be empty")

        if self.start > self.end:
            raise ValueError(
                f"Sample start {self.start!r} cannot be after end "
                f"{self.end!r}"
            )


@dataclass
class ResearchManifest:
    """Configuration contract for one standardized research program."""

    research_id: str
    strategy_family: str
    strategy_version: str
    universe: list[str]
    timeframe: str
    development_period: SamplePeriod
    holdout_period: SamplePeriod
    data_source: str
    cost_model_id: str
    output_root: str
    hypothesis: str
    required_stages: list[str]
    directions: list[str] = field(default_factory=lambda: ["long", "short"])
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.research_id = self.research_id.strip()
        self.strategy_family = self.strategy_family.strip()
        self.strategy_version = self.strategy_version.strip()
        self.timeframe = self.timeframe.strip()
        self.data_source = self.data_source.strip()
        self.cost_model_id = self.cost_model_id.strip()
        self.output_root = self.output_root.strip()
        self.hypothesis = self.hypothesis.strip()

        if not self.research_id:
            raise ValueError("research_id cannot be empty")

        if not self.strategy_family:
            raise ValueError("strategy_family cannot be empty")

        if not self.strategy_version:
            raise ValueError("strategy_version cannot be empty")

        if not self.universe:
            raise ValueError("universe must contain at least one symbol")

        normalized_universe = []

        for symbol in self.universe:
            normalized = symbol.strip().upper()

            if not normalized:
                raise ValueError("universe cannot contain empty symbols")

            if normalized not in normalized_universe:
                normalized_universe.append(normalized)

        self.universe = normalized_universe

        if not self.timeframe:
            raise ValueError("timeframe cannot be empty")

        if not self.data_source:
            raise ValueError("data_source cannot be empty")

        if not self.cost_model_id:
            raise ValueError("cost_model_id cannot be empty")

        if not self.output_root:
            raise ValueError("output_root cannot be empty")

        if not self.hypothesis:
            raise ValueError("hypothesis cannot be empty")

        if not self.required_stages:
            raise ValueError("required_stages cannot be empty")

        normalized_directions = []

        for direction in self.directions:
            normalized = direction.strip().lower()

            if normalized not in {"long", "short"}:
                raise ValueError(
                    f"Unsupported direction {direction!r}; expected "
                    "'long' or 'short'"
                )

            if normalized not in normalized_directions:
                normalized_directions.append(normalized)

        self.directions = normalized_directions

        if self.development_period.end >= self.holdout_period.start:
            raise ValueError(
                "Development period must end before holdout period starts"
            )

        self.validate_stage_requirements(StageRegistry())

    @property
    def output_path(self) -> Path:
        return Path(self.output_root)

    def validate_stage_requirements(
        self,
        registry: StageRegistry,
    ) -> None:
        unknown = [
            stage_id
            for stage_id in self.required_stages
            if stage_id not in registry
        ]

        if unknown:
            raise ValueError(
                "Manifest contains unknown required stages: "
                + ", ".join(unknown)
            )

        duplicates = {
            stage_id
            for stage_id in self.required_stages
            if self.required_stages.count(stage_id) > 1
        }

        if duplicates:
            raise ValueError(
                "Manifest contains duplicate required stages: "
                + ", ".join(sorted(duplicates))
            )

        required_set = set(self.required_stages)

        for stage_id in self.required_stages:
            definition = registry.get(stage_id)

            missing_dependencies = [
                dependency
                for dependency in definition.dependencies
                if dependency not in required_set
            ]

            if missing_dependencies:
                raise ValueError(
                    f"Required stage {stage_id!r} is missing required "
                    f"dependencies: {', '.join(missing_dependencies)}"
                )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["development_period"] = asdict(
            self.development_period
        )
        payload["holdout_period"] = asdict(
            self.holdout_period
        )
        return payload

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(path.suffix + ".tmp")

        temporary_path.write_text(
            json.dumps(
                self.to_dict(),
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        temporary_path.replace(path)
        return path

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> "ResearchManifest":
        copied = dict(payload)

        copied["development_period"] = SamplePeriod(
            **copied["development_period"]
        )
        copied["holdout_period"] = SamplePeriod(
            **copied["holdout_period"]
        )

        return cls(**copied)

    @classmethod
    def read_json(cls, path: Path) -> "ResearchManifest":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(payload)
