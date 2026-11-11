# CAN-Sentinel — Isolation Forest Anomaly Detector

## 1. Objective

The ML detector identifies unusual CAN traffic patterns by learning normal traffic behaviour.

It uses the Isolation Forest unsupervised anomaly detection algorithm. An anomaly indicates traffic that requires further investigation; it is not proof of a cyberattack.

## 2. Model Architecture

The implemented model uses Scikit-learn Isolation Forest.

Isolation Forest identifies observations that are easier to isolate from the learned data distribution. Traffic windows with sufficiently high anomaly scores are classified as anomalous.

The model is trained using normal traffic windows only.

## 3. Input Features

The model uses five numerical features extracted from CAN traffic:

- `frames_per_second`
- `unique_id_count`
- `iat_mean`
- `iat_std`
- `payload_change_rate`

The features represent traffic frequency, CAN identifier diversity, message timing and payload behaviour.

Ground-truth labels and attack-type annotations are not used as model inputs.

## 4. Training Configuration

The current detector configuration is:

| Parameter | Value |
|---|---|
| Algorithm | Isolation Forest |
| Number of estimators | 200 |
| Random state | 42 |
| Training windows | 40 |
| Normal validation windows | 20 |
| Threshold quantile | 95th percentile |
| Threshold | 0.5094646190632834 |
| Scikit-learn version | 1.9.1 |

Training uses normal traffic windows. Normal validation windows are used to calibrate the anomaly threshold.

## 5. Anomaly Score Calculation

The detector calculates anomaly scores using:

`anomaly_score = -IsolationForest.score_samples(X)`

The score is negated so that higher values represent more anomalous observations.

The threshold is calculated using the 95th percentile of anomaly scores from normal validation windows.

The calibrated threshold is:

`0.5094646190632834`

## 6. Prediction Logic

Each feature window receives an anomaly score and a prediction.

The prediction rule is:

- `ANOMALY` when anomaly score is greater than the configured threshold.
- `NORMAL` otherwise.

Prediction outputs include the anomaly score, threshold and predicted class.

## 7. Evaluation Strategy

The detector was evaluated using five generated traffic scenarios:

1. Injection
2. Missing message
3. Payload tampering
4. Unknown CAN ID
5. Mixed traffic

Each individual attack scenario contains 45 normal and 15 attack windows. The mixed-traffic scenario contains 27 normal and 33 attack windows.

Each scenario contains 60 feature windows.

Evaluation compares predictions against the available ground-truth labels.

The reported metrics include:

- True positives and true negatives
- False positives and false negatives
- Precision
- Recall
- F1-score
- False-positive rate

## 8. Evaluation Results

| Scenario | Precision | Recall | F1-score | False-positive rate |
|---|---:|---:|---:|---:|
| Injection | 57.69% | 100.00% | 73.17% | 24.44% |
| Missing message | 55.56% | 100.00% | 71.43% | 26.67% |
| Payload tampering | 31.25% | 33.33% | 32.26% | 24.44% |
| Unknown CAN ID | 57.69% | 100.00% | 73.17% | 24.44% |
| Mixed traffic | 84.38% | 81.82% | 83.08% | 18.52% |

The mixed-traffic scenario achieved the highest F1-score in the current evaluation.

Payload tampering achieved the lowest F1-score, indicating that the current feature set does not reliably detect this scenario.

The false-positive rates also indicate that additional tuning and validation are required.

## 9. Reproducibility Artefacts

The repository contains:

- `models/can_sentinel_isolation_forest.joblib` — trained Isolation Forest model.
- `models/detector_config.json` — model configuration, features and threshold.
- `models/*_features_evaluation.json` — evaluation metrics for each scenario.
- `models/*_features_predictions.csv` — per-window prediction outputs.
- `requirements.txt` — pinned Python dependencies.

The trained model was successfully loaded using the project virtual environment and produced an anomaly score and prediction for a test input.

This smoke test verifies model loading and inference execution. It is not an additional performance evaluation.

## 10. Limitations and Future Improvements

- Evaluation currently uses generated simulation datasets.
- Training and validation windows originate from the same generated normal-traffic simulation.
- Independent capture sessions are needed to assess generalization.
- False-positive rates require further reduction.
- Payload-tampering detection requires improved features.
- Unknown CAN-ID detection should incorporate an approved CAN-ID allowlist.
- Missing-message detection should incorporate expected ECU message schedules.
- Live capture performance and detection latency require validation in a suitable Linux SocketCAN environment.

The current WSL2 environment did not provide a working vcan interface, so independent live CAN capture validation remains outstanding.

## 11. Implementation Status

The Isolation Forest detector has been implemented, trained and evaluated against five simulated traffic scenarios.

The trained model, configuration, evaluation metrics and prediction outputs have been generated and committed to the project repository.

The current results demonstrate the implemented simulation-based detection workflow. They do not establish real-world automotive detection performance.
