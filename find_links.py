from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import os, time

def find_links():
    chrome_install = ChromeDriverManager().install()
    folder_name = os.path.dirname(chrome_install)
    chromedriver_path = os.path.join(folder_name, "chromedriver.exe")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    service = Service(chromedriver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        driver.get("https://giayphep.abei.gov.vn/g1")
        time.sleep(5)
        
        # Look for the card wrapper
        cards = driver.find_elements(By.CSS_SELECTOR, ".ant-card")
        print(f"Found {len(cards)} cards.")
        
        for i, card in enumerate(cards[:3]):
            print(f"\n--- Card {i} ---")
            print(f"Tag: {card.tag_name}")
            print(f"Class: {card.get_attribute('class')}")
            print(f"HREF: {card.get_attribute('href')}")
            
            # Check parent
            parent = driver.execute_script("return arguments[0].parentNode;", card)
            print(f"Parent Tag: {parent.tag_name}")
            print(f"Parent HREF: {parent.get_attribute('href')}")
            
            # Check for any <a> inside
            inner_links = card.find_elements(By.TAG_NAME, "a")
            for link in inner_links:
                print(f"Inner Link: {link.get_attribute('href')}")

    finally:
        driver.quit()

if __name__ == "__main__":
    find_links()
