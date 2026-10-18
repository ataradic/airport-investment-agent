"""Tools exposed to the LLM.

Every tool returns {"data": ..., "assumptions": [...], "warnings": [...]} so that
transparency and uncertainty are built into the plumbing, not bolted on afterwards.
"""
import data
import metrics
import scoring

GAP_RANGE = 0.02  # a demand-minus-capacity growth gap of +/-2 points per year maps to 0..1 (fixed scale)

# Differences smaller than this are reported as "roughly equal".
SMALL_DIFF = {"growth": 0.005, "congestion": 0.02, "peak": 0.02, "reach": 150}


def _assumptions(extra=None):
    meta = data.get_meta()
    base = [f"Source: BTS T-100 Segment summary by origin airport (data.transportation.gov, dataset {data.DATASET_ID}); "
            f"{meta['base_year']} vs {meta['latest_year']}; departing passengers only; covers reporting carriers."]
    return base + (extra or [])


def _warnings(extra=None):
    meta = data.get_meta()
    notes = [f"Growth is measured against {meta['base_year']}, a pre-pandemic year, so it mixes recovery and structural change.",
             "On-time/delay data is NOT part of this dataset; delays are not used in any score."]
    if meta["quality"] != "live":
        notes.append(f"Data comes from a local cache fetched at {meta['fetched_at']} (live API not used in this run)."
                     + (f" Live fetch failed: {meta['note']}" if meta["note"] else ""))
    return notes + (extra or [])


def _response(payload, assumptions=None, warnings=None):
    return {"data": payload, "assumptions": _assumptions(assumptions), "warnings": _warnings(warnings)}


def _unknown(iata):
    known = sorted(a["iata"] for a in data.all_airports())
    return _response(None, warnings=[f"Airport '{iata}' is not in the dataset. Known: {known}"])


def _airport_warning(*records):
    return [data.AIRPORT_WARNINGS[r["iata"]] for r in records if r["iata"] in data.AIRPORT_WARNINGS]


def _unmet_parts(a):
    """Normalised components (0-1) of the unmet-demand proxy for one airport."""
    universe = data.all_airports()

    def norm(fn):
        values = [fn(x) for x in universe]
        return scoring._minmax(fn(a), min(values), max(values))

    gap = metrics.demand_capacity_gap(a)
    return {
        "load_factor": norm(metrics.load_factor),
        # Fixed scale instead of min-max: min-max would blow a tiny gap up to 0 or 1 when all airports are close together.
        "demand_minus_capacity_growth": min(max((gap + GAP_RANGE) / (2 * GAP_RANGE), 0.0), 1.0),
        "peak_load_factor": norm(metrics.peak_load_factor),
    }


def _unmet_index(a):
    parts = _unmet_parts(a)
    return round(sum(parts.values()) / len(parts), 2), parts


def list_airports(region: str = "all") -> dict:
    """List airports in the dataset for a region such as 'new england', 'california', 'alaska', or 'all'."""
    found = data.airports_in_region(region)
    if found is None:
        return _response(None, warnings=[f"Unknown region '{region}'. Known: {sorted(data.REGIONS)}"])
    return _response([{"iata": a["iata"], "name": a["name"], "state": a["state"]} for a in found])


def rank_airports(region: str = "all", top_n: int = 5) -> dict:
    """Rank airports in a region by the deterministic investment-attractiveness screening score (0-100)."""
    found = data.airports_in_region(region)
    if found is None:
        return _response(None, warnings=[f"Unknown region '{region}'. Known: {sorted(data.REGIONS)}"])
    ranked = scoring.rank(found)[:top_n]
    for item in ranked:
        item["unmet_demand_proxy"] = _unmet_index(data.get_airport(item["iata"]))[0]
    extra = []
    negative = [r["iata"] for r in ranked if r["raw"]["growth"] < 0]
    if negative:
        extra.append(f"Passenger growth is NEGATIVE for {negative}. Growth contribution is a relative score only: "
                     "the least-negative airport scores highest. Do not describe these airports as growing.")
    extra += _airport_warning(*[data.get_airport(r["iata"]) for r in ranked])
    return _response(
        {"region": region, "ranking": ranked, "sensitivity": scoring.rank_sensitivity(found)},
        assumptions=[
            f"Weights: {scoring.WEIGHTS}",
            "Metrics are min-max normalised against all tracked airports, not only the requested region.",
            "congestion = annual load factor (passengers / seats); peak = highest monthly load factor in the latest year; "
            "reach = average flight distance in miles.",
        ],
        warnings=["Score is a screening aid, not a return forecast: no cost, revenue or regulatory data is included."]
        + extra)


def compare_airports(iata_a: str, iata_b: str) -> dict:
    """Compare two airports by IATA code on score, congestion, peak load factor, growth and flight distance."""
    a, b = data.get_airport(iata_a), data.get_airport(iata_b)
    if a is None:
        return _unknown(iata_a)
    if b is None:
        return _unknown(iata_b)
    sa, sb = scoring.score_airport(a), scoring.score_airport(b)
    higher = {k: (a["iata"] if sa["raw"][k] > sb["raw"][k] else b["iata"]) for k in sa["raw"]}
    small = {k: abs(sa["raw"][k] - sb["raw"][k]) < SMALL_DIFF[k] for k in sa["raw"]}
    warnings = _airport_warning(a, b)
    close = [k for k, v in small.items() if v]
    if close:
        warnings.append(f"Differences are very small for {close}; treat these metrics as roughly equal, not as a real gap.")
    return _response({"a": sa, "b": sb, "higher_raw_value": higher, "difference_is_small": small},
                     assumptions=["congestion = annual load factor (passengers / seats); peak = highest monthly load factor."],
                     warnings=warnings)


def get_route_mix(iata: str) -> dict:
    """Return average flight distance and the international share of departures for an airport (route-mix proxies)."""
    a = data.get_airport(iata)
    if a is None:
        return _unknown(iata)
    return _response(
        {"iata": a["iata"], "avg_stage_miles": round(a["avg_stage_miles"]),
         "international_departure_share": round(a["intl_departure_share"], 3),
         "international_departure_percent": round(100 * a["intl_departure_share"], 1),
         "long_haul_flight_percent": None},
        assumptions=["The exact share of flights above a distance threshold (long-haul %) CANNOT be computed: the dataset only has "
                     "a monthly average flight distance per airport, no per-route data.",
                     "International share of departures and average distance are proxies for route reach, not long-haul %."],
        warnings=_airport_warning(a))


def estimate_unmet_demand(iata: str) -> dict:
    """Estimate unmet demand for an airport using a PROXY (high load factor, demand outgrowing seats, peak-month load)."""
    a = data.get_airport(iata)
    if a is None:
        return _unknown(iata)
    index, parts = _unmet_index(a)
    return _response(
        {"iata": a["iata"], "proxy_index": index, "components": {k: round(v, 2) for k, v in parts.items()},
         "raw": {"load_factor": round(metrics.load_factor(a), 3),
                 "peak_load_factor": round(metrics.peak_load_factor(a), 3),
                 "passenger_cagr": round(metrics.passenger_cagr(a), 4),
                 "seat_cagr": round(metrics.seat_cagr(a), 4)}},
        assumptions=["Equal weights across the three components.",
                     "load_factor and peak_load_factor are min-max scaled against all tracked airports (relative, not absolute); "
                     "demand_minus_capacity_growth uses a fixed scale where +/-2 points per year spans 0 to 1 (0.5 = no gap).",
                     "High load factor + demand outpacing seats + high peak-month load suggest constrained supply."],
        warnings=["Unmet demand cannot be measured directly with this data; this is an indirect proxy index (0-1)."]
        + _airport_warning(a))


TOOLS = [list_airports, rank_airports, compare_airports, get_route_mix, estimate_unmet_demand]