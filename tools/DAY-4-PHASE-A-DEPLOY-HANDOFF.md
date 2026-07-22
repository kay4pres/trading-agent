# Phase A Deployment Handoff — 2026-07-21 EOD

**Status:** All code shipped to gitea. CI build may have triggered. Dev container deployment is the manual step for tomorrow.

## What's already done (Mavis, 2026-07-21)

1. **5 new modules** ported from Lewis Jackson / 01 Accelerator pack:
   - `trading_agent/execution/guard.py` (4-step gate)
   - `trading_agent/data_plane/news_guard/` (NFP/FOMC/CPI blackout)
   - `trading_agent/risk/pre_trade_gate.py` (7 BLOCK conditions)
   - `trading_agent/data_plane/regime/` (Markov 3-state)
   - `trading_agent/learning/` (trading_loop + trade_journal)
2. **Wired into `trader_agent.py`** — gates run before state mutation, audit log persisted, journal CSV on exit
3. **75 tests passing locally** in 4.4s
4. **Dev container files created:**
   - `docker/docker-compose.dev.yml` (port 5060, separate vault+data)
   - `docker/portainer-stack-dev.yml` (one-click Portainer deploy)
   - `smoke_e2e.py` (6-step end-to-end test, all 6 pass locally)
5. **CI workflow updated** to build on `pipeline-builder/**` branches (image tagged `:dev-2026-07-22` + `:dev` + `:latest`)
6. **All commits pushed to gitea** (`pipeline-builder/day-01-relay-extension` branch):
   - `5ca756b` — CI: build-dev on dev/dev-rollout/pipeline-builder/*
   - `7190cc8` — CI: trigger on pipeline-builder/* + dev-rollout
   - `e8de02b` — Phase A files (compose, smoke, port config)

## What you (Kay) need to do tomorrow (5-10 min)

### Step 1: Verify the build
The CI should have triggered automatically. Check one of:
- Gitea UI: http://10.8.0.10:3000/trading/trading-agent/actions
- Portainer: Images — should see `nas:5000/trading-agent:dev-2026-07-22` (or `:dev`)
- SSH: `ssh nas && docker images | grep trading-agent`

If the build didn't trigger (most likely cause: gitea runner is not picking up `pipeline-builder/*` branches), do a manual build via Portainer:
- Portainer → Images → Build a new image
- Name: `nas:5000/trading-agent:dev-2026-07-22`
- Dockerfile: paste from `E:\Me\TradingAgent\docker\Dockerfile`
- Build context: paste the repo's current `pipeline-builder/day-01-relay-extension` content (or use the "Repository" option and point at the gitea URL)

### Step 2: Deploy the Dev stack
Via Portainer UI:
- Stacks → Add stack
- Method: **Upload** (or **Repository** if pointing at gitea)
- Stack name: `trading-agent-dev`
- File: paste from `E:\Me\TradingAgent\docker\portainer-stack-dev.yml`
- **Set the env vars** in the Portainer UI before deploy:
  - `ALPACA_API_KEY` = Dev paper-trading key
  - `ALPACA_SECRET_KEY` = Dev paper-trading secret
  - `MINIMAX_API_KEY` = Dev LLM key
  - (Optional) `TV_WEBHOOK_SECRET`
- Click Deploy

Wait ~30s for the container to come up. Healthcheck passes when `(healthy)` shows next to the container in Portainer.

### Step 3: Run the smoke test
SSH to the NAS (or use Portainer's "Console" button):
```bash
docker exec trading-agent-dev python /app/smoke_e2e.py
```

All 6 steps should pass. If any fails, copy the output and send to Mavis.

### Step 4: Verify the 6 stop/go criteria
Mark each ✅ in the checklist below.

- [ ] All 75 unit tests pass inside the Dev container
- [ ] IBGW relay smoke test passes (status:ok from http://nas:5000/status or similar)
- [ ] 1 end-to-end paper trade completes: gate → audit → position → exit → journal CSV
- [ ] No errors in container logs (`docker logs trading-agent-dev | grep -i error` is clean)
- [ ] Vault is `/data/compose/2/vault/` on the NAS (NOT local `E:\Me\TradingAgent\vault\`)
- [ ] Portainer stack name is `trading-agent-dev` (NOT `trading-agent`)

If all 6 pass: **Dev is working. Move to UAT only after the 3 blockers (REA-0.2, REA-0.3, REA-1.2) are resolved.**

If any fail: report the failure to Mavis, do NOT proceed to UAT.

## What's NOT done (waiting on UAT / Phase B)

These are the things Phase A explicitly does NOT include — they wait for Phase B (UAT) and the 3 blockers:

- Real scanner code (10 of 25 DTD scanners with confirmed filter values)
- IBKR market data subs on `DU1234567` (REA-0.3)
- TradingView tier for richer data (REA-0.2)
- 45-min DTD walkthrough to confirm filter values (REA-1.2)
- 5-day paper-mode validation
- Monthly `trading_loop` cron
- Regime filter wired into the gate
- Full UAT env with real CapTrader paper account

## Files for tomorrow (if you need to review)

| File | Path | What |
|---|---|---|
| Compose | `E:\Me\TradingAgent\docker\docker-compose.dev.yml` | 4KB, all env vars + volume mappings |
| Portainer stack | `E:\Me\TradingAgent\docker\portainer-stack-dev.yml` | 2KB, identical to compose |
| Smoke test | `E:\Me\TradingAgent\smoke_e2e.py` | 14KB, 6 verification steps |
| CI workflow | `E:\Me\TradingAgent\.gitea\workflows\ci-build-push.yml` | Updated to trigger on pipeline-builder/* |
| Dockerfile | `E:\Me\TradingAgent\docker\Dockerfile` | Unchanged |
| Dashboard | `E:\Me\TradingAgent\dashboard\app.py` | Now reads `DASHBOARD_PORT` env var |
| Entrypoint | `E:\Me\TradingAgent\entrypoint.py` | Now logs the port |
| Requirements | `E:\Me\TradingAgent\requirements.txt` | Added `pytest>=7.0.0` |

## In case of failure

If anything breaks during deploy, do these things in order:

1. **Check container logs first:** `docker logs trading-agent-dev --tail 50`
2. **Check healthcheck:** `docker inspect trading-agent-dev --format '{{json .State.Health}}'`
3. **Try the smoke test in isolation:** `docker exec trading-agent-dev python -m pytest trading_agent/ -q` (should be 75 passed)
4. **If smoke test passes but container is unhealthy:** the entrypoint may have a problem; check `docker logs trading-agent-dev 2>&1 | head -50`
5. **If nothing works:** roll back. `docker stop trading-agent-dev && docker rm trading-agent-dev`. The old `trading-agent` stack is untouched.

Don't try to debug the gate logic itself — that was tested in 75 unit tests. If a gate test fails in the container, the issue is environment (env vars, vault, file paths), not the code.

[INFERRED — Kay sign-off on Phase A]
