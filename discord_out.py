import requests
import os
from datetime import datetime
from typing import List, Dict

def _cap(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else (s[: n - 1] + "…")

def build_error_embed(site_key: str, stage: str, err_msg: str, details: str = "") -> dict:
    """
    Red error embed with minimal, Discord-safe formatting.
    """
    desc_parts = [
        f"**Site:** {site_key}",
        f"**Stage:** {stage}",
        f"**When:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%SZ')} UTC",
        "",
        "**Error:**",
        f"```{_cap(err_msg, 1900)}```",
    ]
    if details:
        desc_parts += ["", "**Details:**", f"```{_cap(details, 1900)}```"]

    return {
        "title": "🛑 sweeps-bot failure",
        "description": "\n".join(desc_parts),
        "color": 0xFF4D4F,  # red
        "footer": {"text": "Sweepstakes Radar • Alert"},
    }

def send_alert(webhook_url: str, embeds):
    """
    Post one or more alert embeds to the alert webhook (no mentions).
    """
    import requests, time
    for i in range(0, len(embeds), 10):
        batch = embeds[i:i+10]
        payload = {
            "content": "",
            "embeds": batch,
            "allowed_mentions": {"parse": []},
        }
        r = requests.post(webhook_url, json=payload, timeout=20)
        print(f"[alert-webhook] status={r.status_code} body={_cap(r.text,300)!r}")
        if r.status_code == 429:
            try:
                delay = float(r.json().get("retry_after", 1.5))
            except Exception:
                delay = 1.5
            time.sleep(delay)
            r = requests.post(webhook_url, json=payload, timeout=20)
            print(f"[alert-webhook-retry] status={r.status_code} body={_cap(r.text,300)!r}")
        r.raise_for_status()

# ZoneInfo is stdlib in 3.9+; for 3.8 we use the backport
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    from backports.zoneinfo import ZoneInfo  # Python 3.8

LOCAL_TZ = ZoneInfo("America/Chicago")

def _fmt_dt(dt, tz=LOCAL_TZ) -> str:
    if not dt:
        return "Unknown"
    return dt.astimezone(tz).strftime("%b %d, %Y %I:%M %p %Z")

def _cap(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else (s[: n - 1] + "…")

def build_embed(item: dict) -> dict:
    # Title
    title = _cap(item.get("title") or "Sweepstakes", 256)

    # Description with safe pieces
    source = item.get("source") or item.get("url") or ""
    parts = []
    if source:
        parts.append(f"[Open Post]({source})")
    if item.get("entry_link"):
        parts.append(f"[Enter Here]({item['entry_link']})")
    if item.get("rules_link"):
        parts.append(f"[Rules]({item['rules_link']})")
    description = _cap(" • ".join(parts), 1000)

    # Fields
    fields = []
    if item.get("prize_summary"):
        fields.append({"name": "Prize", "value": _cap(item["prize_summary"], 1024), "inline": False})
    if item.get("entry_frequency"):
        fields.append({"name": "Entry Frequency", "value": _cap(item["entry_frequency"], 1024), "inline": True})
    if item.get("eligibility"):
        fields.append({"name": "Eligibility", "value": _cap(item["eligibility"], 1024), "inline": False})
    if item.get("start_date"):
        fields.append({"name": "Start Date", "value": item["start_date"].strftime("%b %d, %Y"), "inline": True})
    if item.get("end_date"):
        fields.append({"name": "End Date", "value": item["end_date"].strftime("%b %d, %Y"), "inline": True})

    embed = {
        "title": title,
        "url": source or None,
        "description": description,
        "fields": fields[:25],
        "footer": {"text": "Sweepstakes Radar"},
    }
    if item.get("image_url"):
        embed["image"] = {"url": item["image_url"]}

    return embed

def send_webhook(webhook_url: str, embeds: List[Dict]):
    # Discord: max 10 embeds per request
    for i in range(0, len(embeds), 10):
        payload = {"embeds": embeds[i:i+10]}
        r = requests.post(webhook_url, json=payload, timeout=20)
        r.raise_for_status()
