#!/bin/sh
set -eu
python scripts/bootstrap_env.py
exec gunicorn --bind "0.0.0.0:${PORT:-8080}" --workers 1 --threads 4 --timeout 60 --access-logfile - --error-logfile - run:app
