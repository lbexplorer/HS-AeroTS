# Drones Manuscript

`main.tex` uses the MDPI official LaTeX class and the ACS citation template downloaded from `https://www.mdpi.com/authors/latex` on 2026-08-21. The journal class option is `drones`.

Compile with:

```powershell
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

The manuscript deliberately distinguishes real-flight runtime anomaly diagnosis, static software-module suspects, onset-conditioned mutation rankings, and detector-gated end-to-end results. Replace author and affiliation placeholders and complete verified bibliography metadata before submission.

## Working directories

- `sections/`: LaTeX subsection sources grouped by top-level manuscript section. Each completed subsection is the canonical source included by `main.tex`.
- `figures/`: manuscript figures and figure source assets.
- `main.tex`: assembled MDPI manuscript source.

Current subsection layout:

```text
sections/
  section_3_methodology/
  section_4_experimental_setup/
  section_5_results/
```

Top-level `\section{...}` commands remain in `main.tex`; subsection files begin with `\subsection{...}` and are loaded with `\input`.
