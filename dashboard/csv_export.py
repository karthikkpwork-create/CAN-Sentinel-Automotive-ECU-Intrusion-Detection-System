"""csv_export.py - records live CAN frames and saves them to a CSV file."""
import csv
import os
import time
from collections import deque

HEADER = ["timestamp", "time", "can_id", "dlc", "data", "extended"]
DEFAULT_FOLDER = "captures"


class FrameRecorder:
    """Keeps the live frames in memory so they can be saved as a CSV file."""

    def __init__(self, max_frames=100000):
        self.rows = deque(maxlen=max_frames)   # oldest rows drop out first
        self.first_ts = None
        self.last_ts = None

    def __len__(self):
        return len(self.rows)

    def add(self, frame):
        """Store one frame (the dictionary sent by the bridge)."""
        try:
            ts = float(frame.get("timestamp", 0))
        except (TypeError, ValueError):
            return False                       # skip a frame with a bad timestamp
        if self.first_ts is None:
            self.first_ts = ts
        self.last_ts = ts

        clock = time.strftime("%H:%M:%S", time.localtime(ts))
        millis = int((ts % 1) * 1000)
        self.rows.append([
            f"{ts:.3f}",
            f"{clock}.{millis:03d}",
            frame.get("can_id", ""),
            frame.get("dlc", ""),
            frame.get("data", ""),
            frame.get("extended", ""),
        ])
        return True

    def clear(self):
        self.rows.clear()
        self.first_ts = None
        self.last_ts = None

    def seconds_recorded(self):
        if self.first_ts is None:
            return 0.0
        return max(0.0, self.last_ts - self.first_ts)

    def unique_ids(self):
        return len({row[2] for row in self.rows})

    def summary(self):
        """Short text such as '250 frames, 4 IDs, 12.5 s'."""
        return (f"{len(self.rows)} frames, {self.unique_ids()} IDs, "
                f"{self.seconds_recorded():.1f} s")

    def default_path(self):
        """A file name with the date and time, inside the captures folder."""
        name = time.strftime("live_frames_%Y%m%d_%H%M%S.csv")
        return os.path.join(DEFAULT_FOLDER, name)

    def save(self, path):
        """Write all frames to a CSV file. Returns the number of rows saved.

        The file is written to a temporary name first and renamed at the end,
        so a failed save never leaves a half-written CSV behind.
        """
        rows = list(self.rows)
        folder = os.path.dirname(os.path.abspath(path))
        os.makedirs(folder, exist_ok=True)

        temp_path = path + ".tmp"
        with open(temp_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(HEADER)
            writer.writerows(rows)
        os.replace(temp_path, path)
        return len(rows)