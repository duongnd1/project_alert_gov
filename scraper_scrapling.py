"""
scraper_scrapling.py — Test scraper using Scrapling DynamicFetcher
Replaces Selenium with Playwright via Scrapling for faster scraping.

SAFE: Does NOT touch data.json (saves to data_scrapling_test.json).
Compare speed with scraper_full.py (Selenium).
"""
import json
import re
import time
import logging
import argparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BASE_URL = "https://giayphep.abei.gov.vn"
OUTPUT_FILE = "data_scrapling_test.json"  # Separate file — data.json untouched!

def scrape_listing_page(page):
    """Extract game cards from a listing page (already loaded)."""
    items = []
    cards = page.css(".ant-card")
    for card in cards:
        try:
            # Get the parent <a> link → extract ID
            parent = card.parent
            href = parent.attrib.get("href", "") if parent else ""
            game_id = ""
            if "/g1/" in href:
                game_id = href.split("/g1/")[-1].split("?")[0]

            lines = card.get_text(separator="\n").strip().split("\n")
            lines = [l.strip() for l in lines if l.strip()]

            if len(lines) >= 4:
                items.append({
                    "id": game_id,
                    "name": lines[0],
                    "company": lines[2] if len(lines) > 2 else "",
                    "license": lines[3] if len(lines) > 3 else "",
                    "domain": lines[4] if len(lines) > 4 else "",
                    "status": lines[5] if len(lines) > 5 else "",
                    "date": ""
                })
        except Exception as e:
            logging.debug(f"Card parse error: {e}")
    return items


def phase1_collect_links(fetcher, max_pages=None):
    """Phase 1: Collect all game cards from listing pages."""
    logging.info("Phase 1: Loading listing page...")
    t0 = time.time()

    url = f"{BASE_URL}/g1"
    all_items = []
    page_num = 1

    # First load with network_idle
    page = fetcher.fetch(url, headless=True, network_idle=True, timeout=30000)
    
    while True:
        logging.info(f"Phase 1 - Page {page_num}...")
        items = scrape_listing_page(page)
        all_items.extend(items)
        logging.info(f"  Got {len(items)} cards. Total so far: {len(all_items)}")

        if max_pages and page_num >= max_pages:
            logging.info(f"Reached max_pages={max_pages}, stopping Phase 1.")
            break

        # Check if next button is disabled
        next_btn = page.css("li.ant-pagination-next")
        if not next_btn:
            logging.info("No next button — reached last page.")
            break

        classes = next_btn[0].attrib.get("class", "")
        if "ant-pagination-disabled" in classes:
            logging.info("Phase 1: Last page reached.")
            break

        # Navigate to next page by URL
        page_num += 1
        page = fetcher.fetch(
            f"{url}?page={page_num}", 
            headless=True, network_idle=True, timeout=30000
        )
        # Check if page actually changed (some SPAs ignore page param)
        items_check = page.css(".ant-card")
        if not items_check:
            logging.info("No cards on next page — likely reached end.")
            break

    elapsed = time.time() - t0
    logging.info(f"Phase 1 complete in {elapsed:.1f}s. {len(all_items)} items from {page_num} pages.")
    logging.info(f"  Average: {elapsed/max(page_num,1):.1f}s per page")
    return all_items, page_num, elapsed


def phase2_collect_dates(fetcher, items, stop_before_year=None):
    """Phase 2: Visit each detail page to collect date."""
    logging.info(f"Phase 2: Collecting dates for {len(items)} items...")
    t0 = time.time()
    final_items = []
    items_with_id = [g for g in items if g.get("id")]

    for i, item in enumerate(items_with_id):
        try:
            detail_url = f"{BASE_URL}/g1/{item['id']}"
            page = fetcher.fetch(detail_url, headless=True, network_idle=True, timeout=20000)
            body = page.get_text()

            date_match = re.search(r'(\d{2}/\d{2}/\d{4})', body)
            if date_match:
                date_str = date_match.group(1)
                item["date"] = date_str
                year = int(date_str.split("/")[-1])
                if stop_before_year and year < stop_before_year:
                    logging.info(f"Phase 2: Reached year {year}, stopping.")
                    break

            final_items.append(item)

            if (i + 1) % 10 == 0:
                elapsed_so_far = time.time() - t0
                avg = elapsed_so_far / (i + 1)
                logging.info(f"Phase 2: {i+1}/{len(items_with_id)} | avg {avg:.1f}s/game | est remaining: {avg*(len(items_with_id)-i-1)/60:.1f} min")

        except Exception as e:
            logging.error(f"Phase 2 error for ID {item.get('id')}: {e}")
            continue

    elapsed = time.time() - t0
    avg = elapsed / max(len(final_items), 1)
    logging.info(f"Phase 2 complete in {elapsed:.1f}s. {len(final_items)} games. Avg: {avg:.2f}s/game")
    return final_items, elapsed


def main():
    parser = argparse.ArgumentParser(description="Scrapling test scraper")
    parser.add_argument("--pages", type=int, default=3, help="Max listing pages to scrape (default: 3 for speed test)")
    parser.add_argument("--full", action="store_true", help="Full scrape (all pages, all years)")
    parser.add_argument("--year", type=int, default=2025, help="Stop when year < this (default: 2025)")
    args = parser.parse_args()

    from scrapling.fetchers import DynamicFetcher
    fetcher = DynamicFetcher()

    
    # Phase 1: Listing pages
    max_pages = None if args.full else args.pages
    items, num_pages, p1_time = phase1_collect_links(fetcher, max_pages=max_pages)

    if not items:
        logging.error("No items found in Phase 1!")
        return

    # Phase 2: Detail pages  
    stop_year = None if args.full else args.year
    final_items, p2_time = phase2_collect_dates(fetcher, items, stop_before_year=stop_year)

    # Save to separate test file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_items, f, indent=2, ensure_ascii=False)

    total = time.time() - total_start
    logging.info("\n" + "=" * 50)
    logging.info("SPEED TEST RESULTS:")
    logging.info(f"  Pages scraped: {num_pages}")
    logging.info(f"  Games collected: {len(final_items)}")
    logging.info(f"  Phase 1 (listing): {p1_time:.1f}s")
    logging.info(f"  Phase 2 (details): {p2_time:.1f}s")
    logging.info(f"  TOTAL: {total:.1f}s ({total/60:.1f} min)")
    logging.info(f"  Saved to: {OUTPUT_FILE}")
    logging.info("=" * 50)

    if not args.full:
        # Extrapolate full time estimate
        games_per_page = len(items) / max(num_pages, 1)
        estimated_total_pages = 250
        estimated_total_games = games_per_page * estimated_total_pages
        est_p1 = (p1_time / max(num_pages, 1)) * estimated_total_pages
        est_p2 = (p2_time / max(len(final_items), 1)) * estimated_total_games
        est_total = est_p1 + est_p2
        logging.info(f"\nEstimated FULL scrape time: {est_total:.0f}s ({est_total/3600:.1f} hours)")


if __name__ == "__main__":
    main()
