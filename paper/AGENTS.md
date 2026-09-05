# HS-AeroTS-FL Manuscript Revision Rules

This directory contains the HS-AeroTS-FL manuscript targeting MDPI *Drones*.
The current task is to refine the manuscript section by section, improving clarity, completeness, logic, and formatting rather than rebuilding the paper from scratch.

## 1. Sources and Revision Scope

1. Prioritize, in order:
   - the current manuscript and requested section;
   - `写论文思路.docx`;
   - verified results under `reports/`;
   - the paper outline, project `README.md`, code, and experiment records.

2. Use the reference paper by Zhang et al. only for its argument structure:
   problem → challenge → method → mathematical formulation → experiment question → evidence → conclusion.
   Do not copy its wording, IEEE formatting, or technical content.

3. Read adjacent sections when necessary to preserve consistency, but modify only the requested scope unless a broader revision is explicitly requested.

4. Before revising, briefly identify:
   - unclear or missing information;
   - weak logical transitions;
   - unsupported claims;
   - inconsistent terminology, notation, or formatting.

## 2. Core Writing Logic

Maintain the following evidence chain throughout the paper:

**Research problem → limitation or overlooked issue → motivation → proposed component → experimental evidence → bounded conclusion**

Each paragraph should normally contain:
- a clear topic sentence;
- explanation, evidence, or technical detail;
- a concluding or transitional sentence.

Avoid isolated facts, undefined concepts, abrupt transitions, repeated descriptions, generic filler, and unnecessarily complicated sentences.

## 3. Section-Specific Requirements

### Introduction
Present the task and context, summarize dominant approaches, identify their shared focus or unresolved issue, introduce the motivation, and explain how each proposed component addresses that issue. End with approximately three parallel and non-overlapping contributions.

### Related Work
Organize studies into two or three relevant themes and synthesize methodological trends instead of listing papers individually. Clearly position this work relative to each theme. Prefer:

“Existing studies mainly focus on ..., whereas this work investigates ...”

Avoid dismissive claims such as “previous methods fail to ...”.

### Problem Formulation and Method
Define inputs, outputs, ground truth, symbols, and task objectives before using them. Introduce the overall pipeline first, then explain the proposed components in detail. Describe reused models or standard procedures briefly.

Every equation must have a clear purpose, define all symbols, and connect to the surrounding text, algorithm, figure, or implementation. Explain why each proposed component addresses the stated research problem.

### Experiments and Results
State the research questions that each experiment answers. Report datasets, splits, baselines, metrics, implementation details, and ablation settings clearly enough for reproduction.

For each result:
1. state the main observation;
2. support it with exact numerical evidence;
3. compare it with the relevant baseline or setting;
4. provide only a cautious, evidence-supported explanation.

Ensure that every ablation corresponds to a claimed component or motivation. Preserve negative results and capability boundaries rather than hiding them. Keep Results focused on observations; reserve broader implications for Discussion.

### Conclusion
Summarize the problem, method, principal evidence, practical significance, and limitations. Do not introduce new experiments, mechanisms, or claims.

## 4. Scientific Boundaries

- Never invent results, parameters, references, implementation details, or statistical conclusions. Mark missing information as `[TO VERIFY]`.
- Prefer the terms `runtime anomaly detection`, `fault-domain diagnosis`, `architecture-aware diagnostic evidence`, and `software-module suspect ranking`.
- Do not describe SHAP attribution or static PX4 uORB mapping as causal analysis or root-cause localization.
- Do not claim that Cascade consistently outperforms Direct Five-Class unless supported by the reported results.
- Clearly distinguish fixed chronological, purged, leave-log-out, ALFA, and PX4 replay experiments.
- Preserve the P9 detector-gated negative result as an important capability boundary.
- Distinguish recorded-data evaluation from onboard, online, or real-time deployment.
- Use calibrated expressions such as `suggests`, `indicates`, or `is consistent with` when evidence does not establish causality.

## 5. Style and Formatting

- Use concise, formal, and objective academic English suitable for *Drones*.
- Preserve the journal template, heading hierarchy, citation style, and section numbering.
- Define each acronym and symbol at first use and keep terminology consistent.
- Refer to every figure and table in the text and explain what evidence it provides.
- Avoid Markdown syntax, manual headings, unnecessary bullet lists, malformed equations, inconsistent captions, and irregular paragraph spacing in the manuscript.
- Prefer targeted revision over wholesale rewriting.

## 6. Final Check and Handoff

Before completing a revision, verify:
- logical completeness and paragraph transitions;
- numerical and experimental accuracy;
- consistency among claims, equations, figures, tables, and results;
- terminology, notation, citations, captions, and formatting;
- compliance with all scientific boundaries above.

After each requested revision, briefly report:
1. the main issues corrected;
2. any unresolved `[TO VERIFY]` items;
3. the most logical next section or task.
