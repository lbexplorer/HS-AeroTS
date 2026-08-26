# P13 limited recomputation

Date: 2026-08-26

This directory contains the submission-stage limited recomputation for HS-AeroTS. The runner loads frozen predictions, models, SHAP values, uORB edges, firmware manifests, and log/sequence grouping metadata. It does not collect data, train or tune a model, add a baseline, or execute PX4/SITL replay.

## Outputs

- `stage1_gated/`: Stage 1 TP/FN/FP/TN counts, matching-commit detected-anomaly evidence, and false-positive Stage 2/module distributions.
- `conservative_graph/`: conservative path-exclusion sensitivity, excluded edges, propagation modes, degree-normalized ranks, overlap, and evidence-conservation checks.
- `absolute_uncertainty/`: 1000-repetition cluster-bootstrap confidence intervals with seed `20260825`, with model-seed SD reported separately.
- `input_integrity.json`: SHA-256 inventory before and after recomputation; all 85 protected source artifacts were unchanged.
- `completion_summary.json`: consolidated machine-readable results and boundary statements.

The manuscript reports only values traceable to these files or the previously frozen P12 outputs. The filtered graph is a conservative-exclusion sensitivity and is not an actual PX4 build-target graph.
