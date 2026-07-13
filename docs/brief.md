# Trading Agent — Project Brief

## THE GOAL

Build an AI-driven trading system that learns from Ross Cameron (Warrior Trading), proves profitable in live markets, and becomes Kay's primary income through TaskFlow N.V.

**The path:**
1. **Learn** — absorb Ross's rules through Warrior Trading courses
2. **Alpha (current)** — paper trade, one trade/day, 100 shares, prove profitability
3. **Beta** — live trading with €2,000 IB broker account, 8–12 months alongside Kay
4. **Autonomy** — system runs autonomously, Kay supervises
5. **Product** — distill proven system for others

**Deadline:** July 23, 2026 (12 days remaining).
**Capital:** €2,000 IB broker account.

---

## System Status — 2026-07-13 Sunday (No Market) — BLOCKED: Telegram tokens burned

### Infrastructure
- **Gitea Actions CI/CD** — ✅ All 3 runners registered and online: DEV (org), UAT (id=7 org), PROD (id=10 repo)
- **Docker on NAS** — `trading-agent` (PROD) at `:5050` ✅ alive, `trading-agent-dev` at `:5051` ✅ alive, `trading-agent-uat` at `:5052` ✅ alive
- **UAT Network** — ✅ FIXED: attached to `trading-agent_default` bridge (was isolated on broken `20_default`)
- **Bull/Bear** — ⚠️ Intentional: runs via Mavis/Kay's Windows, not container-native
- **Scanner** — ✅ Functional, writes to Kay's local `E:\Me\TradingAgent\data\`
- **Telegram** — 🔴 ALL BROKEN: both `@Marvless01_bot` and `@Hendrika01_bot` tokens 401 Unauthorized

### Gitea Actions CI/CD ✅ OPERATIONAL
- **All 3 runners online** — DEV (nas-act-runner-dev org), UAT (nas-act-runner-uat id=7 org), PROD (nas-act-runner-prod id=10 repo)
- CI/CD fully operational — code pushes to Gitea auto-build and deploy

### Execution
- **DEV (Alpaca Paper):** `open_position()` is **simulated** — positions tracked in `positions.json`, no real orders placed 🔴
- **UAT (IBKR Paper):** ✅ Container at `:5052`, network fixed, `ib_insync` installed, `ibkr_connector.py` exists — but IBGW unreachable from container 🔴
- **PROD (IBKR Live):** BLOCKED — waits for UAT to be stable

### Active Blockers
| # | Blocker | Owner | Status |
|---|---------|-------|--------|
| 1 | **Telegram tokens burned** | Kay | 🔴 Both @Marvless01_bot and @Hendrika01_bot 401 — need new tokens from @BotFather |
| 2 | **IB Gateway unreachable** | DevOps | 🔴 Port 4002 closed from container — IBGW localhost-only on Windows |
| 3 | **premarket_screener.py missing** | DevOps/Kay | 🔴 09:14 cron fires but file doesn't exist — decide: create or remove |
| 4 | **Bull/Bear data path mismatch** | DevOps | 🔴 Windows script writes to `E:\Me\TradingAgent\data\` not NAS mount |
| 5 | **UAT image old** | DevOps | 🔴 Running Jul 3 image — no Gitea UAT branch for CI rebuild |
| 6 | ~~UAT network isolated~~ | DevOps | ✅ FIXED — `trading-agent_default` bridge |
| 7 | ~~ib_insync not installed~~ | DevOps | ✅ FIXED — v0.9.86 installed in UAT |
| 8 | ~~ibkr_connector.py missing~~ | DevOps | ✅ FIXED — created at `/app/trading_agent/ibkr_connector.py` |
| 9 | ~~All 3 runners~~ | DevOps | ✅ FIXED — all online |

### Docker Deployment
See `docker/README.md` — **Gitea Actions** is primary CI/CD. All 3 environments auto-deploy via their respective branches.

**Containers:**
- `trading-agent` (PROD) at `:5050` ✅ alive
- `trading-agent-dev` at `:5051` ✅ alive — Telegram polling active
- `trading-agent-uat` at `:5052` ✅ alive — Telegram 401 (stale token), IBKR not wired

**Runner containers:**
- `act-runner-dev` `:3031` — ✅ Online (org-level)
- `act-runner-uat` `:3032` — ✅ Online id=7 (org-level)
- `act-runner-prod` `:3033` — ✅ Online id=10 (repo-level)

---

## Strategy: First Pullback (Ross Cameron)

1. Stock **gaps up** on catalyst (earnings, FDA, upgrade, contract)
2. Stock **pulls back** — sellers take profits (wait for this)
3. **First candle making new highs = BUY signal**
4. Target: **+$0.20/share** | Stop: **entry − 2×ATR** (min $0.10) | 2:1 minimum
5. Skip trade if 2×ATR stop makes R:R worse than 2:1 with +$0.20 target
6. **2-min rule:** if price hasn't made new high within 2 bars, exit

**Entry discipline is everything.** Approving at the breakout price (chasing) is the #1 mistake.
Ross's exact words: "Wait for the pullback, then enter when the first candle makes a new high."

---

## Key Rules (from Warrior Trading Courses)

### Course 1 (Day Trading Basics) — 18 rules
### Course 2 (Strategies & Scaling):
- 5 types of risk, breakout/bailout (2-min rule), 2:1 target, daily scaling (¼ size start), halt risk, mindset management
### Course 3:
- **Ch3 P2** (News Catalyst): catalyst types (earnings, FDA, upgrades, contracts), short squeeze candidates, RV rules
- **Ch3 P5** (Building Watchlist): Ross's exact 7PM/6AM/7AM daily process
### Course 4:
- **Ch4 P1** (Daily Chart Patterns): 6 daily pillars, volume confirmation, chart patterns
- **Ch4 P2** (Daily Stock Types): float classification (nano <1M, micro 1-5M, low 5-20M, medium 20-100M, large 100M+)

### Ross's Scanner Types:
- Small Cap High Day (main trigger — stocks up >20% today)
- Top Gainer (gap-up identification)
- Continuation (established trends)
- Columns: name, price, volume, float, relative volume

### Ross's Daily Watchlist Routine:
1. **7-8 PM** — After hours top gainers on phone
2. **6 AM** — Pre-market scan (only thing at 6am)
3. **7 AM** — Build watchlist, 5-10 stocks max
4. Filters: % gain, price ($2–$20), float, RV, total vol, SI, SSR
5. Scanner at 3:30 PM Berlin

### Ch15 Key Rules:
- Alpha Phase: simulator, 100 shares, +$0.20 target, -$0.10 stop
- Beta Phase: 1 trade/day, 10 winning days → real money
- Scaling: 100→150→200 shares every 10 profitable days
- Sweet spot: price $5–$10, float <5M, RV >10×, up 50%+, breaking news NOW
- **$200/day × 300 = $60K/year = $1.5M retirement equivalent**

---

## System Status — 2026-06-29

### Today (2026-06-29) — Market Day
- **Intraday scanner ran** — 4 gap-up stocks (SPCM +3.7%, PLTR +4.7%, LCID +3.1%, TSLA +3.2%), 22 signals found, SPCM top score 4.0
- **Live loop NOT running** — alpaca_secret.enc missing from vault (Kay hasn't run store_alpaca_secret.ps1 yet)
- **Intraday scanner positional args bug** — scanner reads positional arg as symbols, --csv flag doesn't exist; fix: run with no args, picks watchlist_latest.csv automatically
- **live_event_loop.py syntax fix** — bare `return` at module level in Python 3.14 → replaced with `sys.exit(0)`, pushed to GitHub c562048
- **Watchlist:** FGBI (+10.5%, BULL+BULL+pullback) and AOUT (+17.1%, analyst upgrade) from premarket still best setups
- **Pending:** One-time: `powershell -File E:\Me\TradingAgent\vault\store_alpaca_secret.ps1` → then live loop auto-starts 15:25 every market day
- **Pending:** `live_loop_keepalive.ps1` NOT YET INSTALLED — scheduled task not registered, needs running once after secret is in vault
- **End of day 2026-06-29:** 0 trades, 0 positions, vault empty, live loop never started. Market closes 21:00 Berlin.

### Built ✅
- **Richard premarket pipeline** — TV Premium API → Finnhub news → Five Pillars → ranked watchlist CSV → `data/watchlists/watchlist_YYYYMMDD.csv` AND `data/watchlists/watchlist_latest.csv` (synced each morning)
- **Intraday scanner** (`intraday_scanner.py`) — gap-up stocks, 5-min bars, First Pullback detection
- **Trader agent** (`trader_agent.py`) — positions.json ownership, ATR-based stops, deterministic exits, Telegram notifications
- **Bull/Bear debate** (`bull_bear_prompts.py`) — Bull → Bear → Research Manager, conviction scoring, auto-approve ≥7
- **Bull/Bear wired into scan-market cron** — via `bull_bear_signal_handler.py`
- **Event-driven pipeline** — `live_event_loop.py`: Alpaca WebSocket → pullback → `signals_live.json` → scan-market cron (Bull/Bear inline) → `bull_bear_results.json` → poll → auto-open → exit monitor → journal
- **APPROVE → open_position() wired** — `handle_debate_result()` in live_event_loop, conviction≥7 auto-opens
- **positions.json** — shared contract between Richard and Trader, filters held symbols
- **Vault system** — DPAPI encrypted credentials at `E:\Me\TradingAgent\vault\` (alpaca_api_key.enc, llm_api_key.enc)
- **Standalone LLM key** — `vault/llm_api_key.enc` (DPAPI, Kay enters once), `bull_bear_runner.py` reads vault on every run, no Mavis dependency
- **Dashboard** — localhost:5050, watchlist + signals + Telegram buttons + approve/deny/skip
- **GitHub repo** — https://github.com/kay4pres/trading-agent (private)

### Bugs Fixed (2026-06-29) ✅
- `trader_agent.py get_historical()`: undefined → added yfinance implementation (ATR stop was crashing on every entry)
- `live_event_loop.py on_exit()`: double journal logging per close → removed duplicate call
- `trade_journal.md PTLE entry`: wrong exit price $6.31/P&L $25 → corrected to real $6.57/$51

### ATR-Based Stops ✅
- Stop = entry − 2× median intraday ATR (from 5-min bars, today's volatility)
- Minimum stop distance: $0.10 (never tighter)
- Skip if 2×ATR makes R:R < 2:1 with +$0.20 target
- Target always: entry + $0.20 (Ross minimum, guarantees 2:1 when stop ≥ $0.10)
- NOT 3-month daily ATR — too large on gapped stocks

### Backtest Results (2026-06-26)
17 APPROVE decisions, 7 unique symbols, ATR stops:
| Symbol | Entry | ATR | Stop Dist | R:R | Result | P&L |
|--------|-------|-----|-----------|-----|--------|-----|
| SHPH | $5.70 | $0.235 | $0.47 | 0.4:1 | SKIPPED | $0 |
| SDOT | $10.22 | $0.975 | $1.95 | 0.1:1 | SKIPPED | $0 |
| ZDAI | $2.82 | $0.040 | $0.08 | 2.0:1 | STOP_HIT | -$10 |
| CNVS | $2.96 | $0.055 | $0.11 | 1.8:1 | SKIPPED | $0 |
| BDRX | $2.80 | $0.045 | $0.09 | 2.0:1 | STOP_HIT | -$10 |
| LICN | $2.89 | $0.040 | $0.08 | 2.0:1 | STOP_HIT | -$10 |
| MODD | $4.73 | $0.110 | $0.22 | 0.9:1 | SKIPPED | $0 |

**Result: ATR correctly skipped 4 bad entries. System correctly filtered bad R:R trades. 3 losses in $0 P&L range.**
CF fixed $0.10 stop: 3 wins, 14 losses, -$96 — ATR stop is a strict improvement.

**CORE INSIGHT:** All approval prices were momentum/chasing prices, NOT first pullback entries. SDOT at $10.22 was already +44% above open. ATR correctly rejected it.
**✅ FIXED (2026-06-27):** `first_pullback_filter()` added to `intraday_scanner.py`. ATR-based pullback check: entry must be 1.5×–3× ATR below intraday high. Skips extended stocks (ZDAI-style deep pullback = entry too close to ATR stop). Combined with ATR stop = two-layer protection against chasing.

### Live Trade Result ✅
- **PTLE** (2026-06-25): LONG 100 @ $6.06 → EXIT $6.57 → **+$51 (+8.4%)** TARGET_HIT (closed 2026-06-26)
- **Current state:** 0 open positions | 1 closed trade | +$51 total P&L

### Today (2026-06-29) — Richard's Premarket ✅
- **Watchlist:** `data/watchlists/watchlist_20260629.csv` — 8 candidates scanned, 2 actionable
- **Top picks:** FGBI (10.5% gap, bull daily+5m+pullback ✓ BEST), AOUT (17.1% gap, analyst upgrade)
- **Skipped:** IVF/WSHP (halt risk), PYXS (float too high), BDRX/RYOJ (daily BEAR trend)
- **Note:** `watchlist_latest.csv` synced to curated list — was stale (raw TV large-cap scan)

### Known Issue — yfinance Intraday Data Lag (2026-06-29)
- Scanner finds correct gap % (today's close vs yesterday's close) but 5-min candle timestamps are 2-3 days stale
- Root cause: yfinance caching or rate-limiting during active market hours
- Impact: signals_live.json stays empty even when scanner finds gap-up stocks
- Fix options: (A) add `yfinance.Ticker().history(period='2d', interval='5m').tail(100)` to force fresh fetch, (B) use Alpaca as primary intraday source, (C) add `datetime` freshness check to skip stale signals
- **Low urgency** — live loop not yet running anyway

### Critical — Trader Monitoring Loop (review Course 1 before touching)
**NEED TO RE-WATCH COURSE 1. Kay's feedback: "Trader monitors every 5 min is a dead trap."**
- Ross trades on **lower timeframes** — 1-min, 2-min, 5-min bars for entry
- **The Mark** concept from Course 1 — stock can explode up OR down; 5-min polling misses this
- Trader monitoring needs to be on **tick-level or very short intervals**, not 5-min bars
- "Monitors every 5 min" is the wrong model — need to rewatch Ch1-15 for Ross's actual timeframe discipline
- **BLOCKER:** Do not touch trader_agent.py monitoring loop until Course 1 is re-reviewed

### Pending ⏳
1. ~~**Bull/Bear Telegram output**~~ ✅ Done
2. ~~**Bull/Bear LLM fix**~~ ✅ Done — inline session LLM, `bull_bear_prompts.py`, results JSON
3. ~~**6:00 AM Berlin morning cron**~~ ✅ Done — `premarket-scan` cron at 04:00 UTC (6 AM Berlin)
4. ~~**First pullback filter**~~ ✅ Done (2026-06-27) — ATR-based: 1.5×–3× ATR pullback, price above EMA_9, RSI 40–75
5. ~~**Dashboard keepalive**~~ ✅ Done (2026-06-27) — `scripts/dashboard_keepalive.ps1`
6. ~~**Watchlist wiring**~~ ✅ Done (2026-06-28) — premarket writes `watchlist_latest.csv`, live_event_loop reads it by default
7. ~~**Standalone LLM key in vault**~~ ✅ Done (2026-06-29) — `vault/llm_api_key.enc`, bull_bear_runner.py reads vault
8. **Ch13/Ch14 transcription** — raw files exist (Ch13 314MB, Ch14 130MB)
9. **Course 2 Ch5 19 patterns** — transcribe ~20 video files for Course 2 Ch5
10. **Course 2 Ch6 (Level 2, Tape Reading, Hot Keys)** — 8 MP4s, ~27GB in `knowledge/raw/`. Transcription fires Mon-Fri 21:00 Berlin (next: Mon Jun 30)
11. **Dashboard live mode verification** — confirm dashboard reads live from Alpaca WebSocket vs 5-min batch

---

## Agent Team

| Agent | Role | Schedule |
|-------|------|---------|
| **Richard** | Premarket watchlist builder | 14:00 Berlin Mon-Fri |
| **Trader** | Position monitoring + exits | Every 5 min during market |
| **Bull/Bear** | Entry quality filter | On high-conviction signals |
| **Quiz Tutor** | Ross Cameron knowledge quiz | On-demand, before trading |
| **Mavis (root)** | Orchestrator, decision-maker | All sessions |
| **scan-market** | Bull/Bear debate + position exits | Every 15 min 15:30–21:00 (fires at 15:00 too, first meaningful run is 15:30 after market open) |

---

## Architecture

See: `E:\Me\TradingAgent\docs\TRADING_AGENT_ARCHITECTURE_v0.1.md`

### Data Flow — Dual Mode (Option B)

**Mode A — Autonomous** (scanner drives):
```
Richard 14:00 → watchlist_latest.csv
scan-market cron (15:30-21:00) → signals_live.json
Bull/Bear debate (3 LLM calls) → bull_bear_results.json
live_event_loop polls → handle_debate_result()
  conviction >= threshold → AUTO-OPEN position
  conviction < threshold → Kay approval via Telegram
→ Trader monitors exits (stop/target/2-min rule) → positions.json → Telegram
```

**Mode B — Kay-Driven** (TV webhook, 2026-06-29):
```
Kay spots setup on TradingView chart
Pine Script alert fires → POST /webhook/tradingview
dashboard/app.py receives → validates → adds to signals_live.json
Kay approves via dashboard or Telegram → Trader opens position
→ Same exit monitoring as Mode A
```

### Execution & Paper Trading
- **Paper trading**: positions.json (tracking only, no real fills)
- **Live data**: Alpaca WebSocket (free tier, US stocks) — live price feed for stop/target checks
- **IBKR paper**: planned for UAT phase (same broker as live)
- **TV webhook**: `POST /webhook/tradingview` — Kay pastes into TradingView alert settings

### Bull/Bear Cost Logging (2026-06-29)
- 3 LLM calls per debate: Bull, Bear, Research Manager
- `trading_agent/cost_logger.py`: appends every call to `data/cost_log.csv`
- `python cost_logger.py`: prints 30-day cost summary
- MiniMax-M2 pricing: $0.95/M tokens (Tier 1), $0.45/M (1-5M), $0.35/M (5M+)
- Real usage from direct API calls; fallback estimates from `bull_bear_runner.py`

### Key Files
| File | Purpose |
|------|---------|
| `trading_agent/trader_agent.py` | Position tracking, ATR stops, exit logic |
| `trading_agent/bull_bear_debate.py` | Bull/Bear prompt templates |
| `trading_agent/cost_logger.py` | Token cost tracking per debate |
| `trading_agent/bull_bear_signal_handler.py` | Wires Bull/Bear into cron |
| `trading_agent/intraday_scanner.py` | Intraday 5-min signal detection |
| `trading_agent/premarket_screener.py` | Richard's premarket pipeline |
| `trading_agent/telegram_sender.py` | Telegram alerts + button responses |
| `trading_agent/live_event_loop.py` | Alpaca WS + position monitor + Bull/Bear handler |
| `dashboard/app.py` | Dashboard + TV webhook endpoint |
| `scripts/scan_market_bull_bear.py` | Bull/Bear inline runner for Mavis cron |
| `scripts/bull_bear_runner.py` | Standalone Bull/Bear (vault key) |
| `data/positions.json` | Shared positions contract |
| `data/cost_log.csv` | Token cost log (append-only) |
| `data/signals_live.json` | Pending signals (scanner + TV webhook) |
| `vault/` | DPAPI-encrypted credentials |

---

---

## Quiz System (2026-06-27)
**Built to test Trader's Ross Cameron knowledge before going live.**

| File | Purpose |
|------|---------|
| `quiz/bank/quiz_bank.json` | 58 questions across 7 chapters, Easy/Medium/Hard |
| `quiz/run_quiz.py` | Interactive quiz runner |
| `quiz/eval_engine.py` | Self-evaluation + weak-area tracking |
| `quiz/progress.json` | All-time score tracking |
| `quiz/course1_full_quiz.md` | Human-readable quiz for reference |

**Usage:**
- `python run_quiz.py` → Full 50-question quiz (random)
- `python run_quiz.py --chapter Ch15` → Chapter-specific
- `python run_quiz.py --weak-areas` → Practice weak topics
- `python run_quiz.py --md` → Generate markdown quiz
- `python eval_engine.py --report` → Full performance report

**Question breakdown:**
- Ch15 Trading Plan: 16 questions
- Ch5 Intraday Patterns: 17 questions
- Scanners & Screeners: 12 questions
- Risk Management: 4 questions
- Ch3 News Catalyst: 4 questions
- Ch4 Daily Stock Types: 3 questions
- Ch4 Daily Chart Patterns: 2 questions

**Difficulty:** 31 easy, 23 medium, 4 hard.

**Self-evaluation:** After each quiz, weak areas (<70%) are tracked in progress.json and targeted in future sessions. Goal: ≥80% per chapter before live trading.

---

## Docker Deployment (NAS via Portainer) — LIVE 2026-07-01

**Stack:** Docker Compose on NAS (Portainer). Container running: `trading-agent` at `http://10.8.0.10:5050`

### Files
| File | Purpose |
|------|---------|
| `docker/Dockerfile` | Builds from GitHub, Python 3.12-slim, no GPU |
| `docker/docker-compose.yml` | Portainer deploy config |
| `docker/README.md` | Step-by-step build + deploy + rollback guide |
| `entrypoint.py` | Python entrypoint (no shell escaping), reads env vars → writes vault files |
| `trading_agent/telegram_sender.py` | Token: env var → vault file → DPAPI (Windows fallback) |

### How It Works

```
Container: nas:5000/trading-agent:latest
    │
    ├── entrypoint.py (Python — no shell escaping)
    │       │
    │       ├── Reads env vars from Portainer
    │       ├── Writes /app/vault/*.env (chmod 600)
    │       ├── Installs crontab
    │       └── Starts cron + live_loop + dashboard
    │
    ├── Cron (14:00 Berlin): Richard premarket screener
    ├── Cron (15:30–21:00): scan-market + Bull/Bear debate
    └── Cron (21:00): transcription sprint
```

### Build & Deploy (Portainer)

1. GitHub → **Settings → Danger Zone → Make public**
2. Portainer **Images** → **Build a new image**
   - Name: `nas:5000/trading-agent:latest`
   - Dockerfile: paste `docker/Dockerfile`
3. Build → GitHub → **Make private**
4. **Containers** → **Add container**
   - Image: `nas:5000/trading-agent:latest` | Always pull: ✅ | Restart: unless-stopped
   - **Volumes (Bind, Writable):** `/app/vault` → `/data/compose/1/vault` | `/app/data` → `/data/compose/1/data`
   - **Env vars:** ALPACA_API_KEY, ALPACA_SECRET_KEY, TELEGRAM_BOT_TOKEN, MINIMAX_API_KEY

### Dashboard
- `http://10.8.0.10:5050` (WireGuard)
- API: `http://10.8.0.10:5050/api/state`

### Reusable lesson
**Telegram 409 Conflict** = two polling processes with same bot token. Kill all local Python/dashboard processes before starting Docker container. Conflict clears automatically after 1-2 min.

### Credential Loading Priority (telegram_sender)
1. `TELEGRAM_BOT_TOKEN` env var (Docker) ✅
2. `/app/vault/TELEGRAM_BOT_TOKEN.env` (written by entrypoint.py) ✅
3. DPAPI vault file (Windows local) ✅

---

## Credentials (hard rule — never in chat/logs)
- Telegram bot: @Marvless01_bot | Group: -5581171035 | Chat: 8750722880
- NAS: WireGuard `10.8.0.10`, Z:\ backsup to NAS
- DB: `mindgentic_dev` @ `10.8.0.10:5432`
- Token rotation: revoke immediately → new value → DPAPI encrypt → vault
- Kay enters credentials himself via GUI/secure input — Mavis never asks in chat

---

## Course Status
| Chapter | Status | Notes |
|---------|--------|-------|
| Ch1 (Intro) | ✅ | Course 2 |
| Ch2 (Risk Management) | ✅ | Course 2 |
| Ch3 P1 (Stock Selection) | ⏳ | 5.3GB, not uploaded |
| Ch3 P2 (News Catalyst) | ✅ | Transcribed |
| Ch3 P3 (Fundamental Analysis) | ⏳ | 67 min, not uploaded |
| Ch3 P5 (Watchlist) | ✅ | Transcribed |
| Ch4 P1+2 (Daily Patterns) | ✅ | Transcribed |
| Ch5 (Reading Charts) | ✅ | 9 files, 4.5h, transcribed |
| Ch5 (Intraday Patterns) | ✅ | 19 files, 6.5h, transcribed |
| Ch12 (Scanning 101) | ✅ | Transcribed |
| Ch13 (Psychology) | ⏳ | 314MB, ready |
| Ch14 (Preparing to Start) | ⏳ | 130MB, ready |
| Ch15 (Trading Plan) | ✅ | Transcribed |
| Ch6 (Level 2, Tape Reading, Hot Keys) | ⏳ | 8 videos + slides, in raw/, ready for transcription |

---

## What to Avoid
- Don't build infrastructure before proving the workflow
- Don't execute live trades in alpha (paper only)
- Don't chase Expert marketplace skills — build our own
- Don't let scanner re-alert on stocks already in position
- Don't approve at breakout prices — wait for first pullback
- Don't use 3-month daily ATR for intraday stops
- Credentials never in chat or logs
---

## Backlog

### High Priority
- **Course 2 Ch7** — not yet uploaded to `knowledge/raw/`. Upload, then transcribe.
- **Ch13/Ch14 transcription** — raw files ready (Ch13 314MB, Ch14 130MB)

### Medium Priority
- **Dashboard live mode** — confirm dashboard reads live from Alpaca WebSocket vs 5-min batch polling. Ross's momentum trading (Ch7) depends on real-time data.
- **Course 1 review** — Kay re-watching for The Mark + timeframe discipline. Needed before unblocking the lower-timeframe monitoring loop.
- **positions.json file locking** — Richard and Trader both read/write positions.json. Add a simple lock file to prevent race conditions.

### Low Priority
- **Backtest runner** — using historical data to validate the ATR pullback filter on historical signals.
- **Scale-in rules** — from Course 2: start at ¼ size, scale in on confirmation. Phase 2 feature.