import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

import bridge_client
from bridge_client import BridgeClient
from dashboard import (
    AlertTableModel,
    CsvTableModel,
    Dashboard,
    MAX_ALERT_ROWS,
    MAX_LIVE_ROWS,
)


app = QApplication.instance() or QApplication([])


def test_bridge_client_emits_bounded_batches_without_dropping_messages(monkeypatch):
    client = BridgeClient()
    messages = [
        {"can_id": hex(index)}
        for index in range(BridgeClient.MAX_BATCH_SIZE * 2 + 5)
    ]
    payload = b"".join(
        (json.dumps(message) + "\n").encode("utf-8")
        for message in messages
    )

    class SocketStub:
        def __init__(self):
            self.sent_payload = False

        def settimeout(self, _timeout):
            pass

        def recv(self, _size):
            if not self.sent_payload:
                self.sent_payload = True
                return payload
            client._running = False
            return b""

        def close(self):
            pass

    monkeypatch.setattr(
        bridge_client.socket,
        "create_connection",
        lambda *_args, **_kwargs: SocketStub(),
    )
    batches = []
    client.messages_received.connect(batches.append)

    client.run()

    assert [len(batch) for batch in batches] == [
        BridgeClient.MAX_BATCH_SIZE,
        BridgeClient.MAX_BATCH_SIZE,
        5,
    ]
    assert [message for batch in batches for message in batch] == messages


def test_dashboard_applies_live_frames_as_one_batch(monkeypatch):
    window = Dashboard()
    window.frame_model.start_live()
    refresh_count = 0
    refresh = window.id_monitor._refresh

    def count_refresh():
        nonlocal refresh_count
        refresh_count += 1
        refresh()

    monkeypatch.setattr(window.id_monitor, "_refresh", count_refresh)
    frames = [
        {
            "timestamp": 1_700_000_000 + index * 0.005,
            "can_id": "0x100",
            "dlc": 8,
            "data": "00 01 02 03 04 05 06 07",
            "extended": False,
        }
        for index in range(200)
    ]

    alert = {
        "type": "alert",
        "timestamp": 1_700_000_000,
        "can_id_hex": "0x100",
        "score": 0.9,
    }
    window.on_live_messages(frames[:100] + [alert] + frames[100:])

    assert window.frame_model.total == len(frames)
    assert len(window.frame_model.rows) == len(frames)
    assert len(window.recorder) == len(frames)
    assert window.id_monitor.snapshot()[0]["count"] == len(frames)
    assert window.alert_model.rows[0][2] == "interval anomaly"
    assert window.frame_view.currentIndex().isValid()
    assert "ID 0x100" in window.detail.summary.text()
    assert window.detail.table.rowCount() == 8
    assert refresh_count == 1
    window.close()


def test_start_live_clears_stale_can_id_filter(monkeypatch):
    window = Dashboard()
    window.filter_edit.setText("0x123")
    monkeypatch.setattr(BridgeClient, "start", lambda _self: None)

    window.start_live()

    assert window.filter_edit.text() == ""
    assert not window.frame_proxy.has_filter()
    window.close()


def test_loading_frames_csv_selects_latest_visible_frame(tmp_path):
    path = tmp_path / "frames.csv"
    path.write_text(
        "timestamp,can_id,dlc,data,extended\n"
        "1700000000.1,0x100,2,11 22,False\n"
        "1700000000.2,0x200,4,10 34 00 B2,False\n",
        encoding="utf-8",
    )
    window = Dashboard()

    window.load_frames(str(path))

    assert window.frame_view.currentIndex().isValid()
    assert "ID 0x200" in window.detail.summary.text()
    assert window.detail.table.rowCount() == 4
    window.close()


def test_live_frame_model_keeps_only_recent_rows_but_counts_all():
    model = CsvTableModel()
    model.start_live()
    rows = [[str(index)] for index in range(MAX_LIVE_ROWS + 3)]

    model.add_frames(rows)

    assert model.total == MAX_LIVE_ROWS + 3
    assert len(model.rows) == MAX_LIVE_ROWS
    assert model.rows[0] == ["3"]
    assert model.rows[-1] == [str(MAX_LIVE_ROWS + 2)]


def test_alert_model_bounds_history_and_keeps_session_totals():
    model = AlertTableModel()
    alerts = [
        [f"00:00:{index % 60:02}", "0x100", "injection", str(index / 10000)]
        for index in range(MAX_ALERT_ROWS + 250)
    ]

    model.add_many(alerts)

    assert len(model.rows) == MAX_ALERT_ROWS
    assert model.total == MAX_ALERT_ROWS + 250
    assert model.rows[0] == alerts[250]
    assert model.rows[-1] == alerts[-1]
    assert model.highest_score == float(alerts[-1][3])

    model.clear()

    assert model.rows == []
    assert model.total == 0
    assert model.highest_score is None


def test_add_test_alert_creates_four_categories_with_distinct_can_ids():
    window = Dashboard()
    window.show()
    app.processEvents()

    button = next(
        button
        for button in window.findChildren(type(window.btn_live))
        if button.text() == "Add test alert"
    )
    button.click()
    app.processEvents()

    assert len(window.alert_model.rows) == 4
    assert {row[2] for row in window.alert_model.rows} == {
        "injection",
        "unknown ID",
        "payload tampering",
        "missing message",
    }
    can_ids = [row[1] for row in window.alert_model.rows]
    assert len(set(can_ids)) == 4
    assert all(0x100 <= int(can_id, 16) <= 0x7FF for can_id in can_ids)
    window.close()


def test_detector_learning_then_active_mode_adds_live_alert():
    window = Dashboard()
    window.frame_model.start_live()
    window.toggle_detector()
    normal_frames = [
        {
            "timestamp": 1_700_000_000 + index * 0.1,
            "can_id": "0x100",
            "dlc": 2,
            "data": "10 20",
            "extended": False,
        }
        for index in range(3)
    ]

    window.on_live_messages(normal_frames)
    window.toggle_detector()
    window.on_live_messages([{
        "timestamp": 1_700_000_001,
        "can_id": "0x7ff",
        "dlc": 2,
        "data": "10 20",
        "extended": False,
    }])

    assert window.detector.mode == "on"
    assert window.alert_model.total == 1
    assert window.alert_model.rows[-1][2] == "unknown ID"
    window.close()
