# CAN-Sentinel — Machine Learning Design

## 1. Objective

The ML component will identify unusual CAN traffic patterns for investigation.
Isolation Forest is a future candidate for detecting anomalies; it will
complement explainable traffic rules.

## 2. Scope

Current work covers repository and CSV inspection, data-quality review,
feature planning, and a proposed evaluation strategy. Model training and
performance measurement have not been performed.

## 3. Dataset Inventory

| Dataset | Purpose | Status |
| --- | --- | --- |
| `data/samples/sample_attack_dry_run_seed42.csv` | Initial inspection | Present; 446-row synthetic dry-run sample |
| `data/generated/observed_normal_traffic.csv` | Candidate observed-normal data | Missing when checked |
| Independently captured labelled attack data | Future evaluation | Not available in this checkout |

The sample has 157 normal rows and 289 attack rows: 251 injection,
12 payload-tampering, and 26 unknown-ID rows. Label `0` is normal; label `1`
is attack.

## 4. Input Data

The inspected sample columns are:
`timestamp`, `ecu_name`, `message_name`, `can_id`, `can_id_hex`, `dlc`,
`payload_hex`, `interval_s`, `status`, `source`, `label`, `attack_type`.

This is a simulator-side sample, not an independent capture. The documented
observed-traffic file was not available to inspect. Five rows have an empty
`interval_s`; the other inspected columns have no empty values.

The simulator's dry-run code writes synthetic timestamps in seconds with six
fractional digits. This does not verify the clock used by an independent
capture monitor.

## 5. Proposed Features

| Feature | Definition | Possible use |
| --- | --- | --- |
| `frame_count` | Frames in a fixed time window | Traffic-volume changes |
| `frames_per_second` | Frame count divided by window duration | Possible flooding |
| `unique_id_count` | Distinct CAN IDs in a window | Message-diversity changes |
| `iat_mean` | Mean interval between frames of one ID | Timing deviations |
| `iat_std` | Variation in intervals for one ID | Irregular timing |
| `payload_change_rate` | Fraction of comparable consecutive same-ID payloads that differ | Unusual payload changes |

These are proposed features and must be validated against captured data. Do not
use `label` or `attack_type` as model inputs; keep them for evaluation.
Check unexpected IDs separately against an approved configuration allowlist.
That configuration is not available in this checkout.

## 6. Proposed Model and Evaluation

In the future, fit Isolation Forest on normal traffic windows. Choose its
anomaly threshold using separate validation data. Evaluate on held-out traffic
and compare with a deterministic traffic-rate rule.

When independently labelled attack data is available, report precision,
recall, F1-score, false-positive rate, confusion matrix, and detection latency
if measurable. No performance results are available yet.

## 7. Data Split

Separate training, validation, and test data by capture session or
non-overlapping time periods. Do not use overlapping windows across training
and test. Record the final split and random seed when data is available.

## 8. Limitations and Blockers

The inspected data is synthetic and does not establish real-world detector
performance. `data/generated/observed_normal_traffic.csv` is missing. The
attack simulator imports `src.simulator.normal_traffic_simulator`, which is
also missing from this checkout. Capture code and configuration files were
unavailable, so capture timing and ECU-to-ID mappings remain unverified.

## 9. Inspection Findings

- Environment: Windows PowerShell.
- CSV: `data/samples/sample_attack_dry_run_seed42.csv`.
- Rows: 446.
- CAN IDs occur in decimal and hexadecimal columns.
- Payloads are hexadecimal strings.
- Five `interval_s` values are empty.
- Data source: synthetic attack-simulator dry run, not observed capture.



## Data Inventory

| Item | Finding |
| --- | --- |
| Dataset path | `data/samples/sample_attack_dry_run_seed42.csv` |
| Data source | Synthetic attack simulator dry run; mixed mode, seed 42 |
| Number of rows | 446 |
| Column names | `timestamp`, `ecu_name`, `message_name`, `can_id`, `can_id_hex`, `dlc`, `payload_hex`, `interval_s`, `status`, `source`, `label`, `attack_type` |
| Timestamp field | `timestamp` |
| Timestamp units | Seconds in the synthetic dry-run simulator code; the independent capture clock is not verified |
| Empty values | 5 empty `interval_s` values; 0 in each other inspected column |
| Label columns | `label` and `attack_type` |
| Label meanings | `0` = normal; `1` = attack. Attack types found: injection (251), payload tampering (12), unknown ID (26) |
| Suitable for training? | No for the planned normal-only model training; this is a small synthetic mixed-traffic sample |
| Suitable for evaluation? | Pending for final evaluation; it can support preliminary checks, but is not independently captured test data |
| Outstanding issues | The observed-normal CSV, capture code, and configuration files were unavailable. Verify decimal/hex CAN ID agreement and DLC/payload-length agreement before feature extraction. |