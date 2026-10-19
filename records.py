"""Turns raw monthly API rows into one summary record per airport."""
import pandas as pd

from catalog import AIRPORTS
from errors import DataUnavailable

NUMERIC_COLUMNS = ["total_departures", "total_passengers", "total_seats",
                   "total_distance_flight_sm", "domestic_departures"]


def build_records(rows: list, base_year: int, latest_year: int):
    """Return ({iata: record}, [iata with missing data])."""
    frame = _rows_to_dataframe(rows)
    records, missing = {}, []
    for code in AIRPORTS:
        airport_rows = frame[frame["origin_airport_code"] == code]
        base = airport_rows[airport_rows["year"] == base_year]
        latest = airport_rows[airport_rows["year"] == latest_year]
        if _has_usable_data(base, latest):
            records[code] = _summarize_airport(code, base, latest)
        else:
            missing.append(code)
    if not records:
        raise DataUnavailable("No airport had usable data for both years.")
    return records, missing


def _rows_to_dataframe(rows: list) -> pd.DataFrame:
    """Parse API strings into numbers and add a numeric month column."""
    if not rows:
        raise DataUnavailable("The API returned no rows.")
    frame = pd.DataFrame(rows)
    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0) if column in frame else 0
    frame["year"] = pd.to_numeric(frame["year"], errors="coerce")
    frame["month"] = pd.to_datetime(frame["reporting_month"], errors="coerce").dt.month
    return frame


def _has_usable_data(base: pd.DataFrame, latest: pd.DataFrame) -> bool:
    """Both years must exist and have non-zero traffic, seats and departures."""
    if base.empty or latest.empty:
        return False
    return (base["total_seats"].sum() > 0 and base["total_passengers"].sum() > 0
            and latest["total_seats"].sum() > 0 and latest["total_departures"].sum() > 0)


def _summarize_airport(code: str, base: pd.DataFrame, latest: pd.DataFrame) -> dict:
    """Yearly totals plus the three route/season indicators for one airport."""
    name, city, state = AIRPORTS[code]
    departures = float(latest["total_departures"].sum())
    return {
        "name": name, "city": city, "state": state,
        "pax_base": float(base["total_passengers"].sum()),
        "seats_base": float(base["total_seats"].sum()),
        "pax_latest": float(latest["total_passengers"].sum()),
        "seats_latest": float(latest["total_seats"].sum()),
        "departures_latest": departures,
        "peak_load_factor": _peak_load_factor(latest),
        "avg_stage_miles": _average_stage_miles(latest, departures),
        "intl_departure_share": _international_share(latest, departures),
        "months_base": int(base["month"].nunique()),
        "months_latest": int(latest["month"].nunique()),
    }


def _peak_load_factor(latest: pd.DataFrame) -> float:
    """Highest monthly passengers / seats ratio in the latest year."""
    seats = latest["total_seats"].where(latest["total_seats"] > 0)
    return float((latest["total_passengers"] / seats).max())


def _average_stage_miles(latest: pd.DataFrame, departures: float) -> float:
    """Average flight distance, weighted by each month's departures."""
    weighted = (latest["total_distance_flight_sm"] * latest["total_departures"]).sum()
    return float(weighted / departures)


def _international_share(latest: pd.DataFrame, departures: float) -> float:
    """Share of departures that are not domestic, clipped to [0, 1]."""
    share = 1 - float(latest["domestic_departures"].sum()) / departures
    return min(max(share, 0.0), 1.0)
