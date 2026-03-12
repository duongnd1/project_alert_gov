from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import time

def debug_card():
    print("Setting up Chrome...")
    chrome_install = ChromeDriverManager().install()
    folder_name = os.path.dirname(chrome_install)
    chromedriver_path = os.path.join(folder_name, "chromedriver.exe")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--log-level=3")
    
    service = Service(chromedriver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(30)
    
    try:
        url = "https://giayphep.abei.gov.vn/g1"
        print(f"Navigating to {url}...")
        driver.get(url)
        
        # Wait for content
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ant-card-body")))
        
        print("Waiting for skeleton to disappear...")
        time.sleep(5)
        
        # Get first card
        cards = driver.find_elements(By.CSS_SELECTOR, ".ant-card-body")
        if cards:
            print("--- First Card HTML ---")
            print(cards[0].get_attribute('outerHTML'))
            print("--- End HTML ---")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    debug_card()
