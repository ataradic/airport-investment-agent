"""Thin client for the BTS T-100 dataset on the open-data portal (Socrata JSON API).

Dataset: "T100 Segment Summary By Origin Airport", one row per origin airport per month.
"""
import requests

from errors import DataUnavailable

DATASET_ID = "r495-tyji"
DATASET_URL = f"https://data.transportation.gov/resource/{DATASET_ID}.json"
TIMEOUT_SECONDS = 60
MONTHS_PER_YEAR = 12
REFERENCE_AIRPORT = "BOS"  # large airport used to detect which years are fully reported
MAX_ROWS = 50000


def query(params: dict) -> list:
    """Run one SoQL query against the dataset and return the decoded JSON rows."""
    response = requests.get(DATASET_URL, params=params, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def fetch_latest_complete_year() -> int:
    """Most recent year for which the reference airport reports all 12 months."""
    rows = query({
        "$select": "year, count(*) as n",
        "$where": f"origin_airport_code='{REFERENCE_AIRPORT}'",
        "$group": "year",
        "$order": "year DESC",
        "$limit": 6,
    })
    for row in rows:
        if int(row["n"]) >= MONTHS_PER_YEAR:
            return int(row["year"])
    raise DataUnavailable("Could not determine the latest complete year from the API.")


def fetch_rows(airport_codes, years) -> list:
    """All monthly rows for the given airports and years."""
    codes = ",".join(f"'{code}'" for code in airport_codes)
    year_list = ",".join(f"'{year}'" for year in years)
    return query({"$where": f"origin_airport_code in ({codes}) AND year in ({year_list})", "$limit": MAX_ROWS})
