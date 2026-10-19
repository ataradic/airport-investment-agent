"""Static reference data: tracked airports, named regions and per-airport caveats. No statistics live here."""

# iata: (name, city, state)
AIRPORTS = {
    "BOS": ("Boston Logan International", "Boston", "MA"),
    "MHT": ("Manchester-Boston Regional", "Manchester", "NH"),
    "PVD": ("T.F. Green International", "Providence", "RI"),
    "BDL": ("Bradley International", "Hartford", "CT"),
    "PWM": ("Portland International Jetport", "Portland", "ME"),
    "BTV": ("Burlington International", "Burlington", "VT"),
    "LAX": ("Los Angeles International", "Los Angeles", "CA"),
    "SNA": ("John Wayne Airport", "Santa Ana", "CA"),
    "SFO": ("San Francisco International", "San Francisco", "CA"),
    "OAK": ("Oakland International", "Oakland", "CA"),
    "SJC": ("San Jose Mineta International", "San Jose", "CA"),
    "SAN": ("San Diego International", "San Diego", "CA"),
    "SEA": ("Seattle-Tacoma International", "Seattle", "WA"),
    "PDX": ("Portland International", "Portland", "OR"),
    "ANC": ("Ted Stevens Anchorage International", "Anchorage", "AK"),
    "ATL": ("Hartsfield-Jackson Atlanta International", "Atlanta", "GA"),
    "ORD": ("Chicago O'Hare International", "Chicago", "IL"),
    "DFW": ("Dallas/Fort Worth International", "Dallas-Fort Worth", "TX"),
    "DEN": ("Denver International", "Denver", "CO"),
    "JFK": ("John F. Kennedy International", "New York", "NY"),
    "LAS": ("Harry Reid International", "Las Vegas", "NV"),
    "PHX": ("Phoenix Sky Harbor International", "Phoenix", "AZ"),
    "MIA": ("Miami International", "Miami", "FL"),
}

REGIONS = {
    "new england": {"MA", "NH", "RI", "CT", "ME", "VT"},
    "california": {"CA"},
    "alaska": {"AK"},
    "pacific northwest": {"WA", "OR"},
    "west coast": {"CA", "OR", "WA", "AK"},
}

AIRPORT_WARNINGS = {
    "ANC": ("Anchorage is a major cargo hub. Passenger metrics understate its real activity, and it is not verified "
            "whether all-cargo flights are included in departures, so load factor and flight distance may be distorted."),
}

_ALL_REGION_NAMES = ("", "all", "us", "usa")


def is_all_regions(region: str) -> bool:
    """True when the region name means 'no filter'."""
    return (region or "").strip().lower() in _ALL_REGION_NAMES


def states_for_region(region: str):
    """State codes of a named region, or None if the region is unknown."""
    return REGIONS.get(region.strip().lower())
