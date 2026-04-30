"""Extract upcoming JRA races from local jravan.db into a small parquet.

Run this weekly (after EveryDB2 「今週データ B」) so the small parquet can
be committed to git and shipped via the Cloud Run image — production has
no jravan.db. Local dev still reads sqlite directly when present.

Usage:
    cd backend && python scripts/extract_upcoming.py
    DB_PATH=path/to/jravan.db python scripts/extract_upcoming.py
    LOOKAHEAD_DAYS=14 python scripts/extract_upcoming.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.future_prediction import load_upcoming_race_entries  # noqa: E402


def main() -> int:
    db_path = os.getenv("DB_PATH", str(ROOT / "data" / "jravan.db"))
    out_path = os.getenv(
        "UPCOMING_PARQUET_PATH",
        str(ROOT / "data" / "upcoming_races.parquet"),
    )
    lookahead = int(os.getenv("LOOKAHEAD_DAYS", "14"))

    if not os.path.exists(db_path):
        print(f"ERROR: DB not found at {db_path}", file=sys.stderr)
        return 1

    today = datetime.now().date()
    from_date = today.strftime("%Y-%m-%d")
    to_date = (today + timedelta(days=lookahead)).strftime("%Y-%m-%d")

    print(f"DB:        {db_path}")
    print(f"Output:    {out_path}")
    print(f"Window:    {from_date} → {to_date}")

    df = load_upcoming_race_entries(db_path, from_date=from_date, to_date=to_date)
    if df.empty:
        print("WARNING: 0 upcoming entries — writing empty parquet", file=sys.stderr)

    n_races = df["race_key"].nunique() if "race_key" in df.columns else 0
    print(f"Extracted: {len(df)} entries across {n_races} races")

    df.to_parquet(out_path, engine="pyarrow", index=False)
    size_kb = os.path.getsize(out_path) / 1024
    print(f"Wrote:     {out_path} ({size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
