# Point of Truth — Trading Agent Sprint
**File:** `E:\Me\TradingAgent\docs\point-of-truth.md`
|**Updated:** 2026-07-09
**Read before ANY action. Always include path links in your reasoning.**

---

## Smarter Way Communication Rules (Mandatory)

1. Work one step at a time.
2. Each reply must contain exactly one actionable step.
3. The step must be clear, practical, and written in plain language.
4. After giving the step, stop and wait.
5. Do not continue until Kay types `GO`.
6. If Kay types `NOK`, report an error and give only one focused remediation step.
7. Do not give long plans unless explicitly asked.
8. Do not guess or assume facts not proven.
9. Use deterministic evidence when needed.
10. Never expose or request secrets.
11. If something is not proven, say `NOK` and give the next safe verification step.
12. Keep responses short and avoid token waste. Token conservation is a first-class requirement — see MoA §Token Conservation.

---

## Governance Loop (Mandatory Before Any Action)

Before acting on any item, produce a PASS/NOK report:

```
PASS or NOK
Short reason:
MATCHES:
DRIFTS:
PARKED ITEMS:
BLOCKERS:
PROOF / EVIDENCE CHECK
VERIFIED:
ASSUMED:
NOT CHECKED:
NEXT SAFE STEP:
```

- Never call a fact VERIFIED unless there is current evidence.
- Default to NOK when a step crosses an unapproved boundary.
- Keep parked unless explicitly approved by Kay.

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
5. **Check Hermes Kanban** — `hermes kanban ls`
6. **Then act** — dispatch the correct agent, do NOT execute yourself

---

## Sprint Context

**Sprint:** 3-day — Day 2 of 3 (started 2026-07-07)
**Sprint Goal:** Trading Agent → live production
**Day 2 Deadline:** 2026-07-08 23:59 Berlin (~6 hours remaining)
**Current Git Commit:** `47439ed` (pipeline-check docs commit)

**Sprint Board:** Hermes Kanban — `hermes kanban ls`
- All sprint tasks must be on the Hermes Kanban board

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

### Hermes Kanban ✅
- **Command:** `hermes kanban ls` — primary sprint board

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
| **Orchestrator Guardrails** | `E:\\Me\\TradingAgent\\docs\\orchestrator-guardrails\\` |
| **Orchestrator Contract (DB)** | `E:\\Me\\TradingAgent\\docs\\orchestrator-guardrails\\orchestrator-contract.md` |
| **AI Roles** | `E:\\Me\\TradingAgent\\docs\\orchestrator-guardrails\\ai-roles.md` |
| **Governance Loop** | `E:\\Me\\TradingAgent\\docs\\orchestrator-guardrails\\stakeholder-governance-loop.md` |
| **Trading Agent Workflow** | `E:\\Me\\TradingAgent\\docs\\orchestrator-guardrails\\workflow.md` |
| **System Architecture** | `E:\\Me\\TradingAgent\\docs\\orchestrator-guardrails\\architecture.md` |
| **DB Handover** | `E:\\Me\\TradingAgent\\docs\\orchestrator-guardrails\\database-handover.md` |
| **Env Variables** | `E:\\Me\\TradingAgent\\docs\\orchestrator-guardrails\\env-variables.md` |
| **Trading Agent Backlog** | `E:\\Me\\TradingAgent\\docs\\orchestrator-guardrails\\trading-agent-backlog.md` |
| **MoA (Models & Agents)** | `E:\\Me\\AI-Brain\\projects\\trading-agent\\docs\\AI-Brain_MoA.md` |
| **Living HTML Docs** | `E:\\Me\\AI-Brain\\projects\\trading-agent\\docs\\` |
| **Vault** | `E:\\Me\\TradingAgent\\vault\\` |
| **ai_memory DB** | `mindgentic_dev@10.8.0.10:5432` (schema: ai_memory) |
| **Hermes Kanban (Sprint)** | `hermes kanban ls` |

---

## Orchestrator Rules (from orchestrator-guardrails/)

1. **READ point-of-truth.md FIRST** — before any action
2. **Apply Governance Loop** — produce PASS/NOK before any action
3. **Smarter Way first** — one step, wait for GO
4. **Query ai_memory.tasks** — check task state before spawning agents
5. **Dispatch, don't execute** — DevOps/Gitea/BullBear/Researcher are workers, not me
6. **EvidenceQA before PASS** — no task is "done" without QA validation
7. **Write back to ai_memory + STATUS.md** — after every agent completion
8. **Strict quality gates** — 3 retry max, then escalate
9. **Hermes Kanban is the kanban** — all sprint tasks must be on the Hermes Kanban board
10. **WireGuard VPN required** — always verify VPN active before DB connection
11. **Never bypass stakeholder Done rule** — only Kay moves to done

---

## Current Delegation Status

| Delegation ID | Agent | Task | Status |
|--------------|-------|------|--------|
| `deleg_12872b9c` | DevOps/Gitea | Fix act-runner (re-register with Gitea) | 🟡 Running |

---

*This file is the orchestrator's single source of truth.*
*Update it immediately after any significant state change.*
*Never act without reading it first.*
