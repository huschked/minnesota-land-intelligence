"""Report current ingestion edge cases using synthetic inputs, not live services.

Discovery evidence for ML-119, not production validation or permanent regression
expectations. Results should change as ML-125 through ML-127 are implemented.
Only a uniquely owned, ignored temporary directory is created and removed.
"""

from __future__ import annotations

import json
import tempfile
from argparse import ArgumentTypeError
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from openpyxl import Workbook

from mn_land.cli import decimal_argument
from mn_land.counties.isanti import IsantiAdapter
from mn_land.counties.isanti.adapter import parse_decimal
from mn_land.counties.isanti.delinquency import normalize_parcel_id
from mn_land.delinquency.file_loader import (
    DelinquencyMapping,
    FileDelinquencySource,
    parse_money,
    read_tabular_file,
)
from mn_land.delinquency.pipeline import load_latest_parcel_snapshot
from mn_land.ingestion.arcgis import ArcGISClient
from mn_land.utils.http import UrllibJsonTransport

ROOT = Path(__file__).resolve().parents[1]


def observe(function: Callable[[], object]) -> dict[str, object]:
    try:
        return {"outcome": "accepted", "value": function()}
    except (ValueError, TypeError, RuntimeError, AttributeError, ArgumentTypeError) as exc:
        return {"outcome": "rejected", "error_type": type(exc).__name__, "reason": str(exc)}


def main() -> None:
    findings: dict[str, object] = {
        "money_NaN": observe(lambda: str(parse_money("NaN"))),
        "GIS_Infinity": observe(lambda: str(parse_decimal("Infinity"))),
        "CLI_Infinity": observe(lambda: str(decimal_argument("Infinity"))),
        "numeric_identifier_123_point_5": observe(lambda: normalize_parcel_id(123.5)),
    }
    with tempfile.TemporaryDirectory(prefix=".test-tmp-ml119-", dir=ROOT) as temporary:
        directory = Path(temporary)
        mapping = DelinquencyMapping.from_json(
            ROOT / "tests/fixtures/isanti_delinquency_mapping.json"
        )
        invalid_mapping = directory / "mapping.json"
        invalid_mapping.write_text("[]", encoding="utf-8")
        try:
            DelinquencyMapping.from_json(invalid_mapping)
        except (AttributeError, ValueError) as exc:
            findings["mapping_array_error"] = type(exc).__name__

        csv_path = directory / "width.csv"
        csv_path.write_text("PARID,OWN1\n020010200,Example,extra\n", encoding="utf-8")
        findings["extra_CSV_fields"] = observe(lambda: sorted(read_tabular_file(csv_path)[1][0]))
        csv_path.write_text("PARID,OWN1\n020010200\n", encoding="utf-8")
        findings["short_CSV_row"] = observe(
            lambda: read_tabular_file(csv_path)[1][0]["OWN1"] is None
        )

        formula_path = directory / "formula.xlsx"
        workbook = Workbook()
        workbook.active.append(["Parcel ID", "Taxpayer", "Delinquent Year", "Taxes/Penalties"])
        workbook.active.append(["02-001-0200", "Synthetic", 2025, "=100+25"])
        workbook.save(formula_path)
        workbook.close()
        formula_mapping = DelinquencyMapping(
            mapping.source_agency,
            mapping.dataset,
            {
                k: v
                for k, v in mapping.columns.items()
                if k not in {"owner_name", "mailing_address"}
            },
            mapping.delinquency_assertion,
        )
        findings["uncached_formula"] = observe(
            lambda: (
                FileDelinquencySource(formula_path, formula_mapping)
                .load_records()[0]
                .total_taxes_and_penalties_due
                is None
            )
        )

        year_path = directory / "years.xlsx"
        workbook = Workbook()
        workbook.active.append(["PARID", "OWN1", "ASMTYR", "TAXYR"])
        workbook.active.append(["020010200", "Synthetic", 2024, 2025])
        workbook.save(year_path)
        workbook.close()
        mixed_mapping = DelinquencyMapping.from_json(
            ROOT / "docs/counties/isanti-delinquency-2026-10-13.mapping.json"
        )
        findings["mixed_XLSX_numeric_years"] = observe(
            lambda: (
                FileDelinquencySource(year_path, mixed_mapping).load_records()[0].taxes_payable_year
            )
        )

        class Transport:
            requested_page_size: object = None

            def get_json(self, url: str, params: dict) -> dict:
                if not url.endswith("/query"):
                    return {
                        "id": 0,
                        "name": "Synthetic",
                        "objectIdField": "OBJECTID",
                        "maxRecordCount": 1,
                        "capabilities": "Query",
                        "advancedQueryCapabilities": {
                            "supportsPagination": True,
                            "supportsOrderBy": True,
                        },
                        "fields": [
                            {"name": "OBJECTID", "type": "esriFieldTypeOID", "nullable": False},
                            {"name": "PARCELID", "type": "esriFieldTypeString"},
                        ],
                    }
                if params.get("returnCountOnly"):
                    return {"count": 1}
                if params.get("returnIdsOnly"):
                    return {"objectIdFieldName": "OBJECTID", "objectIds": [1]}
                self.requested_page_size = params["resultRecordCount"]
                return {"features": [{"attributes": {"PARCELID": "020010200"}}]}

        transport = Transport()
        client = ArcGISClient(
            "https://example.test/FeatureServer", 0, page_size=2, transport=transport
        )
        findings["missing_first_OBJECTID"] = observe(
            lambda: list(
                client.fetch_all(
                    out_fields=("OBJECTID", "PARCELID"),
                    raw_run_dir=directory / "GIS",
                    retrieved_at=datetime.now(UTC),
                )
            )
        )
        findings["requested_page_size_with_advertised_limit_1"] = transport.requested_page_size

        latest = directory / "snapshots" / "latest"
        latest.mkdir(parents=True)
        (latest / "manifest.json").write_text(
            json.dumps({"retrieved_at": "2026-10-14T00:00:00+00:00"}),
            encoding="utf-8",
        )
        parcels, _, _ = load_latest_parcel_snapshot(IsantiAdapter(client=object()), latest.parent)
        findings["manifest_only_snapshot_loaded_as_empty"] = len(parcels) == 0

        for status in (404, 429):

            def failure(*args, status=status, **kwargs):
                return_error = HTTPError(
                    "https://example.test", status, "Synthetic", {"Retry-After": "30"}, None
                )
                raise return_error

            with (
                patch("mn_land.utils.http.urlopen", side_effect=failure) as request,
                patch("mn_land.utils.http.time.sleep") as sleep,
            ):
                try:
                    UrllibJsonTransport().get_json("https://example.test", {})
                except RuntimeError:
                    findings[f"HTTP_{status}_attempts"] = request.call_count
                    findings[f"HTTP_{status}_waits"] = [
                        call.args[0] for call in sleep.call_args_list
                    ]
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
