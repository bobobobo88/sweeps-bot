# sites/freebieshark.py
# Python 3.8-friendly scraper for https://www.freebieshark.com/category/sweepstakes

import re, time, random, hashlib
from typing import Optional, List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import dateparser

BASE = "https://www.freebieshark.com"
CAT  = f"{BASE}/category/sweepstakes"

UA_POOL = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
]

def _session() -> requests.Session:
    s = requests.Session()
    retries = Retry(total=3, backoff_factor=0.6,
                    status_forcelist=(429,500,502,503,504),
                    allowed_methods=frozenset(["GET","HEAD"]),
                    raise_on_status=False)
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://",  HTTPAdapter(max_retries=retries))
    return s

def _headers():
    return {
        "User-Agent": random.choice(UA_POOL),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": "1",
    }

def _get_soup(url: str) -> BeautifulSoup:
    time.sleep(random.uniform(0.35, 0.9))
    sess = _session()
    r = sess.get(url, headers=_headers(), timeout=25)
    if r.status_code == 403:
        try:
            import cloudscraper
            scraper = cloudscraper.create_scraper(browser={"browser":"chrome","platform":"linux","mobile":False})
            r = scraper.get(url, headers=_headers(), timeout=25)
        except Exception:
            pass
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")

def _text(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def _og(soup: BeautifulSoup, prop: str) -> Optional[str]:
    m = soup.select_one(f'meta[property="{prop}"][content]')
    return _text(m["content"]) if m and m.get("content") else None

def _first_external_link(scope: BeautifulSoup) -> Optional[str]:
    for a in scope.select("a[href]"):
        href = a.get("href", "").strip()
        if not href:
            continue
        abs_url = urljoin(BASE, href)
        host = (urlparse(abs_url).hostname or "").lower()
        if "freebieshark.com" in host:
            continue
        return abs_url
    return None

def _find_label_value(soup: BeautifulSoup, label: str) -> Optional[str]:
    # Look for lines like "ENTRY: Daily Entry" etc.
    rgx = re.compile(rf"^\s*{label}\s*:", re.I)
    for el in soup.find_all(["p","li","div","span","strong","b"]):
        t = _text(el.get_text(" "))
        if ":" not in t:
            continue
        parts = t.split(":", 1)
        if len(parts) != 2:
            continue
        lab, val = parts
        if rgx.search(lab):
            v = _text(val)
            if v:
                return v
    return None

def _parse_date(s: Optional[str]):
    if not s:
        return None
    return dateparser.parse(s, settings={
        "TIMEZONE": "UTC",
        "RETURN_AS_TIMEZONE_AWARE": True,
        "PREFER_DAY_OF_MONTH": "last"
    })

def list_recent(n: int = 40, pages: int = 1) -> List[str]:
    """Collect detail-post URLs from the Sweepstakes category pages."""
    out: List[str] = []
    for page in range(1, max(1, pages)+1):
        url = CAT if page == 1 else f"{CAT}/page/{page}"
        soup = _get_soup(url)
        # Prefer explicit "Read more" links; fallback to post title anchors
        for a in soup.select('a:-soup-contains("Read more"), h2 a, h3 a'):
            href = a.get("href")
            if not href:
                continue
            abs_url = urljoin(BASE, href)
            if "/category/" in abs_url:
                continue
            if abs_url not in out:
                out.append(abs_url)
            if len(out) >= n:
                return out
    return out

def parse_detail(url: str) -> dict:
    soup = _get_soup(url)

    # Title: prefer og:title, then page <h1>, then <title>
    title = _og(soup, "og:title") or _text(getattr(soup.select_one("h1"), "get_text", lambda *_: "")(" ")) \
            or _text(soup.title.string if soup.title and soup.title.string else "") or "Sweepstakes"

    # Image
    image_url = _og(soup, "og:image")

    # Labeled blocks commonly present on FreebieShark posts
    prize_summary = _find_label_value(soup, "PRIZES")
    entry_frequency = _find_label_value(soup, "ENTRY")
    eligibility = _find_label_value(soup, "ELIGIBILITY")
    end_date_raw = _find_label_value(soup, "END DATE")
    start_date_raw = _find_label_value(soup, "START DATE")

    start_date = _parse_date(start_date_raw)
    end_date = _parse_date(end_date_raw)

    entry_link = _first_external_link(soup)
    rules_link = None  # rarely provided; if needed, detect 'Rules' external link

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
        "rules_link": rules_link,
        "image_url": image_url,
    }
