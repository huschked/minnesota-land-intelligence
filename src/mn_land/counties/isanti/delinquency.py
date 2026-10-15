import re

from mn_land.models.delinquency import TaxPeriodStatus


class ParcelIdError(ValueError):
    """An Isanti parcel identifier cannot be normalized safely."""


def normalize_parcel_id(parcel_id: object) -> str:
    """Return the digits-only Isanti join key after removing known separators."""
    if parcel_id is None:
        raise ParcelIdError("parcel ID is missing")
    original = str(parcel_id).strip()
    if not original:
        raise ParcelIdError("parcel ID is blank")
    if re.search(r"[^0-9.\-\s]", original):
        raise ParcelIdError(f"parcel ID contains unsupported characters: {original!r}")
    normalized = re.sub(r"[.\-\s]", "", original)
    if not normalized:
        raise ParcelIdError("parcel ID contains no digits")
    return normalized


def classify_assessment_years(
    row_assessment_year: object, report_assessment_year: object
) -> tuple[int, int, int, TaxPeriodStatus]:
    """Apply county-confirmed conventions, not GIS field-name inference.

    ASMTYR is the individual charge assessment year; TAXYR is the report
    assessment year. Taxes payable follow the assessment year by one year.
    Source inclusion establishes unpaid prior charges or overdue current first-half
    installments, not the status of unlisted parcels or future installments.
    """
    values = []
    for value in (row_assessment_year, report_assessment_year):
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}", value.strip()):
            raise ValueError(f"invalid or missing assessment year: {value!r}")
        values.append(int(value.strip()))
    assessment, report_assessment = values
    if assessment > report_assessment:
        raise ValueError("row assessment year is after the report assessment year")
    status = (
        TaxPeriodStatus.PRIOR_YEAR_UNPAID if assessment < report_assessment
        else TaxPeriodStatus.OVERDUE_CURRENT_YEAR
    )
    return assessment, assessment + 1, report_assessment + 1, status
