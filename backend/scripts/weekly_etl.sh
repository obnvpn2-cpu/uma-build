#!/usr/bin/env bash
# Weekly ETL: postprocess EveryDB2 data + rebuild feature cache
# Run after updating data in EveryDB2 GUI.
#
# Usage:
#   cd backend && bash scripts/weekly_etl.sh
#   # or with custom DB path:
#   DB_PATH=path/to/jravan.db bash scripts/weekly_etl.sh

set -euo pipefail
cd "$(dirname "$0")/.."

DB="${DB_PATH:-data/jravan.db}"

if [[ ! -f "$DB" ]]; then
  echo "ERROR: Database not found at $DB" >&2
  echo "Run EveryDB2 to export data first, or set DB_PATH." >&2
  exit 1
fi

echo "=== UmaBuild Weekly ETL ==="
echo "DB: $DB"
echo ""

python scripts/postprocess_everydb2.py --db "$DB" --build-cache \
  --cache-output-years 5 --cache-history-buffer-years 5

echo ""
echo "--- Extracting upcoming races (Cloud Run ships this parquet) ---"
DB_PATH="$DB" python scripts/extract_upcoming.py

echo ""
echo "ETL complete: feature_table_cache + upcoming_races updated"
echo "Next: git add data/feature_table_cache.parquet data/upcoming_races.parquet && git commit && deploy"
