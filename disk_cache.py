"""Local JSON cache for the processed BTS data."""
import json
import os
from datetime import datetime, timezone

CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "bts_t100.json")
CACHE_MAX_AGE_DAYS = 7


def read_cache():
    """Cached payload, or None if missing or unreadable."""
    try:
        with open(CACHE_PATH, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def write_cache(payload: dict) -> None:
    """Save the payload. Caching is best effort, so write errors are ignored."""
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
    except OSError:
        pass


def age_days(payload: dict) -> float:
    fetched = datetime.fromisoformat(payload["fetched_at"])
    return (datetime.now(timezone.utc) - fetched).total_seconds() / 86400


def is_fresh(payload: dict) -> bool:
    return age_days(payload) <= CACHE_MAX_AGE_DAYS
