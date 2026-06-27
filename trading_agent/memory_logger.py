r"""
memory_logger.py
================
Appends a closed trade to the journal and recalculates P&L stats.

Called by the Bull/Bear signal handler when a position exits.
Never overwrites — only appends.

Usage:
    from memory_logger import log_trade
    log_trade(closed_trade_record)
"""
from pathlib import Path
from datetime import datetime, timezone
import re

JOURNAL_PATH = Path(r"E:\Me\TradingAgent\knowledge\memory\trade_journal.md")


def log_trade(trade: dict) -> str:
    """
    Append a closed trade to the journal.

    trade = {
        "symbol":       "PTLE",
        "action":       "LONG",
        "entry_price":  6.06,
        "exit_price":   6.31,
        "exit_reason":  "TARGET_HIT",   # TARGET_HIT | STOP_HIT | TIME_EXIT | MANUAL
        "pnl":          25.00,
        "pnl_pct":      4.13,
        "closed_at":    "2026-06-25T16:55:00+02:00",
        "notes":        "First pullback, gap +20.2%, RV 7.7x"   # optional
    }
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+02:00")
    win = "WIN" if trade["pnl"] > 0 else "LOSS" if trade["pnl"] < 0 else "BE"
    symbol = trade["symbol"].upper()
    action = trade.get("action", "LONG")
    entry = trade["entry_price"]
    exit_px = trade["exit_price"]
    pnl = trade["pnl"]
    pnl_pct = trade["pnl_pct"]
    reason = trade.get("exit_reason", "UNKNOWN")
    notes = trade.get("notes", "")

    entry_block = f"""### Trade — {symbol} | {ts}
**Type:** {action} | **Result:** {win}

| Field | Value |
|-------|-------|
| Entry | ${entry:.2f} |
| Exit  | ${exit_px:.2f} |
| P&L   | ${pnl:+.2f} ({pnl_pct:+.2f}%) |
| Exit Reason | {reason} |
{"| Notes | " + notes + " |" if notes else ""}

**What Trader learned:**
<!-- Trader — write your reflection here after each trade. Why did it work? What would you do differently? How will this change your next decision? -->

---
"""

    # Read current journal
    content = JOURNAL_PATH.read_text(encoding="utf-8")

    # Split off the P&L table and Trade Log header
    marker = "## Trade Log"
    if marker not in content:
        raise ValueError(f"Journal missing '{marker}' section — check format")

    before, after = content.split(marker, 1)

    # Append new entry
    new_content = before + marker + "\n\n" + entry_block + after

    # Recalculate P&L stats
    new_content = _recalc_stats(new_content)

    JOURNAL_PATH.write_text(new_content, encoding="utf-8")
    return f"[Memory] Logged {win} on {symbol}: ${pnl:+.2f}"


def _recalc_stats(content: str) -> str:
    """Parse trade entries from journal and rebuild the P&L summary table."""
    entries = _extract_entries(content)

    total = len(entries)
    wins = sum(1 for e in entries if e["pnl"] > 0)
    losses = sum(1 for e in entries if e["pnl"] < 0)
    win_rate = f"{wins / total * 100:.1f}%" if total > 0 else "—"
    total_pnl = sum(e["pnl"] for e in entries)
    win_values = [e["pnl"] for e in entries if e["pnl"] > 0]
    loss_values = [e["pnl"] for e in entries if e["pnl"] < 0]
    avg_win = f"${sum(win_values)/len(win_values):.2f}" if win_values else "—"
    avg_loss = f"${sum(loss_values)/len(loss_values):.2f}" if loss_values else "—"
    best = f"${max(e['pnl'] for e in entries):.2f}" if entries else "—"
    worst = f"${min(e['pnl'] for e in entries):.2f}" if entries else "—"

    new_table = f"""| Metric | Value |
|--------|-------|
| Total Trades | {total} |
| Wins | {wins} |
| Losses | {losses} |
| Win Rate | {win_rate} |
| Total P&L | ${total_pnl:+.2f} |
| Avg Win | {avg_win} |
| Avg Loss | {avg_loss} |
| Best Trade | {best} |
| Worst Trade | {worst} |
"""

    # Replace P&L table by finding start/end line indices
    lines = content.split("\n")
    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if "| Metric | Value |" in line:
            start_idx = i
        if start_idx is not None and end_idx is None and line.strip() == "---":
            end_idx = i
            break

    if start_idx is not None and end_idx is not None:
        # Replace lines from start_idx to end_idx (inclusive), then put back the "---"
        new_lines = lines[:start_idx] + new_table.strip().split("\n") + ["", "---", ""] + lines[end_idx + 1:]
        return "\n".join(new_lines)
    return content


def _extract_entries(content: str) -> list:
    """Pull P&L data from all trade entries already in the journal."""
    entries = []
    # Find each trade block: "### Trade — SYMBOL" through the next "---"
    block_pattern = r"(### Trade — (\w+).*?)(?=\n---|\Z)"
    for block_m in re.finditer(block_pattern, content, re.DOTALL):
        block = block_m.group(1)
        symbol = block_m.group(2)
        # Extract P&L row: | P&L   | $+25.00 (+4.13%) |
        pnl_m = re.search(r"\| P&L\s+\|\s*\$\s*([+-]?[\d.]+)\s+\([+-]?([\d.]+)%\)", block)
        reason_m = re.search(r"\| Exit Reason \|\s*(\w+)", block)
        if pnl_m:
            entries.append({
                "symbol": symbol,
                "pnl": float(pnl_m.group(1)),
                "pnl_pct": float(pnl_m.group(2)),
                "exit_reason": reason_m.group(1) if reason_m else "UNKNOWN",
            })
    return entries


def demo():
    """Dry-run: append a fake trade and print the updated journal."""
    fake = {
        "symbol": "PTLE",
        "action": "LONG",
        "entry_price": 6.06,
        "exit_price": 6.31,
        "exit_reason": "TARGET_HIT",
        "pnl": 25.00,
        "pnl_pct": 4.13,
        "closed_at": "2026-06-25T16:55:00+02:00",
        "notes": "First pullback, gap +20.2%, RV 7.7x, bull_bear conviction 8.5",
    }
    print(log_trade(fake))


if __name__ == "__main__":
    demo()