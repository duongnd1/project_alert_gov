"""
recover_data.py - One-time script to recover missing games.

Runs a full scrape and MERGES results with existing data.json.
No data will be lost - only new games are added.
"""
import sys
import os

# Import from scraper_full
from scraper_full import (
    create_driver, phase1_collect_links, phase2_collect_dates,
    backup_data, merge_data
)
from datetime import datetime as dt
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def recover():
    # Step 1: Backup current data
    logging.info("=" * 50)
    logging.info("RECOVERY: Starting data recovery...")
    logging.info("=" * 50)
    
    backup_path = backup_data()
    if backup_path:
        logging.info(f"Current data backed up to: {backup_path}")
    
    # Step 2: Load existing data
    existing_data = []
    if os.path.exists("data.json"):
        with open("data.json", "r", encoding="utf-8") as f:
            existing_data = json.load(f)
    logging.info(f"Existing data: {len(existing_data)} games")
    
    # Step 3: Run full scrape
    logging.info("Starting full scrape (Phase 1 + Phase 2)...")
    driver = create_driver()
    
    try:
        all_items = phase1_collect_links(driver)
        logging.info(f"Phase 1 collected {len(all_items)} items from listing pages")
        
        final_items = phase2_collect_dates(driver, all_items)
        logging.info(f"Phase 2 collected dates for {len(final_items)} items (2025+)")
        
        # Dedup scraped items
        seen_ids = set()
        unique_items = []
        for item in final_items:
            gid = item.get("id", "")
            if gid and gid not in seen_ids:
                seen_ids.add(gid)
                unique_items.append(item)
        
        # Step 4: MERGE with existing data
        merged = merge_data(existing_data, unique_items)
        
        # Sort by date (newest first)
        def parse_date(g):
            try:
                return dt.strptime(g.get('date', ''), '%d/%m/%Y')
            except (ValueError, TypeError):
                return dt.min
        merged.sort(key=parse_date, reverse=True)
        
        # Step 5: Save
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        
        logging.info("=" * 50)
        logging.info(f"RECOVERY COMPLETE!")
        logging.info(f"Before: {len(existing_data)} games")
        logging.info(f"After:  {len(merged)} games")
        logging.info(f"Added:  {len(merged) - len(existing_data)} new games")
        logging.info("=" * 50)
        
    except Exception as e:
        logging.error(f"Recovery error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    recover()
