from selenium import webdriver
import os
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json

def check_network():
    print("Setting up Chrome...")
    chrome_install = ChromeDriverManager().install()
    folder_name = os.path.dirname(chrome_install)
    chromedriver_path = os.path.join(folder_name, "chromedriver.exe")
    
    print(f"Driver path: {chromedriver_path}")

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    
    service = Service(chromedriver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        url = "https://giayphep.abei.gov.vn/g1"
        print(f"Navigating to {url}...")
        driver.get(url)
        
        # Wait for input
        wait = WebDriverWait(driver, 10)
        input_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input.ant-input")))
        print("Found search input.")
        
        # Type search query
        input_element.send_keys("GAMOTA")
        print("Typed query 'GAMOTA'...")
        
        # Click search icon
        search_icon = driver.find_element(By.CSS_SELECTOR, ".ant-input-suffix .anticon-search")
        search_icon.click()
        print("Clicked search icon.")
        
        time.sleep(5) # Wait for requests
        
        # Get logs
        logs = driver.get_log('performance')
        
        print(f"Captured {len(logs)} logs. Analyzing...")
        
        found_api = False
        for entry in logs:
            message = json.loads(entry['message'])['message']
            if message['method'] == 'Network.requestWillBeSent':
                req_url = message['params']['request']['url']
                if "giayphep.abei.gov.vn" in req_url and not req_url.endswith(('.js', '.css', '.png', '.svg', '.jpg', '.woff2')):
                    print(f"Request: {req_url}")
                    found_api = True
                    
        if not found_api:
            print("No obvious API requests found. Data might be loaded via WebSockets or strictly client-side.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    check_network()
