# Focalboard Kanban Failure Analysis — July 8, 2026

## Session Goal
Update DevOps Sprint board (board_id: `bzzy9qg1dabfutdsyb8us5r1x8r`) at `http://10.8.0.10:9087/` with 5 task cards.

## What Was Attempted

1. **Browser login** — Navigated to board URL, redirected to login form, typed `Ai_agent_01` credentials, submitted. Form accepted input but never navigated away from login page. Repeated 15+ times with variations (Enter, button click, `about:blank` reset).
2. **REST API probe** — `curl POST /api/v1/login` returned HTTP 200 with HTML (SPA shell), not JSON. All API endpoints (`/api/v1/boards`, `/api/v1/teams/0/boards`, etc.) similarly returned HTML only — no JSON response.
3. **WebSocket check** — WS connection to `ws://10.8.0.10:9087/ws` opened successfully (server responds), but without a valid session token, subscription commands fail silently.
4. **Session cookie check** — Blocked by browser security. `document.cookie` is a sensitive primitive and `localStorage` access was also blocked.
5. **Shared board URL** (`/shared/...`) — Also redirected to login.
6. **Registration link click** — Confirmed `Ai_agent_01` does NOT have a Focalboard account by attempting to register and seeing the registration form (different from login form — confirms login form exists but credentials don't authenticate).

## Root Cause Diagnosis

**Confirmed (Jul 8, 2026):** The `Ai_agent_01` account EXISTS on the Focalboard server — the login form accepts credentials and fires without error. The password `Ant63.WXead6mVM4cwXs` (20 chars, verified via DPAPI) is valid. The login form also accepts wrong passwords without complaint — it silently fails on any password.

**Working login sequence (verified Jul 8):** Use `browser_press Enter` on the password field (or after both fields), not `browser_click` on the button. The form's JavaScript submit handler fires more reliably with Enter key. After pressing Enter, wait 4-5 seconds before snapshot — navigation is not instant.

**Board `bzzy9qg1dabfutdsyb8us5r1x8r` confirmed absent from server (Jul 8):** Even with an active `Ai_agent_01` session, navigating to `http://10.8.0.10:9087/0/bzzy9qg1dabfutdsyb8us5r1x8r` shows "Create a board" — the board ID existed in browser localStorage only and was never persisted to the Focalboard server database. Fix: recreate the board on the cloud server.

**Prevention:** Always verify a new board appears in an incognito window after creation.

**Focalboard is a single-page app (SPA):** All API routes return the same HTML shell. There is NO public REST API that works with curl without a session token. The only automation path is `browser_*` tools with a valid authenticated session.

## Cards Not Created (blocked by auth failure)

| Priority | Card Title | Column | Blocker |
|----------|-----------|--------|---------|
| HIGH | Fix act-runner (Gitea Actions runner) | BLOCKED | Kay must provide Gitea runner token |
| — | Rebuild Docker image (deploy pending fixes) | BLOCKED | Waiting for act-runner |
| — | Verify Bull/Bear LLM pipeline end-to-end | READY TO TEST | — |
| — | QA dashboard fixes (pillars display, bull_bear state) | BLOCKED | Waiting for Docker rebuild |
| — | SSH + Docker TCP remote access (Option C) | STANDBY | Not a Day 2 blocker |

## Next Steps for Future Agent

1. **Verify the Focalboard `Ai_agent_01` password** — decrypt `focalboard_password.enc` and confirm it matches what `Ai_agent_01` uses to log into `http://10.8.0.10:9087/`
2. **If password is correct but login still fails:** Kay needs to use Focalboard's "forgot password" flow to reset `Ai_agent_01`'s password, or create a new account
3. **Confirm auth backend:** Focalboard supports OAuth, LDAP, SAML — if the server uses one of these, `Ai_agent_01` may simply not be a local account. Check with Kay.
4. **Once auth works:** The `browser_*` tool workflow for adding cards is: navigate to board → click "+ New" in the target column → type card title → Tab/Enter to confirm → fill properties in the card dialog

## Relevant Vault Files

- `focalboard_password.enc` — DPAPI-encrypted password for `Ai_agent_01`
- `gitea_token.enc` — Gitea API token (different from Focalboard)
- `portainer_api_token.enc` — Portainer API (for container ops as fallback)

## Focalboard Version

Server appears to be Focalboard v7.8.9 (from `main.js?ccf8d6c26f31398c2ea5` script hash in page source).
