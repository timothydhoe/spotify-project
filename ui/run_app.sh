#!/usr/bin/env bash
# run_app.sh — Launch the Project R.E.M. Shiny app
#
# Usage:
#   ./ui/run_app.sh
#   ./ui/run_app.sh --port=8080
#   ./ui/run_app.sh --reload
#
# Windows: run this in Git Bash or WSL. See README.md.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

PORT=8000
HOST="127.0.0.1"
RELOAD=false

for arg in "$@"; do
    case $arg in
        --port=*)  PORT="${arg#*=}" ;;
        --host=*)  HOST="${arg#*=}" ;;
        --reload)  RELOAD=true ;;
        --help|-h)
            echo "Usage: ./ui/run_app.sh [OPTIONS]"
            echo ""
            echo "  --port=N    Port to listen on (default: 8000)"
            echo "  --host=X    Host to bind to (default: 127.0.0.1)"
            echo "  --reload    Enable hot-reload on file changes (dev mode)"
            echo ""
            echo "The app will open at http://$HOST:$PORT"
            exit 0
            ;;
        *)
            echo "Unknown option: $arg  (try --help)" >&2
            exit 1
            ;;
    esac
done

if ! command -v uv &>/dev/null; then
    echo "Error: uv not found. Run ./bootstrap.sh first." >&2
    exit 1
fi

SHINY_ARGS=(--port "$PORT" --host "$HOST")
$RELOAD && SHINY_ARGS+=(--reload)

echo "Starting app → http://$HOST:$PORT"
exec uv run shiny run ui/app.py "${SHINY_ARGS[@]}"
