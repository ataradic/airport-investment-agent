"""Raw metrics computed from one airport record. Pure functions, no scaling."""
import data


def _years_between() -> int:
    meta = data.get_meta()
    return meta["latest_year"] - meta["base_year"]


def passenger_cagr(airport: dict) -> float:
    """Compound annual growth of departing passengers, base year to latest complete year."""
    return (airport["pax_latest"] / airport["pax_base"]) ** (1 / _years_between()) - 1


def seat_cagr(airport: dict) -> float:
    """Compound annual growth of seat capacity."""
    return (airport["seats_latest"] / airport["seats_base"]) ** (1 / _years_between()) - 1


def load_factor(airport: dict) -> float:
    """Annual passengers divided by seats (congestion proxy)."""
    return airport["pax_latest"] / airport["seats_latest"]


def peak_load_factor(airport: dict) -> float:
    """Highest monthly load factor in the latest year (peak-season stress proxy)."""
    return airport["peak_load_factor"]


def stage_length(airport: dict) -> float:
    """Departure-weighted average flight distance in statute miles (reach proxy)."""
    return airport["avg_stage_miles"]


def intl_departure_share(airport: dict) -> float:
    """Share of departures that are international."""
    return airport["intl_departure_share"]


def demand_capacity_gap(airport: dict) -> float:
    """Passenger growth minus seat growth. Positive: demand is outpacing capacity."""
    return passenger_cagr(airport) - seat_cagr(airport)


# Metrics that feed the investment score, keyed by the names used in scoring.WEIGHTS.
SCORED_METRICS = {
    "growth": passenger_cagr,
    "congestion": load_factor,
    "peak": peak_load_factor,
    "reach": stage_length,
}
