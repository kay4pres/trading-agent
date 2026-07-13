# Trading Agent CI/CD Architecture
## DevOps Automator — Kay's Trading Agent
**Date:** 2026-07-04
**Status:** DESIGN DRAFT — awaiting Kay's approval

---

## 1. What We Found

### 1.1 Plain-Text Credentials — AUDIT FAILURE ❌

`\\10.8.0.10\Docker\PortainerCE\data\compose\10\stack.env` contains:
```
ALPACA_API_KEY=PKOVKNXVN43NJM3P3R5GQPWEB6
ALPACA_SECRET_KEY=4zPTVSf3QqFXC2qxusR7H55uhck5BcpQk8SfocR2PnCf
TELEGRAM_BOT_TOKEN=8940612948:AAGGwuXwSumMGcrQVPKbqMkrLivd6kX3_Ss
MINIMAX_API_KEY=sk-cp-_feW8j1rKU6djBAwC_JlM3umPcbXpoyWsJTs6xWFCobUD4sxP3_f13dUwTSj-Tc4UrgxvgvnCyUKohBCgdy_hBzf19P9y0GhNDSWaNTO4spYpOIcUVhWzII
```

Also at `\\10.8.0.10\Docker\vault\`:
```
ALPACA_API_KEY.env        (plain text)
ALPACA_SECRET_KEY.env     (plain text)
MINIMAX_API_KEY.env       (plain text)
TELEGRAM_BOT_TOKEN.env    (plain text)
```

**Action:** All plain-text files must be encrypted or removed before any audit.

### 1.2 Current Stack (Stack ID 10)
- **Container:** `trading-agent` on port 5050
- **Image:** `nas:5000/trading-agent:latest`
- **Compose:** Portainer stack (standalone, NOT Swarm)
- **Credentials:** Plain-text `stack.env`
- **Dashboard:** `http://10.8.0.10:5050` ✅

### 1.3 Gitea Setup
- **URL:** `http://10.8.0.10:3000`
- **Repo:** `trading/trading-agent` (source of truth)
- **Docker socket:** mounted in Gitea container (`/var/run/docker.sock`)
- **Gitea Actions:** NOT yet enabled on the repo ❌

### 1.4 Docker Swarm Status
- **Unknown** — cannot confirm from remote. Port 9000 (Portainer) is bound to localhost on NAS, unreachable externally.
- **Likely:** Asustor NAS does NOT run Docker Swarm by default. Portainer uses standalone Docker.

---

## 2. Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Gitea (10.8.0.10:3000)                  │
│   Source of truth — dev / uat / main branches                   │
│   Gitea Actions runner (Docker container on NAS)                 │
└────────────────────────┬────────────────────────────────────────┘
                         │ push to branch
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              Gitea Actions Workflow (.gitea/workflows/)          │
│  on push to dev  → build + deploy to trading-agent-dev   :5050  │
│  on push to uat  → build + deploy to trading-agent-uat  :5051  │
│  on push to main → build + deploy to trading-agent-prod :5052  │
└────────────────────────┬────────────────────────────────────────┘
                         │ docker build / push / Portainer API
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    NAS:5000 Docker Registry                       │
│              nas:5000/trading-agent:dev|uat|prod                │
└────────────────────────┬────────────────────────────────────────┘
                         │ Portainer API calls
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Portainer (10.8.0.10:19900)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  dev stack   │  │  uat stack   │  │  prod stack  │          │
│  │  port 5050   │  │  port 5051   │  │  port 5052   │          │
│  │  :dev tag    │  │  :uat tag    │  │  :prod tag   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                         │
                         │ secrets mounted from vault
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              Vault Directory (audit-compliant)                     │
│   /volume1/Docker/vault-dev/    (dev credentials)               │
│   /volume1/Docker/vault-uat/    (uat credentials)               │
│   /volume1/Docker/vault-prod/   (prod credentials)              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Environment Definitions

| Aspect       | DEV                          | UAT                          | PROD                         |
|--------------|------------------------------|------------------------------|------------------------------|
| **Branch**   | `dev`                        | `uat`                        | `main`                       |
| **Container**| `trading-agent-dev`          | `trading-agent-uat`          | `trading-agent-prod`         |
| **Image tag**| `nas:5000/trading-agent:dev` | `nas:5000/trading-agent:uat` | `nas:5000/trading-agent:prod`|
| **Dashboard**| `10.8.0.10:5050`             | `10.8.0.10:5051`             | `10.8.0.10:5052`             |
| **Bot**      | Separate dev bot             | Separate uat bot             | Separate prod bot            |
| **Alpaca**   | Paper (same — paper only)    | Paper (same — paper only)    | Paper (same — paper only)    |
| **Data dir** | `/volume1/Docker/ta-dev/`    | `/volume1/Docker/ta-uat/`    | `/volume1/Docker/ta-prod/`   |
| **Auto-deploy**| Yes (on push)             | Yes (on push)                | Yes (on push, with approval) |

---

## 4. Secrets Strategy (Audit-Compliant)

### 4.1 The Problem
Plain-text credentials in `stack.env` and `vault/` directories fail any security audit.

### 4.2 Vault Solution: Gitea Actions Secrets + Portainer Env Var Substitution

**Chosen approach:** Gitea Actions Secrets (per environment) + Portainer stack environment variables

**Why:** No Swarm required, native to Gitea, no external vault service needed, audit-trail via Gitea.

**How it works:**
1. Kay enters secrets in Gitea Actions UI per repo (Settings → Secrets)
2. Gitea Actions workflow injects secrets as environment variables during build/deploy
3. Workflow calls Portainer API to update the stack's environment variables
4. Portainer redeploys the stack with new env vars
5. Container reads env vars at startup

**Secrets per environment:**

| Secret Name          | DEV  | UAT  | PROD |
|----------------------|------|------|------|
| `ALPACA_API_KEY`     | ✅   | ✅   | ✅   |
| `ALPACA_SECRET_KEY`  | ✅   | ✅   | ✅   |
| `TELEGRAM_BOT_TOKEN` | ✅   | ✅   | ✅   |
| `MINIMAX_API_KEY`    | ✅   | ✅   | ✅   |
| `NAS_REGISTRY_USER`  | ✅   | ✅   | ✅   |
| `NAS_REGISTRY_PASS`  | ✅   | ✅   | ✅   |

### 4.3 Future Upgrade Path
If Docker Swarm becomes available:
- Migrate to Docker Secrets for container-native secret propagation
- Gitea Actions → Docker Swarm secrets (encrypted at rest)
- No code changes needed, just compose file updates

---

## 5. Gitea Actions Setup Steps

### 5.1 Enable Gitea Actions (Admin)
```
Site Admin → Actions → Enable Local Runner → Save
```

### 5.2 Add Runner Registration Token (Gitea Actions Secrets)
In Gitea Actions settings for the repo:
- Settings → Secrets → Add secret: `GITEA_RUNNER_TOKEN` = (runner registration token)

### 5.3 Add NAS Registry Credentials (Gitea Actions Secrets)
- Settings → Secrets → Add:
  - `NAS_REGISTRY_USER` = admin (or dedicated user)
  - `NAS_REGISTRY_PASS` = password for nas:5000

### 5.4 Create Workflow Files
Add to repo at `.gitea/workflows/`:

```
.gitea/workflows/dev.yml     — deploys on push to dev branch
.gitea/workflows/uat.yml     — deploys on push to uat branch
.gitea/workflows/prod.yml    — deploys on push to main branch (may require manual approval)
```

### 5.5 Start Act Runner on NAS
The Gitea Actions runner runs as a Docker container on the NAS (via the Gitea compose):
```bash
docker run -d \
  --name gitea-runner \
  -v /var/run/docker.sock:/var/run/docker.sock \
  gitea/act_runner:latest
```

---

## 6. Directory Structure on NAS

```
/volume1/Docker/
├── vault/                    ← OLD — plain text, DELETE after migration
├── PortainerCE/              ← Portainer data (compose stacks, backups)
├── trading-agent-source/      ← Gitea mirror / deploy source
│
├── ta-dev/                   ← DEV environment
│   ├── vault/                ← dev credentials (future: encrypted)
│   ├── data/
│   ├── dashboard/static/
│   ├── knowledge/
│   ├── models/
│   └── config/
│
├── ta-uat/                   ← UAT environment
│   ├── vault/
│   ├── data/
│   ├── dashboard/static/
│   ├── knowledge/
│   └── config/
│
└── ta-prod/                  ← PROD environment
    ├── vault/
    ├── data/
    ├── dashboard/static/
    ├── knowledge/
    ├── models/
    └── config/
```

---

## 7. Docker Swarm Decision

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Docker Swarm (full) | Native secrets, rolling updates, orchestration | Asustor may not support, complex setup | **Deferred** — investigate |
| Portainer Stacks (current) | Works today, simple | No native secrets, manual env var updates | **Use for now** |
| Docker Secrets standalone | Native secrets without full Swarm | Requires at least single-node Swarm | **Investigate** |

**Action item:** Test `docker swarm init` on NAS (requires SSH or Gitea exec). If it works, enable full Swarm mode.

---

## 8. Immediate Actions

### Priority 1 — Remove Plain-Text Credentials (TODAY)
- [ ] Delete `\\10.8.0.10\Docker\vault\*.env` files (already backed up in stack.env)
- [ ] Delete or encrypt `stack.env` in Portainer data directory
- [ ] Add secrets to Gitea Actions UI

### Priority 2 — Fix Current Container (TONIGHT)
- [ ] Rebuild container with `dev` branch to get fincept_connector.py fix
- [ ] Either: add `GIT_REF=dev` env var in Portainer, OR merge dev→main

### Priority 3 — Set Up Gitea Actions
- [ ] Enable Gitea Actions (Site Admin)
- [ ] Add runner token to Gitea Actions secrets
- [ ] Write 3 workflow files (dev/uat/prod)
- [ ] Start Act Runner container on NAS

### Priority 4 — Create Environment Stacks
- [ ] Create `ta-dev/` directory structure on NAS
- [ ] Create `ta-uat/` directory structure on NAS
- [ ] Create Portainer stacks for dev and uat (prod = current stack 10)
- [ ] Add per-environment secrets to Gitea Actions

---

## 9. Open Questions

1. **Docker Swarm** — Can we run `docker swarm init` on the NAS? Need SSH access or Gitea exec to test.
2. **New Telegram bot** — Current bot token is in plain text AND was previously compromised. Needs rotation for prod.
3. **UAT approval gate** — Should UAT→PROD require manual approval in Gitea Actions, or auto-deploy?
4. **Act Runner placement** — Run as Docker container on NAS (needs `/var/run/docker.sock`), or as host process?
5. **Database (pgAdmin)** — Kay mentioned the DB also needs dev/uat/prod. Which DB? Postgres? Where is it running?

---

*End of Architecture Document*
