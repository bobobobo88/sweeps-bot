import os, argparse
from datetime import timezone
from importlib import import_module
from storage import get_db, seen, save
from discord_out import build_embed, send_webhook

def load_site_module(site: str):
    if site in ("fanatics", "sf"):
        return import_module("sweepstakesfanatics_scraper")
    elif site in ("stoday", "st"):
        return import_module("sweepstakestoday_scraper")
    elif site in ("both",):
        return None  # special case handled below
    else:
        raise SystemExit("Unknown --site. Use: fanatics | stoday | both")

def run_recent(limit=12, pages=3, dry=False):
    webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    db_path = os.environ.get("DB_PATH", "data.db")
    print(f"[info] DB_PATH={db_path}")
    print(f"[info] WEBHOOK set? {'yes' if bool(webhook) else 'NO'}")
    conn = get_db(db_path)

    urls = list_recent(n=limit, pages=pages)
    print(f"[info] discovered {len(urls)} recent urls (limit={limit}, pages={pages})")
    embeds = []
    for u in urls:
        item = parse_detail(u)
        if seen(conn, item["id"]):
            print(f"[skip] already seen: {u}")
            continue
        print(f"[new] {item['title']} -> {u}")
        if not dry:
            embeds.append(build_embed(item))
        deadline_iso = item["end_date"].astimezone(timezone.utc).isoformat() if item.get("end_date") else None
        save(conn, item["id"], item["source"], item["title"], deadline_iso)

    if not dry and embeds:
        if not webhook:
            raise RuntimeError("DISCORD_WEBHOOK_URL not set")
        print(f"[post] sending {len(embeds)} embed(s) to Discord...")
        send_webhook(webhook, embeds)
        print("[post] done.")
    elif dry:
        print("[dry] would post", len(embeds), "embeds")
    else:
        print("[info] nothing new to post.")

def run_example():
    url = "https://sweepstakesfanatics.com/white-claw-wednesday-shore-club-friendsgiving-sweepstakes/"
    item = parse_detail(url)
    embed = build_embed(item)
    wh = os.environ.get("DISCORD_WEBHOOK_URL")
    if not wh:
        raise RuntimeError("DISCORD_WEBHOOK_URL not set")
    print(f"[post] example -> {url}")
    send_webhook(wh, [embed])
    print("[post] done.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["recent", "dry"], default="recent")
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--site", choices=["fanatics","stoday","both"], default="fanatics")
    args = ap.parse_args()

    def run_for(mod, limit, pages, dry):
        webhook = os.environ.get("DISCORD_WEBHOOK_URL")
        db_path = os.environ.get("DB_PATH", "data.db")
        print(f"[info] DB_PATH={db_path}")
        print(f"[info] WEBHOOK set? {'yes' if bool(webhook) else 'NO'}")
        conn = get_db(db_path)

        urls = mod.list_recent(n=limit, pages=pages)
        print(f"[info] discovered {len(urls)} recent urls (limit={limit}, pages={pages})")
        embeds = []
        for u in urls:
            item = mod.parse_detail(u)
            if seen(conn, item["id"]):
                print(f"[skip] already seen: {u}")
                continue
            print(f"[new] {item['title']} -> {u}")
            if not dry:
                embeds.append(build_embed(item))
            deadline_iso = item["end_date"].astimezone(timezone.utc).isoformat() if item.get("end_date") else None
            save(conn, item["id"], item["source"], item["title"], deadline_iso)

        if not dry and embeds:
            if not webhook:
                raise RuntimeError("DISCORD_WEBHOOK_URL not set")
            print(f"[post] sending {len(embeds)} embed(s) to Discord...")
            send_webhook(webhook, embeds)
            print("[post] done.")
        elif dry:
            print("[dry] would post", len(embeds), "embeds")
        else:
            print("[info] nothing new to post.")

    if args.site == "both":
        for site in ("fanatics","stoday"):
            print(f"\n===== Running site: {site} =====")
            mod = load_site_module(site if site != "fanatics" else "sf") or import_module("sweepstakesfanatics_scraper")
            # fanatics uses RSS discovery internally now; pages arg is ignored there.
            run_for(mod, limit=args.limit, pages=args.pages, dry=(args.mode=="dry"))
    else:
        mod = load_site_module(args.site)
        run_for(mod, limit=args.limit, pages=args.pages, dry=(args.mode=="dry"))
