import pytest

from mn_land.counties.isanti.delinquency import ParcelIdError, normalize_parcel_id


@pytest.mark.parametrize(
    "raw",
    ["01.001.0201", "01-001-0201", "01 001 0201", "  01.001.0201  ", "01. 001-0201"],
)
def test_isanti_known_separators_produce_same_exact_key(raw: str) -> None:
    assert normalize_parcel_id(raw) == "010010201"


@pytest.mark.parametrize("raw", [None, "", "01/001/0201", "01.OO1.0201", "parcel 010010201"])
def test_isanti_normalization_rejects_unsafe_values(raw: object) -> None:
    with pytest.raises(ParcelIdError):
        normalize_parcel_id(raw)
