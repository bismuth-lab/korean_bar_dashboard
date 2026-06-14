#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

VENV_DIR=".venv"
if [ ! -f "$VENV_DIR/bin/activate" ]; then
  VENV_DIR=".venv-macos"
fi

if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install -r requirements.txt
streamlit run app.py --server.port 8502
