"""Validate reviewed Isanti mappings without inferring source meanings."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, fields
from datetime import date
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import urlsplit

from mn_land.config.input_limits import DEFAULT_INPUT_LIMITS, InputLimits
from mn_land.delinquency.errors import DelinquencyFileError
from mn_land.delinquency.tabular import read_input

CANONICAL_COLUMNS = {
    "parcel_id",
    "taxpayer_name",
    "owner_name",
    "mailing_address",
    "delinquent_years",
    "delinquent_tax_amount",
    "penalty_amount",
    "total_taxes_and_penalties_due",
}
DELINQUENCY_ASSERTION = "each_row_represents_delinquent_parcel"
MIXED_UNPAID_ASSERTION = "mixed_unpaid_prior_and_overdue_current_year_taxes"


def _nonblank(value: object, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DelinquencyFileError(f"mapping {field} must be nonblank text")


def _relative(value: object) -> str:
    _nonblank(value, "document path")
    assert isinstance(value, str)
    windows = PureWindowsPath(value)
    parts = value.split("/")
    if (
        windows.drive
        or windows.root
        or PurePosixPath(value).is_absolute()
        or "\\" in value
        or any(part in {"", ".", ".."} for part in parts)
        or any(char in value for char in ':*?"<>|\x00')
    ):
        raise DelinquencyFileError("supporting documents require contained portable relative paths")
    if any(part.endswith((" ", ".")) for part in parts):
        raise DelinquencyFileError("document paths must not have ambiguous trailing spaces/dots")
    if any(
        re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", part.split(".")[0].upper())
        for part in parts
    ):
        raise DelinquencyFileError("document paths must not use reserved Windows device names")
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise DelinquencyFileError(f"duplicate mapping JSON key: {key}")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class DelinquencyMapping:
    source_agency: str
    dataset: str
    columns: dict[str, str]
    delinquency_assertion: str
    source_url: str | None = None
    publication_date: str | None = None
    verification_hold_reason: str | None = None
    tax_year_convention: str | None = None
    year_semantics_reference: str | None = None
    supporting_documents: tuple[str, ...] = ()
    review_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("source_agency", "dataset", "delinquency_assertion"):
            _nonblank(getattr(self, name), name)
        if not re.match(r"^isanti county(?:\b)", self.source_agency.casefold()):
            raise DelinquencyFileError("source_agency must identify Isanti County")
        if self.delinquency_assertion not in (DELINQUENCY_ASSERTION, MIXED_UNPAID_ASSERTION):
            raise DelinquencyFileError("unsupported delinquency_assertion")
        if not isinstance(self.columns, dict) or not self.columns.get("parcel_id"):
            raise DelinquencyFileError("mapping columns must include parcel_id")
        if set(self.columns) - CANONICAL_COLUMNS:
            raise DelinquencyFileError("mapping contains unsupported canonical fields")
        for key, value in self.columns.items():
            _nonblank(value, f"columns.{key}")
        if len({value.strip() for value in self.columns.values()}) != len(self.columns):
            raise DelinquencyFileError("mapping has duplicate source-column assignments")
        if any(value != value.strip() for value in self.columns.values()):
            raise DelinquencyFileError("mapped source-header names must be trimmed")
        for name in (
            "source_url",
            "publication_date",
            "verification_hold_reason",
            "tax_year_convention",
            "year_semantics_reference",
        ):
            if getattr(self, name) is not None:
                _nonblank(getattr(self, name), name)
        if self.source_url is not None:
            try:
                url = urlsplit(self.source_url)
                if (
                    url.scheme not in {"http", "https"}
                    or not url.hostname
                    or url.username
                    or url.password
                ):
                    raise ValueError("not an HTTP(S) URL without credentials")
                _ = url.port
                if any(char.isspace() for char in self.source_url):
                    raise ValueError("URL contains whitespace")
            except ValueError as exc:
                raise DelinquencyFileError(
                    "mapping source_url must be a valid HTTP(S) URL"
                ) from exc
        if self.publication_date is not None:
            try:
                if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", self.publication_date):
                    raise ValueError("not ISO date")
                date.fromisoformat(self.publication_date)
            except ValueError as exc:
                raise DelinquencyFileError(
                    "publication_date must be a valid ISO YYYY-MM-DD"
                ) from exc
        if self.tax_year_convention not in (None, "isanti_assessment_year_plus_one"):
            raise DelinquencyFileError("unsupported tax_year_convention")
        if not isinstance(self.supporting_documents, tuple):
            raise DelinquencyFileError("supporting_documents must be a tuple for callable mappings")
        paths = [_relative(value) for value in self.supporting_documents]
        if len({value.casefold() for value in paths}) != len(paths):
            raise DelinquencyFileError("duplicate supporting-document destinations")
        if self.year_semantics_reference is not None:
            _relative(self.year_semantics_reference)
        if self.tax_year_convention is not None and self.year_semantics_reference not in paths:
            raise DelinquencyFileError("year convention requires a retained reference")
        if (
            self.delinquency_assertion == MIXED_UNPAID_ASSERTION
            and self.tax_year_convention is None
        ):
            raise DelinquencyFileError(
                "mixed tax data requires verified year convention and retained reference"
            )
        if not isinstance(self.review_notes, tuple) or not all(
            isinstance(n, str) for n in self.review_notes
        ):
            raise DelinquencyFileError("review_notes must contain text")

    def supporting_paths(self, base: Path) -> dict[str, Path]:
        if not self.supporting_documents:
            return {}
        try:
            root = base.resolve(strict=True)
            resolved = {}
            for name in self.supporting_documents:
                _relative(name)
                candidate = (root / name).resolve(strict=True)
                if not candidate.is_relative_to(root) or not candidate.is_file():
                    raise DelinquencyFileError(
                        "supporting document escapes its base or is not a regular file"
                    )
                if str(candidate).casefold() in {str(p).casefold() for p in resolved.values()}:
                    raise DelinquencyFileError("supporting document aliases another document")
                resolved[name] = candidate
            return resolved
        except (OSError, RuntimeError, ValueError) as exc:
            if isinstance(exc, DelinquencyFileError):
                raise
            raise DelinquencyFileError(f"cannot resolve supporting document: {exc}") from exc

    @classmethod
    def from_json(
        cls,
        path: Path,
        *,
        limits: InputLimits = DEFAULT_INPUT_LIMITS,
        supporting_root: Path | None = None,
    ) -> DelinquencyMapping:
        try:
            payload = json.loads(
                read_input(path, limits).decode("utf-8"), object_pairs_hook=_unique_object
            )
            if not isinstance(payload, dict):
                raise DelinquencyFileError("mapping JSON root must be an object")
            if set(payload) - {field.name for field in fields(cls)}:
                raise DelinquencyFileError("mapping contains unknown top-level keys")
            for name in ("source_agency", "dataset", "columns", "delinquency_assertion"):
                if name not in payload:
                    raise DelinquencyFileError(f"mapping is missing required key: {name}")
            for name in ("supporting_documents", "review_notes"):
                if name in payload:
                    if not isinstance(payload[name], list):
                        raise DelinquencyFileError(f"mapping {name} must be an array")
                    payload[name] = tuple(payload[name])
            mapping = cls(**payload)
            mapping.supporting_paths(supporting_root or path.parent)
            return mapping
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, RecursionError) as exc:
            raise DelinquencyFileError(f"cannot read mapping JSON {path.name}: {exc}") from exc
