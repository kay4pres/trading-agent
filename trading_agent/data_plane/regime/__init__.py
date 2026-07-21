"""regime — Markov regime detection for any asset.

Adapted from Roan's (@RohOnChain) Markov framework, refactored into a
Claude Code plugin by Lewis Jackson. Asset-agnostic, accepts ticker or CSV.

For the trading-agent project, the primary use is on SPY (market proxy):
  * Detect Bull/Bear/Sideways state
  * Get the `signal` field in [-1, 1] for regime-aware risk gating
  * Get the `stationary_distribution` for tail-risk position sizing
  * Run walk-forward backtest for out-of-sample validation

Use:
    from trading_agent.data_plane.regime import analyze_from_csv, signal

    result = analyze_from_csv("path/to/spy_history.csv", window=20, threshold=0.05)
    if result["signal"] < 0:   # bear regime
        skip_long_entries()
    pos_size = base_size * (1.0 - result["stationary_distribution"]["bear"])
"""

from trading_agent.data_plane.regime.markov_regime import (
    DEFAULT_MIN_TRAIN,
    DEFAULT_THRESHOLD,
    DEFAULT_WINDOW,
    DEFAULT_YEARS,
    STATES,
    analyze,
    build_transition_matrix,
    fetch_ticker,
    fit_hmm,
    label_regimes,
    load_csv,
    nstep_forecast,
    signal_from_matrix,
    stationary_distribution,
    walk_forward_backtest,
)

__all__ = [
    "DEFAULT_MIN_TRAIN",
    "DEFAULT_THRESHOLD",
    "DEFAULT_WINDOW",
    "DEFAULT_YEARS",
    "STATES",
    "analyze",
    "build_transition_matrix",
    "fetch_ticker",
    "fit_hmm",
    "label_regimes",
    "load_csv",
    "nstep_forecast",
    "signal_from_matrix",
    "stationary_distribution",
    "walk_forward_backtest",
    "analyze_from_csv",
    "analyze_from_ticker",
    "regime_filter",
]


# Convenience wrappers for the trading-agent use case
def analyze_from_csv(csv_path: str, window: int = DEFAULT_WINDOW,
                     threshold: float = DEFAULT_THRESHOLD, source: str = None) -> dict:
    """Run Markov regime analysis on a local CSV (date + close columns)."""
    close = load_csv(csv_path)
    if source is None:
        source = str(csv_path)
    return analyze(close, source=source, window=window, threshold=threshold,
                   min_train=DEFAULT_MIN_TRAIN, hmm=False)


def analyze_from_ticker(ticker: str, years: int = DEFAULT_YEARS,
                        window: int = DEFAULT_WINDOW,
                        threshold: float = DEFAULT_THRESHOLD) -> dict:
    """Run Markov regime analysis on a ticker via yfinance."""
    close = fetch_ticker(ticker, years=years)
    return analyze(close, source=ticker, window=window, threshold=threshold,
                   min_train=DEFAULT_MIN_TRAIN, hmm=False)


def regime_filter(result: dict, min_bull_signal: float = 0.0) -> bool:
    """Hard filter: only return True if regime signal >= threshold.

    Use as a guard on our DTD scanners: 'Don't take first-pullback long if
    market regime is bear'. Default 0 means 'no long unless bull_prob > bear_prob'.

    Args:
        result: the dict from analyze() / analyze_from_ticker()
        min_bull_signal: minimum signal in [-1, 1] to approve
    """
    return result.get("signal", 0.0) >= min_bull_signal
