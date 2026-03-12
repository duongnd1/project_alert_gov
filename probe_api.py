"""
Probe script to detect Next.js API endpoints on giayphep.abei.gov.vn.
This DOES NOT touch data.json or any existing files.
"""
import requests
import json

BASE = "https://giayphep.abei.gov.vn"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, */*",
    "Referer": BASE,
}

def try_endpoint(url, label):
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"\n[{label}] Status: {r.status_code}")
        ct = r.headers.get("content-type", "")
        print(f"  Content-Type: {ct}")
        if r.status_code == 200:
            if "json" in ct:
                data = r.json()
                print(f"  ✅ JSON response! Keys: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}")
                print(f"  Preview: {str(data)[:300]}")
                return data
            else:
                print(f"  Content (first 200 chars): {r.text[:200]}")
        return None
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None

print("=== Probing Next.js API endpoints ===\n")

# Common Next.js API patterns
endpoints = [
    # Next.js data fetching APIs
    ("/api/games", "Next.js /api/games"),
    ("/api/g1", "Next.js /api/g1"),
    ("/api/license", "Next.js /api/license"),
    ("/api/giayphep", "Next.js /api/giayphep"),
    # Next.js RSC / getServerSideProps data
    ("/_next/data/", "Next.js RSC data root"),
    # Common REST patterns
    ("/g1/api", "REST /g1/api"),
    ("/api/v1/games", "REST /api/v1/games"),
    ("/api/v1/g1", "REST /api/v1/g1"),
    # Try with query params (pagination)
    ("/api/games?page=1&limit=10", "API with pagination"),
    ("/g1?page=1&format=json", "JSON format param"),
]

results = {}
for path, label in endpoints:
    url = BASE + path
    data = try_endpoint(url, label)
    if data is not None:
        results[label] = data

print("\n\n=== Summary ===")
if results:
    print(f"✅ Found {len(results)} working API endpoint(s)!")
    for label in results:
        print(f"  - {label}")
else:
    print("❌ No direct JSON API found. Will need browser automation.")
    print("   Next option: Try fetching the page with requests and parsing the __NEXT_DATA__ script tag.")

# Also try parsing __NEXT_DATA__ from the main page (Next.js embeds state in HTML)
print("\n=== Checking __NEXT_DATA__ in HTML ===")
try:
    r = requests.get(BASE + "/g1", headers=headers, timeout=15)
    import re
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text, re.DOTALL)
    if match:
        next_data = json.loads(match.group(1))
        print(f"✅ Found __NEXT_DATA__! Keys: {list(next_data.keys())}")
        # Look for game data in props
        props = next_data.get("props", {})
        page_props = props.get("pageProps", {})
        print(f"  pageProps keys: {list(page_props.keys())}")
        if page_props:
            print(f"  Preview: {str(page_props)[:500]}")
    else:
        print("❌ No __NEXT_DATA__ found. Site likely uses SSR without embedding data.")
except Exception as e:
    print(f"❌ Error: {e}")
