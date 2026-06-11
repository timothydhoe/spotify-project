#!/usr/bin/env bash
# scripts/notebooks.sh — Run all 4 ML notebooks to regenerate app outputs.
#
# Run this after ./scripts/pipeline.sh --all has completed.
# Saved models (models/) are committed to git so this is fast by default
# (~1–3 min total): notebooks load existing fitted models and re-export
# all CSVs, JSON summaries, and plots that the Shiny app reads.
#
# Usage:
#   ./scripts/notebooks.sh              # regenerate outputs, reuse saved models
#   ./scripts/notebooks.sh --fresh      # refit models from scratch (~10 min)
#   ./scripts/notebooks.sh --help

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# ── Argument parsing ──────────────────────────────────────────────────────────
FRESH=false
for arg in "$@"; do
  case "$arg" in
    --fresh)   FRESH=true ;;
    --help|-h)
      echo "Usage: ./scripts/notebooks.sh [--fresh]"
      echo ""
      echo "  (no flags)   Regenerate app outputs using saved models (fast, default)"
      echo "  --fresh      Refit all models from scratch — use when underlying data"
      echo "               has changed substantially (~10 min, requires GPU/CPU time)"
      exit 0
      ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

NB_DIR="$ROOT/notebooks/ml"
NOTEBOOKS=(
  "1_circadian_ml.ipynb"
  "2_bayesian_recommender.ipynb"
  "3_music_class_supervised.ipynb"
  "4_music_class_unsupervised.ipynb"
)

# ── Pre-flight checks ─────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  R.E.M. Notebook Pipeline"
echo "============================================================"

if ! command -v uv &>/dev/null; then
  echo "✗ uv not found — run ./bootstrap.sh first." >&2
  exit 1
fi

FM="$ROOT/data/analysis/circadian_baselines/feature_matrix.csv"
if [ ! -f "$FM" ]; then
  echo "✗ feature_matrix.csv not found at:" >&2
  echo "    $FM" >&2
  echo "  Run ./scripts/pipeline.sh --all first to build biometric data." >&2
  exit 1
fi

echo "  Notebooks : ${#NOTEBOOKS[@]}"
if $FRESH; then
  echo "  Mode      : --fresh (refit all models from scratch)"
else
  echo "  Mode      : fast (REUSE_MODEL=True — loads committed model artefacts)"
fi
echo ""

# ── Helper: temporarily patch REUSE_MODEL in a notebook for --fresh ──────────
_patch_notebook() {
  local src="$1" dst="$2"
  python3 - "$src" "$dst" <<'PYEOF'
import json, sys
src, dst = sys.argv[1], sys.argv[2]
with open(src) as f:
    nb = json.load(f)
for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        cell['source'] = [
            line.replace('REUSE_MODEL = True', 'REUSE_MODEL = False')
            for line in cell['source']
        ]
        # clear previous outputs so nbconvert doesn't skip cells
        cell['outputs'] = []
        cell['execution_count'] = None
with open(dst, 'w') as f:
    json.dump(nb, f)
PYEOF
}

# ── Run each notebook ─────────────────────────────────────────────────────────
FAILED=()
TOTAL_START=$SECONDS

for nb in "${NOTEBOOKS[@]}"; do
  nb_path="$NB_DIR/$nb"
  echo "------------------------------------------------------------"
  echo "  $nb"
  echo "------------------------------------------------------------"
  START=$SECONDS

  if $FRESH; then
    tmp="${nb_path%.ipynb}.tmp_fresh.ipynb"
    _patch_notebook "$nb_path" "$tmp"
    run_path="$tmp"
  else
    run_path="$nb_path"
  fi

  if uv run jupyter nbconvert \
      --to notebook \
      --execute \
      --inplace \
      --ExecutePreprocessor.timeout=1800 \
      --ExecutePreprocessor.kernel_name=python3 \
      "$run_path" 2>&1; then
    ELAPSED=$((SECONDS - START))
    echo "  ✓ Done in ${ELAPSED}s"
  else
    ELAPSED=$((SECONDS - START))
    echo "  ✗ FAILED after ${ELAPSED}s"
    FAILED+=("$nb")
  fi

  # Remove temp file if used
  $FRESH && rm -f "${nb_path%.ipynb}.tmp_fresh.ipynb" || true
  echo ""
done

# ── Summary ───────────────────────────────────────────────────────────────────
TOTAL=$((SECONDS - TOTAL_START))
echo "============================================================"
echo "  Summary  (${TOTAL}s total)"
echo "============================================================"
for nb in "${NOTEBOOKS[@]}"; do
  if printf '%s\n' "${FAILED[@]:-}" | grep -qx "$nb"; then
    echo "  ✗  $nb"
  else
    echo "  ✓  $nb"
  fi
done
echo ""

if [ ${#FAILED[@]} -eq 0 ]; then
  echo "  All notebooks complete."
  echo "  App outputs written to data/analysis/."
  echo ""
  echo "  Launch the app:  ./ui/run_app.sh"
else
  echo "  ${#FAILED[@]} notebook(s) failed — check output above." >&2
  exit 1
fi
