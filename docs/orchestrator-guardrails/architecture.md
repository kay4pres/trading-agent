# System Architecture — Trading Agent Project

## 1. Purpose

This document describes the technical architecture of Kay's Trading Agent development environment.

It defines:
- Components (tools, models, infra)
- Data flow
- Trust boundaries
- On-prem database strategy
- Kanban integration
- How agents must respect this architecture

Kay is the Stakeholder and final approver for all architectural changes.

---

## 2. High-Level Stack Overview

The stack consists of:

- **Hermes Agent** — local orchestrator and pipeline manager
- **OpenCode GO + external LLMs** — paid and API-based models (MiniMax, etc.)
- **Mavis / Local LLMs** — on-prem reasoning via IPC socket
- **Richard** — Pre-Market Scanner (Warrior Trading criteria)
- **Bull / Bear** — LLM Debate Agent (conviction scoring)
- **Trader** — Trade Execution Agent (Alpaca API)
- **Researcher** — Market Research Agent
- **DevOps** — Infrastructure Agent (Docker, NAS, CI/CD)
- **Gitea Agent** — Source Control Agent
- **EvidenceQA** — QA Validation Agent
- **NAS** — on-prem infrastructure (database + Docker services)
- **WireGuard VPN** — secure tunnel to NAS resources
- **Hermes Kanban** — multi-agent work queue (SQLite-backed, `hermes kanban` CLI). Source of truth for tasks.
- **Git repository** — source of truth for code and docs

All agents must treat this architecture as the baseline and may not assume cloud-only setups.

---

## 3. Components

### 3.1 Orchestration

- **Hermes Agent**
  - Runs locally on Kay's machine.
  - Orchestrates specialist agents (Richard, Bull/Bear, Trader, etc.).
  - Uses OpenCode GO + external LLMs for reasoning.
  - Uses working directory `E:\Me\TradingAgent\`.

- **Skills and Agents**
  - Richard, Bull/Bear, Trader, Researcher, DevOps, Gitea Agent, EvidenceQA are installed and available.
  - They read `E:\Me\TradingAgent\docs\` for workflow, roles, prompts, and architecture.

### 3.2 Reasoning Layer

- **Local LLMs (Mavis / Big Pickle Free)**
  - Provide large-context reasoning on-prem.
  - Used for multi-file understanding and code generation.
  - Must obey Smarter Way rules and Stakeholder governance.

- **OpenCode GO + external LLMs**
  - Provide higher-capacity or specialized reasoning.
  - Accessed via API or paid endpoints.
  - Selected per task based on need (performance, cost, latency).

- **Reasoning Engine Layer**
  - Abstracts over local + external models.
  - Chooses the best model for each task.
  - Never fabricates facts; uses deterministic evidence when required.

### 3.3 NAS & On-Prem Database

- **NAS**
  - Hosts Docker services (PostgreSQL, Gitea, Portainer).
  - Runs the primary on-prem database.
  - Access via WireGuard VPN (10.8.0.10).

- **Database**
  - Runs inside Docker on the NAS.
  - Acts as the main data store for AI memory and trading data.
  - Access controlled via WireGuard tunnel.
  - No direct exposure to the public internet.

- **Connection**
  ```
  postgresql://<user>:***@10.8.0.10:5432/<database>
  WireGuard VPN required. LAN IP (172.20.50.193) is not accessible from VPN subnet.
  ```

### 3.4 Kanban Board (Hermes Kanban)

- **Hermes Kanban** — managed via `hermes kanban` CLI (SQLite-backed, multi-agent).
- Provides a visual Kanban board: Backlog → Ready → Doing → Review → Done.
- `hermes kanban ls` shows all tasks. `hermes kanban show` shows board state.
- ai_memory.tasks remains the orchestration layer; Hermes Kanban is the execution layer.

- **Governance**
  - Agents may create and update tasks.
  - Only Kay may approve and move tasks to "Done".

---

## 4. Data Flow

### 4.1 Trading Pipeline Flow

1. **Richard** generates premarket/intraday signals → `signals_live.json`
2. **Bull/Bear** reads signals → runs LLM debate → writes `bull_bear_results.json`
3. **live_event_loop** polls Bull/Bear results → calls **Trader** on APPROVE
4. **Trader** opens position via Alpaca → writes `positions.json`
5. **Trader** monitors exits → Telegram notifications
6. **ai_memory** receives: reasoning_logs, session_reflections, tasks

### 4.2 Development Flow

1. Kay interacts with **Hermes Agent**.
2. Hermes invokes specialist agents based on task type.
3. Agents read project context from `E:\Me\TradingAgent\docs\`.
4. Code and plans are written to the Git repo.
5. Application code connects to the **NAS database** via **WireGuard**.
5. Kanban tasks are generated and tracked via Hermes Kanban.
7. EvidenceQA validates before PASS.

---

## 5. Architectural Principles

1. **On-Prem First**
   - Prefer NAS and local models over cloud-only solutions.
   - Keep data under Kay's control.

2. **Model-Agnostic Reasoning**
   - Do not bind the architecture to a single LLM.
   - Use local, paid, and API models as needed.

3. **Smarter Way Governance**
   - All agent interactions with Kay must follow Smarter Way rules.
   - Architecture changes must be explained in clear, short steps.

4. **Agile + Kanban**
   - Work is organized into Sprints and Kanban flow.
   - Architecture tasks appear on the Kanban board.

5. **No Secrets in Code or Docs**
   - Secrets are never printed, logged, or stored in plain text.
   - Credentials are managed via DPAPI vault.

---

## 6. How Agents Must Use This Architecture

- **Richard**
  - Must scan using Warrior Trading criteria only.
  - Must not execute trades.

- **Bull/Bear**
  - Must run full LLM debate on Richard signals.
  - Must output conviction score and APPROVE/SKIP.
  - Must not call Trader directly.

- **Trader**
  - Must receive APPROVE from Bull/Bear before opening.
  - Must manage all exits (target, stop, 2-min rule).
  - Must log all decisions to ai_memory.

- **DevOps**
  - Must plan features and infra in line with: NAS DB, WireGuard, Docker, Hermes Kanban.
  - Must not assume cloud-hosted DB by default.

- **Reasoning Engine Layer**
  - Must respect: trust boundaries, no-secrets rule, Smarter Way communication, Stakeholder approval for major changes.
