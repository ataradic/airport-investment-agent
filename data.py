"""Public data API for the rest of the app.

Loads once per process. Order of preference: fresh cache -> live API -> stale cache -> error.
Limits of the underlying BTS dataset: departing passengers only, no delay data, no per-route data.
"""
from datetime import datetime, timezone

import bts_client
import disk_cache
import records
from catalog import AIRPORTS, is_all_regions, states_for_region
from errors import DataUnavailable  # re-exported for callers

BASE_YEAR = 2019  # pre-pandemic reference year

_STATE = {}  # filled by _ensure_loaded: payload, quality, note


def _load_live() -> dict:
    """Fetch rows from the API and build a cacheable payload."""
    latest_year = bts_client.fetch_latest_complete_year()
    rows = bts_client.fetch_rows(list(AIRPORTS), [BASE_YEAR, latest_year])
    airport_records, missing = records.build_records(rows, BASE_YEAR, latest_year)
    return {"fetched_at": datetime.now(timezone.utc).isoformat(), "base_year": BASE_YEAR,
            "latest_year": latest_year, "records": airport_records, "missing": missing}


def _resolve_source():
    """Return (payload, quality, note); quality is 'cache', 'live' or 'stale_cache'."""
    cached = disk_cache.read_cache()
    if cached and disk_cache.is_fresh(cached):
        return cached, "cache", ""
    try:
        payload = _load_live()
    except Exception as exc:  # network error, HTTP error, schema change
        if cached is None:
            raise DataUnavailable(f"Live BTS data could not be loaded and no cache exists: {exc}") from exc
        return cached, "stale_cache", str(exc)
    disk_cache.write_cache(payload)
    return payload, "live", ""


def _ensure_loaded() -> None:
    if _STATE:
        return
    payload, quality, note = _resolve_source()
    _STATE.update(payload=payload, quality=quality, note=note)


def get_meta() -> dict:
    """Years covered, fetch time, data quality ('live' / 'cache' / 'stale_cache') and missing airports."""
    _ensure_loaded()
    payload = _STATE["payload"]
    return {"base_year": payload["base_year"], "latest_year": payload["latest_year"],
            "fetched_at": payload["fetched_at"], "quality": _STATE["quality"],
            "note": _STATE["note"], "missing": payload.get("missing", [])}


def get_airport(iata: str):
    """Record for one airport (with its 'iata' code), or None if unknown or without data."""
    _ensure_loaded()
    code = iata.strip().upper()
    record = _STATE["payload"]["records"].get(code)
    return None if record is None else {"iata": code, **record}


def all_airports() -> list:
    _ensure_loaded()
    return [{"iata": code, **record} for code, record in _STATE["payload"]["records"].items()]


def airports_in_region(region: str):
    """Airports in a named region (all airports for 'all'). None if the region is unknown."""
    if is_all_regions(region):
        return all_airports()
    states = states_for_region(region)
    if states is None:
        return None
    return [airport for airport in all_airports() if airport["state"] in states]
