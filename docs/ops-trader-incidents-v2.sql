# Ops-trader incidents.db v2 migration

-- Existing rows are preserved. Apply once through the trading-agent-dev
-- container's Python sqlite3 module because the NAS host has no python3.
ALTER TABLE incidents ADD COLUMN which_engineer_dispatched TEXT;
ALTER TABLE incidents ADD COLUMN specialist_task_id TEXT;
ALTER TABLE incidents ADD COLUMN fix_verified_at TEXT;
