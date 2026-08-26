# HS-AeroTS Stage 4.5 Final Integrity Audit

Audit date: 2026-08-26
Workflow: academic-research-suite Stage 4.5
Verdict: **PASS WITH NOTES**

## Scope and legacy boundary

This project predates the suite's claim-passport/claim-registry contracts. Those contracts were not fabricated retrospectively. The audit therefore used the complete manuscript, all cited bibliography entries, frozen P12/P13 reports, executable tests, source/configuration files, and rendered PDF. Status: `[LEGACY-NO-CONTRACT]`, with direct manual and machine-readable trace checks.

## Claim–evidence–citation consistency

- All P13 numerical statements were checked against `reports/p13/completion_summary.json` and its component CSV/JSON files. One transcription error in matching-commit recall was detected and corrected from the all-test value `0.6909 ± 0.0229` to `0.6728 ± 0.0248`.
- All 36 cited keys have bibliography entries; all 36 bibliography entries are cited. Missing citations: 0. Unused entries: 0. Duplicate labels: 0.
- Bibliographic identity and topical support were checked online against publisher, conference, repository, author, DOI, or preprint records. No reference was invented, added, or modified during P13.
- Exact-phrase searches of distinctive new claim-boundary language found no matching source text. This is a bounded originality screen, not a commercial similarity score.
- Data and software availability statements match the actual policy: third-party datasets are identified, source code is not public, and specified frozen artifacts may be supplied confidentially to editors/reviewers.

## Result-surface consistency

- Abstract, Highlights, Methods, Results, Discussion, Conclusion, Table 5, Figures 3–5, and Appendices A–B use the same evidence boundaries.
- Ground-truth-anomaly-conditioned explanation, Stage-1-gated real-flight analysis, onset-conditioned replay, and detector-gated replay are not mixed.
- Seed SD is identified as model-training dispersion; 95% cluster intervals are identified as sampling uncertainty.
- Conservative graph filtering is described as source-path exclusion sensitivity, not actual build-target reconstruction.
- CATCH and GCAD are described only as resource-constrained feasibility references.

## Failure-mode audit

| Failure mode | Finding | Status |
|---|---|---|
| Implementation bug | Count sums, matching-commit membership, strict edge subsets, evidence conservation, deterministic bootstrap, and CI/point consistency are unit tested | CLEAR |
| Bad or ghost citations | 36/36 cited keys resolved; identity and claim-context screen completed | CLEAR |
| Hallucinated experimental details | P13 values trace to machine-readable outputs; 85 protected inputs remained hash-identical | CLEAR |
| Shortcut reliance | Strict/purged/leave-log-out degradation and semantic-map failures are disclosed; residual model shortcut risk is not claimed away | PASS WITH NOTE |
| Negative result reframed as success | Detector-gated replay remains 0/12 and is explicitly a capability boundary | CLEAR |
| Methodology/configuration fabrication | Software versions, seeds, filters, splits, and budgets match code/reports | CLEAR |
| Frame lock / overclaiming | Title and conclusions were narrowed; causal, deployment, build-target, and SOTA claims are explicitly disallowed | CLEAR |

## Seven Major dispositions

1. M1 — conditioned versus gated evidence: **ADDRESSED**.
2. M2 — uORB independent validation wording: **MITIGATED**, residual no-gold-audit limitation retained.
3. M3 — whole-tree applicability: **MITIGATED**, residual no-build-graph limitation retained.
4. M4 — metric formulas and random baseline: **ADDRESSED**.
5. M5 — recent baseline positioning: **MITIGATED**, residual fair-retraining limitation retained.
6. M6 — seed SD versus sampling CI: **ADDRESSED**.
7. M7 — no public Supplement: **MITIGATED**, full human-readable appendix supplied and non-public machine-readable scope disclosed.

## Build and visual QA

- `latexmk` completed successfully: 30 pages.
- Undefined citations/references: 0; multiply defined labels: 0; overfull boxes: 0; DOI footer: absent.
- Rendered checks covered the title page, all principal figures/statistical tables, 87-channel longtable, reproducibility appendix, and final references page.
- Test result: 37 passed, 1 deselected because of a documented Windows sandbox temporary-directory permission constraint.

## Residual notes

The manuscript is internally consistent and submission-ready for its narrowed claims. Acceptance risk remains from the absence of an independent uORB gold audit, an actual PX4 build graph, fairly retrained recent baselines, broader replay data, public source code, and a machine-readable public Supplement. These are disclosed limitations; none is represented as completed work.
