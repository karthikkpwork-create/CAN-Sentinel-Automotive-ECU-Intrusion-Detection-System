# CAN-Sentinel - Dashboard & Frame Viewer

## Overview
A CSV-based CAN Frame Viewer built using Python and PyQt5 to display CAN frames in an interactive table for inspection and analysis.

## Key Features
- Load CAN frame data from CSV files.
- Display timestamps, CAN IDs, DLC, and payload data.
- Stretchable columns and alternating row colors for readability.
- Ready for integration with real-time monitors and intrusion detection alerts.

## Requirements
```bash
pip install -r dashboard/requirements.txt
```
Or directly:
```bash
python -m pip install PyQt5 pandas pyqtgraph
```

## How to Run

1. **Standalone Frame Table:**
   ```bash
   python dashboard/frame_table.py
   ```
   Click **Open CSV...** and select a dataset (e.g. from `data/samples/` or `data/generated/`).

2. **Load CSV Directly via CLI:**
   ```bash
   python dashboard/frame_table.py data/samples/sample_sender_dry_run_seed42.csv
   ```

3. **Main Dashboard:**
   ```bash
   python dashboard/dashboard.py
   ```
## Live CAN Feed (vcan0 to Dashboard)

The dashboard can show CAN frames live from a virtual CAN bus (`vcan0`).
`vcan0` only exists inside Ubuntu (WSL), but the dashboard runs on Windows,
so a small bridge program sends the frames between them.

### How it works

```
cansend / attack script -> vcan0 (Ubuntu) -> vcan_bridge.py (Ubuntu)
    -> TCP port 8765 -> bridge_client.py (Windows) -> dashboard.py
```

| File | Where it runs | What it does |
|------|---------------|--------------|
| `dashboard/vcan_bridge.py` | Ubuntu (WSL) | Reads frames from `vcan0` and sends each one as a line of JSON on port 8765 |
| `dashboard/bridge_client.py` | Windows | Background thread that connects to the bridge and passes each frame to the dashboard |
| `dashboard/dashboard.py` | Windows | Shows the frames in the table, the Frames loaded card and the message rate chart |

Each frame is sent as one JSON line, for example:

```
{"timestamp":1234567890.0,"can_id":"0x123","dlc":8,"data":"11 22 33 44 55 66 77 88","extended":false}
```

### Setup (after every PC restart)

`vcan0` is removed when WSL restarts, so create it again each time:

```
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set up vcan0
```

Python packages: `python-can` (Ubuntu), `PyQt5` and `pyqtgraph` (Windows).

### Run

1. Ubuntu terminal 1: start the bridge.
   ```
   cd /mnt/d/Infotact_Internship/CAN-Sentinel-Automotive-ECU-Intrusion-Detection-System/dashboard
   python3 vcan_bridge.py
   ```
   It prints `CAN bridge listening on port 8765`.
2. Windows PowerShell: start the dashboard.
   ```
   cd D:\Infotact_Internship\CAN-Sentinel-Automotive-ECU-Intrusion-Detection-System\dashboard
   python dashboard.py
   ```
3. Click **Start live**. The bottom line shows `Live: Connected`.
4. Ubuntu terminal 2: send frames.
   ```
   cansend vcan0 123#1122334455667788
   ```
   To send a steady stream (about 10 frames per second for 10 seconds):
   ```
   for i in $(seq 1 100); do cansend vcan0 123#1122334455667788; sleep 0.1; done
   ```

### Notes

- The bridge serves one client at a time. Restart the bridge if you close the dashboard and open it again.
- The live table keeps the newest 5000 frames.
- If the dashboard cannot connect, check that `vcan0` exists (`ip link show vcan0`) and that the bridge is running.
- Opening a frames CSV stops live mode.
- Detector alerts will appear in the Alerts panel when the detector calls `add_alert()`. The detector is not connected to the live feed yet.

### Screenshot

![Dashboard in live mode](docs/screenshots/dashboard-live.png)