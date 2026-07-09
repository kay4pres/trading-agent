# Trading Agent — Environment Separation Proposal

**Author:** Kay  
**Date:** 2026-07-09  
**Status:** Draft  
**Reference:** Based on `E:/Me/AI-Brain/projects/trading-agent/docs/{ARCHITECTURE_OVERVIEW, TECHNICAL_BACKEND, OPERATIONAL_OVERVIEW}`

---

## 1. Current State

Single Docker stack on NAS (`10.8.0.10`), single Portainer stack, one `dev` schema in PostgreSQL, all environments mixed into one container. Key secrets (Alpaca API keys, LLM API key) are missing from vault — currently blocking the Bull/Bear debate and live trading.

```
┌─────────────────────────────────────────────────────────┐
│  NAS 10.8.0.10  (WireGuard VPN)                        │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Portainer :19900                                  │   │
│  │  └── 1 Stack: trading-agent                       │   │
│  │       └── 1 Container: trading-agent:latest       │   │
│  │            ├── Richard (premarket)                │   │
│  │            ├── Bull/Bear inline LLM               │   │
│  │            ├── Trader Agent                        │   │
│  │            ├── live_event_loop                     │   │
│  │            ├── Dashboard (Flask :5050)             │   │
│  │            └── Telegram bot polling                │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─ NAS Volumes ────────────────────────────────────┐  │
│  │ /volume1/Docker/vault/       ← ALL envs mixed     │  │
│  │ /volume1/Docker/data/       ← ALL envs mixed     │  │
│  │ /volume1/Docker/config/     ← ALL envs mixed     │  │
│  │ /volume1/Docker/knowledge/  ← ALL envs mixed     │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌─ PostgreSQL ─────────────────────────────────────┐  │
│  │ 10.8.0.10:5432  mindgentic_dev                     │  │
│  │  ├── dev schema   (mostly unused)                  │  │
│  │  ├── uat schema  (empty)                           │  │
│  │  └── prod schema (empty)                           │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌─ Gitea :3000 ──────────────────────────────────────┐  │
│  │ trading/trading-agent  (source of truth)           │  │
│  │ kay/ai-brain                                       │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Separation Principle

**Air-gapped by credential + data + network posture — shared by infrastructure.**

| Dimension | DEV | UAT | PROD |
|-----------|-----|-----|------|
| Credentials | Test-only API keys | Real paper trading keys | Real live trading keys |
| Network | Local/sandbox APIs where available | Real Alpaca paper, no market impact | Real Alpaca live + IBKR |
| Data | Synthetic/mock data OK | Real market data, paper positions | Real money, real positions |
| Access | Kay only | Kay + automated agents | Hardened, minimal human touch |

---

## 3. Components That MUST Be Separate Per Environment

### 3.1 Docker Containers — One Stack Per Environment

Each environment gets its own Portainer stack and container(s). No sharing between environments.

```
DEV stack     →  trading-agent-dev:latest
UAT stack     →  trading-agent-uat:latest
PROD stack    →  trading-agent-prod:latest
```

Rationale: A crash or bad deploy in DEV must never affect UAT or PROD. Separate `:latest` image tags per environment prevent a single `docker-compose pull` from bleeding across environments.

### 3.2 Vault Credentials — Fully Isolated Per Environment

Vault directories on NAS, completely separate:

```
/volume1/Docker/vault-dev/     ← DEV credentials only
/volume1/Docker/vault-uat/     ← UAT credentials only
/volume1/Docker/vault-prod/    ← PROD credentials only
```

Each vault directory contains:

| File | DEV | UAT | PROD |
|------|-----|-----|------|
| `alpaca_api_key.env` | DEV paper key | **UAT paper key** | **PROD live key** |
| `alpaca_secret.env` | DEV paper secret | **UAT paper secret** | **PROD live secret** |
| `llm_api_key.enc` | DEV MiniMax key | **UAT MiniMax key** | **PROD MiniMax key** |
| `telegram_bot_token.env` | Same bot OK | Same bot OK | Same bot OK |
| `ibkr_credentials.env` | Mock/none | Paper account | **Live account** |

Rationale: PROD credentials on the DEV vault is the single highest-risk misconfiguration in a system like this. Physical isolation (different directories, different Portainer environment variable sets) makes credential bleed impossible.

### 3.3 Database Schemas — Strictly Isolated

```
PostgreSQL mindgentic_dev @ 10.8.0.10:5432
├── dev schema    ← DEV trades, signals, backtest results
├── uat schema    ← UAT paper trades (Alpaca paper)
└── prod schema   ← PROD live trades (IBKR)
```

Each schema has identical tables. Agents in each environment connect with `schema=<env>` in the connection string.

Rationale: Trade history, open positions, and performance metrics must never cross-contaminate environments. A PROD analyst querying the wrong schema is a compliance and financial risk.

### 3.4 Alpaca API Keys — Separate Per Environment

| Environment | Alpaca Key Type | Purpose |
|-------------|----------------|---------|
| DEV | Test/mock — no real market interaction | Development and debugging |
| UAT | **Paper trading key** — real market data, simulated fills | Pre-production validation |
| PROD | **Live trading key** — real money | Actual trading |

> **Warning:** Alpaca paper and live keys look similar. Label them explicitly (`ALPACA_PAPER_KEY`, `ALPACA_LIVE_KEY`) and store in separate vault directories.

### 3.5 Telegram Bots — Separate Per Environment (Recommended)

| Environment | Bot | Chat ID | Rationale |
|-------------|-----|---------|-----------|
| DEV | `@Marvless01_bot` or dev clone | DEV-only group | Test alerts don't pollute live chat |
| UAT | `@Marvless01_bot` or UAT clone | UAT group | Pre-prod notifications |
| PROD | `@Marvless01_bot` | PROD group | Real trade alerts |

Minimum viable: keep 1 bot but use **separate chat IDs** (DEV group, UAT group, PROD group). Kay's personal chat (8750722880) receives PROD only.

### 3.6 NAS Data Volumes — Separate Subdirectories Per Environment

```
/volume1/Docker/
├── vault-dev/       ← DEV credentials
├── vault-uat/       ← UAT credentials
├── vault-prod/      ← PROD credentials
├── data-dev/        ← DEV watchlists, signals, positions
├── data-uat/        ← UAT watchlists, signals, positions
├── data-prod/       ← PROD watchlists, signals, positions
├── config-dev/      ← DEV TradingView session, Finnhub keys
├── config-uat/      ← UAT config
├── config-prod/     ← PROD config (hardened)
└── knowledge/       ← SHARED: course transcripts, rules, quiz bank
```

The `knowledge/` directory (course transcripts, rules, quiz bank) is shared read-only across all environments — it is read-only design reference data, not trade data.

---

## 4. Components That CAN Be Shared

### 4.1 Gitea (Source of Truth)

```
http://10.8.0.10:3000
├── trading/trading-agent     ← single repo, all environments deploy from here
└── kay/ai-brain
```

**How it works:** Git branches map to environments:

| Branch | Environment | Deploy Trigger |
|--------|------------|----------------|
| `dev` | DEV | Auto-deploy on push to `dev` |
| `uat` | UAT | Auto-deploy on push to `uat` |
| `main` | PROD | Manual tag / approval required |

Tagging and branch protection on `main` prevents unreviewed code reaching PROD.

### 4.2 Portainer Instance (Single Installation)

One Portainer at `http://10.8.0.10:19900` managing **3 separate environments (stacks)**:

```
Portainer Environments:
├── NAS-Dev    → stack: trading-agent-dev
├── NAS-UAT    → stack: trading-agent-uat
└── NAS-Prod   → stack: trading-agent-prod
```

Each Portainer "environment" maps to a different Docker context or endpoint, all on the same NAS host. This is standard Portainer behavior — no additional install needed.

### 4.3 NAS Hardware (10.8.0.10)

The NAS itself is shared infrastructure. It hosts all volumes (dev/uat/prod) and runs all container stacks. This is fine — the separation is at the volume and credential level, not the hardware level.

### 4.4 WireGuard VPN

Same WireGuard VPN (`10.8.0.10`) connects all environments to the NAS. No change needed — credentials and data paths are environment-scoped.

### 4.5 Dashboard (Flask)

| Environment | URL | Container Port | Host Port |
|-------------|-----|---------------|-----------|
| DEV | `http://10.8.0.10:5050` | 5050 | **5050** |
| UAT | `http://10.8.0.10:5051` | 5050 | **5051** |
| PROD | `http://10.8.0.10:5052` | 5050 | **5052** |

Three separate container instances, different host ports, same Flask app. Each reads from its own `data-{env}/` and `vault-{env}/`.

### 4.6 PostgreSQL Instance (Same Host, Different Schemas)

One PostgreSQL database (`mindgentic_dev`) serving all 3 environments via schema separation. This is already the design — schemas provide logical isolation on shared infrastructure.

### 4.7 Knowledge/Course Data (Read-Only Reference)

```
/volume1/Docker/knowledge/
├── rules/           ← SHARED: c*_rules.md (Ross Cameron course)
├── quiz/            ← SHARED: quiz_bank.json
└── memory/          ← Per-environment: trade_journal_dev.md, trade_journal_uat.md, trade_journal_prod.md
```

Course rules and quiz bank are immutable reference data. Trade journals are per-environment.

---

## 5. Proposed Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│  KAY'S MACHINE (Windows)                                                  │
│                                                                          │
│  ┌── Git ─────────────────────────────────────────────────────────────┐ │
│  │  E:\Me\TradingAgent  →  Gitea :3000 (trading/trading-agent)        │ │
│  │                                                                    │ │
│  │  branches: dev (auto-deploy) / uat (auto-deploy) / main (manual)  │ │
│  └───────────────────────────────────────────────────────────────────  │ │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                     ┌──────────────┼──────────────┐
                     │              │              │
                     ▼              ▼              ▼
              ┌──────────┐ ┌──────────┐   ┌──────────────┐
              │   DEV    │ │   UAT    │   │    PROD      │
              │  @Dev    │ │  @UAT    │   │  @ProdBot    │
              │  group   │ │  group   │   │  Kay's DM    │
              └────┬─────┘ └────┬─────┘   └──────┬───────┘
                   │            │                │
┌──────────────────┼────────────┼────────────────┼──────────────────────────┐
│  NAS 10.8.0.10   │            │                │                        │
│  WireGuard VPN   │            │                │                        │
│                  │            │                │                        │
│  ┌───────────────┴─────────────┴────────────────┴───────────────┐        │
│  │               Portainer :19900                               │        │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │        │
│  │  │  NAS-DEV     │  │  NAS-UAT     │  │  NAS-PROD    │        │        │
│  │  │  (Endpoint)  │  │  (Endpoint)  │  │  (Endpoint)  │        │        │
│  │  │              │  │              │  │              │        │        │
│  │  │ dev stack    │  │ uat stack    │  │ prod stack   │        │        │
│  │  │  • vault-dev │  │  • vault-uat │  │  • vault-prod│        │        │
│  │  │  • data-dev  │  │  • data-uat  │  │  • data-prod │        │        │
│  │  │  • config-dev│  │  • config-uat│  │  • config-prd│        │        │
│  │  │  • :5050     │  │  • :5051     │  │  • :5052     │        │        │
│  │  └──────────────┘  └──────────────┘  └──────────────┘        │        │
│  └────────────────────────────────────────────────────────────────┘        │
│                                                                          │
│  ┌─ PostgreSQL ──────────────────────────────────────────────────────┐   │
│  │  10.8.0.10:5432  mindgentic_dev                                  │   │
│  │  ├── dev schema     ← Richard DEV, Trader DEV, Bull/Bear DEV      │   │
│  │  ├── uat schema     ← Richard UAT, Trader UAT, Bull/Bear UAT      │   │
│  │  └── prod schema    ← Richard PROD, Trader PROD, Bull/Bear PROD  │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌─ Shared (Read-Only) ──────────────────────────────────────────────┐   │
│  │  /volume1/Docker/knowledge/rules/     ← course rules (all envs)  │   │
│  │  /volume1/Docker/knowledge/quiz/       ← quiz bank (all envs)     │   │
│  │  Gitea :3000                           ← single source of truth  │   │
│  └───────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘

                      External Services
         ┌──────────────┼──────────────────┐
         ▼              ▼                  ▼
  ┌─────────────┐ ┌──────────────┐  ┌──────────────┐
  │ TradingView │ │  Alpaca      │  │   IBKR       │
  │  Premium    │ │  (Paper)     │  │   (Prod)     │
  │  (all envs) │ │  DEV+UAT     │  │   PROD only  │
  └─────────────┘ └──────────────┘  └──────────────┘
```

---

## 6. Environment Matrix

| Component | DEV | UAT | PROD | Shared? |
|-----------|:---:|:---:|:----:|:-------:|
| Docker container(s) | ✅ separate | ✅ separate | ✅ separate | ❌ |
| Portainer stack | ✅ separate | ✅ separate | ✅ separate | ❌ |
| Vault credentials | ✅ separate | ✅ separate | ✅ separate | ❌ |
| Alpaca API keys | ✅ dev/mock | ✅ paper | ✅ live | ❌ |
| IBKR credentials | ❌ none | ❌ none | ✅ live | ❌ |
| Telegram bot token | ✅ separate | ✅ separate | ✅ separate | ❌ |
| Telegram chat ID | DEV group | UAT group | PROD group | ❌ |
| NAS data volume | ✅ data-dev | ✅ data-uat | ✅ data-prod | ❌ |
| NAS vault volume | ✅ vault-dev | ✅ vault-uat | ✅ vault-prod | ❌ |
| PostgreSQL schema | ✅ dev | ✅ uat | ✅ prod | ❌ |
| Dashboard port | :5050 | :5051 | :5052 | ❌ |
| Gitea repo (source) | — | — | — | ✅ |
| Git branch | `dev` | `uat` | `main` | ✅ |
| Course/rules knowledge | — | — | — | ✅ shared RO |
| Quiz bank | — | — | — | ✅ shared RO |
| WireGuard VPN | — | — | — | ✅ shared |
| Portainer instance | — | — | — | ✅ shared |
| NAS hardware | — | — | — | ✅ shared |

---

## 7. Migration Path (From Current State)

### Phase 1 — Stabilize Current (Day 1)

1. **Add missing keys to current vault** — store Alpaca paper keys and MiniMax LLM key so Bull/Bear and Trader can actually run.
2. **Tag current container image** → `nas:5000/trading-agent:stable` as baseline.

### Phase 2 — Create DEV Environment (Day 2–3)

1. Create `vault-dev/` on NAS with DEV credentials.
2. Create `data-dev/`, `config-dev/` directories.
3. In Portainer, add new environment endpoint `NAS-DEV`.
4. Deploy `docker-compose.dev.yml` pointing to `vault-dev/`, `data-dev/`, schema `dev`.
5. Verify Bull/Bear, Richard, and Trader run in DEV container.
6. Point Telegram DEV bot to DEV group.

### Phase 3 — Create UAT Environment (Day 4–5)

1. Create `vault-uat/` with real Alpaca paper keys.
2. Create `data-uat/`, `config-uat/` directories.
3. In Portainer, add endpoint `NAS-UAT`.
4. Deploy `docker-compose.uat.yml` pointing to `vault-uat/`, `data-uat/`, schema `uat`.
5. Run pipeline end-to-end with paper trading — validate trade signals, exits, Telegram alerts.
6. Tune Bull/Bear conviction thresholds based on UAT results.

### Phase 4 — Create PROD Environment (Day 6–7)

1. Create `vault-prod/` with live Alpaca + IBKR credentials (hardened — minimal access).
2. Create `data-prod/`, `config-prod/`.
3. In Portainer, add endpoint `NAS-PROD`.
4. Deploy `docker-compose.prod.yml` pointing to `vault-prod/`, `data-prod/`, schema `prod`.
5. Set branch protection on `main` — require PR + review to merge.
6. Point Telegram PROD bot to PROD group + Kay's DM.

### Phase 5 — Cut Over (Day 8+)

1. Freeze DEV and UAT — they remain as monitoring environments.
2. PROD becomes the live trading stack.
3. Set up `git tag` releases for PROD: `v1.0.0-prod`, `v1.1.0-prod`, etc.

---

## 8. Key Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| PROD credentials accidentally written to DEV vault | Medium | Separate `vault-dev/`, `vault-uat/`, `vault-prod/` directories; Portainer env vars scoped per stack |
| UAT trades with live Alpaca key | Low | Explicit labeling: `ALPACA_PAPER_KEY` vs `ALPACA_LIVE_KEY`; different vault dirs |
| Bull/Bear LLM costs accumulate across DEV+UAT | Medium | Per-environment `llm_api_key.enc`; monitor MiniMax dashboard per key |
| Single NAS failure takes all environments down | Low | Z: drive backups already exist; extend `ai-brain-backup` cron to cover all three data dirs |
| Telegram alert fatigue from 3 environments | Medium | Separate chat IDs per environment; Kay's DM only gets PROD alerts |

---

## 9. Summary

**Must separate:** Docker containers (per stack), vault credentials (per env), Alpaca/IBKR keys (per env), Telegram bots (or at minimum chat IDs), database schemas, NAS data volumes, dashboard ports.

**Can share:** Gitea (branches), Portainer (instance, different endpoints), NAS hardware, WireGuard VPN, course/knowledge data, PostgreSQL host.

The migration is incremental — no big-bang cutover. Build DEV first, validate the pattern, then clone to UAT and PROD with progressively more sensitive credentials.
