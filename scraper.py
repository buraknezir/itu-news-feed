import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
import time
from datetime import datetime

DEPARTMENTS = [
    "https://yurtburs.itu.edu.tr/haberler",
    "https://ydy.itu.edu.tr/haberler",
    "https://kim.itu.edu.tr/haberler",
    # Add more department URLs here
]

# Set the cutoff date (inclusive)
MIN_DATE_STR = "2026-08-01"

TR_MONTHS = {
    "Oca": "01", "Şub": "02", "Mar": "03", "Nis": "04",
    "May": "05", "Haz": "06", "Tem": "07", "Ağu": "08",
    "Eyl": "09", "Eki": "10", "Kas": "11", "Ara": "12"
}

def parse_date(date_str):
    clean = date_str.replace(" (?)", "").strip()
    parts = clean.split()
    if len(parts) == 3:
        day, month_abbr, year = parts
        month = TR_MONTHS.get(month_abbr, "01")
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    return "1970-01-01"

def fetch_news(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return []

    base_domain = "/".join(url.split("/")[:3])
    soup = BeautifulSoup(response.text, 'html.parser')
    news_items = []

    for row in soup.select('div.row.type2'):
        date_div = row.select_one('div.date')
        if not date_div: continue
        
        date_text = date_div.get_text(" ", strip=True)
        sortable_date = parse_date(date_text)
        
        # FILTER: Only include news from August 2026 onwards
        if sortable_date >= MIN_DATE_STR:
            link_tag = row.select_one('div.contents h6 a') or row.select_one('h6 a')
            if link_tag:
                news_items.append({
                    'date': sortable_date,
                    'display_date': date_text.replace(" (?)", ""),
                    'title': link_tag.text.strip(),
                    'link': urljoin(base_domain, link_tag.get('href'))
                })
    return news_items

def main():
    all_news = []
    print("Starting scrape...")
    for dept_url in DEPARTMENTS:
        print(f"Fetching: {dept_url}")
        all_news.extend(fetch_news(dept_url))
        time.sleep(1)

    # Sort newest first
    all_news.sort(key=lambda x: x['date'], reverse=True)
    
    # Save to news.json
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(all_news, f, ensure_ascii=False, indent=2)
    
    print(f"Done! Saved {len(all_news)} items to news.json")

if __name__ == "__main__":
    main()