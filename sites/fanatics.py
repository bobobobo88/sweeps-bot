import re, hashlib, random, time
from urllib.parse import urljoin, urlparse
from typing import Optional, List

import requests, feedparser, dateparser
from bs4 import BeautifulSoup
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

BASE = "https://sweepstakesfanatics.com"

UA_POOL = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
]

def _browser_headers() -> dict:
    import random
    return {
        "User-Agent": random.choice(UA_POOL),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

def _session() -> requests.Session:
    s = requests.Session()
    retries = Retry(total=3, backoff_factor=0.8,
                    status_forcelist=(429,500,502,503,504),
                    allowed_methods=frozenset(["GET","HEAD"]),
                    raise_on_status=False)
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    return s

def _get_soup(url: str) -> BeautifulSoup:
    time.sleep(random.uniform(0.35, 1.0))
    sess = _session()
    r = sess.get(url, timeout=25, headers=_browser_headers())
    if r.status_code == 403:
        try:
            import cloudscraper
            scraper = cloudscraper.create_scraper(browser={"browser":"chrome","platform":"linux","mobile":False})
            r = scraper.get(url, timeout=25, headers=_browser_headers())
        except Exception:
            pass
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")

def _text(t) -> str:
    import re
    return re.sub(r"\s+", " ", (t or "").strip())

def _first_external_link(content: BeautifulSoup) -> Optional[str]:
    links = content.select("a[href]")
    scored = []
    for a in links:
        href = a.get("href", "").strip()
        if not href:
            continue
        abs_url = urljoin(BASE, href)
        host = urlparse(abs_url).hostname or ""
        if "sweepstakesfanatics.com" in host:
            continue
        text = _text(a.get_text(" "))
        score = 0
        if re.search(r"\b(enter|official|submit|click here)\b", text, re.I):
            score += 5
        if re.search(r"sweep|contest|giveaway|promo|win", text, re.I):
            score += 2
        scored.append((score, abs_url))
    if not scored:
        return None
    scored.sort(key=lambda x: (-x[0]))
    return scored[0][1]

def _og_image(soup: BeautifulSoup) -> Optional[str]:
    m = soup.select_one('meta[property="og:image"][content]')
    if m and m.get("content"):
        return m["content"].strip()
    c = soup.select_one("article .entry-content") or soup.select_one(".entry-content")
    if c:
        im = c.select_one("img[src]")
        if im:
            return urljoin(BASE, im["src"])
    return None

def _og_title(soup: BeautifulSoup) -> Optional[str]:
    m = soup.select_one('meta[property="og:title"][content]')
    return m["content"].strip() if m and m.get("content") else None

LABEL_PATTERNS = {
    "entry_frequency": re.compile(r"(entry\s*frequency|ntry\s*frequency|frequency)\s*:", re.I),
    "eligibility": re.compile(r"(eligibility)\s*:", re.I),
    "start_date": re.compile(r"(start\s*date|begins|open\s*from)\s*:", re.I),
    "end_date": re.compile(r"(end\s*date|ends|deadline)\s*:", re.I),
}

def _parse_labeled_fields(content: BeautifulSoup) -> dict:
    result = {k: None for k in LABEL_PATTERNS.keys()}
    for el in content.find_all(["p","li","div","span","strong","b"]):
        txt = _text(el.get_text(" "))
        if not txt or ":" not in txt:
            continue
        for key, pat in LABEL_PATTERNS.items():
            if pat.search(txt):
                parts = txt.split(":", 1)
                if len(parts) == 2:
                    val = _text(parts[1])
                    if val:
                        result[key] = val
                break
    if any(v is None for v in result.values()):
        for dt in content.find_all("dt"):
            label = _text(dt.get_text(" "))
            dd = dt.find_next_sibling("dd")
            val = _text(dd.get_text(" ")) if dd else None
            line = f"{label}: {val}" if val else label
            for key, pat in LABEL_PATTERNS.items():
                if pat.search(line):
                    result[key] = val
    return result

def _parse_dates(raw: Optional[str]):
    if not raw:
        return None
    return dateparser.parse(raw, settings={"TIMEZONE":"UTC","RETURN_AS_TIMEZONE_AWARE":True,"PREFER_DAY_OF_MONTH":"first"})

def parse_detail(url: str) -> dict:
    soup = _get_soup(url)
    title = None
    h1 = soup.select_one("h1.entry-title") or soup.select_one("h1")
    if h1:
        title = _text(h1.get_text(" "))
    if not title:
        title = _og_title(soup) or "Untitled"

    content = soup.select_one("article .entry-content") or soup.select_one(".entry-content") or soup
    image_url = _og_image(soup)

    prize_summary = None
    for p in content.find_all("p"):
        t = _text(p.get_text(" "))
        if re.search(r"\b(\$[0-9]|winners?|prize|cash|gift|card)\b", t, re.I):
            prize_summary = t
            break
    if not prize_summary:
        prize_summary = _text(content.get_text(" "))[:400]

    labeled = _parse_labeled_fields(content)
    entry_frequency = labeled.get("entry_frequency")
    eligibility = labeled.get("eligibility")
    start_date = _parse_dates(labeled.get("start_date"))
    end_date   = _parse_dates(labeled.get("end_date"))
    entry_link = _first_external_link(content)

    pid = hashlib.sha1(url.encode()).hexdigest()
    return {
        "id": pid,
        "source": url,
        "title": title,
        "prize_summary": prize_summary,
        "entry_frequency": entry_frequency,
        "eligibility": eligibility,
        "start_date": start_date,
        "end_date": end_date,
        "entry_link": entry_link,
        "image_url": image_url,
    }

def list_recent_from_feed(n: int = 40) -> List[str]:
    feed_url = f"{BASE}/feed/"
    fp = feedparser.parse(feed_url)
    urls: List[str] = []
    for e in fp.entries:
        link = e.get("link")
        if link:
            urls.append(link)
        if len(urls) >= n:
            break
    return urls

def list_recent(n: int = 40, pages: int = 3) -> List[str]:
    # Use RSS for discovery (avoids 403 on homepage HTML)
    return list_recent_from_feed(n=n)
