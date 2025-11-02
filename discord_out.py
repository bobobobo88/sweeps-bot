import requests
from typing import List, Dict

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

def build_embed(item: dict) -> dict:
    fields = []
    if item.get("prize_summary"):
        fields.append({"name": "Prize", "value": item["prize_summary"][:1000], "inline": False})
    if item.get("entry_frequency"):
        fields.append({"name": "Entry Frequency", "value": item["entry_frequency"], "inline": True})
    if item.get("eligibility"):
        fields.append({"name": "Eligibility", "value": item["eligibility"][:1024], "inline": False})
    if item.get("start_date"):
        fields.append({"name": "Start Date", "value": _fmt_dt(item["start_date"]), "inline": True})
    if item.get("end_date"):
        fields.append({"name": "End Date", "value": _fmt_dt(item["end_date"]), "inline": True})

        desc = f"[Open Post]({item['source']})"
    if item.get("entry_link"):
        desc += f" • [Enter Here]({item['entry_link']})"
    if item.get("rules_link"):
        desc += f" • [Rules]({item['rules_link']})"

    embed = {
        "title": item.get("title", "Sweepstakes"),
        "url": item["source"],
        "description": desc,
        "fields": fields[:25],
        "footer": {"text": "SweepstakesFanatics Radar"},
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
