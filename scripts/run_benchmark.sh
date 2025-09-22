#!/usr/bin/env bash
set -euo pipefail

# Tokkit Benchmark Runner
#
# Usage:
#   ./scripts/run_benchmark.sh                # default: fastapi/fastapi
#   ./scripts/run_benchmark.sh owner/repo     # any GitHub repo

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Activate project venv if present
if [ -f "$ROOT/.venv/bin/activate" ]; then
    source "$ROOT/.venv/bin/activate"
fi

echo "Building tokkit (maturin develop)..."
maturin develop --quiet 2>&1 | tail -1
echo ""

exec python -m tokkit_benchmark "$@"
