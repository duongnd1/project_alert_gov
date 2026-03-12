from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import time

def check_pagination():
    print("Setting up Chrome...")
    chrome_install = ChromeDriverManager().install()
    folder_name = os.path.dirname(chrome_install)
    chromedriver_path = os.path.join(folder_name, "chromedriver.exe")
    
    print(f"Driver path: {chromedriver_path}")

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
        
        # Scroll to bottom to ensure pagination is visible
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        # Look for pagination
        pagination = driver.find_elements(By.CSS_SELECTOR, ".ant-pagination")
        print(f"Found {len(pagination)} pagination elements.")
        
        if pagination:
            # Try to find "Next" button
            next_btns = driver.find_elements(By.CSS_SELECTOR, "li.ant-pagination-next")
            print(f"Found {len(next_btns)} next buttons.")
            
            # Try to find total pages (last number)
            page_items = driver.find_elements(By.CSS_SELECTOR, "li.ant-pagination-item")
            if page_items:
                last_page = page_items[-1].get_attribute("title")
                print(f"Estimated last page: {last_page}")
                
            # Check if next button is disabled
            if next_btns:
                is_disabled = "ant-pagination-disabled" in next_btns[0].get_attribute("class")
                print(f"Next button disabled: {is_disabled}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    check_pagination()
