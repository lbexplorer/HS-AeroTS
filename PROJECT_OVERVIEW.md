# HS-AeroTS Project Overview

## Purpose

HS-AeroTS is a research project for hierarchical runtime anomaly detection,
subsystem diagnosis, and interpretable telemetry evidence on real PX4/UAV
flight logs. The main chain is:

`telemetry -> aligned channels -> statistical features -> anomaly detector -> subsystem diagnosis -> SHAP/topic/module evidence`

P9 additionally evaluates controlled PX4 ULog replay with source-level
mutations. It is not a full closed-loop SITL experiment.

## Repository Entry Points

| Need | File or directory |
|---|---|
| AI/project overview | `PROJECT_OVERVIEW.md` |
| Human/project instructions | `AGENT.md` |
| Reproduction commands | `README.md` |
| Experiment configurations | `configs/` |
| Source code | `src/hs_aerots/` |
| Experiment scripts | `scripts/` |
| Tests | `tests/` |
| All experiment reports | `reports/` |
| P9 report index | `reports/p9/INDEX.md` |
| Research plans and references | `docs/INDEX.md` |

## Experiments

### P1 Data Preparation

Builds the UAV-SEAD inventory, annotations, numeric data dictionary, core
channels, aligned data, and reproducibility checks. The accepted dataset has
1,389 logs, 87 core channels, and 218,537 windows. Main evidence is in
`reports/p1/`.

### P2 AeroTSBoost Baseline

Uses 87 aligned telemetry channels, 18 statistical descriptors per channel,
chronological per-log splits, class-balanced LightGBM, and five seeds. The
main AUPRC is `0.7522 +/- 0.0039`. Evidence is in `reports/p2/`.

### P3 Stage 2 Diagnosis

Diagnoses four telemetry anomaly categories: External Position, Global
Position, Altitude, and Mechanical/Electrical. The five-seed Stage 2 Macro-F1
is `0.8980 +/- 0.0020`. Evidence is in `reports/p3/`.

### P4 Explainability

Aggregates TreeSHAP evidence from feature to channel, topic, and subsystem.
Consistency@1 is `0.3705 +/- 0.0109`, above the exact random baseline `0.1703`.
External Position remains close to its random evidence baseline and must be
reported with that limitation. Evidence is in `reports/p4/`.

### P5-P7 Additional Validation

- P5 compares CATCH and a clearly labeled linear Granger/forecast-error
  ablation. CATCH AUPRC is approximately `0.1930`; the Granger ablation is
  approximately `0.1991`.
- P6 ALFA external binary detection reports AUPRC `0.3181 +/- 0.0086` and
  AUROC `0.6679 +/- 0.0069`.
- P7 unknown-fault weak-label screening reports flight-level AUPRC
  `0.2784 +/- 0.0046`; point-level and Event-F1 claims are not valid because
  unknown faults have no onset intervals.

### P8 Software Module Mapping

Maps 18 PX4 topics to 54 modules through static uORB publisher/subscriber
relations. The mapping is evidence propagation and module suspicion, not proof
of root cause.

### P9 Controlled Replay and Module Ranking

Uses four source mutations on three real logs: Commander navigation-state
override, EKF2 innovation bias, INAV local-z freeze, and Land Detector
state inversion. The development paired-residual result is:

- Fault Recall: `10/12`
- Normal false alarms: `1/12`
- Top-1/3/5: `4/12`, `10/12`, `10/12`
- MRR: `0.5833`

The independent new-source replay completed 36 runs. The frozen main gate
obtained Recall `12/12`, but normal false alarms were `11/12` and 10/12 fault
runs alarmed before the 30-second onset. Therefore this is not reliable
cross-flight diagnosis evidence.

Normal-only gate optimization tested feature q99 scaling, topic q90
aggregation, event-level Normal thresholds, and a uniform 15-second warm-up.
The development candidate reached Recall `9/12`, normal false alarms `2/12`,
and zero pre-onset alarms, but transferred poorly to the independent sources:
Recall `12/12`, normal false alarms `11/12`, Top-3 `5/12`, MRR `0.4116`.
No optimized gate was promoted to the P9 primary method.

Read `reports/p9/INDEX.md` first for P9 artifacts and exact results.

### P10-P11 Robustness and Leave-Log-Out

P10 reports purged sensitivity results and P11 reports strict leave-log-out
results. Under P11, Stage 1 AUPRC is `0.6296 +/- 0.0023`, Stage 2 Macro-F1 is
`0.9041 +/- 0.0029`, Cascade Macro-F1 is `0.5962 +/- 0.0048`, and Direct
Five-Class Macro-F1 is `0.6092 +/- 0.0043`.

### P12 Submission-Readiness Analyses

P12 consolidates commit-matched PX4 evidence, semantic mapping checks, explicit
uORB declaration audits, full-channel CATCH evaluation, purged five-seed
statistics, replay statistics, masking statistics, and paired method
comparisons. These artifacts are frozen under `reports/p12/` and provide the
evidence base used during manuscript review; P12 does not replace the primary
P1-P11 protocols.

### P13 Limited Recalculation

P13 is inference-only submission-stage recomputation over frozen predictions,
models, SHAP values, mappings, and grouping metadata. It performs no training,
tuning, new data collection, baseline addition, or PX4 replay. It verifies 85
protected inputs as hash-identical, reports Stage-1 gated evidence, a
conservative source-path graph sensitivity (180 to 145 edges; 54 to 36 modules),
and 1,000-repetition flight/sequence-cluster bootstrap intervals. Evidence is
in `reports/p13/`.

## Current Scientific Conclusion

The project supports hierarchical anomaly detection and controlled-replay
candidate module ranking. P9 provides preliminary evidence of partial
end-to-end diagnostic capability under matched replay, especially for some
Commander and EKF2 cases. It does not currently support claims of reliable
low-false-alarm cross-flight diagnosis, deployment-level root-cause diagnosis,
or standalone online diagnosis without a matched healthy reference.

## Verification

The latest P9 implementation checks pass with 28 relevant tests. Raw ULogs,
large model/data artifacts, replay logs, and temporary render files are not
intended as the first navigation layer; use the report indexes before opening
those artifacts.
