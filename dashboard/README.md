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
