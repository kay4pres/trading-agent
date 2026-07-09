# Build Pipeline — trading-agent
**Date:** 2026-07-09
**Source of Truth:** Gitea `http://10.8.0.10:3000/trading/trading-agent`

---

## Overview

```
Gitea push (dev / uat / main)
    │
    ▼
Gitea Actions Runner (nas-act-runner)
    │  clones from Gitea: http://kay:<token>@10.8.0.10:3000/trading/trading-agent.git
    │
    ├── lint job  ──► syntax check + flake8
    │
    └── build job ──► docker buildx build
                          --file /build/docker/Dockerfile
                          --platform linux/amd64
                          --tag nas:5000/trading-agent:<branch>
                          --push
                          nas:5000 registry (on NAS)
```

---

## Source of Truth

| | |
|---|---|
| **Repo** | `http://10.8.0.10:3000/trading/trading-agent` |
| **Workflow file** | `.gitea/workflows/ci-host-mode.yml` |
| **Dockerfile** | `docker/Dockerfile` |
| **Registry** | `nas:5000` |
| **Runner** | `nas-act-runner` (self-hosted, online) |

The GitHub repo (`github.com/kay4pres/trading-agent`) is **NOT** part of the
pipeline. Any code there is ignored by the Gitea Actions runner.

---

## Branch → Image Tag Mapping

| Git Branch | Image Tag | Pushed By |
|------------|-----------|-----------|
| `dev` | `nas:5000/trading-agent:dev` | `build-dev` job |
| `uat` | `nas:5000/trading-agent:uat` | `build-uat` job *(pending — see §Action Required)* |
| `main` | `nas:5000/trading-agent:main` + `:latest` | `build-main` job |

---

## Workflow Triggers

| Event | Jobs Run |
|-------|----------|
| Push to `dev` | lint + build-dev |
| Push to `uat` | lint + build-uat |
| Push to `main` | lint + build-main |
| PR to `main` | lint only |
| `workflow_dispatch` (manual) | lint + all build jobs (if conditions pass) |

---

## Dockerfiles

Two Dockerfiles exist in the repo:

| Path | Used By | Notes |
|------|---------|-------|
| `docker/Dockerfile` | **Gitea Actions** (primary) | Fixed: uses `COPY . /app` from build context |
| `Dockerfile` (repo root) | Portainer manual builds (legacy) | Still has GitHub `ADD` — avoid using |

> **Warning:** The root `Dockerfile` is the old one with the GitHub `ADD` trap.
> Do not use it for Portainer manual builds. Use `docker/Dockerfile`.

---

## How to Trigger a Rebuild

### Automatic (recommended)
Push any commit to `dev`, `uat`, or `main`. Gitea Actions handles everything.

```bash
# From your local clone (gitea remote)
git add .
git commit -m "fix: ..."
git push gitea <branch>
```

### Manual via Gitea UI
1. Open `http://10.8.0.10:3000/trading/trading-agent`
2. → **Actions** tab
3. → **CI — Lint, Build & Push** workflow
4. → **Run workflow** button
5. Select branch, click **Ok**

### Manual via Portainer (legacy — bypasses Gitea)
1. Portainer → **Images** → **Build a new image**
2. Name: `nas:5000/trading-agent:latest`
3. Dockerfile: paste from `docker/Dockerfile` (NOT root `Dockerfile`)
4. Build args: none required
5. **Build**
> ⚠️ This bypasses the Gitea workflow — use only for emergencies.

---

## After a Successful Build

The runner pushes to `nas:5000`. To deploy:

```bash
# On the NAS host (or via Portainer console)
docker pull nas:5000/trading-agent:<tag>

# Or in Portainer UI:
# Containers → trading-agent → Recreate → Pull image → Deploy
```

---

## Docker Registry

| | |
|---|---|
| **Registry URL** | `nas:5000` |
| **Auth** | `NAS_REGISTRY_USER` / `NAS_REGISTRY_PASS` (stored as Gitea Secrets) |
| **Images stored at** | `/var/lib/docker/volumes/registry/_data` on NAS |

List images on the NAS:
```bash
docker --registry nas:5000 images
# or
curl -s http://nas:5000/v2/_catalog
```

---

## Secrets Required (Gitea Repository Secrets)

| Secret | Used For |
|--------|---------|
| `GITEA_TOKEN` | Cloning the Gitea repo in the runner |
| `NAS_REGISTRY_USER` | `docker login nas:5000` |
| `NAS_REGISTRY_PASS` | `docker login nas:5000` |

---

## Known Issues

### ❌ Fixed: GitHub ADD Trap (sha256:183d993... on :latest)
The `docker/Dockerfile` previously contained:
```dockerfile
ADD https://github.com/kay4pres/trading-agent/archive/refs/heads/${GIT_REF}.zip /app/repo.zip
```
This overrode the Gitea clone entirely — every "Gitea-built" image contained
GitHub code. **Fixed 2026-07-09** by replacing with `COPY . /app`, which
correctly consumes the workflow's Gitea clone.

### ⚠️ Root Dockerfile still has GitHub ADD
The repo-root `Dockerfile` still has the old GitHub ADD line. Do not use it.
This is a legacy file kept for reference.

---

## Action Required

- [ ] **Add `build-uat` job** to `ci-host-mode.yml` — the workflow only handles
  `dev` and `main` branches today. `uat` branch push will run lint but not build
  or push an image.
