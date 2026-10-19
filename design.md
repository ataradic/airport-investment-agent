# Airport Investment Intelligence Agent: Design

**Architecture:**
Streamlit chat → Gemini agent (function calling) → 5 Python tools → scoring code → BTS T-100 data (public API + local cache). The model chooses which tool to call; the code does all calculations.

**Scoring:** a 0-100 screening score, the weighted sum of metrics scaled across all tracked airports:
growth 35% (passenger CAGR vs 2019),
congestion 25% (annual load factor),
peak 25% (peak-month load factor),
reach 15% (average flight distance).
The weights are my assumptions, not validated findings. Each tool returns every metric's contribution, so a score can always be explained.

**Key trade-offs:**
- Public API instead of file downloads: easy to run, but no delay or route data.
- Relative scoring: easy to compare airports, but scores depend on the set of tracked airports.
- Unmet demand and long-haul % are labelled proxies, not exact figures, because the data does not contain them.

**Where AI is used:** 
Gemini understands the question, picks tools and explains the results.
It does not fetch data or calculate: every number comes from a tool, together with its assumptions and warnings.

**Not done:** validation of the weights, voice input.
