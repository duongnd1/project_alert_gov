from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import os
import time
import logging
import re

from datetime import datetime as dt
import glob
import shutil

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BACKUP_DIR = "backups"
MAX_BACKUPS = 5

def backup_data():
    """Creates a timestamped backup of data.json before any write operation.
    Keeps only the latest MAX_BACKUPS files."""
    if not os.path.exists("data.json"):
        return None
    
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"data_backup_{timestamp}.json")
    shutil.copy2("data.json", backup_path)
    logging.info(f"Backup created: {backup_path}")
    
    # Cleanup old backups
    backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "data_backup_*.json")))
    while len(backups) > MAX_BACKUPS:
        oldest = backups.pop(0)
        os.remove(oldest)
        logging.info(f"Removed old backup: {oldest}")
    
    return backup_path

def merge_data(existing_data, new_data):
    """Merges new scraped data with existing data without losing any games.
    Uses game ID as the unique key. New data updates existing entries."""
    merged = {}
    
    # First, add all existing data
    for g in existing_data:
        gid = g.get("id", "")
        if gid:
            merged[gid] = g
    
    # Then merge new data (update existing, add new)
    added = 0
    updated = 0
    for g in new_data:
        gid = g.get("id", "")
        if not gid:
            continue
        if gid in merged:
            # Update only if new data has more info (e.g. has date)
            old = merged[gid]
            if g.get("date") and not old.get("date"):
                merged[gid] = g
                updated += 1
            elif g.get("date") and old.get("date"):
                # Keep the existing one (already has date)
                pass
            elif not old.get("date") and not g.get("date"):
                pass
        else:
            merged[gid] = g
            added += 1
    
    result = list(merged.values())
    logging.info(f"Merge complete: {added} new, {updated} updated, {len(result)} total")
    return result

def create_driver():
    """Creates a new Chrome driver instance."""
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
    return driver

def phase1_collect_links(driver):
    """Phase 1: Collect all card links and basic info from listing pages."""
    url = "https://giayphep.abei.gov.vn/g1"
    logging.info(f"Phase 1: Collecting links from {url}...")
    driver.get(url)
    
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ant-card-body")))
    time.sleep(3)
    
    all_items = []
    page_num = 1
    
    while True:
        logging.info(f"Phase 1 - Page {page_num}...")
        
        # Find all cards
        cards = driver.find_elements(By.CSS_SELECTOR, ".ant-card")
        
        for card in cards:
            try:
                # Get ID from parent <a> tag
                parent = driver.execute_script("return arguments[0].parentNode;", card)
                href = parent.get_attribute("href") or ""
                
                text = card.text.split('\n')
                
                game_id = ""
                if "/g1/" in href:
                    game_id = href.split("/g1/")[-1].split("?")[0]
                
                if len(text) >= 4:
                    item = {
                        "id": game_id,
                        "name": text[0],
                        "company": text[2] if len(text) > 2 else "",
                        "license": text[3] if len(text) > 3 else "",
                        "domain": text[4] if len(text) > 4 else "",
                        "status": text[5] if len(text) > 5 else "",
                        "date": ""
                    }
                    all_items.append(item)
            except Exception as e:
                pass
        
        # Navigate to next page
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
            next_btn = driver.find_element(By.CSS_SELECTOR, "li.ant-pagination-next")
            if "ant-pagination-disabled" in next_btn.get_attribute("class"):
                logging.info("Phase 1: Reached last page.")
                break
            
            driver.execute_script("arguments[0].click();", next_btn)
            page_num += 1
            time.sleep(3)
            
        except Exception as e:
            logging.error(f"Phase 1 navigation error: {e}")
            break
    
    logging.info(f"Phase 1 complete. Collected {len(all_items)} items.")
    return all_items

def phase2_collect_dates(driver, items):
    """Phase 2: Visit each detail page to get the date. Stop when year < 2025."""
    logging.info(f"Phase 2: Collecting dates for {len(items)} items (Target: 2025+)...")
    
    items_with_id = [item for item in items if item.get("id")]
    final_items = []
    
    for i, item in enumerate(items_with_id):
        try:
            detail_url = f"https://giayphep.abei.gov.vn/g1/{item['id']}"
            driver.get(detail_url)
            time.sleep(2)
            
            body_text = driver.find_element(By.TAG_NAME, "body").text
            
            # Look for date pattern (DD/MM/YYYY)
            date_match = re.search(r'(\d{2}/\d{2}/\d{4})', body_text)
            if date_match:
                date_str = date_match.group(1)
                item["date"] = date_str
                
                # Check year
                year = int(date_str.split("/")[-1])
                if year < 2025:
                    logging.info(f"Phase 2: Reached year {year} for ID {item['id']}. Skipping, but continuing search.")
                    continue # IMPORTANT: Changed from break to continue to avoid stopping the whole process on unordered dates
            
            final_items.append(item)
            
            if (i + 1) % 10 == 0:
                logging.info(f"Phase 2: Processed {i + 1} items...")
                # Intermediate save
                with open("data.json", "w", encoding="utf-8") as f:
                    json.dump(final_items, f, indent=2, ensure_ascii=False)
                    
        except Exception as e:
            logging.error(f"Phase 2 error for ID {item['id']}: {e}")
            continue
    
    logging.info(f"Phase 2 complete. Collected {len(final_items)} items from 2025+.")
    return final_items

def quick_check():
    """Quick check: only scan page 1 for new games, compare with existing data.
    
    Much faster than scrape_all() (~30s vs ~18min).
    Returns (new_games_count, total_count) tuple.
    """
    # Load existing data to find the latest known game ID
    existing_data = []
    known_ids = set()
    if os.path.exists("data.json"):
        try:
            with open("data.json", "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                known_ids = {g.get("id") for g in existing_data if g.get("id")}
        except Exception as e:
            logging.error(f"Quick check: Error loading data.json: {e}")
            return 0, len(existing_data)
    
    latest_id = existing_data[0].get("id") if existing_data else None
    logging.info(f"Quick check: Latest known ID = {latest_id}, {len(known_ids)} known games.")
    
    driver = create_driver()
    new_items = []
    
    try:
        url = "https://giayphep.abei.gov.vn/g1"
        driver.get(url)
        
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ant-card-body")))
        time.sleep(3)
        
        # Only check page 1
        cards = driver.find_elements(By.CSS_SELECTOR, ".ant-card")
        logging.info(f"Quick check: Found {len(cards)} cards on page 1.")
        
        for card in cards:
            try:
                parent = driver.execute_script("return arguments[0].parentNode;", card)
                href = parent.get_attribute("href") or ""
                text = card.text.split('\n')
                
                game_id = ""
                if "/g1/" in href:
                    game_id = href.split("/g1/")[-1].split("?")[0]
                
                # Stop if we hit a known game ID
                if game_id and game_id in known_ids:
                    logging.info(f"Quick check: Hit known game ID {game_id}. Stopping.")
                    break
                
                if len(text) >= 4 and game_id:
                    item = {
                        "id": game_id,
                        "name": text[0],
                        "company": text[2] if len(text) > 2 else "",
                        "license": text[3] if len(text) > 3 else "",
                        "domain": text[4] if len(text) > 4 else "",
                        "status": text[5] if len(text) > 5 else "",
                        "date": ""
                    }
                    new_items.append(item)
            except Exception:
                pass
        
        if not new_items:
            logging.info("Quick check: No new games found.")
            return 0, len(existing_data)
        
        # Get dates for new items only
        logging.info(f"Quick check: Found {len(new_items)} new games! Getting dates...")
        for item in new_items:
            try:
                detail_url = f"https://giayphep.abei.gov.vn/g1/{item['id']}"
                driver.get(detail_url)
                time.sleep(2)
                body_text = driver.find_element(By.TAG_NAME, "body").text
                date_match = re.search(r'(\d{2}/\d{2}/\d{4})', body_text)
                if date_match:
                    item["date"] = date_match.group(1)
            except Exception as e:
                logging.error(f"Quick check: Error getting date for {item['id']}: {e}")
        
        # Prepend new games to existing data
        updated_data = new_items + existing_data
        
        # Dedup (safety)
        seen_ids = set()
        unique_data = []
        for g in updated_data:
            gid = g.get("id", "")
            if gid and gid not in seen_ids:
                seen_ids.add(gid)
                unique_data.append(g)
            elif not gid:
                unique_data.append(g)
        
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(unique_data, f, indent=2, ensure_ascii=False)
        
        logging.info(f"Quick check: Added {len(new_items)} new games. Total: {len(unique_data)}")
        return len(new_items), len(unique_data)
        
    except Exception as e:
        logging.error(f"Quick check error: {e}")
        return 0, len(existing_data)
    finally:
        driver.quit()


def scrape_all():
    """Full scrape: re-crawl all pages. MERGES with existing data (never overwrites)."""
    # Backup before doing anything
    backup_data()
    
    # Load existing data for merge
    existing_data = []
    if os.path.exists("data.json"):
        try:
            with open("data.json", "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            logging.info(f"Loaded {len(existing_data)} existing games for merge.")
        except Exception as e:
            logging.error(f"Error loading existing data: {e}")
    
    driver = create_driver()
    
    try:
        # Phase 1: Collect all links
        all_items = phase1_collect_links(driver)
        
        # Save temporary list
        with open("data_temp.json", "w", encoding="utf-8") as f:
            json.dump(all_items, f, indent=2, ensure_ascii=False)
            
        # Phase 2: Deep scrape for dates (2025+)
        final_items = phase2_collect_dates(driver, all_items)
        
        # Deduplicate scraped items
        seen_ids = set()
        unique_items = []
        for item in final_items:
            game_id = item.get("id", "")
            if game_id and game_id not in seen_ids:
                seen_ids.add(game_id)
                unique_items.append(item)
            elif not game_id:
                unique_items.append(item)
        
        removed = len(final_items) - len(unique_items)
        if removed > 0:
            logging.info(f"Dedup: removed {removed} duplicate entries.")
        
        # MERGE with existing data instead of overwriting
        merged = merge_data(existing_data, unique_items)
        
        # Sort by date (newest first)
        def parse_date(g):
            try:
                return dt.strptime(g.get('date', ''), '%d/%m/%Y')
            except (ValueError, TypeError):
                return dt.min
        merged.sort(key=parse_date, reverse=True)
        
        # Save final
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        logging.info(f"Final results saved to data.json ({len(merged)} unique items, was {len(existing_data)})")
        
    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        driver.quit()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        new_count, total = quick_check()
        print(f"New: {new_count}, Total: {total}")
    else:
        scrape_all()

