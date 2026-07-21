# Focalboard + DPAPI Vault — Reference

## Verified Working: Store + Retrieve Cycle

### 1. Store (Kay runs PowerShell)

```powershell
$ErrorActionPreference = 'Stop'
$outPath = "E:\Me\TradingAgent\vault\focalboard_password.enc"

Write-Host "Focalboard Password Vault Storage" -ForegroundColor Cyan
Write-Host "Username: Ai_agent_01" -ForegroundColor Gray
Write-Host "Paste the password below. It will be encrypted with DPAPI" -ForegroundColor Gray
Write-Host "and saved to: $outPath" -ForegroundColor Gray
Write-Host ""

$pass = Read-Host "Password" -AsSecureString
$plain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($pass))

Add-Type -AssemblyName System.Security
$enc = [System.Security.Cryptography.ProtectedData]::Protect(
    [System.Text.Encoding]::UTF8.GetBytes($plain),
    $null,
    [System.Security.Cryptography.DataProtectionScope]::CurrentUser
)

[IO.File]::WriteAllBytes($outPath, $enc)
Remove-Variable pass, plain, enc
Write-Host "[OK] Password encrypted and saved to vault." -ForegroundColor Green
```

### 2. Retrieve (Hermes/agent runs)

```powershell
powershell -Command "
Add-Type -AssemblyName System.Security
\$encBytes = [IO.File]::ReadAllBytes('E:\Me\TradingAgent\vault\focalboard_password.enc')
\$decrypted = [System.Security.Cryptography.ProtectedData]::Unprotect(\$encBytes, \$null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)
\$password = [System.Text.Encoding]::UTF8.GetString(\$decrypted)
Write-Host \$password
"
```

## Verified Vault Files

| File | Contents | Status |
|------|----------|--------|
| `focalboard_password.enc` | Ai_agent_01 Focalboard password | ✅ Verified 2026-07-06 |
| `focalboard_kay_password.enc` | Kay's own Focalboard password (cloud server) | ✅ Stored |
| `store_telegram_token.ps1` | Generic Telegram bot token vault script | ✅ Used for @Hendrika01_bot token |

## DevOps Sprint Board — CRITICAL RECOVERY NEEDED (Jul 8, 2026)

**⚠️ The DevOps Sprint board (`bzzy9qg1dabfutdsyb8us5r1x8r`) is NOT on the cloud server.**

When navigating to `http://10.8.0.10:9087/bzzy9qg1dabfutdsyb8us5r1x8r`, the browser shows **"Create a board"** — the board and all its cards (Triage items from Jul 7, the 6-column structure) exist only in a browser's localStorage and were **never persisted to the cloud server**.

**Symptoms:**
- Board URL returns the "Create a board" page instead of the board
- The sidebar shows "DevOps Sprint" as a board link, but clicking it loads the empty "Create a board" view
- The `bzzy9qg1dabfutdsyb8us5r1x8r` board ID is valid in URL format but has no corresponding cloud record
- The Focalboard REST API (`/api/v2/boards/{id}`) returns `{"error":"checkCSRFToken FAILED"}` for unauthenticated requests; authenticated browser session also shows the wrong page

**Diagnosis sequence (Scrummaster should run these first):**
1. Navigate to `http://10.8.0.10:9087/bzzy9qg1dabfutdsyb8us5r1x8r` — if it shows "Create a board", the board is in localStorage only
2. Press Escape to dismiss any modal dialog, then check the sidebar for the "BOARDS" section
3. If "DevOps Sprint" appears under BOARDS in the sidebar, click it — if it still shows "Create a board", the board is localStorage-only
4. Alternatively: open the browser's developer console → `localStorage.getItem('focalboard_session')` or similar to confirm session exists

**Recovery options (one of these must be done by a human first):**
1. **Best — Export from localStorage:** In the browser that created the board, use Focalboard's export function or dump localStorage → export board JSON → import to cloud server
2. **Fastest — Recreate:** Log in as Ai_agent_01 at `http://10.8.8.0.10:9087/` from any browser → create a new board → name it "DevOps Sprint" → recreate all 6 columns (Triage, Todo, Ready, In Progress, Blocked, Done) → re-create any needed cards
3. **DSM File Station:** Board data may exist in a Focalboard SQLite DB on the NAS if the server uses file-based storage (check `/var/packages/Focalboard/` on the NAS)

**Prevention:** Always verify a board persists by opening it from a different browser tab or incognito window before considering it saved. If "Create a board" appears, the board is localStorage-only.

**Cards lost (Jul 7 state):** 4 in Triage ("1. Rebuild container", "2. Fix GitHub Actions", "3. Add smoke test", "🚕 Fix @Marvless01_bot"), 0 in other columns. These must be recreated.

## Key Architectural Facts

- `localhost:9087` and `10.8.0.10:9087` are the **same Focalboard server** (self-hosted on NAS)
- Kay's local board created at `localhost:9087` in his browser's localStorage does **not** automatically appear for other users — it lives in his browser session only
- The correct multi-agent board URL is `http://10.8.0.10:9087/<workspace-id>/<board-id>`
- Navigating to just the workspace root (`http://10.8.0.10:9087/<workspace-id>`) shows "Create a board" — the board doesn't exist at that URL without the board-id
- There is ONE shared DevOps Sprint board on the cloud server — Kay and Ai_agent_01 both access it from their own browser tabs at the same URL
- **⚠️ Prevention rule: Always verify a board persists by opening it from a different browser tab or incognito window before considering it saved.** If "Create a board" appears in the second tab, the board is localStorage-only and must be exported/imported to persist.
