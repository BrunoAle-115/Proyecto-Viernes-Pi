#!/usr/bin/env bash
# ==============================================================================
# V.I.E.R.N.E.S. - Lanzador Directo
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

export PYTHONPATH="$PROJECT_DIR"
python3 viernes/main.py
