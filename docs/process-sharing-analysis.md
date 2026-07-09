# Trading Agent — Process Sharing Analysis

**Date:** 2026-07-09
**Context:** Kay wants to identify which Docker container processes can be **SINGLE** (shared across all environments) vs **PER-ENV** (replicated per Dev/UAT/PROD), to reduce duplicate API calls, eliminate redundant LLM calls, and centralize singleton-style work.

---

## 1. Environment Topology

Currently there is **one Docker stack** on the NAS. The plan is to split into three environments:

| Environment | Purpose | Broker | Credentials |
|---|---|---|---|
| **DEV** | Development & testing | Alpaca paper | Test-only keys |
| **UAT** | Pre-production validation | Alpaca paper | Staging keys |
| **PROD** | Live trading | IBKR | Hardened vault |

All three share the **same Docker image** (`nas:5000/trading-agent:latest`) but run in **separate Docker containers** with their own:
- Environment-specific credential sets (`vault/`)
- Environment-specific data directories (`data/DEV/`, `data/UAT/`, `data/PROD/`)
- Separate `positions.json` per environment
- Separate Telegram bot (or same bot, different chat IDs)

---

## 2. Process Inventory

| Process | Script | Runs | Classification |
|---|---|---|---|
| Richard (premarket screener) | `premarket_screener.py` | 14:00 Mon–Fri | **SINGLE** (shared) |
| Intraday Scanner | `intraday_scanner.py` | Every 15 min, 15:30–21:00 | **SINGLE** (shared) |
| Bull/Bear LLM Debate | `bull_bear_prompts.py` | Triggered by scanner | **SINGLE** (shared) |
| Bull/Bear Signal Handler | `bull_bear_signal_handler.py` | Triggered after Bull/Bear | **PER-ENV** |
| Trader Agent | `trader_agent.py` | Every 5 min + live events | **PER-ENV** |
| Live Event Loop | `live_event_loop.py` | 15s Alpaca WS poll | **SINGLE** (shared) |
| Dashboard | `dashboard/app.py` | Always on (:5050) | **PER-ENV** |
| Telegram Sender | `telegram_sender.py` | Triggered by any agent | **SINGLE** (shared) |
| Alpaca News Feed | `news_providers.py` | Finnhub REST polling | **SINGLETON** candidate |

---

## 3. Classification Detail

### 3.1 SINGLE — Shared by All Environments

These processes run **once**, produce **environment-agnostic output**, and their results are consumed by each environment's own downstream handlers.

#### Richard — Premarket Screener (`premarket_screener.py`)

- **What it does:** Pulls gap-up stocks from TradingView Premium, enriches with Finnhub catalyst scoring, runs Five Pillars + Ch2 risk rules, outputs ranked watchlist CSV.
- **Why shared:** Market data (TV gap-ups, Finnhub news) is identical for all environments. Running it three times wastes API credits and TV session quota. The watchlist is a ranked list of stocks — it is environment-agnostic.
- **Output:** `data/watchlists/watchlist_YYYYMMDD.csv`
- **How each env consumes it:** Each env's Bull/Bear Signal Handler reads the same CSV, applies its own position state (does this env already have a position in this ticker?) and sends its own Telegram alert.

> **Caveat:** If two environments both try to auto-open the same ticker, the position state diverges. The `positions.json` check inside the signal handler (`if ticker in open_positions: skip`) prevents double-alerting within a single env — but across environments this is a business logic choice, not a technical constraint.

#### Intraday Scanner (`intraday_scanner.py`)

- **What it does:** Every 15 min, pulls 5-min bar gap-ups, runs First Pullback Filter (ATR 1.5×–3× depth), writes qualifying signals to `signals_live.json`.
- **Why shared:** Same reasoning as Richard — the market data feed is shared. Duplicate scanner runs across 3 envs = 3× TV/Finnhub API calls for identical results.
- **Output:** `data/signals/signals_live.json`
- **Each env consumes it via:** Its own Bull/Bear instance reading the same file.

> **Caveat:** Race condition if two Bull/Bear instances both read `signals_live.json` simultaneously. Mitigation: each env's scanner+Bull/Bear writes to env-specific paths (`signals_live_DEV.json`, etc.) — BUT this undoes the sharing benefit. Better: the shared scanner writes once; each env's Bull/Bear reads the same file but uses its own `bull_bear_results_{ENV}.json` output path. The signal handler uses file locking (`fcntl.flock`) or an atomic rename to prevent double-processing.

#### Bull/Bear LLM Debate (`bull_bear_prompts.py`)

- **What it does:** Runs Bull Researcher, Bear Researcher, and Research Manager prompts via MiniMax M2.7, outputs `FINAL_VERDICT: APPROVE/SKIP` + conviction score.
- **Why shared (carefully):** The Ross Cameron rules encoded in the prompts are the same for all environments. One LLM call = one token spend. If each env runs it independently, three identical LLM calls are made for the same ticker on the same day.
- **Output per env:** `data/bull_bear_results_{ENV}.json` — each env writes its own result file to avoid overwriting peers.
- **How it works:** Shared scanner writes `signals_live.json`. A shared Bull/Bear Orchestrator script reads it, fans out N LLM calls, then writes `bull_bear_results_DEV.json`, `bull_bear_results_UAT.json`, `bull_bear_results_PROD.json` simultaneously (or sequentially, same results written to 3 files).

> **Key insight:** The LLM output (verdict + conviction) is identical across envs for the same input signal. The only thing that differs is what each env does with that verdict — one env might have capital available, another might not, one might be in paper mode, another in live. The verdict itself is env-agnostic.

#### Telegram Sender (`telegram_sender.py`)

- **What it does:** Sends Telegram messages to Kay's group or direct chat.
- **Why shared:** It is a stateless relay — it reads a message and a target chat ID from environment config, then sends. No position state. No market state. Three identical telegram_sender processes would send 3× the alerts (bad). One shared process receives message+chat via a queue or filesystem contract and sends once.
- **Implementation:** Each env's signal handler writes its alert intent to a FIFO or a shared `alerts/outgoing/` directory. One shared `telegram_sender` process consumes this directory and dispatches. Or: each env sends its own alerts but uses **different Telegram bots** or **different group chat IDs** to keep them distinct.

> **Alternative (simpler):** Keep `telegram_sender.py` per-environment but route alerts to different destinations:
> - DEV → `@KayDevBot` → DEV group
> - UAT → `@KayUATBot` → UAT group
> - PROD → `@Marvless01Bot` (current) → "Kay's Trading Team"
>
> This avoids the shared singleton complexity and keeps alert channels clean.

---

### 3.2 SINGLETON — Exactly One Process, Shared Read-Only Data

A **SINGLETON** differs from **SINGLE** in that there is **exactly one running instance** of the process, period — not one per environment, not one shared that fans out, but literally one process running that all environments consume.

#### Alpaca News Feed (Finnhub REST) — `news_providers.py`

- **The canonical singleton example Kay requested.**
- **What it does:** Polls Finnhub for breaking news and real-time market news every N minutes, scores catalysts per ticker (P4: News Catalyst Score).
- **Why exactly one:** News is identical for all environments. Polling it 3× burns Finnhub API quota. The news feed is a **broadcast** — all environments receive the same news at the same time.
- **Implementation:** One `news_provider` service runs outside the env containers (or as a sidecar). It writes to a shared `data/news_finnhub_latest.json` that all envs read. Each env's scanner reads this file as its news input instead of calling Finnhub directly.
- **Data freshness contract:** All envs read the same file. If an env was down for 30 min and restarts, it picks up the news from the file (possibly stale for 30 min — acceptable for news/catalyst scoring, not acceptable for live price).
- **Extends to:** TradingView connector, Fincept connector — all data sources that return identical data regardless of which environment calls them.

```
┌─────────────────────────────────────────────────────────┐
│  Alpaca News Singleton (news_providers.py, 1 process)   │
│  Polls Finnhub every 5 min → data/news_finnhub.json    │
└──────────────────────┬──────────────────────────────────┘
                       │ shared file read
          ┌────────────┼────────────┐
          ▼            ▼            ▼
     DEV scanner   UAT scanner   PROD scanner
```

---

### 3.3 PER-ENV — Must Be Replicated Per Environment

These processes manage **position state**, **execution**, or **environment-specific configuration** and **cannot** safely share a single instance or output.

#### Bull/Bear Signal Handler (`bull_bear_signal_handler.py`)

- **What it does:** Reads `bull_bear_results_{ENV}.json`, checks conviction ≥7, checks `positions.json` for open position on that ticker, sends Telegram alert or triggers auto-open.
- **Why per-env:** This is where the environment's **position state** enters the picture. The decision to auto-open depends on `positions.json` which is unique per environment. Two environments cannot share a single signal handler because they have different position states and different capital availability.
- **Auto-open logic:** Only the environment that has capital available and no existing position should auto-open. If one shared handler processed both UAT and PROD, it could open a PROD position on a UAT signal (catastrophic).

#### Trader Agent (`trader_agent.py`)

- **What it does:** Reads `positions.json`, pulls live prices via Fincept/yfinance, checks exit conditions (target / stop / 2-min rule), updates `positions.json` to `CLOSED`, sends exit Telegram.
- **Why per-env:** This is the **position-owning** process. Each environment has its own `positions.json`. If a single Trader Agent processed positions from both UAT and PROD, it would have no way to distinguish which environment's positions to manage. Each environment must have its own Trader Agent reading and writing its own `positions.json`.
- **The shared JSON file contract:** `positions.json` is the boundary. Richard reads it (to filter tickers already held). Bull/Bear reads it (to skip tickers with open positions). Trader writes to it (opens/closes). Making it per-env is the natural extension of the current design.

#### Dashboard (`dashboard/app.py`, Flask :5050)

- **Why per-env (recommended):** The dashboard reads from data files mounted in its container. If DEV, UAT, and PROD each have their own data directories (`data/DEV/`, `data/UAT/`, `data/PROD/`), the dashboard should be per-env so each shows only its own environment's state.
- **Alternative (shared, not recommended):** One shared dashboard could show a multi-env overview by reading all three `positions.json` files simultaneously. This is operationally useful for Kay but adds complexity and risk of cross-env data leakage in the UI.
- **Recommendation:** Per-env dashboards on different ports:
  - DEV dashboard → `:5051`
  - UAT dashboard → `:5052`
  - PROD dashboard → `:5050` (current)
- **Telegram status requests** (`/pm status`): A shared PM-Agent could query all three dashboards and aggregate the response.

#### Live Event Loop (`live_event_loop.py`)

- **What it does:** Alpaca WebSocket connection, 15s polling, pullback detection, auto-open on conviction ≥7, exit monitoring.
- **Why this is a nuanced case:**
  - **The WebSocket feed is shared by nature** — Alpaca streams the same live market data to whoever connects. Three separate WS connections = 3× the connection overhead for identical data.
  - **But the position actions must be per-env** — auto-open in DEV when UAT already has a position is wrong.
- **Recommended architecture:**
  - **One shared `live_event_loop`** connects to Alpaca WS once, receives live ticks, and writes tick events to a shared `data/tick_events.json` or a message queue.
  - **Per-env `live_event_loop_worker`** processes the shared tick events against its own `positions.json` and `bull_bear_results_{ENV}.json`, performing the actual auto-open/exit actions for that environment.
  - This avoids 3 WS connections while keeping position logic per-env.

```
┌──────────────────────────────────────────────┐
│  Shared Alpaca WS (live_event_loop core)    │
│  1 connection → writes tick_events.json      │
└────────────────────┬────────────────────────┘
                     │ shared file / queue
     ┌───────────────┼───────────────┐
     ▼               ▼               ▼
  DEV worker     UAT worker     PROD worker
  (per-env)      (per-env)      (per-env)
```

---

## 4. Summary Matrix

| Process | Type | Rationale |
|---|---|---|
| `news_providers.py` (Finnhub) | **SINGLETON** | Identical data, polling cost, broadcast nature |
| `tradingview_connector.py` | **SINGLETON** | Same TV session data for all envs |
| `fincept_connector.py` | **SINGLETON** | Same price/bar data for all envs |
| Richard (`premarket_screener.py`) | **SINGLE** | One analysis result, consumed by all envs |
| Intraday Scanner (`intraday_scanner.py`) | **SINGLE** | One scan result, consumed by all envs |
| Bull/Bear (`bull_bear_prompts.py`) | **SINGLE** | One LLM verdict, consumed by all envs |
| Bull/Bear Signal Handler | **PER-ENV** | Environment-specific position state |
| Trader Agent (`trader_agent.py`) | **PER-ENV** | Owns `positions.json` per environment |
| Live Event Loop core (WS) | **SINGLETON** | One WS connection, shared tick events |
| Live Event Loop workers | **PER-ENV** | Per-env position actions |
| Dashboard (`dashboard/app.py`) | **PER-ENV** | Per-env data isolation, separate ports |
| Telegram Sender | **PER-ENV** (simpler) or **SINGLE** | Per-env bots/chats avoids cross-env spam |

---

## 5. Data File Ownership Under Sharing

| File | Owner | Read By | Sharing |
|---|---|---|---|
| `news_finnhub_latest.json` | Singleton news provider | All scanners (read-only) | Shared read |
| `watchlist_YYYYMMDD.csv` | Richard (shared) | All env Bull/Bear handlers (read) | Shared read |
| `signals_live.json` | Scanner (shared) | All env Bull/Bear (read) | Shared read |
| `bull_bear_results_{ENV}.json` | Bull/Bear (shared) | Per-env signal handler + Trader | Per-env write |
| `tick_events.json` | Shared WS core | Per-env workers | Shared read |
| `positions_{ENV}.json` | Per-env Trader | Per-env Trader + Richard (filter) | **PER-ENV** |
| `positions.json` (legacy) | Split into per-env | Per-env | DEPRECATE |

---

## 6. Duplicate Work Reduction — Quantified

| Process | Before (3× per env) | After (shared/singleton) | Savings |
|---|---|---|---|
| Finnhub news poll | 3× every 5 min | 1× | ~67% API quota |
| TradingView gap-up scan | 3× premarket | 1× | ~67% TV API calls |
| Intraday scanner | 3× every 15 min | 1× | ~67% TV + Finnhub |
| Bull/Bear LLM calls | 3× identical per signal | 1× | ~67% token spend |
| Alpaca WS connections | 3× concurrent | 1× | 2 fewer WS connections |
| Richard (premarket) | 3× identical | 1× | ~67% TV + LLM calls |

**Estimated total API/WS savings: 60–70% reduction** across all external data providers, with the largest gains in LLM token spend and Finnhub polling.

---

## 7. Implementation Risks

### Risk: Shared scanner race conditions
If two env Bull/Bear instances read `signals_live.json` simultaneously, they could both process the same signal. **Mitigation:** Atomic file writes + file locking, or have the shared scanner fan out and write env-specific result files itself.

### Risk: Shared Bull/Bear overwrites
Bull/Bear writes identical verdicts to `bull_bear_results_DEV/UAT/PROD.json` — if the same ticker appears simultaneously in all three envs' signals, there is no conflict (each file is separate). Only risk is if two envs process the same ticker at slightly different times and overwrite each other's file. **Mitigation:** Write to a temp file then atomic rename (`os.rename`).

### Risk: Single Alpaca WS failure takes down all env event processing
If the shared WS core dies, all three envs lose live tick processing. **Mitigation:** WS core should have a watchdog that auto-restarts and reconnects. Per-env workers should have a local fallback that re-connects directly if the shared feed goes silent for >60s.

### Risk: Dashboard per-env port sprawl
Kay accessing 3 different ports is cognitively heavy. **Mitigation:** A **shared `pm-agent`** (portfolio manager overview) can aggregate all three env dashboards into one view, or use a reverse proxy (`nginx`) that routes `/dev/`, `/uat/`, `/prod/` to the correct backend port on the same host.

---

## 8. Recommended Architecture Under Sharing

```
                        ┌─────────────────────────┐
                        │  SINGLETON PROCESSES    │
                        │  (run once, outside env)│
                        ├─────────────────────────┤
                        │  news_providers.py      │
                        │  (Finnhub → news JSON)  │
                        │                         │
                        │  tradingview_connector  │
                        │  (TV → gap-up JSON)     │
                        │                         │
                        │  fincept_connector.py   │
                        │  (price/bar data)       │
                        │                         │
                        │  live_event_loop core   │
                        │  (Alpaca WS → ticks)    │
                        └────────────┬────────────┘
                                     │ shared JSON files
         ┌────────────────────────────┼────────────────────────────┐
         ▼                            ▼                            ▼
   ┌───────────┐              ┌───────────┐              ┌───────────┐
   │    DEV    │              │    UAT    │              │   PROD    │
   ├───────────┤              ├───────────┤              ├───────────┤
   │Richard(s) │              │           │              │           │
   │Scanner(s) │◄─reads───────┤  shared   │              │           │
   │Bull/Bear(s)              │  files    │              │           │
   │         │              │           │              │           │
   │ BB Handler│             │ BB Handler│              │ BB Handler│
   │ (PER-ENV) │              │ (PER-ENV) │              │ (PER-ENV) │
   │         │              │           │              │           │
   │ Trader   │              │ Trader    │              │ Trader    │
   │ (PER-ENV) │              │ (PER-ENV) │              │ (PER-ENV) │
   │         │              │           │              │           │
   │Dashboard │              │Dashboard  │              │Dashboard  │
   │ (:5051)  │              │ (:5052)   │              │ (:5050)   │
   │         │              │           │              │           │
   │WS worker │◄─tick feed──│WS worker  │              │WS worker  │
   │ (PER-ENV)│              │(PER-ENV) │              │(PER-ENV) │
   └───────────┘              └───────────┘              └───────────┘

(s) = SINGLE (shared across all envs, runs once)
PER-ENV = replicated per environment
```

---

## 9. Decisions Required

1. **Bull/Bear fan-out:** Does the shared Bull/Bear write 3 result files sequentially, or does each env run its own Bull/Bear but read from shared scanner output? ( Latter is simpler. Former saves LLM calls. )
2. **Telegram topology:** Separate bots per env (cleanest) or one shared sender with env-tagged messages?
3. **Dashboard aggregation:** Three separate ports, or a reverse-proxy that presents a unified view?
4. **WS worker fallback:** If the shared WS core goes down, do per-env workers reconnect directly or wait for the core to recover?
5. **positions.json migration:** The legacy `positions.json` must be split into `positions_DEV.json`, `positions_UAT.json`, `positions_PROD.json` before this architecture can work.

---

*Analysis based on: ARCHITECTURE_OVERVIEW.html (2026-07-03) and OPERATIONAL_OVERVIEW.html (2026-07-03) from the trading-agent project.*
