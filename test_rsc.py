import requests
import json

def test_search():
    # Based on logs: https://giayphep.abei.gov.vn/g1?keyword=&_rsc=2ubim
    # When searching: https://giayphep.abei.gov.vn/g1?keyword=GAMOTA&_rsc=2ubim
    # The _rsc value might change, but let's try with the one from logs.
    
    url = "https://giayphep.abei.gov.vn/g1"
    params = {
        "keyword": "GAMOTA",
        "_rsc": "2ubim" # Extracted from logs
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'RSC': '1',
        'Next-Router-State-Tree': '%5B%22%22%2C%7B%22children%22%3A%5B%22g1%22%2C%7B%22children%22%3A%5B%22__PAGE__%22%2C%7B%7D%5D%7D%5D%7D%2Cnull%2Cnull%2Ctrue%5D',
        'Next-Url': '/g1',
    }
    
    print(f"Fetching {url} with params {params}...")
    try:
        response = requests.get(url, params=params, headers=headers)
        print(f"Status: {response.status_code}")
        
        # Save response to analyze RSC format
        with open("rsc_response.txt", "w", encoding="utf-8") as f:
            f.write(response.text)
        print("Saved response to rsc_response.txt")
        
        # Simple check if GAMOTA is in response
        if "GAMOTA" in response.text:
            print("✅ Found 'GAMOTA' in response!")
        else:
            print("❌ 'GAMOTA' not found. RSC signature might be expired or wrong.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_search()
