from detector import RuleDetector, normalize_can_id


def frame(timestamp, can_id="0x123", dlc=2, data="10 20"):
    return {
        "timestamp": timestamp,
        "can_id": can_id,
        "dlc": dlc,
        "data": data,
    }


def learn_detector(detector, can_id="0x123"):
    detector.start_learning()
    for timestamp in (1.0, 2.0, 3.0):
        assert detector.check(frame(timestamp, can_id=can_id)) == []
    assert detector.finish_learning()


def test_normalize_can_id_handles_prefix_case_and_whitespace():
    assert normalize_can_id("0x123") == "123"
    assert normalize_can_id(" 0X7DF ") == "7df"
    assert normalize_can_id("123") == "123"
    assert normalize_can_id("") == ""


def test_detector_is_silent_until_learning_starts():
    detector = RuleDetector()
    assert detector.check(frame(1.0)) == []
    assert detector.stats == {}
    assert detector.check_missing() == []


def test_learning_normalizes_can_id_and_measures_mean_interval():
    detector = RuleDetector()
    learn_detector(detector, can_id="0X123")

    assert list(detector.stats) == ["123"]
    assert detector.mean_interval["123"] == 1.0


def test_unknown_id_is_reported_once_across_id_formats():
    detector = RuleDetector()
    learn_detector(detector)

    assert detector.check(frame(3.1, can_id="0x7DF")) == [("unknown ID", 0.9)]
    assert detector.check(frame(3.2, can_id="7df")) == []


def test_fast_frame_is_reported_as_injection():
    detector = RuleDetector()
    learn_detector(detector)

    alerts = detector.check(frame(3.1))
    assert alerts == [("injection", 0.9)]


def test_out_of_range_payload_is_reported_after_id_normalization():
    detector = RuleDetector()
    learn_detector(detector)

    alerts = detector.check(frame(4.0, can_id="123", data="10 FF"))
    assert ("payload tampering", 0.8) in alerts


def test_unexpected_payload_length_is_reported():
    detector = RuleDetector()
    learn_detector(detector)

    alerts = detector.check(frame(4.0, dlc=3, data="10 20 30"))
    assert alerts == [("payload tampering", 0.8)]


def test_invalid_numeric_frame_fields_are_ignored():
    detector = RuleDetector()
    learn_detector(detector)

    assert detector.check(frame("not-a-time")) == []
    assert detector.check(frame(4.0, dlc="not-a-length")) == []


def test_missing_message_uses_runtime_clock_and_alerts_once_per_silence():
    detector = RuleDetector()
    detector.clock = lambda: 100.0
    learn_detector(detector)

    detector.clock = lambda: 101.0
    assert detector.check_missing() == []

    detector.clock = lambda: 106.0
    expected = [("123", "missing message", 0.6)]
    assert detector.check_missing() == expected
    assert detector.check_missing() == []

    detector.check(frame(3.1))
    assert detector.check_missing() == []

    detector.clock = lambda: 112.0
    assert detector.check_missing() == expected
