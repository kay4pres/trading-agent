# Docker Secrets Setup — Trading Agent Databases

> **Owner:** DevOps  
> **Created:** 2026-07-08  
> **Purpose:** Document how to provision and verify Docker Secrets for the standalone `trading_agent_<env>` databases.

---

## Secrets to Create

| Secret Name | Environment | Purpose |
|---|---|---|
| `TRADING_AGENT_DB_PASSWORD_DEV` | Development | Password for `trading_agent_dev` PostgreSQL user |
| `TRADING_AGENT_DB_PASSWORD_UAT` | UAT | Password for `trading_agent_uat` PostgreSQL user |
| `TRADING_AGENT_DB_PASSWORD_PROD` | Production | Password for `trading_agent_prod` PostgreSQL user |

---

## Step-by-Step Setup

### 1. Connect to the NAS via WireGuard

```bash
# Ensure WireGuard is active and you can reach the NAS
# NAS management IP: 10.8.0.10
ssh <your-nas-user>@10.8.0.10
```

### 2. Create Docker Secrets

Run each command on the NAS shell (requires Docker Swarm mode — DSM 7+ has this enabled by default):

```bash
# DEV
echo "your-strong-dev-password" | docker secret create TRADING_AGENT_DB_PASSWORD_DEV -

# UAT
echo "your-strong-uat-password" | docker secret create TRADING_AGENT_DB_PASSWORD_UAT -

# PROD
echo "your-strong-prod-password" | docker secret create TRADING_AGENT_DB_PASSWORD_PROD -
```

> **Security note:** Replace the placeholder passwords with strong, unique values. Do not use the same password across environments. The `echo ... | docker secret create ... -` pattern avoids password appearing in shell history.

---

## How the Container Consumes These Secrets

In the `trading-agent` `docker-compose.yml` (or `container definition`), each secret is referenced as a Docker Swarm secret and mounted into the container as a file:

```yaml
secrets:
  TRADING_AGENT_DB_PASSWORD_DEV:
    external: true
  TRADING_AGENT_DB_PASSWORD_UAT:
    external: true
  TRADING_AGENT_DB_PASSWORD_PROD:
    external: true

services:
  trading-agent:
    image: trading-agent:latest
    secrets:
      - TRADING_AGENT_DB_PASSWORD_DEV
      - TRADING_AGENT_DB_PASSWORD_UAT
      - TRADING_AGENT_DB_PASSWORD_PROD
    environment:
      DB_HOST: "<host>"
      TRADING_AGENT_DB: "trading_agent_<env>"
      # The container reads the secret file directly:
      # e.g., /run/secrets/TRADING_AGENT_DB_PASSWORD_DEV
```

The application reads the password from the secret file at runtime (typically `/run/secrets/<secret_name>`). No environment variable leakage occurs since secrets are mounted as files, not exposed via `env:`.

---

## Verification Commands

### On the NAS — confirm secrets exist:

```bash
docker secret ls
```

Expected output should list all three secrets:

```
ID                          NAME                              CREATED              UPDATED
xxxxxxxxxxxxx              TRADING_AGENT_DB_PASSWORD_DEV     2026-07-08 ...       ...
xxxxxxxxxxxxx              TRADING_AGENT_DB_PASSWORD_UAT     2026-07-08 ...       ...
xxxxxxxxxxxxx              TRADING_AGENT_DB_PASSWORD_PROD    2026-07-08 ...       ...
```

### Inspect a secret (metadata only — value is never shown):

```bash
docker secret inspect TRADING_AGENT_DB_PASSWORD_DEV
```

### Inside the running container — verify secret file is mounted:

```bash
docker exec <container_name> ls /run/secrets/
# Should list: TRADING_AGENT_DB_PASSWORD_DEV, TRADING_AGENT_DB_PASSWORD_UAT, TRADING_AGENT_DB_PASSWORD_PROD

docker exec <container_name> cat /run/secrets/TRADING_AGENT_DB_PASSWORD_DEV
# Should output the password (keep terminal safe / clear after reading)
```

---

## Rollback / Re-create a Secret

If a secret needs to be updated:

```bash
# Remove old secret
docker secret rm TRADING_AGENT_DB_PASSWORD_UAT

# Re-create with new value
echo "new-uat-password" | docker secret create TRADING_AGENT_DB_PASSWORD_UAT -
```

> **Note:** Removing a secret that is currently in use will cause the service to fail. Perform secret rotations during a maintenance window or use `docker config` with a versioned approach for zero-downtime rotation.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `Error: This node is not a swarm manager` | Docker not in Swarm mode | Enable Swarm in DSM or use `docker swarm init` |
| Secret file not found inside container | Secret not declared in `secrets:` block of service | Add secret to service definition in compose file |
| Service starts but DB connection fails | Wrong password in secret | Re-create the secret with correct value |
| `docker secret ls` returns empty | Secrets were not created or were created on a different node | Ensure you are on the manager node |

---

## Next Steps After Setup

1. ✅ Create Docker Secrets (this doc)
2. ⬜ Wire `trading_agent_<env>` into `docker-compose.yml` (see Kanban task: "Wire trading_agent_<env> into trading-agent docker-compose")
3. ⬜ Create the `trading_agent_dev/uat/prod` databases on the NAS PostgreSQL instance
4. ⬜ Update orchestrator guardrails to reference Docker Secrets (see Kanban task: "Update orchestrator guardrails: DB schema, agent registry")
