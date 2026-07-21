"""news_guard — event-blackout layer for the trading risk engine.

Adapted from Lewis Jackson's news-guard skill (MIT-style). See news_guard.py
for full attribution and module docstring.
"""

from trading_agent.data_plane.news_guard.news_guard import (
    BUNDLED_CSV,
    CRYPTO_INSTRUMENTS,
    CRYPTO_KEYWORDS,
    DEFAULT_AFTER_MIN,
    DEFAULT_BEFORE_MIN,
    FF_URL,
    INSTRUMENT_MAP,
    Event,
    decide,
    evaluate,
    file_log,
    instrument_currencies,
    is_crypto,
    load_events,
    load_from_csv,
    load_from_forexfactory,
    parse_time,
)

__all__ = [
    "BUNDLED_CSV",
    "CRYPTO_INSTRUMENTS",
    "CRYPTO_KEYWORDS",
    "DEFAULT_AFTER_MIN",
    "DEFAULT_BEFORE_MIN",
    "FF_URL",
    "INSTRUMENT_MAP",
    "Event",
    "decide",
    "evaluate",
    "file_log",
    "instrument_currencies",
    "is_crypto",
    "load_events",
    "load_from_csv",
    "load_from_forexfactory",
    "parse_time",
]
