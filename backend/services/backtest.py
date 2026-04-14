"""Backtest service for UmaBuild.

Calculates ROI, hit rate, and condition-breakdown metrics from
model predictions and actual race results.
"""

import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _top1_per_race(df: pd.DataFrame) -> pd.DataFrame:
    """Select the top-1 predicted horse per race (highest pred_prob)."""
    return df.loc[df.groupby("race_key")["pred_prob"].idxmax()]


def _topN_per_race(df: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    """Select the top-N predicted horses per race."""
    return (
        df.sort_values(["race_key", "pred_prob"], ascending=[True, False])
        .groupby("race_key")
        .head(n)
    )


def _calc_roi(
    picks: pd.DataFrame,
    bet_amount: float = 100,
) -> Dict[str, float]:
    """Calculate ROI for a set of picks.

    Assumes simple win betting on each selected horse at the displayed odds.

    Args:
        picks: DataFrame with columns [actual_win, win_odds].
        bet_amount: Amount bet per race (yen).

    Returns:
        Dict with total_bet, total_return, roi, profit.
    """
    n_bets = len(picks)
    total_bet = n_bets * bet_amount

    if total_bet == 0:
        return {"total_bet": 0, "total_return": 0, "roi": 0.0, "profit": 0}

    # Win returns: prefer actual payout data, then odds, then fallback
    if "tansho_payout" in picks.columns and picks["tansho_payout"].notna().any():
        wins = picks[(picks["actual_win"] == 1) & picks["tansho_payout"].notna()]
        total_return = float(wins["tansho_payout"].sum()) * (bet_amount / 100)
    elif "win_odds" in picks.columns:
        wins = picks[picks["actual_win"] == 1]
        total_return = float((wins["win_odds"] * bet_amount).sum())
    else:
        # If no odds data, assume average odds of 8.0 for winners
        n_wins = int(picks["actual_win"].sum())
        total_return = n_wins * 8.0 * bet_amount

    profit = total_return - total_bet
    roi = (profit / total_bet) * 100 if total_bet > 0 else 0.0

    return {
        "total_bet": int(total_bet),
        "total_return": int(total_return),
        "roi": round(roi, 2),
        "profit": int(profit),
    }


def _calc_hit_rate(picks: pd.DataFrame) -> Dict[str, float]:
    """Calculate hit rate (percentage of bets that won).

    Args:
        picks: DataFrame with column [actual_win].

    Returns:
        Dict with n_bets, n_hits, hit_rate.
    """
    n_bets = len(picks)
    n_hits = int(picks["actual_win"].sum())
    hit_rate = (n_hits / n_bets * 100) if n_bets > 0 else 0.0

    return {
        "n_bets": n_bets,
        "n_hits": n_hits,
        "hit_rate": round(hit_rate, 2),
    }


def _condition_breakdown(
    picks: pd.DataFrame,
    bet_amount: float = 100,
) -> List[Dict[str, Any]]:
    """Calculate ROI/hit-rate breakdown by surface + track_condition.

    Args:
        picks: DataFrame with columns [surface, track_condition, actual_win, win_odds].
        bet_amount: Bet amount per race.

    Returns:
        List of dicts, each with condition info and metrics.
    """
    breakdowns = []

    if "surface" not in picks.columns or "track_condition" not in picks.columns:
        logger.warning("Surface or track_condition columns missing for condition breakdown.")
        return breakdowns

    surface_labels = {1: "芝", 2: "ダート"}
    condition_labels = {1: "良", 2: "稍重", 3: "重", 4: "不良"}

    for (surface, condition), group in picks.groupby(["surface", "track_condition"]):
        roi_data = _calc_roi(group, bet_amount)
        hit_data = _calc_hit_rate(group)

        surface_label = surface_labels.get(int(surface), str(surface))
        condition_label = condition_labels.get(int(condition), str(condition))

        breakdowns.append({
            "surface": surface_label,
            "track_condition": condition_label,
            "surface_code": int(surface),
            "track_condition_code": int(condition),
            "n_bets": hit_data["n_bets"],
            "n_hits": hit_data["n_hits"],
            "hit_rate": hit_data["hit_rate"],
            "roi": roi_data["roi"],
            "profit": roi_data["profit"],
        })

    # Sort by ROI descending
    breakdowns.sort(key=lambda x: x["roi"], reverse=True)
    return breakdowns


def _yearly_breakdown(
    picks: pd.DataFrame,
    bet_amount: float = 100,
) -> List[Dict[str, Any]]:
    """Calculate ROI/hit-rate breakdown by year.

    Args:
        picks: DataFrame with columns [race_date, actual_win, win_odds].
        bet_amount: Bet amount per race.

    Returns:
        List of dicts, each with year info and metrics.
    """
    breakdowns = []

    if "race_date" not in picks.columns:
        logger.warning("race_date column missing for yearly breakdown.")
        return breakdowns

    picks = picks.copy()
    picks["race_date"] = pd.to_datetime(picks["race_date"], errors="coerce")
    picks["year"] = picks["race_date"].dt.year

    for year, group in picks.groupby("year"):
        roi_data = _calc_roi(group, bet_amount)
        hit_data = _calc_hit_rate(group)

        breakdowns.append({
            "year": int(year),
            "n_bets": hit_data["n_bets"],
            "n_hits": hit_data["n_hits"],
            "hit_rate": hit_data["hit_rate"],
            "roi": roi_data["roi"],
            "profit": roi_data["profit"],
        })

    breakdowns.sort(key=lambda x: x["year"])
    return breakdowns


def _distance_breakdown(
    picks: pd.DataFrame,
    bet_amount: float = 100,
) -> List[Dict[str, Any]]:
    """Calculate ROI/hit-rate breakdown by distance category.

    Args:
        picks: DataFrame with columns [distance, actual_win, win_odds].
        bet_amount: Bet amount per race.

    Returns:
        List of dicts with distance category and metrics.
    """
    breakdowns = []

    if "distance" not in picks.columns:
        return breakdowns

    picks = picks.copy()

    def dist_cat(d):
        if pd.isna(d):
            return "不明"
        d = float(d)
        if d <= 1200:
            return "短距離(~1200m)"
        elif d <= 1600:
            return "マイル(~1600m)"
        elif d <= 2000:
            return "中距離(~2000m)"
        elif d <= 2400:
            return "中長距離(~2400m)"
        else:
            return "長距離(2500m~)"

    picks["dist_cat"] = picks["distance"].apply(dist_cat)

    for cat, group in picks.groupby("dist_cat"):
        roi_data = _calc_roi(group, bet_amount)
        hit_data = _calc_hit_rate(group)

        breakdowns.append({
            "distance_category": cat,
            "n_bets": hit_data["n_bets"],
            "n_hits": hit_data["n_hits"],
            "hit_rate": hit_data["hit_rate"],
            "roi": roi_data["roi"],
            "profit": roi_data["profit"],
        })

    breakdowns.sort(key=lambda x: x["roi"], reverse=True)
    return breakdowns


def run_backtest(
    predictions_df: pd.DataFrame,
    bet_amount: float = 100,
    top_n: int = 1,
) -> Dict[str, Any]:
    """Run a full backtest on model predictions.

    Calculates overall metrics and per-condition breakdowns.

    Args:
        predictions_df: DataFrame with columns:
            - race_key: Race identifier
            - horse_key: Horse identifier
            - pred_prob: Predicted probability
            - actual_win: Whether horse actually won (1/0)
            - win_odds: Win odds (optional, for ROI calc)
            - finish_order: Actual finish position
            - surface: Surface type (optional)
            - track_condition: Track condition (optional)
            - race_date: Race date (optional)
            - distance: Distance (optional)
        bet_amount: Amount to bet per race.
        top_n: Number of horses to select per race.

    Returns:
        Dict with overall metrics and breakdowns.
    """
    logger.info(
        "Running backtest: %d predictions, top-%d selection, %d yen/bet",
        len(predictions_df), top_n, bet_amount,
    )

    if predictions_df.empty:
        return {
            "summary": {
                "roi": 0.0,
                "hit_rate": 0.0,
                "n_races": 0,
                "n_bets": 0,
            },
            "condition_breakdown": [],
            "yearly_breakdown": [],
            "distance_breakdown": [],
        }

    # Select top predictions
    if top_n == 1:
        picks = _top1_per_race(predictions_df)
    else:
        picks = _topN_per_race(predictions_df, n=top_n)

    n_races = predictions_df["race_key"].nunique()

    # Overall metrics
    roi_data = _calc_roi(picks, bet_amount)
    hit_data = _calc_hit_rate(picks)

    # Confidence calibration: bin predictions and check actual win rate
    calibration = _calc_calibration(predictions_df)

    # Breakdowns
    cond_breakdown = _condition_breakdown(picks, bet_amount)
    year_breakdown = _yearly_breakdown(picks, bet_amount)
    dist_breakdown = _distance_breakdown(picks, bet_amount)

    # Compute reliability score (0-5 stars based on data quality & consistency)
    reliability = _compute_reliability(
        n_races=n_races,
        n_bets=hit_data["n_bets"],
        roi=roi_data["roi"],
        hit_rate=hit_data["hit_rate"],
        yearly=year_breakdown,
    )

    result = {
        "summary": {
            "roi": roi_data["roi"],
            "total_return": roi_data["total_return"],
            "total_bet": roi_data["total_bet"],
            "profit": roi_data["profit"],
            "hit_rate": hit_data["hit_rate"],
            "n_hits": hit_data["n_hits"],
            "n_bets": hit_data["n_bets"],
            "n_races": n_races,
            "reliability_stars": reliability,
        },
        "calibration": calibration,
        "condition_breakdown": cond_breakdown,
        "yearly_breakdown": year_breakdown,
        "distance_breakdown": dist_breakdown,
    }

    logger.info(
        "Backtest complete: ROI=%.2f%%, Hit rate=%.2f%%, %d bets over %d races",
        roi_data["roi"], hit_data["hit_rate"], hit_data["n_bets"], n_races,
    )

    return result


def _calc_calibration(
    df: pd.DataFrame,
    n_bins: int = 10,
) -> List[Dict[str, float]]:
    """Calculate prediction calibration (predicted vs actual win rate by bins).

    Args:
        df: DataFrame with columns [pred_prob, actual_win].
        n_bins: Number of bins.

    Returns:
        List of dicts with bin info.
    """
    if df.empty or "pred_prob" not in df.columns:
        return []

    df = df.copy()
    df["bin"] = pd.qcut(df["pred_prob"], q=n_bins, duplicates="drop")

    calibration = []
    for bin_label, group in df.groupby("bin", observed=True):
        calibration.append({
            "bin": str(bin_label),
            "predicted_avg": round(float(group["pred_prob"].mean()), 4),
            "actual_avg": round(float(group["actual_win"].mean()), 4),
            "count": len(group),
        })

    return calibration


def _compute_reliability(
    n_races: int,
    n_bets: int,
    roi: float,
    hit_rate: float,
    yearly: List[Dict[str, Any]],
) -> int:
    """Compute a reliability score (1-5 stars).

    Based on:
    - Data volume (more races = more reliable)
    - ROI consistency across years
    - Hit rate reasonableness

    Args:
        n_races: Total number of races.
        n_bets: Total number of bets.
        roi: Overall ROI.
        hit_rate: Overall hit rate.
        yearly: Yearly breakdown data.

    Returns:
        Score from 1 to 5.
    """
    score = 0

    # Data volume
    if n_races >= 500:
        score += 1
    if n_races >= 1000:
        score += 1

    # ROI not suspiciously high (overfitting indicator)
    if -50 < roi < 100:
        score += 1

    # Yearly consistency
    if len(yearly) >= 2:
        yearly_rois = [y["roi"] for y in yearly]
        roi_std = np.std(yearly_rois)
        # Check that most years are profitable or all years similar
        profitable_years = sum(1 for r in yearly_rois if r > 0)
        if profitable_years >= len(yearly) * 0.5:
            score += 1
        if roi_std < 30:
            score += 1

    # Minimum score of 1
    return max(1, min(5, score))
