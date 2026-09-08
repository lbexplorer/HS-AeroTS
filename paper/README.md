# Drones Manuscript

## Current revision: 8 September 2026

The current review copies are `build/HS-AeroTS_Drones_revision_v1.1.pdf` and
`build/HS-AeroTS_Supplement_v1.1.pdf`. The earlier submission v1.0 is retained
as a historical version; it contains replay interpretations superseded by the
execution audit. The complete pre-revision manuscript is archived under
`../reports/paper_finalization_20260908/pre_revision_manuscript.zip`.

The revision emphasizes conditional fault-domain classification, SHAP masking,
and exploratory paired-replay sampling improvements while retaining false
alarms, strict split comparisons, and scope limits. MTCL-UAV (TIM 2025) replaces
the preprint as the primary published detector selected for reproduction;
LDC-P-VAE (TIM 2026) is a second candidate. Neither has a matched-protocol
performance result in this revision. These preparation statuses are internal;
the manuscript introduces both methods in related work without reproduction
progress or pending-result statements. AeroTSBoost is retained only as the
provenance reference for the existing Stage 1 implementation. See
`../reports/mtcl_uav_reproduction/README.md` for preparation and resource checks.

Generate numeric tables from the project root, then compile in `paper/`:

```powershell
.venv/Scripts/python.exe paper/generate_revision_assets.py
.venv/Scripts/python.exe scripts/paper/generate_primary_tables.py
Set-Location paper
latexmk -pdf -outdir=build -jobname=HS-AeroTS_Drones_revision_v1.1 -interaction=nonstopmode -halt-on-error main.tex
latexmk -pdf -outdir=build -jobname=HS-AeroTS_Supplement_v1.1 -interaction=nonstopmode -halt-on-error supplement.tex
```

Table ledgers and the completion checklist are in
`../reports/paper_finalization_20260908/`. Do not rerun the one-time
`scripts/paper/revise_content.py` transformation on the final sources: it starts
from the archived original and predates later citation and visual-QA edits.
Author metadata and declarations are retained pending author verification.

## Historical preparation notes (superseded where stated above)

`main.tex` is the single manuscript entry point. It uses the MDPI official LaTeX class and the ACS citation template downloaded from `https://www.mdpi.com/authors/latex` on 2026-08-21. The journal class option is `drones`.

Compile with:

```powershell
pdflatex -output-directory=build -interaction=nonstopmode main.tex
pdflatex -output-directory=build -interaction=nonstopmode main.tex
```

The manuscript deliberately distinguishes real-flight runtime anomaly diagnosis, ground-truth-anomaly-conditioned explanation, Stage-1-gated real-flight analysis, commit-level source-tree inspection candidates, onset-conditioned mutation rankings, and detector-gated replay. Author metadata, CRediT contributions, equal-contribution and correspondence marks, Funding, institutional-review and consent statements, Data Availability, the MDPI-compatible AI-use disclosure, Conflicts of Interest, and Highlights are complete. The MDPI class uses the `moreauthors` option so that the correspondence line and plural copyright wording render correctly.

The latest checked submission artifact is `build/HS-AeroTS_Drones_submission_v1.0.pdf` (32 pages). It can be rebuilt with:

```powershell
latexmk -pdf -outdir=build -jobname=HS-AeroTS_Drones_submission_v1.0 -interaction=nonstopmode -halt-on-error main.tex
```

The limited recomputation is recorded under `../reports/p13/`; it loads frozen predictions/models only and does not retrain, tune, add data, add baselines, or rerun PX4/SITL replay.

## Directory Layout

- `main.tex`: single assembled manuscript source and compilation entry point. It is updated whenever manuscript body text is revised.
- `sections/`: LaTeX subsection sources grouped by top-level manuscript section. Each completed source is the canonical text included by `main.tex`.
- `figures/`: manuscript figures and figure source assets.
- `references/`: verified literature pool and BibTeX metadata used while drafting Sections 1--3.
- `Definitions/`: MDPI class, bibliography styles, and journal assets.
- `documentation/`: writing guidance, reference papers, and the journal template.
- `build/`: versioned PDF releases, archived PDFs, LaTeX auxiliary files, and visual-QA outputs; not manuscript source.

Current section-source layout:

```text
sections/
  section_1_introduction/
  section_2_related_work/
  section_3_methodology/
  section_4_experiments_results/
  section_5_discussion/
  section_6_conclusions/
  appendices/
```

Top-level `\section{...}` commands remain in `main.tex`; section source files are loaded with `\input`. Introduction is maintained as the single source file `sections/section_1_introduction/1_introduction.tex`.
