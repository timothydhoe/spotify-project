#!/usr/bin/env bash
# pipeline.sh — Run the Project R.E.M. analysis pipeline
#
# Thin wrapper around scripts/main.py that lets you pass participant codenames
# as positional arguments (no need to type --participants every time).
#
# Usage:
#   ./scripts/pipeline.sh --all
#   ./scripts/pipeline.sh bosbes peer kokosnoot
#   ./scripts/pipeline.sh --all --force
#   ./scripts/pipeline.sh --all --skip-extraction
#   ./scripts/pipeline.sh bosbes --skip-baseline --force
#
# Windows: run this in Git Bash or WSL. See README.md.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# ── Help ─────────────────────────────────────────────────────────────────────
if [ $# -eq 0 ] || [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
    echo "Usage: ./scripts/pipeline.sh [--all | CODENAME...] [OPTIONS]"
    echo ""
    echo "Participants:"
    echo "  bosbes  kokosnoot  limoen  peer  kiwi  watermeloen  aardbei  citroen"
    echo ""
    echo "Options:"
    echo "  --all                  Run for all participants"
    echo "  --force                Re-run even if outputs are up to date"
    echo "  --skip-extraction      Skip Stage 1 (raw exports → processed CSVs)"
    echo "  --skip-baseline        Skip Stage 2 (circadian baselines)"
    echo "  --skip-sessions        Skip Stage 3 (session analysis + significance)"
    echo ""
    echo "Examples:"
    echo "  ./scripts/pipeline.sh --all"
    echo "  ./scripts/pipeline.sh bosbes peer"
    echo "  ./scripts/pipeline.sh --all --force"
    echo "  ./scripts/pipeline.sh bosbes --skip-extraction"
    exit 0
fi

# ── Check uv ─────────────────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
    echo "Error: uv not found. Run ./bootstrap.sh first." >&2
    exit 1
fi

# ── Translate positional codenames → --participants ───────────────────────────
# Collect flags (--*) and non-flag args (participant codenames) separately.
PARTICIPANTS=()
FLAGS=()
for arg in "$@"; do
    if [[ "$arg" == --* ]]; then
        FLAGS+=("$arg")
    else
        PARTICIPANTS+=("$arg")
    fi
done

if [ ${#PARTICIPANTS[@]} -gt 0 ]; then
    # Positional codenames were given — inject --participants
    exec uv run python scripts/main.py --participants "${PARTICIPANTS[@]}" "${FLAGS[@]+"${FLAGS[@]}"}"
else
    # No positional args — pass everything through as-is (e.g. --all --force)
    exec uv run python scripts/main.py "${FLAGS[@]}"
fi
