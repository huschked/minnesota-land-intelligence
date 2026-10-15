"""F01/F08: strict reviewed mappings and contained evidence references."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from mn_land.config.input_limits import InputLimits
from mn_land.delinquency.file_loader import DelinquencyFileError, DelinquencyMapping

FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.fixture
def payload() -> dict:
    return json.loads((FIXTURES / "isanti_delinquency_mapping.json").read_text(encoding="utf-8"))


def load(tmp_path: Path, payload: object) -> DelinquencyMapping:
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return DelinquencyMapping.from_json(path)


@pytest.mark.parametrize("root", [[], None, True, "mapping", 12])
def test_F01_nonobject_mapping_fails(tmp_path, root) -> None:
    with pytest.raises(DelinquencyFileError, match="root"):
        load(tmp_path, root)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("source_agency", []),
        ("source_agency", "Other County"),
        ("source_agency", "Isanti Countyevil"),
        ("dataset", 123),
        ("dataset", "  "),
        ("delinquency_assertion", True),
        ("delinquency_assertion", "guess"),
        ("columns", []),
        ("columns", {"owner_name": "Owner"}),
        ("columns", {"parcel_id": 42}),
        ("columns", {"parcel_id": " "}),
        ("columns", {"parcel_id": "PARID", "owner_name": "PARID"}),
        ("columns", {"parcel_id": "PARID", "guess": "A"}),
        ("source_url", 42),
        ("source_url", "file:///secret"),
        ("source_url", "https://"),
        ("source_url", "https://user:password@example.test"),
        ("source_url", "https://example.test:bad"),
        ("source_url", "https://example.test/a b"),
        ("publication_date", "2026-02-30"),
        ("publication_date", "20261014"),
        ("publication_date", False),
        ("verification_hold_reason", " "),
        ("tax_year_convention", "invented"),
        ("supporting_documents", "note.md"),
        ("supporting_documents", [1]),
        ("review_notes", "text"),
        ("review_notes", [False]),
        ("assertion_typo", "ignored"),
    ],
)
def test_F01_invalid_mapping_members_fail(tmp_path, payload, key, value) -> None:
    payload[key] = value
    with pytest.raises(DelinquencyFileError):
        load(tmp_path, payload)


@pytest.mark.parametrize(
    "body", ["{", '{"dataset":"a","dataset":"b"}', '{"columns":{"parcel_id":"A","parcel_id":"B"}}']
)
def test_F01_invalid_or_duplicate_JSON_keys(tmp_path, body) -> None:
    path = tmp_path / "mapping.json"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(DelinquencyFileError):
        DelinquencyMapping.from_json(path)


@pytest.mark.parametrize(
    "missing", ["source_agency", "dataset", "columns", "delinquency_assertion"]
)
def test_F01_missing_required_metadata(tmp_path, payload, missing) -> None:
    del payload[missing]
    with pytest.raises(DelinquencyFileError, match="missing"):
        load(tmp_path, payload)


@pytest.mark.parametrize(
    "document",
    [
        "../outside.md",
        "/absolute.md",
        "C:/private.md",
        "C:private.md",
        "//server/share/a.md",
        "\\\\server\\share\\a.md",
        "nested\\a.md",
        "nested/../a.md",
        "./note.md",
        "a//b.md",
        "note.md ",
        "CON.md",
        "evidence/LPT1.txt",
    ],
)
def test_F08_unsafe_document_paths_rejected_before_reads(tmp_path, payload, document) -> None:
    payload["supporting_documents"] = [document]
    with pytest.raises(DelinquencyFileError):
        load(tmp_path, payload)


def test_F08_nested_documents_and_mixed_reference_are_verified(tmp_path, payload) -> None:
    directory = tmp_path / "evidence"
    directory.mkdir()
    (directory / "note.md").write_text("Synthetic county confirmation", encoding="utf-8")
    payload.update(
        delinquency_assertion="mixed_unpaid_prior_and_overdue_current_year_taxes",
        tax_year_convention="isanti_assessment_year_plus_one",
        year_semantics_reference="evidence/note.md",
        supporting_documents=["evidence/note.md"],
    )
    mapping = load(tmp_path, payload)
    assert mapping.supporting_paths(tmp_path) == {
        "evidence/note.md": (directory / "note.md").resolve()
    }
    payload["year_semantics_reference"] = "elsewhere.md"
    with pytest.raises(DelinquencyFileError, match="retained reference"):
        load(tmp_path, payload)


@pytest.mark.parametrize("documents", [["missing.md"], ["note.md", "NOTE.md"], ["folder"]])
def test_F08_missing_collision_or_directory_fails(tmp_path, payload, documents) -> None:
    (tmp_path / "note.md").write_text("Synthetic", encoding="utf-8")
    (tmp_path / "folder").mkdir()
    payload["supporting_documents"] = documents
    with pytest.raises(DelinquencyFileError):
        load(tmp_path, payload)


def test_F08_symlink_escape_fails(tmp_path, payload) -> None:
    base = tmp_path / "base"
    base.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("Synthetic outside evidence", encoding="utf-8")
    try:
        (base / "link.md").symlink_to(outside)
    except OSError:
        pytest.skip("This Windows account cannot create symlinks; Linux CI exercises this case.")
    payload["supporting_documents"] = ["link.md"]
    with pytest.raises(DelinquencyFileError, match="escapes"):
        load(base, payload)


def test_F01_direct_mapping_and_size_boundary(tmp_path, payload) -> None:
    mapping = load(tmp_path, payload)
    with pytest.raises(DelinquencyFileError):
        replace(mapping, dataset=False)
    path = tmp_path / "mapping.json"
    size = path.stat().st_size
    assert DelinquencyMapping.from_json(path, limits=InputLimits(max_file_bytes=size)) == mapping
    with pytest.raises(DelinquencyFileError, match="max_file_bytes"):
        DelinquencyMapping.from_json(path, limits=InputLimits(max_file_bytes=size - 1))


def test_F01_reviewed_mapping_and_template_remain_valid() -> None:
    project = Path(__file__).parents[2]
    for relative in (
        "docs/counties/isanti-delinquency-2026-10-13.mapping.json",
        "docs/examples/isanti-delinquency-mapping.example.json",
        "tests/fixtures/isanti_delinquency_mapping.json",
    ):
        assert DelinquencyMapping.from_json(project / relative).columns["parcel_id"]


def test_F01_any_active_year_convention_needs_retained_evidence(tmp_path, payload) -> None:
    payload["tax_year_convention"] = "isanti_assessment_year_plus_one"
    with pytest.raises(DelinquencyFileError, match="retained reference"):
        load(tmp_path, payload)
