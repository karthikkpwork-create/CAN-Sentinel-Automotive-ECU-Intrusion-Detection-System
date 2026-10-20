**Status: Target design.** This document describes the target design, not all behavior of the current extractor.

# CAN-Sentinel — ML Feature Extraction

## 1. Objective

Convert raw CAN traffic records into numerical, time-window-based features for downstream anomaly detection using Isolation Forest.

## 2. Input data

The extractor accepts a CSV containing:

- A timestamp column: `observed_timestamp` or `timestamp`
- A CAN identifier column: `can_id_hex` or `can_id`
- An optional `payload_hex` column

Numeric timestamps must have a documented unit. All timestamps are converted to seconds before window grouping.

## 3. Window configuration

The initial window duration is one second. Windows are anchored to the earliest valid timestamp in the capture. Records are sorted by timestamp before extraction.

The window duration can be changed using the `--window-seconds` argument.

## 4. Extracted features

| Feature | Definition |
|---|---|
| `frame_count` | Number of CAN frames in the window |
| `frames_per_second` | Frame count divided by window duration |
| `unique_id_count` | Number of distinct CAN IDs in the window |
| `mean_inter_arrival_s` | Mean difference between consecutive frame timestamps within the window |
| `std_inter_arrival_s` | Population standard deviation of those time differences |
| `payload_change_rate` | Changed comparable payload pairs divided by all comparable pairs |
| `payload_comparison_count` | Number of consecutive, valid payload comparisons for the same CAN ID |

If a window contains insufficient timing observations, timing statistics are set to zero. If there are no comparable payload pairs, the payload change rate is set to zero and the comparison count is zero. Interpret this combination as insufficient comparison data, not proof that payloads did not change.

## 5. Payload validation

Payloads are normalized by removing whitespace and an optional `0x` prefix, and converting hexadecimal characters to lowercase. Payloads with an odd number of hexadecimal characters or non-hexadecimal characters are excluded from payload comparisons and counted as invalid.

Payload comparisons are performed only between consecutive valid payloads for the same CAN ID within the same window.

## 6. Output

The extractor writes a CSV with one row per non-empty time window. Each row contains the window index, relative window boundaries, frame and ID counts, timing statistics, and payload-change statistics.

The input CSV is not modified.

## 7. Quality and repeatability checks

- Verify that the input schema matches the actual dataset.
- Confirm timestamp units before processing numeric timestamps.
- Check that output columns and row counts are as expected.
- Check for empty cells and non-finite numeric values.
- Run extraction twice with the same input and settings and compare output hashes.

## 8. Limitations and future work

- Anomalous feature values are not proof of malicious activity.
- Legitimate vehicle operating conditions can change message rates and payloads.
- Unknown-ID detection requires an approved CAN-ID allowlist.
- Missing-message detection is improved by knowing the expected periodic message schedule.
- Window duration should be evaluated against real traffic and the expected detection latency.
- Isolation Forest training and evaluation are separate tasks and must use appropriately separated data.

No detection-performance claims are made until evaluation has been performed on suitable normal and labelled attack data.

## 9. Industry-relevant enhancements