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
