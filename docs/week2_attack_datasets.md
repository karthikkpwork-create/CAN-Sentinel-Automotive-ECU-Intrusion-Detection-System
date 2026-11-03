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

## Dataset columns
`timestamp, ecu_name, message_name, can_id, can_id_hex, dlc, payload_hex, interval_s, status, source, label, attack_type`
`*_suppressed.csv`: `timestamp, can_id, can_id_hex, label, attack_type`
`attack_windows.csv`: `dataset, attack_type, start_s, end_s, start_timestamp, end_timestamp, target_can_id_hex`

## Change in this update
Added an optional `on_suppressed` callback and the suppressed/windows files so missing_message has ground truth. The main CSV output is byte-identical to before.

## Limitations
- Dry-run data is generated, not captured on a real vcan0 (run `scripts/run_demo.sh` on Ubuntu for real captures).
- Invented IDs and signals; classical CAN only.
