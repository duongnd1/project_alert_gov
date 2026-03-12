import requests
from bs4 import BeautifulSoup
import json

URL = "https://giayphep.abei.gov.vn/g1"

def inspect():
    print(f"Fetching {URL}...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(URL, headers=headers)
    print(f"Status: {response.status_code}")
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # 1. Inspect title
    print(f"Title: {soup.title.string if soup.title else 'No Title'}")
    
    # 2. Look for tables
    tables = soup.find_all('table')
    print(f"Found {len(tables)} tables.")
    
    # 3. Look for potential data in scripts (e.g. Next.js data)
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'NEXT_DATA' in script.string:
            print("Found NEXT_DATA!")
            # parse it if needed
    
    # 4. Dump structure to file
    with open("site_structure.html", "w", encoding="utf-8") as f:
        f.write(soup.prettify())
    print("Saved structure to site_structure.html")

if __name__ == "__main__":
    inspect()
