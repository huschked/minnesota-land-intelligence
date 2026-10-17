"""ML-203 keyboard controls and state transitions; not a browser/a11y audit."""

import json
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
import streamlit as st
from streamlit.testing.v1 import AppTest

from mn_land.config import settings
from mn_land.config.settings import Settings
from mn_land.review_service import ReviewService

pytestmark = pytest.mark.ui
APP = Path(__file__).parents[2] / "src/mn_land/ui/app.py"
FIXTURE = Path(__file__).parents[1] / "fixtures/isanti_parcel.json"


def feature(index=200, *, acres=25.5, improvement=0, classification="Other", owner="Example Owner"):
    row = json.loads(FIXTURE.read_text(encoding="utf-8"))
    row["attributes"].update(
        OBJECTID=index,
        PARCELID=f"02.001.{index:04d}",
        DEEDEDACRES=acres,
        IMPRVALUE=improvement,
        PRIMARYCLASS=classification,
        OWNERNME1=owner,
    )
    return row


@pytest.fixture
def browser(monkeypatch, viewer_data):
    def make(**kwargs):
        kwargs.setdefault("features", [feature()])
        root, joined, review = viewer_data(**kwargs)
        monkeypatch.setattr(settings, "SETTINGS", Settings(processed_dir=root))
        at = AppTest.from_file(str(APP), default_timeout=30).run()
        at.selectbox(key="snapshot_choice").select(f"review/{review.name}").run()
        at.button(key="load").click().run()
        assert not at.exception
        return at, root, joined, review

    return make


def texts(at):
    return [item.value for item in at.text]


def test_default_dynamic_views_exact_display_allowlist_and_export_controls(browser):
    st.set_option("client.disableDataExport", False)
    at, _, _, review = browser()
    assert at.selectbox(key="table_view").value == "focused"
    assert "Filtered view: 1 distinct parcels" in texts(at)
    assert "Prior or current (distinct parcels): 1" in texts(at)
    assert "Both prior and current: 1" in texts(at)
    table = at.dataframe[0]
    assert list(table.value.columns) == [
        "Parcel ID",
        "Deeded acres",
        "Classification",
        "Improvement value",
        "Tax periods (dated listing)",
        "GIS owner",
    ]
    assert table.value.iloc[0]["Parcel ID"] == "02.001.0200"
    assert table.value.iloc[0]["Improvement value"] == "0"
    assert st.get_option("client.disableDataExport") is True
    assert table.proto.selection_mode == [table.proto.SINGLE_COLUMN]
    assert table.proto.alt
    assert not at.get("download_button")
    assert not at.html
    assert at.session_state["loaded"].key.run_id == review.name


def test_keyboard_open_sort_page_back_and_pure_reruns_preserve_identity(browser, monkeypatch):
    features = [feature(i, acres=10 + (i % 20)) for i in range(200, 227)]
    rows = [f"02001{i:04d},Synthetic,2024,2025,100" for i in range(200, 227)]
    at, _, _, review = browser(features=features, rows=rows)
    assert len(at.dataframe[0].value) == 25
    at.selectbox(key="parcel_choice").select("02.001.0226").run()
    at.button(key="open_summary").click().run()
    identity = at.session_state["open_parcel"]
    assert identity.parcel_id == "02.001.0226"  # not on first grid page
    assert identity.snapshot_token == f"review/{review.name}"

    def no_disk(*args, **kwargs):
        pytest.fail("Filtering, sorting or selection attempted a disk-backed load")

    monkeypatch.setattr(ReviewService, "load", no_disk)
    monkeypatch.setattr(ReviewService, "load_parcels", no_disk)
    monkeypatch.setattr(ReviewService, "catalog", no_disk)
    at.selectbox(key="table_sort").select("deeded_acres").run()
    at.toggle(key="table_desc").set_value(True).run()
    assert at.session_state["open_parcel"] == identity
    at.number_input(key="table_page").set_value(2).run()
    assert len(at.dataframe[0].value) == 2
    assert at.session_state["open_parcel"] == identity
    at.button(key="back_results").click().run()
    assert at.session_state["open_parcel"] is None
    assert at.session_state["parcel_choice"] == "02.001.0226"
    assert at.selectbox(key="table_sort").value == "deeded_acres"
    assert at.number_input(key="table_page").value == 2
    at.run()
    assert not at.exception


def test_filtering_out_selection_clears_it_and_invalid_floor_never_shows_old_table(browser):
    at, _, _, _ = browser()
    at.selectbox(key="parcel_choice").select("02.001.0200").run()
    at.button(key="open_summary").click().run()
    at.text_input(key="table_search").set_value("no match").run()
    assert at.session_state["open_parcel"] is None
    assert at.session_state["parcel_choice"] is None
    assert any("selection was cleared" in item.value for item in at.info)
    assert not at.dataframe
    assert at.button(key="open_summary").disabled
    at.button(key="clear_table").click().run()
    assert len(at.dataframe[0].value) == 1
    assert at.text_input(key="table_min").value == "10"
    at.text_input(key="table_min").set_value("9.99").run()
    assert any("loaded candidate floor" in item.value for item in at.error)
    assert not at.dataframe
    assert not at.exception


def test_current_category_classification_unknown_and_improvement_controls(browser):
    at, _, _, _ = browser(features=[feature(improvement=None, classification=None, owner=None)])
    assert not at.dataframe  # unknown is not silently land-focused
    at.selectbox(key="table_view").select("current").run()
    at.selectbox(key="table_improvement").select("unknown").run()
    at.multiselect(key="table_class").select(0).run()  # explicit unknown classification
    assert len(at.dataframe[0].value) == 1
    assert at.dataframe[0].value.iloc[0]["Improvement value"] is None
    at.selectbox(key="table_improvement").select("zero").run()
    assert not at.dataframe
    assert not at.exception


def test_reload_preserves_filters_but_new_loaded_snapshot_resets_them(browser, viewer_data):
    at, _, _, review = browser()
    at.text_input(key="table_search").set_value("Example").run()
    at.selectbox(key="parcel_choice").select("02.001.0200").run()
    at.button(key="open_summary").click().run()
    identity = at.session_state["open_parcel"]
    at.button(key="reload").click().run()
    assert at.session_state["open_parcel"] == identity
    assert at.text_input(key="table_search").value == "Example"
    _, _, newer = viewer_data(features=[feature()])
    at.button(key="reload").click().run()
    at.selectbox(key="snapshot_choice").select(f"review/{newer.name}").run()
    assert at.session_state["loaded"].key.run_id == review.name
    at.button(key="load").click().run()
    assert at.session_state["loaded"].key.run_id == newer.name
    assert not at.text_input(key="table_search").value
    assert at.session_state["open_parcel"] is None
    assert at.session_state["parcel_choice"] is None
    assert not at.exception


def test_literal_source_text_not_markup_or_links_in_grid_and_summary(browser):
    owner = "<script>alert(1)</script> ![x](https://example.test/private) =1+1"
    at, _, _, _ = browser(features=[feature(owner=owner)])
    assert at.dataframe[0].value.iloc[0]["GIS owner"] == owner
    at.selectbox(key="parcel_choice").select("02.001.0200").run()
    at.button(key="open_summary").click().run()
    assert f"GIS owner: {owner}" in texts(at)
    assert not at.html and not at.get("image")
    assert not at.link_button
    assert not at.exception
