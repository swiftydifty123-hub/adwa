#!/usr/bin/env sh
# One-click launcher for macOS / Linux. Usage: ./optimize.sh [command] [options]
cd "$(dirname "$0")" || exit 1
PY=$(command -v python3 || command -v python)
[ -z "$PY" ] && { echo "Python 3 is required: https://www.python.org/downloads/"; exit 1; }
"$PY" -c "import psutil" 2>/dev/null || "$PY" -m pip install --user -q -r requirements.txt
exec "$PY" -m optimizer "$@"
