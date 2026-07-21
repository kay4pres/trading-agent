# Focalboard — Failure Modes Reference (Jul 9, 2026)

Four distinct failure modes. Diagnose with the symptom, not the file.

---

## Mode 1: "Create a board" at a board URL — localStorage-only board

**Symptom:** Navigating to `http://10.8.0.10:9087/<workspace>/<board-id>` shows the "Create a board" welcome dialog, even when logged in as `Ai_agent_01`.

**Root cause:** The board was persisted to browser localStorage but never written to the Focalboard server database. This happens when the server write fails silently (e.g., offline during creation, or the server API endpoint wasn't reached).

**Diagnosis:** Other boards from the same account work fine → board-specific, not auth. Board ID looks valid (e.g. `bzzy9qg1dabfutdsyb8us5r1x8r`).

**Fix:** Recreate on server. Log in as `Ai_agent_01` → workspace root → "Create a new board" → name it → verify in incognito window.

**Prevention:** Always open a new board in an incognito window after creation.

---

## Mode 2: Login accepts credentials but no session created — **RESOLVED Jul 9, 2026**

**Original symptom (Jul 8):** Form accepted `Ai_agent_01` + password, button fired, but page never navigated.

**Root cause (Jul 8):** `browser_click` on the Log In button does NOT reliably fire the form's JavaScript submit handler.

**Fix (Jul 9 — VERIFIED WORKING):** Use `browser_press Enter` on the **password field**, not `browser_click` on the Log In button. After pressing Enter, wait **4-5 seconds** before snapshot — navigation is not instant.

```
1. browser_navigate → http://10.8.0.10:9087/bzzy9qg1dabfutdsyb8us5r1x8r
   → redirected to /login, form visible
2. browser_type username → Ai_agent_01
3. browser_click password field (or Tab to it)
4. browser_type password → [decrypted from vault]
5. browser_press Enter  ← USE THIS, NOT button click
6. wait 4-5 seconds
7. browser_snapshot → board loads
```

**Confirmed working Jul 9, 2026:** Password `An363.WXead6mVM4cwXs` + Enter key = successful login to DevOps Sprint board `bzzy9qg1dabfutdsyb8us5r1x8r`.

---

## Mode 3: `/api/v1/*` returns HTML — but `/api/v2/*` is a real JSON API

**Symptom:** `curl http://10.8.0.10:9087/api/v1/boards` returns 200 with HTML.

**Root cause:** `/api/v1/*` is handled by the SPA router (all routes return the same HTML shell). The **real JSON API is `/api/v2/*`**.

**Verified working JSON endpoints (require session/CSRF):**
- `GET /api/v2/clientConfig` → `{"error":"checkCSRFToken FAILED","errorCode":400}` ✅ server speaks JSON
- `POST /api/v2/login` → `{"error":"invalid login type","errorCode":400}` ✅ server speaks JSON

**Login format for v2 API:**
```json
POST /api/v2/login
Content-Type: application/json
X-Requested-With: XMLHttpRequest

{"loginId":"admin","password":"PASSWORD"}
```
Returns `{"error":"invalid login type","errorCode":400}` — the server uses a non-standard `loginType` value (SSO/OAuth), not `normal`/`username`/`email`.

**Key finding (Jul 8, 2026):** The Focalboard server at `10.8.0.10:9087` has a JSON API (v2) but the login endpoint requires a `loginType` that standard values don't satisfy. Browser-based authentication is the only working path. The vault password `An363.WXead6mVM4cwXs` is confirmed valid via DPAPI decryption — `Ai_agent_01` login now works with the Enter-key pattern (Mode 2 resolved).

---

## Mode 4: `Group by: <column>` Hides ALL cards (NEW — Jul 9, 2026)

**Symptom:** Board appears completely empty — no cards visible in any column. All previously-seen cards have vanished without trace.

**Root cause:** Focalboard's "Group by" feature (toolbar button `Group by:`) filters the display to show only ONE column's cards. If `Group by: Ready` is set and Ready has 0 cards, the ENTIRE board shows as empty — all cards in Triage, Todo, In Progress, Blocked, Done are invisible but **still exist on the server**.

**Diagnosis:**
- Board header shows `Group by: Ready` (or another column name) → a filter is active
- The Jul 8 session misdiagnosed this as "board doesn't exist on server" — it was purely a view filter issue
- Board ID `bzzy9qg1dabfutdsyb8us5r1x8r` confirmed on server (successful login Jul 9, 2026)

**Fix:** Click `Group by:` button in the toolbar → select a different column name, or select "none" to show all cards ungrouped.

**Prevention:** After every successful login, immediately verify `Group by:` is set to "none" (or the intended column). If a Scrummaster run reports "board is empty," the **first** diagnostic is to check `Group by:`.

## Quick Diagnostic Checklist

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Board URL → "Create a board" | localStorage-only board | Recreate on server |
| Login accepted, no session | Use Enter key, not button click | Mode 2 fix |
| Board appears empty | `Group by:` filter active | Set to "none" |
| All API v1 calls return HTML | v1 is SPA catch-all | Use `/api/v2/*` for JSON |
| All API v2 calls return CSRF error | Session required | Use browser auth first |
| Session expires on every action | Normal SPA behavior | Re-authenticate |
| Port 9087 unreachable | Focalboard container down | Check via DSM / Portainer |

---

## Vault Credential

`focalboard_password.enc` → `An363.WXead6mVM4cwXs` (verified Jul 8, 2026 via DPAPI decryption)
