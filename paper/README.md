# Drones Manuscript

## Current revision: 13 September 2026

The latest main-paper review copy is [revision v1.9 (29 pages, no line numbers)](build/HS-AeroTS_Drones_revision_v1.9.pdf);
the current supplement is [Supplement v1.1](build/HS-AeroTS_Supplement_v1.1.pdf). The earlier
submission v1.0 is retained
as a historical version; it contains replay interpretations superseded by the
execution audit. The complete pre-revision manuscript is archived under
`../reports/paper_finalization_20260908/pre_revision_manuscript.zip`.

The current LaTeX sources are available directly in this directory, starting
with [main.tex](main.tex), and as a [complete v1.9 source ZIP](build/packages/HS-AeroTS_revision_v1.9_sources.zip).
The ZIP includes the main paper and supplement sources, all section files,
figures, generated tables, bibliography files, MDPI class assets, and the build
script. Extract it and run `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex`
from the extracted directory to compile the main paper. Revision v1.9 includes
the updated abstract, Introduction, Related Work, and overview figure.

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
.\build-main.ps1
```

`build-main.ps1` compiles `main.tex` to `build/latex-temp/main/` and then
publishes a new, incremented main-paper PDF at the top level of `build/`, for
example `HS-AeroTS_Drones_revision_v1.2.pdf`. The script increments the minor
version from the highest existing revision PDF only after a successful build.
It also moves top-level non-PDF build artifacts into subdirectories. To organize
existing artifacts without compiling, run `.\build-main.ps1 -OrganizeOnly`.

Build the supplement separately when needed:

```powershell
latexmk -pdf -outdir=build/latex-temp/supplement -jobname=HS-AeroTS_Supplement -interaction=nonstopmode -halt-on-error supplement.tex
```

Table ledgers and the completion checklist are in
`../reports/paper_finalization_20260908/`. Do not rerun the one-time
`scripts/paper/revise_content.py` transformation on the final sources: it starts
from the archived original and predates later citation and visual-QA edits.
Author metadata and declarations are retained pending author verification.

## Historical preparation notes (superseded where stated above)

`main.tex` is the single manuscript entry point. It uses the MDPI official LaTeX class and the ACS citation template downloaded from `https://www.mdpi.com/authors/latex` on 2026-08-21. The journal class option is `drones`.

For a manual diagnostic compile that does not add files to the top level of
`build/`:

```powershell
pdflatex -output-directory=build/latex-temp/manual -interaction=nonstopmode main.tex
pdflatex -output-directory=build/latex-temp/manual -interaction=nonstopmode main.tex
```

The manuscript deliberately distinguishes real-flight runtime anomaly diagnosis, ground-truth-anomaly-conditioned explanation, Stage-1-gated real-flight analysis, commit-level source-tree inspection candidates, onset-conditioned mutation rankings, and detector-gated replay. Author metadata, CRediT contributions, equal-contribution and correspondence marks, Funding, institutional-review and consent statements, Data Availability, the MDPI-compatible AI-use disclosure, Conflicts of Interest, and Highlights are complete. The MDPI class uses the `moreauthors` option so that the correspondence line and plural copyright wording render correctly.

The latest checked submission artifact is `build/HS-AeroTS_Drones_submission_v1.0.pdf` (32 pages). It can be rebuilt with:

```powershell
latexmk -pdf -outdir=build/latex-temp/submission -jobname=HS-AeroTS_Drones_submission_v1.0 -interaction=nonstopmode -halt-on-error main.tex
```

The limited recomputation is recorded under `../reports/p13/`; it loads frozen predictions/models only and does not retrain, tune, add data, add baselines, or rerun PX4/SITL replay.

## Directory Layout

- `main.tex`: single assembled manuscript source and compilation entry point. It is updated whenever manuscript body text is revised.
- `sections/`: LaTeX subsection sources grouped by top-level manuscript section. Each completed source is the canonical text included by `main.tex`.
- `figures/`: manuscript figures and figure source assets.
- `references/`: verified literature pool and BibTeX metadata used while drafting Sections 1--3.
- `Definitions/`: MDPI class, bibliography styles, and journal assets.
- `documentation/`: writing guidance, reference papers, and the journal template.
- `build/`: top-level versioned paper PDFs only. Intermediate LaTeX files are in `build/latex-temp/`, source packages are in `build/packages/`, and historical or QA outputs are in their respective subdirectories.

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
