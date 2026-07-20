# /review — Mavis Code port

> **Source:** `G:\Projects\Gstack\gstack\review\SKILL.md` (v1.0.0, 1788 lines)
> **Port date:** 2026-07-20
> **What this is:** Pre-landing PR review. Analyzes diff against base branch for SQL safety, LLM trust boundary violations, conditional side effects, structural issues, security, performance, maintainability, and test coverage gaps.
> **What was stripped:** bash preamble, `gstack-*` CLI binaries, `~/.gstack/` state, Greptile, GBrain, Codex. Mavis-native agents used for specialist review.
> **What was kept:** Step 0-5 workflow, 8 specialist domains, AUTO-FIX/ASK classification, adversarial probe pattern, scope-drift detection.

---

## When to invoke

Use this skill when:
- "review this PR", "code review", "pre-landing review"
- "check my diff", "is this ready to merge?"
- About to land code changes (Hermes mode)
- After significant edits, before commit

For trading-agent project: every change that touches `trading_agent/`, `scripts/`, `dashboard/`, or `entrypoint.py` should be reviewed before push.

## 3-stage workflow

```
  Step 0-3: Setup (platform, branch, diff, checklist)
      ↓
  Step 4: Critical pass (core review — you)
      ↓
  Step 4.5: Specialist army (parallel subagent dispatch)
      ↓
  Step 5: Fix-First Review (AUTO-FIX / ASK / DEFER)
      ↓
  Step 5.7: Adversarial probe (always-on)
      ↓
  Output: Verdict (PASS / FAIL / CHANGES_REQUESTED)
```

---

## Step 0: Detect platform + base branch

```powershell
git remote get-url origin 2>$null

# If GitHub → use gh
# If Gitea (self-hosted) → use gitea CLI or HTTP API
# If unknown → use git-native only

# Get base branch
git symbolic-ref refs/remotes/origin/HEAD 2>$null | sed 's|refs/remotes/origin/||'
# Fallback: main / master
```

For trading-agent:
- Primary remote: Gitea `http://10.8.0.10:3000/kay/tools-*` and `trading/trading-agent` (mirror)
- Branch model: `dev` (alpha) | `main` (stable)
- Use Gitea HTTP API for PR operations, not GitHub CLI

## Step 1: Check branch + scope drift

```powershell
git rev-parse --abbrev-ref HEAD
git log --oneline -10
git diff <base> --stat
```

**Scope drift detection:** Compare diff stats against expected scope. If touched files > expected, flag.

## Step 2: Read the checklist

```powershell
# Read project checklist
Get-Content tools\gstack-mavis-port\checklist.md -ErrorAction SilentlyContinue
```

For trading-agent, the working checklist lives at:
- `docs/point-of-truth.md` — project invariants
- `.hermes/plans/*.md` — current plans
- `tools/DAY-*-END-OF-DAY-*.md` — recent handoffs

## Step 3: Get the diff

```powershell
git fetch origin
git diff <base>...HEAD --stat
git diff <base>...HEAD > /tmp/diff.patch
```

Read the full diff. For trading-agent, also check:
- `git status` for uncommitted changes
- `data/` directory changes (should be in `.gitignore`)
- `vault/*.enc` (HARD: should NEVER be in diff)

## Step 4: Critical pass (core review — you do this inline)

Look for these patterns:

### 4.1 SQL Safety
- Raw SQL strings? Use parameterized queries.
- String concatenation into SQL? Injection risk.
- `f"... WHERE {var} ..."`? Extract to a constant or param.

### 4.2 LLM Trust Boundary
- User input → LLM prompt? Sanitize.
- LLM output → executed code / SQL / shell? NEVER trust without validation.
- LLM-controlled fields flowing into privileged operations? Flag.

### 4.3 Conditional Side Effects
```python
# BAD — silent failure on condition
if config.get('feature_x'):
    do_something_dangerous()  # what if feature_x is None? missing? wrong type?

# GOOD — explicit
if config.get('feature_x') is True:
    do_something_dangerous()
```

### 4.4 Error Handling
- Bare `except:` or `except Exception:`? Smell — name the exception.
- `except: pass`? Silent failure. Flag as critical.
- `try/except` around I/O without retry/backoff? Brittle.
- New codepaths without error handling? Flag.

### 4.5 Secrets
- Hardcoded API keys / passwords / tokens? CRITICAL — never in code.
- `.env` files in diff? Should be `.gitignore`'d.
- Credentials in logs? `print(f"key={api_key}")`? CRITICAL.
- Vault file paths: must be `E:\Me\TradingAgent\vault/*.enc` (DPAPI), not plaintext.

### 4.6 Path Safety
- Hardcoded `E:\Me\TradingAgent\` paths in Docker code? Bug — use `TRADING_DATA_DIR` env var.
- Hardcoded `C:\` paths? Brittle.
- `os.path.join` with user input? Path traversal risk.

### 4.7 Type/Import Hygiene
- Unused imports? Remove.
- Missing imports? Add.
- Type mismatches? Fix.
- Circular imports? Refactor.

### 4.8 Naming + Comments
- Misleading names? (`def get_data():` that actually deletes?)
- Magic numbers? Name them.
- Non-obvious logic without comments? Add.

## Step 4.5: Specialist Army (parallel subagent dispatch)

For non-trivial diffs (>100 lines or new feature), dispatch specialists in parallel via `task` tool.

**8 specialist domains → Mavis agent mapping:**

| Domain | gstack specialist | Mavis agent | When to dispatch |
|--------|-------------------|-------------|------------------|
| **testing** | `specialists/testing.md` | `verifier` agent | Any new logic, no tests, flaky tests |
| **security** | `specialists/security.md` | `security-architect` agent | New endpoints, auth, secrets, user input |
| **red-team** | `specialists/red-team.md` | `general` agent + adversarial prompt | Critical code paths (live trading, position mgmt) |
| **performance** | `specialists/performance.md` | `coder` agent + perf prompt | Hot paths (cron, scanner, WebSocket consumer) |
| **maintainability** | `specialists/maintainability.md` | `coder` agent + review prompt | All non-trivial changes |
| **data-migration** | `specialists/data-migration.md` | `coder` agent + data prompt | Schema changes, format migrations |
| **api-contract** | `specialists/api-contract.md` | `coder` agent + API prompt | New/changed HTTP/WS/RPC endpoints |
| **design-checklist** | `design-checklist.md` | `general` agent + UX prompt | UI/dashboard changes |

### Dispatch pattern

```python
# Spawn in parallel
tasks = [
    task(prompt="""You are the testing specialist. Review this diff for:
- Unit test coverage gaps (per new function/method)
- Integration test gaps (per new cross-module flow)
- E2E test gaps (per new user-facing flow)
- Adversarial probes: race conditions, null inputs, malformed data, stale state
[DIFF CONTENT HERE]
Return: numbered findings with file:line, severity (CRITICAL/HIGH/MED/LOW), fix suggestion.
""", agent_name="verifier", run_in_background=False),
    
    task(prompt="""You are the security specialist. Review this diff for:
- Authn/authz on new endpoints
- Input validation, output encoding
- Secrets in code/logs/git
- Dependency vulnerabilities
- Threat model for new flows
- DPAPI vault usage (not plain env vars)
[DIFF CONTENT HERE]
Return: numbered findings with file:line, severity, fix suggestion.
""", agent_name="security-architect", run_in_background=False),
    
    # ... 6 more specialists
]
```

For small diffs (<100 lines, single function), skip the army. Step 4 alone suffices.

## Step 5: Fix-First Review

### 5.0. Cross-review finding dedup

Merge findings from Step 4 + specialist army. Same finding from multiple sources = 1 finding, highest severity wins.

### 5a. Classify each finding

| Class | Action | Examples |
|-------|--------|----------|
| **AUTO-FIX** | Apply immediately, no question | Unused imports, missing type hints, obvious typos, hardcoded paths in Docker code (use TRADING_DATA_DIR), missing `if not quote: continue` guards |
| **ASK** | Ask user via `ask_user` | Scope changes, new deps, breaking API changes, security tradeoffs |
| **DEFER** | Add to TODOS.md, don't fix now | Future improvements, nice-to-haves, non-blocking cleanup |
| **BLOCK** | Cannot proceed | Critical security flaw, data loss risk, breaking change without migration |

### 5b. Auto-fix all AUTO-FIX items

Apply immediately. Verify the fix doesn't break the build. Use `coder` agent for non-trivial auto-fixes.

### 5c. Batch-ask about ASK items

Group all ASK items into a single `ask_user` call (multi-select). Don't ask 1-by-1.

For each ASK item, give:
- Description
- Effort (S/M/L)
- Risk (Low/Med/High)
- Recommendation + WHY

### 5d. Apply user-approved fixes

After Kay approves fixes, apply them. Re-run build/test.

## Step 5.5: TODOS cross-reference

For each finding, check if it relates to an existing TODO. If so, link. If not, add to `tools/TODO-REVIEW.md`.

## Step 5.6: Documentation staleness

- New API endpoint? Update `docs/API.md` or `README.md`.
- New config var? Update `docs/configuration.md` or `.env.example`.
- Changed behavior? Update `docs/CHANGELOG.md`.
- New file/folder? Update `docs/STRUCTURE.md`.

For trading-agent:
- New cron? Update `docs/cron-schedule.md` (or add).
- New agent? Update `docs/AGENTS-ROSTER.md`.
- New tool/skill? Update `tools/INDEX.md`.

## Step 5.7: Adversarial probe (always-on)

For every review, run at least one adversarial probe:

**Code probes:**
- Boundary values (0, -1, MAX_INT, empty string, very long string)
- Concurrency (race conditions, deadlocks, idempotency)
- Orphan operations (what if a request fails midway through a multi-step flow?)
- Malformed input (truncated JSON, wrong types, missing fields)

**Document probes:**
- Internal contradictions (Section 2 says X, Section 5 says not-X)
- Claims without evidence
- Numbers that don't add up
- Missing edge cases

**Cross-session / cross-agent probes (Mavis-specific):**
- "Agent A is foregrounded; rotate Agent B; A must not be yanked over"
- "Team plan owner rotates mid-cycle; new session must inherit plan"
- "Session fetches downstream resource; fetch fails; pre-fetch invariants must still hold"
- "Concurrent cron jobs writing to same file — race?"

For trading-agent specifically:
- "Premarket cron at 4 AM ET runs while scan-market from yesterday still active"
- "Two signals for same symbol arrive within 100ms — dedup race"
- "Bull/Bear subprocess fails — does live_event_loop still get signals?"
- "Position update during exit execution — consistent state?"

## Step 5.8: Persist + Verdict

Write the review result to:
- For PRs: comment on Gitea/GitHub PR
- For local changes: write to `tools/REVIEW-<date>-<feature>.md`

### Output format

```markdown
## Review Report

**Date:** YYYY-MM-DD HH:MM
**Reviewer:** Hermes (Mavis Code) + specialist army
**Diff:** <base>...HEAD
**Files changed:** N
**Lines:** +X / -Y

### Summary
- Critical: N | High: N | Medium: N | Low: N
- Auto-fixed: N
- User-approved: N
- Deferred: N
- Blocked: N

### Critical findings
1. [SECURITY] `file.py:42` — hardcoded API key. Fix: read from `vault/<name>_api_key.enc`.

### High findings
1. [BUG] `file.py:88` — bare `except Exception` swallows all errors. Fix: name the exception.

### Auto-applied fixes
1. Removed unused import `os` from `trading_agent/scanner.py`.
2. Added `if not quote: continue` guard in `intraday_scanner.py:124`.

### User-approved fixes
1. [Approved] Replace `os.environ['KEY']` with `vault_reader.get('key')`.

### Deferred
1. Add proper retry/backoff to `bull_bear_runner.py` — TODOS.md.

### Adversarial probes
- PROBE: Two signals for AAPL within 100ms — does dedup handle it?
  - RESULT: PASS — `signal_dedup_open_positions` skill checks `positions.json` first.

### Verdict
- **PASS** — safe to merge
- **CHANGES_REQUESTED** — fixes applied, re-review needed
- **FAIL** — critical blocker, do not merge
```

### Verdict rules

- **PASS:** 0 critical, 0 high unresolved. All medium auto-fixed or user-approved.
- **CHANGES_REQUESTED:** 0 critical, but high findings require user decision.
- **FAIL:** Any critical finding unresolved. Any blocked finding. Any security/data-loss risk.

## Mavis Code integration

| gstack | Mavis Code |
|--------|------------|
| `~/.claude/skills/gstack/bin/*` | `bash` tool, `mavis` tool |
| Greptile API | `coder` agent + read tool |
| Codex adversarial | `general` agent with adversarial prompt |
| `~/.gstack/projects/<slug>/` | `tools/gstack-mavis-port/` for adapted skills, `tools/REVIEW-*.md` for output |
| GitHub `gh` CLI | Gitea HTTP API via `bash` curl, or `gitea-agent` subagent |
| `gstack-timeline-log` | Append to `tools/REVIEW-LOG.md` |

For long-running reviews (>10 min), spawn `verifier` agent with full diff context and let it run in background.

## Important Rules

1. **Never fabricate file:line citations.** If you claim `file.py:42` has an issue, READ the file first.
2. **Never PASS without an adversarial probe.** At least 1 probe, with result.
3. **Never silently auto-fix high/critical.** AUTO-FIX is for clear, mechanical fixes only.
4. **Never skip the dedup step.** Multiple specialists will find the same thing.
5. **Never review without reading the full diff first.** Skim ≠ review.
6. **Always cross-check against existing patterns in the codebase.** New code should match conventions.
7. **Always check for secrets in the diff.** `git diff | grep -E "key|secret|token|password"` is your first reflex.
8. **Always verify after auto-fix.** Run build + tests.

## Completion Status Protocol

When finishing, report:
- **DONE** — review complete, verdict issued, fixes applied.
- **DONE_WITH_CONCERNS** — review complete, but unresolved findings remain.
- **BLOCKED** — cannot complete review (e.g., diff too large, missing context).
- **NEEDS_CONTEXT** — Kay input needed for ASK items.

Format: `STATUS`, `REASON`, `ATTEMPTED`, `RECOMMENDATION`.
