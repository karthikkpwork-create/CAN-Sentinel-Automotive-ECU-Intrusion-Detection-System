import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from id_monitor import CanIdMonitorPanel, normalize_can_id

app = QApplication.instance() or QApplication([])


def test_normalize_can_id_handles_prefix_and_whitespace():
    assert normalize_can_id("0x123") == "123"
    assert normalize_can_id(" 0X7DF ") == "7df"
    assert normalize_can_id("123") == "123"
    assert normalize_can_id("") == ""


def test_monitor_counts_ids_and_tracks_gap():
    panel = CanIdMonitorPanel()
    panel.record_frame({"timestamp": 10.0, "can_id": "0x123", "data": "11 22"})
    panel.record_frame({"timestamp": 12.0, "can_id": "123", "data": "33 44"})
    panel.record_frame({"timestamp": 20.0, "can_id": "0x7df", "data": "01 02"})

    rows = panel.snapshot()
    can_ids = [row["can_id"] for row in rows]
    assert "123" in can_ids
    assert "7df" in can_ids

    for row in rows:
        if row["can_id"] == "123":
            assert row["count"] == 2
            assert row["status"] in {"Active", "Quiet"}
            break
    else:
        raise AssertionError("123 row missing")


def test_monitor_load_rows_from_csv_snapshot():
    panel = CanIdMonitorPanel()
    rows = [
        ["1.0", "256", "0x100", "8", "11 22"],
        ["2.0", "256", "0x100", "8", "33 44"],
        ["4.0", "512", "0x200", "8", "55 66"],
    ]
    header = ["timestamp", "can_id", "can_id_hex", "dlc", "data"]

    panel.load_rows(rows, header)
    ids = {row["can_id"] for row in panel.snapshot()}
    assert {"100", "200"}.issubset(ids)
