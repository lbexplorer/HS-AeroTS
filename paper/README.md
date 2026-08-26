# Drones Manuscript

`main.tex` uses the MDPI official LaTeX class and the ACS citation template downloaded from `https://www.mdpi.com/authors/latex` on 2026-08-21. The journal class option is `drones`.

Compile with:

```powershell
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

The manuscript deliberately distinguishes real-flight runtime anomaly diagnosis, ground-truth-anomaly-conditioned explanation, Stage-1-gated real-flight analysis, commit-level source-tree inspection candidates, onset-conditioned mutation rankings, and detector-gated replay. Author metadata, CRediT contributions, equal-contribution and correspondence marks, Funding, institutional-review and consent statements, Data Availability, the MDPI-compatible AI-use disclosure, Conflicts of Interest, and Highlights are complete. The MDPI class uses the `moreauthors` option so that the correspondence line and plural copyright wording render correctly.

The final checked submission artifact is `HS-AeroTS_Drones_submission.pdf` (30 pages). It can be rebuilt with:

```powershell
latexmk -pdf -jobname=HS-AeroTS_Drones_submission -interaction=nonstopmode -halt-on-error main.tex
```

The limited recomputation is recorded under `../reports/p13/`; it loads frozen predictions/models only and does not retrain, tune, add data, add baselines, or rerun PX4/SITL replay.

## Working directories

- `sections/`: LaTeX subsection sources grouped by top-level manuscript section. Each completed subsection is the canonical source included by `main.tex`.
- `figures/`: manuscript figures and figure source assets.
- `references/`: verified literature pool and BibTeX metadata used while drafting Sections 1--3.
- `main.tex`: assembled MDPI manuscript source.

Current subsection layout:

```text
sections/
  section_1_introduction/
  section_2_related_work/
  section_3_methodology/
  section_4_experimental_setup/
  section_5_results/
  section_6_discussion/
  section_7_conclusions/
  appendices/
```

Top-level `\section{...}` commands remain in `main.tex`; subsection files begin with `\subsection{...}` and are loaded with `\input`.
