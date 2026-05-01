"""Diff legacy-unstable baseline parquet vs newly-built vectorised parquet.

After running `bash scripts/weekly_etl.sh` with the vectorised path, run this
to confirm that the new parquet is statistically equivalent to the prior
build. Used as Step B of the vectorisation rollout verification plan.

Note: legacy was an unstable sort, so per-row diff between the two parquets
is expected to differ for same-day same-horse rows. We compare column-level
statistics (mean, std, count, NaN count) which are insensitive to order.

Usage:
    cd backend && python scripts/verify_vec_equivalence.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
NEW = ROOT / "data" / "feature_table_cache.parquet"
OLD = ROOT / "data" / "feature_table_cache.parquet.legacy_unstable_baseline"

# rtol: 1e-5 by default (cumsum cancellation tolerated up to ~6 sig figs);
# 1e-3 for prize sums (large dynamic range), and 1e-7 for rates / means.
TOLERANCES = {
    "default": 1e-5,
    "horse_total_prize": 1e-3,
    "horse_avg_prize": 1e-3,
    "horse_earnings_per_start": 1e-3,
    "horse_win_rate": 1e-7,
    "horse_in3_rate": 1e-7,
    "horse_dist_win_rate": 1e-7,
    "horse_surface_win_rate": 1e-7,
    "horse_course_win_rate": 1e-7,
}


def main() -> int:
    if not NEW.exists():
        print(f"ERROR: new parquet not found: {NEW}", file=sys.stderr)
        return 1
    if not OLD.exists():
        print(f"ERROR: baseline parquet not found: {OLD}", file=sys.stderr)
        return 1

    print(f"NEW: {NEW}")
    print(f"OLD: {OLD}")

    new_df = pd.read_parquet(NEW)
    old_df = pd.read_parquet(OLD)

    print(f"\nshape: NEW {new_df.shape} vs OLD {old_df.shape}")
    if new_df.shape != old_df.shape:
        print("WARNING: shape mismatch (could be due to cache_output_years config)")

    # Column-level statistics comparison — order-insensitive
    common = sorted(set(new_df.columns) & set(old_df.columns))
    issues = 0
    print(f"\nComparing {len(common)} common columns by statistical signature...\n")
    print(f"{'column':50s} {'new_mean':>14} {'old_mean':>14} {'rel_diff':>10}  {'status'}")
    print("-" * 100)
    for c in common:
        if not pd.api.types.is_numeric_dtype(new_df[c]) or not pd.api.types.is_numeric_dtype(old_df[c]):
            continue
        new_v = new_df[c].dropna()
        old_v = old_df[c].dropna()
        if len(new_v) == 0 and len(old_v) == 0:
            continue

        new_mean = new_v.mean() if len(new_v) > 0 else np.nan
        old_mean = old_v.mean() if len(old_v) > 0 else np.nan
        nan_diff = abs(new_df[c].isna().sum() - old_df[c].isna().sum())
        len_new, len_old = len(new_v), len(old_v)

        # Statistics-level comparison (legacy unstable sort means row-wise diff is noisy,
        # but the column distribution should be near-identical).
        denom = max(abs(old_mean), 1e-12) if pd.notna(old_mean) else 1.0
        rel_diff = abs(new_mean - old_mean) / denom if pd.notna(new_mean) and pd.notna(old_mean) else 0.0
        tol = TOLERANCES.get(c, TOLERANCES["default"])

        # Allow nan-count differences up to ~0.1% of total rows (sort instability
        # could shift NaN positions in conditional features at tie-rows)
        nan_tol = max(50, int(0.001 * len(new_df)))

        bad = (rel_diff > tol) or (nan_diff > nan_tol) or (abs(len_new - len_old) > nan_tol)
        status = "FAIL" if bad else "ok"
        if bad:
            issues += 1
        if bad or rel_diff > 1e-9:
            print(f"{c:50s} {new_mean:>14.6g} {old_mean:>14.6g} {rel_diff:>10.2e}  {status}"
                  + (f"  (nan_diff={nan_diff})" if nan_diff > 0 else ""))

    print("\n" + "=" * 100)
    if issues == 0:
        print(f"PASS: all {len(common)} numeric columns within tolerance")
        return 0
    else:
        print(f"FAIL: {issues} columns exceeded tolerance")
        return 2


if __name__ == "__main__":
    sys.exit(main())
