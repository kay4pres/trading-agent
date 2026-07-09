# Mindgentic Environment Variables and Credential Handling — Trading Agent Project

## Purpose

This document defines how the Trading Agent orchestrator should handle database connection settings and credentials.

The goal is to avoid hardcoded passwords and support a corporate-grade approval model for credential retrieval.

## Core Principle

Connection details may be documented.

Secrets must not be stored in project documentation, source code, Git, logs, prompts, or agent memory.

Passwords must be retrieved from an approved secret store or password vault.

## Connection Method

Use WireGuard VPN PostgreSQL access.

```
Host: 10.8.0.10
Port: 5432
WireGuard VPN required.
```

## Environment Databases

| Environment | Database |
|-------------|----------|
| dev | mindgentic_dev |
| uat | mindgentic_uat |
| prod | mindgentic_prod |

## Technical Roles

AI roles:

| Environment | Role |
|-------------|------|
| dev | ai_agent_dev |
| uat | ai_agent_uat |
| prod | ai_agent_prod |

Application backend roles:

| Environment | Role |
|-------------|------|
| dev | app_backend_dev |
| uat | app_backend_uat |
| prod | app_backend_prod |

Admin GUI role:

| Role | Access |
|------|--------|
| pgadmin_user | dev, uat, prod |

## Required Environment Variables

## Shared Settings

```
MINDGENTIC_DB_HOST=10.8.0.10
MINDGENTIC_DB_PORT=5432
MINDGENTIC_ENV=dev|uat|prod
```

## Dev

```
MINDGENTIC_DEV_DB_NAME=mindgentic_dev
MINDGENTIC_DEV_AI_USER=ai_agent_dev
MINDGENTIC_DEV_APP_USER=app_backend_dev
```

## UAT

```
MINDGENTIC_UAT_DB_NAME=mindgentic_uat
MINDGENTIC_UAT_AI_USER=ai_agent_uat
MINDGENTIC_UAT_APP_USER=app_backend_uat
```

## Prod

```
MINDGENTIC_PROD_DB_NAME=mindgentic_prod
MINDGENTIC_PROD_AI_USER=ai_agent_prod
MINDGENTIC_PROD_APP_USER=app_backend_prod
```

## Secret Variables

Passwords must not be committed.

If a local .env file is used during development, it must be excluded from Git.

Suggested secret variable names:

```
MINDGENTIC_DEV_AI_PASSWORD
MINDGENTIC_UAT_AI_PASSWORD
MINDGENTIC_PROD_AI_PASSWORD

MINDGENTIC_DEV_APP_PASSWORD
MINDGENTIC_UAT_APP_PASSWORD
MINDGENTIC_PROD_APP_PASSWORD
```

## Current Decision

Current setup uses:

- WireGuard VPN PostgreSQL access (10.8.0.10:5432)
- Environment-specific roles
- Environment-specific passwords
- DPAPI vault for credential storage (E:\Me\TradingAgent\vault\)
- No reverse SSH tunnel dependency

## Stakeholder Approval Model

Credential retrieval should follow an approval model.

Required rule: The orchestrator must not retrieve production credentials without stakeholder approval.

## Environment Approval Rules

- Dev: Dev credentials may be retrieved automatically if local policy allows.
- UAT: UAT credentials may require stakeholder approval depending on risk.
- Prod: Prod credentials always require stakeholder approval.

## Secret Handling Rules for Orchestrator

The orchestrator must:

- Never hardcode passwords.
- Never print passwords.
- Never write passwords into logs.
- Never store passwords in ai_memory.reasoning_logs.
- Never store passwords in ai_memory.tasks.metadata.
- Never expose passwords to subagents unless explicitly required.
- Never use prod credentials in dev or uat.
- Never reuse dev password for uat or prod.
- Never reuse uat password for prod.
- Never connect to prod by default.
- Never fall back to prod after dev failure.
- Never store credentials in project docs.
- Never store credentials in Git.
- Never store credentials in task metadata.
- Never store credentials in reasoning logs.

## Connection String Construction

The orchestrator may construct connection strings at runtime only after retrieving the password.

Template:

```
postgresql://<user>:***@10.8.0.10:5432/<database>
```

Dev AI example:

```
postgresql://ai_agent_dev:***@10.8.0.10:5432/mindgentic_dev
```

UAT AI example:

```
postgresql://ai_agent_uat:***@10.8.0.10:5432/mindgentic_uat
```

Prod AI example:

```
postgresql://ai_agent_prod:***@10.8.0.10:5432/mindgentic_prod
```

## Runtime Environment Selection

The orchestrator must select the environment explicitly.

Required value:

```
MINDGENTIC_ENV=dev
MINDGENTIC_ENV=uat
MINDGENTIC_ENV=prod
```

The orchestrator must fail closed if MINDGENTIC_ENV is missing or invalid.

## Fail-Closed Rules

The orchestrator must fail closed when:

- environment is missing
- environment is invalid
- matching DB name is missing
- matching username is missing
- password cannot be retrieved
- stakeholder approval is required but not granted
- role does not match environment
- connection target does not match expected NAS host
- WireGuard VPN is not active

## Required Validation Before Connecting

Before opening a database connection, the orchestrator must verify:

1. WireGuard VPN is active (GMTec interface Up).
2. Selected environment matches database name.
3. Selected environment matches role name.
4. Host equals 10.8.0.10 (WireGuard IP).
5. Port equals 5432.
6. Password came from DPAPI vault (approved secret source).
7. Prod access has stakeholder approval.

## Prohibited Behavior

The orchestrator must not:

- use postgres superuser for normal work
- use pgadmin_user for automated agent work
- reuse dev password for uat or prod
- reuse uat password for prod
- connect to prod by default
- fall back to prod after dev failure
- store credentials in project docs
- store credentials in Git
- store credentials in task metadata
- store credentials in reasoning logs
