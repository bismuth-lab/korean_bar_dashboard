#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
elif [ -x ".venv-macos/bin/python" ]; then
  PYTHON=".venv-macos/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
else
  PYTHON="python"
fi

"$PYTHON" export_public.py
"$PYTHON" export_static_public.py

mkdir -p docs
cp public/public_log.csv public/public_summary.json public/index.html docs/

git add public/public_log.csv public/public_summary.json public/index.html docs/public_log.csv docs/public_summary.json docs/index.html

if git diff --cached --quiet; then
  echo "No public dashboard changes to publish."
  exit 0
fi

git commit -m "Update public BarPass log"
git push
