"""Standard response envelope shared by all tools: {"data", "assumptions", "warnings"}.

Transparency lives here: every tool answer carries its data source and known limitations.
"""
import bts_client
import catalog
import data


def data_assumptions(extra=None) -> list:
    meta = data.get_meta()
    source = (f"Source: BTS T-100 Segment summary by origin airport (data.transportation.gov, dataset {bts_client.DATASET_ID}); "
              f"{meta['base_year']} vs {meta['latest_year']}; departing passengers only; covers reporting carriers.")
    return [source] + (extra or [])


def data_warnings(extra=None) -> list:
    meta = data.get_meta()
    notes = [f"Growth is measured against {meta['base_year']}, a pre-pandemic year, so it mixes recovery and structural change.",
             "On-time/delay data is NOT part of this dataset; delays are not used in any score."]
    if meta["quality"] != "live":
        notes.append(f"Data comes from a local cache fetched at {meta['fetched_at']} (live API not used in this run)."
                     + (f" Live fetch failed: {meta['note']}" if meta["note"] else ""))
    return notes + (extra or [])


def build_response(payload, assumptions=None, warnings=None) -> dict:
    """Wrap a tool result with the standard assumptions and warnings."""
    return {"data": payload, "assumptions": data_assumptions(assumptions), "warnings": data_warnings(warnings)}


def unknown_airport(iata: str) -> dict:
    known = sorted(airport["iata"] for airport in data.all_airports())
    return build_response(None, warnings=[f"Airport '{iata}' is not in the dataset. Known: {known}"])


def unknown_region(region: str) -> dict:
    return build_response(None, warnings=[f"Unknown region '{region}'. Known: {sorted(catalog.REGIONS)}"])


def airport_warnings(*airports) -> list:
    """Caveats attached to specific airports (e.g. Anchorage cargo)."""
    return [catalog.AIRPORT_WARNINGS[a["iata"]] for a in airports if a["iata"] in catalog.AIRPORT_WARNINGS]
