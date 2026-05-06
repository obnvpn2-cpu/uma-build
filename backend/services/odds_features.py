"""Odds-derived features for EV-strategy experimentation.

The raw `popularity` column is the **rank** of `win_odds` per race and is
a near-perfect proxy for market consensus — including it dominates the
model (high AUC) but yields useless EV strategies because the model just
mirrors the market. These derived features carry primarily *magnitude*
information from `win_odds`, with limited per-race relative info via
race-level aggregates (min, mean).

**Honest residual-leak note**: `log_odds_gap_to_fav` is the per-row log
odds minus the per-race minimum log odds. Combined with `log_win_odds`,
a model can deduce per-race-min(log_win_odds) but cannot recover the
full popularity rank from per-row features alone (tree splits do not
compute per-race ordering). Empirically, including these features
brought AUC to 0.838 (vs 0.851 with raw popularity, 0.798 without
either) and kept EV strategies functional (best non-noise -18.5%, vs
-22.7% without odds and -20.2% with popularity-driven rank model). So
the leak is partial, not total — the model does not collapse to
"always agree with favorite". Drop `log_odds_gap_to_fav` if you want
strictly magnitude-only signal.

All helpers operate on a DataFrame with at least `race_key` and a
`win_odds` column scaled `actual_odds * 10` (matching the EveryDB2
convention used in the parquet cache). Rows with `win_odds == 0` are
the EveryDB2 sentinel for "odds not ingested" (~41% of races, mostly
older). Helpers clip them to `_MIN_REAL_ODDS` so log stays finite, but
this **silently maps missing data to a constant** — callers should drop
those races at the row/race level before training (the explore script
does this automatically when `--with-odds-aware` is set).

Design choices:
- We never include raw `popularity` in the derived set (that is the
  full rank leak; partial rank info via gap-to-fav is a deliberate
  trade — see note above).
- `log_win_odds` and `implied_prob` carry magnitude only.
- `log_odds_gap_to_fav` is per-race; favorite is always 0.
- `log_odds_gap_to_mean` is per-race; centered (sums to 0).
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
    """Add `fuku_odds_uncertainty` = (high - low) / clip(low, lower=1.0).

    Relative spread in the place-bet odds range. High = market is unsure
    whether the horse will be top-3. Independent signal from win odds.
    Returns NaN when `fuku_odds_low` or `fuku_odds_high` is missing or
    when `high < low` (data corruption — the relationship is invariant).
    """
    df = df.copy()
    low = df.get("fuku_odds_low")
    high = df.get("fuku_odds_high")
    if low is None or high is None:
        df["fuku_odds_uncertainty"] = np.nan
        return df
    low_real = (low.astype("float64") / _ODDS_SCALE).clip(lower=1.0)
    high_real = high.astype("float64") / _ODDS_SCALE
    raw = (high_real - low_real) / low_real
    # Negative spread → corrupted row; mark NaN rather than emitting a
    # nonsensical negative "uncertainty".
    df["fuku_odds_uncertainty"] = raw.where(high_real >= low_real, np.nan)
    return df


def add_odds_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all odds-derived feature helpers in one shot.

    Single in-place mutation on a top-level copy (each helper would
    otherwise re-copy a 1M-row frame five times).

    Returns a copy with new columns:
      - log_win_odds
      - implied_prob
      - log_odds_gap_to_fav
      - log_odds_gap_to_mean
      - fuku_odds_uncertainty (when fuku_odds columns present)

    Caller is responsible for dropping rows where source `win_odds == 0`.
    """
    out = df.copy()
    real = _real_odds(out["win_odds"])
    out["log_win_odds"] = np.log(real)
    out["implied_prob"] = 1.0 / real
    out["log_odds_gap_to_fav"] = (
        out["log_win_odds"]
        - out.groupby("race_key")["log_win_odds"].transform("min")
    )
    out["log_odds_gap_to_mean"] = (
        out["log_win_odds"]
        - out.groupby("race_key")["log_win_odds"].transform("mean")
    )
    if "fuku_odds_low" in out.columns and "fuku_odds_high" in out.columns:
        low_real = (out["fuku_odds_low"].astype("float64") / _ODDS_SCALE).clip(lower=1.0)
        high_real = out["fuku_odds_high"].astype("float64") / _ODDS_SCALE
        raw = (high_real - low_real) / low_real
        out["fuku_odds_uncertainty"] = raw.where(high_real >= low_real, np.nan)
    else:
        out["fuku_odds_uncertainty"] = np.nan
    return out


ODDS_DERIVED_COLUMNS: list[str] = [
    "log_win_odds",
    "implied_prob",
    "log_odds_gap_to_fav",
    "log_odds_gap_to_mean",
    "fuku_odds_uncertainty",
]
