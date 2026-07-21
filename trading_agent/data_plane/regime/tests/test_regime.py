"""Smoke tests for the Markov regime detector.

No network access required — uses a synthetic CSV. Tests the three contracts
our trading-agent code consumes:
  1. analyze_from_csv returns the structured dict (signal, current_regime,
     stationary_distribution, walk_forward).
  2. regime_filter() blocks bear regime for long entries.
  3. The signal field is in [-1, 1].

Adapted from Lewis Jackson's regime skill tests (MIT-style).
"""

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from trading_agent.data_plane.regime import (  # noqa: E402
    STATES,
    analyze_from_csv,
    build_transition_matrix,
    label_regimes,
    regime_filter,
    signal_from_matrix,
    stationary_distribution,
)


@pytest.fixture
def synthetic_csv(tmp_path) -> Path:
    """Build a synthetic price series with 3 regimes: bull, bear, sideways."""
    np.random.seed(42)
    n = 600
    dates = [date(2024, 1, 2) + timedelta(days=i) for i in range(n)]
    # Construct regime-segmented returns
    rets = np.zeros(n)
    # Bull: 0.001/day, 100 days
    rets[0:100] = np.random.normal(0.001, 0.01, 100)
    # Sideways: 0.0/day, 100 days
    rets[100:200] = np.random.normal(0.0, 0.01, 100)
    # Bear: -0.001/day, 100 days
    rets[200:300] = np.random.normal(-0.001, 0.01, 100)
    # Bull again, 300 days
    rets[300:] = np.random.normal(0.001, 0.01, 300)
    prices = 100.0 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({"date": dates, "close": prices})
    path = tmp_path / "synthetic.csv"
    df.to_csv(path, index=False)
    return path


def test_analyze_from_csv_returns_expected_keys(synthetic_csv):
    result = analyze_from_csv(str(synthetic_csv), window=20, threshold=0.05)
    expected_keys = {
        "source", "rows", "date_start", "date_end", "params", "states",
        "current_regime", "next_state_probabilities", "signal",
        "transition_matrix", "persistence_diagonal",
        "stationary_distribution", "walk_forward", "hmm", "framework",
        "disclaimer",
    }
    assert expected_keys.issubset(result.keys()), (
        f"Missing keys: {expected_keys - result.keys()}"
    )


def test_signal_is_in_minus_one_one(synthetic_csv):
    result = analyze_from_csv(str(synthetic_csv), window=20, threshold=0.05)
    assert -1.0 <= result["signal"] <= 1.0, f"signal={result['signal']}"


def test_stationary_distribution_sums_to_one(synthetic_csv):
    result = analyze_from_csv(str(synthetic_csv), window=20, threshold=0.05)
    sd = result["stationary_distribution"]
    total = sd["bear"] + sd["sideways"] + sd["bull"]
    assert abs(total - 1.0) < 0.01, f"stationary_distribution sums to {total}"


def test_states_are_bear_sideways_bull():
    assert STATES == ["Bear", "Sideways", "Bull"]


def test_regime_filter_blocks_bear_for_long_entries():
    """A bear signal (negative) should be blocked by default long filter."""
    bear_result = {"signal": -0.4, "current_regime": "Bear"}
    assert regime_filter(bear_result, min_bull_signal=0.0) is False
    assert regime_filter(bear_result, min_bull_signal=-0.5) is True  # permissive


def test_regime_filter_passes_bull_for_long_entries():
    bull_result = {"signal": 0.5, "current_regime": "Bull"}
    assert regime_filter(bull_result, min_bull_signal=0.0) is True


def test_transition_matrix_rows_sum_to_one(synthetic_csv):
    result = analyze_from_csv(str(synthetic_csv), window=20, threshold=0.05)
    P = np.array(result["transition_matrix"])
    row_sums = P.sum(axis=1)
    for i, s in enumerate(row_sums):
        assert abs(s - 1.0) < 0.01, f"row {i} sums to {s}"


def test_label_regimes_returns_three_states():
    """The labeler must produce only the canonical 3 states in order."""
    s = pd.Series([0.01, -0.01, 0.001, 0.005, -0.005, 0.0, 0.02, -0.02])
    labels = label_regimes(s, window=3, threshold=0.01)
    unique = set(labels.dropna().unique())
    assert unique.issubset({0, 1, 2}), f"Unexpected labels: {unique}"


def test_stationary_distribution_helper_matches_scipy_eigenvector():
    """Quick sanity: a known 3x3 transition matrix produces the right vector."""
    P = np.array([
        [0.7, 0.2, 0.1],
        [0.2, 0.6, 0.2],
        [0.1, 0.2, 0.7],
    ])
    pi = stationary_distribution(P)
    # For a doubly-stochastic matrix, the uniform is the stationary dist.
    np.testing.assert_allclose(pi, [1 / 3, 1 / 3, 1 / 3], atol=1e-6)
