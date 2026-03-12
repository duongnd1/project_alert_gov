from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os, time

def test():
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
        # Go to detail page directly
        url = "https://giayphep.abei.gov.vn/g1/131828"
        print(f"Navigating to {url}...")
        driver.get(url)
        time.sleep(5)
        
        # Print full page text
        body = driver.find_element(By.TAG_NAME, "body").text
        print("=== FULL TEXT ===")
        print(body)
        print("=================")
        
        # Also try to find specific table or labeled elements
        all_elements = driver.find_elements(By.CSS_SELECTOR, "span, div, p, td")
        for el in all_elements:
            txt = el.text.strip()
            if "Ngày" in txt or "cấp" in txt:
                print(f"FOUND: '{txt}' in <{el.tag_name}> class='{el.get_attribute('class')}'")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    test()
