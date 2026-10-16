"""Compare preserved county reports with the explicit verification worklist."""

from __future__ import annotations

import argparse
import csv
import json
import re
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from pypdf import PdfReader

from mn_land.runs import validate_run, workspace_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    evidence = args.evidence_dir
    manifest = json.loads((evidence / "manifest.json").read_text(encoding="utf-8"))
    review_dir = Path(manifest["review_dir"])
    validate_run(review_dir, "review")
    with (review_dir / "isanti_county_verification_worklist.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        worklist = list(csv.DictReader(handle))
    findings = []
    for row in worklist:
        pdf_path = evidence / f"{row['parcel_id']}.pdf"
        reader = PdfReader(pdf_path)
        first = reader.pages[0].extract_text(extraction_mode="layout")
        second = reader.pages[1].extract_text(extraction_mode="layout")
        area = re.search(r"Area:\s+([\d,.]+) Acres", first)
        lines = [line for line in second.splitlines() if "Outstanding" in line]
        amounts = re.findall(r"\$([\d,]+\.\d{2})", lines[0]) if len(lines) == 1 else []
        headers = re.findall(r"(\d{4}) Payable", first)
        if not area or headers[:2] != ["2026", "2025"] or len(amounts) != len(headers):
            raise ValueError(f"Cannot establish year/amount alignment for {row['parcel_id']}")
        payable_years = [
            int(year) for year in row.get("taxes_payable_years", "").split(";") if year
        ]
        if not payable_years:
            raise ValueError(f"No verified taxes-payable years for {row['parcel_id']}")
        balances = {
            str(year): amounts[headers.index(str(year))].replace(",", "")
            if str(year) in headers
            else None
            for year in payable_years
        }
        result = (
            "positive_outstanding_for_listed_prior_year"
            if any(value is not None and Decimal(value) > 0 for value in balances.values())
            else "listed_year_not_in_report_window"
            if any(value is None for value in balances.values())
            else "zero_outstanding_requires_current_status_review"
        )
        findings.append(
            {
                "parcel_id": row["parcel_id"],
                "county_report_url": row["parcel_report_url"],
                "county_report_pdf": str(pdf_path.resolve()),
                "listing_source_row_number": row["source_row_number"],
                "listing_report_assessment_year": row["listed_TAXYR"],
                "listing_charge_assessment_years": row["listed_ASMTYR"],
                "listed_taxes_payable_years": ";".join(str(y) for y in payable_years),
                "listing_TOTAMT_uninterpreted": row["source_TOTAMT_uninterpreted"],
                "report_deeded_acres": area.group(1),
                "GIS_deeded_acres": row["deeded_acres"],
                "acreage_matches": Decimal(area.group(1).replace(",", ""))
                == Decimal(row["deeded_acres"]),
                "GIS_owner_text_found_in_report": (
                    "".join(row["GIS_owner_name"].split()) in "".join(first.split())
                ),
                "report_2026_outstanding_balance": amounts[0].replace(",", ""),
                "report_outstanding_by_listed_payable_year": json.dumps(balances),
                "verification_result": result,
            }
        )
    # Comparison evidence is separate from the immutable published review.
    # A later review can explicitly pin its JSON via --comparison.
    output = workspace_path(evidence / "comparison" / uuid4().hex)
    output.mkdir(parents=True, exist_ok=False)
    path = output / "isanti_official_report_comparison.csv"
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(findings[0]))
        writer.writeheader()
        writer.writerows(findings)
    with (output / "official_report_comparison.json").open("x", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "evidence_manifest": str((evidence / "manifest.json").resolve()),
                    "reports_compared": len(findings),
                    "acreage_matches": sum(row["acreage_matches"] for row in findings),
                    "positive_listed_prior_year_reports": sum(
                        row["verification_result"] == "positive_outstanding_for_listed_prior_year"
                        for row in findings
                    ),
                    "operational_status": "COUNTY_CONFIRMED_YEAR_MAPPING_SAMPLE_COMPARED",
                    "full_balance_reconciliation_complete": False,
                    "method": "Each charge assessment year is converted to taxes-payable year using county confirmation; matching report columns are compared. A year outside the report window remains unknown. No unobserved parcel status or additive balance is inferred.",
                    "findings": findings,
                },
                indent=2,
            )
            + "\n"
        )
    print(path)


if __name__ == "__main__":
    main()
