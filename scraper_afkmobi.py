"""
AFKMobi Game Scraper — Quét danh sách game sắp ra mắt từ afkmobi.com/buzz-game
Sử dụng requests + BeautifulSoup (không cần Selenium).
"""

import json
import os
import sys
import logging
import re
from datetime import datetime
from bs4 import BeautifulSoup
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BASE_URL = "https://afkmobi.com/buzz-game"
DATA_FILE = "afkmobi_data.json"
MIN_YEAR = 2026

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}


def load_existing_data():
    """Load existing AFKMobi data from JSON file."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading {DATA_FILE}: {e}")
    return []


def save_data(data):
    """Save data to JSON file."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logging.info(f"Saved {len(data)} games to {DATA_FILE}")


def parse_date(date_str):
    """Parse date string from AFKMobi format.
    Supports:
    - DD-MM-YYYY HH:mm
    - DD-MM-YYYY
    - Tháng MM-YYYY
    - MM-YYYY
    """
    s = date_str.strip()
    # Clean up "Tháng " prefix if exists
    s = re.sub(r'^[Tt]h\u00e1ng\s+', '', s)
    
    try:
        return datetime.strptime(s, "%d-%m-%Y %H:%M")
    except (ValueError, AttributeError):
        try:
            return datetime.strptime(s, "%d-%m-%Y")
        except (ValueError, AttributeError):
            try:
                # Month-only format
                dt = datetime.strptime(s, "%m-%Y")
                # Default to 1st of month
                return dt.replace(day=1)
            except (ValueError, AttributeError):
                return None


def extract_game_id(url):
    """Extract game slug/ID from AFKMobi URL."""
    # https://afkmobi.com/game/bleach-cong-huong-linh-hon -> bleach-cong-huong-linh-hon
    if "/game/" in url:
        return url.split("/game/")[-1].strip("/").split("?")[0]
    return ""


def scrape_page(page_num):
    """Scrape a single page and return list of game dicts."""
    url = f"{BASE_URL}?page={page_num}"
    logging.info(f"Scraping page {page_num}: {url}")
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        resp.encoding = "utf-8"  # Ensure Vietnamese text is decoded correctly
    except requests.RequestException as e:
        logging.error(f"Failed to fetch page {page_num}: {e}")
        return [], False  # games, should_continue
    
    soup = BeautifulSoup(resp.text, "html.parser")
    games = []
    oldest_year = 9999
    
    # Find all game entries
    entries = soup.select(".entry-aside.clearfix")
    if not entries:
        # Fallback: try alternative selector
        entries = soup.select(".entry-aside")
    
    logging.info(f"Page {page_num}: Found {len(entries)} entries")
    
    for entry in entries:
        try:
            # Game name & link
            title_el = entry.select_one(".entry-title a")
            if not title_el:
                continue
            
            name = title_el.get_text(strip=True)
            detail_url = title_el.get("href", "")
            if detail_url and not detail_url.startswith("http"):
                detail_url = "https://afkmobi.com" + detail_url
            
            game_id = extract_game_id(detail_url)
            
            # Release date — validate format DD-MM-YYYY or MM-YYYY
            date_el = entry.select_one(".entry-date")
            release_date = date_el.get_text(strip=True) if date_el else ""
            
            # Identify month-only (approximate) dates
            is_approximate = False
            # Check for DD-MM-YYYY vs MM-YYYY
            if re.search(r'^\d{2}-\d{2}-\d{4}', release_date):
                is_approximate = False
            elif re.search(r'(?:[Tt]h\u00e1ng\s+)?\d{2}-\d{4}$', release_date):
                is_approximate = True
            else:
                logging.debug(f"Skipping '{name}': invalid date format '{release_date}'")
                continue
            
            # Check year
            parsed_dt = parse_date(release_date)
            if parsed_dt:
                if parsed_dt.year < MIN_YEAR:
                    oldest_year = min(oldest_year, parsed_dt.year)
                    continue  # Skip games before MIN_YEAR
                oldest_year = min(oldest_year, parsed_dt.year)
            
            # Genre/category
            genre = ""
            genre_el = entry.select_one(".entry-content p")
            if genre_el:
                genre = genre_el.get_text(strip=True)
            
            # Status tags (REG, CBT, OBT, GIFT, etc.)
            tags = []
            tag_els = entry.select(".entry-meta span")
            for tag_el in tag_els:
                tag_text = tag_el.get_text(strip=True)
                if tag_text:
                    tags.append(tag_text)
            
            # Thumbnail image
            img_el = entry.select_one(".img-holder img")
            image_url = ""
            if img_el:
                image_url = img_el.get("src", "") or img_el.get("data-src", "")
            
            game = {
                "id": game_id,
                "name": name,
                "genre": genre,
                "release_date": release_date,
                "is_approximate": is_approximate,
                "status_tags": tags,
                "url": detail_url,
                "image": image_url,
            }
            games.append(game)
            
        except Exception as e:
            logging.warning(f"Error parsing entry on page {page_num}: {e}")
            continue
    
    # Determine if we should continue to next page
    # Stop if all games on this page are before MIN_YEAR
    has_next = soup.select_one("a.next.page-numbers") is not None
    should_continue = has_next and oldest_year >= MIN_YEAR
    
    return games, should_continue


def scrape_all_pages():
    """Full scrape: iterate through all pages until year < MIN_YEAR.
    
    Returns list of all scraped games (from 2026 onwards).
    """
    all_games = []
    page = 1
    max_pages = 100  # Safety limit
    
    while page <= max_pages:
        games, should_continue = scrape_page(page)
        all_games.extend(games)
        
        if not should_continue:
            logging.info(f"Stopping at page {page} (no more relevant data or last page)")
            break
        
        page += 1
    
    # Deduplicate by game ID
    seen_ids = set()
    unique_games = []
    for g in all_games:
        gid = g.get("id", "")
        if gid and gid not in seen_ids:
            seen_ids.add(gid)
            unique_games.append(g)
        elif not gid:
            unique_games.append(g)
    
    # Sort by release date (newest first)
    def sort_key(g):
        dt = parse_date(g.get("release_date", ""))
        return dt if dt else datetime.min
    
    unique_games.sort(key=sort_key, reverse=True)
    
    logging.info(f"Full scrape complete: {len(unique_games)} unique games from {MIN_YEAR}+")
    return unique_games


def quick_check():
    """Quick check: scrape only page 1, compare with existing data.
    
    Returns (new_games_list, total_count).
    """
    existing = load_existing_data()
    known_ids = {g.get("id") for g in existing if g.get("id")}
    
    logging.info(f"Quick check: {len(known_ids)} known games in database.")
    
    page1_games, _ = scrape_page(1)
    
    new_games = []
    for g in page1_games:
        gid = g.get("id", "")
        if gid and gid not in known_ids:
            new_games.append(g)
    
    if not new_games:
        logging.info("Quick check: No new games found.")
        return [], len(existing)
    
    # Prepend new games to existing data
    updated = new_games + existing
    
    # Deduplicate
    seen_ids = set()
    unique = []
    for g in updated:
        gid = g.get("id", "")
        if gid and gid not in seen_ids:
            seen_ids.add(gid)
            unique.append(g)
        elif not gid:
            unique.append(g)
    
    save_data(unique)
    logging.info(f"Quick check: Found {len(new_games)} new games. Total: {len(unique)}")
    return new_games, len(unique)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        new_games, total = quick_check()
        print(f"New: {len(new_games)}, Total: {total}")
        if new_games:
            print("\nNew games found:")
            for g in new_games:
                print(f"  🎮 {g['name']} | 📅 {g.get('release_date', 'N/A')} | {g.get('url', '')}")
    else:
        games = scrape_all_pages()
        save_data(games)
        print(f"\nTotal: {len(games)} games saved to {DATA_FILE}")
