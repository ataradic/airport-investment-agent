"""One-off probe #2: check the on-time dataset, look for route-level datasets, and test filtering by airport/year."""
import requests

BASE = "https://data.transportation.gov/resource"

# 1) Columns of the on-time performance dataset
r = requests.get(f"{BASE}/939q-bf5e.json", params={"$limit": 2}, timeout=30)
print("== 939q-bf5e (on-time) ==", r.status_code)
print(r.json())

# 2) Test filtering on the airport-level T-100 dataset (BOS, 2024)
r = requests.get(f"{BASE}/r495-tyji.json",
                 params={"$where": "origin_airport_code='BOS' AND year='2024'", "$limit": 50}, timeout=30)
rows = r.json()
print("\n== r495-tyji BOS 2024 ==", r.status_code, "rows:", len(rows))
if rows:
    print({k: rows[0][k] for k in ("reporting_month", "total_departures", "total_passengers", "total_seats")})

# 3) Search the portal catalog for other relevant datasets (route level, on-time by airport)
for q in ("T-100 route", "T100 origin destination", "on-time airport"):
    c = requests.get("https://api.us.socrata.com/api/catalog/v1",
                     params={"domains": "data.transportation.gov", "q": q, "limit": 8}, timeout=30)
    print(f"\n== catalog search: {q} ==", c.status_code)
    if c.status_code == 200:
        for item in c.json().get("results", []):
            print(item["resource"]["id"], "|", item["resource"]["name"])