# Pipeline Status — 2026-07-07 15:30 (Berlin, UTC+2)

## Dashboard State (live check 15:30)
| Field | Value | Notes |
|---|---|---|
| `last_scan` | 15:30 | ✅ Scanner is live and updating |
| `market_open` | true | ✅ |
| `watchlist` | 7 stocks | ✅ (LHSW, PEW, SEER, WBX, SPHL, CRE, YDES — from premarket CSV) |
| `signals` | 7 signals | ✅ Today's signals showing |
| `positions` | `[]` | No open positions |
| `bull_bear` | `[]` | No debates yet |
| `mount_status` | `ok` | ✅ Watchlist CSV now visible to container |
| `pillars` | ❌ **EMPTY** | **BUG FOUND: P1-P5 scores not displaying** |

## Root Cause — Five Pillars Scores Lost at CSV Round-Trip

### The Bug
Richard's `premarket_screener.py` computes P1-P5 scores correctly in `check_pillars()`.
However, `save_watchlist()` explicitly excluded `pillars` from the CSV output:
```python
row = {k: v for k, v in r.items() if k not in ('pillars',)}
```

When the dashboard's `app.py` loaded the CSV back, it had no pillar data and hardcoded:
```python
'pillars': {},  # ← always empty
```
This happened in TWO places: `load_premarket_watchlist()` and `_load_watchlist_csv()`.

### Evidence
- All 7 signals in dashboard have `"pillars": {}`
- `total_score` shows (e.g., 3.0) — score IS computed, just not persisted
- fincept_connector NOT the issue — yfinance fallback works fine (quote layer healthy)

## Fix Applied ✅ (commit `ca0ff79`)

### 1. `trading_agent/premarket_screener.py`
Changed `save_watchlist()` to write `pillars_json` column:
```python
row['pillars_json'] = json.dumps(row.get('pillars', {}))
```
Added `'pillars_json'` to CSV fieldnames. Removed the `if k not in ('pillars',)` exclude.

### 2. `dashboard/app.py`
Two fixes (lines ~88 and ~308):
```python
'pillars': json.loads(row.get('pillars_json', '{}')) or {},
```

### Commit
- Gitea: `ca0ff79 fix: persist Five Pillars scores to CSV and deserialize in dashboard`
- GitHub push: timed out (network issue from this machine) — push manually or run from NAS shell

## Docker Container Restart Required
The fix is in the source code, but the running container still has the old `app.py`.
Container must be redeployed to pick up the changes:
- Portainer → Stacks → trading-agent → Recreate container
- Or: GitHub Actions build → push to NAS registry → Portainer webhook

## What's Working
- ✅ Dashboard alive on port 5050, updating every 60s
- ✅ Scanner live (last_scan: 15:30)
- ✅ fincept_connector / yfinance fallback healthy (no quote errors)
- ✅ 7 signals from today's premarket watchlist (LHSW, PEW, SEER, WBX, SPHL, CRE, YDES)
- ✅ Docker volume mount now OK (watchlist visible)
- ✅ Telegram alerts wired

## What's Fixed
- ✅ **Pillars display bug** — fix committed to `dev` branch

## What's Still Pending
- ⏳ Docker container restart (needed for fix to take effect)
- ⏳ GitHub push (network timeout from this machine)
- ⏳ Bull/Bear LLM pipeline (LLM key not stored — Kay needs to run `vault/store_llm_key.ps1`)
- ⏳ Trader agent — position tracking, deterministic exits, live price monitoring
- ⏳ Bull/Bear debate design — adapt TradingAgents pattern for Ross Cameron rules

## Today's Signals (7 stocks, 2026-07-07 premarket)
| Symbol | Price | Gap | RelVol | Float | Score | P4 |
|---|---|---|---|---|---|---|
| LHSW | $6.80 | +278% | 49.8× | 0.3M | 3.0 | 1.0 |
| PEW | $2.85 | +21% | 36.0× | 20.7M | 3.0 | 1.0 |
| SEER | $2.19 | +35% | 28.5× | 40.1M | 3.0 | 1.0 |
| WBX | $5.62 | +35% | 14.3× | 3.5M | 3.0 | 1.0 |
| SPHL | $2.96 | +16% | 146.3× | 1.0M | 2.8 | 0.75 |
| CRE | $2.75 | +10% | 21.8× | 1.1M | 2.8 | 0.75 |
| YDES | $2.34 | +23% | 37.8× | 0.3M | 2.5 | 0.5 |

## Cron Health
- `premarket-scan` (Richard 14:00 Berlin): ✅ Today's watchlist generated
- `scan-market` (Mavis 15:30-21:00): ✅ Running every 15 min
- `pipeline-check` (this session): ✅ Running at 15:30
