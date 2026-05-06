"""Odds-derived features for EV-strategy experimentation.

The raw `popularity` column is a near-perfect proxy for market consensus
and dominates the model — high AUC but useless for EV betting because the
model just mirrors the market. These derived features carry partial market
information (the *magnitude* of odds, not the rank) so a model can learn
where its own ability estimate diverges from the market without reducing
to "always agree with the favorite".

All helpers operate on a DataFrame with at least `race_key` and a
`win_odds` column scaled `actual_odds * 10` (matching the EveryDB2
convention used in the parquet cache). Rows with `win_odds == 0` are
treated as missing — the cache contains older races with no odds ingested
(~41% of races); callers should drop those races or NaN-fill the derived
columns.

Design choices:
- We never include raw `popularity` in the derived set (that is the leak).
- `log_win_odds` and `implied_prob` carry magnitude only.
- `log_odds_gap_to_fav` is per-race (no cross-race signal); horizontally
  centered so the favorite is always 0 — captures relative position.
- `fuku_odds_uncertainty` is independent of win odds; market's place-bet
  spread is a proxy for "how confident is the market this horse is top-3".
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Real odds = stored value / 10 (EveryDB2 N_ODDS_TANPUKU convention)
_ODDS_SCALE = 10.0
_MIN_REAL_ODDS = 1.05  # JRA floor; clip to keep log finite


def _real_odds(s: pd.Series) -> pd.Series:
    return (s.astype("float64") / _ODDS_SCALE).clip(lower=_MIN_REAL_ODDS)


def add_log_win_odds(df: pd.DataFrame) -> pd.DataFrame:
    """Add `log_win_odds` = ln(win_odds_real). Requires `win_odds` column."""
    df = df.copy()
    df["log_win_odds"] = np.log(_real_odds(df["win_odds"]))
    return df


def add_implied_prob(df: pd.DataFrame) -> pd.DataFrame:
    """Add `implied_prob` = 1 / win_odds_real (no takeout adjustment).

    This is the market-implied raw win probability. Sums to >1 across a
    race because of the takeout (~25% in JRA tansho).
    """
    df = df.copy()
    df["implied_prob"] = 1.0 / _real_odds(df["win_odds"])
    return df


def add_log_odds_gap_to_fav(df: pd.DataFrame) -> pd.DataFrame:
    """Add `log_odds_gap_to_fav` = log_win_odds - per-race min(log_win_odds).

    The favorite is always 0; longshots are positive. Captures relative
    market position without leaking the absolute rank.
    """
    df = df.copy()
    log_odds = np.log(_real_odds(df["win_odds"]))
    df["log_odds_gap_to_fav"] = log_odds - log_odds.groupby(df["race_key"]).transform("min")
    return df


def add_log_odds_gap_to_mean(df: pd.DataFrame) -> pd.DataFrame:
    """Add `log_odds_gap_to_mean` = log_win_odds - per-race mean(log_win_odds).

    Centered version: 0 = average horse in this race, negative = better
    than average market expectation, positive = worse.
    """
    df = df.copy()
    log_odds = np.log(_real_odds(df["win_odds"]))
    df["log_odds_gap_to_mean"] = log_odds - log_odds.groupby(df["race_key"]).transform("mean")
    return df


def add_fuku_odds_uncertainty(df: pd.DataFrame) -> pd.DataFrame:
    """Add `fuku_odds_uncertainty` = (high - low) / max(low, 1.0).

    Relative spread in the place-bet odds range. High = market is unsure
    whether the horse will be top-3. Independent signal from win odds.
    Returns NaN when `fuku_odds_low` or `fuku_odds_high` is missing.
    """
    df = df.copy()
    low = df.get("fuku_odds_low")
    high = df.get("fuku_odds_high")
    if low is None or high is None:
        df["fuku_odds_uncertainty"] = np.nan
        return df
    low_real = (low.astype("float64") / _ODDS_SCALE).clip(lower=1.0)
    high_real = high.astype("float64") / _ODDS_SCALE
    df["fuku_odds_uncertainty"] = (high_real - low_real) / low_real
    return df


def add_odds_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all odds-derived feature helpers in one shot.

    Returns a copy with new columns:
      - log_win_odds
      - implied_prob
      - log_odds_gap_to_fav
      - log_odds_gap_to_mean
      - fuku_odds_uncertainty (when fuku_odds columns present)

    Caller is responsible for dropping rows where source `win_odds == 0`.
    """
    df = add_log_win_odds(df)
    df = add_implied_prob(df)
    df = add_log_odds_gap_to_fav(df)
    df = add_log_odds_gap_to_mean(df)
    df = add_fuku_odds_uncertainty(df)
    return df


ODDS_DERIVED_COLUMNS: list[str] = [
    "log_win_odds",
    "implied_prob",
    "log_odds_gap_to_fav",
    "log_odds_gap_to_mean",
    "fuku_odds_uncertainty",
]
