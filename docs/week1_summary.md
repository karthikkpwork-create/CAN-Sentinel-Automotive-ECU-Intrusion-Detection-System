# Week 1 Summary

> **Template:** sections marked _(fill in)_ must be completed from your own test runs. Nothing below describes a test as passed until you record it.

## What Week 1 was intended to achieve
A reproducible virtual CAN lab where normal synthetic messages are generated, independently received, inspected and saved, as the baseline for later anomaly detection.

## What was implemented
* `scripts/setup_vcan.sh`: create/inspect/remove `vcanN` (refuses non-virtual interfaces).
* `src/simulator/normal_traffic_simulator.py` (+ `payload.py`): four invented ECU identities, configurable IDs/intervals/payload signals, seeded randomness, validation, structured logging, graceful shutdown, `--dry-run`.
* `src/capture/can_monitor.py`: Python raw-socket monitor, CSV dataset output.
* `c_src/can_capture.c`: C raw-socket capture with CSV output.
* `src/utils/compare_logs.py`: matches transmitted frames against observed frames.
* CSV schemas, config validation, 37 automated tests, documentation.
* Design decision: a SocketCAN raw socket is used instead of libpcap (reasoning in `week1_fundamentals.md`).

## What was tested
* In the build environment (no CAN support): unit tests, C compilation, dry-run reproducibility, error handling. See `week1_progress.md`.
* On your machine: _(fill in which of T01-T20 you ran and when)_

## Actual results
_(fill in: paste the compare table from `scripts/run_demo.sh`, counts, pass/fail summary from `week1_testing.md`)_

## Problems and solutions
_(fill in from `week1_progress.md`)_

## Limitations
Classical CAN only; invented IDs/payloads; software-scheduled timing; virtual bus (no electrical behaviour, bit timing or arbitration); results depend on your kernel's `vcan` support.

## Preparation for Week 2
Use `observed_normal_traffic.csv` as the baseline. Features already available: per-ID inter-arrival time, DLC, payload bytes. Reuse `SocketCanSender`, `PayloadGenerator` and the CSV schemas when adding controlled anomalous traffic. Keep the dry-run mode for reproducible dataset generation.
