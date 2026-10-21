#!/usr/bin/env bash
# CAN-Sentinel demo runner (owner: Person A).
#
#   scripts/run_pipeline_demo.sh [seconds]          Week 1 live demo on vcan0 (normal traffic)
#   scripts/run_pipeline_demo.sh offline [options]  full pipeline WITHOUT vcan0:
#                                          simulate -> extract features -> train -> detect
#   scripts/run_pipeline_demo.sh --help
#
# Offline options:
#   --duration N   seconds of simulated traffic per dataset (default 60)
#   --seed N       random seed for the training data (default 1; test data uses N+1)
#   --model PATH   use an existing model file instead of training a temporary one
#   --keep         keep the temporary work folder (datasets, model) and print its path
#
# Environment: PYTHON (default python3), CONFIG (default config/config.example.json).
# Nothing here sends traffic to a real vehicle. Offline mode never touches vcan0 or
# models/; it works in a temporary folder that it deletes (only that folder) on exit.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"
CONFIG="${CONFIG:-config/config.example.json}"

usage() { sed -n '2,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }
die() { echo "ERROR: $*" >&2; exit 1; }

# ---------------------------------------------------------------- live (Week 1)
run_live() {
  local duration="$1"
  mkdir -p data/generated logs

  "$PY" -m src.capture.can_monitor --config "$CONFIG" --save --quiet &
  MON_PID=$!
  cleanup_live() { kill -INT "$MON_PID" 2>/dev/null || true; }
  trap cleanup_live EXIT

  sleep 1
  if ! kill -0 "$MON_PID" 2>/dev/null; then
    die "the monitor exited early (see message above). Is vcan0 up?  sudo scripts/setup_vcan.sh up"
  fi

  "$PY" -m src.simulator.normal_traffic_simulator --config "$CONFIG" --duration "$duration"

  sleep 1
  kill -INT "$MON_PID"
  wait "$MON_PID" || true
  trap - EXIT

  echo
  echo "=== Independent verification: sender log vs monitor dataset ==="
  "$PY" -m src.utils.compare_logs --config "$CONFIG"
}

# ---------------------------------------------------------------- offline pipeline
check_offline_prerequisites() {
  command -v "$PY" >/dev/null 2>&1 || die "'$PY' not found. Install Python 3 or set PYTHON=/path/to/python."
  local f
  for f in scripts/generate_datasets.py src/ml/extract_features.py src/detector/detector.py "$CONFIG"; do
    [ -f "$f" ] || die "required file missing: $f (are you on a branch that has the Week 1 files?)"
  done
  if ! "$PY" -c "import pandas, sklearn, joblib" >/dev/null 2>&1; then
    cat >&2 <<EOF
ERROR: pandas, scikit-learn and joblib are required for the detector.
Create a virtual environment once, then install the dependencies:
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements-detector.txt
Then run this script again (the venv's python is used when it is activated).
EOF
    exit 1
  fi
}

# Run one step quietly; show its output only if it fails.
run_step() {
  local label="$1"; shift
  echo "-> $label"
  if ! "$@" >"$WORK/step.log" 2>&1; then
    cat "$WORK/step.log" >&2
    die "step failed: $label"
  fi
}

run_offline() {
  local duration=60 seed=1 model="" keep=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --duration) [ $# -ge 2 ] || die "--duration needs a value"; duration="$2"; shift 2 ;;
      --seed)     [ $# -ge 2 ] || die "--seed needs a value"; seed="$2"; shift 2 ;;
      --model)    [ $# -ge 2 ] || die "--model needs a path"; model="$2"; shift 2 ;;
      --keep)     keep=1; shift ;;
      -h|--help)  usage; exit 0 ;;
      *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
  done
  [[ "$duration" =~ ^[1-9][0-9]*$ ]] || die "--duration must be a positive whole number"
  [[ "$seed" =~ ^[0-9]+$ ]] || die "--seed must be a whole number"
  [ -z "$model" ] || [ -f "$model" ] || die "model file not found: $model"

  check_offline_prerequisites

  WORK="$(mktemp -d)"   # the only thing this script ever deletes
  if [ "$keep" -eq 1 ]; then
    echo "Work folder kept at: $WORK"
  else
    trap 'rm -rf "$WORK"' EXIT
  fi

  echo "=== CAN-Sentinel offline demo (no vcan0, no real vehicle) ==="
  run_step "simulate normal + attack traffic for training (seed $seed, ${duration}s)" \
    "$PY" scripts/generate_datasets.py --config "$CONFIG" --output-dir "$WORK/train" \
      --duration "$duration" --seed "$seed"
  run_step "simulate a separate test set (seed $((seed + 1)))" \
    "$PY" scripts/generate_datasets.py --config "$CONFIG" --output-dir "$WORK/test" \
      --duration "$duration" --seed "$((seed + 1))"

  if [ -z "$model" ]; then
    model="$WORK/model.joblib"
    run_step "train the Isolation Forest on NORMAL traffic only" \
      "$PY" -m src.detector.detector train --normal-csv "$WORK/train/normal_traffic.csv" \
        --model "$model" --seed 42
  else
    echo "-> using existing model: $model"
  fi

  echo
  echo "=== Detection on mixed attack traffic ==="
  "$PY" -m src.detector.detector detect --csv "$WORK/test/mixed_traffic.csv" \
    --model "$model" --check-labels
  echo
  echo "=== False-alarm check on normal-only traffic ==="
  "$PY" -m src.detector.detector detect --csv "$WORK/test/normal_traffic.csv" \
    --model "$model" --check-labels --max-alerts 3

  cat <<'EOF'

Done. Notes:
  * The detector names the abused CAN ID, not the physical ECU that sent it.
  * Live detection from vcan0 is not implemented yet.
  * Dashboard (needs PyQt5, started separately):  python3 dashboard/dashboard.py
EOF
}

# ---------------------------------------------------------------- dispatch
case "${1:-}" in
  -h|--help) usage ;;
  offline)   shift; run_offline "$@" ;;
  "")        run_live 10 ;;
  *)
    [[ "$1" =~ ^[1-9][0-9]*$ ]] || { echo "Unknown argument: $1" >&2; usage >&2; exit 2; }
    run_live "$1"
    ;;
esac
