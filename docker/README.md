# Docker Deployment Guide

## Quick Start

### Build the image (Portainer)

1. Make GitHub repo **public** (Settings → Danger Zone → Change visibility)
2. Portainer → **Images** → **Build a new image**
   - **Name:** `nas:5000/trading-agent:latest`
   - **Dockerfile:** paste contents of `Dockerfile` from this directory
   - **Build args (optional):** `GIT_REF=main`
3. Hit **Build the image**
4. Immediately set GitHub repo back to **private**

### Deploy the container (Portainer)

**Containers** → **Add container**

| Field | Value |
|-------|-------|
| Name | `trading-agent` |
| Image | `nas:5000/trading-agent:latest` |
| Always pull | ✅ |
| Restart policy | `unless-stopped` |
| Publish all exposed ports | ✅ |

**Volumes (Bind, Writable):**
| Container | Host |
|----------|------|
| `/app/vault` | `/data/compose/1/vault` |
| `/app/data` | `/data/compose/1/data` |

**Environment variables:**
| Name | Value |
|------|-------|
| `ALPACA_API_KEY` | From Alpaca dashboard |
| `ALPACA_SECRET_KEY` | From Alpaca dashboard |
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `MINIMAX_API_KEY` | From platform.minimaxi.com |
| `TV_WEBHOOK_SECRET` | Optional — for TV webhook verification |

### Access

- Dashboard: `http://<nas-ip>:5050`
- WireGuard: `http://10.8.0.10:5050`

---

## Rebuilding after code changes

1. Commit + push changes to GitHub
2. Make repo public
3. Portainer **Images** → Find `nas:5000/trading-agent:latest` → **Rebuild** (same Dockerfile)
4. Stop + recreate container from updated image
5. Make repo private again

---

## Health check

```bash
curl http://localhost:5050/api/state
```

Expected response:
```json
{
  "market_open": true,
  "signals": [],
  "positions": [],
  "watchlist": [],
  "pnl": 0.0
}
```

---

## Logs

Container logs: Portainer → Container → **Logs** tab

Key log files inside container:
- `/app/data/logs/debug.log` — entrypoint startup sequence
- `/app/data/logs/live_loop.log` — live event loop output
- `/app/data/logs/richard.log` — premarket screener output

---

## Architecture

```
Container (trading-agent)
├── Flask dashboard    :5050      ← Kay's browser
├── Telegram polling   ← Kay's bot @Marvless01_bot
├── Alpaca WebSocket              ← live price feed
├── Cron jobs
│   ├── 14:00 Berlin  → Richard premarket screener
│   ├── 15:30–21:00   → scan-market + Bull/Bear debate
│   └── 21:00         → transcription sprint
└── Volumes
    ├── /app/vault  ← credentials (gitignored on host)
    └── /app/data    ← positions, signals, logs
```

---

## Rollback

To use an older image:
1. Find the image by date/tag in Portainer **Images**
2. Recreate container from that image tag

Date tags format: `nas:5000/trading-agent:YYYY-MM-DD`
