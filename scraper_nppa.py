import json
from bs4 import BeautifulSoup
import os

# Define the paths for the manual HTML dumps
LIST_HTML_PATH = "nppa_list.html"
DETAIL_HTML_PATH = "nppa_detail.html"
OUTPUT_JSON_PATH = "nppa_data.json"

def parse_list_page(html_content):
    """Parses the NPPA announcement list HTML and extracts links/titles."""
    soup = BeautifulSoup(html_content, 'html.parser')
    announcements = []
    
    # Typically they are in <ul class="news_list"> -> <li> -> <a>
    # But we will use broad selectors to be safe if they change slightly
    list_items = soup.select('.news_list li')
    if not list_items:
        # Fallback broad selector
        list_items = soup.find_all('li')
        
    for item in list_items:
        a_tag = item.find('a')
        date_span = item.find('span')
        
        if a_tag and a_tag.get('href'):
            title = a_tag.text.strip()
            # Handle relative links by prefixing the domain
            link = a_tag['href']
            if not link.startswith('http'):
                # Handle edge cases where href is like "./yxspbgxx/..."
                if link.startswith('./'):
                    link = 'https://www.nppa.gov.cn/bsfw/jggs/yxspjg' + link[1:]
                else:
                    link = 'https://www.nppa.gov.cn' + link 

            date_str = date_span.text.strip() if date_span else ""
            
            # Very basic filter to only grab game approval titles (they usually contains these keywords)
            if "审批" in title or "游戏" in title:
                announcements.append({
                    "title": title,
                    "link": link,
                    "date": date_str,
                    "games": [] # To be filled in Phase 2
                })
                
    return announcements

def parse_detail_page(html_content):
    """Parses an NPPA announcement detail HTML and extracts the game table."""
    soup = BeautifulSoup(html_content, 'html.parser')
    games = []
    
    # NPPA tables are usually simple <table>
    table = soup.find('table')
    if not table:
        print("No table found in the detail HTML.")
        return games
        
    rows = table.find_all('tr')
    
    # Usually the first row is headers. We'll skip it and parse the rest.
    # NPPA tables can vary, but generally: 序号 (Serial), 名称 (Name), 申报类别 (Platform/Category), 出版单位 (Publisher), 运营单位 (Operator), etc.
    for row in rows[1:]:
        cols = row.find_all(['td', 'th'])
        cols = [c.text.strip() for c in cols]
        
        # We need at least 5 columns to figure out basic game info
        if len(cols) >= 5:
            # We will use generic indexing based on the pattern we saw in testing:
            # [0] Serial, [1] Name, [2] Category/Platform, [3] Publisher, [4] Operator/Changes
            games.append({
                "serial": cols[0],
                "name": cols[1],
                "platform": cols[2], # 申报类别
                "publisher": cols[3], # 出版单位
                "operator": cols[4]   # 运营单位 / 变更信息
            })
            
    return games

def main():
    print("--- NPPA Offline Scraper ---")
    
    # 1. Parse List
    if not os.path.exists(LIST_HTML_PATH):
        print(f"Error: {LIST_HTML_PATH} not found. Please create it and paste the list page HTML inside.")
        return
        
    with open(LIST_HTML_PATH, 'r', encoding='utf-8') as f:
        list_html = f.read()
        
    print(f"Parsing {LIST_HTML_PATH}...")
    announcements = parse_list_page(list_html)
    print(f"Found {len(announcements)} announcements in the list.")
    
    for i, ann in enumerate(announcements[:5]): # Show top 5
        print(f"  {i+1}. {ann['title']} ({ann['date']})")
    
    # 2. Parse Detail (Optional, only if the user provided it)
    if os.path.exists(DETAIL_HTML_PATH):
        with open(DETAIL_HTML_PATH, 'r', encoding='utf-8') as f:
            detail_html = f.read()
            
        if len(detail_html.strip()) > 50: # Ensure it's not our empty placeholder
            print(f"\nParsing {DETAIL_HTML_PATH}...")
            games = parse_detail_page(detail_html)
            print(f"Extracted {len(games)} games from the detail HTML.")
            
            # For demonstration, we'll attach this detailed game list to the FIRST announcement in our list
            if announcements:
                announcements[0]['games'] = games
                print(f"Attached these {len(games)} games to the announcement: '{announcements[0]['title']}'")
        else:
             print(f"\n{DETAIL_HTML_PATH} is empty. Skipping detail parsing.")
    
    # 3. Save Output
    print(f"\nSaving data to {OUTPUT_JSON_PATH}...")
    with open(OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(announcements, f, indent=2, ensure_ascii=False)
        
    print("Done! You can now review nppa_data.json")

if __name__ == "__main__":
    main()
