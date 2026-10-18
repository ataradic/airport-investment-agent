"""Data layer: live BTS T-100 data from the open-data portal (Socrata API) with a local JSON cache.

Dataset: "T100 Segment Summary By Origin Airport" (r495-tyji), one row per origin airport per month.
Limits of this dataset (stated to users by the tools):
  * passengers are DEPARTING passengers only;
  * no delay / on-time data;
  * no per-route data, only the monthly average flight distance per airport.
"""
import json
import os
from datetime import datetime, timezone

import pandas as pd
import requests

DATASET_ID = "r495-tyji"
DATASET_URL = f"https://data.transportation.gov/resource/{DATASET_ID}.json"
BASE_YEAR = 2019  # pre-pandemic reference year
CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "bts_t100.json")
CACHE_MAX_AGE_DAYS = 7
TIMEOUT_SECONDS = 60

# Static reference data (names and geography), not statistics.
AIRPORTS = {
    "BOS": ("Boston Logan International", "Boston", "MA"),
    "MHT": ("Manchester-Boston Regional", "Manchester", "NH"),
    "PVD": ("T.F. Green International", "Providence", "RI"),
    "BDL": ("Bradley International", "Hartford", "CT"),
    "PWM": ("Portland International Jetport", "Portland", "ME"),
    "BTV": ("Burlington International", "Burlington", "VT"),
    "LAX": ("Los Angeles International", "Los Angeles", "CA"),
    "SNA": ("John Wayne Airport", "Santa Ana", "CA"),
    "SFO": ("San Francisco International", "San Francisco", "CA"),
    "OAK": ("Oakland International", "Oakland", "CA"),
    "SJC": ("San Jose Mineta International", "San Jose", "CA"),
    "SAN": ("San Diego International", "San Diego", "CA"),
    "SEA": ("Seattle-Tacoma International", "Seattle", "WA"),
    "PDX": ("Portland International", "Portland", "OR"),
    "ANC": ("Ted Stevens Anchorage International", "Anchorage", "AK"),
    "ATL": ("Hartsfield-Jackson Atlanta International", "Atlanta", "GA"),
    "ORD": ("Chicago O'Hare International", "Chicago", "IL"),
    "DFW": ("Dallas/Fort Worth International", "Dallas-Fort Worth", "TX"),
    "DEN": ("Denver International", "Denver", "CO"),
    "JFK": ("John F. Kennedy International", "New York", "NY"),
    "LAS": ("Harry Reid International", "Las Vegas", "NV"),
    "PHX": ("Phoenix Sky Harbor International", "Phoenix", "AZ"),
    "MIA": ("Miami International", "Miami", "FL"),
}

REGIONS = {
    "new england": {"MA", "NH", "RI", "CT", "ME", "VT"},
    "california": {"CA"},
    "alaska": {"AK"},
    "pacific northwest": {"WA", "OR"},
    "west coast": {"CA", "OR", "WA", "AK"},
}

AIRPORT_WARNINGS = {
    "ANC": ("Anchorage is a major cargo hub. Passenger metrics understate its real activity, and it is not verified "
            "whether all-cargo flights are included in departures, so load factor and flight distance may be distorted."),
}

NUMERIC_COLS = ["total_departures", "total_passengers", "total_seats", "total_distance_flight_sm", "domestic_departures"]


class DataUnavailable(RuntimeError):
    """Raised when neither the live API nor a local cache can provide data."""


# ---------------------------------------------------------------- API access
def _query(params: dict):
    response = requests.get(DATASET_URL, params=params, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def _latest_complete_year() -> int:
    """Most recent year for which a reference airport (BOS) reports all 12 months."""
    rows = _query({"$select": "year, count(*) as n", "$where": "origin_airport_code='BOS'",
                   "$group": "year", "$order": "year DESC", "$limit": 6})
    for row in rows:
        if int(row["n"]) >= 12:
            return int(row["year"])
    raise DataUnavailable("Could not determine the latest complete year from the API.")


def _fetch_rows(years):
    codes = ",".join(f"'{c}'" for c in AIRPORTS)
    yrs = ",".join(f"'{y}'" for y in years)
    return _query({"$where": f"origin_airport_code in ({codes}) AND year in ({yrs})", "$limit": 50000})


def _build_records(rows, base_year: int, latest_year: int):
    if not rows:
        raise DataUnavailable("The API returned no rows.")
    df = pd.DataFrame(rows)
    for col in NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0) if col in df else 0
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["month"] = pd.to_datetime(df["reporting_month"], errors="coerce").dt.month

    records, missing = {}, []
    for code, (name, city, state) in AIRPORTS.items():
        sub = df[df["origin_airport_code"] == code]
        base, latest = sub[sub["year"] == base_year], sub[sub["year"] == latest_year]
        if (base.empty or latest.empty or base["total_seats"].sum() <= 0 or base["total_passengers"].sum() <= 0
                or latest["total_seats"].sum() <= 0 or latest["total_departures"].sum() <= 0):
            missing.append(code)
            continue
        monthly_lf = latest["total_passengers"] / latest["total_seats"].where(latest["total_seats"] > 0)
        departures = float(latest["total_departures"].sum())
        stage = float((latest["total_distance_flight_sm"] * latest["total_departures"]).sum() / departures)
        intl = 1 - float(latest["domestic_departures"].sum()) / departures
        records[code] = {
            "name": name, "city": city, "state": state,
            "pax_base": float(base["total_passengers"].sum()), "seats_base": float(base["total_seats"].sum()),
            "pax_latest": float(latest["total_passengers"].sum()), "seats_latest": float(latest["total_seats"].sum()),
            "departures_latest": departures,
            "peak_load_factor": float(monthly_lf.max()),
            "avg_stage_miles": stage,
            "intl_departure_share": min(max(intl, 0.0), 1.0),
            "months_base": int(base["month"].nunique()), "months_latest": int(latest["month"].nunique()),
        }
    if not records:
        raise DataUnavailable("No airport had usable data for both years.")
    return records, missing


def _load_live():
    latest_year = _latest_complete_year()
    rows = _fetch_rows([BASE_YEAR, latest_year])
    records, missing = _build_records(rows, BASE_YEAR, latest_year)
    return {"fetched_at": datetime.now(timezone.utc).isoformat(), "base_year": BASE_YEAR,
            "latest_year": latest_year, "records": records, "missing": missing}


# ---------------------------------------------------------------- cache
def _read_cache():
    try:
        with open(CACHE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _write_cache(payload):
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
    except OSError:
        pass  # caching is best effort


def _age_days(payload) -> float:
    fetched = datetime.fromisoformat(payload["fetched_at"])
    return (datetime.now(timezone.utc) - fetched).total_seconds() / 86400


_STATE = {}


def _ensure_loaded():
    """Load once per process: fresh cache -> live API -> stale cache -> error."""
    if _STATE:
        return
    cache = _read_cache()
    if cache and _age_days(cache) <= CACHE_MAX_AGE_DAYS:
        payload, quality, note = cache, "cache", ""
    else:
        try:
            payload, quality, note = _load_live(), "live", ""
            _write_cache(payload)
        except Exception as exc:  # network, HTTP error, schema change
            if cache is None:
                raise DataUnavailable(f"Live BTS data could not be loaded and no cache exists: {exc}") from exc
            payload, quality, note = cache, "stale_cache", str(exc)
    _STATE.update(payload=payload, quality=quality, note=note)


# ---------------------------------------------------------------- public API
def get_meta() -> dict:
    _ensure_loaded()
    p = _STATE["payload"]
    return {"base_year": p["base_year"], "latest_year": p["latest_year"], "fetched_at": p["fetched_at"],
            "quality": _STATE["quality"], "note": _STATE["note"], "missing": p.get("missing", [])}


def get_airport(iata: str):
    """Return the record for an airport, or None if unknown or without data."""
    _ensure_loaded()
    code = iata.strip().upper()
    record = _STATE["payload"]["records"].get(code)
    return None if record is None else {"iata": code, **record}


def all_airports():
    _ensure_loaded()
    return [{"iata": code, **rec} for code, rec in _STATE["payload"]["records"].items()]


def airports_in_region(region: str):
    """Airports in a named region (everything for 'all'). None if the region is unknown."""
    if not region or region.strip().lower() in ("all", "us", "usa"):
        return all_airports()
    states = REGIONS.get(region.strip().lower())
    if states is None:
        return None
    return [a for a in all_airports() if a["state"] in states]