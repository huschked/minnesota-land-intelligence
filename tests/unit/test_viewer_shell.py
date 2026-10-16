"""Supported AppTest controls only; no claim of browser or screen-reader testing."""
import socket
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
def shell(tmp_path, monkeypatch):
    def make(root=None):
        monkeypatch.setattr(settings, "SETTINGS", Settings(processed_dir=root or tmp_path / "missing"))
        return AppTest.from_file(str(APP), default_timeout=20).run()
    return make


def choose_review(at, review):
    at.selectbox(key="snapshot_choice").select(f"review/{review.name}").run()
    at.button(key="load").click().run()
    assert not at.exception
    return at.session_state["loaded"]


def test_missing_data_is_explained_without_fake_zero_results(shell):
    at = shell()
    assert not at.exception
    assert "No eligible complete result" in at.warning[0].value
    assert at.button(key="load").disabled
    assert not at.session_state["loaded"]


def test_legacy_can_be_inspected_but_not_loaded(shell, tmp_path):
    legacy = tmp_path / "processed/isanti/delinquency/old"
    legacy.mkdir(parents=True)
    (legacy / "manifest.json").write_text("{}", encoding="utf-8")
    at = shell(tmp_path / "processed")
    at.selectbox(key="snapshot_choice").select("delinquency_processed/old").run()
    assert at.button(key="load").disabled
    assert any("never certified" in item.value for item in at.text)
    assert not at.exception


def test_explicit_load_and_pure_rerun_keep_identity_without_new_disk_reads(shell, viewer_data, monkeypatch):
    root, _, review = viewer_data()
    at = shell(root)
    assert at.session_state["loaded"] is None
    loaded = choose_review(at, review)
    assert loaded.key.run_id == review.name
    assert any("Synthetic test data" in item.value for item in at.warning)
    assert any("Combined tax/penalty balance: 1 unknown" == item.value for item in at.text)

    def prohibited(*args, **kwargs):
        pytest.fail("A pure rerun reread disk or silently replaced the selection")

    monkeypatch.setattr(ReviewService, "catalog", prohibited)
    monkeypatch.setattr(ReviewService, "load", prohibited)
    at.run()
    assert at.session_state["loaded"] == loaded
    assert not at.exception


def test_reload_lists_new_run_without_switching_loaded_identity(shell, viewer_data):
    root, _, review = viewer_data()
    at = shell(root)
    loaded = choose_review(at, review)
    _, _, newer_review = viewer_data()
    at.button(key="reload").click().run()
    assert at.session_state["loaded"].key == loaded.key
    assert at.session_state["snapshot_choice"] == loaded.key.token
    assert len(at.selectbox(key="snapshot_choice").options) == 4
    at.selectbox(key="snapshot_choice").select(f"review/{newer_review.name}").run()
    assert at.session_state["loaded"].key == loaded.key
    at.button(key="load").click().run()
    assert at.session_state["loaded"].key.run_id == newer_review.name
    assert not at.exception


def test_corruption_after_catalog_load_fails_and_clears_old_view(shell, viewer_data):
    root, _, review = viewer_data()
    at = shell(root)
    choose_review(at, review)
    (review / "summary.json").write_text("{}", encoding="utf-8")
    at.button(key="load").click().run()
    assert at.session_state["loaded"] is None
    assert at.error
    assert "nothing was refreshed" in at.error[0].value
    assert not at.exception


def test_reload_invalidates_changed_source_graph(shell, viewer_data):
    root, _, review = viewer_data()
    at = shell(root)
    choose_review(at, review)
    (review / "summary.json").unlink()
    at.button(key="reload").click().run()
    assert at.session_state["loaded"] is None
    assert at.error
    assert at.button(key="load").disabled
    assert not at.exception


def test_empty_completed_snapshot_has_distinct_success_state(shell, viewer_data):
    root, _, review = viewer_data(empty=True)
    at = shell(root)
    choose_review(at, review)
    assert any("Valid completed result with no" in item.value for item in at.info)
    assert not any("No eligible complete" in item.value for item in at.warning)


def test_source_hold_is_literal_text_not_markup(shell, viewer_data):
    root, _, review = viewer_data(held=True)
    at = shell(root)
    choose_review(at, review)
    assert any("Active source hold" in item.value for item in at.warning)
    assert any("<script>not markup</script>" in item.value for item in at.text)
    assert not at.get("html")
    assert not at.dataframe


def test_apptest_still_blocks_dns_public_and_arbitrary_loopback_connections(shell):
    at = shell()
    assert not at.exception
    with pytest.raises(pytest.fail.Exception, match="Network access is disabled"):
        socket.getaddrinfo("example.com", 443)
    for host in ("127.0.0.1", "8.8.8.8"):
        with (
            socket.socket() as connection,
            pytest.raises(pytest.fail.Exception, match="Network access is disabled"),
        ):
            connection.connect((host, 443))
