"""Full evidence UI, literal text, memory-only reruns and corruption invalidation."""

import json
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

from mn_land.config import settings
from mn_land.config.settings import Settings
from mn_land.review_service import ReviewService

pytestmark = pytest.mark.ui
APP = Path(__file__).parents[2] / "src/mn_land/ui/app.py"


@pytest.fixture
def detail_app(viewer_data, monkeypatch):
    def make(rows=None):
        feature = json.loads(
            (Path(__file__).parents[1] / "fixtures/isanti_parcel.json").read_text(encoding="utf-8")
        )
        feature["attributes"]["IMPRVALUE"] = 0
        root, _, review = viewer_data(features=[feature], rows=rows)
        monkeypatch.setattr(settings, "SETTINGS", Settings(processed_dir=root))
        at = AppTest.from_file(str(APP), default_timeout=30).run()
        at.selectbox(key="snapshot_choice").select(f"review/{review.name}").run()
        at.button(key="load").click().run()
        at.selectbox(key="parcel_choice").select("02.001.0200").run()
        assert not at.exception
        return at, review

    return make


def test_detail_years_source_owners_unknown_balances_and_no_implicit_links(detail_app):
    at, _ = detail_app()
    at.button(key="open_summary").click().run()
    assert not at.exception
    detail = at.session_state["parcel_details"]
    assert len(detail.rows) == 2
    texts = [item.value for item in at.text]
    assert "Listing owner text (OWN1): Synthetic owner" in texts
    assert "GIS owner: Example Owner" in texts
    assert any("Charge payable year: 2025" in text for text in texts)
    assert any("Charge payable year: 2026" in text for text in texts)
    assert any(
        "Recorded canonical total_taxes_and_penalties_due: Unknown" in text for text in texts
    )
    assert any("not assessed" in text for text in texts)
    assert not at.link_button and not at.html and not at.get("image")


def test_all_rows_paginate_without_new_disk_reads_and_back_keeps_filters(detail_app, monkeypatch):
    at, _ = detail_app(rows=["020010200,Synthetic owner,2024,2025,100"] * 12)
    at.button(key="open_summary").click().run()
    assert not at.exception
    detail = at.session_state["parcel_details"]
    assert len(detail.rows) == 12

    def prohibited(*args, **kwargs):
        pytest.fail("Pure detail pagination/rerun performed a new disk read")

    monkeypatch.setattr(ReviewService, "load_details", prohibited)
    monkeypatch.setattr(ReviewService, "load_parcels", prohibited)
    at.number_input(key="source_page").set_value(2).run()
    assert at.session_state["parcel_details"] == detail
    assert len([item for item in at.text if item.value.startswith("Source record:")]) == 2
    at.toggle(key="table_desc").set_value(True).run()
    assert at.session_state["parcel_details"] == detail
    at.button(key="back_results").click().run()
    assert at.session_state["parcel_details"] is None
    assert at.toggle(key="table_desc").value is True
    assert not at.exception


def test_new_detail_read_failure_clears_already_rendered_table(detail_app):
    at, review = detail_app()
    (review / "summary.json").write_text("{}", encoding="utf-8")
    at.button(key="open_summary").click().run()
    assert at.session_state["loaded"] is None
    assert at.session_state["parcel_details"] is None
    assert at.error and not at.dataframe
    assert not at.exception


def test_source_markup_is_literal_and_reload_discards_old_detail(detail_app):
    value = "<script>bad</script> ![x](https://evil.test/image) =1+1"
    at, _ = detail_app(rows=[f"020010200,{value},2024,2025,100"])
    at.button(key="open_summary").click().run()
    assert any(value in item.value for item in at.text)
    assert not at.html and not at.get("image") and not at.link_button
    at.button(key="reload").click().run()
    assert at.session_state["parcel_details"] is None
    assert any("details were cleared" in item.value for item in at.info)
    assert not at.exception
