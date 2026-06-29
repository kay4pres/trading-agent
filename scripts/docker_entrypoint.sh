#!/bin/bash
# docker_entrypoint.sh — runs inside the container
# Reads env vars → writes to vault files (mode 600, root only) → starts services

set -e

VAULT_DIR="/app/vault"
mkdir -p "$VAULT_DIR"
mkdir -p /app/data/logs

echo "[entrypoint] Loading secrets into vault..."

inject_secret() {
    local name="$1"
    local value="$2"
    local path="$VAULT_DIR/${name}.env"
    if [[ -n "$value" ]]; then
        echo -n "$value" > "$path"
        chmod 600 "$path"
        echo "[entrypoint] ✓ $name loaded"
    else
        echo "[entrypoint] ⚠ $name not set — skipping"
    fi
}

# Core credentials — names match .env.example
inject_secret "ALPACA_API_KEY"     "${ALPACA_API_KEY:-}"
inject_secret "ALPACA_SECRET_KEY"  "${ALPACA_SECRET_KEY:-}"
inject_secret "TELEGRAM_BOT_TOKEN"  "${TELEGRAM_BOT_TOKEN:-}"
inject_secret "MINIMAX_API_KEY"     "${MINIMAX_API_KEY:-}"
inject_secret "TV_WEBHOOK_SECRET"   "${TV_WEBHOOK_SECRET:-}"

echo "[entrypoint] Vault ready at $VAULT_DIR"
echo "[entrypoint] Starting cron..."

# ── Cron: Richard + scan-market + transcription ───────────────────────────────
(crontab -l 2>/dev/null || true; cat <<'CRON'
# Richard premarket — 14:00 Berlin Mon-Fri
TZ=Europe/Berlin
14 0 * * 1-5 cd /app && python -m trading_agent.premarket_screener >> /app/data/logs/richard.log 2>&1
# scan-market — every 15 min 15:30-21:00 Mon-Fri
30,45 15 * * 1-5 cd /app && python -m scripts.scan_market_bull_bear >> /app/data/logs/scan.log 2>&1
0,15,30,45 16-20 * * 1-5 cd /app && python -m scripts.scan_market_bull_bear >> /app/data/logs/scan.log 2>&1
0,15,30,45 21 * * 1-5 cd /app && python -m scripts.scan_market_bull_bear >> /app/data/logs/scan.log 2>&1
# Transcription sprint — 21:00 Mon-Fri
0 21 * * 1-5 cd /app && python -m trading_agent.process_new_chapters >> /app/data/logs/transcribe.log 2>&1
CRON
) | crontab -

cron

echo "[entrypoint] Starting live event loop (Alpaca WebSocket)..."
python -m trading_agent.live_event_loop \
    --vault-dir "$VAULT_DIR" \
    >> /app/data/logs/live_loop.log 2>&1 &

echo "[entrypoint] Starting dashboard on :5050..."
exec python -m dashboard.app
