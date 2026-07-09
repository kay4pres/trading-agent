# Trading Agent Build Backlog

## Purpose

This document defines the implementation backlog for the Trading Agent on-prem AI workflow.

The database foundation exists in `mindgentic_dev`.
The next phase is integrating the Trading Agent into the existing ai_memory schema.

## Completed Foundation

- PostgreSQL runs on NAS @ 10.8.0.10:5432 (WireGuard)
- pgAdmin connects through LAN
- Databases exist:
  - mindgentic_dev
  - mindgentic_uat
  - mindgentic_prod
- Schemas exist:
  - ai_memory
  - app_data
- AI memory tables exist:
  - agent_sessions
  - reasoning_logs
  - reflections
  - tasks
  - task_status_history
  - agent_registry
- Environment-specific roles exist:
  - ai_agent_dev
  - ai_agent_uat
  - ai_agent_prod
  - app_backend_dev
  - app_backend_uat
  - app_backend_prod

## Trading Agent Integration Build Items

### 1. Credential Retrieval

Status: in-progress

Goal:
- Define how orchestrator retrieves DB credentials for trading-agent context.
- Use DPAPI vault (already in use by trading-agent).
- Never store passwords in docs, code, logs, prompts, task metadata, or reasoning logs.

Output:
- Secret retrieval interface for ai_memory writes
- Environment-specific credential loading (dev/uat/prod)

### 2. Orchestrator DB Connector

Status: not started

Goal:
- Connect to PostgreSQL using correct environment role.
- Validate host (10.8.0.10), port (5432), database, role, and environment before connecting.
- Fail closed on mismatch.

Required environments:
- dev (mindgentic_dev + ai_agent_dev)
- uat (mindgentic_uat + ai_agent_uat)
- prod (mindgentic_prod + ai_agent_prod)

Output:
- Reusable DB connection module for trading-agent context

### 3. Task Read/Write Module

Status: not started

Goal:
- Read tasks from `ai_memory.tasks`
- Create tasks
- Assign tasks to trading agents
- Update statuses
- Enforce workflow rules from orchestrator side
- Rely on DB constraint for stakeholder-only Done protection

Allowed statuses:
- backlog
- ready
- doing
- review
- done

Output:
- Task service/module for orchestrator

### 4. Agent Session Logging

Status: not started

Goal:
- Create rows in `ai_memory.agent_sessions`
- Write logs to `ai_memory.reasoning_logs`
- Link task operations to agent sessions where possible
- Log trading decisions (signal, debate, entry, exit)

Output:
- Session/logging module for trading pipeline

### 5. Hermes Kanban Sync

Status: not started

Goal:
- Sync PostgreSQL task state with Hermes Kanban board.
- PostgreSQL remains agent source of truth.
- Hermes Kanban remains human-visible board.

Fields to sync:
- title
- description
- status
- assigned_agent
- kanban_id
- hermes_kanban_url
- metadata

Output:
- Hermes Kanban sync module

### 6. Trading Signal Integration

Status: not started

Goal:
- Connect Richard signals to Bull/Bear pipeline.
- Connect Bull/Bear results to Trader execution.
- Log all signals to ai_memory.reasoning_logs.

Output:
- Signal routing module connecting Richard → Bull/Bear → Trader

### 7. Backup and Restore

Status: not started

Goal:
- Define backup method for trading-agent data in PostgreSQL.
- Define restore testing procedure.
- Include dev/uat/prod separately.

Output:
- Backup/restore runbook

### 8. Monitoring and Health Checks

Status: not started

Goal:
- Check PostgreSQL availability.
- Check role connectivity.
- Check table availability.
- Check Hermes Kanban availability.
- Check Docker container status.

Output:
- Health-check script or runbook

## Build Order

Recommended order:

1. Orchestrator DB connector (10.8.0.10:5432 via WireGuard)
2. Task read/write module
3. Agent session logging
4. Trading signal integration
5. Hermes Kanban sync
6. Backup/restore
7. Monitoring/health checks

## Rule

Do not build Hermes Kanban sync before the orchestrator can reliably read/write `ai_memory.tasks`.
