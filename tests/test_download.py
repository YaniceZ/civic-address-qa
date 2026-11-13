import pytest

from civic_qa.download import DownloadError, fetch_layer


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def feature(i):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-89.2, 48.4]}, "properties": {"OBJECTID": i}}


class FakeSession:
    """Serves a layer of `total` features, `page_cap` at a time, like an ArcGIS server."""

    def __init__(self, total, page_cap=None, error=False):
        self.total, self.page_cap, self.error = total, page_cap, error
        self.offsets = []

    def get(self, url, params, timeout):
        if params.get("returnCountOnly"):
            return FakeResponse({"count": self.total})
        if not url.endswith("/query"):
            return FakeResponse({"name": "fake", "maxRecordCount": 2})
        if self.error:
            return FakeResponse({"error": {"code": 400, "message": "bad"}})
        start = params["resultOffset"]
        self.offsets.append(start)
        size = min(params["resultRecordCount"], self.page_cap or 10**6)
        ids = range(start, min(start + size, self.total))
        return FakeResponse({"type": "FeatureCollection", "features": [feature(i) for i in ids]})


def test_pages_through_whole_layer():
    session = FakeSession(total=5)
    gdf = fetch_layer("https://example.com/FeatureServer/0", session=session)
    assert len(gdf) == 5
    assert session.offsets == [0, 2, 4]
    assert gdf.crs.to_epsg() == 4326


def test_short_pages_raise_instead_of_returning_partial_data():
    with pytest.raises(DownloadError, match="Expected 5"):
        fetch_layer("https://example.com/FeatureServer/0", session=FakeSession(total=5, page_cap=1))


def test_error_body_with_http_200_is_a_failure(monkeypatch):
    monkeypatch.setattr("civic_qa.download.time.sleep", lambda s: None)
    with pytest.raises(DownloadError):
        fetch_layer("https://example.com/FeatureServer/0", session=FakeSession(total=3, error=True))
