# Re-architecture Kanban — Hermes Orchestrator

**Project:** Trading-Agent DTD-replica + day-trading rebuild
**Owner:** Hermes (Mavis Code) for Kay
**Created:** 2026-07-20
**Last sync:** 2026-07-20 18:35 Berlin (Day 3 EOD)

---

## 📋 Board (synced 2026-07-20 18:35)

Status flow: `Backlog` → `Ready` → `In Progress` → `In Review` → `Done`

Legend: ✅ Done | 🔵 In Progress | 🟡 Ready | ⚪ Backlog | 🔴 Blocked on Kay

---

## Done ✅

### REA-1.1 — Course-grounded decisions sweep ✅
- **Owner:** Hermes (with 28 course citations in ARCHITECTURE_v1.0.md)
- **Completed:** 2026-07-20
- **Evidence:** `docs/ARCHITECTURE_v1.0.md` cites `[C1.Ch2.P1]`, `[C1.Ch5]`, `[C1.Ch6]`, `[C1.Ch11]`, `[C1.Ch12]`, `[C1.Ch15]`, `[C2.Ch2]`, `[C2.Ch6.P3]`, `[C3.P5]`, `[C4.Ch2.P1]`, plus 13 `[INFERRED — Kay sign-off]` markers for un-cited decisions.
- **Verifier check:** Skipped tonight (Kay-approved) — to run in Day 4.

### REA-1.3 — First-principles architecture design ✅
- **Owner:** Hermes + Coder
- **Completed:** 2026-07-20
- **Evidence:** `docs/ARCHITECTURE_v1.0.md` (36,975 bytes). 6 planes: data, scanner, decision, execution, dashboard, guardrails. Each plane has contract, owner, files, tests, citations.
- **Supersedes:** `docs/TRADING_AGENT_ARCHITECTURE_v0.1.md` + `.hermes/plans/momentum-decision-cockpit.md` (both kept for history).
- **Review:** `tools/PLAN-ARCHITECTURE-V1-REVIEW.md` (SCOPE EXPANSION mode). 5/7 delight candidates accepted, 13 open items for Kay.
- **Pushed:** Commit `089bd64` on `pipeline-builder/day-01-relay-extension`.

### REA-1.4 — Choose real-time data path ✅
- **Owner:** Hermes
- **Completed:** 2026-07-20
- **Decision:** Approach B (IBKR consolidated tape primary, TradingView paid secondary, yfinance/Finnhub tertiary).
- **Timeframe:** 10s bars from IBKR `/bars?interval=10s&duration=1d`, 1m fallback.
- **Rationale:** IBKR is the only path to live tick + Level 2 + halt. TV is gold standard for scanners (same data DTD uses). yfinance/Finnhub is free fallback when TV cookie expires or IBGW is down.
- **Course citation:** `[C1.Ch6.P1]`, `[C1.Ch11]`, `[INFERRED — Kay sign-off on data path priority]`.
- **Drives:** Phase 2 (Data + Scanner MVP).

### REA-0.4 — Verify Alpaca real-time data tier ✅ (deprecated path)
- **Owner:** Hermes
- **Completed:** 2026-07-20
- **Decision:** v1.0 deprecates Alpaca WS in favor of IBKR. Alpaca remains as fallback (paper) only.
- **Rationale:** IBKR is the live broker path. Using one feed = no reconciliation. Alpaca is kept for paper-mode testing only.

### REA-0.1 — Clarify Gstack + Headroom method ✅
- **Owner:** Hermes
- **Completed:** 2026-07-20
- **Evidence:** `tools/BASELINE-REPORT-2026-07-20.md` (8,814 bytes) — 4 tools cloned + smoke-tested + 2 gstack skills ported to Mavis Code (`tools/gstack-mavis-port/plan-ceo-review.md`, `tools/gstack-mavis-port/review.md`).
- **Ponytail persona** adopted for NEW code only. **Headroom** installed in sandbox mode. **agency-agents** cloned (200+ specialists available on demand). **Gstack** adapted to Mavis Code.

---

## Awaiting Kay sign-off 🔴

### REA-0.2 — Verify TradingView tier on Kay's account
- **Owner:** Kay
- **Blocks:** Final ratification of 10s chart strategy
- **Acceptance:** Tier confirmed (Essential / Plus / Premium / Ultimate) or redacted screenshot
- **Default if no answer:** Use 1m bars from IBKR, 10s overlay only if TV Ultimate confirmed. Documented in `docs/ARCHITECTURE_v1.0.md` §5 Q1.

### REA-0.3 — Verify IBKR market data subscriptions on DU1234567
- **Owner:** Kay + IB Gateway Specialist
- **Blocks:** Final ratification of Level 2 / T&S path
- **Acceptance:** Confirmed whether NASDAQ TotalView + NYSE Open Book + IB News Feed are active on the paper account
- **Default if no answer:** Assume delayed, plan to subscribe if not. Documented in `docs/ARCHITECTURE_v1.0.md` §5 Q2.

### REA-1.2 — DTD screen-share with Kay
- **Owner:** Kay + Researcher
- **Type:** Research
- **Deliverable:** `docs/dtd-walkthrough-2026-07-XX.md` — per-scanner filter values + alert UX for all 24 scanners
- **Why it matters:** Confirms the 5 watch list + 5 alert MVP scanners match DTD's actual behavior, not just marketing copy. Critical for the "replicate, don't approximate" mandate.
- **Estimated effort:** 45 min screen-share.

---

## Ready (can start once Kay's blockers resolved + ARCHITECTURE_v1.0 ratified)

### REA-2.1 — IBGW relay extensions
- **Owner:** Hermes + Coder
- **Depends on:** REA-0.2, REA-0.3, REA-1.3 ratified
- **Type:** Implementation
- **Deliverable:** Extend `scripts/ibgw_relay.py` with `/quote/<sym>`, `/depth/<sym>`, `/trades/<sym>`, `/bars/<sym>?interval=...&duration=...`, `/halt/<sym>` endpoints + API key auth
- **Effort:** 1 week (CC + Hermes)
- **Effort scale:** human ~3 weeks / CC + Hermes ~1 week

### REA-2.2 — Data plane module
- **Owner:** Coder
- **Depends on:** REA-2.1
- **Deliverable:** `trading_agent/data_plane/` (5 files: tv_screener.py, ibkr_quote.py, ibkr_bars.py, yfinance_fallback.py, cache.py)
- **Tests:** Unit + integration per `docs/ARCHITECTURE_v1.0.md` §2.1

### REA-2.3 — Scanner module (10 of 24 DTD)
- **Owner:** Coder + Richard
- **Depends on:** REA-2.2
- **Deliverable:** `trading_agent/scanner/` (6 files: watch_list.py, alert_scanners.py, first_pullback.py, score.py, dedup.py, dtd_top10.json)
- **Tests:** Unit + integration per `docs/ARCHITECTURE_v1.0.md` §2.2

### REA-2.4 — Paper-mode validation
- **Owner:** Hermes + PM-Agent
- **Depends on:** REA-2.1, REA-2.2, REA-2.3
- **Deliverable:** 5 trading days of paper-mode observation. Logs in `data/scanner_runs/`.
- **Gate:** All 10 scanners fire, no crashes, dedup works.

---

## Backlog (Phase 3-9)

### REA-3.x — Decision + Execution MVP
- `trading_agent/decision/` (5 files: pipeline.py, prompts.py, conviction.py, cost_logger.py, llm_resolver.py)
- `trading_agent/execution/` (6 files: position_manager.py, ibkr_orders.py, stop_target.py, monitor_loop.py, daily_pnl.py, scale_in.py)
- `trading_agent/guardrails/` (5 files: limits.py, daily_pnl.py, position_cap.py, halt_check.py, eod.py)
- File locking for `positions.json` (`fcntl.flock` / `msvcrt.locking`)
- End-to-end paper trade test

### REA-4.x — Dashboard rewrite
- `dashboard/app.py` rewrite (3 views: Live, Watch List, History)
- Manual kill switch + override endpoints
- Daily P&L digest generator
- Healthcheck endpoint `/api/health`
- End-to-end browser test

### REA-5.x — Paper month (1 month)
- Run full pipeline, paper mode
- Daily review of P&L digest
- Weekly review of conviction accuracy
- Iterate on scanner thresholds

### REA-6.x — Live beta phased (paper → €500 → €2K)
- Each phase requires ≥60% win rate over 20 trades
- All guardrails active
- Daily P&L review with Kay

### REA-7.x — Close remaining 14 scanners
- Top Losers, Top Penny Stocks, Top Large Cap, Top Recent IPOs Moving, Penny Stocks, Earnings Movers, Low Float Top Gainers, HOD Momentum, VWAP Reclaim, Resistance Breakouts, Float Rotation, Multi-Day Consolidations, Large Cap Momentum, Running Up

### REA-8.x — Autonomy
- Self-tuning prompt engine from `trading_memory.md` reflections
- Rolling 10-trade win rate auto-scales position size
- Kay reviews weekly, not daily

---

## Phase Plan (Post-Architecture)

| Phase | Duration | Output | Gate to next |
|-------|----------|--------|--------------|
| 1. Top 10 DTD scanners | 1-2 weeks | 5 watch list + 5 alert detectors, replayable, paper-only execution | E2E test on historical data |
| 2. Dashboard v2 | 1-2 weeks | TradingView widget + scanner panels + event tape + chart + news | Kay approves visual UX |
| 3. Shadow calibration | 1-2 weeks | Run alongside DTD manually, mark discrepancies, tune | 10 sessions of measurements |
| 4. Phased live execution | ongoing | paper → €500 → €2K with 10% daily loss limit, auto-trade + 21:00 digest | 5 profitable sessions → next phase |
| 5. Close 20% (remaining 14 DTD scanners) | post-6c | Full DTD parity | Kay's call |

---

## Agent Assignments

| Agent | Specialization | Used in |
|-------|---------------|---------|
| **Coder** (Mavis Code, coder mode) | Code generation, file edits | REA-2.x, REA-3.x, REA-4.x |
| **Researcher** | Course transcripts, DTD walkthrough | REA-1.2 (with Kay) |
| **IB Gateway Specialist** | IBGW relay, entitlements, contract | REA-2.1 |
| **Gitea Agent** | Source control, branch management | All commits (used today ✅) |
| **DevOps Automator** | Docker, NAS, Portainer, CI/CD | Phase 2+ deployment |
| **PM-Agent** | Pipeline monitor, health checks | All phases (live) |
| **Verifier** (built-in) | Independent QA | Every shipped deliverable |
| **PM-Architect** (Kay) | Final sign-off on all gates | All phases |
| **Doc-Sheriff** (planned, not yet built) | Living-doc sync after accepted changes | EOD sync, weekly refresh |

---

## Definition of Done for this Kanban

- All 24 DTD capabilities working in shadow against DTD
- Concordance metric ≥80% on DTD reference observations
- Multi-position discipline wired with ¼ size start + scale-in rules
- 10s/15s/24s chart data flowing in real-time
- Live execution phased guardrails proven on paper → €500 → €2K
- Daily P&L digest at 21:00 Berlin (file fallback while Telegram dead)
- All architectural decisions cited to Course 1 or Course 2 transcript
- Doc-Sheriff agent created and registered

---

## Today's Progress (2026-07-20)

**Before today:** All REA-0 + REA-1 in Backlog / Ready. Nothing Done.

**After Day 3:**
- 5 items moved to Done: REA-0.1, REA-0.4, REA-1.1, REA-1.3, REA-1.4
- 3 items still Awaiting Kay: REA-0.2, REA-0.3, REA-1.2
- 4 items now Ready: REA-2.1, REA-2.2, REA-2.3, REA-2.4 (can start once Kay signs off)
- 5 items still in Backlog: REA-3.x through REA-8.x

**Velocity:** 5 items / 1 day (Hermes solo, Kay away). This is the upper bound; with Kay active, expect 2-3 items/day on average due to clarification cycles.

---

## Risk Register (Top 3)

1. **Kay's 3 blockers (REA-0.2/0.3/1.2) all need his input** — if he's away another day, Phase 2 stalls. Mitigation: assume defaults per `docs/ARCHITECTURE_v1.0.md` §5, document the assumptions, Kay overrides tomorrow.
2. **IBGW relay extensions** are untested at 10s cadence — could hit performance walls. Mitigation: profile early in Phase 2, fall back to 1m if needed.
3. **Conviction threshold ≥7** is a guess — could be too aggressive (over-trades) or too conservative (under-trades). Mitigation: backtest on 30 days of historical signals, tune in Phase 3.
