# Tool Stack Baseline Report — 2026-07-20

**Owner:** Hermes (Mavis Code)
**Status:** Tools cloned, smoke tests in progress, baseline measurements pending

---

## What was cloned (Day 0)

All 3 GitHub tools cloned to `C:\Users\Kay\repos\trading-agent\tools\`:

| Tool | Source | Path | Size estimate | Integration target |
|------|--------|------|---------------|-------------------|
| **Ponytail** | https://github.com/DietrichGebert/ponytail | `tools/ponytail/` | ~50MB | Mavis Code skill |
| **Headroom** | https://github.com/headroomlabs-ai/headroom | `tools/headroom/` | ~500MB (Rust core + Python + TypeScript) | LLM-call proxy at 127.0.0.1:8787 |
| **Agency-agents** | https://github.com/msitarzewski/agency-agents | `tools/agency-agents/` | ~5MB (200+ .md files) | Hermes skill catalog |
| **Gstack** | local @ `G:\Projects\Gstack\gstack\` | (not yet in tools/) | ~1GB | Mavis Code workflow wrapper |

Gitea clones are available; I can mirror these to `trading/tools-*` repos on `http://10.8.0.10:3000` if desired for source-of-truth backup.

---

## Tool-by-tool quick read

### 1. Ponytail — "Lazy senior dev, says nothing, writes one line"

**What it is:** A code-reduction skill (markdown prompt + agent plugins). Replaces 50+ lines of over-built code with 1-3 lines of native/essential code.

**Measured impact (from their benchmarks):**
- LOC: **-54%** (94% on over-built components)
- Tokens: **-22%**
- Cost: **-20%**
- Time: **-27%**
- Safety: **100%** (keeps all guards; only reduces verbosity)

**Integrations:** 20+ agents (`.claude-plugin`, `.codex-plugin`, `.cursor`, `.openclaw`, `.hermes`, etc.)

**Use for trading-agent:**
- Audit `trading_agent/*.py` for over-built components
- Slim `dashboard/app.py` (62KB, 1700+ lines) → probably 50% smaller
- Reduce `live_event_loop.py` complexity if there's ceremony

**Install path:** `cd tools/ponytail && npm install` (Node-based, also Python)

**Risk:** Could over-simplify our domain logic if blindly applied. Need manual review of every change.

### 2. Headroom — "The context compression layer for AI agents"

**What it is:** Production-grade token compression layer. Three modes:
- **Library** — `compress(messages)` inline
- **Proxy** — `headroom proxy --port 8787`, zero code changes, wraps any LLM call
- **MCP server** — `headroom_compress`, `headroom_retrieve`, `headroom_stats` for any MCP client
- **Agent wrap** — `headroom wrap claude|codex|hermes|copilot|...` in one command
- **Cross-agent memory** — shared across Claude, Codex, Gemini, Grok
- **`headroom learn`** — mines failed sessions, writes to `AGENTS.md` / `CLAUDE.md`
- **Output token reduction** — trims what the model writes back, not just input

**Measured impact:**
- JSON data: **60-95% fewer tokens**
- Coding agents: **15-20% fewer tokens**

**Has dedicated Hermes integration** (`headroom/headroom-agent-hooks/hermes/`).

**Use for trading-agent:**
- Wrap all our LLM calls (MiniMax, OpenAI, OpenCode, OpenRouter) through the proxy
- Connect `bull_bear_runner.py`, `scan_market_bull_bear.py`, `bull_bear_debate.py` to the proxy
- Use `headroom learn` to auto-capture agent mistakes and write to our `AGENTS.md`

**Install path:** `cd tools/headroom && pip install -e .` (or use Docker image)

**Architecture:** Rust core (RTK) + Python wrapper + TypeScript SDK + MCP server. Heavy infra, but it's battle-tested (500+ tests).

### 3. Agency-agents — "A complete AI agency at your fingertips"

**What it is:** 200+ pre-built specialist agent `.md` files, each with:
- Identity & personality
- Core mission & workflows
- Technical deliverables with code examples
- Success metrics & communication style

**Categories (sample):**
- Engineering: `engineering-ai-engineer`, `engineering-devops-automator`, `engineering-prompt-engineer`, `engineering-rag-pipeline-engineer`, `engineering-multi-agent-systems-architect`
- Finance: `finance-bookkeeper-controller`, `finance-financial-analyst`, `finance-investment-researcher`, `finance-tax-strategist`
- Strategy: `business-strategist`, `change-management-consultant`
- Specialized: `agents-orchestrator`, `codebase-archaeologist`, `workflow-architect`, `model-qa`
- Testing: `testing-evidence-collector`, `testing-reality-checker`, `testing-test-automation-engineer`, `testing-performance-benchmarker`
- Security: `security-architect`, `security-appsec-engineer`, `security-incident-responder`

**Install scripts** for: Claude Code, Cursor, Codex, Gemini CLI, OpenCode, OpenClaw, **Hermes**, Antigravity, Aider, Windsurf, Kimi Code, Osaurus, Mistral Vibe, GitHub Copilot

**Use for trading-agent:**
- Pick 5-10 agents that fill gaps in our existing specialist pool
- `engineering-multi-agent-systems-architect` — for our DTD-replica architecture design
- `finance-financial-analyst` / `finance-investment-researcher` — for our trading domain
- `testing-evidence-collector` / `testing-reality-checker` — for our QA loop
- `security-architect` / `security-appsec-engineer` — for our credential handling
- `workflow-architect` — for our 3-layer Hermes workflow

**Install command:** `./scripts/install.sh --tool hermes --division engineering,security,testing,specialized,finance`

### 4. Gstack — Virtual engineering team wrapper for Mavis Code

**What it is:** A framework that turns Mavis Code into a virtual engineering team. Adds slash commands:
- `/office-hours` — describe what you're building, get engineering review
- `/plan-ceo-review` — review feature ideas before implementing
- `/review` — review any branch with changes

**What I found at `G:\Projects\Gstack\gstack\`:**
- ~200K lines of TypeScript / JavaScript
- 100+ test files (`skill-e2e-*.test.ts`, `gstack-*.test.ts`)
- Skills, specialists, references, templates subdirs
- SKILL.md files up to 163KB each
- `agent-sdk-runner.ts`, `gbrain.ts` (memory/sync), `gen-skill-docs.ts`, `eval-store.ts`, `preflight-agent-sdk.ts`, `review-army.ts`

**Status:** Cloned locally, not yet mirrored to Gitea. **Researcher dispatch needed** to extract:
- How `/office-hours`, `/plan-ceo-review`, `/review` work (semantics, expected inputs/outputs)
- How to integrate with our existing Hermes orchestrator role
- What `gbrain.ts` provides (memory layer for cross-agent context)
- What `preflight-agent-sdk.ts` does (sounds like our pre-flight checks)

**Estimated effort:** 1-2 days focused pass

---

## Day 1-3 plan (in progress)

### Day 1 — Smoke test (TODAY, in progress)
- [x] Clone all 4 tools ✅
- [ ] Smoke test Ponytail: `npm install` + run audit on a small test file
- [ ] Smoke test Headroom: `pip install` + start proxy on 127.0.0.1:8787 + send 1 test request
- [ ] Smoke test agency-agents install: `./scripts/install.sh --tool hermes --division engineering`
- [ ] Dispatch Researcher: Gstack internals extraction (1-2 day focus pass)

### Day 2 — Baseline measurements
- [ ] Ponytail audit on `trading_agent/*.py` → measure LOC reduction (target: ≥20% to integrate)
- [ ] Headroom proxy on real Bull/Bear debate call → measure token reduction (target: ≥15% to integrate)
- [ ] agency-agents install → check what gets picked up by our Hermes

### Day 3 — Decision report
- For each tool: integrate / partial / skip
- Wire integrated tools into our workflow
- Commit changes to Gitea `dev` branch
- Update kanban with status

---

## Risk register

| Risk | Mitigation |
|------|------------|
| Headroom proxy breaks our existing LLM calls | Smoke test on 1 known prompt first; revert if quality drops |
| Ponytail over-simplifies domain logic | Manual review of every change; never auto-apply |
| Agency-agents catalog is overwhelming | Pick 5-10 high-value ones, ignore rest |
| Gstack internals take longer than expected | Time-box to 1-2 days; if no clear path, treat as reference docs |

---

## Open questions (need Kay's call)

1. **Gitea mirror:** mirror these 3 GitHub tools to `http://10.8.0.10:3000` repos (so Gitea stays source of truth)? Or keep GitHub as primary?
2. **Live trading risk during integration:** Headroom proxy wraps all LLM calls. Should we put it in front of LIVE trading calls, or only paper/Bull-Bear debate calls first?
3. **Ponytail scope:** apply to all `trading_agent/*.py`, or only new code we write from now on?
4. **Agency-agents count:** install 5-10 specialist agents, or go bigger and install 30+?
5. **Gstack priority:** if Researcher finds Gstack is mostly mature but complex, do we adopt it (replace our manual Proof+Verifier), or treat as reference?

---

## What's NOT in scope

- Replacing our existing `trading_agent/*.py` (refactor only, not rewrite)
- Adding new LLM providers beyond MiniMax/OpenAI/OpenCode/OpenRouter
- Changing our DTD-replica architecture (that's Phase 1, after baseline)
- Touching live trading code paths (paper-only changes)
