# gstack-mavis-port

Mavis Code adaptations of gstack skills. Stripped of bash preamble, CLI binaries, `~/.gstack/` state, and Greptile/GBrain/Codex. Mavis-native agents and tools used instead.

## Source

`G:\Projects\Gstack\gstack\` (1.3 GB, NOT mirrored to Gitea because too large)

## Adapted skills

| Skill | Source | Purpose | Size |
|-------|--------|---------|------|
| `plan-ceo-review.md` | `G:\Projects\Gstack\gstack\plan-ceo-review\SKILL.md` (2223 lines) | CEO/founder-mode plan review. 4 modes: SCOPE EXPANSION, SELECTIVE EXPANSION, HOLD SCOPE, SCOPE REDUCTION. 11 review sections. | 17,955 bytes |
| `review.md` | `G:\Projects\Gstack\gstack\review\SKILL.md` (1788 lines) | Pre-landing PR review. 8 specialist domains. AUTO-FIX/ASK classification. Adversarial probe. | 13,412 bytes |

## What was stripped vs kept

**Stripped:**
- bash preamble (`gstack-config`, telemetry, lake intro, vendoring, repo-mode)
- `AskUserQuestion` plan-mode gates → Mavis `ask_user` instead
- CLI `gstack-*` binary calls
- `~/.gstack/` file paths
- Greptile API → `coder` agent + read tool
- Codex adversarial → `general` agent with adversarial prompt
- `gh` CLI → Gitea HTTP API

**Kept:**
- 4-mode philosophy + prime directives
- 11 review sections
- "Boil the Lake" completeness principle
- AUTO-FIX / ASK / DEFER / BLOCK classification
- Adversarial probe pattern
- 8 specialist domains (mapped to Mavis agents)

## Mavis agent mapping

| gstack specialist | Mavis agent | Trigger words |
|-------------------|-------------|---------------|
| testing | `verifier` | test coverage, flaky test, missing test |
| security | `security-architect` | secret, leak, auth, vulnerability |
| red-team | `general` (adversarial prompt) | break, exploit, attack |
| performance | `coder` (perf prompt) | slow, latency, throughput |
| maintainability | `coder` (review prompt) | cleanup, refactor, simplify |
| data-migration | `coder` (data prompt) | schema, migration, format change |
| api-contract | `coder` (API prompt) | endpoint, RPC, schema change |
| design-checklist | `general` (UX prompt) | UI, dashboard, empty state |

## How to use

```python
# In Mavis Code session:
# 1. Read the skill
read("tools/gstack-mavis-port/plan-ceo-review.md")
# or
read("tools/gstack-mavis-port/review.md")

# 2. Follow the workflow
# 3. For specialist review, dispatch via task tool
task(prompt="[specialist prompt with diff content]", agent_name="verifier", run_in_background=False)
```

## What was NOT ported

- `/office-hours` — too dependent on `gstack-brain`, gbrain context. Replaced by inline design discussion in Hermes sessions.
- `/qa`, `/investigate` — generic enough to handle directly without a skill wrapper.
- `/ship`, `/land-and-deploy` — depends on gstack-specific deploy hooks. Replaced by Gitea Agent + `gitea-mirror.ps1` for the trading-agent project.
- `/autoplan` — too dependent on `/office-hours` upstream.

## Versioning

| Port date | Source version | Author |
|-----------|----------------|--------|
| 2026-07-20 | gstack v1.0.0 (plan-ceo-review, review) | Hermes (Mavis Code) |

Re-port when source upgrades: `diff` against new `G:\Projects\Gstack\gstack\<skill>\SKILL.md` and merge relevant additions.
