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

python scripts/postprocess_everydb2.py --db "$DB" --build-cache

echo ""
echo "ETL complete: feature_table_cache updated"
echo "Next: deploy to Render (git push or manual deploy)"
