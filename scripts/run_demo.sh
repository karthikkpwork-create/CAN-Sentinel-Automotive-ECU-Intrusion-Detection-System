#!/usr/bin/env bash
# End-to-end Week 1 demo: start the monitor, run the simulator, then compare.
#
#   scripts/run_demo.sh [seconds]        (default 10; vcan0 must already be up)
#
# The monitor is started FIRST so it cannot miss the first frames.
set -euo pipefail
cd "$(dirname "$0")/.."

DURATION="${1:-10}"
CONFIG="${CONFIG:-config/config.example.json}"
PY="${PYTHON:-python3}"

mkdir -p data/generated logs

"$PY" -m src.capture.can_monitor --config "$CONFIG" --save --quiet &
MON_PID=$!
cleanup() { kill -INT "$MON_PID" 2>/dev/null || true; }
trap cleanup EXIT

sleep 1
if ! kill -0 "$MON_PID" 2>/dev/null; then
  echo "ERROR: the monitor exited early (see message above). Is vcan0 up?  sudo scripts/setup_vcan.sh up" >&2
  exit 1
fi

"$PY" -m src.simulator.normal_traffic_simulator --config "$CONFIG" --duration "$DURATION"

sleep 1
kill -INT "$MON_PID"
wait "$MON_PID" || true
trap - EXIT

echo
echo "=== Independent verification: sender log vs monitor dataset ==="
"$PY" -m src.utils.compare_logs --config "$CONFIG"
