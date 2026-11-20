# Week 2 Test Plan and Results (attack traffic and labeled datasets)

Only tests that were actually run are marked Pass. Tests needing a real `vcan0` are **Not run** until you run them on Ubuntu and fill in the result.

| ID | Test | How | Result |
|----|------|-----|--------|
| W2-01 | Automated unit tests (59) | `make test` | Pass (run in a CAN-less environment) |
| W2-02 | Dry-run reproducibility | same `--seed` twice gives identical CSV (`test_same_seed_gives_identical_output`) | Pass |
| W2-03 | Labels correct per attack type | `tests/test_attack_simulator.py` | Pass |
| W2-04 | missing_message ground truth | `*_suppressed.csv` + `attack_windows.csv`; test `test_suppressed_frames_are_reported_with_label_1` | Pass |
| W2-05 | Live transmit path (fake sender) | `tests/test_attack_cli_and_live.py` | Pass |
| W2-06 | Send failure handling and abort after 50 failures | same file | Pass |
| W2-07 | Invalid attack parameters rejected (exit 2) | same file | Pass |
| W2-08 | Observed-frame labeling | `tests/test_label_observed.py` | Pass |
| W2-09 | All 6 datasets generate | `python3 scripts/generate_datasets.py --duration 60` | Pass |
| W2-10 | Attack on real vcan0, monitor sees frames | `scripts/run_attack_demo.sh mixed 30` | Not run |
| W2-11 | compare_logs: sent vs observed counts per ID on vcan0 | output of W2-10 | Not run |
| W2-12 | Observed capture labeled, attack share plausible | `observed_attack_mixed_labeled.csv` | Not run |
| W2-13 | Injection visible in `candump vcan0` during window | manual | Not run |

Record real results for W2-10 to W2-13 here, with the date and the pasted compare table.
