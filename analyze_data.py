import requests
from bs4 import BeautifulSoup
import json
import re

URL = "https://giayphep.abei.gov.vn/g1"

def analyze():
    print(f"Fetching {URL}...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(URL, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Next.js usually puts data in a script tag with id "__NEXT_DATA__"
    # Inspect site structure showed:  (self.__next_f=self.__next_f||[]).push...
    # It seems this site uses Next.js 13+ App Router which uses a different hydration format.
    # It streams data in `self.__next_f.push` calls.
    
    print("Searching for __next_f scripts...")
    scripts = soup.find_all('script')
    
    found_data = []
    
    for script in scripts:
        if script.string and 'self.__next_f.push' in script.string:
            # Try to find JSON-like structures inside the push arguments
            # This is messy because it's a list of operations
            content = script.string
            # Check for keywords related to the data we want
            if "GAMOTA" in content or "HONKA" in content or "giấy phép" in content:
                print("Found potential data chunk!")
                found_data.append(content)
                
    if found_data:
        print(f"Found {len(found_data)} chunks with keywords.")
        with open("next_f_data.js", "w", encoding="utf-8") as f:
            for chunk in found_data:
                f.write(chunk + "\n\n")
        print("Saved relevant data chunks to next_f_data.js")
    else:
        print("No obvious data chunks found in HTML. Data might be fetched client-side via API.")
        
        # Fallback: Check if there's a different API call in the network tab (simulated by checking common endpoints again)
        # But let's look at the full HTML again carefully.
        with open("full_page.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())
        print("Saved full page to full_page.html")

if __name__ == "__main__":
    analyze()
