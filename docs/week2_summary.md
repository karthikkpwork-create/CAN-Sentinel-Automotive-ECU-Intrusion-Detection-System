# Week 2 Summary (Role B)

**Achieved:** controlled attack traffic (4 types plus mixed) with per-frame labels, six labeled datasets, ground truth for the missing-message attack, sample datasets for model training and validation, a live vcan0 demo script and an observed-frame labeler.
**Verified:** 59 automated tests in a CAN-less environment, including the live transmit path with a fake sender; dry-run output is reproducible by seed.
**Not yet verified:** behavior on a real `vcan0` (tests W2-10..W2-13). All shared sample datasets are simulator-generated, not independently captured.
**Limitations:** classical CAN only; invented IDs and signals; timestamps in dry-run data use a virtual clock starting at 1700000000; missing_message has no attack rows in the main CSV by design.
**For Week 3:** train on `normal_capture_train.csv`, choose thresholds on `normal_capture_validation.csv`, evaluate on `validation_attacks_mixed.csv`. Use `label`/`attack_type` only for evaluation.
