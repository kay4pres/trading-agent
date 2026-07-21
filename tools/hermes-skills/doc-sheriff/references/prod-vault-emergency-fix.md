# PROD Vault Emergency Fix — Ephemeral Vault Recovery

## Problem
PROD container `trading-agent` (compose/10) is running but the vault bind mount target does NOT exist on the NAS host:
```
/volume1/Docker/PortainerCE/data/compose/10/vault/   ← MISSING on host
```
Container is running with an **ephemeral writable layer** vault — files survive container restart only if the image hasn't changed, and are lost if the container is recreated.

**Diagnosis:**
```bash
# Check if vault dir exists on host
ssh -i "E:/Me/TradingAgent/vault/Ai_agent_01_openssh.key" Ai_agent_01@10.8.0.10 \
  "ls -la /volume1/Docker/PortainerCE/data/compose/10/vault/ 2>/dev/null || echo 'MISSING'"

# Check what's inside the running container's vault
docker exec trading-agent ls -la /app/vault/

# If container vault has files but host dir is missing = EPHEMERAL
docker exec trading-agent stat /app/vault/TELEGRAM_BOT_TOKEN.env
# Compare mtime to host dir mtime — if host is older/missing, it's ephemeral
```

## Fix Procedure

### Step 1 — Create vault directory on host
```bash
ssh -i "E:/Me/TradingAgent/vault/Ai_agent_01_openssh.key" Ai_agent_01@10.8.0.10 \
  "mkdir -p /volume1/Docker/PortainerCE/data/compose/10/vault && chmod 755 /volume1/Docker/PortainerCE/data/compose/10/vault"
```

### Step 2 — Copy vault files from running container to host
```bash
# Read current vault files from container
docker exec trading-agent cat /app/vault/ALPACA_API_KEY.env
docker exec trading-agent cat /app/vault/ALPACA_SECRET_KEY.env
docker exec trading-agent cat /app/vault/MINIMAX_API_KEY.env
docker exec trading-agent cat /app/vault/TELEGRAM_BOT_TOKEN.env

# Write to host vault (single SSH with heredoc)
ssh -i "E:/Me/TradingAgent/vault/Ai_agent_01_openssh.key" Ai_agent_01@10.8.0.10 << 'EOF'
  mkdir -p /volume1/Docker/PortainerCE/data/compose/10/vault
  chmod 755 /volume1/Docker/PortainerCE/data/compose/10/vault
  printf '%s' 'VALUE_FROM_ABOVE' > /volume1/Docker/PortainerCE/data/compose/10/vault/ALPACA_API_KEY.env
  printf '%s' 'VALUE_FROM_ABOVE' > /volume1/Docker/PortainerCE/data/compose/10/vault/ALPACA_SECRET_KEY.env
  printf '%s' 'VALUE_FROM_ABOVE' > /volume1/Docker/PortainerCE/data/compose/10/vault/MINIMAX_API_KEY.env
  printf '%s' 'VALUE_FROM_ABOVE' > /volume1/Docker/PortainerCE/data/compose/10/vault/TELEGRAM_BOT_TOKEN.env
  chmod 600 /volume1/Docker/PortainerCE/data/compose/10/vault/*.env
  ls -la /volume1/Docker/PortainerCE/data/compose/10/vault/
EOF
```

### Step 3 — Add docker socket mount to PROD compose
The `read_docker_secret.py` script needs docker socket access. Add to compose volumes section:
```yaml
volumes:
  - ./vault:/app/vault:rw
  - /var/run/docker.sock:/var/run/docker.sock:ro   # ADD THIS
  - /data/compose/10/vault/read_docker_secret.py:/app/read_docker_secret.py:ro  # ADD THIS
```

### Step 4 — Copy read_docker_secret.py to PROD vault
```bash
ssh -i "E:/Me/TradingAgent/vault/Ai_agent_01_openssh.key" Ai_agent_01@10.8.0.10 \
  "cp /volume1/Docker/trading-agent-uat/read_docker_secret.py /volume1/Docker/PortainerCE/data/compose/10/vault/read_docker_secret.py && chmod 644 /volume1/Docker/PortainerCE/data/compose/10/vault/read_docker_secret.py"
```

### Step 5 — Update entrypoint_wrapper.sh in PROD vault
```bash
ssh -i "E:/Me/TradingAgent/vault/Ai_agent_01_openssh.key" Ai_agent_01@10.8.0.10 \
  "cat > /tmp/ep_wrapper.sh << 'WRAP'
#!/bin/bash
export PATH=/usr/local/bin:/usr/bin:/bin:/sbin:/usr/local/sbin
python3 /app/vault/read_docker_secret.py telegram_bot_tokenMarvless01bot /app/vault/TELEGRAM_BOT_TOKEN.env 2>/dev/null || true
python3 /app/vault/fix_cron_after_startup.py &
exec python3 /app/entrypoint.py
WRAP
cp /tmp/ep_wrapper.sh /volume1/Docker/PortainerCE/data/compose/10/vault/entrypoint_wrapper.sh
chmod 755 /volume1/Docker/PortainerCE/data/compose/10/vault/entrypoint_wrapper.sh"
```

### Step 6 — Recreate PROD container
```bash
ssh -i "E:/Me/TradingAgent/vault/Ai_agent_01_openssh.key" Ai_agent_01@10.8.0.10 \
  "cd /volume1/Docker/PortainerCE/data/compose/10 && docker compose down && docker compose up -d"
```

### Step 7 — Verify
```bash
# Vault dir now exists on host
ssh -i "E:/Me/TradingAgent/vault/Ai_agent_01_openssh.key" Ai_agent_01@10.8.0.10 \
  "ls -la /volume1/Docker/PortainerCE/data/compose/10/vault/"

# Container vault has files
docker exec trading-agent ls -la /app/vault/

# Docker socket accessible
docker exec trading-agent ls /var/run/docker.sock

# read_docker_secret.py exists
docker exec trading-agent ls /app/read_docker_secret.py
```

## Telegram Token Fix (After New Bot Created)

Once Kay creates new `@Marvless01_bot` via @BotFather and provides the token:

```bash
# Update UAT Docker Secret
docker secret rm telegram_bot_tokenMarvless01bot 2>/dev/null
printf '%s' 'NEW_TOKEN' | docker secret create telegram_bot_tokenMarvless01bot -
docker compose -f /volume1/Docker/trading-agent-uat/docker-compose.yml up -d

# Update PROD stack.env (then restart)
ssh -i "E:/Me/TradingAgent/vault/Ai_agent_01_openssh.key" Ai_agent_01@10.8.0.10 \
  "sed -i 's/TELEGRAM_BOT_TOKEN=.*/TELEGRAM_BOT_TOKEN=NEW_TOKEN/' /volume1/Docker/PortainerCE/data/compose/10/stack.env"
docker restart trading-agent
```

## Key Distinction: 404 vs 401

| HTTP Code | Meaning | Action |
|-----------|---------|--------|
| `{"ok":false,"error_code":404}` | Bot was **DELETED** via @BotFather | Must create new bot — old tokens are permanently dead |
| `{"ok":false,"error_code":401}` | Token was **revoked** but bot still exists | Can generate new token via @BotFather for same bot |
| `{"ok":false,"error_code":403}` | Bot blocked or bot disabled | Check @BotFather for bot status |
