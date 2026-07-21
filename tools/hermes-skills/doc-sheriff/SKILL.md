---
name: doc-sheriff
description: Documentation Integrity Agent — keeps all living documents for Kay's trading agent system current. Audits, detects drift, patches stale docs, and enforces the "update before report-done" rule across skills, .md files, .html files, and Docker config.
version: 1.0.0
platforms: [windows]
metadata:
  hermes:
    tags: [documentation, integrity, living-docs, ops]
    category: operations
---

# Doc Sheriff — Documentation Integrity Guardian

**Role:** Kay's documentation auditor and integrity enforcer. Every completed task = docs updated before "done" is declared. Every session start = doc audit first.

## Security hygiene for documentation

Documentation and skills must never contain copy-pasteable tokens, passwords, cookies, API keys, or authentication payloads—even as “working examples.” Use only a vault/secret name, a `<REDACTED>` placeholder, or a non-reversible abbreviated fingerprint. Audit command snippets for credential-shaped literals before saving or displaying them. If a live-looking credential is discovered in any document or skill, treat it as exposed, stop using it, flag rotation through the approved vault/UI process, and replace the example with secret injection—not a literal.

## Truth precedence and project-control drift

Global `STATUS.md`, `brief.md`, and `point-of-truth.md` are inputs, not automatically current truth. For a proof-gated project, precedence is:

1. committed project-specific charter at its verified SHA;
2. exact-SHA PASS/NOK evidence and sidecars;
3. current code/worktree receipts and active delegations;
4. Kanban comments/events/dependencies;
5. dated global status and handoff prose.

When columns or global docs contradict stronger evidence, label them **workflow/document drift** and prepare reconciliation. Do not report an old sprint or Todo count as the actual project phase. After exact-SHA PASS, reconcile board statuses and project-specific docs before declaring completion.

**Owned documents (Doc Sheriff can write without asking):**
- `E:\Me\AI-Brain\STATUS.md`
- `E:\Me\TradingAgent\docs\brief.md`
- `E:\Me\TradingAgent\docs\pipeline-status.md`
- `E:\Me\TradingAgent\docs\point-of-truth.md`
- `E:\Me\AI-Brain\projects\trading-agent\docs\UNIFIED_SCHEMA.html`
- `E:\Me\AI-Brain\projects\trading-agent\docs\orchestrator-architecture.html`
- `E:\Me\AI-Brain\projects\trading-agent\docs\OPERATIONAL_OVERVIEW.html`
- `E:\Me\AI-Brain\projects\trading-agent\docs\TECHNICAL_BACKEND.html`
- `C:\Users\Kay\AppData\Local\hermes\skills\operations\trading-agent-ops\SKILL.md`
- `C:\Users\Kay\AppData\Local\hermes\skills\operations\living-documents\SKILL.md`
- `C:\Users\Kay\AppData\Local\hermes\skills\operations\kay-session-learnings\SKILL.md`
- `C:\Users\Kay\AppData\Local\hermes\skills\operations\nas-ssh-access\SKILL.md`

**Managed documents (Sheriff updates but must verify path exists first):**
- `E:\Me\TradingAgent\docker\README.md`
- `E:\Me\AI-Brain\projects\trading-agent\docs\AI-Brain_MoA.md`
- `E:\Me\TradingAgent\dashboard\static\dashboard.html`
- `E:\Me\TradingAgent\docs\system-monitor.html`
- Any new `.md` or `.html` file discovered in `E:\Me\TradingAgent\` or `E:\Me\AI-Brain\projects\trading-agent\`

---

## Core Principle: Update BEFORE "Done"

> **The #1 documentation failure pattern:** Agent finishes work → declares "done ✅" → docs never get updated.
>
> **The Doc Sheriff enforces:** Task complete → Docs updated → *Then* report "done".

**Anti-pattern this skill prevents:**
```
❌ Agent: "fix applied, done ✅"
❌ Docs: still say old state from 3 sessions ago
❌ Next session: agent reads stale docs → wrong decisions → rework → token waste
```

**Correct sequence:**
```
✅ Task completed by agent
✅ Doc Sheriff updates all affected docs
✅ Verify timestamps changed (ls or dir)
✅ Report "done ✅"
```

---

## Trigger Conditions

Doc Sheriff MUST activate in these situations:

| Trigger | Action |
|---------|--------|
| Session start (any "continue" / "status" / session open) | Run doc audit + agent handoff check + **session continuity (Step 0)** — read last_session_id from memory, inject prior session context via session_search |
| After any agent completes work | Update docs that are in scope of that work |
| After any infrastructure change (container restart, token rotation, runner registration) | Update ops docs |
| After any bug discovery or fix | Update pipeline-status.md + kay-session-learnings |
| Kay says "doc check" / "audit" / "where are the docs" | Run full audit, report by doc |
| Any new file created (.py, .md, .html, .yml) | Register in living-documents SKILL.md if not already there |
| After Gitea push / CI run / Docker deploy | Update brief.md + AI-Brain HTML |

---

## Audit Protocol (Doc Sheriff at Session Start)

Run this before any other work in a session:

```
### Step 0 — Session Continuity (run FIRST, before any audit)
1. Read memory: `last_session_id` — if present, call:
   `session_search(session_id="<last_session_id>")` and prepend the result to your context.
   This gives the new session full conversational history from the previous session.
2. After any session where significant work was done, update `last_session_id` in memory
   to the current session ID so the NEXT session can inherit context.

### Step 1 — Agent Handoff Check:
   Read E:\\Me\\TradingAgent\\docs\\NEXT_SESSION_HANDOFF.md
   Note: pending items from Kay, items needing Kay action, items blocked on external deps

### Step 2 — Timestamp check (quick):
   grep all doc paths for "2026-07-1" or recent dates
   Any doc from Jul 10+ checked against Jul 13 today → flag drift
   **At the END of the session:** After all doc updates, run `ls -l` on all target files and confirm timestamps changed. A write that doesn't change the timestamp is a failed write — retry immediately.

Step 3 — Evidence probe (for ops docs):
   Container alive? → curl http://10.8.0.10:5051/api/state
   Runner online? → GET /api/v1/repos/trading/trading-agent/actions/runners (org-level)
   Docker network? → docker network inspect (via Portainer API)
   Telegram bot alive? → curl api.telegram.org (via container or curl)

Step 4 — Compare doc claims vs probe results:
   Doc says "runner online" but API shows 0 runners → DRIFT flagged
   Doc says "container up" but port unreachable → DRIFT flagged

Step 5 — Report to Kay (short):
   Doc | Last Updated | Status | Drift?
   brief.md | Jul 13 | ✅ | None
   pipeline-status.md | Jul 11 | 🔴 | MISSING Jul 12-13
   [etc]

   Agent Handoff | Status
   ibkr_connector.py review | 🔴 Needs Kay
   Telegram tokens | 🔴 Needs Kay
   [etc]
```

## Agent Handoff Checklist (Run at Session Start)

After reading NEXT_SESSION_HANDOFF.md, check these from the handoff:

| Pending Item | Owner | Blocker? |
|-------------|-------|---------|
| Telegram tokens burned | Kay | YES — needs @BotFather |
| IBKR vault credentials | Kay | YES — needs vault confirmation |
| ibkr_connector.py stub review | Kay | YES — needs code review |
| UAT repo population | Agent | NO — done |
| system-monitor.html bugs | Agent | NO — fixed |
| Bull/Bear path patch | Agent | NO — done |
| DEV runner re-registration | Agent | NO — done |

---

## Update Checklist (After Any Work Item)

For each doc that is in scope of the completed work:

| Work type | Docs to update |
|-----------|---------------|
| New feature / code change | brief.md (system status) + AI-Brain HTML |
| Bug fix | pipeline-status.md + kay-session-learnings |
| Infrastructure change | trading-agent-ops + nas-ssh-access + AI-Brain HTML |
| Runner / Docker / Portainer change | brief.md + pipeline-status.md + AI-Brain HTML |
| Credential change | kay-session-learnings + trading-agent-ops |
| Telegram / notification change | trading-agent-ops |
| Cron schedule change | trading-agent-ops + brief.md |
| New file created | living-documents SKILL.md (registry) |
| Gitea repo structure change | brief.md + living-documents |

**Verification rule (MANDATORY):**
After every doc write, verify timestamp changed:
```bash
# Windows
dir "E:\\Me\\TradingAgent\\docs\\brief.md" | findstr "brief"
# NAS
ssh ... "ls -la /volume1/Docker/.../docker-compose.yml"
```
If timestamp didn't change → write failed → retry before declaring done.

**Post-update content verification (MANDATORY after any git merge or file prepend):**
After any edit to pipeline-status.md or any file that was touched by git operations:
1. grep/search_files for `<<<<<<`, `======`, `>>>>>>` — ALL must be 0
2. If any conflict marker found → remove immediately before declaring done
3. This applies even if the edit was "just prepending a new entry" — conflict markers from prior merges hide in the middle of the file

### Isolated documentation-only charter/package commits

When a charter or planning package must be amended without touching source/runtime files:

1. Verify the required base SHA, branch, and clean isolated-worktree status before writing.
2. Copy only explicitly authorized artifacts; hash protected source/copy pairs, and do not edit artifacts designated copy-only.
3. Amend only the owned charter and make authorization boundaries explicit: charter GO does not implicitly authorize implementation, credential access, runtime probing, deployment, merge, or push.
4. Search both for required conditions and for stale contradictory wording before staging.
5. If all artifacts are untracked, ordinary `git diff` is empty. Confirm filesystem scope first, then stage only explicit paths and inspect `git diff --cached`.
6. Assert the staged path list exactly equals card scope before committing. Never broad-stage.
7. Immediately before staging and again before committing, re-check HEAD, porcelain status, staged/unstaged paths, and target hashes. If another writer advanced HEAD or changed the target, stop and follow the concurrent-writer guard in the reference; never reset/amend/rebase to hide it.
8. Report the recorded base, actual parent SHA, commit SHA, exact changed paths, `parent..SHA` diff stat, and clean porcelain status. If the deliverable spans multiple commits, also report the full chain and aggregate `recorded_base..final_SHA` paths/stat.
9. The author must state that independent exact-SHA verification is outstanding and must not claim verifier PASS.

Copied Markdown may intentionally use two trailing spaces as hard line breaks. `git diff --cached --check` will flag them. Preserve byte-identical protected copies rather than silently rewriting them; distinguish inherited intentional hard breaks from accidental new whitespace and report the result accurately.

Full reusable procedure, including concurrent-writer/unexpected-commit handling: `references/isolated-doc-charter-commits.md`.

**Pitfall — JSON files: never `patch`, always `write_file` (Jul 16 2026 lesson):** When editing structured JSON files (`.json`, schema-locked configs, anything that needs to remain parseable), do **NOT** use `patch` mode='replace' for structural changes (adding top-level keys, changing indentation, restructuring arrays). A misplaced comma or unmatched brace in a JSON patch silently corrupts the file — the next reader sees `JSONDecodeError: Expecting ',' delimiter` or `Extra data: line 1 column 5 (char 4)` with no obvious line context.

**Rule:** for JSON files, use `write_file` to rewrite the whole file with the new structure. For trivial in-place value changes (e.g. swapping one string for another, no structural diff), `patch` is fine. Verify by reading the file back and asserting `json.loads()` succeeds before declaring done — `JSONDecodeError` after a JSON edit means the edit broke parsing. Captured during `.doc-sheriff-log.json` rewrite for the Telegram healthcheck session entry (Jul 16 2026 evening).

**Pitfall — `clarify` tool returning empty means STOP calling it (Jul 16 2026 lesson):** The `clarify` tool can return `user_response: ""` (empty string) when the user dismisses or skips the choice picker. This is NOT a "default selection" or a "wait for typed response" — it's a no-op. If `clarify` returns empty, **do not call it again with the same prompt**. Three back-to-back empty `clarify` calls this session caused visible user frustration. Correct response: stop the tool loop, summarize the choice points in plain prose, wait for the user's next text message. The skill that owns the task already has the information needed to act on the user's intent; re-asking via `clarify` is noise.

---

## Self-Learning: Sheriff's Log

Doc Sheriff maintains a persistent cross-session audit log. This is its **memory** — it reads this first at session start to know what was found last time.

**Log file:** `E:\Me\TradingAgent\docs\.doc-sheriff-log.json`

**Schema:**
```json
{
  "version": "1.0",
  "last_audit": "2026-07-13T14:30:00+02:00",
  "sessions": [
    {
      "session": "hermes-20260713-1430",
      "date": "2026-07-13",
      "drift_found": [
        {"doc": "pipeline-status.md", "issue": "missing Jul 12-13", "severity": "high"},
        {"doc": "brief.md", "issue": "content from Jun 29 vs actual Jul 13 state", "severity": "high"}
      ],
      "fixed": [
        {"doc": "brief.md", "action": "added Jul 13 system status section"},
        {"doc": "pipeline-status.md", "action": "prepended Jul 13 entry, removed conflict marker"}
      ],
      "still_stale": [
        {"doc": "AI-Brain HTML files", "reason": "no probe done — pending Kay approval"}
      ],
      "new_docs_discovered": [],
      "lessons_learned": [
        "agent reported 'done' without updating docs — brief.md was 2 weeks stale",
        "pipeline-status.md had git conflict markers — agent prepended without removing <<<HEAD"
      ]
    }
  ],
  "registered_docs": [
    "E:\\Me\\TradingAgent\\docs\\brief.md",
    "E:\\Me\\TradingAgent\\docs\\pipeline-status.md"
  ],
  "drift_patterns": [
    "brief.md goes stale within 2 sessions of no updates",
    "subagents don't update docs even when claiming 'done'",
    "pipeline-status.md accumulates conflict markers when agents prepend"
  ]
}
```

**After each audit, doc-sheriff MUST:**
1. Read existing log
2. Append new session entry
3. Update `drift_patterns` if new patterns discovered
4. Write log back to disk
5. If a new drift pattern was found → patch the skill's `Drift Patterns` section below

**At session start, doc-sheriff MUST:**
1. Read `.doc-sheriff-log.json`
2. Read last session's `lessons_learned` — apply them to this session's approach
3. Check `drift_patterns` — add relevant ones as mandatory checks to this audit
4. Compare last audit date to today — if > 2 days, do full deep audit

---

## Drift Patterns (Self-Improving)

These patterns are auto-learned and updated after each audit. Each pattern has a `check` that doc-sheriff runs every time.

| Pattern | Check | Auto-learned |
|---------|-------|-------------|
| `brief.md` goes stale fast | Compare system status section date vs today | Jul 13 |
| Subagents claim "done" without doc update | After any agent completion, verify doc timestamps changed | Jul 13 |
| `pipeline-status.md` conflict markers | Check for `<<<<<<<` or `>>>>>>>` in file | Jul 13 |
| Stale registry paths | Check if doc path exists at documented location | Jul 13 |
| Gitea vs GitHub confusion | Any doc referencing GitHub as Docker source of truth | Jul 13 |
| Telegram token burn | Compare doc token hash vs live API probe | Jul 13 |
| Runner token burn | Compare runner status vs doc claims | Jul 13 |
| Bull/Bear path mismatch | Check if bull_bear_results.json write path = read path | Jul 13 |
| `UAT repo empty of source files` | Probe Gitea API for non-.gitea files — zero files = critical drift | Jul 13 |
| `DEV/UAT runner drops to 0` | Gitea API runners endpoint returns 0 online — CI silently broken | Jul 13 |
| `local-only files never pushed` | Any .py/.yml created locally but not in git = fragility gap | Jul 13 |
| `system monitor bugs (IBGW, runner auth, container API)` | Monitor probes return wrong data — IBGW pointing to wrong host, auth using wrong format | Jul 13 |
| `probe results sanity check` | A probe returning data ≠ probe returning correct data — cross-check probe output format against expected schema | Jul 13 |
| `Telegram token cross-contamination (same token in multiple containers)` | ~~RETIRED Jul 14 — Kay confirmed: single bot (`Marvless01_bot`) for both UAT+PROD by design. Message content + color header distinguishes env. NOT a drift.~~ RETIRED Jul 15 — NEW architecture: Docker Secret `telegram_bot_tokenMarvless01bot` is single source of truth. Entrypoint distributes to `/app/vault/TELEGRAM_BOT_TOKEN.env`. Check: compose files must NOT contain hardcoded `TELEGRAM_BOT_TOKEN=...` values. | Jul 15 |
| `Hardcoded tokens in compose files` | Compose files should use env vars from Docker Secrets, not hardcoded token values. After Jul 15 rebuild, any compose file containing `TELEGRAM_BOT_TOKEN=8940...` or `TELEGRAM_BOT_TOKEN=8951...` is drift. Check: `grep TELEGRAM_BOT_TOKEN= /volume1/Docker/*/docker-compose.yml` — equals sign after token name means hardcoded value, not secret reference. | Jul 15 |
| `session handoff docs have stale Bull/Bear path claims` | ~~RETIRED Jul 14 — verified UAT git has correct `\\10.8.0.10\Docker\data\` path. Only the handoff file had wrong claim. Verify handoff claims against git repo before acting.~~ | Jul 14 |
| `Docker Secrets vs standalone containers` | Docker Secrets (Swarm) only work with `docker service create`. UAT and PROD are standalone containers (`docker run`/`docker compose`). Swarm secrets cannot be read from standalone containers — `read_docker_secret.py` fails silently. Vault files on host are the actual source of truth for standalone containers. Check: `docker info | grep Swarm` — if "Swarm: inactive", secrets cannot be used by standalone containers. | Jul 16 |
| `PROD vault ephemeral — missing bind mount` | Container running but vault dir missing on NAS host = bind mount creates empty dir inside container's writable layer (ephemeral). Vault files survive container restart only if host dir exists. Check: `docker exec <container> cat /proc/1/mounts | grep vault` — if `rootfs /app/vault rootfs` appears (no host path), vault is ephemeral. Fix: create host dir + bind mount in compose. | Jul 16 |
| `Scripts in temp/ ≠ deployed fixes` | Fix scripts in /tmp or Windows `%TEMP%` dir were never executed. Scripts must be pushed to git OR actually run via SSH + verified. Detection: check if script's filesystem timestamp matches a run time, not just creation time. | Jul 16 |

| `dashboard/app.py lives in PROD repo, not UAT repo` | UAT container uses `nas:5000/trading-agent:latest` (PROD image). UAT repo has NO dashboard/. Fixes to app.py must be pushed to `trading/trading-agent` (PROD repo), not UAT repo. Bind mount at `/volume1/Docker/trading-agent-uat/dashboard/` is ephemeral — not in git. | Jul 14 |
| `bull_bear_signal_handler.py missing from UAT container` | The file that bridges Bull/Bear results → `open_position()` is not packaged in the UAT image. APPROVE path is dead in UAT. Bull/Bear runs on Windows via Hermes cron, writes to NAS mount. Container never calls signal_handler. | Jul 14 |
| `Fincept Windows paths fail in Linux` | `FINCEPT_HOST = r"C:\Program Files\FinceptTerminal\..."` hardcoded. On Linux, subprocess tries to run this as a Linux path → `can't open file '/app/C:\Program Files\...'`. Must use `sys.platform != "win32"` guard at top of `_run()`. | Jul 14 |
| `/api/scan/liveness` pushed to DEV only — UAT/PROD need separate rebuilds | Commit `dbc4c55c` pushed to `trading/trading-agent` DEV branch. DEV returns 200. UAT and PROD still return 404. Each environment needs its own image rebuild. | Jul 14 |
| `Gitea push ≠ deployed fix` | Pushing a fix to Gitea does NOT automatically deploy it. Container must be rebuilt and recreated. `docker compose down && up` required to pick up new image. `docker restart` alone does NOT re-pull the image. | Jul 14 |

**Auto-learn rule:** When doc-sheriff discovers a NEW drift pattern not in this list, it MUST:
1. Add it to this table immediately (skill patch)
2. Add it to `drift_patterns` in the sheriff's log
3. Add the check to the next audit

---

## Lessons Learned (Self-Patching Archive)

When doc-sheriff makes a mistake or discovers a gap, it writes it here AND patches the skill to prevent recurrence:

| Date | Lesson | Fix Applied to Skill |
|------|--------|---------------------|
| Jul 13 | Agent reported "done" but docs weren't updated — brief.md was 2 weeks stale | Added "any task completes → doc-sheriff updates docs" to Trigger Conditions |
| Jul 13 | pipeline-status.md had `<<<<<<< HEAD` conflict marker — agent prepended without removing conflict | Added conflict marker check to Drift Patterns |
| Jul 13 | Registry had wrong paths (`C:\Users\Kay\repos\trading-agent\`) that don't exist | Fixed all paths to `E:\Me\TradingAgent\` — added existence check to audit |
| Jul 13 | `premarket_screener.py` path mismatch not documented until it broke production | Added premarket_screener path check to Drift Patterns |
| Jul 13 | Telegram tokens burned but docs claimed they worked | Added Telegram token live probe to Audit Protocol |
| Jul 13 | `doc-sheriff` itself missed conflict markers for TWO sessions — documented as "fixed" but never actually removed | Added conflict marker grep to post-update verification checklist |
| Jul 13 | system-monitor.html bugs (IBGW localhost:4002, runner ?token=, container ?token=) caused probes to return wrong data | Added probe-result-sanity-check to post-audit verification |
| Jul 13 | Bull/Bear path fix (`\\\\10.8.0.10\\Docker\\data\\`) not reflected in brief.md — still listed as broken | Added doc cross-check: fixed issues must also update brief.md |
| Jul 14 | Both UAT and PROD containers have same Telegram token `8940612948:***` — Kay confirmed this is BY DESIGN (single bot lean setup, message content+color distinguishes env). Removed Telegram token cross-contamination from active drift patterns. |
| Jul 14 | `handoff_jul14.md` had wrong Bull/Bear path claim. Verified UAT git has correct NAS path `\\10.8.0.10\Docker\data\`. Handoff docs can contain stale/inaccurate claims — always cross-check against live git repo before acting. | Added session handoff stale-claim pattern to drift patterns. |
| Jul 14 | dashboard/app.py CRLF crash loop: assignment inside dict literal (`rows.append({..., _pj_raw = row.get(...)}))` is a SyntaxError. Python misparses it because CR char makes error location misleading. Pattern confirmed Jul 14. | Added CRLF+diet-literal bug to `dashboard/app.py repo ownership` drift pattern. |
| Jul 15 | Telegram token was fragmented across 13+ locations (compose files, Docker Secrets, vault files, Hermes .env, Mavis credentials). Root cause: no single source of truth. Fix: Docker Secret as master, entrypoint as distribution mechanism. Token update now requires only updating the Docker Secret + restarting containers. | Added new drift patterns: "Telegram token cross-contamination" updated to Docker Secret architecture, "Hardcoded tokens in compose files" added. Updated brief.md, trading-agent-ops, kay-session-learnings. |
| Jul 14 | 4 new drift patterns auto-learned and added to Drift Patterns table: dashboard/app.py PROD repo ownership, bull_bear_signal_handler missing from UAT, Fincept Windows paths in Linux, /api/scan/liveness per-env rebuild requirement. | Patch applied to Drift Patterns. |

---

## Known Document Inventory (Source of Truth for Audits)

### Ops Docs (Windows filesystem)
```
E:\Me\AI-Brain\STATUS.md                                          — sprint state, blockers, deadline
E:\Me\TradingAgent\docs\brief.md                                  — pipeline roadmap, execution, system status
E:\Me\TradingAgent\docs\pipeline-status.md                        — operational probe results (chronological)
E:\Me\TradingAgent\docs\point-of-truth.md                        — pipeline state, task owners, blockers
E:\Me\TradingAgent\docker\README.md                               — build/deploy, CI/CD, runner status
E:\Me\AI-Brain\projects\trading-agent\docs\UNIFIED_SCHEMA.html    — agent roster, system components
E:\Me\AI-Brain\projects\trading-agent\docs\orchestrator-architecture.html — agent diagram, runner status
E:\Me\AI-Brain\projects\trading-agent\docs\OPERATIONAL_OVERVIEW.html — ENV paths, DEV/UAT/PROD setup
E:\Me\AI-Brain\projects\trading-agent\docs\TECHNICAL_BACKEND.html  — pipeline flow, execution notes
E:\Me\AI-Brain\projects\trading-agent\docs\AI-Brain_MoA.md         — LLM models, agent roster
```

### Skills (Hermes agent skills)
```
C:\Users\Kay\AppData\Local\hermes\skills\operations\trading-agent-ops\SKILL.md
C:\Users\Kay\AppData\Local\hermes\skills\operations\living-documents\SKILL.md
C:\Users\Kay\AppData\Local\hermes\skills\operations\kay-session-learnings\SKILL.md
C:\Users\Kay\AppData\Local\hermes\skills\operations\nas-ssh-access\SKILL.md
C:\Users\Kay\AppData\Local\hermes\skills\agents-orchestrator\SKILL.md
```

### Docker/Infra Files (NAS + Gitea)
```
Gitea: trading/trading-agent (dev branch)  — entrypoint.py, docker/Dockerfile, scripts/
Gitea: trading/trading-agent-uat (main)    — ibkr_connector.py, docker/ (if exists)
NAS:   /volume1/Docker/trading-agent-uat/docker-compose.yml
NAS:   /volume1/Docker/PortainerCE/data/compose/10/docker-compose.yml   (PROD)
NAS:   /volume1/Docker/PortainerCE/data/compose/20/docker-compose.yml   (DEV)
NAS:   /volume1/Docker/PortainerCE/data/compose/21/docker-compose.yml   (DEV runner)
```

---

## Drift Detection — What to Check

### Container state (PROD=5050, DEV=5051, UAT=5052)
```
curl -s http://10.8.0.10:5051/api/state | python -c "import json,sys; d=json.load(sys.stdin); print(f'last_scan={d.get(\"last_scan\",\"?\")} bull_bear={len(d.get(\"bull_bear\",[]))} positions={len(d.get(\"positions\",[]))} signals={len(d.get(\"signals\",[]))}')"
```

### Runner state (Gitea API)
```
curl -s "http://10.8.0.10:3000/api/v1/repos/trading/trading-agent/actions/runners" \
  -H "Authorization: Bearer 84c70a81c60914e31cc2f269f6cd99e8591fd8cc"
```

### Telegram tokens (curl from container or direct)
```
curl -s "https://api.telegram.org/bot<TOKEN>/getMe"
```

### Docker network (Portainer API)
```
JWT=$(curl -s -X POST "http://10.8.0.10:19900/api/auth" \
  -H "Content-Type: application/json" \
  -d '{"Username":"Ai_agent_01","Password":"IFQ4TomWhQ.E8s9QC86r"}" \
  | python -c "import json,sys; print(json.load(sys.stdin)['jwt'])")

curl -s "http://10.8.0.10:19900/api/endpoints/3/docker/networks" \
  -H "Authorization: Bearer $JWT" | python -c "import json,sys; nets=json.load(sys.stdin); [print(n['Name'], n['Driver']) for n in nets]"
```

---

## HTML Doc Update Rules

AI-Brain HTML files are rendered dashboards. When updating:
- Update the relevant section with new status/date
- Update the "last updated" timestamp in the footer
- Verify: open in browser or check file modified time

Common update targets in HTML docs:
- `UNIFIED_SCHEMA.html` → agent status badges, component versions
- `orchestrator-architecture.html` → runner status (PROD/DEV/UAT labels in SVG)
- `OPERATIONAL_OVERVIEW.html` → ENV var values, port numbers, container names
- `TECHNICAL_BACKEND.html` → pipeline flow arrows, cron schedules

---

## Self-Improvement Loop (How Sheriff Gets Better)

```
Every audit cycle:
1. Probe actual state (containers, runners, Telegram, etc.)
2. Compare to what docs claim
3. Any GAP found that wasn't in drift_patterns?
   → YES: Add to drift_patterns table (skill patch)
            Add to sheriff's log → sessions[-1].lessons_learned
            Add check to next audit automatically
4. Any MISSED doc in registered_docs?
   → YES: Add to living-documents SKILL.md registry
5. Any WRONG path in registry?
   → YES: Fix in living-documents + living-documents is self-aware
6. Any doc update that FAILED (timestamp unchanged)?
   → YES: Retry immediately. If still failing, log as blocker.
7. Any subagent claiming "done" without doc update?
   → YES: Update docs anyway, log to sheriff's log → sessions[-1].lessons_learned
```

**The loop runs automatically.** Every session start, doc-sheriff reads the log, runs the checks, patches itself. No human needed to improve the system.

---

## Critical Rules (Non-Negotiable)

1. **No doc update = task not done.** If a subagent reports "done" but the docs weren't updated, Doc Sheriff must update them anyway and note the gap in kay-session-learnings.

2. **Token conservation:** Doc audits use grep/search_files, NOT full file dumps. Batch reads with offset/limit.

3. **Credential handling:** When updating docs with credentials, use abbreviated hashes (first 7 + last 4), never full tokens. Token format: `84c70a8...d8cc`.

4. **Gitea vs GitHub:** For the trading agent, Gitea is the source of truth. Any doc referencing GitHub as source of truth for Docker builds must be flagged and corrected.

5. **Brief.md is project truth.** If any other doc contradicts brief.md, brief.md wins. Update the contradicting doc to match.

6. **New files = register immediately.** Any new `.py`, `.md`, `.yml`, `.yaml`, `.html` created during a session must be added to the living-documents registry in the same session.

7. **Evidence before claims.** When auditing, probe actual state (API calls, curl) before reading docs. Compare actual vs documented, report drift.

---

## Doc Sheriff Session Report Format

When Kay asks for a doc audit or status, respond with:

```
## 📋 Doc Audit — [DATE]

| Doc | Last Updated | Current State | Drift? |
|-----|-------------|--------------|--------|
| brief.md | Jul 13 | ✅ vs probe | None |
| pipeline-status.md | Jul 11 | 🔴 vs probe | MISSING Jul 12-13 |
| trading-agent-ops | Jul 13 | ✅ | None |
| AI-Brain HTML (all) | Jul 11 | 🟡 | Need probe |
...

Action taken: [what was updated now]
Still stale: [what needs more work]
Blockers: [what requires Kay action]
```

---

## How to Run

**Passive (session start — triggered by "continue" / "status" / session open):**
```
Load skill → run Audit Protocol (Steps 1-5) → report drift + agent handoff status → await instruction
```

**Active (after task completion):**
```
Agent reports done → Sheriff updates docs in scope → verify timestamps → confirm "done"
```

**Kay-triggered audit:**
```
Load skill → full audit → detailed drift report → propose fixes → await GO
```

---

## Telegram Health Monitoring — Auto-Healing Loop

**Full reference:** `references/telegram-token-autopsy-jul16.md` — token formats, 13 location cleanup list, extraction technique (xxd hex), self-healing design.

**ops-trader health cron must probe every 15 min:**
```bash
TOKEN=$(cat /app/vault/TELEGRAM_BOT_TOKEN.env)
curl -s "https://api.telegram.org/bot${TOKEN}/getMe"
# 200 OK → silent, log
# 401     → token revoked → rotate Docker Secret + restart
# 404     → BOT DELETED (or fully invalid) → CANNOT AUTO-FIX → alert Kay via @Hendrika01_bot
```

**PROD token extraction (Docker masks stdout):**
```bash
docker exec trading-agent cat /app/vault/TELEGRAM_BOT_TOKEN.env | xxd -p | tr -d '\n'
# Then decode: python -c "print(bytes.fromhex('HEX').decode('ascii'))"
```

## Emergency Fix References

| Reference | When to Use |
|-----------|-------------|
| `references/docker-swarm-secrets-standalone-containers.md` | Swarm vs standalone containers, why Docker Secrets fail, vault file as source of truth |
| `references/telegram-token-autopsy-jul16.md` | Both tokens 404, 13 location cleanup, PROD vault ephemeral, xxd token extraction, self-healing loop design |
| `references/prod-vault-emergency-fix.md` | PROD vault missing on NAS, ephemeral vault recovery |

## Key Paths Reference (always use these exact paths)

```
# Windows docs
STATUS.md:              E:\Me\AI-Brain\STATUS.md
brief.md:               E:\Me\TradingAgent\docs\brief.md
pipeline-status.md:     E:\Me\TradingAgent\docs\pipeline-status.md
point-of-truth.md:     E:\Me\TradingAgent\docs\point-of-truth.md
Docker README:          E:\Me\TradingAgent\docker\README.md

# AI-Brain HTML
UNIFIED_SCHEMA:         E:\Me\AI-Brain\projects\trading-agent\docs\UNIFIED_SCHEMA.html
orchestrator-arch:      E:\Me\AI-Brain\projects\trading-agent\docs\orchestrator-architecture.html
ops-overview:           E:\Me\AI-Brain\projects\trading-agent\docs\OPERATIONAL_OVERVIEW.html
tech-backend:            E:\Me\AI-Brain\projects\trading-agent\docs\TECHNICAL_BACKEND.html
MoA:                     E:\Me\AI-Brain\projects\trading-agent\docs\AI-Brain_MoA.md

# Hermes skills
trading-agent-ops:      C:\Users\Kay\AppData\Local\hermes\skills\operations\trading-agent-ops\SKILL.md
living-documents:       C:\Users\Kay\AppData\Local\hermes\skills\operations\living-documents\SKILL.md
kay-session-learnings:  C:\Users\Kay\AppData\Local\hermes\skills\operations\kay-session-learnings\SKILL.md
nas-ssh-access:         C:\Users\Kay\AppData\Local\hermes\skills\operations\nas-ssh-access\SKILL.md

# Gitea
trading-agent repo:     http://10.8.0.10:3000/trading/trading-agent (dev branch)
trading-agent-uat repo: http://10.8.0.10:3000/trading/trading-agent-uat (main branch)
Gitea PAT:              84c70a8...d8cc (abbreviated)

# Docker (Portainer API base)
Portainer API:           http://10.8.0.10:19900/api
Auth:                    {"Username":"Ai_agent_01","Password":"IFQ4TomWhQ.E8s9QC86r"}
Endpoint for containers: /api/endpoints/3/docker/
```
