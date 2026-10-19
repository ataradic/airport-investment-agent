"""Tools exposed to the LLM (function calling). Docstrings and type hints are read by the model.

Each tool returns {"data", "assumptions", "warnings"} via responses.build_response.
"""
import data
import metrics
import scoring
import unmet_demand
from responses import airport_warnings, build_response, unknown_airport, unknown_region

# Metric differences below these values are reported as "roughly equal".
SMALL_DIFFERENCE = {"growth": 0.005, "congestion": 0.02, "peak": 0.02, "reach": 150}


# ---- helpers (not exposed to the model) ------------------------------------
def _attach_unmet_proxy(ranked: list) -> None:
    """Add the unmet-demand proxy index to every ranked item, so rankings compare the same metrics."""
    for item in ranked:
        item["unmet_demand_proxy"] = unmet_demand.unmet_index(data.get_airport(item["iata"]))[0]


def _negative_growth_warning(ranked: list) -> list:
    """Warn when growth is negative: the growth contribution is only a relative score."""
    negative = [item["iata"] for item in ranked if item["raw"]["growth"] < 0]
    if not negative:
        return []
    return [f"Passenger growth is NEGATIVE for {negative}. Growth contribution is a relative score only: "
            "the least-negative airport scores highest. Do not describe these airports as growing."]


def _higher_airport_per_metric(score_a: dict, score_b: dict) -> dict:
    return {name: (score_a["iata"] if score_a["raw"][name] > score_b["raw"][name] else score_b["iata"])
            for name in score_a["raw"]}


def _small_difference_flags(score_a: dict, score_b: dict) -> dict:
    return {name: abs(score_a["raw"][name] - score_b["raw"][name]) < SMALL_DIFFERENCE[name]
            for name in score_a["raw"]}


# ---- tools -----------------------------------------------------------------
def list_airports(region: str = "all") -> dict:
    """List airports in the dataset for a region such as 'new england', 'california', 'alaska', or 'all'."""
    found = data.airports_in_region(region)
    if found is None:
        return unknown_region(region)
    return build_response([{"iata": a["iata"], "name": a["name"], "state": a["state"]} for a in found])


def rank_airports(region: str = "all", top_n: int = 5) -> dict:
    """Rank airports in a region by the deterministic investment-attractiveness screening score (0-100)."""
    found = data.airports_in_region(region)
    if found is None:
        return unknown_region(region)
    ranked = scoring.rank(found)[:top_n]
    _attach_unmet_proxy(ranked)
    ranked_airports = [data.get_airport(item["iata"]) for item in ranked]
    return build_response(
        {"region": region, "ranking": ranked, "sensitivity": scoring.rank_sensitivity(found)},
        assumptions=[
            f"Weights: {scoring.WEIGHTS}",
            "Metrics are min-max normalised against all tracked airports, not only the requested region.",
            "congestion = annual load factor (passengers / seats); peak = highest monthly load factor in the latest year; "
            "reach = average flight distance in miles.",
        ],
        warnings=["Score is a screening aid, not a return forecast: no cost, revenue or regulatory data is included."]
        + _negative_growth_warning(ranked) + airport_warnings(*ranked_airports))


def compare_airports(iata_a: str, iata_b: str) -> dict:
    """Compare two airports by IATA code on score, congestion, peak load factor, growth and flight distance."""
    airport_a, airport_b = data.get_airport(iata_a), data.get_airport(iata_b)
    if airport_a is None:
        return unknown_airport(iata_a)
    if airport_b is None:
        return unknown_airport(iata_b)
    score_a, score_b = scoring.score_airport(airport_a), scoring.score_airport(airport_b)
    small = _small_difference_flags(score_a, score_b)
    warnings = airport_warnings(airport_a, airport_b)
    close = [name for name, is_small in small.items() if is_small]
    if close:
        warnings.append(f"Differences are very small for {close}; treat these metrics as roughly equal, not as a real gap.")
    return build_response(
        {"a": score_a, "b": score_b, "higher_raw_value": _higher_airport_per_metric(score_a, score_b),
         "difference_is_small": small},
        assumptions=["congestion = annual load factor (passengers / seats); peak = highest monthly load factor."],
        warnings=warnings)


def get_route_mix(iata: str) -> dict:
    """Return average flight distance and the international share of departures for an airport (route-mix proxies)."""
    airport = data.get_airport(iata)
    if airport is None:
        return unknown_airport(iata)
    international = metrics.intl_departure_share(airport)
    return build_response(
        {"iata": airport["iata"], "avg_stage_miles": round(metrics.stage_length(airport)),
         "international_departure_share": round(international, 3),
         "international_departure_percent": round(100 * international, 1),
         "long_haul_flight_percent": None},
        assumptions=["The exact share of flights above a distance threshold (long-haul %) CANNOT be computed: the dataset only has "
                     "a monthly average flight distance per airport, no per-route data.",
                     "International share of departures and average distance are proxies for route reach, not long-haul %."],
        warnings=airport_warnings(airport))


def estimate_unmet_demand(iata: str) -> dict:
    """Estimate unmet demand for an airport using a PROXY (high load factor, demand outgrowing seats, peak-month load)."""
    airport = data.get_airport(iata)
    if airport is None:
        return unknown_airport(iata)
    index, components = unmet_demand.unmet_index(airport)
    return build_response(
        {"iata": airport["iata"], "proxy_index": index,
         "components": {name: round(value, 2) for name, value in components.items()},
         "raw": {"load_factor": round(metrics.load_factor(airport), 3),
                 "peak_load_factor": round(metrics.peak_load_factor(airport), 3),
                 "passenger_cagr": round(metrics.passenger_cagr(airport), 4),
                 "seat_cagr": round(metrics.seat_cagr(airport), 4)}},
        assumptions=["Equal weights across the three components.",
                     "load_factor and peak_load_factor are min-max scaled against all tracked airports (relative, not absolute); "
                     "demand_minus_capacity_growth uses a fixed scale where +/-2 points per year spans 0 to 1 (0.5 = no gap).",
                     "High load factor + demand outpacing seats + high peak-month load suggest constrained supply."],
        warnings=["Unmet demand cannot be measured directly with this data; this is an indirect proxy index (0-1)."]
        + airport_warnings(airport))


TOOLS = [list_airports, rank_airports, compare_airports, get_route_mix, estimate_unmet_demand]
