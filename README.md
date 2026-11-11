# CAN-Sentinel

CAN-Sentinel is a lab project for generating synthetic CAN traffic and viewing
frames in a PyQt dashboard. All example ECU names, CAN IDs, and payloads are
invented. Use only a virtual CAN interface (`vcanN`); this project is not for
connecting to or testing a real vehicle.

## What is in this checkout

| Component | Status |
|---|---|
| Normal synthetic traffic simulator | Implemented; supports a no-interface dry run |
| Synthetic attack traffic and labeled dataset generator | Implemented; dataset generation runs offline |
| PyQt CSV viewer and dashboard | Implemented; CSV loading was exercised with a generated capture |
| Live dashboard bridge for `vcan0` | Code is present; end-to-end live operation still needs validation on a configured `vcan0` |
| Dashboard detector | Rule-based heuristic detector; it is not an Isolation Forest |
| Isolation Forest training/inference pipeline | Not included in this checkout |
| Independent Python/C CAN capture and sender/observer comparison tools | Not included in this checkout |

The dashboard details and controls are in [dashboard/README.md](dashboard/README.md).

## Install

From the repository root, create an environment and install the dashboard
dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r dashboard/requirements.txt
```

The simulators use the Python standard library. The live bridge additionally
needs `python-can` in the environment where the bridge runs:

```bash
python -m pip install python-can
```

## Run a safe offline demo

Generate a short synthetic normal-traffic CSV. Dry-run mode sends nothing and
does not require a CAN interface:

```bash
python3 -m src.simulator.normal_traffic_simulator \
  --config config/config.example.json \
  --dry-run --duration 3 --seed 42 \
  --output data/generated/dashboard_demo.csv
```

Open that file in the main dashboard:

```bash
python dashboard/dashboard.py data/generated/dashboard_demo.csv
```

You can also open a CSV from the dashboard's **Open frames CSV...** button, or
run the simpler standalone frame table:

```bash
python dashboard/frame_table.py data/generated/dashboard_demo.csv
```

The checked-in sample capture is
[`data/samples/sample_attack_dry_run_seed42.csv`](data/samples/sample_attack_dry_run_seed42.csv).
It is synthetic dry-run data, not a live capture.

## Generate labeled datasets offline

This command creates normal, injection, unknown-ID, payload-tampering,
missing-message, and mixed datasets without transmitting CAN frames:

```bash
python scripts/generate_datasets.py \
  --duration 5 --seed 42 \
  --output-dir data/generated/demo
```

The output directory includes CSV files and ground-truth attack windows.
Missing-message scenarios also have a separate suppressed-frame CSV because a
suppressed frame does not appear in the main traffic stream.

## Live dashboard on a virtual CAN bus

Live mode requires Linux/WSL with the `vcan` kernel module and permission to
create a virtual interface. In the Linux terminal:

```bash
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set up dev vcan0
python dashboard/vcan_bridge.py
```

Start the dashboard on the same host and select **Start live**:

```bash
python dashboard/dashboard.py
```

To produce benign synthetic frames on the virtual bus, use another terminal:

```bash
python3 -m src.simulator.normal_traffic_simulator \
  --config config/config.example.json --interface vcan0 --duration 10
```

The bridge listens on TCP port `8765` and the dashboard client connects to
`127.0.0.1:8765` by default. The bridge currently binds to all network
interfaces; run it only in a trusted lab environment and restrict network
access to the port. A live `vcan0` session has not been validated as part of
this checkout's verification.

## Dashboard features

- Load frame CSV files and inspect individual frame bytes.
- Filter frames by one or more CAN IDs.
- View frame and alert counters, per-ID activity, message-rate and ID charts.
- Load an alerts CSV, display detector alerts, and export frames recorded in a
  live session.
- Toggle dark/light themes.

The **Add test alert** button creates a UI-only sample alert; it does not
represent a detector result.

## Detector and ML status

`dashboard/detector.py` contains a basic rule-based detector. It can learn a
baseline from live frames and check for unfamiliar IDs, unusually fast frames,
payload length/value changes, and missing messages. Its thresholds are
heuristics. This checkout does not include a trained Isolation Forest or an
ML feature-extraction/training/inference pipeline.

## Tests

Install `pytest` in the active environment, then run the focused, hardware-free
tests:

```bash
python -m pip install pytest
QT_QPA_PLATFORM=offscreen python -m pytest -q \
  tests/test_attack_simulator.py \
  dashboard/test_detector.py \
  dashboard/test_id_monitor.py
```

Some other `dashboard/test_*.py` files are standalone scripts rather than
pytest tests; avoid running the entire dashboard test directory blindly.

## Current checkout limitations

There is no top-level `Makefile` or `requirements.txt` in this checkout.
`scripts/setup_vcan.sh`, `scripts/run_demo.sh`, the independent capture
programs, and the sender/observer comparison tool are also not present. Set up
`vcan0` manually as above if you want to test the live bridge.
