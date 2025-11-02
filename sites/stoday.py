# sweepstakestoday_scraper.py
# Python 3.8-friendly; resilient fetch; correct title detection for SweepstakesToday

import re
import hashlib
import random
import time
from urllib.parse import urljoin, urlparse
from typing import Optional, List

import requests
from bs4 import BeautifulSoup
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import dateparser

BASE = "https://www.sweepstakestoday.com"

UA_POOL = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
]

def _browser_headers() -> dict:
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
    retries = Retry(
        total=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    return s

def _get_soup(url: str) -> BeautifulSoup:
    # polite jitter + browsery headers + cloudscraper fallback if 403
    time.sleep(random.uniform(0.35, 1.0))
    sess = _session()
    r = sess.get(url, timeout=25, headers=_browser_headers())
    if r.status_code == 403:
        try:
            import cloudscraper
            scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "linux", "mobile": False})
            r = scraper.get(url, timeout=25, headers=_browser_headers())
        except Exception:
            pass
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")

def _text(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def _label_value(soup: BeautifulSoup, label_regex: re.Pattern) -> Optional[str]:
    """
    Pages show lines like 'Expires On: <date>' and 'Frequency: <text>'.
    We scan blocks and split on ':' to find label -> value.
    """
    for el in soup.find_all(["div", "p", "li", "span", "strong", "b"]):
        t = _text(el.get_text(" "))
        if ":" not in t:
            continue
        label, val = t.split(":", 1)
        if label_regex.search(label):
            v = _text(val)
            if v:
                return v
    return None

def _first_external_link(scope: BeautifulSoup) -> Optional[str]:
    for a in scope.select("a[href]"):
        href = a.get("href", "").strip()
        if not href:
            continue
        abs_url = urljoin(BASE, href)
        host = urlparse(abs_url).hostname or ""
        if "sweepstakestoday.com" in host:
            continue
        return abs_url
    return None

def _entry_link(soup: BeautifulSoup) -> Optional[str]:
    # Prefer link near 'Enter Here', else first external
    for tag in soup.find_all(text=re.compile(r"\bEnter\s*Here\b", re.I)):
        parent = tag.parent
        if parent:
            a = parent.find("a", href=True)
            if a:
                return urljoin(BASE, a["href"])
    return _first_external_link(soup)

def _rules_link(soup: BeautifulSoup) -> Optional[str]:
    for tag in soup.find_all(text=re.compile(r"\bRules\s*Page\b", re.I)):
        parent = tag.parent
        if parent:
            a = parent.find("a", href=True)
            if a:
                return urljoin(BASE, a["href"])
    for a in soup.select('a[href*="rules"]'):
        href = a.get("href")
        if href:
            return urljoin(BASE, href)
    return None

def _og_image(soup: BeautifulSoup) -> Optional[str]:
    m = soup.select_one('meta[property="og:image"][content]')
    if m and m.get("content"):
        return m["content"].strip()
    im = soup.select_one("img[src]")
    if im and im.get("src"):
        return urljoin(BASE, im["src"])
    return None

def _parse_date(s: Optional[str]):
    if not s:
        return None
    return dateparser.parse(
        s,
        settings={"TIMEZONE": "UTC", "RETURN_AS_TIMEZONE_AWARE": True, "PREFER_DAY_OF_MONTH": "first"},
    )

def _extract_title(soup: BeautifulSoup) -> str:
    """
    Correct title: prefer og:title, then <title> (strip ' | Sweepstakes Today'), then heading near details.
    Avoid site banner text like 'Win your share of ...'
    """
    # 1) og:title
    mt = soup.select_one('meta[property="og:title"][content]')
    if mt and mt.get("content"):
        t = _text(mt["content"])
        if t:
            return t
    # 2) <title> fallback
    if soup.title and soup.title.string:
        t = _text(soup.title.string)
        t = re.sub(r"\s*\|\s*Sweepstakes\s*Today.*$", "", t, flags=re.I)
        if t:
            return t
    # 3) a heading that contains the sweep link/title
    hlink = soup.select_one("h1 a, h2 a, h3 a")
    if hlink:
        t = _text(hlink.get_text(" "))
        if t:
            return t
    # 4) last resort: nearest plain heading
    h = soup.select_one("h3, h2, h1")
    if h:
        t = _text(h.get_text(" "))
        if t:
            return t
    return "Sweepstakes"

def parse_detail(url: str) -> dict:
    soup = _get_soup(url)

    title = _extract_title(soup)

    # Prize summary: prefer 'Prize Details' block; else first paragraph with prize keywords
    prize_summary = None
    for hdr in soup.find_all(["h3", "h4"]):
        if re.search(r"\bPrize\s+Details\b", _text(hdr.get_text(" ")), re.I):
            b = hdr.find_next(["p", "div", "li"])
            if b:
                prize_summary = _text(b.get_text(" "))
                break
    if not prize_summary:
        for p in soup.find_all("p"):
            t = _text(p.get_text(" "))
            if re.search(r"\b(\$[0-9]|winners?|prize|cash|gift|card)\b", t, re.I):
                prize_summary = t
                break

    end_date_raw = _label_value(soup, re.compile(r"^\s*Expires\s*On\s*$", re.I))
    frequency = _label_value(soup, re.compile(r"^\s*Frequency\s*$", re.I))

    start_date = None
    end_date = _parse_date(end_date_raw)

    entry_link = _entry_link(soup)
    rules_link = _rules_link(soup)
    image_url = _og_image(soup)

    pid = hashlib.sha1(url.encode()).hexdigest()
    return {
        "id": pid,
        "source": url,
        "title": title or "Sweepstakes",
        "prize_summary": prize_summary,
        "entry_frequency": frequency,
        "eligibility": None,
        "start_date": start_date,
        "end_date": end_date,
        "entry_link": entry_link,
        "rules_link": rules_link,
        "image_url": image_url,
    }

def list_recent(n: int = 40, pages: int = 1) -> List[str]:
    """
    Discover newest 'Details' pages from /sweeps/new.
    Links look like /sweeps/details/<id>/<slug>.
    """
    urls: List[str] = []
    soup = _get_soup(f"{BASE}/sweeps/new")
    for a in soup.select('a[href*="/sweeps/details/"]'):
        href = a.get("href")
        if not href:
            continue
        abs_url = urljoin(BASE, href)
        if abs_url not in urls:
            urls.append(abs_url)
        if len(urls) >= n:
            break
    return urls
