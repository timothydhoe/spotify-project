#!/usr/bin/env bash
# bootstrap.sh — First-time setup for Project R.E.M.
#
# Run this once after cloning the repository to install dependencies
# and create the expected data directory structure.
#
# Usage:
#   ./bootstrap.sh          # Full setup
#   ./bootstrap.sh --check  # Verify setup without making changes
#
# Windows: run this in Git Bash or WSL. See README.md.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

# ── Colors (disabled when not a TTY or NO_COLOR is set) ──────────────────────
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    GRN='\033[0;32m' YLW='\033[1;33m' RED='\033[0;31m' BLD='\033[1m' RST='\033[0m'
else
    GRN='' YLW='' RED='' BLD='' RST=''
fi

ok()     { echo -e "${GRN}✓${RST} $*"; }
warn()   { echo -e "${YLW}!${RST} $*"; }
fail()   { echo -e "${RED}✗${RST} $*" >&2; }
header() { echo -e "\n${BLD}$*${RST}"; }

CHECK_ONLY=false
for arg in "$@"; do
    case $arg in
        --check) CHECK_ONLY=true ;;
        --help|-h)
            echo "Usage: ./bootstrap.sh [--check]"
            echo ""
            echo "  (no args)  Install dependencies and create data directories"
            echo "  --check    Verify setup without making any changes"
            echo ""
            echo "After setup, use:"
            echo "  ./scripts/pipeline.sh --all          # Full analysis pipeline"
            echo "  ./scripts/pipeline.sh bosbes peer    # Specific participants"
            echo "  ./scripts/playlists.sh <codename>    # Generate playlists"
            echo "  ./ui/run_app.sh                      # Launch the Shiny app"
            exit 0
            ;;
    esac
done

header "Project R.E.M. — Setup"

# ── 1. Check uv ──────────────────────────────────────────────────────────────
header "Checking uv..."
if command -v uv &>/dev/null; then
    ok "uv $(uv --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')"
else
    fail "uv not found."
    echo "  Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "  Or:      pip install uv"
    exit 1
fi

# ── 2. Sync dependencies ─────────────────────────────────────────────────────
if ! $CHECK_ONLY; then
    header "Installing dependencies..."
    uv sync
    ok "Dependencies installed"
fi

# ── 3. Check Python version ──────────────────────────────────────────────────
PY_VER=$(uv run python --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 12 ]; }; then
    fail "Python 3.12+ required, found Python $PY_VER"
    exit 1
fi
ok "Python $PY_VER"

# ── 4. Create data directories ───────────────────────────────────────────────
header "Checking data directories..."
PARTICIPANTS=(bosbes kokosnoot limoen peer kiwi watermeloen aardbei citroen)
DIRS=(
    "data/checkins"
    "data/playlists"
    "data/analysis"
)
for p in "${PARTICIPANTS[@]}"; do
    DIRS+=(
        "data/wearables/$p/raw/export"
        "data/wearables/$p/processed"
    )
done

MISSING=0
for d in "${DIRS[@]}"; do
    if [ ! -d "$d" ]; then
        if $CHECK_ONLY; then
            warn "Missing: $d"
            MISSING=$((MISSING + 1))
        else
            mkdir -p "$d"
        fi
    fi
done

if $CHECK_ONLY && [ $MISSING -gt 0 ]; then
    warn "$MISSING directories missing — run ./bootstrap.sh to create them"
else
    ok "Data directories ready"
fi

# ── 5. Check-in CSV ──────────────────────────────────────────────────────────
CHECKIN="data/checkins/Check-in_formulier_REM.csv"
if [ -f "$CHECKIN" ]; then
    ok "Check-in CSV found"
else
    warn "Check-in CSV not found at $CHECKIN"
    echo "     Place the Google Forms export there before running the pipeline."
fi

# ── Done ─────────────────────────────────────────────────────────────────────
header "Setup complete."
echo ""
echo "Place your data files:"
echo "  data/playlists/<codename>/             ← Exportify CSVs"
echo "  data/wearables/<codename>/raw/export/  ← Garmin ZIPs or Huawei JSONs"
echo "  data/checkins/Check-in_formulier_REM.csv"
echo ""
echo "Then run:"
echo "  ./scripts/pipeline.sh --all       # Full analysis pipeline"
echo "  ./scripts/playlists.sh <codename> # Generate playlists"
echo "  ./ui/run_app.sh                   # Launch the Shiny app"
