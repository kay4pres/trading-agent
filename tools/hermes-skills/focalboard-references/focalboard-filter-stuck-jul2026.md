# Focalboard "Group by" Filter Gets Stuck — Jul 14, 2026

## Symptom
- Focalboard "Group by: Ready" filter activates (clicking the `Group by:` button in the toolbar)
- Selecting a column (e.g. "Ready") or "none" does NOT reset the filter
- The dropdown opens and shows options, but clicking an option has no visible effect
- The toolbar label remains "Group by: Ready" and cards are hidden accordingly
- Cards still exist — column counts in the sidebar (e.g. "Triage (7)") reflect actual card counts
- But the card area shows "No Ready" and only the filtered column's empty state is visible

## What Was Tried (all failed)
1. Click `Group by:` button → dropdown opens
2. Click "Ready" column text — no effect
3. Click "Board view" in View menu → no effect  
4. Click "Add view" (ref e87) → creates new view, filter still stuck
5. Refresh/navigate → session restored, filter still active

## Root Cause
Focalboard v7.8.9 — the "Group by" state persists server-side in the session. Clicking the dropdown option does not fire the clear/reset action properly.

## Impact
- Board shows incorrect state (appears empty or column appears empty)
- Cards cannot be moved via UI while filter is stuck
- 7 Triage cards were invisible because "Ready" was selected (0 cards in Ready = "No Ready" displayed)

## Workaround
Use Hermes Kanban (`hermes kanban ls`) as the primary board. Focalboard is permanently deprecated for automation due to this bug plus session expiry and API returning HTML.

## Files
- Focalboard URL: http://10.8.0.10:9087/bzzy9qg1dabfutdsyb8us5r1x8r
- Board: DevOps Sprint
- User: Ai_agent_01
- Password (DPAPI vault): `E:\Me\TradingAgent\vault\focalboard_password.enc` → `An363.WXead6mVM4cwXs`
