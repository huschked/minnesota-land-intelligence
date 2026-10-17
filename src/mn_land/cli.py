from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from decimal import Decimal
from pathlib import Path

from mn_land.config.settings import SETTINGS
from mn_land.counties.isanti import IsantiAdapter
from mn_land.delinquency.file_loader import DelinquencyFileError, inspect_delinquency_file
from mn_land.delinquency.pipeline import (
    DelinquencyPipelineError,
    import_and_join_delinquency,
    replay_delinquency,
)
from mn_land.ingestion.pipeline import run_pipeline
from mn_land.runs import RunValidationError, select_latest
from mn_land.utils.http import ArcGISError
from mn_land.utils.validation import minimum_acres

LOGGER = logging.getLogger(__name__)


def decimal_argument(value: str) -> Decimal:
    try:
        return minimum_acres(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mn-land", description="Minnesota Land Intelligence Platform"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    compare_command = sub.add_parser("compare-snapshots", help="Compare saved completed joins offline")
    compare_command.add_argument("--county", choices=("isanti",), required=True)
    compare_command.add_argument("--before", type=Path, required=True)
    compare_command.add_argument("--after", type=Path, required=True)
    compare_command.add_argument("--as-of", type=date.fromisoformat, required=True, help="UTC calendar date")
    compare_command.add_argument("--stale-after-days", type=int, default=30)
    compare_command.add_argument("--output-root", type=Path, help="Processed data root")
    for name in ("validate-source", "find-candidates", "status"):
        command = sub.add_parser(name)
        command.add_argument("--county", choices=("isanti",), required=True)
        if name == "find-candidates":
            command.add_argument(
                "--min-acres", type=decimal_argument, default=Decimal(SETTINGS.default_min_acres)
            )
    inspect_command = sub.add_parser("inspect-delinquency-file")
    inspect_command.add_argument("--county", choices=("isanti",), required=True)
    inspect_command.add_argument("--file", type=Path, required=True)
    import_command = sub.add_parser("import-delinquency")
    import_command.add_argument("--county", choices=("isanti",), required=True)
    import_command.add_argument("--file", type=Path, required=True)
    import_command.add_argument("--mapping", type=Path, required=True)
    import_command.add_argument(
        "--parcel-snapshot", type=Path,
        help="Explicit completed raw parcel snapshot instead of latest eligible",
    )
    import_command.add_argument("--output-root", type=Path, help="Processed data root")
    import_command.add_argument(
        "--min-acres", type=decimal_argument, default=Decimal(SETTINGS.default_min_acres)
    )
    replay_command = sub.add_parser("replay-delinquency")
    replay_command.add_argument("--county", choices=("isanti",), required=True)
    replay_input = replay_command.add_mutually_exclusive_group(required=True)
    replay_input.add_argument("--snapshot", type=Path, help="Completed join with pinned inputs")
    replay_input.add_argument("--import-snapshot", type=Path, help="Completed raw delinquency import")
    replay_command.add_argument("--parcel-snapshot", type=Path, help="Completed raw parcel acquisition")
    replay_command.add_argument(
        "--min-acres", type=decimal_argument,
        help="Default: recorded join threshold, or configured default for an explicit raw pair",
    )
    replay_command.add_argument("--output-root", type=Path, help="Processed data root")
    review_command = sub.add_parser("review-delinquency")
    review_command.add_argument("--county", choices=("isanti",), required=True)
    review_command.add_argument("--snapshot", type=Path, required=True)
    review_command.add_argument("--min-acres", type=decimal_argument, default=Decimal(10))
    review_command.add_argument(
        "--comparison",
        type=Path,
        help="Explicit retained comparison evidence; no automatic legacy discovery",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    if args.command == "compare-snapshots":
        from mn_land.runs import read_json
        from mn_land.snapshot_diff import compare_snapshots

        try:
            output = compare_snapshots(
                args.before, args.after, as_of=args.as_of,
                stale_after_days=args.stale_after_days, processed_root=args.output_root,
            )
        except (RunValidationError, OSError, ValueError) as exc:
            LOGGER.error("%s", exc)
            return 2
        manifest = read_json(output / "manifest.json")
        print(f"Offline snapshot comparison: {output}")
        print(json.dumps(manifest["summary"], sort_keys=True))
        for warning in manifest["warnings"]:
            print(f"WARNING: {warning}")
        print("Missing is not paid. Current payment statuses and identity relationships remain unknown.")
        return 0
    if args.command == "review-delinquency":
        from mn_land.counties.isanti.review import build_review

        try:
            output = build_review(args.snapshot, args.min_acres, comparison_path=args.comparison)
        except (DelinquencyFileError, DelinquencyPipelineError, ValueError, OSError) as exc:
            LOGGER.error("%s", exc)
            return 2
        print(f"Review artifacts: {output}")
        print((output / "summary.json").read_text(encoding="utf-8"))
        return 0
    if args.command == "status":
        for label, root, kind in (
            ("Parcel raw acquisition", SETTINGS.raw_dir / "isanti", "parcel_raw"),
            (
                "Parcel processed results",
                SETTINGS.processed_dir / "isanti" / "parcels",
                "parcel_processed",
            ),
            (
                "Delinquency raw import",
                SETTINGS.raw_dir / "isanti" / "delinquency",
                "delinquency_raw",
            ),
            (
                "Delinquency processed results",
                SETTINGS.processed_dir / "isanti" / "delinquency",
                "delinquency_processed",
            ),
            ("Review results", SETTINGS.processed_dir / "isanti" / "review", "review"),
            ("Snapshot comparisons", SETTINGS.processed_dir / "isanti" / "comparisons", "comparison"),
        ):
            diagnostics = []
            try:
                latest = select_latest(root, kind, diagnostics=diagnostics)
            except (RunValidationError, OSError):
                print(f"{label}: NO ELIGIBLE COMPLETE RUN")
            else:
                print(f"{label}: COMPLETE {latest.path.name}")
                if kind == "delinquency_processed":
                    print(f"Verified candidates: {latest.manifest['verified_candidates']}")
                    if latest.manifest.get("unverified_matches"):
                        print("Verification: HOLD - county reconciliation required")
            legacy = (
                [
                    path
                    for path in root.iterdir()
                    if path.is_dir()
                    and (path / "manifest.json").is_file()
                    and not (path / "completion.json").exists()
                ]
                if root.is_dir()
                else []
            )
            if legacy:
                print(
                    f"  Legacy/unverified or incomplete snapshots: {len(legacy)} (not auto-selected)"
                )
            for diagnostic in diagnostics:
                print(f"  WARNING: {diagnostic['reason']}")
        return 0
    if args.command == "inspect-delinquency-file":
        try:
            inspection = inspect_delinquency_file(args.file)
        except DelinquencyFileError as exc:
            LOGGER.error("%s", exc)
            return 2
        print(f"File type: {inspection.file_type.upper()}")
        print(f"Rows: {inspection.row_count:,}")
        print("Detected columns:")
        for column in inspection.columns:
            print(f"- {column}")
        print("Potential mapping (inspection only; never auto-accepted):")
        if inspection.potential_mapping:
            for target, source in sorted(inspection.potential_mapping.items()):
                print(f"- {target} -> {source}")
        else:
            print("- none")
        for target, columns in sorted(inspection.ambiguous_suggestions.items()):
            print(f"WARNING ambiguous {target}: {', '.join(columns)}")
        print("Import requires an explicit reviewed mapping JSON file.")
        return 0
    if args.command in {"import-delinquency", "replay-delinquency"}:
        try:
            if args.command == "replay-delinquency":
                stats = replay_delinquency(
                    snapshot=args.snapshot, parcel_snapshot=args.parcel_snapshot,
                    import_snapshot=args.import_snapshot, min_acres=args.min_acres,
                    processed_root=args.output_root,
                )
            else:
                stats = import_and_join_delinquency(
                    args.file, args.mapping, args.min_acres,
                    parcel_snapshot=args.parcel_snapshot, processed_root=args.output_root,
                )
        except (DelinquencyFileError, DelinquencyPipelineError, ValueError, OSError) as exc:
            LOGGER.error("%s", exc)
            return 2
        heading = (
            "Offline Delinquency Replay" if args.command == "replay-delinquency"
            else "Authoritative Delinquency Import"
        )
        print(f"Minnesota Land Intelligence Platform - {heading}\n")
        print("County: Isanti")
        print(f"Delinquency records loaded: {stats.records_loaded:,}")
        print(f"Parcel records loaded:      {stats.parcels_loaded:,}")
        print(f"Exact normalized matches:   {stats.exact_matches:,}")
        print(f"Unmatched records:          {stats.unmatched_records:,}")
        print(f"Duplicate parcel IDs:       {stats.duplicate_parcel_ids:,}")
        print(f"Ambiguous records:          {stats.ambiguous_records:,}")
        print(f"Verified 10+ candidates:    {stats.verified_candidates:,}")
        manifest = json.loads(
            (stats.processed_snapshot_dir / "manifest.json").read_text(encoding="utf-8")
        )
        if manifest.get("prior_year_source_rows") or manifest.get("current_year_source_rows"):
            print(f"Prior-year unpaid rows:     {manifest['prior_year_source_rows']:,}")
            print(f"Overdue current-year rows:  {manifest['current_year_source_rows']:,}")
            print(
                "Current-year installments are exported separately; repeated balances are not summed."
            )
        mapping = json.loads((stats.raw_snapshot_dir / "mapping.json").read_text(encoding="utf-8"))
        if mapping.get("verification_hold_reason"):
            print(f"VERIFICATION HOLD: {mapping['verification_hold_reason']}")
        print(f"Raw snapshot: {stats.raw_snapshot_dir}")
        print(f"Processed snapshot: {stats.processed_snapshot_dir}")
        selection = manifest["selection"]
        print(f"Input selection: {selection['mode']}")
        print(f"Parcel snapshot: {selection['parcel_run_id']}")
        print(f"Import snapshot: {selection['import_run_id']}")
        print(f"Parcel captured: {selection['dates']['parcel_retrieved_at']}")
        print(f"Listing captured: {selection['dates']['delinquency_imported_at']}")
        print(f"Listing published: {selection['dates']['delinquency_publication_date'] or 'UNKNOWN'}")
        for warning in selection["dates"]["warnings"]:
            print(f"WARNING: {warning}")
        print(f"Replay comparison: {selection['comparison']}")
        print(selection["dates"]["limitation"])
        return 0
    adapter = IsantiAdapter()
    if args.command == "validate-source":
        try:
            metadata = adapter.client.metadata()
            adapter.validate_metadata(metadata)
            record_count = adapter.client.count()
        except (ValueError, ArcGISError) as exc:
            LOGGER.error("%s", exc)
            return 2
        summary = {
            "name": metadata.get("name"),
            "geometryType": metadata.get("geometryType"),
            "spatialReference": metadata.get("spatialReference"),
            "maxRecordCount": metadata.get("maxRecordCount"),
            "supportsPagination": metadata.get("advancedQueryCapabilities", {}).get(
                "supportsPagination"
            ),
            "recordCount": record_count,
            "taxSemanticsVerified": False,
            "taxWarning": "TOTPRVTXTOD means Total Previous Taxes Owed; delinquent/past-due semantics are not officially defined.",
        }
        print(json.dumps(summary, indent=2))
        return 0
    try:
        stats = run_pipeline(adapter, args.min_acres)
    except (ValueError, ArcGISError, OSError) as exc:
        LOGGER.error("%s", exc)
        return 2
    print("Minnesota Land Intelligence Platform\n")
    print("County: Isanti")
    print(f"Records retrieved:       {stats.retrieved:,}")
    print(f"Records normalized:      {stats.normalized:,}")
    print(f"Normalization errors:    {stats.normalization_errors:,}")
    for reason, count in sorted(stats.rejected.items()):
        print(f"Rejected ({reason}): {count:,}")
    print(f"Candidates accepted:     {stats.candidates:,}")
    print(f"Tax-semantics review:    {stats.tax_semantics_review_records:,}")
    print(
        "\nWARNING: Past-due tax semantics are unverified; strict candidate classification is disabled."
    )
    print(f"Raw run: {stats.raw_run_dir}")
    print("Output:")
    for path in stats.output_paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
