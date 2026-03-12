import requests
import json

# Extracted from HTML
BUILD_ID = "nEOutQdBMk2UBrqU0f1Pe"
URL = f"https://giayphep.abei.gov.vn/_next/data/{BUILD_ID}/g1.json"

def check_data():
    print(f"Checking {URL}...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(URL, headers=headers)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Success! Found JSON data.")
            # Verify if it has the game list
            page_props = data.get('pageProps', {})
            print(f"Keys in pageProps: {page_props.keys()}")
            
            # Save sample to analyze
            with open("next_data_sample.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print("Saved to next_data_sample.json")
        else:
            print("❌ Failed. It might not be a static page or the Build ID changed.")
            print(response.text[:200])
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_data()
