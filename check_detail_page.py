from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import time

def check_detail():
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
        
        wait = WebDriverWait(driver, 10)
        card = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".ant-card-body")))
        
        print("Clicking first card...")
        # Use JS click to avoid interception
        driver.execute_script("arguments[0].click();", card)
        
        # Wait for detail modal or page
        time.sleep(3)
        
        print("--- Body Text (First 1000 chars) ---")
        body_text = driver.find_element(By.TAG_NAME, "body").text
        print(body_text[:1000])
        print("------------------------------------")
        
        # Check for date patterns
        if "Ngày" in body_text or "/" in body_text:
             print("Potential date found!")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    check_detail()
