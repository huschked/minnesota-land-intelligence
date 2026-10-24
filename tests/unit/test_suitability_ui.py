"""Optional explicit suitability selection, held states, stale callback revocation."""
import json
from pathlib import Path
from queue import SimpleQueue
from threading import Event

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest
from test_enrichment import payload

from mn_land.config import settings
from mn_land.config.settings import Settings
from mn_land.runs import RunValidationError
from mn_land.suitability_service import SuitabilityObservation, SuitabilityService
from mn_land.ui.suitability import SuitabilityDownload
from mn_land.worklists import canonical

pytestmark = pytest.mark.ui
APP = Path(__file__).parents[2]/"src/mn_land/ui/app.py"


@pytest.fixture
def suitability_app(viewer_data, monkeypatch):
    def make(held=False, assessed=True):
        feature = json.loads((Path(__file__).parents[1]/"fixtures/isanti_parcel.json").read_text())
        feature["attributes"]["IMPRVALUE"] = 0
        root, _, review = viewer_data(features=[feature])
        doc = payload(held=held)
        if not assessed: doc["records"] = []
        observation = SuitabilityObservation("synthetic-gis", "a"*64, canonical(doc))
        calls = []
        monkeypatch.setattr(settings, "SETTINGS", Settings(processed_dir=root))
        monkeypatch.setattr(SuitabilityService, "catalog", lambda self: ("synthetic-gis",))
        def load(self, *args, **kwargs):
            calls.append("load")
            return observation
        monkeypatch.setattr(SuitabilityService, "load", load)
        at = AppTest.from_file(str(APP), default_timeout=30).run()
        at.selectbox(key="snapshot_choice").select("review/"+review.name).run()
        at.button(key="load").click().run()
        assert not at.exception
        return at, observation, calls
    return make


def test_no_implicit_load_explicit_columns_details_and_memory_only_filters(suitability_app):
    at, _, calls = suitability_app()
    assert not calls and at.session_state["suit_loaded"] is None
    assert "Suitability status" not in at.dataframe[0].value
    at.selectbox(key="suit_choice").select("synthetic-gis").run()
    assert not calls
    at.button(key="suit_load").click().run()
    assert not at.exception and calls == ["load"]
    assert at.dataframe[0].value["Estimated remaining acres"].iloc[0] == 25.5
    at.text_input(key="table_search").set_value("02.001").run()
    assert calls == ["load"]
    at.selectbox(key="parcel_choice").select("02.001.0200").run()
    at.button(key="open_summary").click().run()
    assert not at.exception
    assert any("estimated_remaining_acres: 25.5" in t.value for t in at.text)


@pytest.mark.parametrize("held,assessed,status", [(True, True, "held"), (False, False, "not_assessed")])
def test_held_and_not_assessed_never_render_as_zero(suitability_app, held, assessed, status):
    at, _, _ = suitability_app(held, assessed)
    at.selectbox(key="suit_choice").select("synthetic-gis").run()
    at.button(key="suit_load").click().run()
    assert not at.exception
    table = at.dataframe[0].value
    assert table["Suitability status"].iloc[0] == status
    assert table["Estimated remaining acres"].isna().all()


def test_preview_download_revalidates_and_filter_reload_revoke(suitability_app):
    at, _, calls = suitability_app()
    at.selectbox(key="suit_choice").select("synthetic-gis").run()
    at.button(key="suit_load").click().run()
    at.button(key="suit_preview_button").click().run()
    assert not at.exception
    preview = at.session_state["suit_preview"]
    job = SuitabilityDownload(SuitabilityService(settings.SETTINGS.processed_dir), preview,
                              "json", at.session_state["suit_revoked"], SimpleQueue())
    assert json.loads(job())["records"][0]["parcel_id"] == "020010200"
    assert calls == ["load", "load", "load"]
    at.text_input(key="table_search").set_value("no results").run()
    assert not at.exception and job.revoked.is_set()
    with pytest.raises(RunValidationError): job()
    at.button(key="reload").click().run()
    assert not at.exception and at.session_state["suit_loaded"] is None


def test_failed_new_load_removes_stale_metrics_and_keeps_base(suitability_app, monkeypatch):
    at, _, _ = suitability_app()
    at.selectbox(key="suit_choice").select("synthetic-gis").run()
    at.button(key="suit_load").click().run()
    def fail(*args, **kwargs): raise RunValidationError("Changed synthetic publication")
    monkeypatch.setattr(SuitabilityService, "load", fail)
    at.button(key="suit_load").click().run()
    assert not at.exception
    assert at.session_state["suit_loaded"] is None
    assert at.session_state["parcels"] is not None
    assert "Suitability status" not in at.dataframe[0].value
    assert any("Changed synthetic" in e.value for e in at.error)


def test_revoked_deferred_job_does_not_call_service():
    event = Event()
    event.set()
    job = SuitabilityDownload(None, None, "csv", event, SimpleQueue())
    with pytest.raises(RunValidationError): job()
