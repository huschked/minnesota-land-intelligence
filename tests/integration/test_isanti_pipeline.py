import pytest

from mn_land.counties.isanti import IsantiAdapter


@pytest.mark.integration
def test_live_isanti_metadata_and_count() -> None:
    adapter = IsantiAdapter()
    metadata = adapter.client.metadata()
    assert metadata["name"] == "TaxParcels_Public"
    assert metadata["geometryType"] == "esriGeometryPolygon"
    assert metadata["advancedQueryCapabilities"]["supportsPagination"] is True
    assert adapter.client.count() > 0
