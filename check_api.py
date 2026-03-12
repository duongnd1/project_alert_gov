import requests

ENDPOINTS = [
    "https://giayphep.abei.gov.vn/api/search",
    "https://giayphep.abei.gov.vn/api/g1/search",
    "https://giayphep.abei.gov.vn/api/g1",
    "https://giayphep.abei.gov.vn/api/TraCuu",
    "https://giayphep.abei.gov.vn/services/g1",
    "https://giayphep.abei.gov.vn/g1/api"
]

def check():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Content-Type': 'application/json'
    }
    
    for url in ENDPOINTS:
        try:
            print(f"Checking {url}...", end=" ")
            resp = requests.get(url, headers=headers, timeout=5)
            print(f"GET: {resp.status_code}", end=" | ")
            
            resp_post = requests.post(url, headers=headers, json={"keyword": "a"}, timeout=5)
            print(f"POST: {resp_post.status_code}")
            
            if resp.status_code == 200 or resp_post.status_code == 200:
                print(f"FOUND POTENTIAL API: {url}")
                print(resp.text[:200])
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    check()
