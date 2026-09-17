import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
import time
import re
from datetime import datetime, timezone

DEPARTMENTS = [
    {"name": "Burslar ve Yurtlar Koordinatörlüğü", "url": "https://yurtburs.itu.edu.tr/haberler"},
    {"name": "Yabancı Diller Yüksekokulu", "url": "https://ydy.itu.edu.tr/haberler"},
    {"name": "Kart İşlem Merkezi", "url": "https://kim.itu.edu.tr/haberler"},
]

MIN_DATE_STR = "2026-08-15"

TR_MONTHS = {
    "Oca": "01", "Şub": "02", "Mar": "03", "Nis": "04",
    "May": "05", "Haz": "06", "Tem": "07", "Ağu": "08",
    "Eyl": "09", "Eki": "10", "Kas": "11", "Ara": "12"
}

DATE_PATTERNS = [
    re.compile(r'(\d{1,2})\s+(Oca|Şub|Mar|Nis|May|Haz|Tem|Ağu|Eyl|Eki|Kas|Ara)\s+(\d{4})'),
    re.compile(r'(\d{1,2})\.(\d{2})\.(\d{4})'),
    re.compile(r'(\d{4})-(\d{2})-(\d{2})'),
]

def parse_date(date_str):
    if not date_str:
        return None
    for pattern in DATE_PATTERNS:
        match = pattern.search(date_str)
        if match:
            groups = match.groups()
            if len(groups) == 3:
                if groups[1] in TR_MONTHS:
                    day, month_abbr, year = groups
                    month = TR_MONTHS[month_abbr]
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                elif len(groups[0]) == 4:
                    year, month, day = groups
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                else:
                    day, month, year = groups
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    return None

def extract_news_items(soup, base_domain):
    news_items = []

    item_selectors = [
        'div.news-list__item',
        'div.row.type2',
        'article',
        'div.news-item',
        'div.haber-item',
        'div.card',
    ]

    items_found = []
    for sel in item_selectors:
        found = soup.select(sel)
        if found:
            items_found.extend(found)
            break

    if not items_found:
        for elem in soup.find_all(['div', 'article', 'li']):
            link = elem.find('a', href=True)
            if link and re.search(r'\d{1,2}\s+(Oca|Şub|Mar|Nis|May|Haz|Tem|Ağu|Eyl|Eki|Kas|Ara)', elem.get_text()):
                items_found.append(elem)

    seen = set()
    unique_items = []
    for item in items_found:
        item_id = id(item)
        if item_id not in seen:
            seen.add(item_id)
            unique_items.append(item)

    for item in unique_items:
        # --- Extract title and link ---
        title = None
        link = None

        for tag in ['h2', 'h3', 'h4', 'h5', 'h6']:
            heading = item.select_one(tag)
            if heading:
                link_tag = heading.find('a', href=True) or item.find('a', href=True)
                if link_tag:
                    title = heading.get_text(strip=True)
                    link = link_tag.get('href')
                    break

        if not title or not link:
            for a in item.find_all('a', href=True):
                text = a.get_text(strip=True)
                if text and len(text) > 5:
                    href = a.get('href', '')
                    if '/haber' in href or '/news' in href or '/detay' in href:
                        title = text
                        link = href
                        break

        if not title or not link:
            continue

        # --- Extract date (only the matched portion) ---
        matched_date_str = None

        # Prefer more specific date containers first (before generic card__footer)
        date_selectors = [
            'div.card__footer-left',   # YDY: only the left half with the date
            'div.date',                # Yurtburs
            'span.date',
            'div.news-date',
            'time',
            'div.card__footer',        # YDY fallback (may include button)
            'div.meta',
        ]

        for dsel in date_selectors:
            date_elem = item.select_one(dsel)
            if date_elem:
                text = date_elem.get_text(" ", strip=True)
                for pattern in DATE_PATTERNS:
                    match = pattern.search(text)
                    if match:
                        matched_date_str = match.group(0)
                        break
                if matched_date_str:
                    break

        # Fallback: search entire item text
        if not matched_date_str:
            full_text = item.get_text(" ", strip=True)
            for pattern in DATE_PATTERNS:
                match = pattern.search(full_text)
                if match:
                    matched_date_str = match.group(0)
                    break

        if not matched_date_str:
            continue

        sortable_date = parse_date(matched_date_str)
        if not sortable_date:
            continue

        if sortable_date < MIN_DATE_STR:
            continue

        # Use ONLY the matched date string as display - no "Devamı", no icons
        display_date = matched_date_str.strip()

        full_link = urljoin(base_domain, link)

        news_items.append({
            'department': 'PLACEHOLDER',
            'date': sortable_date,
            'display_date': display_date,
            'title': title,
            'link': full_link
        })

    return news_items

def fetch_news(dept):
    url = dept["url"]
    dept_name = dept["name"]

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return []

    base_domain = "/".join(url.split("/")[:3])
    soup = BeautifulSoup(response.text, 'html.parser')

    news_items = extract_news_items(soup, base_domain)

    for item in news_items:
        item['department'] = dept_name

    return news_items

def main():
    all_news = []
    print("Starting scrape...")
    for dept in DEPARTMENTS:
        print(f"Fetching: {dept['name']}")
        news = fetch_news(dept)
        print(f"  Found {len(news)} items")
        all_news.extend(news)
        time.sleep(1)

    all_news.sort(key=lambda x: x['date'], reverse=True)

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": all_news
    }

    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nDone! Saved {len(all_news)} items to news.json")


if __name__ == "__main__":
    main()