# CAN-Sentinel — ML Feature Extraction

## 1. Objective

Convert CAN traffic records into numerical, time-window-based features for anomaly detection. These features are used by the Isolation Forest detector to identify unusual traffic patterns for further investigation.

An anomaly is an indication for investigation, not proof of a cyberattack.

## 2. Input Data

The feature extractor processes generated CAN traffic records containing information such as:

- CAN timestamps
- CAN identifiers
- Payload data
- Traffic event information used for evaluation labels

The extractor processes the available input dataset and produces numerical features for each non-empty time window.

## 3. Time Window Configuration

The current implementation uses one-second time windows.

Traffic records are grouped into windows to calculate message frequency, identifier diversity, timing behaviour and payload changes.

The window duration is configurable through the feature extraction command.

## 4. Extracted Features

The extractor calculates seven features:

| Feature | Definition | Possible security relevance |
|---|---|---|
| `frame_count` | Number of CAN frames in the window | Traffic-volume changes |
| `frames_per_second` | Number of frames divided by window duration | Possible flooding |
| `unique_id_count` | Number of distinct CAN identifiers | Unexpected message diversity |
| `iat_mean` | Mean inter-arrival time between frames | Timing deviations |
| `iat_std` | Standard deviation of inter-arrival times | Irregular message timing |
| `payload_change_rate` | Fraction of comparable consecutive same-ID payload pairs that differ | Unusual payload changes |
| `payload_comparisons` | Number of valid payload comparisons | Interpretation of payload-change rate |

## 5. Features Used by the Model

The Isolation Forest detector uses five numerical features:

- `frames_per_second`
- `unique_id_count`
- `iat_mean`
- `iat_std`
- `payload_change_rate`

The following extracted features are not used as model inputs:

- `frame_count`
- `payload_comparisons`

They are retained to support traffic analysis and interpretation.

Ground-truth labels and attack-type annotations are used for evaluation, not as model input features.

## 6. Payload Comparison

Payload-change rate is calculated using comparable consecutive payload observations for the same CAN identifier within a time window.

The calculation is:

`payload_change_rate = changed_payload_pairs / valid_payload_comparisons`

When there are no valid comparisons, the rate is set to zero. This does not prove that the payload remained unchanged; it indicates insufficient comparison data.

## 7. Output

The feature extraction process produces a CSV containing one row per non-empty time window.

The output includes:

- Window information
- Frame count and frame rate
- Unique CAN identifier count
- Inter-arrival timing statistics
- Payload-change statistics
- Available ground-truth evaluation annotations

The generated feature datasets are used by the training and evaluation pipeline.

## 8. Relationship to Anomaly Detection

The extracted features describe traffic behaviour rather than directly identifying an attack.

For example:

- Increased frame rate may indicate possible flooding.
- Changes in CAN identifier diversity may indicate unusual message activity.
- Irregular inter-arrival times may indicate timing anomalies.
- Changes in payload patterns may indicate unusual message content.

These indicators require further investigation and should not independently be treated as proof of malicious activity.

## 9. Limitations and Future Improvements

- Legitimate vehicle operating conditions can change traffic rates and payloads.
- Unknown CAN-ID detection can be strengthened with an approved identifier allowlist.
- Missing-message detection should use expected ECU message schedules and timing.
- Payload-tampering detection needs improved features and validation.
- Window duration should be evaluated against real traffic and detection latency.
- Independent normal and attack capture sessions are needed to assess generalization.

## 10. Implementation Status

Feature extraction has been implemented and integrated with the Isolation Forest pipeline.

The current model evaluation uses generated simulation datasets covering injection, missing message, payload tampering, unknown CAN ID and mixed traffic.

The evaluation results are documented separately in the ML design and model evaluation documentation.

Independent real-vehicle CAN capture validation remains outstanding.
