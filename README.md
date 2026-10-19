# Airport Investment Intelligence Agent

Conversational agent that screens US airports for modernization investment using live BTS T-100 data
and a deterministic scoring model. See `design.md` for methodology, trade-offs and limitations.

## Run

```
pip install -r requirements.txt
set GEMINI_API_KEY=...            # PowerShell: $env:GEMINI_API_KEY="..."
streamlit run app.py
```

Optional: `GEMINI_MODEL` selects the model (default `gemini-3.8-flash`).
The first run fetches data from data.transportation.gov and caches it in `cache/bts_t100.json`
(keep this file when submitting so the app also works offline).

## Sample questions

- Which airports in New England are strong candidates for terminal expansion?
- Compare LA and Santa Ana airport congestion levels.
- What is the percentage of long haul flights out of Anchorage airport?
- What is the unmet flight demand in SFO airport and why?
