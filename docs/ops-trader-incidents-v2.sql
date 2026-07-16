-- Ops-trader incidents.db v2 additive migration.
-- Apply once through the trading-agent-dev container's Python sqlite3 module
-- because the NAS host has no python3. Existing rows are preserved; all new
-- columns are nullable for compatibility.

ALTER TABLE incidents ADD COLUMN which_engineer_dispatched TEXT;
ALTER TABLE incidents ADD COLUMN specialist_task_id TEXT;
ALTER TABLE incidents ADD COLUMN fix_verified_at TEXT;
