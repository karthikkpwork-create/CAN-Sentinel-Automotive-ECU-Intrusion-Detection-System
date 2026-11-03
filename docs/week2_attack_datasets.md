# Week 2: Attack traffic simulator and labeled datasets

## Attack types
| attack_type | What it does | Rows labeled 1 |
|---|---|---|
| injection | frames for a known ID (default 0x100) every 5 ms | injected frames |
| unknown_id | frames with an unauthorized ID (default 0x7FF) every 50 ms | injected frames |
| payload_tampering | normal ID with out-of-range signal values | tampered frames |
| missing_message | the target ID stops transmitting for the window | none in main CSV; see `*_suppressed.csv` and `attack_windows.csv` |
| mixed | the four attacks in sequence with clean gaps | as above |
| none | normal baseline only | none |

## Commands
```bash
python3 -m src.simulator.attack_traffic_simulator --dry-run --attack mixed --duration 60 --seed 42 --output data/generated/mixed_traffic.csv
python3 scripts/generate_datasets.py --duration 60 --seed 42     # 6 datasets + attack_windows.csv + *_suppressed.csv
make test                                                      # includes missing-message ground-truth tests
```

## Live run on vcan0 (real captures)
```bash
sudo scripts/setup_vcan.sh up
scripts/run_attack_demo.sh mixed 30      # monitor -> attack simulator -> compare -> label observed frames
```
Outputs in `data/generated/`: `attack_sender_<attack>.csv` (what was sent), `observed_attack_<attack>.csv` (what the monitor saw),
`observed_attack_<attack>_labeled.csv` (observed frames with `label` / `attack_type`, via `src/utils/label_observed.py`).
An observed frame with no matching sender row is labeled `1 / unmatched`; sent frames never observed are counted in the summary line.
For `missing_message` and `mixed`, the simulator also writes `<output>_suppressed.csv` next to the sender CSV.

## Input checks (exit code 2 with a clear message)
Attack start after the end of the run; `--target-id` not in the config (for payload_tampering / missing_message / mixed);
IDs outside 0x000-0x7FF; `--injection-interval-ms <= 0`; `--attack-duration <= 0`.

## Dataset columns
`timestamp, ecu_name, message_name, can_id, can_id_hex, dlc, payload_hex, interval_s, status, source, label, attack_type`
`*_suppressed.csv`: `timestamp, can_id, can_id_hex, label, attack_type`
`attack_windows.csv`: `dataset, attack_type, start_s, end_s, start_timestamp, end_timestamp, target_can_id_hex`

## Changes in Week 2 follow-up
- Optional `on_suppressed` callback plus suppressed/windows files so missing_message has ground truth (main CSV output unchanged).
- CLI input validation, `_suppressed.csv` from the CLI, `label_observed.py`, `run_attack_demo.sh`.
- Tests for the live transmit path (fake sender), send failures, abort after 50 consecutive failures, stop signal, CLI validation, reproducibility.

## Limitations
- Dry-run data is generated, not captured on a real vcan0 (run `scripts/run_demo.sh` on Ubuntu for real captures).
- Invented IDs and signals; classical CAN only.
