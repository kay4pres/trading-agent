# Focalboard — Cloud Server vs. Local localStorage Failure (Jul 8 2026)

## The Problem

A board was created (likely in one browser session) and appeared to work. When navigating to its URL from a different browser/tab/session, it showed **"Create a board"** instead of the Kanban.

This is NOT a login failure. The user was already authenticated.

## Root Cause

Focalboard is a **single-page app (SPA)**. Cards are stored server-side in the Focalboard database. But when a board is first created, the creation request may succeed on the server AND be written to browser localStorage simultaneously. 

In some cases (particularly after failed server writes, or if the browser was offline during board creation), the board metadata lives **only in localStorage** — it was never persisted to the Focalboard server database.

When any other session (different browser, different tab, or after localStorage is cleared) tries to access that board URL, the server has no record of it → returns the default "Create a board" SPA shell.

## How to Diagnose

1. Board URL shows "Create a board" even when logged in
2. No error message — just an empty board creation screen
3. Other boards (created the same way) may work fine
4. The URL contains a valid-looking workspace+board ID format

## How to Fix

**Option A — Recreate on server (preferred):**
1. Log into Focalboard as `Ai_agent_01` from any browser
2. Navigate to the workspace root (`http://10.8.0.10:9087/<workspace-id>`)
3. Click "Create a new board" → name it the same
4. Rebuild the cards manually or with PM Agent

**Option B — Export/Import (if cards exist):**
1. Open the board in the browser where it DOES appear (localStorage session)
2. Focalboard v7.x supports board export: Board → Settings → Export
3. Import into the server board

## Prevention

- Always verify a new board appears when accessed from an incognito window
- Check Focalboard server logs if boards are disappearing
- `Ai_agent_01` must have Admin role on the workspace for board creation to persist server-side

## Related

See `references/focalboard-kanban-fail-jul2026.md` for the full auth failure diagnosis including the "login accepted but no session created" variant.
