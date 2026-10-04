#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
.venv/bin/python -c "import sys; assert sys.version_info >= (3, 11), 'Use Python 3.11 ou superior; recomendado 3.12.'"
if ! cmp -s requirements.txt .venv/mana-requirements.txt; then
  .venv/bin/python -m pip install -r requirements.txt
  cp requirements.txt .venv/mana-requirements.txt
fi
.venv/bin/python scripts/setup.py
exec .venv/bin/python scripts/launch.py
