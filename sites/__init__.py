import os
from importlib import import_module

REGISTRY = {
        "freebieshark": "freebieshark",
"fanatics": "fanatics",
    "stoday":   "stoday",
}

def list_sites():
    return list(REGISTRY.keys())

def load_module(site_key: str):
    return import_module(f"sites.{REGISTRY[site_key]}")

def site_webhook(site_key: str):
    return os.getenv(f"{site_key.upper()}_WEBHOOK_URL") or os.getenv("DISCORD_WEBHOOK_URL")

def site_limit(site_key: str, default: int):
    v = os.getenv(f"{site_key.upper()}_LIMIT"); return int(v) if (v and v.isdigit()) else default

def site_pages(site_key: str, default: int):
    v = os.getenv(f"{site_key.upper()}_PAGES"); return int(v) if (v and v.isdigit()) else default
