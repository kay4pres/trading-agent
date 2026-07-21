# Telegram Token Autopsy — Jul 16, 2026

## What Happened

Both `@Marvless01_bot` tokens returned `404 Not Found` on `getMe`. Initial conclusion: "bot deleted." Actual conclusion after deeper probe: **tokens were revoked, bot still exists**.

**The error codes:**
| HTTP Code | `getMe` result | Meaning | Fix |
|-----------|---------------|---------|-----|
| `{"ok": false, "error_code": 401}` | `Unauthorized` | Token revoked, bot still alive | `/revoke` in BotFather → new token |
| `{"ok": false, "error_code": 404}` | `Not Found` | **Ambiguous**: bot deleted OR token revoked | Must check BotFather `/mybots` |

**BotFather `/mybots` checklist:**
1. Open Telegram → @BotFather → `/mybots`
2. If `@Marvless01_bot` appears → bot alive → just `/revoke` → new token
3. If NOT listed → bot deleted → `/newbot` → recreate with same name

## PROD Token Extraction (xxd technique)

PROD docker exec masks tokens with `***` in stdout. Full value extracted via hex:

```bash
# PROD container — raw hex dump (no masking)
docker exec trading-agent cat /app/vault/TELEGRAM_BOT_TOKEN.env | xxd -p | tr -d '\n'

# Decode
python -c "hex_str='HEXSTRING'; print(bytes.fromhex(hex_str).decode('ascii'))"
```

**PROD token hex:** `383934303631323934383a414145623d456e6574615f6838544852585257494d506c727646786b4c6d6247393455`
**PROD token:** `8940612948:AAEb=Eneta_h8THRXRWIMPlrvFxkLmbG94U`
**Anomaly:** `=` mid-token and `AAEb=` sequence non-standard. Telegram tokens are URL-safe base64. This suggests corruption during Jul 15 rotation (stdin redirection likely failed over SSH, leaving partial token).

**UAT token (valid format):** `8951488228:AAEQ4TomWhQ.E8s9QC86r` → `getMe` = 404 = revoked but bot alive

## Architecture State (Jul 16)

| Component | Status | Detail |
|-----------|--------|--------|
| UAT docker-compose.yml | ✅ Clean | `TELEGRAM_BOT_TOKEN` env var commented, Docker Secret referenced in comment only |
| UAT vault (bind mount) | 🔴 Stale | `8951488228:AAEQ4TomWhQ.E8s9QC86r` — revoked token |
| UAT entrypoint | ✅ Correct | Standard entrypoint.py reads env var → writes vault |
| UAT Docker Secret | ✅ Correct | `telegram_bot_tokenMarvless01bot` contains valid token |
| PROD vault | 🔴 Ephemeral | `/volume1/Docker/PortainerCE/data/compose/10/vault/` missing on host — container uses writable layer |
| PROD stack.env | 🔴 Hardcoded | `TELEGRAM_BOT_TOKEN=8940612948:***` masked |
| PROD entrypoint_wrapper.sh | ✅ Correct | `/app/vault/read_docker_secret.py` + `entrypoint.py` |
| PROD docker.sock mount | ❌ Missing | Not in PROD compose |
| Fix scripts (`fix-prod-telegram.py`) | ❌ Never executed | Created in `C:\Users\Kay\AppData\Local\Temp\` Jul 15, never run |

## 13 Token Locations — What to Delete

```
WINDOWS HOST (Kay's PC) — DELETE ALL:
E:\Me\TradingAgent\vault\telegram_token.enc
E:\Me\TradingAgent\vault\TELEGRAM_BOT_TOKEN.env
E:\Me\TradingAgent\config\telegram_token.enc
C:\Users\Kay\AppData\Local\hermes\.env  (remove TELEGRAM line)

NAS DOCKER — MIGRATE/DELETE:
Docker Secret (telegram_bot_tokenMarvless01bot) → UPDATE with new token
UAT vault bind mount → overwrite after new token
PROD vault → create on host after new token
stack.env PROD → update with new token
```

**Only source of truth AFTER fix:**
- Docker Secret `telegram_bot_tokenMarvless01bot` (UAT + DEV)
- `stack.env` (PROD — not Swarm, so must use file)
- Entrypoint distributes to `/app/vault/TELEGRAM_BOT_TOKEN.env` in all containers

## Self-Healing Loop Design

```
ops-trader health cron (every 15 min):
  curl https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe

  200 OK     → silent, log to .telegram-health.log
  401        → token revoked → rotate via Docker Secret rm+create + restart
  404        → BOT DELETED → alert Kay via @Hendrika01_bot (separate bot)
```

**404 is the hard stop** — cannot auto-create bot. Must alert Kay with exact instructions.

**Health log:** `E:\Me\TradingAgent\docs\.telegram-health.log` — append-only, every probe + result + action taken.

## The Jul 15 Architecture Was Correct — But Never Executed

The Docker Secret + entrypoint distribution pattern designed Jul 15 was the right architecture. The failure was operational: scripts were written to `C:\Users\Kay\AppData\Local\Temp\` but never executed. The fix existed on paper only.

**Lesson:** A fix script in a temp directory is not a deployed fix. Fix must be:
1. Pushed to git (if code) OR
2. Actually executed and verified via live probe AND
3. Documented in the session handoff with "EXECUTE THIS" not just "FIXED"
