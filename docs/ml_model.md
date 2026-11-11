# CAN-Sentinel — Isolation Forest Detector

> **Status: Implementation in progress.** The feature-loader tests pass, but the model has not been trained and the end-to-end normal and flood scenarios have not been run.

## Objective

Detect anomalous CAN traffic windows by learning patterns from normal training traffic.

## Input features

The model is configured to use:

- `frames_per_second`
- `unique_id_count`
- `iat_mean`
- `iat_std`
- `payload_change_rate`

Input features must be numeric and finite. Payload-change rate must be between 0 and 1.

## Training approach

Isolation Forest is intended to be fitted on normal training windows only. The random seed is fixed to make the experiment reproducible.

Training has not yet been run because separate normal-only training and validation data are not available.

## Threshold selection

The detector calculates anomaly scores by negating `IsolationForest.score_samples`, so higher scores represent more anomalous observations.

The threshold will be selected using the specified quantile of normal validation anomaly scores. The initial configuration uses the 99th percentile.

A threshold selected from validation data must remain fixed during final test evaluation. No threshold has been calculated yet.

## Predictions

Each scored window receives:

- `anomaly_score`
- `threshold`
- `prediction` (`NORMAL` or `ANOMALY`)

An anomaly is a signal for investigation, not proof of an attack.

## Required tests

1. **Normal sample:** Pending a trained model and separate held-out normal data.
2. **Simulated flood:** Pending a trained model and a controlled flood feature file.
3. **Invalid input:** The loader rejected a non-numeric `frames_per_second` value. Both automated feature-loader tests passed.

## Reproducibility artefacts

Planned artefacts:

- Trained model file
- Detector configuration and threshold
- Input dataset references and capture identifiers
- Prediction CSV
- Dependency versions
- Test results and execution commands

No trained model, threshold, or prediction CSV has been generated yet.

## Limitations

Detection depends on the training distribution, threshold and feature quality. Legitimate vehicle operating changes may trigger alerts. Synthetic flood tests demonstrate behaviour on the chosen simulation only and do not establish real-world attack detection performance.

Precision, recall, F1 and confusion-matrix results are not available because training and final evaluation have not been performed.