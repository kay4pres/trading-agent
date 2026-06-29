r"""
alpaca_ws_subprocess.py
=======================
Dedicated subprocess that streams live Alpaca quotes.
Runs in a completely isolated Python process with its own event loop.
Prints every quote as JSON to stdout — parent reads line by line.

Usage (subprocess):
    py -3 alpaca_ws_subprocess.py --api-key KEY --secret SECRET --symbols BDRX,WSHP,AOUT

Parent (live_event_loop.py) reads quotes via:
    AlpacaWSSubprocess.subscribe(['BDRX', 'WSHP'], callback_fn)
"""

import argparse
import asyncio
import json
import signal
import sys
from datetime import datetime, timezone, timedelta

# ── CLI ─────────────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(description="Alpaca WebSocket quote streamer (subprocess)")
parser.add_argument("--api-key", required=True)
parser.add_argument("--secret", required=True)
parser.add_argument("--symbols", required=True, help="Comma-separated symbol list")
args = parser.parse_args()

SYMBOLS = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
AMSTERDAM_TZ = timezone(timedelta(hours=2))


# ── WebSocket stream ────────────────────────────────────────────────────────────

async def stream_quotes(api_key: str, secret: str, symbols: list[str]):
    """
    Stream live quotes, print each one as JSON to stdout.
    Parent process reads stdout line by line.
    """
    from alpaca.data.live import StockDataStream

    stream = StockDataStream(api_key=api_key, secret_key=secret)

    async def handler(quote):
        payload = {
            "symbol": quote.symbol,
            "bid": float(quote.bid_price),
            "ask": float(quote.ask_price),
            "timestamp": quote.timestamp.isoformat(),
        }
        # Print JSON to stdout — parent reads this line by line
        print(json.dumps(payload), flush=True)

    stream.subscribe_quotes(handler, *symbols)
    print(f"[WS] Connected to Alpaca streaming quotes for {symbols}", flush=True)
    print(f"[WS] STREAM_START", flush=True)  # signal to parent that stream is live
    await stream.run()


# ── Main ────────────────────────────────────────────────────────────────────────

async def main():
    loop = asyncio.get_event_loop()

    # Graceful shutdown on Ctrl+C
    def shutdown():
        print("[WS] Shutdown signal received", flush=True)
        task.cancel()

    signal.signal(signal.SIGINT, lambda *_: shutdown())
    signal.signal(signal.SIGTERM, lambda *_: shutdown())

    task = asyncio.create_task(stream_quotes(args.api_key, args.secret, SYMBOLS))
    try:
        await task
    except asyncio.CancelledError:
        print("[WS] Stream cancelled", flush=True)
    except Exception as e:
        # Suppress Alpaca SDK bug on stop() — _loop can be None on exit
        err_str = str(e)
        if "is_running" in err_str or "NoneType" in err_str:
            print("[WS] Stream ended", flush=True)
        else:
            print(f"[WS] Error: {e}", flush=True)
            sys.exit(1)


asyncio.run(main())