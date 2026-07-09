# Trading Agent Orchestrator DB Contract

## Purpose

This document defines how the Hermes orchestrator connects to the Mindgentic PostgreSQL database and interacts with the ai_memory and trading_agent schemas.

## Connection Method

Use WireGuard VPN PostgreSQL access only.

```
Host: 10.8.0.10
Port: 5432
WireGuard VPN required (interface GMTec, status Up).
```

### Environment Connection Strings

Development:
```
postgresql://ai_agent_dev:***@10.8.0.10:5432/mindgentic_dev
```

Application backend:
```
postgresql://app_backend_dev:***@10.8.0.10:5432/mindgentic_dev
```

UAT:
```
postgresql://ai_agent_uat:***@10.8.0.10:5432/mindgentic_uat
```

Application backend:
```
postgresql://app_backend_uat:***@10.8.0.10:5432/mindgentic_uat
```

Production:
```
postgresql://ai_agent_prod:***@10.8.0.10:5432/mindgentic_prod
```

Application backend:
```
postgresql://app_backend_prod:***@10.8.0.10:5432/mindgentic_prod
```

## Environment Rules

The orchestrator must always choose the correct environment first.

- dev = active development and testing
- uat = validation/staging
- prod = stable production

Rules:
1. Use dev first.
2. Promote to uat only after validation.
3. Use prod only for stable workflows.
4. Never let a dev role connect to uat or prod.
5. Never let a uat role connect to dev or prod.
6. Never let a prod role connect to dev or uat.

## Agent Registry

Known agents are stored in:

```
ai_memory.agent_registry
```

Registered logical agents:
- stakeholder (Kay — final approver)
- Richard (Pre-Market Scanner)
- Bull (Bull/Bear debate — Bull side)
- Bear (Bull/Bear debate — Bear side)
- Trader (Trade Execution Agent)
- Researcher (Market Research Agent)
- DevOps (Infrastructure Agent)
- Gitea Agent (Source Control Agent)
- EvidenceQA (QA Validation Agent)
- Hermes Agent (Orchestrator — this agent)

The orchestrator must read this table before assigning work.

## Task Table

Main task table:

```
ai_memory.tasks
```

Purpose: Stores task state for the AI workflow. Primary task system: Hermes Kanban (see below). ai_memory.tasks is the orchestration layer.

Important fields:
- id
- title
- description
- status
- assigned_agent
- created_by
- approved_by
- approved_at
- completed_by
- completed_by_role
- completed_at
- kanban_id
- kanban_url
- priority
- environment
- metadata
- created_at
- updated_at

### Allowed Task Statuses

- backlog
- ready
- doing
- review
- done

Kanban mapping:
- backlog = Backlog
- ready = Ready
- doing = Doing
- review = Review
- done = Done

### Done Rule

Only the stakeholder role may move a task to done.

Database constraint: status = done requires completed_by_role = stakeholder

Agents must not attempt to set status = done unless completed_by_role = stakeholder.

### Creating Tasks

When the orchestrator creates a task, it must insert into:

```
ai_memory.tasks
```

Minimum required fields:
- title
- status
- created_by
- environment
- metadata

Recommended insert pattern:

```sql
INSERT INTO ai_memory.tasks (
    title,
    description,
    status,
    assigned_agent,
    created_by,
    priority,
    environment,
    metadata
)
VALUES (
    '<task title>',
    '<task description>',
    'backlog',
    '<agent name or null>',
    '<creator name>',
    'normal',
    '<dev|uat|prod>',
    '{}'::jsonb
)
RETURNING id;
```

### Updating Tasks

Agents may update:
- description
- status
- assigned_agent
- approved_by
- approved_at
- completed_by
- completed_by_role
- completed_at
- kanban_id
- kanban_url
- priority
- metadata

Status updates must use normal UPDATE statements on ai_memory.tasks.

The database automatically updates: updated_at
The database automatically logs status changes to: ai_memory.task_status_history

### Status Change Audit

Audit table:

```
ai_memory.task_status_history
```

Purpose: Records task status transitions.

Fields:
- task_id
- old_status
- new_status
- changed_by
- changed_by_role
- changed_at
- metadata

## Reasoning and Session Logging

Agent sessions are stored in:

```
ai_memory.agent_sessions
```

Reasoning/log output is stored in:

```
ai_memory.reasoning_logs
```

### Session Creation Pattern

```sql
INSERT INTO ai_memory.agent_sessions (
    agent_name,
    metadata
)
VALUES (
    '<agent name>',
    '{}'::jsonb
)
RETURNING id;
```

### Reasoning Log Pattern

```sql
INSERT INTO ai_memory.reasoning_logs (
    session_id,
    agent_name,
    role,
    input,
    output,
    tags,
    extra
)
VALUES (
    '<session uuid>',
    '<agent name>',
    '<role>',
    '<input>',
    '<output>',
    ARRAY['tag1','tag2'],
    '{}'::jsonb
);
```

### Trading-Specific Logging

For trading pipeline logging:
```sql
INSERT INTO ai_memory.reasoning_logs (
    session_id, agent_name, role, input, output, tags, extra
)
VALUES (
    '<session uuid>',
    'BullBear',
    'debate',
    json_build_object('signal', '<symbol>', 'price', '<price>')::text,
    json_build_object('verdict', '<APPROVE|SKIP>', 'conviction', <score>, 'bull_args', '<args>', 'bear_args', '<args>')::text,
    ARRAY['trading','bull_bear','<symbol>'],
    '{"environment": "dev"}'::jsonb
);
```

## Hermes Kanban Contract
Hermes Kanban is the primary task system. `hermes kanban` CLI manages tasks.

Commands:
- `hermes kanban ls` — list all tasks
- `hermes kanban show` — show board state
- `hermes kanban create --title "..." --status ready --assignee <agent>` — create task
- `hermes kanban complete <id>` — mark task complete
- `hermes kanban comment <id> --text "..."` — add comment

Columns: backlog → ready → doing → review → done

ai_memory.tasks fields for Kanban integration:
- kanban_id
- kanban_url
- status
- title
- description
- assigned_agent
- metadata

## Source of Truth Rule

Hermes Kanban is the primary task system.
PostgreSQL ai_memory.tasks is the orchestration layer for agent coordination.

Conflict rules:
- done status must never be auto-applied unless completed_by_role = stakeholder.
- stakeholder decisions override agent decisions.
- agent updates may move tasks backlog → ready → doing → review.
- only stakeholder may move review → done.

## Required Orchestrator Behavior

The orchestrator must:

1. Verify WireGuard VPN is active before connecting.
2. Load environment config (MINDGENTIC_ENV).
3. Connect using the matching environment role.
4. Read ai_memory.agent_registry.
5. Create or resume an agent_sessions row.
6. Read tasks from ai_memory.tasks.
7. Assign tasks by updating assigned_agent.
8. Move tasks through allowed statuses.
9. Write reasoning logs to ai_memory.reasoning_logs.
10. Never bypass the stakeholder-only Done rule.
11. Never attempt direct LAN connection (172.20.50.193) from VPN.
12. Use WireGuard VPN PostgreSQL access only (10.8.0.10:5432).

## Trading Pipeline Integration

The orchestrator coordinates the trading pipeline:

1. Richard generates signals → ai_memory.reasoning_logs (tag: trading_signal)
2. Bull/Bear runs debate → ai_memory.reasoning_logs (tag: bull_bear_debate)
3. Trader executes → positions.json (local file) + ai_memory.reasoning_logs (tag: trade_execution)
4. All pipeline stages logged with session_id, agent_name, role, tags

## Pending Build Items

- Orchestrator integration (in progress)
- Credential vault integration (DPAPI vault in use)
- Backup/restore runbook (not built)
- Monitoring/health checks (not built)
