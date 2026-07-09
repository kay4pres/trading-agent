# Docker-Compose DB Wiring Plan

## Context

The trading-agent Docker container currently has **no database connectivity** configured.
The PostgreSQL instance (NAS @ 10.8.0.10:5432) is the source of truth for ai_memory data.
Three environment databases exist: `mindgentic_dev`, `mindgentic_uat`, `mindgentic_prod`.

---

## Decision: Docker Postgres vs. NAS PostgreSQL

**Connect the trading-agent container to the NAS PostgreSQL @ 10.8.0.10:5432** — not to a Docker-internal Postgres container.

Rationale:
- The NAS PostgreSQL already holds `mindgentic_dev/uat/prod` with the `ai_memory` schema and all existing tables.
- Running a separate Postgres inside Docker would duplicate storage and diverge from the single source of truth.
- The container already reaches 10.8.0.10 via WireGuard (the compose mounts `/volume1/Docker/vault` and has network access to the NAS).

---

## Required Environment Variables

Add a new `environment:` block section to the `trading-agent` service in docker-compose.yml:

```yaml
# ── Database (NAS PostgreSQL) ─────────────────────────────────────────────────
- TRADING_AGENT_DB_HOST=10.8.0.10
- TRADING_AGENT_DB_PORT=5432
- TRADING_AGENT_DB_NAME=${TRADING_AGENT_DB_NAME}       # mindgentic_dev | mindgentic_uat | mindgentic_prod
- TRADING_AGENT_DB_USER=${TRADING_AGENT_DB_USER}       # ai_agent_dev | ai_agent_uat | ai_agent_prod
- TRADING_AGENT_DB_PASSWORD=${TRADING_AGENT_DB_PASSWORD} # per-environment password
```

### Per-environment DB credentials

| Env | Database | Role |
|-----|----------|------|
| dev | mindgentic_dev | ai_agent_dev |
| uat | mindgentic_uat | ai_agent_uat |
| prod | mindgentic_prod | ai_agent_prod |

---

## Docker Secrets Strategy

> ⚠️ Docker Secrets approach is **stalled** due to ASUSTOR Swarm permissions issues.
> Plan assumes Docker Secrets will eventually be available; **fallback is env vars**.

### Preferred (when Swarm permissions are resolved)

Docker Secrets are defined in Portainer **before** the stack is deployed:

| Secret Name | Maps To |
|-------------|---------|
| `trading_agent_db_name_dev` | `TRADING_AGENT_DB_NAME` (dev only) |
| `trading_agent_db_user_dev` | `TRADING_AGENT_DB_USER` (dev only) |
| `trading_agent_db_password_dev` | `TRADING_AGENT_DB_PASSWORD` |
| (repeat for uat / prod) | |

In docker-compose.yml, reference secrets via `docker_secrets:` block:

```yaml
secrets:
  trading_agent_db_name_dev:
    external: true
  trading_agent_db_user_dev:
    external: true
  trading_agent_db_password_dev:
    external: true

services:
  trading-agent:
    secrets:
      - trading_agent_db_name_dev
      - trading_agent_db_user_dev
      - trading_agent_db_password_dev
    environment:
      - TRADING_AGENT_DB_NAME=/run/secrets/trading_agent_db_name_dev
      - TRADING_AGENT_DB_USER=/run/secrets/trading_agent_db_user_dev
      - TRADING_AGENT_DB_PASSWORD=/run/secrets/trading_agent_db_password_dev
```

### Fallback (current — env vars in .env file)

Credentials live in `vault/.env` (gitignored, never committed):

```env
# .env (vault/.env — NOT committed)
TRADING_AGENT_DB_NAME=mindgentic_dev
TRADING_AGENT_DB_USER=ai_agent_dev
TRADING_AGENT_DB_PASSWORD=<dev-password>
```

The compose `environment:` section reads from `${VAR}` — Docker compose自动 substitutes from the `.env` file at `docker compose up` time.

---

## Changes to docker-compose.yml

### 1. Add environment section (fallback / current)

```yaml
    environment:
      - TZ=Europe/Berlin

      # ── Database (NAS PostgreSQL) ────────────────────────────────────────────
      - TRADING_AGENT_DB_HOST=10.8.0.10
      - TRADING_AGENT_DB_PORT=5432
      - TRADING_AGENT_DB_NAME=${TRADING_AGENT_DB_NAME}
      - TRADING_AGENT_DB_USER=${TRADING_AGENT_DB_USER}
      - TRADING_AGENT_DB_PASSWORD=${TRADING_AGENT_DB_PASSWORD}

      # ── Alpaca ──────────────────────────────────────────────────────────────
      # ... existing ...
```

### 2. Add secrets block (for future Portainer enablement)

```yaml
    # Comment: Docker Secrets require ASUSTOR Swarm permission fix first.
    # Uncomment when secrets are available in Portainer.
    #secrets:
    #  - trading_agent_db_name
    #  - trading_agent_db_user
    #  - trading_agent_db_password
```

### 3. Add health check probe for DB connectivity

```yaml
    healthcheck:
      test: ["CMD", "python", "-c",
             "import urllib.request; urllib.request.urlopen('http://localhost:5050/api/state')"]
      # Also verify DB connectivity (app-level):
      # test: ["CMD-SHELL", "python -c \"import trading_agent.db; trading_agent.db.health_check()\""]
```

---

## Changes to .env (vault/.env)

```env
# ── Database ──────────────────────────────────────────────────────────────────
TRADING_AGENT_DB_NAME=mindgentic_dev
TRADING_AGENT_DB_USER=ai_agent_dev
TRADING_AGENT_DB_PASSWORD=<dev-password-from-DPAPI-vault>
```

For uat/prod, either:
- Use separate `.env.uat` / `.env.prod` files loaded via `docker --env-file`
- Or manage via Portainer environment variable overrides per stack

---

## Implementation Order

1. **Add env vars to docker-compose.yml** (`TRADING_AGENT_DB_*`) — no secrets, plain env var fallback
2. **Create/update `vault/.env`** with dev credentials from DPAPI vault
3. **Verify container reaches NAS PostgreSQL** via WireGuard network
4. **Add DB connection module** to trading-agent app (`src/db.py` or similar)
5. **Enable Docker Secrets** in Portainer once ASUSTOR Swarm permissions are resolved
6. **Migrate uat/prod** env vars to secrets once confirmed working in dev

---

## Files to Modify

| File | Action |
|------|--------|
| `/volume1/Docker/docker-compose.yml` | Add `TRADING_AGENT_DB_*` environment vars; add commented secrets block |
| `vault/.env` | Add `TRADING_AGENT_DB_NAME`, `TRADING_AGENT_DB_USER`, `TRADING_AGENT_DB_PASSWORD` |
| `trading-agent/src/db.py` (app side) | Add DB connector that reads `TRADING_AGENT_DB_*` env vars |

---

## Out of Scope

- Running Postgres inside Docker — the NAS instance is the canonical DB
- Changing database schema — `ai_memory` schema is already defined
- Modifying roles/permissions — `ai_agent_dev/uat/prod` roles already exist
