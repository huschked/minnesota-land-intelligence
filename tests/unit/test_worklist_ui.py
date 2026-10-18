"""Explicit preview, native deferred jobs and invalidation; not browser download QA."""

import json
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

from mn_land.config import settings
from mn_land.config.settings import Settings
from mn_land.review_service import ReviewService
from mn_land.runs import RunValidationError

pytestmark = pytest.mark.ui
APP = Path(__file__).parents[2] / "src/mn_land/ui/app.py"


@pytest.fixture
def export_app(viewer_data, monkeypatch):
    import streamlit as st

    jobs = {}
    original = st.download_button

    def capture(label, data, **kwargs):
        assert callable(data)  # never hand a stale cached blob to the browser
        jobs[data.format] = data
        return original(label, data, **kwargs)

    monkeypatch.setattr(st, "download_button", capture)

    def make(held=False):
        root, _, review = viewer_data(held=held)
        monkeypatch.setattr(settings, "SETTINGS", Settings(processed_dir=root))
        at = AppTest.from_file(str(APP), default_timeout=30).run()
        at.selectbox(key="snapshot_choice").select(f"review/{review.name}").run()
        at.button(key="load").click().run()
        at.selectbox(key="table_view").select("either").run()
        assert not at.exception and not at.download_button
        return at, review, jobs

    return make


def test_preview_context_deferred_download_and_pure_reruns(export_app, monkeypatch):
    at, _, jobs = export_app()
    at.button(key="preview_export").click().run()
    assert not at.exception and len(at.download_button) == 2
    assert any("Candidate parcels to export: 1" == item.value for item in at.text)
    assert any("prefixed with an apostrophe" in item.value for item in at.text)
    data = json.loads(jobs["json"]())
    assert len(data["candidates"]) == 1 and data["issues"]
    preview = at.session_state["export_preview"]

    def prohibited(*args, **kwargs):
        pytest.fail("Pure export rerun performed a new disk read")

    monkeypatch.setattr(ReviewService, "prepare_export", prohibited)
    at.number_input(key="issue_page").set_value(1).run()
    at.button(key="export_status").click().run()
    assert at.session_state["export_preview"] is preview
    assert not at.exception


def test_filter_sort_scope_selection_and_reload_revoke_old_downloads(export_app):
    at, _, jobs = export_app()
    at.button(key="preview_export").click().run()
    previous = jobs["json"]
    at.toggle(key="table_desc").set_value(True).run()
    assert at.session_state["export_preview"] is None and not at.download_button
    with pytest.raises(RunValidationError, match="expired"):
        previous()
    at.selectbox(key="export_scope").select("selected").run()
    assert at.button(key="preview_export").disabled
    at.selectbox(key="parcel_choice").select("02.001.0200").run()
    at.button(key="preview_export").click().run()
    assert not at.exception
    assert at.session_state["export_preview"].scope == "selected"
    latest = jobs["csv"]
    at.button(key="reload").click().run()
    assert at.session_state["export_preview"] is None
    with pytest.raises(RunValidationError):
        latest()
    assert not at.exception


def test_changed_evidence_download_refused_then_visible_status_clears_stale_table(export_app):
    at, review, jobs = export_app()
    at.button(key="preview_export").click().run()
    (review / "summary.json").write_text("{}", encoding="utf-8")
    with pytest.raises(RunValidationError, match="Download refused"):
        jobs["json"]()
    at.button(key="export_status").click().run()
    assert at.error and not at.dataframe and not at.download_button
    assert at.session_state["loaded"] is None
    assert not at.exception


def test_failed_preview_clears_old_table_and_held_preview_keeps_issues(export_app):
    at, review, _ = export_app()
    (review / "summary.json").write_text("{}", encoding="utf-8")
    at.button(key="preview_export").click().run()
    assert at.error and not at.dataframe and not at.exception
    # A second fixture instance has a fresh independent graph/session.
    at, _, jobs = export_app(held=True)
    at.button(key="preview_export").click().run()
    assert not at.exception and at.download_button
    data = json.loads(jobs["json"]())
    assert not data["candidates"] and data["issues"] and data["context"]["holds"]


def test_replaced_identical_preview_ignores_old_job_errors_and_inflight_revocation(monkeypatch):
    from queue import SimpleQueue
    from threading import Event
    from types import SimpleNamespace

    from mn_land.ui import worklists

    old, active = Event(), Event()
    errors = SimpleQueue()
    errors.put((old, "expired old job with the same content fingerprint"))
    state = SimpleNamespace(export_errors=errors, export_revoked=active)
    monkeypatch.setattr(worklists.st, "session_state", state)
    assert worklists.check_export_errors() is None
    errors.put((active, "current evidence changed"))
    assert worklists.check_export_errors() == "current evidence changed"

    def finish_then_revoke(*args):
        active.set()
        return b"must not be returned"

    service = SimpleNamespace(download_export=finish_then_revoke)
    job = worklists.DownloadJob(service, SimpleNamespace(), "json", active, errors)
    with pytest.raises(RunValidationError, match="during download"):
        job()
