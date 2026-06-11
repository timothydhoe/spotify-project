#!/usr/bin/env bash
# playlists.sh — Generate Spotify playlists for a participant
#
# Wraps scripts/playlists/spotify_cli.py with a friendlier interface.
# All extra flags are passed through to the CLI unchanged.
#
# Usage:
#   ./scripts/playlists.sh <codename>                 # Full workflow (default: all)
#   ./scripts/playlists.sh <codename> generate        # Single step
#   ./scripts/playlists.sh <codename> generate --calm-tempo-max 95
#
# Windows: run this in Git Bash or WSL. See README.md.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

KNOWN_PARTICIPANTS=(bosbes kokosnoot limoen peer kiwi watermeloen aardbei citroen)

# ── Help / no args ────────────────────────────────────────────────────────────
if [ $# -eq 0 ] || [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
    echo "Usage: ./scripts/playlists.sh <codename> [command] [options]"
    echo ""
    echo "Commands (default: all):"
    echo "  all       Full workflow: prepare → generate → analyse"
    echo "  prepare   Combine and clean Exportify CSV exports"
    echo "  generate  Filter songs by BPM/energy, apply ISO ordering"
    echo "  analyse   Validate output and generate visualizations"
    echo ""
    echo "Known participants: ${KNOWN_PARTICIPANTS[*]}"
    echo ""
    echo "Options are passed through to spotify_cli.py, e.g.:"
    echo "  --calm-tempo-max 95 --upbeat-energy-min 0.7"
    echo ""
    echo "Examples:"
    echo "  ./scripts/playlists.sh bosbes"
    echo "  ./scripts/playlists.sh bosbes generate"
    echo "  ./scripts/playlists.sh bosbes generate --calm-tempo-max 95"
    echo ""
    echo "Full CLI help:"
    echo "  uv run python scripts/playlists/spotify_cli.py --help"
    exit 0
fi

# ── Check uv ─────────────────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
    echo "Error: uv not found. Run ./bootstrap.sh first." >&2
    exit 1
fi

# ── Parse args ────────────────────────────────────────────────────────────────
CODENAME="$1"
shift

# Second positional arg is the command (if it doesn't start with --)
COMMAND="all"
if [ $# -gt 0 ] && [[ "$1" != --* ]]; then
    COMMAND="$1"
    shift
fi

# ── Warn if data directory is missing ────────────────────────────────────────
if [ ! -d "data/playlists/$CODENAME" ]; then
    echo "Warning: data/playlists/$CODENAME not found — creating it."
    echo "         Place Exportify CSVs there before running 'prepare'."
    mkdir -p "data/playlists/$CODENAME"
fi

# ── Run ──────────────────────────────────────────────────────────────────────
exec uv run python scripts/playlists/spotify_cli.py "$COMMAND" "$CODENAME" "$@"
