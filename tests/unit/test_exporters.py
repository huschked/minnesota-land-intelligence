import csv
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from mn_land.counties.isanti.adapter import IsantiAdapter
from mn_land.export.exporters import export_tax_semantics_review_sample


def test_tax_semantics_sample_is_explicitly_not_a_candidate(tmp_path: Path) -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "isanti_parcel.json"
    raw = json.loads(fixture.read_text(encoding="utf-8"))
    parcel = IsantiAdapter(client=object()).normalize_parcel(raw, datetime.now(UTC))

    path, count = export_tax_semantics_review_sample([parcel], tmp_path, Decimal(10))

    row = next(csv.DictReader(path.open(encoding="utf-8")))
    assert count == 1
    assert row["source_previous_taxes_owed"] == "5000.01"
    assert row["review_status"] == "NOT A CANDIDATE - tax semantics unverified"
