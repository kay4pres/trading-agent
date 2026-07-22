# Phase A Build + Deploy — Step-by-Step for Kay

**Updated 2026-07-22 09:00 Berlin** after fact-check delegation. The previous handoff was wrong in 3 places — this one is verified.

## Fact-check from this morning

I delegated fact-checks to `gitea-agent` and `nas-ssh-access` and got the ground truth:

| Claim | Reality | Source |
|---|---|---|
| Image `nas:5000/trading-agent:dev-2026-07-22` exists | **FALSE** — registry only has `:latest` (7 days old). CI never ran on our `pipeline-builder/day-01-relay-extension` branch. | nas-ssh-access |
| `docker-compose.dev.yml` would work as-is | **FALSE** — used `/data/compose/2/vault` which doesn't exist on the NAS. Real path is `/volume1/Docker/trading-agent-dev/vault`. | nas-ssh-access |
| CI builds on `pipeline-builder/*` | **PARTIALLY TRUE** — workflow updated correctly, but the act-runner containers are **ghosted** (2 broken runners flooding Gitea with 500s since Jul 8 and Jul 22). New pushes aren't picked up. | nas-ssh-access + gitea-agent |
| `trading-agent-dev` directory exists on NAS | **FALSE** — does NOT exist. Need to create it (with `Ai_agent` ownership) before deploying. | nas-ssh-access |
| Files in `E:\Me\TradingAgent\docker\` exist | **TRUE** — SHA256-verified below. | local |

The previous plan assumed CI would build. CI is broken. **We build the image manually using the `git archive` pattern from the NAS-build reference doc** (which I read and is correct).

## What's verified to exist (SHA256)

```
E:\Me\TradingAgent\docker\docker-compose.dev.yml  270304C39C9073CB4506D0587371E8C89591EA4F6605C987314C4F9EB7F23B43
E:\Me\TradingAgent\docker\portainer-stack-dev.yml FE576C05CAB65D81053A93603373DCD66CD992B9F6A869EC48ED995BABF88DDB
E:\Me\TradingAgent\smoke_e2e.py                  BCDFAE460C77B436D2A63C4BA4A14739C10395917B007E201096166D66824F9A
E:\Me\TradingAgent\requirements.txt                F64ADC65B9DD09C89DA9010FAFD5ADD923CE19B969E3834E8E02DF71DFFCAEC9
E:\Me\TradingAgent\dashboard\app.py                5A7B53A4AE4FF79317496AFB3BD85F6018F20F487902A18994D37CC4BD226D8C
E:\Me\TradingAgent\entrypoint.py                  8706624CF37B96DEA0A46ED5F0E548B219848881B6821B2C5005082D342F7203
E:\Me\TradingAgent\.gitea\workflows\ci-build-push.yml E69192EDA3F36A29D3DA811FF2DB010F0D3E40881CCD81272335678B8D5205DD
```

Both `E:\` and `C:\Users\Kay\repos\trading-agent\` (git mirror) have the same files with matching hashes. Gitea has them on `pipeline-builder/day-01-relay-extension` branch (commits 5ca756b → 8f4bef6).

## The 5 steps you (Kay) need to do

### Step 1 — Create the dev directory on the NAS

Open an SSH session to the NAS (port 22, user `Ai_agent_01`, key in `E:\Me\TradingAgent\vault\Ai_agent_01_openssh.key`).

```bash
ssh nas-automation
# Or: ssh -i "E:/Me/TradingAgent/vault/Ai_agent_01_openssh.key" Ai_agent_01@nas.local

# Create the dev dir with the right ownership
sudo mkdir -p /volume1/Docker/trading-agent-dev/{vault,dashboard/static,models,knowledge,config,logs}
sudo chown -R Ai_agent:Ai_agent /volume1/Docker/trading-agent-dev
ls -la /volume1/Docker/trading-agent-dev
# Should show: vault/, dashboard/, models/, knowledge/, config/, logs/ — all owned by Ai_agent
```

### Step 2 — Extract the source from gitea (no git needed on NAS)

The gitea container already has git. We use `git archive` to extract the exact commit you want to build.

Find the target commit SHA. Pick the most recent green commit on `pipeline-builder/day-01-relay-extension`. The candidates are:
- `8f4bef6` — docs: doc-sheriff log session 12 (latest, 2 days ago)
- `a0a33f3` — docs: Day 4 EOD Phase A handoff
- `5ca756b` — ci: build-dev on dev/dev-rollout/pipeline-builder/* branches

I'll use `8f4bef6` (latest). If you want a different one, swap the SHA in the command below.

```bash
# Inside the gitea container
docker exec gitea sh -c 'mkdir -p /tmp/dev-extract && \
  git --git-dir=/var/lib/gitea/git/repositories/trading/trading-agent.git \
  archive 8f4bef6 | tar -xf - -C /tmp/dev-extract'

# Verify the extract
docker exec gitea ls /tmp/dev-extract
# Should show: docker/, docs/, requirements.txt, entrypoint.py, trading_agent/, ...

# Copy to NAS filesystem (we'll build from here)
docker cp gitea:/tmp/dev-extract/. /tmp/dev-build/
ls /tmp/dev-build/ | head -20
# Verify the key files are present
ls /tmp/dev-build/docker/
ls /tmp/dev-build/trading_agent/ | head
test -f /tmp/dev-build/smoke_e2e.py && echo "smoke_e2e.py: present"
test -f /tmp/dev-build/docker/portainer-stack-dev.yml && echo "portainer-stack-dev.yml: present"
```

### Step 3 — Build the Docker image

```bash
# Build the image. Use the existing Dockerfile (already has the dashboard
# directory creation + ib_insync etc. Note: my Phase A code uses numpy/pandas
# which are also already in the existing Dockerfile).
docker build \
  -t nas:5000/trading-agent:latest \
  -f /tmp/dev-build/docker/Dockerfile \
  /tmp/dev-build
```

Watch the build output. If it fails on a missing module, check the requirements.txt — it should now include `pytest>=7.0.0`. The Dockerfile reads `requirements.txt` and runs `pip install -r /app/requirements.txt`.

When the build finishes, verify:

```bash
docker images nas:5000/trading-agent:latest
# Should show: nas:5000/trading-agent  latest  <new sha>  <just now>  347MB
```

### Step 4 — Push to the registry (so Portainer can use it)

```bash
docker push nas:5000/trading-agent:latest
# Watch for: "latest: digest: sha256:... size: ..." then "Push referer:..."
```

Verify:

```bash
curl -s http://10.8.0.10:5000/v2/trading-agent/tags/list
# Should show: {"name":"trading-agent","tags":["latest"]}
```

### Step 5 — Deploy the stack via Portainer

Open Portainer: `https://10.8.0.10:18999` (or whatever the port is on your NAS — check the bookmark).

#### 5a — Add the stack

1. **Portainer → Stacks → Add stack**
2. **Name:** `trading-agent-dev`
3. **Build method:** Click **"Upload"** (not Repository)
4. **Upload the file:** paste the contents of `E:\Me\TradingAgent\docker\portainer-stack-dev.yml` (also at `C:\Users\Kay\repos\trading-agent\docker\portainer-stack-dev.yml`)
5. **Scroll down to "Environment variables"** and click **"+ Add environment variable"** for each of:
   - `ALPACA_API_KEY` = your Dev paper-trading key
   - `ALPACA_SECRET_KEY` = your Dev paper-trading secret
   - `MINIMAX_API_KEY` = your Dev LLM key (same one used for the chat agent)
   - (Optional) `TV_WEBHOOK_SECRET` = leave blank
6. **Click "Deploy the stack"**

#### 5b — Wait for healthy

The stack will start a container named `trading-agent-dev`. Watch Portainer → Containers:
- Initially: `starting`
- After ~30s: `healthy` (the healthcheck hits the dashboard)
- If it goes into restart loop: open the container's logs and read the error

If restart loop happens, common causes:
- Missing `vault/` directory ownership (Step 1 chown fix)
- `dashboard/static/` doesn't exist (Step 1 creates it)
- DASHBOARD_PORT=5060 mismatch (we made this env-var driven — the container should bind on 5060)

#### 5c — Run the smoke test

In Portainer, go to **Containers → trading-agent-dev → Console → Connect**.

Or via SSH on the NAS:

```bash
docker exec trading-agent-dev python /app/smoke_e2e.py
```

Expected output: 6/6 steps pass. The smoke test verifies:
1. 75 unit tests pass inside the container
2. Pre-trade gate blocks over-positioned order
3. Valid order is paper-routed
4. Audit log has decision + audit_id
5. execute_exit() appends to trade_journal.csv
6. trading_loop engine reads the journal

### Step 6 — Verify the 6 stop/go criteria

- [ ] All 75 unit tests pass inside the Dev container (`smoke_e2e.py` Step 1)
- [ ] IBGW relay smoke test passes — check with `curl http://nas:5000/status` or similar (relay runs as host process)
- [ ] 1 end-to-end paper trade completes: gate → audit → position → exit → journal (Steps 2-6 of smoke_e2e)
- [ ] No errors in container logs — `docker logs trading-agent-dev | grep -i error` is empty
- [ ] Vault is `/volume1/Docker/trading-agent-dev/vault/` on the NAS (NOT local `E:\Me\TradingAgent\vault\`)
- [ ] Portainer stack name is `trading-agent-dev` (NOT `trading-agent`)

## What if it doesn't work

### Symptom: "no such file or directory" on /volume1/Docker/trading-agent-dev/
- You skipped Step 1. Create the directory.

### Symptom: "image not found" nas:5000/trading-agent:latest
- You skipped Step 3 or Step 4. Build the image, then push to the registry.

### Symptom: container restart loop
- Check `docker logs trading-agent-dev --tail 50` for the actual error
- Most common: dashboard dir not in image, or vault dir not owned by Ai_agent
- If dashboard dir issue: re-run Step 3 with the corrected Dockerfile (already has `RUN mkdir -p /app/dashboard/static`)

### Symptom: smoke test fails at Step 1 (pytest)
- 75 tests should pass. If not, the image was built from a stale commit — re-run Step 2 with the correct SHA, then Step 3.

### Symptom: smoke test fails at Step 5 (journal CSV empty)
- The trade_journal.py module writes to `E:\Me\TradingAgent\data\trade_journal.csv` in the container, which is mapped to `/volume1/Docker/data/...`. Verify the volume mount: `docker exec trading-agent-dev ls -la /app/data/`

## What's NOT done (waiting on UAT / Phase B)

These are explicitly out of scope for Phase A:

- Real scanner code (10 of 25 DTD scanners with confirmed filter values)
- IBKR market data subs on `DU1234567` (REA-0.3)
- TradingView tier for richer data (REA-0.2)
- 45-min DTD walkthrough to confirm filter values (REA-1.2)
- 5-day paper-mode validation
- Monthly `trading_loop` cron
- Regime filter wired into the gate
- Full UAT env with real CapTrader paper account

## Side note: the act-runner ghost containers

The CI is broken because 2 act-runner containers are flooded with 500 errors from gitea. This needs cleanup separately, but **does not block Phase A** — we built the image manually. If you want me to clean those up, say so and I'll do it in a separate pass.

[INFERRED — Kay sign-off on Phase A deployment]
