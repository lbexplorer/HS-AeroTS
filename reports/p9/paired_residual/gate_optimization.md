# P9 Detection Gate Optimization

## Scope

This experiment optimized detection gating only. The 54-module candidate set,
publisher mapping, evidence aggregation after gating, and ranking tie policy
were unchanged. No mutation label, fault onset, or ground-truth module was used
to fit a gate.

## Candidate rule

The development candidate used Normal replay only:

- feature residual scale: Normal q99 with a 0.05 floor;
- within-topic aggregation: q90 of normalized features;
- across-topic aggregation: maximum topic score;
- event persistence: three consecutive windows;
- warm-up: suppress all gates before 15 seconds;
- flight/event threshold: maximum sustained event score in Normal calibration.

The development calibration consisted of 12 existing Normal replay targets,
with source-level leave-one-source-out fitting. The candidate was then applied
without refitting to the 12 fault and 12 Normal targets from the 2018
independent replay set.

## Results

| Evaluation | Recall | Normal false alarms | Fault pre-onset alarms | Top-1 | Top-3 | Top-5 | MRR |
|---|---:|---:|---:|---:|---:|---:|---:|
| Original frozen gate | 12/12 | 11/12 | 10/12 | 6/12 | 9/12 | 9/12 | 0.6369 |
| Normal-calibrated q90 + warm-up, independent 2018 set | 12/12 | 11/12 | 9/12 | 4/12 | 5/12 | 5/12 | 0.4116 |
| Same rule calibrated on 2018 Normal validation only* | 7/12 | 0/12 | 0/12 | 1/12 | 1/12 | 1/12 | 0.1110 |

`*` The last row is a sensitivity analysis, not a confirmatory result: the
2018 Normal controls and 2018 fault targets share source flights. It shows the
false-alarm/recall trade-off when the threshold is raised enough to cover the
observed Normal flights.

Development-only candidate screening gave Recall 9/12, Normal false alarms
2/12, zero fault pre-onset alarms, Top-3 6/12, and MRR 0.4375. This does not
transfer to the independent source flights.

## Interpretation

The dominant false alarms are persistent residuals from `vehicle_attitude`,
`estimator_status`, and `vehicle_local_position`, with many appearing around
11--17 seconds. A 15-second warm-up removes part of the common initialization
transient, but the independent Normal flights continue to produce persistent
post-warm-up residuals. Topic-wise normalization and q90 aggregation reduce
single-feature domination, but do not remove source-level paired baseline
mismatch.

No optimized gate is promoted to the P9 primary method. The current evidence
does not support a gate that simultaneously achieves the requested low false
alarm rate, at least 8/12 recall, and non-degraded module ranking. P9 therefore
continues to support only a cautious statement about preliminary partial
end-to-end diagnostic capability under controlled replay, not reliable
cross-flight deployment-level diagnosis.

Implementation artifacts are in `scripts/p9/evaluate_independent_gate.py` and
`src/hs_aerots/optimized_gate.py`; candidate outputs are under
`reports/p9/paired_residual/independent/optimized_gate_candidates/`.
