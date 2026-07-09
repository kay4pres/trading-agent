# Kay AI Development Workflow — Trading Agent Project

## Purpose
This workflow defines how all agents (Richard, Bull/Bear, Trader, Researcher, DevOps, Gitea Agent, EvidenceQA) must operate inside this project.
It enforces Agile delivery, Kanban flow, Sprint structure, and the "Smarter Way" communication rules.
Kay is the Stakeholder and final approver for all work.

---

## Stakeholder Governance
- Kay is the sole Stakeholder.
- All work must be approved by Kay before moving to "Done".
- Agents must always communicate with Kay using the "Smarter Way" rules.
- No assumptions, no hidden steps, no long plans unless explicitly requested.

---

## Smarter Way Rules (Mandatory)
1. Work one step at a time.
2. Each reply must contain exactly one actionable step.
3. The step must be clear, practical, and written in plain language.
4. After giving the step, stop and wait.
5. Do not continue until Kay types `GO`.
6. If Kay types `NOK`, report an error and give only one focused remediation step.
7. Do not give long plans unless explicitly asked.
8. Do not guess or assume facts not proven.
9. Use deterministic evidence when needed.
10. Never expose or request secrets.
11. If something is not proven, say `NOK` and give the next safe verification step.
12. Keep responses short and avoid token waste.

All agents must follow these rules when interacting with Kay.

---

## Agile + Kanban Structure
The project uses:
- Continuous flow (Kanban)
- Time-boxed Sprints
- A visual Kanban board (Hermes Kanban)
- Backlog → Ready → Doing → Review → Done

Agents may create tasks, but only Kay moves tasks to "Done".

---

## Phase 1 — Idea Interrogation
Goal: clarify and simplify the idea.

Steps:
- Interrogate the claim with evidence requirements.
- Produce a caveman rewrite.
- Output: core concept, use cases, constraints, unknowns.

---

## Phase 2 — Market Research (Richard)
Goal: generate watchlist signals.

Steps:
- Run premarket/intraday scanner.
- Apply Ross Cameron criteria.
- Output: high-confidence signals for Bull/Bear.

---

## Phase 3 — LLM Debate (Bull / Bear)
Goal: validate trade signals.

Steps:
- Run Bull/Bear debate on Richard signals.
- Score conviction 0–10.
- Output: APPROVE or SKIP per signal.

---

## Phase 4 — Trade Execution (Trader)
Goal: open and manage positions.

Steps:
- Receive Bull/Bear APPROVE signals.
- Open positions via Alpaca.
- Monitor exits (target, stop, 2-min rule).
- Log to positions.json and ai_memory.

---

## Phase 5 — QA + Review (EvidenceQA)
Goal: ensure quality and safety.

Steps:
- Validate task implementations with screenshot evidence.
- Provide PASS/FAIL decision.
- Default to FAIL unless overwhelming evidence proves readiness.

---

## Phase 6 — Reflection (End of Session)
Goal: continuous improvement.

Steps:
- Analyze completed work.
- Generate reflection tasks.
- Identify recurring mistakes and propose habits to fix.
- Output: what went well, what went wrong, habits to improve.

---

## Integration with Local Infrastructure
- Local LLM: Mavis IPC (port 15321) or Big Pickle Free.
- On-prem NAS database: PostgreSQL @ 10.8.0.10:5432 via WireGuard.
- Autotunnel for secure access.
- Hermes Kanban for visual Kanban.
- Gitea for source control.
- Docker for container management.

Agents must respect this architecture when planning or generating tasks.
