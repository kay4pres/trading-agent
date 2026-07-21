"""trade_journal — schema extension + CSV export for the trading-loop engine.

The trading-loop engine consumes trade records in this format:
    date, asset, direction, entry, stop, exit, session, setup,
    rule_compliance, emotional_state, r_multiple

Our `positions.json` (in data/) tracks open + closed positions, but its
schema is missing the fields the learning loop needs (r_multiple,
rule_compliance, session, setup, emotional_state). This module:

  1. EXTENDS the positions.json schema with the new fields (additive,
     non-breaking — old records work, new records carry the extras).
  2. APPENDS a closed position to the trade journal CSV (one row per
     closed trade, in the engine's schema).
  3. EXPORTS positions.json -> trade_journal.csv on demand, so the
     trading_loop engine can read historical closed positions.

The CSV is the engine's input. The positions.json remains the source of
truth for live state.
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Path discipline: E:\ is operational truth.
POSITIONS_FILE = Path(
    os.environ.get(
        "POSITIONS_FILE", r"E:\Me\TradingAgent\data\positions.json"
    )
)
JOURNAL_CSV = Path(
    os.environ.get(
        "TRADE_JOURNAL_CSV", r"E:\Me\TradingAgent\data\trade_journal.csv"
    )
)

# Engine-compatible column order (matches trading_loop/engine.py:_r_multiple)
JOURNAL_COLUMNS = [
    "date",          # ISO date of entry
    "asset",         # symbol
    "direction",     # long / short
    "entry",         # entry price
    "stop",          # stop loss
    "exit",          # exit price
    "session",       # premarket / open / midday / close
    "setup",         # First Pullback / Bull Flag / etc.
    "rule_compliance",  # true / false
    "emotional_state",  # calm / anxious / FOMO / etc.
    "r_multiple",    # derived: (exit-entry)/|entry-stop|, sign by direction
    "pnl",           # realized P&L in $
    "exit_reason",   # target / stop / 2min / manual
    "notes",         # free text
]


def derive_r_multiple(entry: float, stop: float, exit_price: float,
                      direction: str) -> Optional[float]:
    """R multiple = realized reward / planned risk. Sign by direction.
    Matches trading_loop/engine.py:_r_multiple() so the engine and our
    journal produce identical R values for the same trade."""
    risk = abs(entry - stop)
    if risk == 0:
        return None
    sign = -1.0 if direction.lower() in ("short", "sell", "s") else 1.0
    return ((exit_price - entry) * sign) / risk


def infer_session(opened_at: str) -> str:
    """Best-effort session inference from ISO timestamp.
    04:00-09:30 ET = premarket | 09:30-12:00 = open | 12:00-15:00 = midday
    | 15:00-16:00 = close."""
    from datetime import timedelta
    try:
        ts = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
        # Convert to ET (UTC-5 in summer, UTC-4 in winter).
        # DST in the US: second Sunday of March to first Sunday of November.
        utc_dt = ts.astimezone(timezone.utc)
        m, d = utc_dt.month, utc_dt.day
        # Coarse DST: March-November inclusive = summer (UTC-4 in ET, but ET = UTC-4 in DST, UTC-5 in standard)
        # Actually, US Eastern Daylight Time is UTC-4, US Eastern Standard Time is UTC-5.
        # DST: ~mid-March to ~early November.
        is_dst = (m > 3 and m < 11) or (m == 3 and d >= 8) or (m == 11 and d < 7)
        et_offset = -4 if is_dst else -5
        et = ts.astimezone(timezone(timedelta(hours=et_offset)))
        h = et.hour + et.minute / 60.0
        if h < 9.5:
            return "premarket"
        if h < 12.0:
            return "open"
        if h < 15.0:
            return "midday"
        return "close"
    except Exception:
        return "unknown"


def timedelta_hours(hours: float) -> timezone:
    """PowerShell-safe timezone construction."""
    from datetime import timedelta
    return timezone(timedelta(hours=hours))


def load_positions() -> dict:
    if not POSITIONS_FILE.exists():
        return {
            "schema_version": "1.0",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "positions": {},
            "history": [],
        }
    with open(POSITIONS_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def closed_positions() -> list[dict]:
    """Return all closed positions, newest first."""
    state = load_positions()
    history = state.get("history", [])
    return [p for p in history if p.get("status") in ("CLOSED", "EXITED", "closed")]


def extend_position_schema(pos: dict) -> dict:
    """Add trade-journal fields to a position dict if absent.
    Additive: never overwrites existing values. Defaults:
      rule_compliance: True (assume good unless recorded otherwise)
      session: inferred from opened_at
      setup: from entry_signal field
      emotional_state: 'unknown'
      r_multiple: derived from exit_price vs entry vs stop
    """
    extended = dict(pos)
    extended.setdefault("rule_compliance", True)
    extended.setdefault("emotional_state", "unknown")
    if "session" not in extended and "opened_at" in extended:
        extended["session"] = infer_session(extended["opened_at"])
    if "setup" not in extended and "entry_signal" in extended:
        extended["setup"] = extended["entry_signal"]
    if "r_multiple" not in extended and all(
        k in extended for k in ("entry_price", "stop", "exit_price", "direction")
    ):
        try:
            r = derive_r_multiple(
                float(extended["entry_price"]),
                float(extended["stop"]),
                float(extended["exit_price"]),
                extended["direction"],
            )
            extended["r_multiple"] = r
        except (TypeError, ValueError):
            pass
    extended.setdefault("notes", "")
    return extended


def export_to_csv(path: Optional[Path] = None) -> int:
    """Export closed positions to the journal CSV. Returns row count written.
    Existing CSV is appended; duplicates are NOT removed (engine de-dupes by
    date+asset+direction+r_multiple).
    """
    if path is None:
        path = JOURNAL_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for pos in closed_positions():
        ext = extend_position_schema(pos)
        rows.append({
            "date": (ext.get("opened_at") or "")[:10],
            "asset": ext.get("symbol", ""),
            "direction": ext.get("direction", "long"),
            "entry": ext.get("entry_price", ""),
            "stop": ext.get("stop", ""),
            "exit": ext.get("exit_price", ""),
            "session": ext.get("session", "unknown"),
            "setup": ext.get("setup", ext.get("entry_signal", "unknown")),
            "rule_compliance": "true" if ext.get("rule_compliance") else "false",
            "emotional_state": ext.get("emotional_state", "unknown"),
            "r_multiple": ext.get("r_multiple", ""),
            "pnl": ext.get("pnl", ""),
            "exit_reason": ext.get("exit_reason", ""),
            "notes": ext.get("notes", ""),
        })
    # Append to file (header only if empty)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=JOURNAL_COLUMNS)
        if write_header:
            writer.writeheader()
        for r in rows:
            writer.writerow(r)
    return len(rows)


def load_journal(path: Optional[Path] = None) -> list[dict]:
    """Load the journal CSV and return a list of trade dicts in the engine's
    expected schema (date, asset, direction, entry, stop, exit, session,
    setup, rule_compliance, emotional_state, r_multiple)."""
    if path is None:
        path = JOURNAL_CSV
    if not path.exists():
        return []
    out = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            # Coerce numeric fields
            for k in ("entry", "stop", "exit", "r_multiple", "pnl"):
                if r.get(k) in ("", None):
                    r[k] = None
                else:
                    try:
                        r[k] = float(r[k])
                    except (TypeError, ValueError):
                        r[k] = None
            # Coerce rule_compliance
            rc = str(r.get("rule_compliance", "true")).lower()
            r["rule_compliance"] = rc in ("true", "1", "yes", "y", "t")
            out.append(r)
    return out


# --------------------------------------------------------------------------- #
# Wire helpers — called from trader_agent.execute_exit()
# --------------------------------------------------------------------------- #
def on_position_closed(pos: dict) -> dict:
    """Called when a position transitions from OPEN to CLOSED. Adds
    journal fields and appends to the CSV. Returns the extended dict.
    """
    ext = extend_position_schema(pos)
    export_to_csv()
    return ext
