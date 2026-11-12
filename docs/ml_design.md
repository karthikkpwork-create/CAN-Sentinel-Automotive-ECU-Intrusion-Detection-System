# CAN-Sentinel — Machine Learning Design

## 1. Objective

The ML component identifies unusual CAN traffic patterns for investigation.
It complements rule-based traffic monitoring by using time-window-based
features and an Isolation Forest anomaly detector.

An anomaly is an indication for further investigation, not proof of a
cyberattack.

## 2. Implementation Status

The following ML components have been implemented:

- CAN traffic feature extraction using fixed time windows.
- Normal and attack traffic dataset generation for simulation.
- Isolation Forest training using normal traffic windows.
- Threshold calibration using normal validation windows.
- Prediction and evaluation across five traffic scenarios.
- Saved model, detector configuration, evaluation metrics and prediction files.

The implementation has been tested with generated simulation datasets.
Independent real-vehicle CAN capture validation remains outstanding.

## 3. ML Workflow

1. Generate normal and simulated attack CAN traffic.
2. Extract numerical features from traffic records using one-second windows.
3. Prepare normal-only training and validation feature windows.
4. Train the Isolation Forest detector on normal training windows.
5. Calculate anomaly scores for normal validation windows.
6. Select the anomaly threshold using the 95th percentile of validation scores.
7. Evaluate predictions against labelled simulated scenarios.
8. Save the trained model, configuration, evaluation metrics and predictions.

## 4. Input Data and Dataset Scope

The ML pipeline uses generated CAN traffic and extracted feature datasets.

The earlier repository inspection included
`data/samples/sample_attack_dry_run_seed42.csv`, a 446-row synthetic
dry-run sample. That sample was useful for initial inspection but is not
the sole basis for the current model evaluation.

Current evaluation covers these scenarios:

- Injection
- Missing message
- Payload tampering
- Unknown CAN ID
- Mixed traffic

The current evaluation datasets contain 60 feature windows per scenario.
The four individual attack scenarios contain 45 normal and 15 attack
windows each. The mixed-traffic scenario contains 27 normal and 33 attack
windows.

These are simulated datasets, not independently captured vehicle traffic.

## 5. Extracted Features

The feature extractor calculates the following values for each non-empty
time window:

| Feature | Definition | Possible use |
| --- | --- | --- |
| `frame_count` | Number of CAN frames in the window | Traffic-volume changes |
| `frames_per_second` | Frame count divided by window duration | Possible flooding |
| `unique_id_count` | Number of distinct CAN IDs in the window | Message-diversity changes |
| `iat_mean` | Mean inter-arrival time | Timing deviations |
| `iat_std` | Standard deviation of inter-arrival time | Irregular timing |
| `payload_change_rate` | Fraction of comparable consecutive same-ID payload pairs that differ | Unusual payload changes |
| `payload_comparisons` | Number of valid payload comparisons | Interpretation of payload-change rate |

The Isolation Forest model uses five features:

- `frames_per_second`
- `unique_id_count`
- `iat_mean`
- `iat_std`
- `payload_change_rate`

`frame_count` and `payload_comparisons` are retained as extracted
features but are not model inputs. Ground-truth labels and attack-type
annotations are used for evaluation, not as model inputs.

## 6. Model and Evaluation Strategy

The implemented detector uses Isolation Forest.

- Training data: normal traffic windows only.
- Number of estimators: 200.
- Random state: 42.
- Training windows: 40.
- Normal validation windows: 20.
- Threshold quantile: 95th percentile.
- Threshold: 0.5094646190632834.

The anomaly score is calculated as:

`anomaly_score = -IsolationForest.score_samples(X)`

A higher score indicates more anomalous behaviour.

The prediction rule is:

- `ANOMALY` when the anomaly score is greater than the threshold.
- `NORMAL` otherwise.

Evaluation reports confusion-matrix counts, precision, recall, F1-score
and false-positive rate.

## 7. Evaluation Results

| Scenario | Precision | Recall | F1-score | False-positive rate |
| --- | ---: | ---: | ---: | ---: |
| Injection | 57.69% | 100.00% | 73.17% | 24.44% |
| Missing message | 55.56% | 100.00% | 71.43% | 26.67% |
| Payload tampering | 31.25% | 33.33% | 32.26% | 24.44% |
| Unknown CAN ID | 57.69% | 100.00% | 73.17% | 24.44% |
| Mixed traffic | 84.38% | 81.82% | 83.08% | 18.52% |

The mixed-traffic scenario has the highest F1-score in this evaluation.
Payload tampering has the weakest detection performance and requires
further investigation.

These results describe the current simulated datasets only. They do not
establish real-world vehicle detection performance.

## 8. Data Split and Validation Considerations

The current model configuration uses 40 normal windows for training and
20 normal windows for threshold validation.

These windows originate from the current generated normal-traffic
simulation. They are not an independent capture-session validation set.

Further validation should use separate normal capture sessions and
independently labelled attack traffic. Capture-session separation is
important for measuring generalization beyond the simulation used to
develop the detector.

## 9. Limitations and Future Work

- Current evaluation uses simulated traffic, not independent vehicle CAN captures.
- The false-positive rates show that additional tuning and validation are needed.
- Payload-tampering detection is weak with the current feature set.
- Unknown-ID detection should be strengthened with an approved CAN-ID allowlist.
- Missing-message detection should use expected ECU message schedules and timing.
- Training and validation should be repeated using independent capture sessions.
- Detection latency should be measured in a suitable live capture environment.
- The capture monitor requires Linux SocketCAN. The offline ML evaluation
  does not validate live capture or detection latency, so independent live
  capture validation remains incomplete.

## 10. Reproducibility Artefacts

The repository includes:

- `models/can_sentinel_isolation_forest.joblib` — trained model.
- `models/detector_config.json` — model features and threshold configuration.
- `models/*_features_evaluation.json` — scenario evaluation metrics.
- `models/*_features_predictions.csv` — per-window prediction outputs.
- `requirements.txt` — pinned Python dependencies.
- `src/ml/` — feature extraction, training and prediction implementation.

The model was successfully loaded from the project virtual environment
and produced an anomaly score and prediction for a test input.
That smoke test verifies model loading and inference execution; it is
not an additional performance evaluation.
