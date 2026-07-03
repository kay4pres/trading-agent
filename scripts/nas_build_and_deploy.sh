#!/usr/bin/env bash
# ============================================================
# trading-agent build & deploy to nas:5000
# Run from git-bash on your PC
# ============================================================

set -e

# ── EDIT THESE ──────────────────────────────────────────────
NAS_SSH_USER="NAS_USERNAME"       # e.g. admin — FILL IN
NAS_HOST="10.8.0.10"              # don't change
PORTAINER_USER="PORT_USERNAME"    # e.g. admin — FILL IN
PORTAINER_PASS="PORT_PASSWORD"    # FILL IN
# ─────────────────────────────────────────────────────────────

REPO_DIR="/z/trading-agent-source"
IMAGE="nas:5000/trading-agent:latest"
CONTAINER_NAME="trading-agent"

echo "=== Step 1/4: Pull latest from Gitea ==="
ssh "$NAS_SSH_USER@$NAS_HOST" "cd $REPO_DIR && git pull gitea dev"
echo "✓ Code updated"

echo ""
echo "=== Step 2/4: Build Docker image (no cache) ==="
# Build on NAS where Z: drive is local — no network latency
ssh "$NAS_SSH_USER@$NAS_HOST" "cd $REPO_DIR && docker build --no-cache -t $IMAGE -f docker/Dockerfile ."
echo "✓ Image built"

echo ""
echo "=== Step 3/4: Push to nas:5000 registry ==="
ssh "$NAS_SSH_USER@$NAS_HOST" "docker push $IMAGE"
echo "✓ Image pushed to nas:5000"

echo ""
echo "=== Step 4/4: Restart container via Portainer API ==="
# Authenticate with Portainer
TOKEN=$(ssh "$NAS_SSH_USER@$NAS_HOST" \
  "curl -s -X POST http://localhost:9000/api/auth \
   -H 'Content-Type: application/json' \
   -d '{\"username\":\"$PORTAINER_USER\",\"password\":\"$PORTAINER_PASS\"}'" \
  | grep -o '"jwt":"[^"]*' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
  echo "✗ Portainer auth failed — restart container manually in Portainer UI"
  exit 1
fi

# Get container ID
CONTAINER_ID=$(ssh "$NAS_SSH_USER@$NAS_HOST" \
  "curl -s http://localhost:9000/api/containers/json \
   -H 'Authorization: Bearer $TOKEN'" \
  | grep -o "\"Id\":\"[^\"]*$CONTAINER_NAME[^\"]*\"" \
  | grep -o '"Id":"[^"]*' | head -1 | cut -d'"' -f4)

if [ -z "$CONTAINER_ID" ]; then
  echo "✗ Could not find container '$CONTAINER_NAME'"
  exit 1
fi

# Restart container
ssh "$NAS_SSH_USER@$NAS_HOST" \
  "curl -s -X POST http://localhost:9000/api/containers/$CONTAINER_ID/restart \
   -H 'Authorization: Bearer $TOKEN'"

echo "✓ Container restarted"

echo ""
echo "=== All done ==="
echo "Dashboard: http://10.8.0.10:5050"
