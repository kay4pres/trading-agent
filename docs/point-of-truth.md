# Point of Truth — Trading Agent Sprint
**File:** `E:\Me\TradingAgent\docs\point-of-truth.md`
**Updated:** 2026-07-23 18:17 Berlin (Day 4 EOD — **Phase A GREEN: 6/6 smoke test PASS** ✅)
**Read before ANY action. Always include path links in your reasoning.**

---

## Session Startup Checklist

Before doing ANYTHING else in a new session:

1. **Read this file** — `E:\Me\TradingAgent\docs\point-of-truth.md`
2. **Read STATUS.md** — `E:\Me\AI-Brain\STATUS.md` (sprint state, blockers, deadlines)
3. **Query ai_memory** — `mindgentic_dev@10.8.0.10:5432` (ai_memory schema)
   - Check `ai_memory.tasks` for pending/blocked tasks
   - Check `ai_memory.session_reflections` for session continuity
   - Check `ai_memory.reasoning_logs` for recent agent decisions
4. **Read pipeline-status.md** — `E:\Me\TradingAgent\pipeline-status.md` (operational state)
5. **Check Focalboard** — `http://10.8.0.10:9087/bzzy9qg1dabfutdsyb8us5r1x8r`
6. **Then act** — dispatch the correct agent, do NOT execute yourself

---

## Sprint Context

**Sprint:** Re-architecture sprint (Day 3 of ~25, started 2026-07-20)
**Sprint Goal:** Replace v0.1 (alpha 1-position, 5-min polling) with DTD-replica v1.0 (6 planes, 10 of 24 DTD scanners MVP, 10s bars, multi-position 1-3, 4 AM ET premarket, auto-trade phased)
**Day 3 Deadline:** Re-arch ratified → Phase 2 (Data + Scanner MVP) starts
**Current Git Commit:** `977d3b3` on `pipeline-builder/day-01-relay-extension` (gitea primary)

## ⭐ Day 3 Handoff (2026-07-20, audited 2026-07-21)

**Architecture v1.0 drafted — awaiting Kay ratification:**
- `E:\Me\TradingAgent\docs\ARCHITECTURE_v1.0.md` (37 KB) — DTD-replica, 6 planes, 10 of 24 scanners MVP, 10s bars, multi-position 1-3, 4 AM ET premarket, auto-trade phased (paper → €500 → €2K). 28 course citations + 13 [INFERRED — Kay sign-off]. Supersedes v0.1 + cockpit charter.
- `E:\Me\TradingAgent\tools\PLAN-ARCHITECTURE-V1-REVIEW.md` (20 KB) — SCOPE EXPANSION review. Approach B recommended. 13 open items for Kay override.
- `E:\Me\TradingAgent\tools\DAY-3-END-OF-DAY-2026-07-20.md` (10 KB) — full handoff doc.
- `E:\Me\TradingAgent\tools\kanban-stakeholder-view.html` (32 KB) — visual kanban (one-off, Focalboard is the live board).
- `C:\Users\Kay\repos\trading-agent\.hermes\plans\re-architecture-kanban.md` — synced: 5 Done, 3 Blocked on Kay, 4 Ready, 5+ Backlog.

**3 items blocked on Kay:**
1. REA-0.2 — TradingView tier (Plus/Premium/Ultimate)
2. REA-0.3 — IBKR market data subs on DU1234567
3. REA-1.2 — 45-min DTD screen-share

**Once unblocked, Phase 2 (Data + Scanner MVP) starts.** ~1-2 weeks.

**Pushed to gitea:** commits `089bd64` (7 files) + `a54fa2f` (EOD) + `977d3b3` (doc-sheriff sync) on `pipeline-builder/day-01-relay-extension`.

## Day 4 — other-ai-investing-system review (2026-07-21 PM)

**New OSS reference reviewed:** `E:\Me\TradingAgent\tools\oss-references\other-ai-investing-system\REVIEW.md` (17 KB)
**Vendor:** Lewis Jackson / 01 Accelerator — `jackson-video-resources/skills` (MIT-style)
**Mental model:** *"System = environment · Strategy = plug-in · Risk = authority · AI = operator"*
**Key pattern:** paper-first with hard 4-step gate (mode check → risk limits → typed human confirmation → audit log). Self-learning via monthly closed cadence with keep/revert gate.

**Adopt-3 / Fork-3 / Skip-7 / Watch-4 verdict:**
- **ADOPT:** execution-safety (5 KB, 9 tests), news-guard (4 KB, 9 tests), trade-journal schema
- **FORK:** trading-loop engine (19 KB, 5 tests), risk-manager pre-trade gate, regime Markov
- **SKIP:** TV MCP, Alpha Vantage MCP, Pine trio, claude-api, mcp-builder, etc.
- **WATCH:** tear-sheet (QuantStats), alpha-combine, strategy-audit, edge-machine

**Arch v1.0 patch proposed (low-risk additive, ~35 KB total new code):**
- NEW `validation_plane/` — strategy-audit + pbo-deflated-sharpe + regime
- NEW `learning_plane/` — trade-journal + trading-loop
- REWRITE `execution_plane/` — wrap with `execution-safety` 4-step gate
- REWRITE `guardrails_plane/news_guard.py` — port NFP/FOMC/CPI detection

**Course citations:** `[A-1]`, `[A-2]`, `[A-3]`, `[F-1]`, `[F-2]`, `[F-3]` in REVIEW.md. `[INFERRED — Kay sign-off]` on all adopt/fork items.

**Critical missing piece (in our arch, filled by their trading-loop):** the closed self-learning loop with keep/revert gate. We have `knowledge/memory/trade_journal.md` plan but no mechanism. Their `trading-loop` engine (19 KB, numpy + stdlib, 5 tests) is the template.

## Day 4 EOD — Phase A (Dev environment) complete, awaiting Kay deploy

**Status:** Code shipped, CI build configured to auto-trigger. Tomorrow Kay deploys.

**Files shipped today (Phase A):**
- `E:\Me\TradingAgent\docker\docker-compose.dev.yml` (port 5060, separate vault+data)
- `E:\Me\TradingAgent\docker\portainer-stack-dev.yml` (Portainer stack file)
- `E:\Me\TradingAgent\smoke_e2e.py` (14KB, 6-step end-to-end test)
- `E:\Me\TradingAgent\dashboard\app.py` (DASHBOARD_PORT env var)
- `E:\Me\TradingAgent\entrypoint.py` (passes DASHBOARD_PORT)
- `E:\Me\TradingAgent\requirements.txt` (added pytest>=7.0.0)
- `E:\Me\TradingAgent\.gitea\workflows\ci-build-push.yml` (build on dev/dev-rollout/pipeline-builder/*)

**Smoke test passes locally: 6/6 steps.**

**What Kay does tomorrow (Phase A deploy):**
1. Verify CI build ran (Portainer images or gitea actions)
2. Deploy `docker/portainer-stack-dev.yml` via Portainer UI
3. Set Dev API keys in Portainer env vars
4. Run `docker exec trading-agent-dev python /app/smoke_e2e.py`
5. Verify 6 stop/go criteria
6. If all 6 pass: Phase A done. Move to UAT only after 3 blockers resolved.

**Hand-off doc:** `E:\Me\TradingAgent\tools\DAY-4-PHASE-A-DEPLOY-HANDOFF.md`

## Day 4 Final Update — Phase A DEPLOYED + SMOKE PASS (2026-07-23 18:17 Berlin)

**Phase A status: GREEN ✅ — 6/6 smoke test PASS in container.**

```
[PASS] Step 1/6: 75/75 unit tests
[PASS] Step 2/6: Pre-trade gate blocks over-positioned order
[PASS] Step 3/6: Valid order paper-routed + audit_id persisted
[PASS] Step 4/6: Audit log has decision + audit_id
[PASS] Step 5/6: execute_exit() appends to trade_journal.csv
[PASS] Step 6/6: trading_loop engine reads the journal
```

**Container:** `trading-agent-dev` running on port 5060, image `trading-agent-dev:2026-07-23` (sha `3ccfb094`, 367MB). 4G memory limit. All 6 volume mounts active, 10 env vars set, restart=unless-stopped.

**Bug found + fixed during deploy:** `events.csv` extracted as 0 bytes via `git archive | tar` in the gitea container. Workaround: `docker exec ... python3 -c 'open(...).write(content)'` to write content in-container. Root cause still under investigation. **Next build must verify file sizes BEFORE `docker build`** — add a `find /tmp/dev-build -size 0` pre-flight check.

**UAT blockers (3) — must resolve before Phase B:**
1. REA-0.2 — TradingView tier (Plus/Premium/Ultimate)
2. REA-0.3 — IBKR market data subs on `DU1234567`
3. REA-1.2 — 45-min DTD walkthrough to confirm scanner filter values

**Side issues tracked (not blockers):**
- yfinance outbound from NAS container times out (30s) — fincept_connector fallback gets 20/24 quotes. Real scanner work in Phase B will need it. Ticket: `E:\Me\TradingAgent\docs\YFINANCE-EGRESS-2026-07-23.md`
- 2 ghost act-runner containers flooding gitea with 500s. CI builds on `pipeline-builder/*` don't trigger. Workaround: manual Portainer build via `git archive` in gitea container.
- `host.docker.internal` doesn't resolve in alpine getent. Use NAS host IP `10.8.0.10` instead.
- Healthcheck URL is `/api/state` (not `/`) — matches UAT, exercises dashboard API.
- DASHBOARD_PORT env-var driven end-to-end. 4G memory minimum for Dev (2G OOM-killed).

**Full handoff doc:** `E:\Me\TradingAgent\tools\DAY-4-PHASE-A-DEPLOY-HANDOFF.md` (updated 2026-07-23 18:17).

## ⚠️ Critical: Path Discipline (re-discovered 2026-07-21)

- **Operational source of truth:** `E:\Me\TradingAgent\` (NOT `C:\Users\Kay\repos\trading-agent\`)
- **Git mirror (version control):** `C:\Users\Kay\repos\trading-agent\` (cloned FROM E: drive, syncs via git push to gitea)
- **Gitea source:** `http://10.8.0.10:3000/trading/trading-agent` (`dev` branch) → portainer auto-builds → NAS registry → container
- **All doc-sheriff audits read E:** — anything written only to C:\ is "agent reported done without updating docs" drift pattern
- **Day 3 (2026-07-20): Hermes wrote to C:\ by mistake** — Day 4 (2026-07-21) re-anchored 7 files to E: drive
- **Lesson:** when in Mavis Code working on trading-agent project, ALWAYS write to E:\Me\TradingAgent\ first, then mirror to C:\Users\Kay\repos\trading-agent\ for git.

## Focalboard Status (2026-07-21)

- **URL:** `http://10.8.0.10:9087` (container `mindgentic-kanban` running `mattermost/focalboard:latest`)
- **Auth:** username `Ai_agent_01`, password DPAPI-encrypted at `E:\Me\TradingAgent\vault\focalboard_password.enc`
- **Sprint Board ID:** `bzzy9qg1dabfutdsyb8us5r1x8r` — **STATUS UNKNOWN as of 2026-07-21** (per Jul 8 doc-sheriff ref, the board was in browser localStorage only, may be gone from cloud)
- **Pending:** verify board state, recreate if missing, mirror REA items from markdown kanban

**Sprint Board:** `http://10.8.0.10:9087/bzzy9qg1dabfutdsyb8us5r1x8r`
- Focalboard login unstable — may need manual login per session

---

## Active Blockers (Day 2)

| # | Blocker | Owner | Path to Resolution |
|---|---------|-------|--------------------|
| 1 | **act-runner unregistered** — Gitea deleted runner from registry | DevOps/Gitea Agent | ✅ Delegated — fix in progress (deleg_12872b9c) |
| 2 | **Container rebuild blocked** — waiting for act-runner | DevOps | Unblocks: Bull/Bear fixes, CSV fallback scoring, signals_live.json |
| 3 | **Bull/Bear `bull_bear: []`** — needs container rebuild + Mavis cron | DevOps + Bull/Bear | Fix pushed (b6c5f49), needs rebuild |
| 4 | **Alpaca keys missing** — `alpaca_api_key.enc` / `alpaca_secret.enc` in vault | Trader | Keys exist in vault, container not reading them |

---

## Sprint Backlog (Priority Order)

| Priority | Card | Status | Notes |
|----------|------|--------|-------|
| 🔴 HIGH | Fix act-runner | **IN PROGRESS** | deleg_12872b9c running — DevOps fixing |
| 🔴 HIGH | Rebuild Docker image | **BLOCKED** | Waiting for act-runner |
| 🟡 MED | Verify Bull/Bear LLM end-to-end | **READY** | LLM key fixed. EvidenceQA needed after rebuild |
| 🟡 MED | QA dashboard fixes (pillars, bull_bear) | **BLOCKED** | Waiting for Docker rebuild |
| 🟢 LOW | SSH + Docker TCP (Option C) | **STANDBY** | SSH fail2ban, port 2375 closed |

---

## Current System State

### Container ✅
- **Image:** `nas:5000/trading-agent:latest` — running
- **Commit behind:** `74054af` — 76 commits behind HEAD (`47439ed`)
- **Fixes pending deploy:** ca0ff79, f9b82d9, cc2ff96, cde656b, b6c5f49

### Dashboard ✅
- **URL:** `http://10.8.0.10:5050/`
- **`/api/state`:** ✅ responding — `last_scan: 16:30`, 7 signals, `bull_bear: []` (pending rebuild)

### Bull/Bear 🟡
- **LLM key:** ✅ MiniMax HTTP 200 confirmed (fixed overnight)
- **Pipeline:** ✅ Fixed (b6c5f49) — Mavis IPC socket, env var fallback, CSV path support
- **Status:** ⚠️ Running old container image — needs rebuild to pick up fixes
- **3-tier LLM fallback:** Mavis IPC (port 15321) → MINIMAX_API_KEY env var → vault DPAPI

### Scanner ✅
- **Status:** Alive — `last_scan: 16:30`, 7 signals
- **Source:** premarket_csv (penny stocks, yfinance stale during market hours)
- **CSV fallback scoring:** ✅ Active (b6c5f49)

### Gitea ✅
- **URL:** `http://10.8.0.10:3000`
- **Runner:** `nas-act-runner` — ⛔ unregistered, fix delegated

### Focalboard ⚠️
- **URL:** `http://10.8.0.10:9087/bzzy9qg1dabfutdsyb8us5r1x8r`
- **Login:** Unstable in automation — manual login may be needed per session

---

## ai_memory Protocol (NAS PostgreSQL)

**Connection:** `postgresql://ai_agent_dev:<vault_password>@10.8.0.10:5432/mindgentic_dev`

**Schema:** `ai_memory`

**Tables:**
- `tasks` — task queue and status (PRIMARY for orchestrator state)
- `session_reflections` — session-level learnings
- `reasoning_logs` — agent reasoning traces
- `agent_sessions` — active session tracking
- `agent_registry` — registered agents and configs
- `knowledge_items` — structured knowledge entries

**Write Protocol — After Every Agent Action:**
```
1. Agent completes action
2. Write result to appropriate ai_memory table
3. Write to E:\Me\TradingAgent\pipeline-status.md
4. Write to E:\Me\AI-Brain\STATUS.md
5. Return summary with path links to orchestrator
```

**Critical Tables for This Sprint:**
- `ai_memory.tasks` — sprint backlog items, updated on status change
- `ai_memory.session_reflections` — written at end of each session
- `ai_memory.reasoning_logs` — written when agent makes significant decision

---

## Key Paths

| Asset | Path |
|-------|------|
| **This file (Point of Truth)** | `E:\Me\TradingAgent\docs\point-of-truth.md` |
| **STATUS.md (Sprint State)** | `E:\Me\AI-Brain\STATUS.md` |
| **Pipeline Status (Ops)** | `E:\Me\TradingAgent\pipeline-status.md` |
| **Unified Schema (Living)** | `E:\Me\AI-Brain\projects\trading-agent\docs\UNIFIED_SCHEMA.html` |
| **Orchestrator Arch (Living)** | `E:\Me\AI-Brain\projects\trading-agent\docs\orchestrator-architecture.html` |
| **Ops Overview (Living)** | `E:\Me\AI-Brain\projects\trading-agent\docs\OPERATIONAL_OVERVIEW.html` |
| **AgentsOrchestrator Personality** | `E:\Me\TradingAgent\docs\AgentsOrchestrator Agent Personality.md` |
| **Vault** | `E:\Me\TradingAgent\vault\` |
| **ai_memory DB** | `mindgentic_dev@10.8.0.10:5432` (schema: ai_memory) |
| **Focalboard Sprint Board** | `http://10.8.0.10:9087/bzzy9qg1dabfutdsyb8us5r1x8r` |

---

## Orchestrator Rules (from AgentsOrchestrator Personality)

1. **READ this file FIRST** — before any action
2. **Query ai_memory.tasks** — check task state before spawning agents
3. **Dispatch, don't execute** — DevOps/Gitea/BullBear/Researcher are workers, not me
4. **EvidenceQA before PASS** — no task is "done" without QA validation
5. **Write back to ai_memory + STATUS.md** — after every agent completion
6. **Strict quality gates** — 3 retry max, then escalate
7. **Focalboard is the kanban** — all sprint tasks must be on the board

---

## Current Delegation Status

| Delegation ID | Agent | Task | Status |
|--------------|-------|------|--------|
| `deleg_12872b9c` | DevOps/Gitea | Fix act-runner (re-register with Gitea) | 🟡 Running |

---

*This file is the orchestrator's single source of truth.*
*Update it immediately after any significant state change.*
*Never act without reading it first.*
