# P9 Report Index

## Read First

1. `reports/p9/README.md`: P9 top-level status, historical context, and
   current scientific conclusion.
2. `reports/p9/paired_residual/README.md`: paired replay development,
   independent validation, and current gate conclusion.
3. `reports/p9/paired_residual/independent/README.md`: frozen independent
   validation protocol and final run-level results.
4. `reports/p9/paired_residual/gate_optimization.md`: Normal-only gate
   optimization and why no candidate was promoted.

## Main Result Files

| Purpose | Path |
|---|---|
| Original P9 run manifest | `reports/p9/run_manifest.tsv` |
| Original mutation metadata | `reports/p9/mutation_manifest.csv` |
| Original localization metrics | `reports/p9/localization_metrics.json` |
| Original per-mutation metrics | `reports/p9/localization_by_mutation.csv` |
| Original module rankings | `reports/p9/module_rankings.csv` |
| Replay/effect checks | `reports/p9/injection_effect_validation.csv` |
| Stage 1 replay reassessment | `reports/p9/stage1_reassessment/README.md` |
| Corrected development summary | `reports/p9/paired_residual/corrected_results/summary.csv` |
| Independent validation summary | `reports/p9/paired_residual/independent/summary.csv` |
| Independent run-level results | `reports/p9/paired_residual/independent/results_by_run.csv` |
| Independent mutation results | `reports/p9/paired_residual/independent/by_mutation.csv` |
| Source independence audit | `reports/p9/paired_residual/independent/source_independence_audit.csv` |
| Replay quality audit | `reports/p9/paired_residual/independent/replay_quality.csv` |
| Integrity verification | `reports/p9/paired_residual/independent/verification.json` |

## Gate Optimization

Candidate outputs are under:

`reports/p9/paired_residual/independent/optimized_gate_candidates/`

The principal candidate is
`development_quantile_q0.9_e1_w15/`. Its independent migration result is
Recall `12/12`, normal false alarms `11/12`, onset-preceding alarms `9/12`,
Top-3 `5/12`, and MRR `0.4116`. It is retained as a negative optimization
result and is not the P9 primary gate.

## Reproduction Code

- `scripts/p9/run_replay_pipeline.sh`: original replay pipeline.
- `scripts/p9/rerun_native_inputs.sh`: local-input replay reassessment.
- `scripts/p9/evaluate_paired_residual.py`: development paired-residual
  evaluation.
- `scripts/p9/freeze_independent.py`: seals the independent protocol.
- `scripts/p9/evaluate_independent.py`: frozen independent inference/scoring.
- `scripts/p9/evaluate_independent_gate.py`: Normal-only gate optimization.
- `scripts/p9/audit_independent.py`: independent validity audit.

## Important Boundaries

- P9 is controlled PX4 ULog replay, not closed-loop SITL.
- The three independent source flights were not P9 development sources, but
  their windows were present in the historical P2 scaler training exposure.
- The 12 normal targets are from only three source flights and are not 12
  independent flights.
- Module ranks are candidate-module ranks from static mapping, not guaranteed
  unique root causes.
- Failed effect checks remain in the primary denominator.
