# ML sample datasets (simulator-generated, dry-run)
NOT captured from a real vcan0. Virtual clock starts at 1700000000. Schema: timestamp, ecu_name, message_name, can_id, can_id_hex, dlc, payload_hex, interval_s, status, source, label, attack_type.

| File | Use | Seed | Duration |
|---|---|---|---|
| normal_capture_train.csv | train on normal traffic | 42 | 600 s |
| normal_capture_validation.csv | normal hold-out, false-positive check | 7 | 180 s |
| validation_attacks_mixed.csv | labeled evaluation (label 0/1, attack_type) | 7 | 180 s |
| validation_attacks_mixed_suppressed.csv | frames the missing_message attack dropped (label=1) | 7 | 180 s |
| attack_windows.csv | ground-truth attack time windows | 7 | - |
| timestamp_sample_normal.csv / timestamp_sample_mixed.csv (+ _suppressed) | small format samples | 42 | 5 s / 10 s |

Suppressed frames never appear in the main CSV (they were not sent); evaluate missing_message with the _suppressed file or attack_windows.csv.
