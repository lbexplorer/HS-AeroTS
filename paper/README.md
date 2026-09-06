# Drones Manuscript

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
