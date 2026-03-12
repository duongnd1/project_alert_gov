import requests

URL = "https://giayphep.abei.gov.vn/_next/static/chunks/app/g1/page-ac4f58b7b204a966.js"

def download():
    print(f"Downloading {URL}...")
    try:
        response = requests.get(URL)
        response.encoding = 'utf-8' # Ensure utf-8
        
        with open("page.js", "w", encoding="utf-8") as f:
            f.write(response.text)
        print("✅ Saved to page.js")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    download()
