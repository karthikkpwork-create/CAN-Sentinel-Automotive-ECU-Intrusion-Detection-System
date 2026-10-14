# CAN-Sentinel-Automotive-ECU-Intrusion-Detection-System
CAN-Sentinel is an automotive cybersecurity system that monitors CAN bus communication between Electronic Control Units (ECUs). It detects suspicious activities such as message injection, replay attacks, and denial-of-service attacks using rule-based techniques and machine learning to improve vehicle security.

13/08/2026
# CAN-Sentinel: Automotive ECU Intrusion Detection System

## Project Overview
CAN-Sentinel is an automotive cybersecurity project focused on analyzing CAN traffic to help identify potentially suspicious communication between Electronic Control Units (ECUs).

## My Contribution
Developing a CSV-based CAN Frame Viewer using Python and PyQt5 to display CAN frames in a table for easier inspection and analysis.

## Technologies Used
- Python
- PyQt5
- CSV
- Git and GitHub

## Key Features
- Load CAN frame data from CSV files.
- Display timestamps, CAN IDs, DLC, and data bytes.
- Generate synthetic CAN frames for testing.
- Prepare the dashboard for future integration with intrusion detection results.

## Sample Data
Synthetic CAN data is used for initial testing. It does not represent real vehicle traffic.

## How to Run
1. Activate the Python virtual environment.
2. Install PyQt5: `python -m pip install PyQt5`
3. Run the dashboard: `python dashboard/frame_table.py`
4. Click **Open CSV** and select a dataset.

## Status
The CSV-based dashboard is under development. Integration with intrusion detection components will follow as the project progresses.
# CAN-Sentinel: Automotive ECU Intrusion Detection System

A four-week automotive cybersecurity project. **This repository currently contains Week 1 only**: a controlled *virtual* CAN environment that generates, transmits, independently captures and saves **normal synthetic** CAN traffic. No real vehicle, ECU or CAN hardware is involved or needed.

## Overview

Automotive ECUs talk to each other over a CAN bus. To detect abnormal (possibly malicious) messages later, we first need a trustworthy picture of what *normal* traffic looks like. Week 1 builds that baseline in a lab on one Linux machine using SocketCAN's virtual interface `vcan0`.

## Status: implemented vs planned

| Item | Status |
|------|--------|
| Virtual CAN setup script (`scripts/setup_vcan.sh`) | Implemented |
| Normal traffic simulator (Python) | Implemented |
| Python capture monitor | Implemented |
| C capture program (SocketCAN raw socket) | Implemented |
| CSV datasets (sender log, observed dataset) + comparison tool | Implemented |
| Unit tests (no CAN needed) | Implemented |
| Tests on a real `vcan0` | **To be run by you**, see `docs/week1_testing.md` |
| Anomalous / attack traffic | Planned (Week 2) |
| Isolation Forest anomaly detection | Planned (Week 3) |
| Integration + PyQt dashboard | Planned (Week 4) |

## Week 1 objectives

1. Create and verify `vcan0`.
2. Send and receive a manual test frame.
3. Generate normal synthetic traffic from simulated ECUs (engine, dashboard, temperature sensor, battery monitor). Their IDs and payloads are **invented for this lab, not from any real vehicle**.
4. Capture the traffic with an independent process (Python and C).
5. Save a reproducible dataset for Week 2.

## Architecture

```
  Simulator (Python)                       Monitors (separate processes)
  ┌───────────────────┐                   ┌────────────────────────────┐
  │ engine_ecu   0x100│                   │ can_monitor.py  -> CSV     │
  │ dashboard    0x200│──►  vcan0  ──────►│ can_capture (C) -> CSV     │
  │ temperature  0x300│  (kernel virtual  │ candump (can-utils)        │
  │ battery      0x400│   CAN interface)  └────────────────────────────┘
  └─────────┬─────────┘
            ▼
     sender_log.csv                         observed_normal_traffic.csv
     ("generated/transmitted")              ("independently observed")  <-- Week 2 input
```

Three counts are kept apart: **generated** (payload built), **transmitted** (kernel accepted the send), **observed** (another process read it). `src/utils/compare_logs.py` checks the last against the second.

## Technologies

Linux SocketCAN, `vcan`, `can-utils`, Python 3 (standard library only), C (GCC, raw SocketCAN socket), Git/GitHub, CSV/JSON. About libpcap: see "Capture method" in `docs/week1_fundamentals.md`.

## Prerequisites

Ubuntu 22.04/24.04 (native or VM) with sudo. Windows PowerShell alone cannot do this; use an Ubuntu VM. Default WSL2 kernels often lack `vcan`.

```bash
sudo apt update
sudo apt install -y build-essential git python3 python3-venv iproute2 can-utils linux-libc-dev
```

## Installation

```bash
git clone <your-repo-url> CAN-Sentinel && cd CAN-Sentinel
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt     # no third-party packages needed in Week 1
make test                           # unit tests, no CAN needed
make c                              # builds bin/can_capture
```

## Setup: virtual CAN

```bash
sudo scripts/setup_vcan.sh up       # create and bring up vcan0
scripts/setup_vcan.sh status        # inspect it
sudo scripts/setup_vcan.sh down     # remove it when finished
```

## Manual CAN test

```bash
# Terminal 1 (start first)        # Terminal 2
candump vcan0                     cansend vcan0 123#DEADBEEF
```
Expected (spacing varies): `vcan0  123   [4]  DE AD BE EF`.

## Simulator usage

```bash
python3 -m src.simulator.normal_traffic_simulator --config config/config.example.json --duration 10
python3 -m src.simulator.normal_traffic_simulator --dry-run --duration 3    # no interface needed
```
Options: `--interface`, `--duration`, `--seed`, `--output`, `--dry-run`, `--log-level`. Every setting in the JSON config is explained in `docs/week1_setup.md`.

## Capture usage

```bash
python3 -m src.capture.can_monitor --config config/config.example.json --save   # Python
./bin/can_capture -i vcan0 -o data/generated/observed_c.csv                      # C
```

One-command demo (monitor first, then simulator, then comparison):

```bash
scripts/run_demo.sh 10
```

## Dataset format

* `data/generated/sender_log.csv` (from the simulator): `timestamp, ecu_name, message_name, can_id, can_id_hex, dlc, payload_hex, interval_s, status, source`
* `data/generated/observed_normal_traffic.csv` (from the monitor): `observed_timestamp, can_id, can_id_hex, ecu_name, message_name, dlc, payload_hex, inter_arrival_s, frame_flags, source`

Timestamps come from each program's own clock. `ecu_name`/`message_name` in the observed file come from looking up the CAN ID in the config (the bus itself carries no names). The C program leaves those two columns empty.
`data/samples/` holds a small **dry-run** sample (seed 42), which was generated by the simulator without sending anything; it is *not* captured traffic.

## Testing

Unit tests: `make test`. Hardware-free tests cannot prove `vcan0` works; follow the full plan in `docs/week1_testing.md` and record your real results there.

## Troubleshooting

See `docs/week1_troubleshooting.md`.

## Known limitations

* Classical CAN only: standard 11-bit IDs, payload at most 8 bytes. No CAN FD.
* Synthetic data: the IDs and signals are invented and simpler than real vehicle traffic.
* Python timing is software-scheduled, so intervals jitter by a millisecond or so under load.
* The `vcan0` tests have not been run by the author of this repo skeleton; results are yours to record.
* The simulator is limited to `vcanN` interfaces by design.

## Future stages

Week 2 controlled anomalous traffic and feature engineering; Week 3 Isolation Forest; Week 4 integration and PyQt dashboard.

## Documentation

`docs/week1_fundamentals.md`, `week1_setup.md`, `week1_testing.md`, `week1_troubleshooting.md`, `week1_git.md`, `week1_progress.md`, `week1_summary.md`.
