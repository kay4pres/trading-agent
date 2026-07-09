# PROD Environment Architecture — Proposal
**Date:** 2026-07-09
**Status:** Draft — requires approval before implementation

---

## Context

Today there is a single deployment: `nas:5000/trading-agent:latest` on port **5050**.
DEV / UAT / PROD are not separated — all share the same image tag and port.

The trading agent already supports an environment variable `TRADING_AGENT_ENV`
(defaults to `UAT` per `docker-compose.yml` line 58). This makes a single-image,
multi-environment approach straightforward.

---

## Option A — Single Image, ENV VAR (Recommended ✅)

### Concept
One image with three tags, all built from the same Dockerfile:
- `nas:5000/trading-agent:dev`   → `TRADING_AGENT_ENV=DEV`,   port **5050**
- `nas:5000/trading-agent:uat`   → `TRADING_AGENT_ENV=UAT`,   port **5051**
- `nas:5000/trading-agent:prod`  → `TRADING_AGENT_ENV=PROD`,  port **5052**

The `TRADING_AGENT_ENV` variable is set at **container startup** (Portainer
"Advanced" → Environment variables), NOT baked into the image. This means:

- One build pipeline, three deployments
- Rebuilding the image automatically propagates to all three environments
- No branching strategy needed for environment-specific code

### Why this is cleaner
| | Option A (single image + env) | Option B (one tag per build) |
|---|---|---|
| Image builds | 1 per push | 3 per push |
| Rebuild trigger | push to branch | push to branch + manual tags |
|rollback | re-pull old image tag | re-tag old build |
| Complexity | low | medium |
| Portainer UI | 3 containers, easy to read | 3 containers + image list |

### Proposed Git Branch / Tag Strategy

| Branch | Image Tag | TRADING_AGENT_ENV | Use |
|--------|-----------|-------------------|-----|
| `dev`  | `trading-agent:dev` | `DEV` | local dev / feature testing |
| `uat`  | `trading-agent:uat` | `UAT` | pre-production validation |
| `main` | `trading-agent:prod` | `PROD` | live trading |

### Container Ports

| Container | Image Tag | Port | Notes |
|-----------|-----------|------|-------|
| `trading-agent-dev` | `nas:5000/trading-agent:dev` | **5050** | |
| `trading-agent-uat` | `nas:5000/trading-agent:uat` | **5051** | |
| `trading-agent-prod` | `nas:5000/trading-agent:prod` | **5052** | |

### What needs to change

#### 1. Update the Gitea workflow (`ci-host-mode.yml`)
Add a `build-uat` job that triggers on `uat` branch and tags the image as `uat`.
Currently only `build-dev` (on `dev`) and `build-main` (on `main`) exist.

```yaml
  build-uat:
    name: Build & Push (uat)
    runs-on: [self-hosted, linux, docker]
    if: gitea.ref == 'refs/heads/uat'
    steps:
      - name: Clone and checkout
        run: |
          rm -rf /build
          git clone --depth=1 --branch=uat http://kay:${GITEA_TOKEN}@10.8.0.10:3000/trading/trading-agent.git /build
          cd /build && git fetch origin uat && git checkout ${{ gitea.sha }}

      - name: Build and push
        env:
          NAS_REGISTRY_PASS: ${{ secrets.NAS_REGISTRY_PASS }}
          NAS_REGISTRY_USER: ${{ secrets.NAS_REGISTRY_USER }}
        run: |
          docker login nas:5000 -u "$NAS_REGISTRY_USER" -p "$NAS_REGISTRY_PASS"
          cd /build
          docker buildx create --use --name multiarch 2>/dev/null || \
          docker buildx use multiarch 2>/dev/null || true
          docker buildx build \
            --platform linux/amd64 \
            --tag nas:5000/trading-agent:uat \
            --push \
            --file /build/docker/Dockerfile \
            /build
```

#### 2. Update `build-main` job
Change `--tag nas:5000/trading-agent:latest` to `--tag nas:5000/trading-agent:prod`.
The `latest` tag can remain but should point to prod for clarity.

#### 3. Create Portainer containers

| Action | Image | Port | Env var `TRADING_AGENT_ENV` |
|--------|-------|------|------------------------------|
| Create `trading-agent-uat` | `nas:5000/trading-agent:uat` | 5051 | `UAT` |
| Create `trading-agent-prod` | `nas:5000/trading-agent:prod` | 5052 | `PROD` |
| Update `trading-agent` | rename to `trading-agent-dev` | 5050 | `DEV` |

**Before creating prod**: verify database credentials, Alpaca keys, and Telegram
webhook are pointing to production endpoints.

#### 4. Database / Credential Separation
`TRADING_AGENT_ENV=UAT` and `TRADING_AGENT_ENV=PROD` should select different:
- `TRADING_AGENT_DB_NAME` (`mindgentic_uat` vs `mindgentic_prod`)
- `TRADING_AGENT_DB_USER` (`ai_agent_uat` vs `ai_agent_prod`)
- Alpaca keys — prod should use a separate or paper/live flag

### Rollback Procedure
```bash
# 1. Stop current prod container in Portainer
# 2. Pull the previous image
docker pull nas:5000/trading-agent:prod@sha256:<previous-sha>
# 3. Start container with that SHA (or retag the :prod alias)
# 4. Restart container in Portainer UI
```

---

## Option B — Separate Builds Per Environment (Not Recommended)
Each environment has its own image tag baked at build time from separate branches.
Rejects: more CI complexity, more to manage, no atomic rollback across envs.

---

## Decision Required

1. **Approve Option A?** (single image + env var approach)
2. **Which port for prod?** Current port 5050 is the live running container.
   - Proposal: keep 5050 for `dev`, move UAT to 5051, prod to 5052.
3. **Database**: does PROD have its own DB credentials in Portainer Secrets,
   or should `TRADING_AGENT_ENV=PROD` load them from vault?

---

## Risks
- **Prod traffic**: port change from 5050 → 5052 requires updating any external
  consumers (TradingView webhooks, Telegram bot polling URL).
- **DB migration**: if UAT and PROD share the same DB, `TRADING_AGENT_ENV`
  toggles schema — confirm with Kay whether a PROD DB is already provisioned.
