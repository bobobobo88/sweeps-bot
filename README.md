# SweepstakesFanatics → Discord (Webhook) Bot

This mini-project scrapes SweepstakesFanatics post pages, extracts key fields (title, prize summary,
entry frequency, eligibility, start/end dates, image, and entry link), and posts them to a Discord channel
as an embed via **webhook**.

## 1) Prereqs
- Python **3.11+**
- A Discord channel **webhook URL** (Server Settings → Integrations → Webhooks → New Webhook → Copy URL)

## 2) Setup (macOS/Linux)
```bash
cd sweeps-bot
python3 --version
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# edit .env and paste your webhook URL

# Load .env into the shell for this session
export $(grep -v '^#' .env | xargs)
```

### Setup (Windows PowerShell)
```powershell
cd sweeps-bot
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env
# open .env and paste your webhook URL

# Load .env for this session (simple way):
# In PowerShell, set variables manually:
$env:DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/XXX/YYY"
$env:DB_PATH=".\data.db"
```

## 3) Run a test (posts the example White Claw sweep to your Discord channel)
```bash
python main.py
```
- You should see one embed appear in your Discord channel.
- The first run will create `data.db` for deduping.

## 4) Switch to auto-discovery of new posts
By default, `main.py` uses the **example** URL so you can verify end-to-end.  
To switch to monitoring recent posts from the homepage:
- Open `main.py`
- Replace the last two lines with:

```python
if __name__ == "__main__":
    run_once(seed_urls=None)  # will use list_recent(n=12)
```

Then run:
```bash
python main.py
```

## 5) Schedule it
### Cron (every 10 minutes)
```bash
crontab -e
# add:
*/10 * * * * cd /absolute/path/to/sweeps-bot && /absolute/path/to/sweeps-bot/.venv/bin/python main.py >> bot.log 2>&1
```

### Windows Task Scheduler
- Create Basic Task → Trigger: Daily, repeat every 10 minutes for a duration of 1 day.
- Action: Start a program
  - Program/script: `C:\full\path\to\python.exe`
  - Arguments: `C:\full\path\to\sweeps-bot\main.py`
  - Start in: `C:\full\path\to\sweeps-bot`

## 6) Notes & Tips
- Respect the site’s ToS and be gentle: avoid very frequent runs; add backoff if you see errors.
- All dates are parsed and displayed in **America/Chicago** in the embed.
- Deduping: We store the hashed URL in `data.db`. If a post is already seen, it won’t repost.
- Troubleshooting:
  - **403/429**: slow down your schedule; ensure a realistic User-Agent.
  - **ModuleNotFoundError**: re-run `pip install -r requirements.txt` in the activated venv.
  - **Windows**: If `zoneinfo` problems occur, ensure Python ≥ 3.9 (we recommend 3.11+).

## 7) One-off: test-only parse (without posting)
You can temporarily add this to the bottom of `main.py` to print the parsed payload:
```python
from pprint import pprint
item = parse_detail("https://sweepstakesfanatics.com/white-claw-wednesday-shore-club-friendsgiving-sweepstakes/")
pprint(item)
```
