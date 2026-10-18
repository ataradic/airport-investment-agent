"""Raw metrics computed from airport records. Pure functions, no scaling."""
import data


def _years() -> int:
    meta = data.get_meta()
    return meta["latest_year"] - meta["base_year"]


def passenger_cagr(a: dict) -> float:
    """Compound annual growth of departing passengers, base year to latest complete year."""
    return (a["pax_latest"] / a["pax_base"]) ** (1 / _years()) - 1


def seat_cagr(a: dict) -> float:
    """Compound annual growth of seat capacity."""
    return (a["seats_latest"] / a["seats_base"]) ** (1 / _years()) - 1


def load_factor(a: dict) -> float:
    """Annual passengers divided by seats (congestion proxy)."""
    return a["pax_latest"] / a["seats_latest"]


def peak_load_factor(a: dict) -> float:
    """Highest monthly load factor in the latest year (peak-season stress proxy)."""
    return a["peak_load_factor"]


def stage_length(a: dict) -> float:
    """Departure-weighted average flight distance in statute miles (reach proxy)."""
    return a["avg_stage_miles"]


def intl_departure_share(a: dict) -> float:
    """Share of departures that are international."""
    return a["intl_departure_share"]


def demand_capacity_gap(a: dict) -> float:
    """Passenger growth minus seat growth. Positive: demand is outpacing capacity."""
    return passenger_cagr(a) - seat_cagr(a)


RAW_METRICS = {
    "growth": passenger_cagr,
    "congestion": load_factor,
    "peak": peak_load_factor,
    "reach": stage_length,
}