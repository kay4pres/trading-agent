# Environment-Shared vs Per-Environment Services Analysis

**Date:** 2026-07-09
**Context:** Trading Agent runs 3 environments (DEV / UAT / PROD). This document classifies every external data source and service as **SHARED** (one instance, all environments consume it) or **PER-ENVIRONMENT** (must be provisioned separately per environment).

---

## Classification Matrix

| Service | Shared? | Rationale |
|---------|---------|-----------|
| **Finnhub News** | ✅ SHARED | Same news feed regardless of environment |
| **Alpaca News Feed** | ✅ SHARED | Example from Kay — reusable across all dashboards |
| **Alpaca WebSocket (market data)** | ✅ SHARED | Live tick stream is market-data-only, no position risk |
| **yfinance** | ✅ SHARED | No credentials; identical public market data |
| **TradingView Premium** | ⚠️ PER-ENV | Session cookie tied to Kay's account; could be shared but risk of state confusion |
| **Alpaca Trading API** | ❌ PER-ENV | Buy/sell/position — DEV paper, UAT paper, PROD live |
| **Telegram Bot (notifications)** | ⚠️ PER-ENV | Bot token shared, but destination (group/chat) must be environment-split |
| **MiniMax LLM** | ✅ SHARED | Inference only; same model for all environments |
| **Fincept Terminal** | ❓ PER-ENV (unconfirmed) | May require credentials; data quality same across envs |
| **Kay's TradingView Alerts** | ❌ PER-ENV | Manual trigger — Kay routes to one environment at a time |

---

## Detailed Breakdown

### ✅ SHARED Services (One instance, all environments)

#### 1. Finnhub News API
- **Connector:** `news_providers.py`
- **What it does:** News headlines, sentiment scoring, catalyst detection (P4 of Five Pillars)
- **Why shared:** Finnhub returns the same news wire for all subscribers. The API key represents a subscription tier, not an environment. There is no "DEV news" vs "PROD news."
- **Credentials:** `FINNHUB_API_KEY` — one key, mounted in all 3 containers via `vault/finnhub_api_key.env`
- **Risk if shared:** Very low. Finnhub is read-only; no trade execution exposure.
- **Verdict:** Single Finnhub subscription serves all environments.

---

#### 2. Alpaca News Feed API
- **Connector:** `alpaca_connector.py` (news endpoint)
- **What it does:** Market news feed via Alpaca's `/news` REST endpoint
- **Why shared (Kay's example):** A news feed is informational — it does not open positions, change account state, or affect P&L. The same news story appears in DEV, UAT, and PROD simultaneously. Sharing avoids duplicating API calls and keeps all dashboards on the same information.
- **Credentials:** `ALPACA_API_KEY` + `ALPACA_SECRET_KEY` — one pair (paper or a dedicated info-only key), mounted in all 3 containers
- **Risk if shared:** Zero. Read-only informational endpoint.
- **Verdict:** One Alpaca news feed key shared across all environments.

---

#### 3. Alpaca WebSocket (Live Tick Feed)
- **Connector:** `alpaca_connector.py` (WebSocket client)
- **What it does:** Streams live bid/ask/quote ticks for price monitoring and exit detection
- **Why shared:** The tick stream is raw market data — it has no concept of positions or P&L. The `live_event_loop` uses ticks to detect pullbacks and check exit conditions against `positions.json`. The same tick data is valid for all environments.
- **Credentials:** Same `ALPACA_API_KEY` + `ALPACA_SECRET_KEY` pair as the news feed
- **Risk if shared:** Zero. WebSocket is read-only; no execution possible over this channel.
- **Verdict:** Single WebSocket connection shared across all environments (or one connection per container — both consume the same tick stream).

---

#### 4. yfinance
- **Connector:** `fincept_connector.py`
- **What it does:** 5-min bars, historical OHLCV, batch price quotes for intraday scanner and trader exit checks
- **Why shared:** yfinance is a free, unauthenticated Python library pulling from Yahoo Finance public feeds. The market data is identical for everyone. No credential to duplicate.
- **Credentials:** None required.
- **Risk if shared:** Zero. yfinance is entirely read-only.
- **Verdict:** No credential management needed. All environments call `yfinance` directly.

---

#### 5. MiniMax LLM (Inference)
- **Used by:** Bull/Bear inline LLM calls, Mavis orchestrator session
- **What it does:** LLM inference — conviction scoring, BULL/BEAR verdict generation, Mavis reasoning
- **Why shared:** An LLM inference call has no environment persona. The model (MiniMax M2.7) is the same; only the prompt changes (which includes `TRADING_AGENT_ENV`). Sharing the API key avoids tripling the spend.
- **Credentials:** `LLM_API_KEY` in `vault/llm_api_key.env`
- **Risk if shared:** Low. Only the prompt distinguishes DEV vs UAT vs PROD behavior.
- **Verdict:** Single LLM key shared across all environments. Use `TRADING_AGENT_ENV` in system prompts to differentiate behavior.

---

### ⚠️ PER-ENVIRONMENT Services (Must Be Provisioned Separately)

#### 6. TradingView Premium (Session Cookie)
- **Connector:** `tradingview_connector.py`
- **What it does:** Pulls gap-up stock lists, premium chart indicators, premarket scanner data
- **Why per-environment (with caution):** Kay's TradingView account session cookie authenticates to his personal TV setup — watchlists, premium indicators, chart layouts. DEV/UAT/PROD could theoretically share the same cookie, but:
  - If all 3 environments poll simultaneously with the same session, TV may throttle or log out the session.
  - A single cookie means a single "last accessed" state on TV's side.
- **Recommendation:** Could be **shared** with rate-limiting ( stagger cron times), but safest approach is **one TV session per environment** stored as:
  - `vault/tv_session_dev.env`
  - `vault/tv_session_uat.env`
  - `vault/tv_session_prod.env`
- **Risk if shared incorrectly:** Session invalidation, rate limiting, unexpected chart state.
- **Verdict:** Shared with caution (staggered polling) OR per-environment cookie. leaning SHARED with staggered timing.

---

#### 7. Alpaca Trading API (Buy / Sell / Position)
- **Connector:** `alpaca_connector.py` (REST), `trader_agent.py`, `bull_bear_signal_handler.py`
- **What it does:** Submit orders, query positions, manage account equity
- **Why per-environment — mandatory:** DEV and UAT use **Alpaca paper trading** accounts. PROD uses a **live account**. These are completely separate accounts with separate balances, positions, and order histories.
  - DEV paper account: isolated test, 100-share lots, fake fills
  - UAT paper account: pre-production validation of the full pipeline
  - PROD live account: real money, real fills
- **Credentials (per environment):**
  - `ALPACA_API_KEY` + `ALPACA_SECRET_KEY` in:
    - `vault/alpaca_api_key_dev.env`
    - `vault/alpaca_api_key_uat.env`
    - `vault/alpaca_api_key_prod.env`
  - PROD keys stored with highest privilege isolation (DPAPI on Windows host, not in plain text in Portainer)
- **Verdict:** ❌ Three completely separate Alpaca account credential sets. No sharing.

---

#### 8. Telegram Bot Notifications
- **Connector:** `telegram_sender.py`
- **What it does:** Sends alerts to Kay's Trading Team group and direct messages
- **Why per-environment — routing required:** A single bot can send to multiple destinations, but DEV, UAT, and PROD must target **different group chats** so Kay doesn't get confused DEV trade alerts mixed with PROD signals.
  - DEV group: `-5581171035_dev` (or separate label)
  - UAT group: `-5581171035_uat`
  - PROD group: `-5581171035` (current live group)
- **Bot token:** The `@Marvless01_bot` token itself is shared (one bot), but the **destination chat IDs** are environment-specific.
- **Credentials:**
  - `TELEGRAM_BOT_TOKEN` — shared (one bot)
  - `TELEGRAM_CHAT_ID_DEV`, `TELEGRAM_CHAT_ID_UAT`, `TELEGRAM_CHAT_ID_PROD` — per environment
- **Kay's direct chat ID** (`8750722880`): Used for urgent escalations. Same across all environments — Kay should receive PROD alerts directly regardless of which environment fired.
- **Verdict:** ⚠️ Bot token shared; destination routing (group chat ID) per-environment.

---

#### 9. Fincept Terminal
- **Connector:** `fincept_connector.py`
- **What it does:** Premium batch quotes, terminal-grade bar data (stale-free compared to yfinance)
- **Status:** Unconfirmed whether Fincept requires per-environment credentials or is a single subscription like yfinance.
- **Action required:** Determine if Fincept has API keys and if those keys support multiple simultaneous environments.
- **If single subscription with key:** Treat as SHARED (same logic as Finnhub).
- **If per-seat or per-environment:** Treat as PER-ENV.
- **Verdict:** ❓ Requires investigation. Flagged as pending confirmation.

---

### ❌ Environment-Specific (Manual / One-Shot)

#### 10. Kay's TradingView Alerts (Webhook Input)
- **Endpoint:** `POST /webhook/tradingview` on each dashboard
- **What it does:** Kay manually triggers a TV alert → signal injected into `signals_live.json` → Bull/Bear debate → trade decision
- **Why per-environment:** Kay chooses which environment to activate when he fires the alert. He would not want a DEV alert to enter the PROD pipeline. Routing is **intentional and manual** — he selects the environment.
- **Implementation:** Each environment's dashboard listens on its own port (5050/5051/5052), so Kay's TV alert webhook URL determines the target environment.
- **Verdict:** ❌ Not a shared service — this is an intentional manual routing decision by Kay per alert.

---

## Summary Table

| # | Service | Shared? | Per-Env Credentials Required |
|---|---------|---------|-------------------------------|
| 1 | Finnhub News API | ✅ YES | No (1 key all envs) |
| 2 | Alpaca News Feed | ✅ YES | No (1 key all envs) |
| 3 | Alpaca WebSocket (ticks) | ✅ YES | No (same key all envs) |
| 4 | yfinance | ✅ YES | None |
| 5 | MiniMax LLM | ✅ YES | No (1 key all envs) |
| 6 | TradingView Premium | ⚠️ CAUTION | Shared with staggered polling OR per-env cookie |
| 7 | Alpaca Trading API | ❌ NO | 3 separate accounts (DEV paper / UAT paper / PROD live) |
| 8 | Telegram Bot | ⚠️ PARTIAL | 1 bot token; 3 destination chat IDs |
| 9 | Fincept Terminal | ❓ TBD | Pending confirmation |
| 10 | Kay's TV Webhook | ❌ NO | Manual routing by Kay per alert |

---

## Credential Storage Requirements

### Shared Vault Entries (readable by all 3 containers)
```
vault/finnhub_api_key.env       # SHARED
vault/llm_api_key.env          # SHARED
vault/alpaca_news_ws_key.env    # SHARED (news + WS tick feed)
```

### Per-Environment Vault Entries
```
vault/tv_session_dev.env        # DEV TradingView session
vault/tv_session_uat.env        # UAT TradingView session
vault/tv_session_prod.env      # PROD TradingView session

vault/alpaca_trading_key_dev.env    # DEV paper
vault/alpaca_trading_key_uat.env    # UAT paper
vault/alpaca_trading_key_prod.env   # PROD live

vault/telegram_chat_id_dev.env      # DEV group
vault/telegram_chat_id_uat.env      # UAT group
vault/telegram_chat_id_prod.env     # PROD group
# (TELEGRAM_BOT_TOKEN.env is shared)
```

---

## Design Recommendations

1. **Adopt the pattern Kay described for Alpaca news:** Apply the same logic to Finnhub news and yfinance — they are informational only and identical across all environments.

2. **Alpaca WebSocket and News on the same key:** The news feed key and WebSocket tick feed key can be the same credential pair, shared across all environments. Only the **Trading API** key (orders/positions) is per-environment.

3. **Stagger TradingView polling:** If sharing the TV session cookie across environments, offset the cron schedules so DEV runs 14:00, UAT runs 14:05, PROD runs 14:10. This avoids TV session conflicts.

4. **Telegram routing via environment variable:**
   ```python
   TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # set per container
   ```
   All `telegram_sender.py` calls use `TELEGRAM_CHAT_ID`; the container's env var determines the destination.

5. **Confirm Fincept credential model:** Before finalizing the shared services list, verify whether Fincept keys are per-seat or unlimited-use. If unlimited, add to SHARED.
