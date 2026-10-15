from __future__ import annotations

import argparse
import json
import logging
from decimal import Decimal, InvalidOperation
from pathlib import Path

from mn_land.config.settings import SETTINGS
from mn_land.counties.isanti import IsantiAdapter
from mn_land.delinquency.file_loader import DelinquencyFileError, inspect_delinquency_file
from mn_land.delinquency.pipeline import (
    DelinquencyPipelineError,
    import_and_join_delinquency,
)
from mn_land.ingestion.pipeline import run_pipeline

LOGGER = logging.getLogger(__name__)


def decimal_argument(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mn-land", description="Minnesota Land Intelligence Platform")
    sub = parser.add_subparsers(dest="command", required=True)
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
        "--min-acres", type=decimal_argument, default=Decimal(SETTINGS.default_min_acres)
    )
    review_command = sub.add_parser("review-delinquency")
    review_command.add_argument("--county", choices=("isanti",), required=True)
    review_command.add_argument("--snapshot", type=Path, required=True)
    review_command.add_argument("--min-acres", type=decimal_argument, default=Decimal(10))
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    if args.command == "review-delinquency":
        from mn_land.counties.isanti.review import build_review

        output = build_review(args.snapshot, args.min_acres)
        print(f"Review artifacts: {output}")
        print((output / "summary.json").read_text(encoding="utf-8"))
        return 0
    if args.command == "status":
        parcel_root = SETTINGS.raw_dir / "isanti"
        parcel_ready = parcel_root.is_dir() and any(
            path.is_dir() and (path / "manifest.json").is_file()
            for path in parcel_root.iterdir()
            if path.name != "delinquency"
        )
        delinquency_root = parcel_root / "delinquency"
        imported = delinquency_root.is_dir() and any(
            path.is_dir() and (path / "manifest.json").is_file()
            for path in delinquency_root.iterdir()
        )
        print(f"Parcel ingestion: {'READY' if parcel_ready else 'NO PARCEL SNAPSHOT'}")
        print("Delinquency ingestion: READY")
        print(
            "Authoritative Isanti delinquency source: "
            f"{'IMPORTED' if imported else 'NOT YET IMPORTED'}"
        )
        processed = SETTINGS.processed_dir / "isanti" / "delinquency"
        manifests = sorted(processed.glob("*/manifest.json")) if processed.is_dir() else []
        if manifests:
            latest = json.loads(manifests[-1].read_text(encoding="utf-8"))
            print(f"Verified candidates: {latest['verified_candidates']}")
            if latest.get("unverified_matches"):
                print("Verification: HOLD - source requires reconciliation with county records")
        else:
            print("Verified candidates: NOT GENERATED")
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
    if args.command == "import-delinquency":
        try:
            stats = import_and_join_delinquency(args.file, args.mapping, args.min_acres)
        except (DelinquencyFileError, DelinquencyPipelineError) as exc:
            LOGGER.error("%s", exc)
            return 2
        print("Minnesota Land Intelligence Platform - Authoritative Delinquency Import\n")
        print("County: Isanti")
        print(f"Delinquency records loaded: {stats.records_loaded:,}")
        print(f"Parcel records loaded:      {stats.parcels_loaded:,}")
        print(f"Exact normalized matches:   {stats.exact_matches:,}")
        print(f"Unmatched records:          {stats.unmatched_records:,}")
        print(f"Duplicate parcel IDs:       {stats.duplicate_parcel_ids:,}")
        print(f"Ambiguous records:          {stats.ambiguous_records:,}")
        print(f"Verified 10+ candidates:    {stats.verified_candidates:,}")
        manifest = json.loads((stats.processed_snapshot_dir / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("prior_year_source_rows") or manifest.get("current_year_source_rows"):
            print(f"Prior-year unpaid rows:     {manifest['prior_year_source_rows']:,}")
            print(f"Overdue current-year rows:  {manifest['current_year_source_rows']:,}")
            print("Current-year installments are exported separately; repeated balances are not summed.")
        mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
        if mapping.get("verification_hold_reason"):
            print(f"VERIFICATION HOLD: {mapping['verification_hold_reason']}")
        print(f"Raw snapshot: {stats.raw_snapshot_dir}")
        print(f"Processed snapshot: {stats.processed_snapshot_dir}")
        return 0
    adapter = IsantiAdapter()
    if args.command == "validate-source":
        metadata = adapter.client.metadata()
        summary = {
            "name": metadata.get("name"),
            "geometryType": metadata.get("geometryType"),
            "spatialReference": metadata.get("spatialReference"),
            "maxRecordCount": metadata.get("maxRecordCount"),
            "supportsPagination": metadata.get("advancedQueryCapabilities", {}).get("supportsPagination"),
            "recordCount": adapter.client.count(),
            "taxSemanticsVerified": False,
            "taxWarning": "TOTPRVTXTOD means Total Previous Taxes Owed; delinquent/past-due semantics are not officially defined.",
        }
        print(json.dumps(summary, indent=2))
        return 0
    stats = run_pipeline(adapter, args.min_acres)
    print("Minnesota Land Intelligence Platform\n")
    print("County: Isanti")
    print(f"Records retrieved:       {stats.retrieved:,}")
    print(f"Records normalized:      {stats.normalized:,}")
    print(f"Normalization errors:    {stats.normalization_errors:,}")
    for reason, count in sorted(stats.rejected.items()):
        print(f"Rejected ({reason}): {count:,}")
    print(f"Candidates accepted:     {stats.candidates:,}")
    print(f"Tax-semantics review:    {stats.tax_semantics_review_records:,}")
    print("\nWARNING: Past-due tax semantics are unverified; strict candidate classification is disabled.")
    print(f"Raw run: {stats.raw_run_dir}")
    print("Output:")
    for path in stats.output_paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
