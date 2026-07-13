# Docker Deployment Guide

**Updated:** 2026-07-13

---

## CI/CD Pipeline (Gitea Actions — Primary)

### How it works

```
Developer → Gitea (SOURCE OF TRUTH — no GitHub mirror)
    ↓
Gitea Actions (dev branch) → nas-act-runner-dev → Docker build → Portainer redeploy
    ↓
Gitea Actions (main branch) → nas-act-runner-prod → Docker build → Portainer
```

1. Developer pushes to Gitea `trading/trading-agent` (dev or main branch) — **this is the source of truth**
2. **NO GitHub push needed** — Gitea Actions fires automatically on push
3. **DEV:** Gitea Actions on `dev` branch → `nas-act-runner-dev` (DEV runner) → builds image → pushes to `nas:5000/trading-agent:latest` → Portainer webhook redeploys
4. **PROD:** Gitea Actions on `main` branch → `nas-act-runner-prod` (PROD runner) → same pipeline
5. **UAT:** Gitea Actions on `uat` branch → `nas-act-runner-uat` → builds `trading-agent-uat` image → Portainer stack redeploys

### Key facts
- **Gitea:** `http://10.8.0.10:3000`
- **Gitea repo:** `trading/trading-agent` — source of truth (dev/main/uat branches)
- **DEV runner:** `nas-act-runner-dev` — registered, stable ✅
- **UAT runner:** `nas-act-runner-uat` — id=7, org-level ✅
- **PROD runner:** `nas-act-runner-prod` — id=10, repo-level ✅
- **Docker registry:** `nas:5000/trading-agent:latest`
- **Image build:** Gitea Actions builds inside the act-runner, no local Docker needed

### Triggering a rebuild (DEV)
1. Push to `dev` branch on Gitea `trading/trading-agent`
2. Gitea Actions fires automatically
3. DEV runner builds + pushes image
4. Portainer webhook redeploys container

### UAT branch
- UAT uses the `uat` branch on `trading/trading-agent`
- UAT compose stack at Portainer (compose/11 or similar)
- UAT container: `trading-agent-uat` at `:5052`

### Manual rebuild (if webhook fails)
1. Portainer → **Images** → Find `nas:5000/trading-agent:latest` → **Rebuild**
2. Or via Gitea Actions UI: `http://10.8.0.10:3000` → repo → Actions → run workflow

---

## Manual Build (Portainer — fallback)

**Only if Gitea Actions is down.**

1. Portainer → **Images** → **Build a new image**
   - **Name:** `nas:5000/trading-agent:latest`
   - **Build method:** BuildKit inline
   - **Dockerfile:** paste contents of `Dockerfile` from the `trading/trading-agent` Gitea repo (dev branch)
   - **Build args (optional):** `GIT_REF=dev`
2. Hit **Build the image**
3. Recreate container from updated image via Portainer

## Rebuilding after code changes

1. Commit + push changes to Gitea `trading/trading-agent` (dev/main/uat branch as appropriate)
2. Gitea Actions fires automatically — no manual rebuild needed
3. If Gitea Actions is down: use Manual Build above

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
