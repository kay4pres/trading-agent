# Point of Truth — Trading Agent Sprint
**File:** `C:\Users\Kay\repos\trading-agent\docs\point-of-truth.md`
**Updated:** 2026-07-20 18:35 Berlin (doc-sheriff sync after Day 3 work)
**Read before ANY action. Always include path links in your reasoning.**

## ⭐ Day 3 Handoff (2026-07-20)

**Architecture v1.0 drafted — awaiting Kay ratification:**
- `docs/ARCHITECTURE_v1.0.md` — DTD-replica, 6 planes, 10 of 24 scanners MVP, 10s bars, multi-position 1-3, 4 AM ET premarket, auto-trade phased (paper → €500 → €2K). 28 course citations + 13 [INFERRED — Kay sign-off]. Supersedes v0.1 + cockpit charter.
- `tools/PLAN-ARCHITECTURE-V1-REVIEW.md` — SCOPE EXPANSION review. Approach B recommended. 13 open items for Kay override.
- `tools/DAY-3-END-OF-DAY-2026-07-20.md` — full handoff doc.
- `tools/kanban-stakeholder-view.html` — visual kanban for stakeholders.
- `.hermes/plans/re-architecture-kanban.md` — synced: 5 Done, 3 Blocked on Kay, 4 Ready, 5+ Backlog.

**3 items blocked on Kay:**
1. REA-0.2 — TradingView tier (Plus/Premium/Ultimate)
2. REA-0.3 — IBKR market data subs on DU1234567
3. REA-1.2 — 45-min DTD screen-share

**Once unblocked, Phase 2 (Data + Scanner MVP) starts.** ~1-2 weeks.

**Pushed:** commits `089bd64` (7 files) + `a54fa2f` (EOD handoff) on `pipeline-builder/day-01-relay-extension`.

---

## Session Startup Checklist

Before doing ANYTHING else in a new session:

1. **Read this file** — `C:\Users\Kay\repos\trading-agent\docs\point-of-truth.md`
2. **Read brief.md** — `C:\Users\Kay\repos\trading-agent\docs\brief.md`
3. **Run `hermes kanban list`**
4. **Query ai_memory** — `mindgentic_dev@10.8.0.10:5432` (ai_memory schema)
5. **Then act** — dispatch the correct agent, do NOT execute yourself

---

## Pipeline Roadmap

|| Env | Broker | Status | Gitea Repo |
||-----|--------|--------|------------|
|| DEV | Alpaca Paper | ✅ Container alive at `:5051` | `trading/trading-agent` `dev` branch |
|| UAT | IBKR Paper | 🔴 Container alive but network isolated | `trading/trading-agent-uat` |
|| PROD | IBKR Live | 🔴 BLOCKED — UAT must be stable first | `trading/trading-agent-prod` |

**⚠️ WARNING: `docker/README.md` says GitHub is source of truth — WRONG.** Gitea is the source of truth. All pushes go to `trading/trading-agent` on Gitea directly. GitHub mirror (if any) is downstream only and unreliable.

**Sprint Board:** `http://10.8.0.10:9087/bzzy9qg1dabfutdsyb8us5r1x8r`

---

## Active Blockers (Jul 13 — Updated 09:15)

| # | Blocker | Owner | Status |
|---|---------|-------|--------|
| 1 | **IB Gateway verification** | Kay | ✅ UP — port 4002 listening since 09:20 |
| 2 | **UAT network isolation** | DevOps | 🔴 UAT stuck on isolated bridge — `docker network connect` fix running |
| 3 | **ib_insync not installed** | DevOps | 🔴 Blocked by UAT network — fix in progress |
| 4 | **ibkr_connector.py missing** | DevOps | 🔴 Fix in progress (deleg_287ca7c6) |
| 5 | **DEV Alpaca wiring not pushed** | DevOps | 🔴 push_data.json ready on NAS — Gitea API push in progress |
| 6 | **UAT Telegram 401** | DevOps | 🔴 Token is working — config wrong in UAT compose → delegated |
| 7 | ~~DEV Telegram DNS~~ | Orchestrator | ✅ FIXED — DEV moved to `trading-agent_default` network |
| 8 | ~~DEV Telegram 401~~ | Kay | ✅ FIXED — token renewed and vault updated |
| 9 | ~~No UAT container~~ | DevOps | ✅ FIXED — `trading-agent-uat` deployed at `:5052` |
| 10 | ~~UAT CI workflow clone bug~~ | Orchestrator | ✅ FIXED — `trading-agent-uat.git` now cloned |
| 11 | ~~All 3 runners~~ | DevOps | ✅ All online: DEV (org), UAT id=7 (org), PROD id=10 (repo) |

---

## Current System State (Verified 2026-07-13 09:15)

### Containers ✅ ALL RESPONDING
| Container | Port | Status | Telegram |
|-----------|------|--------|---------|
| `trading-agent` (PROD) | `:5050` | ✅ Alive (19h) | ✅ No errors |
| `trading-agent-dev` | `:5051` | ✅ Alive (14h) | ✅ 409 conflict (normal, clears 1-2 min) |
| `trading-agent-uat` | `:5052` | ✅ Alive (14h) | 🔴 401 stale token + network isolated |
| `gitea` | `:3000` | ✅ Up 5+ days | — |

### Runner Containers ✅ ALL ONLINE
| Container | Port | Registration | Gitea ID |
|-----------|------|-------------|----------|
| `act-runner-dev` | `:3031` | ✅ Online | org-level |
| `act-runner-uat` | `:3032` | ✅ Online | id=7 (org-level) |
| `act-runner-prod` | `:3033` | ✅ Online | id=10 (repo-level) |

### Bull/Bear ✅
- **LLM:** MiniMax wired (inline session)
- **Status:** Functional; conviction scoring active

### Docker Network Architecture ⚠️
- **UAT** is on isolated `trading-agent-uat_default` bridge → NO external TCP (PyPI, Telegram unreachable)
- **DEV/PROD** are on `trading-agent_default` → full connectivity
- **Fix:** `docker network connect trading-agent_default trading-agent-uat` — in progress (deleg_287ca7c6)

### Installed Packages (container)
| Package | DEV | UAT | Status |
|---------|-----|-----|--------|
| `alpaca-py` | ✅ 0.43.5 | ❌ not installed | DEV: wired but push to Gitea failed |
| `ib_insync` | — | ❌ not installed | Blocked by UAT network isolation |

---

## IB Gateway — Verification Required

**Status: NOT YET VERIFIED** — IB Gateway must be confirmed running and API-enabled before any IBKR wiring begins.

**Verification steps (run from this session before touching anything else):**

1. **Is IB Gateway running on Kay's Windows?**
   ```powershell
   Test-NetConnection -ComputerName localhost -Port 4002
   # If TcpTestSucceeded=True → IB Gateway is listening
   ```

2. **Is it paper mode?**
   - Open TWS/IB Gateway → Settings → Account → Paper Trading should be active

3. **Is API enabled?**
   - TWS: File → Settings → API → Enable ActiveX and Socket Clients ✅
   - Port: 4002 (Socket port)
   - "Allow connections from localhost only" is fine for local apps

4. **Can containers reach it?**
   ```bash
   ssh -i "E:/Me/TradingAgent/vault/Ai_agent_01_openssh.key" Ai_agent_01@10.8.0.10 \
     "curl -s --max-time 5 http://10.8.0.10:4002/v100/portal/ping"
   ```

5. **Does `ib_insync` work from container?**
   ```bash
   ssh -i "E:/Me/TradingAgent/vault/Ai_agent_01_openssh.key" Ai_agent_01@10.8.0.10 \
     "docker exec trading-agent-uat python3 -c 'import ib_insync; print(ib_insync.__version__)'"
   ```
   Expected: version number. If `ModuleNotFoundError` → `ib_insync` not installed.

**If IB Gateway is NOT running:** Kay starts it on Windows. The containers cannot connect to it.

---

## Key Paths

| Asset | Path |
|-------|------|
| **This file** | `C:\Users\Kay\repos\trading-agent\docs\point-of-truth.md` |
| **Brief** | `C:\Users\Kay\repos\trading-agent\docs\brief.md` |
| **Pipeline Status** | `C:\Users\Kay\repos\trading-agent\docs\pipeline-status.md` |
| **Docker README** | `C:\Users\Kay\repos\trading-agent\docker\README.md` |
| **NAS Docker Secrets** | Docker Secrets Swarm (primary vault) |
| **ai_memory DB** | `mindgentic_dev@10.8.0.10:5432` (schema: ai_memory) |
| **Gitea** | `http://10.8.0.10:3000` |
| **Dashboard PROD** | `http://10.8.0.10:5050` |
| **Dashboard DEV** | `http://10.8.0.10:5051` |
| **Dashboard UAT** | `http://10.8.0.10:5052` |
| **Portainer** | `http://10.8.0.10:19900` |

---

## Orchestrator Rules

1. **READ this file FIRST** — before any action
2. **Query ai_memory.tasks** — check task state before spawning agents
3. **Dispatch, don't execute** — DevOps/Gitea agents are workers, not me
4. **EvidenceQA before PASS** — no task is "done" without QA validation
5. **Write back to point-of-truth.md + brief.md** — after every agent completion
6. **Credentials NEVER in chat** — use Docker Secrets or vault files
7. **Kay executes NAS commands** — give ONE pasteable SSH command, Kay runs it manually
8. **On NAS: give ONE pasteable command** — not multiple steps

---

## Credentials & Secrets

- **Telegram:** @Marvless01_bot (group: -5581171035, DM: 8750722880)
- **NAS SSH:** `Ai_agent_01@10.8.0.10` port 2222, key at `E:/Me/TradingAgent/vault/Ai_agent_01_openssh.key`
- **Docker Secrets:** PRIMARY VAULT — all tokens/keys stored as Docker Swarm secrets
- **DPAPI:** Windows-local only; NAS secrets → Docker Secrets
- **Gitea API Token:** `84c70a81c60914e31cc2f269f6cd99e8591fd8cc` (scope: all)
- **Portainer API Key:** `ptr_x4J5FtqAi5ckt5nXtGQtxivkWOg1XSbHq02UE9rfPiA=`

**Note:** `E:\Me\TradingAgent\vault\` is DEPRECATED for NAS secrets. Docker Secrets is the primary vault for all NAS/Docker credentials. Windows-local credentials still use DPAPI vault.

---

## Docker Secrets — Read Pattern

```bash
ssh -i "E:/Me/TradingAgent/vault/Ai_agent_01_openssh.key" Ai_agent_01@10.8.0.10 \
  "docker secret inspect <name> --format '{{range .Spec.Data}}{{println .Data}}{{end}}'"
```

---

## UAT IBKR Setup — Remaining Work

**Prerequisite:** IB Gateway must be verified running with API enabled.

### ✅ Done:
- UAT container deployed at `:5052`
- All 3 runners online
- UAT CI workflow fixed

### 🔴 Remaining:
1. **Verify IB Gateway** — confirm port 4002 is listening and paper mode active
2. **Wire token to UAT** — UAT compose still has stale token `8940612948:...`
3. **Install `ib_insync`** — add to requirements, rebuild UAT container
4. **Write `ibkr_connector.py`** — IBKR API connector for paper trading
5. **Wire Alpaca in DEV** — `open_position()` → real Alpaca paper orders
6. **Test pipeline end-to-end** — scanner → Bull/Bear → position

---

## Docker Network Architecture

**Problem:** Docker Compose projects create isolated bridge networks (`20_default`, `trading-agent-uat_default`) that block egress. The working network is `trading-agent_default` (172.19.0.0/16).

**Fix applied:** DEV and UAT containers manually connected to `trading-agent_default`.

**Note:** Containers restart → they reconnect to their compose network → network may break again after restart. Root fix: change compose project name or daemon DNS order. See `20_default` bridge iptables issue.

**Network check command:**
```bash
docker inspect trading-agent-dev --format '{{range $net,$v := .NetworkSettings.Networks}}{{print $net " "}}{{end}}'
# Should NOT show 20_default
```
