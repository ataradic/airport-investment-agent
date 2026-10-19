"""Deterministic scoring. The LLM never computes or alters these numbers."""
import data
import metrics

# Hypothesis weights. Each one is justified in design.md.
WEIGHTS = {"growth": 0.35, "congestion": 0.25, "peak": 0.25, "reach": 0.15}
SENSITIVITY_DELTA = 0.10
FULL_YEAR_MONTHS = 12


# ---- normalisation ---------------------------------------------------------
def normalise(value: float, low: float, high: float) -> float:
    """Min-max scale to 0-1. Returns 0.5 when all airports are identical."""
    return 0.5 if high == low else (value - low) / (high - low)


def normalise_metric(metric_fn, airport: dict) -> float:
    """Scale one airport's metric against all tracked airports (0-1)."""
    values = [metric_fn(other) for other in data.all_airports()]
    return normalise(metric_fn(airport), min(values), max(values))


def metric_scores(airport: dict) -> dict:
    """Normalised 0-1 value of every scored metric."""
    return {name: normalise_metric(fn, airport) for name, fn in metrics.SCORED_METRICS.items()}


# ---- single airport --------------------------------------------------------
def data_confidence(airport: dict) -> str:
    """'medium' only when both years have a full 12 months of data, else 'low'."""
    complete = airport["months_base"] == FULL_YEAR_MONTHS and airport["months_latest"] == FULL_YEAR_MONTHS
    return "medium" if complete else "low"


def score_airport(airport: dict, weights: dict = None) -> dict:
    """0-100 score with per-metric contributions, raw values and a confidence label."""
    weights = weights or WEIGHTS
    normalised = metric_scores(airport)
    contributions = {name: round(100 * weights[name] * normalised[name], 1) for name in weights}
    return {
        "iata": airport["iata"],
        "name": airport["name"],
        "score": round(sum(contributions.values()), 1),
        "contributions": contributions,
        "raw": {name: round(fn(airport), 4) for name, fn in metrics.SCORED_METRICS.items()},
        "confidence": data_confidence(airport),
    }


# ---- ranking ---------------------------------------------------------------
def rank(airports: list, weights: dict = None) -> list:
    """Scored airports, best first."""
    scored = [score_airport(airport, weights) for airport in airports]
    return sorted(scored, key=lambda item: item["score"], reverse=True)


def shifted_weights(key: str, direction: int, delta: float) -> dict:
    """Weights with one entry changed by +/- delta (relative), then rescaled to sum to 1."""
    shifted = dict(WEIGHTS)
    shifted[key] = max(0.0, shifted[key] * (1 + direction * delta))
    total = sum(shifted.values())
    return {name: value / total for name, value in shifted.items()}


def rank_sensitivity(airports: list, delta: float = SENSITIVITY_DELTA) -> dict:
    """Re-rank under each +/- weight shift and report the orderings that differ from the base ranking."""
    base_order = [item["iata"] for item in rank(airports)]
    changed = {}
    for key in WEIGHTS:
        for direction in (+1, -1):
            order = [item["iata"] for item in rank(airports, shifted_weights(key, direction, delta))]
            if order != base_order:
                sign = "+" if direction > 0 else "-"
                changed[f"{key} {sign}{int(delta * 100)}%"] = order
    return {"base_order": base_order, "orderings_that_changed": changed}
