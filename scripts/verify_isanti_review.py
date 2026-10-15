"""Preserve official reports and REST responses for a selected review sample.

Run using the bundled Python runtime with pypdf installed. This collects
evidence; extraction success is not a declaration that all fields were verified.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from pypdf import PdfReader
from pypdf.errors import PdfReadError


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-dir", type=Path, required=True)
    args = parser.parse_args()
    now = datetime.now(UTC)
    root = Path(__file__).resolve().parents[1]
    output = root / "data/raw/isanti/verification" / now.strftime("%Y-%m-%dT%H%M%S%fZ")
    output.mkdir(parents=True, exist_ok=False)
    with (args.review_dir / "isanti_county_verification_worklist.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        worklist = list(csv.DictReader(handle))
    results = []
    for row in worklist:
        parcel_id = row["parcel_id"]
        url = row["parcel_report_url"]
        evidence = {"parcel_id": parcel_id, "url": url, "retrieved_at": now.isoformat()}
        try:
            with urlopen(url, timeout=30) as response:
                data = response.read()
            if not data.startswith(b"%PDF"):
                raise ValueError("official endpoint did not return a PDF")
            path = output / f"{parcel_id}.pdf"
            path.write_bytes(data)
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            (output / f"{parcel_id}.txt").write_text(text, encoding="utf-8")
            evidence.update({
                "status": "retrieved_not_yet_compared",
                "sha256": hashlib.sha256(data).hexdigest(),
                "pages": len(reader.pages),
                "pdf_path": str(path),
                "contains_parcel_id": parcel_id in text,
            })
        except (OSError, ValueError, PdfReadError) as exc:
            evidence.update({"status": "retrieval_failed", "error": str(exc)})
        results.append(evidence)
        print(parcel_id, evidence["status"], flush=True)
        time.sleep(0.25)

    base = "https://gis.co.isanti.mn.us/arcgis/rest/services/LandRecords/TaxParcels_Public"
    missing = ["050080500", "130240105", "066090010", "126090010", "136090010"]
    # Exact county-supported formatted IDs. No fuzzy identity matching.
    formatted = [f"{pin[:2]}.{pin[2:5]}.{pin[5:]}" for pin in missing]
    where = "PARCELID IN (" + ",".join(f"'{pin}'" for pin in formatted) + ")"
    diagnostics = []
    for suffix in ("FeatureServer/0", "FeatureServer/1", "MapServer/2", "MapServer/3"):
        url = f"{base}/{suffix}"
        diagnostic = {"layer_url": url, "where": where}
        try:
            with urlopen(url + "?f=json", timeout=30) as response:
                metadata = json.load(response)
            (output / (suffix.replace("/", "_") + "_metadata.json")).write_text(
                json.dumps(metadata, indent=2), encoding="utf-8"
            )
            if not any(field["name"] == "PARCELID" for field in metadata.get("fields", [])):
                raise ValueError("layer has no PARCELID field")
            params = {"f": "json", "where": where, "outFields": "*", "returnGeometry": "false"}
            with urlopen(url + "/query?" + urlencode(params), timeout=30) as response:
                payload = json.load(response)
            if "error" in payload:
                raise ValueError(str(payload["error"]))
            (output / (suffix.replace("/", "_") + "_unmatched_query.json")).write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
            diagnostic.update({
                "status": "queried", "layer_name": metadata.get("name"),
                "feature_count": len(payload.get("features", [])),
            })
        except (OSError, ValueError) as exc:
            diagnostic.update({"status": "failed", "error": str(exc)})
        diagnostics.append(diagnostic)
        time.sleep(0.25)
    manifest = {
        "review_dir": str(args.review_dir.resolve()),
        "retrieved_at": now.isoformat(), "reports": results,
        "unmatched_identity_diagnostics": diagnostics,
        "manual_comparison_status": "pending",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Evidence directory:", output)


if __name__ == "__main__":
    main()
