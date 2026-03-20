"""
Game License Scraper — API version (NO Selenium/Chrome needed)
Uses the official API at gpttdt-api.abei.gov.vn

Usage:
  python scraper_full.py --quick    # Quick check page 1 only (~2 seconds)
  python scraper_full.py            # Full scrape all pages (~10 seconds)
"""

import json
import os
import logging
import re
import shutil
import glob

from datetime import datetime as dt
import requests

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# === Config ===
API_BASE = "https://gpttdt-api.abei.gov.vn/services/mcrlmtp/api/license"
PAGE_SIZE = 24  # Same as the website's page size
BACKUP_DIR = "backups"
MAX_BACKUPS = 5
DATA_FILE = "data.json"

FILTER_MODEL = {
    "platformCategoryCode": {"type": "equals", "filterType": "text", "filter": "QD_GAME_G1"},
    "ftsValue": {"type": "contains", "filter": "", "filterType": "text"}
}

def backup_data():
    """Creates a timestamped backup of data.json before any write operation."""
    if not os.path.exists(DATA_FILE):
        return None
    
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"data_backup_{timestamp}.json")
    shutil.copy2(DATA_FILE, backup_path)
    logging.info(f"Backup created: {backup_path}")
    
    # Cleanup old backups
    backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "data_backup_*.json")))
    while len(backups) > MAX_BACKUPS:
        oldest = backups.pop(0)
        os.remove(oldest)
        logging.info(f"Removed old backup: {oldest}")
    
    return backup_path


def api_get_count():
    """Get total number of G1 game licenses."""
    r = requests.post(f"{API_BASE}/pivotCount", json={"filterModel": FILTER_MODEL}, timeout=15)
    r.raise_for_status()
    return r.json().get("data", 0)


def api_get_page(start_row, end_row):
    """Fetch a page of game licenses from the API."""
    payload = {
        "startRow": start_row,
        "endRow": end_row,
        "sortModel": [{"sort": "desc", "colId": "validFrom"}],
        "filterModel": FILTER_MODEL
    }
    r = requests.post(f"{API_BASE}/pivotPaging", json=payload, timeout=15)
    r.raise_for_status()
    resp = r.json()
    return resp.get("data", {}).get("data", [])


def parse_api_item(item):
    """Convert API response item to our data.json format."""
    detail = item.get("licenseDetail", {})
    
    # Parse date from ISO format
    valid_from = item.get("validFrom", "")
    date_str = ""
    if valid_from:
        try:
            parsed = dt.fromisoformat(valid_from.replace("+00:00", "+00:00").split("T")[0])
            date_str = parsed.strftime("%d/%m/%Y")
        except (ValueError, AttributeError):
            date_str = ""
    
    # Map status
    cstatus = item.get("cstatus", "")
    status_map = {"valid": "Đang hoạt động", "revoked": "Đã thu hồi", "expired": "Hết hạn"}
    status = status_map.get(cstatus, cstatus)
    
    # Build domain from homepage + website
    domains = []
    if detail.get("gameHomepage"):
        domains.append(detail["gameHomepage"])
    if detail.get("website") and detail["website"] not in domains:
        domains.append(detail["website"])
    domain = ", ".join(domains)
    
    return {
        "id": str(item.get("id", "")),
        "name": detail.get("gameNameVietnam", ""),
        "company": item.get("companyName", ""),
        "license": item.get("licenseNumber", ""),
        "domain": domain,
        "status": status,
        "date": date_str
    }


def merge_data(existing_data, new_data):
    """Merges new data with existing data without losing any games."""
    merged = {}
    
    for g in existing_data:
        gid = g.get("id", "")
        if gid:
            merged[gid] = g
    
    added = 0
    updated = 0
    for g in new_data:
        gid = g.get("id", "")
        if not gid:
            continue
        if gid in merged:
            old = merged[gid]
            if g.get("date") and not old.get("date"):
                merged[gid] = g
                updated += 1
        else:
            merged[gid] = g
            added += 1
    
    result = list(merged.values())
    logging.info(f"Merge complete: {added} new, {updated} updated, {len(result)} total")
    return result


def quick_check():
    """Quick check: fetch page 1 from API, compare with existing data.
    
    Much faster than Selenium (~2 seconds vs ~2+ minutes).
    Returns (new_games_count, total_count) tuple.
    """
    existing_data = []
    known_ids = set()
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
                known_ids = {g.get("id") for g in existing_data if g.get("id")}
        except Exception as e:
            logging.error(f"Quick check: Error loading {DATA_FILE}: {e}")
            return 0, len(existing_data)
    
    logging.info(f"Quick check: {len(known_ids)} known games. Fetching page 1 from API...")
    
    try:
        items = api_get_page(0, PAGE_SIZE)
        logging.info(f"Quick check: API returned {len(items)} items.")
        
        new_items = []
        for item in items:
            game = parse_api_item(item)
            if game["id"] and game["id"] not in known_ids:
                new_items.append(game)
            elif game["id"] in known_ids:
                # Hit a known game, all subsequent are also known
                break
        
        if not new_items:
            logging.info("Quick check: No new games found.")
            return 0, len(existing_data)
        
        # Prepend new games to existing data
        updated_data = new_items + existing_data
        
        # Dedup
        seen_ids = set()
        unique_data = []
        for g in updated_data:
            gid = g.get("id", "")
            if gid and gid not in seen_ids:
                seen_ids.add(gid)
                unique_data.append(g)
            elif not gid:
                unique_data.append(g)
        
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(unique_data, f, indent=2, ensure_ascii=False)
        
        logging.info(f"Quick check: Added {len(new_items)} new games. Total: {len(unique_data)}")
        return len(new_items), len(unique_data)
        
    except Exception as e:
        logging.error(f"Quick check error: {e}")
        return 0, len(existing_data)


def scrape_all():
    """Full scrape: fetch all pages from API. MERGES with existing data."""
    backup_data()
    
    existing_data = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            logging.info(f"Loaded {len(existing_data)} existing games for merge.")
        except Exception as e:
            logging.error(f"Error loading existing data: {e}")
    
    try:
        total = api_get_count()
        logging.info(f"API reports {total} total G1 licenses.")
        
        all_items = []
        for start in range(0, total, PAGE_SIZE):
            end = min(start + PAGE_SIZE, total)
            items = api_get_page(start, end)
            for item in items:
                game = parse_api_item(item)
                if game.get("name"):
                    all_items.append(game)
            logging.info(f"Fetched {len(all_items)}/{total} items...")
        
        # Dedup scraped items
        seen_ids = set()
        unique_items = []
        for item in all_items:
            gid = item.get("id", "")
            if gid and gid not in seen_ids:
                seen_ids.add(gid)
                unique_items.append(item)
        
        # Merge with existing
        merged = merge_data(existing_data, unique_items)
        
        # Sort by date (newest first)
        def parse_date(g):
            try:
                return dt.strptime(g.get('date', ''), '%d/%m/%Y')
            except (ValueError, TypeError):
                return dt.min
        merged.sort(key=parse_date, reverse=True)
        
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        logging.info(f"Final: {len(merged)} unique items saved (was {len(existing_data)})")
        
    except Exception as e:
        logging.error(f"Full scrape error: {e}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        new_count, total = quick_check()
        print(f"New: {new_count}, Total: {total}")
    else:
        scrape_all()
