"""Download every feature from an ArcGIS REST layer, one page at a time."""

from __future__ import annotations

import logging
import time

import geopandas as gpd
import requests

log = logging.getLogger(__name__)


class DownloadError(RuntimeError):
    pass


def _get_json(session: requests.Session, url: str, params: dict, retries: int = 3) -> dict:
    """GET a JSON response, retrying on network errors.

    ArcGIS servers often answer HTTP 200 with an {"error": ...} body, so that case is treated as a failure too.
    """
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                raise DownloadError(f"{url} returned an error: {data['error']}")
            return data
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            log.warning("Request failed (attempt %d/%d): %s", attempt, retries, exc)
            time.sleep(2 * attempt)
    raise DownloadError(f"Giving up on {url}: {last_error}")


def fetch_layer(
    layer_url: str,
    id_field: str = "OBJECTID",
    where: str = "1=1",
    out_fields: str = "*",
    page_size: int | None = None,
    session: requests.Session | None = None,
) -> gpd.GeoDataFrame:
    """Return all features of a layer as a GeoDataFrame in EPSG:4326.

    Pages are ordered by `id_field` so that offsets are stable, and the final row count is compared
    with the count the server reports. A mismatch raises instead of returning a partial layer.
    """
    session = session or requests.Session()
    layer_url = layer_url.rstrip("/")

    info = _get_json(session, layer_url, {"f": "json"})
    if page_size is None:
        page_size = min(int(info.get("maxRecordCount") or 1000), 2000)

    query_url = f"{layer_url}/query"
    expected = _get_json(session, query_url, {"where": where, "returnCountOnly": "true", "f": "json"})["count"]
    log.info("%s: %d features, %d per page", info.get("name", layer_url), expected, page_size)

    features: list[dict] = []
    for offset in range(0, expected, page_size):
        page = _get_json(
            session,
            query_url,
            {
                "where": where,
                "outFields": out_fields,
                "orderByFields": id_field,
                "resultOffset": offset,
                "resultRecordCount": page_size,
                "outSR": 4326,
                "f": "geojson",
            },
        )
        features.extend(page.get("features", []))

    if len(features) != expected:
        raise DownloadError(f"Expected {expected} features but received {len(features)}")
    return gpd.GeoDataFrame.from_features(features, crs="EPSG:4326")
