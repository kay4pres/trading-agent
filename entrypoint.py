#!/usr/bin/env python3
"""
Docker entrypoint — replaces shell script version.
Handles: vault injection, cron setup, live loop start, dashboard.
"""
import os, sys, subprocess
from pathlib import Path

VAULT_DIR = Path("/app/vault")
VAULT_DIR.mkdir(parents=True, exist_ok=True)

os.makedirs("/app/data/logs", exist_ok=True)

LOG = Path("/app/data/logs/debug.log")
LOG.write_text(f"=== ENTRYPOINT START {os.environ.get('TZ','?')} ===\n")

def log(msg):
    print(msg, flush=True)
    LOG.write_text(msg + "\n")

log(f"Working dir: {os.getcwd()}")
log(f"PYTHONPATH: {os.environ.get('PYTHONPATH','not set')}")

# Check /app/ contents
app_contents = list(Path("/app").iterdir()) if Path("/app").exists() else []
log(f"/app/ contents: {[p.name for p in app_contents]}")

# Test dashboard import
try:
    import dashboard
    log(f"dashboard.__file__: {dashboard.__file__}")
except ImportError as e:
    log(f"IMPORT FAILED: {e}")
    # Try sys.path
    log(f"sys.path: {sys.path}")

# Inject env vars into vault files
os.makedirs("/app/data", exist_ok=True)
data_logs = Path("/app/data/logs")
data_logs.mkdir(parents=True, exist_ok=True)

for name in ["ALPACA_API_KEY", "ALPACA_SECRET_KEY", "TELEGRAM_BOT_TOKEN",
             "MINIMAX_API_KEY", "TV_WEBHOOK_SECRET"]:
    value = os.environ.get(name, "")
    path = VAULT_DIR / f"{name}.env"
    if value:
        path.write_text(value)
        path.chmod(0o600)
        log(f"[OK] {name}")
    else:
        log(f"[SKIP] {name} (not set)")

# Write crontab
# NOTE: premarket_screener.py and process_new_chapters.py are root-level files (not in trading_agent/ package)
# Bull/Bear is NOT in container crontab — Mavis runs it inline in its own scan-market cron session
# (the Bull/Bear runner needs Kay's vault LLM key which is on the host, not in the container)
crontab = """TZ=Europe/Berlin
PATH=/usr/local/bin:/usr/bin:/bin
14 0 * * 1-5 cd /app && /usr/local/bin/python premarket_screener.py >> /app/data/logs/richard.log 2>&1
0 21 * * 1-5 TRADING_DATA_DIR=/app/data RAW_DIR=/app/knowledge/raw TRANSCRIPT_DIR=/app/knowledge/transcripts cd /app && /usr/local/bin/python process_new_chapters.py >> /app/data/logs/transcribe.log 2>&1
"""
try:
    subprocess.run(["crontab", "-"], input=crontab.encode(), check=True)
    log("[OK] crontab installed")
except Exception as e:
    log(f"[WARN] crontab failed: {e}")

# Start cron
try:
    subprocess.Popen(["cron"])
    log("[OK] cron started")
except Exception as e:
    log(f"[WARN] cron start failed: {e}")

# Start live event loop in background
log("[INFO] Starting live_event_loop...")
subprocess.Popen(
    [sys.executable, "-m", "trading_agent.live_event_loop",
     "--vault-dir", str(VAULT_DIR),
     "--data-dir", "/app/data"],
    cwd="/app",
    stdout=open("/app/data/logs/live_loop.log", "a"),
    stderr=subprocess.STDOUT,
)
log("[INFO] live_event_loop running in background")

# Run dashboard (foreground)
log("[INFO] Starting dashboard on :5050...")
os.chdir("/app")
sys.path.insert(0, "/app")
os.environ["PYTHONPATH"] = "/app"
os.execv(sys.executable, [sys.executable, "-m", "dashboard.app"])
