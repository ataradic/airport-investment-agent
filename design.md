# Airport Investment Intelligence Agent: Design Document

## 1. Purpose and scope

The agent helps analysts **screen** US airports for modernization investment (e.g. terminal expansion). It answers questions such as "Which New England airports are strong expansion candidates?" or "Compare LAX and SNA congestion", ranks airports with a deterministic score, and explains the result in a conversation.

It is a **screening aid**, not a return forecast: it contains no cost, revenue, regulatory or physical-capacity data, and says so in every answer.

Scope: 23 tracked airports (New England, California, Pacific Northwest, Anchorage, plus several large hubs used as a comparison baseline).

## 2. Architecture

```
User ─► Streamlit chat (app.py)
            │
            ▼
      Agent (agent.py): Gemini with function calling, conversation history
            │ chooses tools
            ▼
      Tools (tools.py): list_airports, rank_airports, compare_airports,
                        get_route_mix, estimate_unmet_demand
            │
            ▼
      scoring.py ─► metrics.py ─► data.py ─► BTS T-100 via Socrata API
                                              (+ local JSON cache)
```

Every tool returns three parts: `data`, `assumptions`, `warnings`. Transparency is part of the plumbing, so the model cannot present a number without the assumptions that came with it.

## 3. Data

- **Source:** BTS "T-100 Segment Summary by Origin Airport", dataset `r495-tyji` on data.transportation.gov, read through its public JSON API (no download step).
- **Years:** 2019 (pre-pandemic baseline) versus the latest year with 12 reported months, detected automatically (2025 at the time of writing).
- **Cache:** the processed result is cached locally for 7 days. If the API fails, a stale cache is used and the answer states that; with no cache the app shows a clear error.

**Limits of this dataset (all surfaced to the user by the tools):**
- Passengers are *departing* passengers only.
- No on-time/delay data. The on-time dataset on the same portal is not available through the API, so delays are **not** used in any score.
- No per-route data, only a monthly average flight distance per airport.
- Covers reporting carriers only; 2019 as a baseline mixes post-pandemic recovery with structural change.
- Anchorage is a major cargo hub; it is not verified whether all-cargo flights are counted in departures, so its load factor and flight distance may be distorted.

## 4. Scoring methodology

Each airport receives a screening score from 0 to 100.

| Metric | Definition | Weight | Why |
|---|---|---|---|
| growth | Passenger CAGR, 2019 to latest year | 0.35 | Demand trajectory |
| congestion | Annual load factor (passengers / seats) | 0.25 | Sustained capacity pressure |
| peak | Highest monthly load factor in the latest year | 0.25 | Stress in the busiest season, where terminals fail first |
| reach | Departure-weighted average flight distance (miles) | 0.15 | Proxy for longer-haul / higher-value traffic |

**Procedure:** each metric is min-max normalised against all tracked airports (0 to 1), multiplied by its weight, and summed. The tool returns the per-metric contribution, so every score can be explained.

**Interpretation of direction:** higher load factor and faster growth are read as evidence that an airport may need more capacity. This is an assumption, not a validated model.

**Uncertainty handling:**
- *Sensitivity test:* each weight is shifted by ±10% (others rescaled) and the ranking is recomputed. Results where the order changes are reported (e.g. BTV and BOS swap places under a lower peak weight).
- *Small-difference flag:* when two airports differ by less than a fixed threshold on a metric, the tool marks the difference as small and the agent must call them roughly equal. The thresholds are my own judgement, not research-based.
- *Negative growth warning:* normalisation is relative, so the least-negative airport can earn a high growth contribution. The tool warns explicitly when raw growth is negative.
- *Confidence label:* "medium" only if both years have 12 months of data, otherwise "low".

**Unmet demand (proxy):** the data cannot measure unserved demand directly. The tool returns an index from 0 to 1, the equal-weight average of annual load factor, peak-month load factor (both min-max scaled against all tracked airports) and the gap between passenger and seat growth. The gap uses a **fixed scale** (±2 points per year = 0 to 1) because min-max scaling inflated a 0.04-point gap at SFO into a maximum component score. The index is always labelled a proxy.

**Long-haul percentage:** the exact share of flights above a distance threshold cannot be computed from airport-level averages. The tool returns average flight distance and the international share of departures as proxies and sets `long_haul_flight_percent` to `null`. I chose an honest "cannot be computed" over inventing a number.

## 5. Key trade-offs

- **Live API vs downloaded files:** I used the public API (reproducible, no manual steps), accepting a thinner dataset (no delays, no routes) than the full BTS downloads would provide.
- **Relative vs absolute scoring:** min-max over a small universe makes scores easy to compare but relative: adding or removing airports changes every score, and tiny differences can look large. Mitigated with warnings, fixed scaling for the gap, and the small-difference flag.
- **Honest proxies vs complete answers:** some of the requested questions (long-haul %, unmet demand) are answered with labelled proxies rather than precise figures.
- **Deterministic code vs LLM flexibility:** all numbers come from code; the model never calculates. The cost is that new kinds of questions require a new tool.
- **Cache vs freshness:** a 7-day cache keeps the app fast and working offline, at the price of slightly older data.

## 6. Where AI is used (and where it is not)

**Used for:** understanding the question (including mappings such as "LA" to LAX), choosing which tools to call, holding conversation context for follow-ups, and explaining the results in plain language with facts, assumptions and conclusions separated.

**Not used for:** retrieving data, computing metrics, scoring or ranking. These are deterministic and testable.

**Guardrails:** the system prompt requires every number to come from a tool, forbids unsourced facts about specific airports, requires the tool warnings to be shown, and limits the agent to its scope. During testing the model sometimes added facts from its own memory about specific airports, over-stated conclusions from relative scores, and exaggerated tiny differences. Each case was addressed with a prompt rule or a tool-level warning, and re-tested on the four sample questions.

## 7. Known limitations and next steps

- No automated tests yet; verification was manual on the four sample questions plus offline checks of the data pipeline with synthetic rows.
- Weights and thresholds are hypotheses and have not been validated against real expansion projects.
- Add per-route data (T-100 segment files or similar) for an exact long-haul percentage, and the BTS On-Time files for delays.
- Add fare and market data to move the unmet-demand proxy closer to real spill demand.
- Voice input (bonus) is not implemented.

## 8. Running it

```
pip install -r requirements.txt
set GEMINI_API_KEY=...          (PowerShell: $env:GEMINI_API_KEY="...")
streamlit run app.py
```

The first run fetches and caches the data in `cache/bts_t100.json`.