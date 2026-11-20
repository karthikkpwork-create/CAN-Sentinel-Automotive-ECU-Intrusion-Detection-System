#!/usr/bin/env bash
# End-to-end Week 2 demo on a real vcan0: monitor -> attack simulator -> compare -> label observed frames.
#
#   scripts/run_attack_demo.sh [attack] [seconds]     (default: mixed 30; vcan0 must be up)
#   attack = none | injection | unknown_id | payload_tampering | missing_message | mixed
set -euo pipefail
cd "$(dirname "$0")/.."

ATTACK="${1:-mixed}"
DURATION="${2:-30}"
CONFIG="${CONFIG:-config/config.example.json}"
PY="${PYTHON:-python3}"
SENT="data/generated/attack_sender_${ATTACK}.csv"
OBS="data/generated/observed_attack_${ATTACK}.csv"
LABELED="data/generated/observed_attack_${ATTACK}_labeled.csv"

mkdir -p data/generated logs

"$PY" -m src.capture.can_monitor --config "$CONFIG" -o "$OBS" --quiet &
MON_PID=$!
cleanup() { kill -INT "$MON_PID" 2>/dev/null || true; }
trap cleanup EXIT

sleep 1
if ! kill -0 "$MON_PID" 2>/dev/null; then
  echo "ERROR: the monitor exited early. Is vcan0 up?  sudo scripts/setup_vcan.sh up" >&2
  exit 1
fi

"$PY" -m src.simulator.attack_traffic_simulator --config "$CONFIG" --attack "$ATTACK" --duration "$DURATION" --output "$SENT"

sleep 1
kill -INT "$MON_PID"
wait "$MON_PID" || true
trap - EXIT

echo
echo "=== Independent verification: sender log vs monitor dataset ==="
"$PY" -m src.utils.compare_logs --sent "$SENT" --observed "$OBS" || true

echo
echo "=== Labeling observed frames from the sender log ==="
"$PY" -m src.utils.label_observed --sent "$SENT" --observed "$OBS" --output "$LABELED"
