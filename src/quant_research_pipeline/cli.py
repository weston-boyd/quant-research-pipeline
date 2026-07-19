"""Command-line interface for standardized Quant Research Pipeline research programs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .evidence import (
    scan_research_evidence,
    write_evidence_index,
)
from .evidence_review import register_next_evidence_review
from .migration import migrate_research_program
from .models import StageStatus
from .repository import open_research_program


def build_parser() -> argparse.ArgumentParser:
    """Build the Quant Research Pipeline research command parser."""

    parser = argparse.ArgumentParser(
        prog="quant-research",
        description=(
            "Initialize, inspect, validate, and resume standardized "
            "Quant Research Pipeline research programs."
        ),
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    status_parser = subparsers.add_parser(
        "status",
        help="Show the full stage status table.",
    )
    status_parser.add_argument(
        "output_root",
        help="Research root containing manifest.json.",
    )
    status_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Return machine-readable JSON.",
    )

    next_parser = subparsers.add_parser(
        "next",
        help="Show the next actionable research stage.",
    )
    next_parser.add_argument(
        "output_root",
        help="Research root containing manifest.json.",
    )

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate manifest, pipeline state, and artifact references.",
    )
    validate_parser.add_argument(
        "output_root",
        help="Research root containing manifest.json.",
    )

    artifacts_parser = subparsers.add_parser(
        "artifacts",
        help="List artifacts registered to pipeline stages.",
    )
    artifacts_parser.add_argument(
        "output_root",
        help="Research root containing manifest.json.",
    )
    artifacts_parser.add_argument(
        "--stage",
        dest="stage_id",
        help="Restrict output to one stage ID.",
    )
    artifacts_parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Show only artifact references whose files are missing.",
    )

    migrate_parser = subparsers.add_parser(
        "migrate",
        help="Import legacy artifacts using a migration specification.",
    )
    migrate_parser.add_argument(
        "output_root",
        help="Target standardized research program.",
    )
    migrate_parser.add_argument(
        "migration_spec",
        help="Path to the migration JSON specification.",
    )
    migrate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and preview without copying artifacts.",
    )
    migrate_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite conflicting imported artifacts.",
    )

    evidence_parser = subparsers.add_parser(
        "evidence",
        help="Discover and index reusable research evidence.",
    )
    evidence_parser.add_argument(
        "output_root",
        help="Target standardized research program.",
    )
    evidence_parser.add_argument(
        "evidence_spec",
        help="Path to the evidence-scan JSON specification.",
    )
    evidence_parser.add_argument(
        "--write",
        action="store_true",
        help="Write evidence_index.json to the program root.",
    )
    evidence_parser.add_argument(
        "--show-files",
        action="store_true",
        help="Display every matched evidence file.",
    )

    review_parser = subparsers.add_parser(
        "review-evidence",
        help=(
            "Register indexed evidence for formal review of the "
            "next actionable stage."
        ),
    )
    review_parser.add_argument(
        "output_root",
        help="Target standardized research program.",
    )
    review_parser.add_argument(
        "evidence_index",
        help="Path to the generated evidence_index.json.",
    )

    return parser


def status_payload(output_root: str | Path) -> dict:
    """Build a serializable pipeline-status representation."""

    manifest, orchestrator = open_research_program(output_root)

    stages = []

    for definition in orchestrator.stage_registry.ordered():
        result = orchestrator.result(definition.stage_id)

        stages.append(
            {
                "sequence": definition.sequence,
                "stage_id": definition.stage_id,
                "name": definition.name,
                "status": result.status.value,
                "message": result.message,
                "metrics": result.metrics,
                "artifacts": result.artifacts,
            }
        )

    return {
        "research_id": manifest.research_id,
        "strategy_family": manifest.strategy_family,
        "strategy_version": manifest.strategy_version,
        "universe": manifest.universe,
        "timeframe": manifest.timeframe,
        "output_root": str(output_root),
        "next_actionable_stage": (
            orchestrator.next_actionable_stage()
        ),
        "stages": stages,
    }


def command_status(
    output_root: str | Path,
    *,
    as_json: bool = False,
) -> int:
    """Display the complete research-pipeline status."""

    payload = status_payload(output_root)

    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    print()
    print("QUANT RESEARCH PIPELINE")
    print("=" * 108)
    print(f"Research ID:      {payload['research_id']}")
    print(f"Strategy family:  {payload['strategy_family']}")
    print(f"Strategy version: {payload['strategy_version']}")
    print(f"Universe:         {', '.join(payload['universe'])}")
    print(f"Timeframe:        {payload['timeframe']}")
    print()

    print(
        f"{'#':>3}  {'STAGE ID':<26} "
        f"{'STAGE':<34} {'STATUS':<17} MESSAGE"
    )
    print("-" * 108)

    for stage in payload["stages"]:
        print(
            f"{stage['sequence']:>3}  "
            f"{stage['stage_id']:<26} "
            f"{stage['name']:<34} "
            f"{stage['status']:<17} "
            f"{stage['message'] or ''}"
        )

    print()
    print(
        "Next actionable stage: "
        f"{payload['next_actionable_stage'] or 'NONE'}"
    )

    return 0


def command_next(output_root: str | Path) -> int:
    """Display the next actionable stage."""

    manifest, orchestrator = open_research_program(output_root)
    stage_id = orchestrator.next_actionable_stage()

    print()
    print(f"Research ID: {manifest.research_id}")

    if stage_id is None:
        print("Next actionable stage: NONE")
        return 0

    definition = orchestrator.stage_registry.get(stage_id)

    print(f"Next actionable stage: {stage_id}")
    print(f"Stage name: {definition.name}")
    print(f"Sequence: {definition.sequence}")

    if definition.dependencies:
        print(
            "Dependencies: "
            + ", ".join(definition.dependencies)
        )
    else:
        print("Dependencies: NONE")

    return 0


def validate_program(output_root: str | Path) -> list[str]:
    """Return validation errors for one research program."""

    root = Path(output_root)
    errors: list[str] = []

    try:
        manifest, orchestrator = open_research_program(root)
    except Exception as exc:
        return [f"{type(exc).__name__}: {exc}"]

    if Path(manifest.output_root).resolve() != root.resolve():
        errors.append(
            "Manifest output_root does not match the opened directory: "
            f"{manifest.output_root!r} != {str(root)!r}"
        )

    for definition in orchestrator.stage_registry.ordered():
        result = orchestrator.result(definition.stage_id)

        if result.status in {
            StageStatus.PASSED,
            StageStatus.WAIVED,
        }:
            unmet = orchestrator.unmet_dependencies(
                definition.stage_id
            )

            if unmet:
                errors.append(
                    f"Completed stage {definition.stage_id!r} has "
                    "unmet dependencies: "
                    + ", ".join(unmet)
                )

        for artifact in result.artifacts:
            artifact_path = root / artifact

            if not artifact_path.is_file():
                errors.append(
                    f"Missing artifact for stage "
                    f"{definition.stage_id!r}: {artifact}"
                )

    return errors


def command_validate(output_root: str | Path) -> int:
    """Validate one standardized research program."""

    errors = validate_program(output_root)

    print()
    print("QUANT RESEARCH PIPELINE RESEARCH PROGRAM VALIDATION")
    print("=" * 80)
    print(f"Output root: {output_root}")

    if errors:
        print(f"Result: FAIL ({len(errors)} issue(s))")

        for index, error in enumerate(errors, start=1):
            print(f"{index:>3}. {error}")

        return 1

    print("Result: PASS")
    print("Manifest, pipeline state, dependencies, and artifacts are valid.")
    return 0


def collect_artifacts(
    output_root: str | Path,
    *,
    stage_id: str | None = None,
    missing_only: bool = False,
) -> list[dict]:
    """Collect registered artifact information."""

    root = Path(output_root)
    _, orchestrator = open_research_program(root)

    if stage_id is not None:
        orchestrator.stage_registry.get(stage_id)
        definitions = [
            orchestrator.stage_registry.get(stage_id)
        ]
    else:
        definitions = orchestrator.stage_registry.ordered()

    rows: list[dict] = []

    for definition in definitions:
        result = orchestrator.result(definition.stage_id)

        for artifact in result.artifacts:
            artifact_path = root / artifact
            exists = artifact_path.is_file()

            if missing_only and exists:
                continue

            rows.append(
                {
                    "stage_id": definition.stage_id,
                    "status": result.status.value,
                    "artifact": artifact,
                    "exists": exists,
                    "size_bytes": (
                        artifact_path.stat().st_size
                        if exists
                        else None
                    ),
                }
            )

    return rows


def command_artifacts(
    output_root: str | Path,
    *,
    stage_id: str | None = None,
    missing_only: bool = False,
) -> int:
    """Display registered stage artifacts."""

    rows = collect_artifacts(
        output_root,
        stage_id=stage_id,
        missing_only=missing_only,
    )

    print()
    print("QUANT RESEARCH PIPELINE RESEARCH ARTIFACTS")
    print("=" * 120)

    if not rows:
        print("No matching artifacts are registered.")
        return 0

    print(
        f"{'STAGE':<28} {'STATUS':<16} "
        f"{'EXISTS':<8} {'BYTES':>12}  ARTIFACT"
    )
    print("-" * 120)

    for row in rows:
        size = (
            f"{row['size_bytes']:,}"
            if row["size_bytes"] is not None
            else "-"
        )

        print(
            f"{row['stage_id']:<28} "
            f"{row['status']:<16} "
            f"{str(row['exists']):<8} "
            f"{size:>12}  "
            f"{row['artifact']}"
        )

    return 0


def command_review_evidence(
    output_root: str | Path,
    evidence_index: str | Path,
) -> int:
    """Register evidence for formal review of the next stage."""

    result = register_next_evidence_review(
        output_root,
        evidence_index,
    )

    print()
    print("QUANT RESEARCH PIPELINE EVIDENCE REVIEW REGISTRATION")
    print("=" * 88)
    print(f"Research ID:            {result.research_id}")
    print(f"Stage:                  {result.stage_id}")
    print(f"Prior status:           {result.prior_status}")
    print(f"New status:             {result.new_status}")
    print(f"Matching rules:         {result.rule_count}")
    print(
        "Matched artifacts:      "
        f"{result.matched_artifact_count}"
    )
    print(
        "All requirements met:   "
        f"{result.all_requirements_met}"
    )
    print(f"Message:                {result.message}")
    print()
    print(
        "Evidence is registered for formal review. "
        "No stage was automatically promoted to PASSED."
    )

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Quant Research Pipeline research CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "status":
            return command_status(
                args.output_root,
                as_json=args.as_json,
            )

        if args.command == "next":
            return command_next(args.output_root)

        if args.command == "validate":
            return command_validate(args.output_root)

        if args.command == "artifacts":
            return command_artifacts(
                args.output_root,
                stage_id=args.stage_id,
                missing_only=args.missing_only,
            )

        if args.command == "migrate":
            results = migrate_research_program(
                args.output_root,
                args.migration_spec,
                dry_run=args.dry_run,
                overwrite=args.overwrite,
            )

            print()
            print("QUANT RESEARCH PIPELINE RESEARCH MIGRATION")
            print("=" * 100)

            for result in results:
                print(
                    f"{result.stage_id:<28} "
                    f"{result.action:<14} "
                    f"{result.artifact_count:>3} artifact(s)  "
                    f"{result.message}"
                )

            return 0

        if args.command == "review-evidence":
            return command_review_evidence(
                args.output_root,
                args.evidence_index,
            )

        if args.command == "evidence":
            payload = scan_research_evidence(
                args.output_root,
                args.evidence_spec,
            )

            print()
            print("QUANT RESEARCH PIPELINE RESEARCH EVIDENCE")
            print("=" * 108)
            print(
                f"Research ID: {payload['research_id']}"
            )
            print(
                "Matched artifacts: "
                f"{payload['summary']['matched_artifact_count']}"
            )
            print()

            print(
                f"{'STAGE':<28} "
                f"{'RULE':<32} "
                f"{'MATCHES':>7} "
                f"{'REQUIRED':>9} "
                f"{'MET':>6}"
            )
            print("-" * 108)

            for rule in payload["rules"]:
                print(
                    f"{rule['stage_id']:<28} "
                    f"{rule['rule_id']:<32} "
                    f"{rule['matched_count']:>7} "
                    f"{rule['minimum_matches']:>9} "
                    f"{str(rule['requirement_met']):>6}"
                )

                if args.show_files:
                    for match in rule["matches"]:
                        print(
                            "    "
                            f"{match['relative_path']} "
                            f"({match['size_bytes']:,} bytes)"
                        )

            if args.write:
                index_path = write_evidence_index(
                    args.output_root,
                    payload,
                )
                print()
                print(
                    f"Evidence index written: {index_path}"
                )

            print()
            print(
                "Stage statuses were not changed. "
                "Evidence remains pending formal review."
            )

            return 0

    except Exception as exc:
        print(
            f"ERROR: {type(exc).__name__}: {exc}"
        )
        return 1

    parser.error(f"Unsupported command: {args.command}")
    return 2
