from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sys
import json
import os
import time

def search(keyword):
    chrome_install = ChromeDriverManager().install()
    folder_name = os.path.dirname(chrome_install)
    chromedriver_path = os.path.join(folder_name, "chromedriver.exe")

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--log-level=3") # Suppress logs
    
    service = Service(chromedriver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    results = []
    try:
        url = "https://giayphep.abei.gov.vn/g1"
        driver.get(url)
        
        # Wait for input
        wait = WebDriverWait(driver, 10)
        input_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input.ant-input")))
        
        # Type search query
        input_element.send_keys(keyword)
        
        # Click search icon
        search_icon = driver.find_element(By.CSS_SELECTOR, ".ant-input-suffix .anticon-search")
        search_icon.click()
        
        # Wait for results (skeleton loader to disappear or cards to appear)
        time.sleep(3) # Simple wait for now
        
        # Extract data from cards
        cards = driver.find_elements(By.CSS_SELECTOR, ".ant-card-body")
        
        for card in cards:
            try:
                text = card.text.split('\n')
                if len(text) >= 4:
                    item = {
                        "name": text[0],
                        "company": text[2] if len(text) > 2 else "",
                        "license": text[3] if len(text) > 3 else "",
                        "domain": text[4] if len(text) > 4 else "",
                        "status": text[5] if len(text) > 5 else ""
                    }
                    results.append(item)
            except Exception:
                pass
                
    except Exception as e:
        results.append(f"Error: {e}")
    finally:
        driver.quit()
        
    print(json.dumps(results, ensure_ascii=False))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        search(sys.argv[1])
    else:
        print(json.dumps(["No keyword provided"]))
