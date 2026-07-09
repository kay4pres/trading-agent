# Trading Agent Database Handover

## Purpose

This document describes the PostgreSQL, pgAdmin, database, schema, role, table, Kanban, and access model for the Trading Agent project.

## Important Companion Documents

The following documents are part of this handover and must be read together:
- `orchestrator-db-contract.md` — connection and interaction contract
- `mindgentic_env_variables.md` — environment variable definitions
- `mindgentic_build_backlog.md` — implementation backlog

## Executive Summary

The Trading Agent project shares the same on-prem NAS infrastructure as the Mindgentic project:

- Windows PC (WireGuard: 10.8.0.2) → WireGuard tunnel → NAS (10.8.0.10) → PostgreSQL :5432
- Both projects use the same PostgreSQL instance but different databases
- WireGuard VPN is required for access from outside the LAN subnet

## Current Infrastructure

### Windows PC (This Machine)

WireGuard IP: 10.8.0.2/24
VPN status: Active (GMTec interface Up)

### NAS

WireGuard IP: 10.8.0.10
LAN IP: 172.20.50.193 (not accessible from WireGuard subnet)

### PostgreSQL

PostgreSQL runs on the NAS in Docker.

Connection endpoint:
```
Host: 10.8.0.10
Port: 5432
WireGuard VPN required.
```

### Docker Containers

Known running containers on NAS:
- postgres
- pgadmin-new
- PortainerCE

Known services:
- PostgreSQL: host port 5432
- pgAdmin: host port 5430
- Portainer: host ports 19900 / 19943 / 19800

## Network and Connectivity

### Working Path
```
Windows PC (WireGuard: 10.8.0.2) → NAS WireGuard (10.8.0.10:5432) → PostgreSQL
```

### Not Accessible from VPN
```
172.20.50.193:5432 — LAN-only IP, not reachable over WireGuard
```

## PostgreSQL Environment Setup

Two separate PostgreSQL strategies:

### ai_memory (Shared — Mindgentic)
- mindgentic_dev / mindgentic_uat / mindgentic_prod
- Contains: ai_memory schema (agent_registry, tasks, reasoning_logs, agent_sessions, reflections)
- DevOps/Orchestrator access

### trading_agent (Standalone — Option B)
- trading_agent_dev / trading_agent_uat / trading_agent_prod
- Contains: positions, signals, bull_bear_debates (Trading Agent-specific data)
- Docker Secrets for credentials

Three environment databases exist:

| Environment | Database | AI Agent Role | App Backend Role |
|-------------|----------|---------------|------------------|
| dev | mindgentic_dev | ai_agent_dev | app_backend_dev |
| uat | mindgentic_uat | ai_agent_uat | app_backend_uat |
| prod | mindgentic_prod | ai_agent_prod | app_backend_prod |

Purpose:
- dev = build and test
- uat = validation/staging
- prod = stable production

Each database has these schemas:
- ai_memory
- app_data

## ai_memory Tables

Each environment has these AI memory tables:

- agent_sessions
- reasoning_logs
- reflections
- tasks
- task_status_history
- agent_registry

## Role Model

The project uses environment-specific database roles.

### AI Roles
- ai_agent_dev → mindgentic_dev only
- ai_agent_uat → mindgentic_uat only
- ai_agent_prod → mindgentic_prod only

### Application Backend Roles
- app_backend_dev → mindgentic_dev only
- app_backend_uat → mindgentic_uat only
- app_backend_prod → mindgentic_prod only

### Admin GUI Role
- pgadmin_user → dev, uat, prod

## Access Model

Expected access:
- ai_agent_dev → mindgentic_dev only
- ai_agent_uat → mindgentic_uat only
- ai_agent_prod → mindgentic_prod only

Design rule: The orchestrator controls which logical agent performs work. The database controls technical access.

## Agent Registry

Registered logical agents in ai_memory.agent_registry:
- stakeholder (Kay — sole approver)
- Richard (Pre-Market Scanner)
- Bull (Bull/Bear debate — Bull side)
- Bear (Bull/Bear debate — Bear side)
- Trader (Trade Execution Agent)
- Researcher (Market Research Agent)
- DevOps (Infrastructure Agent)
- Gitea Agent (Source Control Agent)
- EvidenceQA (QA Validation Agent)

## Kanban and Task Workflow

Hermes Kanban is the primary task system (`hermes kanban` CLI).
ai_memory.tasks is the agent source of truth.

Workflow:
backlog → ready → doing → review → done

Only stakeholder role may move a task to done.

Database constraint: status = done requires completed_by_role = stakeholder

## Bootstrap Tasks

Bootstrap tasks are inserted into mindgentic_dev.ai_memory.tasks.

They include tasks for both Mindgentic and Trading Agent projects.

## Credential Handling Decision

Passwords must not be hardcoded.

Passwords must not be stored in:
- project documentation
- source code
- Git
- logs
- prompts
- ai_memory.reasoning_logs
- ai_memory.tasks.metadata
- any shared board or doc

Current approach: DPAPI vault at E:\\Me\\TradingAgent\\vault\\
Docker Secrets for container credentials (UAT/PROD).

## What Is Finished

Completed:
- PostgreSQL container exists
- pgAdmin container exists
- pgAdmin connects to PostgreSQL
- WireGuard PostgreSQL connectivity works (10.8.0.10:5432)
- dev / uat / prod databases exist
- ai_memory / app_data schemas exist
- AI memory tables exist
- agent_registry exists
- task status history exists
- updated_at trigger exists
- environment-specific roles exist
- bootstrap tasks inserted into dev

## What Is Not Finished

Not finished:
- Trading Agent orchestrator DB connector
- Trading Agent task read/write module
- Trading Agent agent session logging
- Hermes Kanban task creation (6 tasks to create)
- Backup/restore runbook
- Monitoring/health checks
