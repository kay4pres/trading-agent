# Gitea Actions + Act Runner Setup Guide
# Complete walkthrough to get Gitea Actions CI/CD running for trading/trading-agent
# Last updated: 2026-07-02

## Architecture Overview

```
Git push to Gitea (10.8.0.10:3000)
        │
        ▼
Gitea Actions webhook fires
        │
        ▼
Act Runner (on NAS) picks up job
        │
        ├── lint job      → Python container → flake8, syntax check
        │
        └── build job     → Docker build → push to nas:5000/trading-agent
                                    │
                                    ▼
                            Portainer pulls new image
                            Container auto-recreates
                            ✅ New code live
```

## Prerequisites

- [x] Gitea running at http://10.8.0.10:3000
- [x] trading/trading-agent repo created (mirrored from GitHub)
- [x] Gitea token stored in Windows Credential Manager (`gitea:http://10.8.0.10:3000`)
- [ ] NAS Docker registry at `nas:5000` running
- [ ] Act Runner registered and online

## Step 1 — Enable Gitea Actions (if not already enabled)

1. Open http://10.8.0.10:3000 → Log in as admin
2. Site Admin → Configuration → Actions → Enable Local Runner (toggle ON)
3. Set Default runner permissions: Allow all

## Step 2 — Get Runner Registration Token

Option A — via Gitea UI (Site Admin):
1. Site Admin → Actions → Runners → "New Runner"
2. Name: `nas-act-runner` → Create
3. Copy the **Registration Token** shown (starts with `glrt_`)

Option B — via API:
```powershell
# Requires Gitea token in Credential Manager
. .\scripts\gitea-test.ps1   # verify token first
$token = [CredReader]::GetPassword("gitea:http://10.8.0.10:3000")
$headers = @{ Authorization = "token $token"; Accept = "application/json" }
$resp = Invoke-RestMethod "http://10.8.0.10:3000/api/v1/repos/trading/trading-agent/actions/runners/registration-token" `
    -Headers $headers -Method POST
$resp.token   # this is the registration token
```

Save the token — you need it in Step 4.

## Step 3 — Create runner-data directory on NAS

SSH into NAS:
```bash
ssh admin@10.8.0.10
# Create directory for runner state
mkdir -p /volume1/docker/act-runner/runner-data
chmod 755 /volume1/docker/act-runner/runner-data
```

## Step 4 — Deploy Act Runner via Portainer

1. Portainer → Stacks → Add stack
2. Name: `act-runner`
3. Web editor — paste contents of `docs/act-runner-compose.yml`
4. Add environment variables:
   ```
   GITEA_URL=http://10.8.0.10:3000
   GITEA_RUNNER_TOKEN=<token from Step 2>
   GITEA_INSTANCE_CAPACITY=2
   ```
5. Create → wait 10s → check logs:
   ```bash
   docker logs act-runner
   ```
   Expected: `Starting runner daemon`

## Step 5 — Verify Runner Appears in Gitea

1. Open http://10.8.0.10:3000/trading/trading-agent → Settings → Actions → Runners
2. You should see `nas-act-runner` with status **Active** ✅
3. Labels should include: `self-hosted`, `linux`, `docker`

## Step 6 — Add Gitea Actions Secrets

Add secrets to the repo for the CI workflow to push to NAS registry:

### NAS_REGISTRY_USER + NAS_REGISTRY_PASS
```powershell
# Run this on Kay's machine
. .\scripts\gitea-add-secret.ps1
# When prompted, paste NAS registry credentials (Docker login for nas:5000)
# Use secret name: NAS_REGISTRY_USER
# Then run again for: NAS_REGISTRY_PASS
```

### GITEA_RUNNER_TOKEN (for workflow runners)
```powershell
# Add the same runner token as a repo secret
# This allows workflows to register as runners
```

## Step 7 — Commit Workflow Files

The workflow files are already in `.gitea/workflows/`:

- `mirror-to-github.yml` — mirrors main → GitHub (existing)
- `ci-build-push.yml` — lint + Docker build + push to nas:5000 (new)

Push to trigger the first run:
```powershell
cd E:\Me\TradingAgent
git add .gitea/workflows/ci-build-push.yml
git commit -m "ci: add Gitea Actions workflow — lint + Docker build + push to NAS"
git push gitea dev
```

## Step 8 — Watch the First Run

1. Gitea → trading/trading-agent → Actions tab
2. You should see a new run triggered by the push
3. Click into it → watch lint and build jobs execute on `nas-act-runner`
4. Green = success, Red = check logs

## Troubleshooting

### Runner not showing up
```bash
# Check runner logs
docker logs act-runner

# Common error: "instance URL mismatch"
# → Verify GITEA_URL=http://10.8.0.10:3000 (no trailing slash)

# Common error: "invalid token"
# → Re-generate registration token in Gitea UI and update Portainer env var
```

### Docker build fails in workflow
```bash
# The runner needs Docker socket access
# Verify in Portainer:
#   Volume: /var/run/docker.sock → /var/run/docker.sock
# Without this, Docker build step will fail with:
#   "error connecting to Docker daemon"
```

### Registry push fails
```bash
# Verify nas:5000 is accessible from the act-runner container:
docker exec act-runner docker login nas:5000 -u <user> -p <pass>
# If this fails, the NAS registry may not be running or network is wrong
```

### Workflow shows "No runner with label self-hosted,linux"
```bash
# The workflow uses labels to find the right runner.
# Ensure Act Runner was created with labels: self-hosted,linux,docker
# Check in Gitea → Settings → Actions → Runners → nas-act-runner
```

## Expected Timeline

| Step | Action | Time |
|------|--------|------|
| 2 | Get registration token | 2 min |
| 3 | Create directory on NAS | 1 min |
| 4 | Deploy Act Runner via Portainer | 3 min |
| 5 | Verify runner online | 1 min |
| 6 | Add secrets | 3 min |
| 7 | Push workflow files | 1 min |
| 8 | Watch first run | 2-5 min |

**Total: ~15 minutes** to have full CI/CD running.
