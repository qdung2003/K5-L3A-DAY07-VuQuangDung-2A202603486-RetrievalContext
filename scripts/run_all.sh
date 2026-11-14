#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
stage="${1:-verify}"
results_root="${2:-results}"
case "$stage" in
  dev) python scripts/experiment.py dev --resume --results-root "$results_root" ;;
  select) python scripts/experiment.py select --resume --results-root "$results_root" ;;
  test) python scripts/experiment.py test --resume --results-root "$results_root" ;;
  cost) python scripts/cost_report.py --results-root "$results_root" ;;
  verify) python -m unittest discover -s tests -v
          python scripts/verify_submission.py --results-root "$results_root" ;;
  *) echo "Usage: bash scripts/run_all.sh dev|select|test|verify|cost [results-root]" >&2; exit 2 ;;
esac
