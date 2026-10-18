"""Deterministic scoring. The LLM never computes or alters these numbers."""
import data
import metrics

# Hypothesis weights. Each one needs a written justification in design.md.
WEIGHTS = {"growth": 0.35, "congestion": 0.25, "peak": 0.25, "reach": 0.15}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def _minmax(value, lo, hi):
    return 0.5 if hi == lo else (value - lo) / (hi - lo)


def _bounds(fn):
    values = [fn(a) for a in data.all_airports()]
    return min(values), max(values)


def metric_scores(airport: dict) -> dict:
    """Normalise each raw metric to 0-1 against the full airport universe."""
    out = {}
    for name, fn in metrics.RAW_METRICS.items():
        lo, hi = _bounds(fn)
        out[name] = _minmax(fn(airport), lo, hi)
    return out


def score_airport(airport: dict, weights: dict = None) -> dict:
    """Return the 0-100 score, the per-metric contribution, raw values and a confidence label."""
    weights = weights or WEIGHTS
    normalised = metric_scores(airport)
    contributions = {k: round(100 * weights[k] * normalised[k], 1) for k in weights}
    return {
        "iata": airport["iata"],
        "name": airport["name"],
        "score": round(sum(contributions.values()), 1),
        "contributions": contributions,
        "raw": {k: round(fn(airport), 4) for k, fn in metrics.RAW_METRICS.items()},
        "confidence": "medium" if airport["months_base"] == 12 and airport["months_latest"] == 12 else "low",
    }


def rank(airports: list, weights: dict = None) -> list:
    scored = [score_airport(a, weights) for a in airports]
    return sorted(scored, key=lambda s: s["score"], reverse=True)


def rank_sensitivity(airports: list, delta: float = 0.10) -> dict:
    """Re-rank with each weight shifted by +/- delta (others rescaled) to test ranking stability."""
    base_order = [s["iata"] for s in rank(airports)]
    changed = {}
    for key in WEIGHTS:
        for sign in (+1, -1):
            w = dict(WEIGHTS)
            w[key] = max(0.0, w[key] * (1 + sign * delta))
            total = sum(w.values())
            w = {k: v / total for k, v in w.items()}
            order = [s["iata"] for s in rank(airports, w)]
            if order != base_order:
                changed[f"{key} {'+' if sign > 0 else '-'}{int(delta*100)}%"] = order
    return {"base_order": base_order, "orderings_that_changed": changed}