# CAN-Sentinel Dashboard (Role D)

This directory contains the dashboard and monitoring layer for the CAN-Sentinel project. It is the Role D workstream: the interface that lets a user inspect CAN traffic, review activity patterns, and see alerts raised by the rule-based intrusion detector.

The dashboard is designed for a lab environment. It can work from saved CSV captures without a physical interface, and it can also connect to a live virtual CAN feed (`vcan0`) through the local bridge.

## Role D scope

Role D is responsible for the user-facing monitoring console. In the project plan, that includes:

- loading synthetic CAN traffic from CSV files,
- displaying frames and payload bytes with timestamps,
- monitoring CAN IDs and message rates,
- learning a baseline for normal traffic,
- triggering alerts when suspicious behavior appears,
- presenting alerts in a readable dashboard for demos and validation.

This matches the team plan in the project brief:

- Days 1 to 5: data generation, attack scenarios, and feature setup
- Days 6 to 10: detector logic, dashboard integration, and demo validation
- Day 11 onward: testing, final reporting, and presentation

## What is in this directory

- `dashboard.py` — main PyQt dashboard window
- `frame_table.py` — lightweight standalone CSV frame viewer
- `detector.py` — baseline rule-based intrusion detector
- `id_monitor.py` — per-ID activity tracking
- `id_chart.py` — busiest-ID and activity charts
- `bridge_client.py` — client that connects to the live `vcan0` bridge
- `vcan_bridge.py` — optional TCP bridge for reading live SocketCAN traffic
- `csv_export.py` — live CSV recording and export helpers
- `theme.py` and `style.py` — dark/light theme support and styling
- `requirements.txt` — Python dependencies for the dashboard UI
- `captures/` — saved capture files and demo outputs

## Features

The dashboard includes:

- CSV frame loading for saved CAN traces
- live traffic connection to a virtual `vcan0` interface
- CAN-ID filtering and byte-level frame inspection
- frame and alert counters
- per-ID activity monitoring
- message-rate and busiest-ID charts
- alerts table with time, ID, type, and score
- dark/light theme toggle
- export of live captures to CSV
- detector on/off and learning state controls

The UI is intended for demonstration and validation rather than production automotive use.

## Quick start

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r dashboard/requirements.txt
```

Launch the main dashboard:

```bash
python dashboard/dashboard.py
```

Load a sample capture immediately:

```bash
python dashboard/dashboard.py data/samples/sample_attack_dry_run_seed42.csv
```

Run only the simple table viewer:

```bash
python dashboard/frame_table.py data/samples/sample_attack_dry_run_seed42.csv
```

## Detector behavior

The detector is implemented as a rule-based heuristic engine rather than a machine-learning model.

It can:

- learn a baseline from normal traffic,
- flag unknown CAN IDs,
- detect unusually fast bursts,
- detect unexpected payload changes,
- detect missing messages over time.

The dashboard exposes the detector state via the `Detector` button. It cycles through off, learning, and active detection modes. This makes the logic easy to inspect and explain in a lab demo.

## Live dashboard flow

To use the live feed, a Linux or WSL environment with SocketCAN is required.

```bash
python -m pip install python-can
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set up dev vcan0
```

Start the bridge in one terminal:

```bash
python dashboard/vcan_bridge.py
```

Then launch the dashboard and press `Start live`:

```bash
python dashboard/dashboard.py
```

The bridge listens on TCP port `8765`, and the dashboard connects to `127.0.0.1:8765` by default. This is a lab-only setup and should be used only with a virtual CAN interface, never with a real vehicle bus.

## Notes for the team

The project uses a branch-per-person workflow and merges through pull requests rather than pushing directly to `main`.

The dashboard acts as the validation and demo surface for the attack simulation and detection pipeline. Its purpose is to make the synthetic CAN traffic and alert logic understandable, visible, and testable.

For the full project setup and simulator commands, see the main project README in the repository root.
