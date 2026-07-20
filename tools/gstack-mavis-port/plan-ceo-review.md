# /plan-ceo-review — Mavis Code port

> **Source:** `G:\Projects\Gstack\gstack\plan-ceo-review\SKILL.md` (v1.0.0, 2223 lines)
> **Port date:** 2026-07-20
> **What this is:** CEO/founder-mode plan review. Rethink the problem, find the 10-star product, challenge premises, expand scope when it creates a better product. 4 modes.
> **What was stripped:** bash preamble (gstack-config, telemetry, lake intro, vendoring, repo-mode), AskUserQuestion plan-mode gates, CLI `gstack-*` binary calls, `~/.gstack/` file paths, Mavis-native replacements used instead.
> **What was kept:** the 4-mode philosophy, prime directives, 11 review sections, the "Boil the Lake" principle, mode-specific analysis flow.

---

## When to invoke

Use this skill when Kay says:
- "think bigger", "expand scope", "strategy review"
- "rethink this plan", "is this ambitious enough?"
- "review the architecture" / "is this the right approach?"
- "what's the 10-star version?"

For trading-agent project context: every architectural decision needs a course citation `[C1.ChXX.PX]` or marked `[INFERRED — Kay sign-off]`. Surface un-cited decisions as findings.

## 4 modes

| Mode | Posture | Use when |
|------|---------|----------|
| **SCOPE EXPANSION** | Build a cathedral. Push scope UP. Recommend enthusiastically. | Greenfield, "go big", user says ambitious |
| **SELECTIVE EXPANSION** | Hold scope + cherry-pick expansions individually. Neutral. | Feature enhancement, iteration on existing system |
| **HOLD SCOPE** | Maximum rigor on the existing plan. No expansions. | Bug fix, refactor, hotfix |
| **SCOPE REDUCTION** | Surgeon mode. Strip to MVP. Ruthless. | Plan touches >15 files, overbuilt, wrong-headed |

**Critical rule:** User is 100% in control. Every scope change is explicit opt-in via `ask_user` (Mavis native tool). Once mode is selected, commit to it — do not silently drift.

**Boil the Lake:** AI compresses implementation 10-100x. Prefer complete over shortcut. "Ship the shortcut" is legacy thinking. When the user can have A) full ~150 LOC or B) 90% ~80 LOC for 70 extra lines = minutes of compute, ALWAYS prefer A.

---

## Step 0: Pre-review

### 0.0. Pre-review system audit

Run before doing anything else. This is the context you need to review intelligently.

```powershell
# Recent history
git log --oneline -30

# What's already changed
git diff <base> --stat

# TODOs / hacks in scope
grep -r "TODO\|FIXME\|HACK\|XXX" -l --exclude-dir=node_modules --exclude-dir=.git .

# Recently touched files
git log --since=30.days --name-only --format="" | Sort-Object -Descending | Group-Object | Select-Object Count,Name | Select-Object -First 20
```

Read:
- `docs/point-of-truth.md` (if exists — Kay's project invariants)
- `docs/AgentsOrchestrator Agent Personality.md` (Hermes role/persona)
- Any existing architecture docs in `docs/`
- `.hermes/plans/*.md` (project plans)
- `tools/DAY-*-END-OF-DAY-*.md` (recent handoffs)

### 0A. Premise Challenge
1. Is this the right problem to solve? Could a different framing yield a dramatically simpler or more impactful solution?
2. What is the actual user/business outcome? Is the plan the most direct path, or solving a proxy problem?
3. What would happen if we did nothing? Real pain or hypothetical?
4. Does every decision have a course citation `[C1.ChXX.PX]` or `[INFERRED — Kay sign-off]`? If not, flag the un-cited ones.

### 0B. Existing Code Leverage
Map every sub-problem to existing code. Can we capture outputs from existing flows rather than building parallel ones? Is this rebuilding anything? If yes, explain why rebuild > refactor.

### 0C. Dream State Mapping
Describe the ideal end state 12 months from now. Does this plan move toward or away from that state?

```
  CURRENT STATE       THIS PLAN         12-MONTH IDEAL
  [describe]   --->   [delta]    --->   [target]
```

### 0C-bis. Implementation Alternatives (MANDATORY)

Before mode selection, produce 2-3 distinct approaches.

For each:
```
APPROACH A: [Name]
  Summary: [1-2 sentences]
  Effort:  [S/M/L/XL]  (human-team scale; CC compresses 10-20x)
  Risk:    [Low/Med/High]
  Pros:    [2-3 bullets]
  Cons:    [2-3 bullets]
  Reuses:  [existing code/patterns leveraged]
```

Rules:
- At least 2 approaches required. 3 preferred for non-trivial plans.
- One = minimal viable (fewest files, smallest diff).
- One = ideal architecture (best long-term trajectory).
- **These have equal weight.** Don't default to minimal just because smaller.

**STOP.** Use `ask_user` ONCE per approach decision. Do NOT batch. Recommend + WHY. Do NOT proceed to 0D/0F until Kay responds.

### 0D. Mode-Specific Analysis

**For SCOPE EXPANSION** — run all three, then opt-in ceremony:
1. **10x check:** What's the version 10x more ambitious for 2x effort? Concrete.
2. **Platonic ideal:** If the best engineer had unlimited time + perfect taste, what would this look like? Start from experience, not architecture.
3. **Delight opportunities:** Adjacent 30-min improvements where user thinks "oh nice, they thought of that." List at least 5.
4. **Expansion opt-in ceremony:** Describe vision first. Then concrete scope proposals. Each proposal = own `ask_user`. Options: A) Add to this plan B) Defer to TODOS.md C) Skip. Recommend enthusiastically. Accepted → plan scope. Rejected → "NOT in scope."

**For SELECTIVE EXPANSION** — HOLD SCOPE first, then surface expansions:
1. **Complexity check:** >8 files or >2 new classes/services = smell. Same goal with fewer moving parts?
2. **Minimum set:** What can be deferred without blocking the core?
3. **Expansion scan** (candidates, NOT added yet):
   - 10x check
   - Delight opportunities (5+)
   - Platform potential: would expansion turn this into infra other features build on?
4. **Cherry-pick ceremony:** Each expansion = individual `ask_user`. Neutral recommendation. Options: A) Add B) Defer to TODOS.md C) Skip. If >8 candidates, present top 5-6.

**For HOLD SCOPE** — run this:
1. Complexity check (same as above).
2. Minimum set.

**For SCOPE REDUCTION** — run this:
1. **Ruthless cut:** Absolute minimum that ships value. Everything else deferred. No exceptions.
2. **What can be follow-up PR?** Separate "must ship together" from "nice to ship together."

### 0E. Temporal Interrogation (EXPANSION, SELECTIVE EXPANSION, HOLD modes)

Think ahead to implementation:
```
  HOUR 1 (foundations):     What does the implementer need to know?
  HOUR 2-3 (core logic):   What ambiguities will they hit?
  HOUR 4-5 (integration):  What will surprise them?
  HOUR 6+ (polish/tests):  What will they wish they'd planned for?
```

NOTE: human-team hours. With CC + Mavis, 6h human compresses to ~30-60 min. Always present both scales.

Surface these as questions NOW, not "figure it out later."

### 0F. Mode Selection

Present 4 options via `ask_user`. Each option gets:
- Mode name + posture
- Effort (S/M/L)
- Risk (Low/Med/High)
- Recommendation with reason

Context-dependent defaults:
- Greenfield feature → default EXPANSION
- Feature enhancement → default SELECTIVE EXPANSION
- Bug fix / hotfix → default HOLD SCOPE
- Refactor → default HOLD SCOPE
- Plan touching >15 files → suggest REDUCTION
- User says "go big" / "ambitious" / "cathedral" → EXPANSION, no question
- User says "hold scope but tempt me" → SELECTIVE EXPANSION, no question

After mode is selected, confirm which implementation approach (0C-bis) applies under the chosen mode. EXPANSION may favor ideal architecture; REDUCTION may favor minimal viable.

Once selected, commit fully. Do not silently drift.

**STOP.** `ask_user` ONCE. Recommend + WHY.

---

## 11 Review Sections (after scope + mode agreed)

**Anti-skip rule:** Never condense or skip any section regardless of plan type. If a section has zero findings, say "No issues found" — but evaluate it.

**Anti-shortcut clause:** Plan file is the OUTPUT of interactive review, not a substitute. If you have ANY non-trivial finding, the path goes THROUGH `ask_user`. Zero findings in every section is the only path that bypasses `ask_user`.

### Section 1: Architecture Review

Evaluate and diagram:
- Overall system design + component boundaries. **Draw the dependency graph.**
- **Data flow — all four paths** for every new flow:
  - Happy path (data flows correctly)
  - Nil path (input missing — what happens?)
  - Empty path (input present but empty — what happens?)
  - Error path (upstream fails — what happens?)
- **State machines** — ASCII diagram for every new stateful object. Include impossible/invalid transitions.
- Coupling concerns — what components are now coupled that weren't? Justified?
- Scaling — what breaks first at 10x? 100x?
- Single points of failure — map them.
- **Security architecture** — auth boundaries, data access patterns, API surfaces. For each new endpoint: who can call, what they get, what they can change.
- Production failure scenarios — for each new integration, describe one realistic failure (timeout, cascade, data corruption, auth failure) and whether plan accounts.
- Rollback posture — git revert? Feature flag? DB rollback? How long?

Required: full system architecture ASCII diagram showing new components + relationships.

For trading-agent project specifically:
- Does the data plane avoid hardcoded paths? (PM-Agent has a known bug here.)
- Are credentials read from DPAPI vault, not env vars? (`E:\Me\TradingAgent\vault/*.enc`)
- Is the Bull/Bear pipeline using inline fallback (LLM key in vault)?
- Does the live execution respect 10% daily loss limit + multi-position 1-3 + 4 AM ET premarket?

### Section 2: Error & Rescue Map

This is the section that catches silent failures. NOT optional.

For every new method/service/codepath that can fail, fill in:

```
  METHOD/CODEPATH          | WHAT CAN GO WRONG           | EXCEPTION CLASS
  -------------------------|-----------------------------|-----------------
  ExampleService#call      | API timeout                 | TimeoutError
                           | API returns 429             | RateLimitError
                           | API returns malformed JSON  | JSONParseError
                           | DB pool exhausted           | ConnectionPoolExhausted
                           | Record not found            | RecordNotFound
  -------------------------|-----------------------------|-----------------

  EXCEPTION CLASS              | RESCUED?  | RESCUE ACTION          | USER SEES
  -----------------------------|-----------|------------------------|----------
  TimeoutError                 | Y         | Retry 2x, then raise   | "Service unavailable"
  RateLimitError               | Y         | Backoff 30s, then raise| "Rate limited"
  ...
```

Catch-all `except Exception` is a code smell. Call it out.

For trading-agent: every cron pipeline, every WebSocket consumer, every Telegram/alpaca/IBKR call needs this.

### Section 3: Test Plan Review

- Unit tests for each new function?
- Integration tests for each new cross-module flow?
- E2E tests for each user-facing flow?
- Manual/acceptance tests for each entry point?
- **Adversarial probes** — what could break this? Race conditions, null inputs, malformed data, stale state, network partition, clock skew.

For trading-agent: backtest replay with historical data; paper trading with sim broker; live with €500 → €2K phased.

### Section 4: Observability & Monitoring

- New dashboards? First-class deliverable, not afterthought.
- New alerts? What fires, when, who pages?
- New logs? What fields, what level, retention?
- New traces? What spans?
- **Runbook entries** for each new failure mode.

For trading-agent: every cron writes `data/<pipeline>.log` with timestamps. PM-Agent polls `/api/state` every 30 min. Dead-man-switch: if `last_scan` > 5 min stale, alert.

### Section 5: Security Review

- New attack surface?
- Authn/authz on every new endpoint?
- Input validation, output encoding?
- Secrets in code/logs/git? (HARD RULE: never in chat, never in logs.)
- Dependency vulnerabilities?
- Threat model for new flows?

For trading-agent: delegate to **security-architect** agent via `task` tool with full context.

### Section 6: Performance & Cost

- Latency: P50, P95, P99 targets?
- Throughput: ops/sec, records/sec?
- Cost: per-request, per-day, per-month (API calls, LLM tokens, storage)?
- Memory / CPU / disk usage at steady state and peak?

For trading-agent: LLM token cost is the dominant cost. Bull/Bear debate = 4 LLM calls per signal. 5-10 signals/day = 20-40 calls = ~$0.30-1.00/month at MiniMax pricing.

### Section 7: Deployment & Rollout

- Deploy order: which component first, which second?
- Backward compat: can we ship without downtime?
- Feature flags: what can we toggle off?
- Migrations: schema, data, format versions.
- **Canary / phased rollout?** What % at each step, what triggers promotion/rollback?

For trading-agent: paper → €500 → €2K phased. 10% daily loss limit. Auto-trade with 21:00 Berlin P&L digest.

### Section 8: Documentation

- New READMEs, ADRs, runbooks?
- API contracts: OpenAPI / JSON schema?
- Inline comments for non-obvious logic?
- ADRs (Architecture Decision Records) for non-trivial choices?
- Living docs that update with the system?

For trading-agent: `docs/ARCHITECTURE_v1.0.md` (this skill's output), `tools/DAY-N-END-OF-DAY-*.md` handoffs, ADRs in `docs/adr/`.

### Section 9: Migration / Backwards Compat

- If replacing existing system, how do we cut over?
- Old callers: where do they redirect?
- Old data: keep or migrate?
- Old configs: forward-compat shim?
- What if migration fails midway? Rollback procedure?

For trading-agent: the TRADING_AGENT_ARCHITECTURE_v0.1 → v1.0 migration IS this whole exercise.

### Section 10: Maintenance & Extensibility

- Will the next engineer understand this in 6 months?
- What tribal knowledge is locked in the implementer's head?
- Can a new dev add a new scanner in 1 day?
- Are patterns consistent with the rest of the codebase?
- Are there hidden coupling points? (module A breaks if module B changes X)

For trading-agent: the **Ponytail persona** ("lazy senior dev, no unrequested abstractions, no new deps, deletion over addition") is the maintenance philosophy.

### Section 11: UX/UI Review (if DESIGN_SCOPE)

- Empty states? (zero results, first-time user, error)
- Loading states? (skeleton, spinner, optimistic UI)
- Error states? (network, validation, server)
- Edge cases? (47-char name, slow connection, double-click, navigate-away-mid-action, back button, stale data)
- Hierarchy as service — what does the user see first, second, third?
- Subtraction default — every UI element earns its pixels or gets cut.

For trading-agent dashboard: `http://10.8.0.10:5050` Flask app. Empty states on `last_scan` missing.

---

## Priority Hierarchy Under Context Pressure

Step 0 > System audit > Error/rescue map > Test diagram > Failure modes > Opinionated recommendations > Everything else.

Never skip Step 0, system audit, error/rescue map, or failure modes. These are highest-leverage outputs.

## Mavis Code integration

- `ask_user` = Mavis native tool (replaces AskUserQuestion)
- `bash` = PowerShell (Windows) or bash (Linux) — non-interactive, no stdin prompts
- For long-running deep work: spawn `verifier` agent via `task` tool for QA
- For specialist review: spawn `coder`, `general`, `security-architect`, `devops-automator`, `gitea-agent` as needed
- For 10x check or specialist perspective: optionally spawn `agency-agents` specialist (e.g., `engineering-multi-agent-systems-architect`)

## Prime Directives

1. **Zero silent failures.** Every failure mode visible — to system, team, user.
2. **Every error has a name.** Catch-all `except Exception` is a code smell.
3. **Data flows have shadow paths.** Happy + nil + empty + error. Trace all 4.
4. **Interactions have edge cases.** Double-click, navigate-away, slow connection, stale state, back button.
5. **Observability is scope, not afterthought.** New dashboards/alerts/runbooks are first-class.
6. **Diagrams are mandatory.** ASCII art for every new data flow, state machine, processing pipeline.
7. **Everything deferred must be written down.** TODOS.md or it doesn't exist.
8. **Optimize for 6-month future, not just today.** If plan solves today but creates next-quarter nightmare, say so.
9. **You have permission to say "scrap it and do this instead."** If there's a fundamentally better approach, table it.

## Engineering Preferences

- DRY is important — flag repetition aggressively.
- Well-tested code is non-negotiable.
- "Engineered enough" — not under (fragile/hacky) and not over (premature abstraction).
- More edge cases, not fewer.
- Explicit over clever.
- Right-sized diff: smallest diff that cleanly expresses change. If foundation is broken, say "scrap it."
- Observability not optional.
- Security not optional.
- Deployments not atomic — plan for partial states, rollbacks, feature flags.
- ASCII diagrams in code comments for complex designs.
- Stale diagrams are worse than none — diagram maintenance is part of the change.

## Output

Final output is a revised plan file with:
- Vision (10x check + platonic ideal in EXPANSION mode)
- Scope decisions table (ACCEPTED / DEFERRED / SKIPPED per proposal)
- 11 review sections, each with findings or "No issues found"
- Course citations on every architectural decision (`[C1.ChXX.PX]` or `[INFERRED — Kay sign-off]`)
- Risk register
- Open questions
- Recommended next step (delegate to which Mavis agent)

Write to `docs/<feature>-design.md` or `tools/PLAN-<feature>-REVIEW.md`.

## Completion Status Protocol

When finishing, report status:
- **DONE** — completed with evidence.
- **DONE_WITH_CONCERNS** — completed, but list concerns.
- **BLOCKED** — cannot proceed; state blocker and what tried.
- **NEEDS_CONTEXT** — missing info; state exactly what needed.

Escalate after 3 failed attempts, uncertain security-sensitive changes, or unverifiable scope.

Format: `STATUS`, `REASON`, `ATTEMPTED`, `RECOMMENDATION`.
