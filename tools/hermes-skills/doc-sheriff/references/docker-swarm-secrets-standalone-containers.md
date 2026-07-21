# Docker Swarm Secrets vs Standalone Containers — Why Secrets Failed

**Date:** Jul 16, 2026  
**Incident:** Telegram token broken for 2+ days despite Docker Secret being "correct"  
**Root Cause:** Docker Swarm secrets only work with Swarm services. UAT and PROD are standalone containers.

---

## The Two Docker Worlds

### Swarm Services (`docker service create`)
- Secrets injected via `secrets:` block in compose file
- Mounted at `/run/secrets/<name>` inside the service container
- Secrets visible via `docker secret inspect`
- Works with: Docker Swarm mode

### Standalone Containers (`docker run`, `docker compose up`)
- `secrets:` block in compose is **completely ignored**
- `docker secret inspect` shows secrets exist in the Swarm, but standalone containers **cannot read them**
- Even with Docker socket mounted (`/var/run/docker.sock`), the Docker API for secrets (`GET /secrets`) returns secret metadata but **never the secret data** from inside a standalone container
- Works with: Docker Swarm mode ONLY

---

## How to Check

```bash
# Are you running Swarm or standalone?
docker info | grep Swarm
# Swarm: active = Swarm mode
# Swarm: inactive = standalone mode

# From inside a container — can you list secrets?
docker exec <container> docker secret ls
# If "docker not found" inside container → standalone container
# If permission denied or empty → standalone container trying to access Swarm secrets

# Check if a container's vault is a bind mount or ephemeral rootfs
docker exec <container> cat /proc/1/mounts | grep vault
# rootfs /app/vault rootfs rw → EPHEMERAL (no host bind mount)
# /host/path /app/vault /dev/sda1 rw → BIND MOUNT (persistent)
```

---

## The Telegram Failure Path

```
[Architectural assumption Jul 15]
Docker Secret created: telegram_bot_tokenMarvless01bot
Entrypoint reads secret via read_docker_secret.py
Container gets correct token ✓

[Reality Jul 16]
UAT + PROD are standalone containers (Swarm: inactive)
read_docker_secret.py fails: API returns secret metadata but no data
Secret reader logs: "Could not extract value from secret response"
Entrypoint falls back to empty env var
Vault file has stale/old token
Telegram returns 401/404

[Why it seemed to work Jul 15]
Old tokens were in vault files from manual entry
New Docker Secret was created but entrypoint couldn't read it
Stale tokens in vault files masked the problem temporarily
```

---

## The Correct Architecture for Standalone Containers

**Source of truth:** Host filesystem (bind mount)

```
Host: /volume1/Docker/trading-agent-uat/vault/TELEGRAM_BOT_TOKEN.env
  ↓ bind mount
Container: /app/vault/TELEGRAM_BOT_TOKEN.env
```

**Entrypoint behavior (for standalone containers):**
1. Reads env vars → writes to `/app/vault/`
2. If env var is empty → vault file stays as-is
3. Bind mount means the host file persists across restarts

**To update token:**
1. Edit host vault file (via NAS Explorer in Portainer)
2. Restart container → new token picked up

**NO Docker Secrets needed for standalone containers.**

---

## Key Verification Commands

```bash
# Verify token in container matches host file
docker exec trading-agent-uat cat /app/vault/TELEGRAM_BOT_TOKEN.env
# vs
cat /volume1/Docker/trading-agent-uat/vault/TELEGRAM_BOT_TOKEN.env

# Probe Telegram directly
TOKEN=$(docker exec trading-agent-uat cat /app/vault/TELEGRAM_BOT_TOKEN.env)
curl -s https://api.telegram.org/bot${TOKEN}/getMe

# Check vault persistence
docker exec <container> cat /proc/1/mounts | grep vault
# Ephemeral: rootfs /app/vault rootfs rw,size=...
# Persistent: /dev/sda1 on /app/vault type ext4 rw,relatime
```

---

## Lesson

> Never assume Docker Secrets work without verifying Swarm mode AND container type. A container that can `docker secret ls` is a Swarm service. A standalone container cannot read Swarm secrets even with the socket mounted. When in doubt: probe the actual container, not the documentation.
