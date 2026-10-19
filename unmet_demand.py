"""Unmet-demand PROXY index (0-1). It is an indirect indicator, never a measured quantity."""
import metrics
import scoring

# A demand-minus-capacity growth gap of +/-2 points per year maps to 0..1 (0.5 = no gap).
GAP_RANGE = 0.02


def growth_gap_score(airport: dict) -> float:
    """Fixed-scale score for the passenger-vs-seat growth gap.

    A fixed scale is used instead of min-max: min-max would blow a tiny gap up to 0 or 1
    when all airports are close together.
    """
    gap = metrics.demand_capacity_gap(airport)
    return min(max((gap + GAP_RANGE) / (2 * GAP_RANGE), 0.0), 1.0)


def unmet_components(airport: dict) -> dict:
    """The three 0-1 components of the proxy."""
    return {
        "load_factor": scoring.normalise_metric(metrics.load_factor, airport),
        "demand_minus_capacity_growth": growth_gap_score(airport),
        "peak_load_factor": scoring.normalise_metric(metrics.peak_load_factor, airport),
    }


def unmet_index(airport: dict):
    """(equal-weight average of the components rounded to 2 decimals, the components)."""
    components = unmet_components(airport)
    return round(sum(components.values()) / len(components), 2), components
