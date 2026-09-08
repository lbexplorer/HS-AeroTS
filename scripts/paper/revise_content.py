"""Apply the approved editorial revision to archived manuscript sources.

No experiment is fitted or scored here. Numeric tables are generated separately
from frozen reports. Rerunning restores this revision from the archived draft.
"""
from pathlib import Path
import re,zipfile

ROOT=Path(__file__).resolve().parents[2]
PAPER=ROOT/'paper'
ARCHIVE=ROOT/'reports/paper_finalization_20260908/pre_revision_manuscript.zip'
def old(name):
    with zipfile.ZipFile(ARCHIVE) as z:return z.read('paper/'+name).decode('utf-8-sig').replace('\r\n','\n')
def put(name,text):
    p=PAPER/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(text.strip()+'\n',encoding='utf-8')
def section(folder,name):return 'sections/'+folder+'/'+name+'.tex'
M='section_3_methodology';E='section_4_experiments_results';D='section_5_discussion'

def main():
    # Remove invalid-run capability estimates without changing historical files.
    p=section(E,'4_3_shap_evidence_software_module_suspect_ranking');s=old(p)
    start=s.index('The controlled-replay propagation ablation')
    end=s.index('Figure~\\ref{fig:shap_module_evidence} summarizes',start)
    s=s[:start]+s[end:]
    start=s.index('At the telemetry-channel level,');end=s.index('\n\nFor the architecture-aware layer',start)
    s=s[:start]+r'''At the telemetry-channel level, agreement depends on the semantic reference. Under the document-derived mapping, overall Consistency@1 was $0.2500\pm0.0056$, compared with the exact random baseline of 0.1707. External Position remained near random and Global Position below random; therefore, the positive masking result is evidence of prediction relevance, not uniform agreement with physical fault domains. Supplementary Material Section S2 reports the complete class-level results and the 11 changed channel assignments.''' +s[end:]
    put(p,s)
    p=section(E,'4_4_strict_external_capability_boundaries');s=old(p)
    start=s.index('The controlled PX4 replay provided');end=s.index('\\begin{figure}',start)
    s=s[:start]+s[end:]
    start=s.index('\\begin{figure}',s.index('\\end{figure}')+1)
    s=s[:start]
    s=s.replace('external data, weak labels, and controlled source mutations','external data, and weak labels')
    put(p,s)
    put(section(E,'4_5_controlled_paired_replay'),r'''
\subsection{Controlled Paired-Replay Extension}
\label{sec:paired_replay_results}

This experiment asks whether a matched healthy replay can provide useful detection-gated module evidence, and whether controlling sampling support improves the distinction between healthy and mutated runs. It evaluates the residual extension in Section~\ref{sec:paired_replay_method}, separately from the learned Stage 1--Stage 2--SHAP chain. In the corrected development comparison, the original learned chain detected 10/12 fault runs but also alarmed on 10/12 independent normal targets; no pair met the clean fault-specific detection criterion. Replacing its gate and then its module evidence with paired residuals yielded 10/12 detections, 1/12 normal alarms, Top-3 coverage of 10/12, and MRR 0.5833. The three-method comparison is provided in Supplementary Material Section S3. These development results motivated a frozen-parameter transfer evaluation rather than a reliability claim.

The main transfer result identifies a useful preprocessing improvement. On the same three transfer source flights, common-support residual computation reduced normal alarms from 11/12 to 3/12 under the frozen paired-residual gate, while retaining 10/12 fault detections. Top-3 and Top-5 both became 10/12, and MRR was 0.6667 (Table~\ref{tab:paired_transfer}). The common-support modification was examined after these transfer flights had been inspected and is therefore exploratory. It does not constitute a new independent confirmation, and its benefits cannot be attributed to retraining the original detector or to SHAP.

\input{generated/paired_transfer_table}

The two methods expose different detection trade-offs. The frozen reference method detected all 12 fault runs, but ten had already alarmed before injection and eleven corresponding normal targets alarmed. Common-support processing reduced the number of pre-injection fault alarms to three and increased clean fault-specific detections from one to seven. Its valid channel--run window fraction averaged 83.3\% (median 97.6\%); unavailable channel windows contributed no evidence. Thus, the comparison includes a change in usable observation support as well as the residual calculation, and coverage accompanies the reported improvement.

The remaining failures are concentrated by mutation. Under common support, Commander and Land Detector each produced 3/3 detections without paired normal alarms. All three EKF2 normal targets alarmed, and all three EKF2 fault runs alarmed before injection, so their 3/3 post-onset recall does not establish fault-specific detection. INAV produced only 1/3 detections, with a delay of 107.623 s; its other two trials remain misses. INAV and Land Detector rankings include tied publishers and do not identify a unique root cause. One Commander transfer trial failed the pre-existing effect-exclusivity check and remains in the 12-trial denominator; its score is not treated as an unambiguous diagnostic success. Supplementary Material Section S4 gives the per-mutation and per-run results.

Channel-specific calibration recovered stronger INAV candidate evidence, but the original-cache variant still produced 8/12 normal alarms despite Top-3/5 of 12/12. Further common-support calibration, within-flight calibration, and a two-healthy-reference variant did not resolve the overall recall--false-alarm trade-off. Their complete comparisons, including 24 additional healthy replays and a control on the same new normal targets, are retained in Supplementary Material Section S5. They are not combined with the best metrics of Table~\ref{tab:paired_transfer} to define a synthetic best method.
''')
    put(section(D,'5_3_replay_negative_result_and_capability_boundary'),r'''
\subsection{Replay Validity, Specificity, and Module Evidence}

The corrected replay experiments support a limited but concrete positive finding: paired residuals can carry module-candidate evidence, and controlling sampling support can reduce normal alarms. This finding depends on an independent healthy reference for the same source flight and on the fixed PX4 revision. It demonstrates an offline controlled extension, not a repair of the learned Stage 1--Stage 2--SHAP chain.

Execution validity must be separated from detector behavior. An earlier replay attempt stopped updating its input sensors before the scheduled injection; endpoint extension nevertheless generated later feature windows. The historical 0/12 detection result and associated onset-conditioned rankings therefore cannot estimate capability on complete mutation replays. Staging the same input locally, enforcing input coverage, correcting clock alignment, and correcting the generic EKF2 startup mode restored an interpretable comparison. On the corrected development data, the original model detected 10/12 fault runs but alarmed on 10/12 independent normal targets. The unresolved limitation is consequently specificity, rather than an inability to produce any alarm. Supplementary Material Section S1 records the execution audit without using the invalid runs as performance evidence.

The transfer study further shows why high recall or Top-$K$ alone is insufficient. Normal estimator variation and sampling differences can cause sustained residual alarms, while weaker INAV changes may remain below a threshold that suppresses those fluctuations. Common-support processing reduced normal alarms, but missed two INAV trials and detected the third late. Class-specific descriptions explain these observed failures; they were not used as inputs to calibration or ranking. The extra reference experiment also failed to stabilize normal behavior across source flights, so the present data do not justify a reliable cross-flight operating point.

Module evidence remains useful as a candidate representation within these conditions. Uniform publisher allocation can retain the mutated module among a small set, but shared publishers produce ties and the final scores summarize all gated windows offline. Timely detection, unique module identification, and causal fault diagnosis therefore remain distinct requirements. The present results support exploratory paired-replay candidate ranking and a measurable sampling-support improvement, with their false-alarm, coverage, and latency limits retained.
''')
    put(section(D,'5_1_principal_findings'),r'''
\subsection{Principal Findings}

For RQ1, the strongest diagnostic result is the learnability of the four annotated fault domains once anomalous windows are supplied. Stage 2 Macro-F1 was 0.8980 under the fixed chronological protocol and 0.9041 under leave-log-out. The complete Cascade is more demanding because Stage 1 can miss anomalies or introduce false alarms; its results and the Direct Five-Class comparison are therefore reported separately. The lower detector AUPRC under strict isolation limits the transfer of fixed-split performance to new flights.

For RQ2, hierarchical evidence preserves the provenance of each statistical contribution and supports a quantitative perturbation test. Validation-ranked SHAP masking caused a greater diagnostic performance decrease than equal-size random masking under both replacement strategies. Conservation verifies the aggregation implementation, while the weaker External and Global Position semantic agreement shows that model relevance and physical fault-domain agreement are different properties.

For RQ3, the commit-specific graph converts topic evidence into source-tree inspection candidates, and the controlled paired-replay extension provides a bounded test against known mutated modules. Common-support residual processing reduced normal alarms from 11/12 to 3/12 while retaining 10/12 detections on the examined transfer set. This positive result coexists with EKF2 false alarms, delayed or missed INAV detections, and static publisher ties. It supports further investigation of diagnostic evidence under matched replay conditions, without establishing reliable end-to-end software fault localization.
''')
    put(section(D,'5_4_limitations_and_future_work'),r'''
\subsection{Limitations and Future Work}

The real-flight evidence has defined limits. UAV-SEAD labels describe runtime anomalies and fault domains, not faulty source modules. The fixed chronological reproduction permits a source log to span partitions; only the leave-log-out protocol enforces complete-log isolation. The channel dictionary was selected by unlabelled corpus coverage, whereas each protocol's scaler and supervised models use its training data. External validation is binary only, and Uncategorized screening lacks temporal labels. Budget-limited CATCH and linear VAR(1) results cannot establish detector superiority over modern alternatives.

The explanation and architecture layers are associative. The semantic mapping is author-defined and not independently expert-adjudicated; External and Global Position consistency is weak. The uORB parser's perfect local agreement is an internal shared-vocabulary check, not an independent gold audit. Conservative path exclusion does not reconstruct a target-specific compiled graph. The real-flight architecture analysis covers the 38.7\% matching-commit anomalous subset, while propagation depends on topic degree and publisher/subscriber semantics. Neither this representation nor its masking tests measure engineering inspection time or causal necessity.

The paired-replay extension requires an additional healthy reference from the same source flight and evaluates only four fixed mutation mechanisms at one firmware commit. Its three development and three transfer source flights provide limited independent variation; extra normal replays do not add new source flights. Although replay parameters were frozen before the first transfer evaluation, the historical P2 scaler had already encountered the transfer sources, and subsequent calibration variants used already inspected transfer flights for exploratory assessment. These results are not a fully untouched-pipeline generalization test. Mutation-effect checks failed for one Commander trial in each source set; those trials remain in the primary denominators. Missing or widely separated observations yield unavailable evidence rather than normality. Full-log interpolation and cadence checks, and whole-run evidence aggregation, also preclude an online or real-time claim.

Future work should first isolate healthy EKF2 replay divergence and improve observation-aware residuals without using mutation-specific prediction rules. Any revised method requires separate development and calibration flights followed by a fully untouched source-flight evaluation, including the scaler. Independent semantic adjudication, per-commit graphs, and runtime topic provenance would address the separate limitations of static module evidence. These are extensions of the present evidence framework rather than prerequisites for interpreting its recorded-data classification and explanation results.
''')
    put(section('section_6_conclusions','6_1_conclusion_summary'),r'''
\subsection{Summary and Outlook}

HS-AeroTS connects recorded PX4 anomaly detection and fault-domain diagnosis with traceable telemetry evidence and commit-specific software inspection candidates. The conditional four-domain classifier achieved Macro-F1 of $0.8980\pm0.0020$ under the fixed chronological protocol and $0.9041\pm0.0029$ under leave-log-out. These results establish conditional diagnostic performance; the complete five-class task additionally inherits the detector's errors and does not show a stable Cascade advantage under strict isolation.

The evidence layer provides a second supported result. Feature provenance allows TreeSHAP magnitudes to be conserved across aggregation levels, and attribution-guided masking causes greater degradation than random masking under the evaluated perturbations. The static uORB graph expresses matching-commit topic evidence as module candidates, with semantic-map sensitivity, graph coverage, and propagation assumptions explicitly retained.

In an exploratory paired-replay extension, common-support residual computation reduced normal alarms from 11/12 to 3/12 while detecting 10/12 fault trials; Top-3/5 were 10/12 and MRR was 0.6667. This improvement is specific to the examined matched, offline replay setting. Persistent normal EKF2 alarms, delayed or missed INAV detections, and limited source-flight independence prevent a reliable cross-flight module-diagnosis claim. The resulting contribution is a reproducible diagnostic evidence framework with demonstrated classification and perturbation-test results, together with a controlled account of where module-candidate ranking remains limited.
''')
    # Methods and evaluation interfaces.
    p=section(M,'3_1_data_preprocessing_feature_representation');s=old(p)
    s=s.replace('so subsequent partitioning and window labeling operated at the flight-log level.','so window construction and labeling never crossed a log boundary. This does not imply that every evaluation partition contains disjoint source logs: the fixed chronological reproduction can split a log across partitions, whereas leave-log-out assigns entire logs to one partition.')
    s=s.replace('This ordering prevents validation and test telemetry from influencing the feature scale.','Within each protocol, this ordering restricts estimation of the feature scale to training-window samples. The fixed 87-channel dictionary, however, was selected using unlabelled coverage across the corpus; it is not a training-only channel-discovery experiment.')
    put(p,s)
    p=section(M,'3_0_problem_formulation');s=old(p)
    s=s.replace('The third output is reported separately under onset-conditioned and detector-gated protocols so that supplied onset information or failure of the runtime gate is not hidden.','The third output is evaluated using corrected controlled replay and a separately defined matched-reference residual extension. Onset-conditioned historical runs with inadequate input coverage are retained only as an execution audit, not capability estimates.')
    put(p,s)
    p=section(M,'3_4_px4_software_module_suspect_ranking');s=old(p)
    start=s.index('The primary static mapping evaluates')
    s=s[:start]+r'''The static SHAP analysis evaluates producer-only, consumer-only, and bidirectional propagation. A sensitivity divides each module's aggregate score by its number of mapped topics before renormalization, exposing dependence on graph degree. Scores can be retained per window or aggregated over the stated matching-commit set; this aggregation does not identify a known defective module in real flights. The paired-replay extension below reuses the publisher relations but supplies residual evidence instead of TreeSHAP evidence, and retains the full 54-module candidate universe. It does not apply the 36-module real-flight exclusion sensitivity to improve replay ranks. Mapping coverage, conservation, and real-flight propagation sensitivity are reported in Section~\ref{sec:shap_module_results}.'''
    put(p,s)
    put(section(M,'3_5_paired_replay_extension'),r'''
\subsection{Matched-Reference Residual Extension for Controlled Replay}
\label{sec:paired_replay_method}

The extension tests whether a target replay differs from an independent healthy replay of the same source log. It reuses the 87 channels, 18 descriptors per channel, frozen scaler, and publisher mapping, but replaces both the learned detection score and the downstream SHAP evidence. Neither target mutation type, injected onset, nor ground-truth module is an input to prediction. Distinct file hashes verify that the healthy target and its reference are different replay outputs. Sensor payload matches among the first 256 six-axis samples establish a constant offset to the source clock without using the injected effect. The target header clock is restored only for reporting detection times.

For feature $j$ and window $w$, define the absolute paired difference $d_{wj}=|f^{\mathrm{target}}_{wj}-f^{\mathrm{ref}}_{wj}|$. In the original paired frontend, reference features are interpolated to target feature times only within the shared basic-sensor support. Independent healthy replay pairs from the other two development source flights estimate a feature noise scale
\begin{equation}
n_j=\max\{Q_{0.99}(d^{\mathrm{healthy}}_{\cdot j}),0.05\},\qquad
r_{wt}=\max_{j\in\mathcal F(t)}d_{wj}/n_j,\qquad s_w=\max_t r_{wt},
\label{eq:paired_residual}
\end{equation}
where $Q_{0.99}$ is the implemented higher-order empirical quantile and $\mathcal F(t)$ contains the features of topic $t$. A gate opens at the third consecutive window with $s_w>\theta$, without backfilling earlier windows. Each development fold sets $\theta$ to the maximum healthy three-window sustained score, with a minimum of 3. Before transfer replay, the existing calibration with the largest numerical threshold, $\theta=26.47158145904541$, and its associated noise vector were frozen. A larger threshold does not guarantee more conservative behavior across different noise vectors; all frozen alternatives are retained as sensitivities in the Supplementary Material.

For the gated set $\mathcal G$, topic evidence is
\begin{equation}
R_t=\frac{1}{|\mathcal G|}\sum_{w\in\mathcal G}\max(r_{wt}-\theta,0),\qquad
S_m=\sum_{t:m\in\mathcal M_t^{(\mathrm{producer})}}R_t/|\mathcal M_t^{(\mathrm{producer})}|.
\label{eq:paired_module}
\end{equation}
Both are zero if no window is gated. The original global gate permits different topics to dominate successive windows; same-channel persistence is a separate supplementary calibration variant. Equation~\eqref{eq:paired_module} aggregates all gated windows, not an onset-defined interval, and yields an offline module ranking.

The common-support frontend changes the observation support before computing Equation~\eqref{eq:paired_residual}. For each topic, exact shared source-clock timestamps are used if they contain at least two packets and cover at least half the shorter stream; otherwise each regenerated stream retains its timestamps. At 10 Hz, both streams must support every sample in a 96-sample channel window. There is no endpoint extrapolation, and interpolation gaps may not exceed the larger of 0.1 s and five times the channel-stream median sampling gap. Invalid channel windows contribute no residual evidence and are recorded as unavailable; fault trials remain in the denominator. Original descriptors, noise, threshold, and publisher allocation remain fixed for the principal frontend comparison. Because cadence and interpolation use complete recorded streams, this procedure is offline even though the three-window gate itself uses only present and past scores.
''')
    p=section(E,'4_1_experimental_setup_protocols');s=old(p)
    start=s.index('The replay protocol fixes');end=s.index('\\begin{table}',start)
    s=s[:start]+r'''Corrected replay fixes PX4 commit \texttt{\seqsplit{82aa24adfca29321cfd1209e287eab6c2b16780e}} and Ubuntu 20.04 WSL, without Gazebo, ROS, QGroundControl, or NuttX. The initial three development source logs and three additional transfer logs each have four mutation conditions (Commander, EKF2, INAV, and Land Detector), with a healthy reference, fault target, and independent normal target. Fixed mutation activation at 30 s is used for evaluation only. Source logs lack \texttt{ekf2\_timestamps}, so EKF2 uses the generic publication adapter with \texttt{ekf2 start}, without the dedicated \texttt{-r} handshake. Input completion, clock alignment, finite estimator outputs, and the original effect checks are reported separately from predictive scores.

The first transfer protocol froze its residual parameters before evaluating the three additional sources. Those sources had appeared in the historical P2 scaler data, so the isolation concerns replay calibration, not a globally untouched preprocessing pipeline. Subsequent common-support and calibration analyses use the same already examined transfer sources and are exploratory. A two-reference sensitivity adds 24 healthy replays across the same six source logs, using the new runs as normal targets and the two older healthy outputs as references. These repeats add no independent source flights. Supplementary Material Sections S1 and S5 specify source identities, data roles, and all controls.

''' +s[end:]
    s=s.replace('Replay intervals use 5000 two-way repetitions that independently resample the three source logs and four mutation types.','New replay results are descriptive counts over three source flights per group; old intervals computed from incomplete replay inputs are not transferred to corrected results.')
    s=s.replace('PX4 replay & Module-ranking ground truth & 3 ULogs $\\times$ 4 mutations $\\times$ baseline/fault; 12 fault runs; 30-s injection & Onset-conditioned and detector-gated results reported separately', 'Paired PX4 replay & Controlled extension & 3 development + 3 transfer sources; 12 fault targets per group; separate healthy targets/references & Frozen transfer followed by explicitly exploratory analyses; source identities in Supplement S1')
    s=s.replace('; replay uses 5000 two-way repetitions.','. Corrected replay counts are descriptive; source-flight dependence is retained.')
    put(p,s)
    p=section(E,'4_2_evaluation_metrics');s=old(p)
    start=s.index('Lower EXAM');end=s.index('\n\nAcross repeated',start)
    s=s[:start]+r'''Higher Top-$K$ and MRR indicate better candidate ranking. All fault trials remain in the denominator. Ranks use the worst position among tied module scores; a module with no positive evidence, or a run with no post-onset detection, contributes zero to Top-$K$ and reciprocal rank. EXAM is defined for traceability but is not used to carry historical incomplete-run estimates into the revised replay results.

For a fault trial, detection recall counts whether any gated window occurs at or after its injected onset. The onset is read only during scoring, after predictions and rankings have been fixed. The normal-run false-alarm rate is the proportion of independent healthy targets with at least one alarm over the entire available run, not a window-level false-positive rate. Pre-onset alarms are reported separately. A clean fault-specific detection additionally requires no alarm before the fault onset and no alarm in the corresponding normal target. This paired criterion is not deployment precision. Delay is measured to the first post-onset gated window only among detected trials, with misses reported separately; module evidence uses all gated windows and the delay is not localization-completion time. Observation duration and valid channel-window coverage accompany common-support results.''' +s[end:]
    s=s.replace('Controlled replay uses two-way cluster bootstrapping over source logs and mutation types.','Corrected replay summaries retain source-flight and mutation identities and do not claim precision from treating the 12 related trials as independent flights.')
    put(p,s)
    # Move budget-limited baselines out of the primary performance table.
    p=section(E,'4_2_real_telemetry_detection_fault_domain_diagnosis');s=old(p)
    s='\n'.join(line for line in s.split('\n') if not line.startswith(' & CATCH') and not line.startswith(' & GCAD-inspired'))
    s=s.replace('$^{\\dagger}$Three seeds and a budget-limited normal-only objective. $^{\\ddagger}$Single ridge-regularized linear VAR(1) ablation, not the published nonlinear GCAD architecture.','Budget-limited normal-only references are reported separately in Supplementary Material Section S6.')
    start=s.index('The matched-input CATCH execution');end=s.index('\n\nOn the 3602',start)
    s=s[:start]+'The budget-limited CATCH and GCAD-inspired VAR(1) feasibility references use different training objectives and budgets from the supervised models. Their complete results are retained in Supplementary Material Section S6 and do not support a detector-superiority claim.'+s[end:]
    put(p,s)
    # Align research questions and remove revision-history prose.
    p=section('section_1_introduction','1_introduction');s=old(p)
    s=s.replace(' The earlier ``FL\'\' suffix is removed because the evaluated system does not establish fault localization.','')
    s=s.replace('with fixed data provenance, log-level isolation, feature construction','with fixed data provenance, explicit chronological and log-isolated protocols, feature construction')
    s=s.replace('feature--channel--topic--subsystem hierarchy','feature-to-channel aggregation and separate topic and subsystem views')
    start=s.index('The proposed modules are evaluated');end=s.index('\n\nThe study is organized',start)
    s=s[:start]+r'''The components are evaluated at their corresponding evidence levels. Real-flight labels assess detection, conditional fault-domain classification, and complete five-class decisions under chronological, purged, and leave-log-out protocols. Conservation, attribution-guided masking, and semantic-map sensitivity assess how model evidence is organized. Matching-commit uORB relations then express topic evidence as source-tree candidates. A separate paired-residual extension evaluates controlled module-candidate ranking after replay execution checks, distinguishing its frozen transfer evaluation from later exploratory preprocessing analyses. This design exposes which gains concern classification, evidence representation, or replay-specific adaptation.''' +s[end:]
    s=s.replace('SHAP conservation, guided masking, semantic-map agreement, and commit-specific uORB propagation','SHAP conservation, guided masking, and semantic-map agreement')
    s=s.replace('Feature-to-subsystem evidence and static architecture associations','Feature-to-channel, topic, and subsystem evidence')
    s=s.replace('Controlled PX4 replay with onset-conditioned and detector-gated ranking','Commit-specific uORB propagation and corrected paired replay')
    s=s.replace('Detector recall, Top-1/3/5, MRR, EXAM','Recall, normal alarms, Top-1/3/5, MRR, delay')
    s=s.replace('Mutation-ground-truth module ranking, conditional on the stated gate','Static candidates and exploratory paired-replay ranking')
    s=s.replace('the boundary between onset-conditioned ranking and detector-gated behavior through strict protocols and controlled source-mutation replay','candidate evidence and its detection-specificity limits through matching-commit analysis and corrected controlled replay')
    s=s.replace('controlled replay under onset-conditioned and detector-gated protocols','corrected paired replay with a separately evaluated residual extension')
    put(p,s)
    p=section('section_2_related_work','2_3_px4_architecture_aware_diagnostic_evidence');s=old(p)
    s=s.replace('Closest real-flight detection reference; no diagnosis or code evidence','Closest reference for the adopted binary detector and descriptors')
    s=s.replace('Supplies attribution tests; no PX4 architecture mapping','Supplies attribution and perturbation-test concepts')
    s=s.replace('Even in that setting, onset-conditioned ranking must be distinguished from detector-gated end-to-end ranking: if the runtime detector does not flag a run, the downstream evidence chain produces no result.','In that setting, both detection specificity and candidate ranking require evaluation: a high rank does not establish that the run was correctly distinguished from a healthy control.')
    s=s.replace('The resulting module list is therefore prioritized evidence for engineering inspection, conditional on the observed telemetry, the explanation model, and the reconstructed PX4 revision.','The resulting list is a candidate representation conditional on the observed telemetry, its evidence source, and the reconstructed PX4 revision.')
    s=s.replace('\\par\\vspace{2pt}{\\scriptsize ``Task-dependent\'\' explanation methods can be attached to different predictors but do not themselves define a diagnosis level.}','')
    put(p,s)
    p=section(D,'5_2_hierarchical_model_and_strict_protocols');s=old(p).replace('this interpretability advantage','this explicit decision structure')
    start=s.index('The full-channel CATCH execution');s=s[:start]+'The resource-limited alternative-model executions remain feasibility references; their objectives and budgets are documented with the complete results in Supplementary Material Section S6. They are not used to claim state-of-the-art superiority.\n'
    put(p,s)
    # Main entry point: keep title, template and author facts.
    s=old('main.tex')
    abstract=r'''Runtime anomaly detection does not by itself provide fault-domain or software inspection evidence. HS-AeroTS combines a LightGBM detector, a conditional four-domain classifier, hierarchical TreeSHAP aggregation, and a commit-specific PX4 uORB graph. Across 1,389 usable UAV-SEAD logs, the conditional classifier achieved five-seed Macro-F1 of $0.8980\pm0.0020$ under fixed chronological evaluation and $0.9041\pm0.0029$ under leave-log-out. Detector AUPRC was $0.7522\pm0.0039$ and $0.6296\pm0.0023$, respectively, showing the importance of source-flight isolation. Complete five-class Cascade results were evaluated separately and did not establish a stable advantage over direct classification under strict protocols. Feature provenance preserved attribution magnitudes across channel, topic, and subsystem views, while validation-ranked SHAP masking caused greater degradation than equal-size random masking. Semantic-map agreement remained weak for two fault domains. The firmware-matched graph translated topic evidence into software-module inspection candidates. A separate, exploratory paired-replay residual extension reduced normal alarms from 11/12 to 3/12 through common-support preprocessing on three previously examined transfer source flights, while retaining 10/12 fault detections; Top-3/5 were 10/12 and MRR was 0.6667. These replay results require matched healthy references and retain false-alarm, latency, and test-exposure limitations. HS-AeroTS thus provides recorded-data fault-domain classification and traceable architecture-aware evidence, with controlled improvements in paired-replay specificity rather than a demonstrated reliable end-to-end root-cause diagnosis capability.'''
    s=re.sub(r'\\abstract\{.*?\}\n\\keyword',lambda m:'\\abstract{'+abstract+'}\n\\keyword',s,flags=re.S)
    s=s.replace('\\item A two-stage hierarchy separates real-flight anomaly detection from four-domain diagnosis.','\\item Conditional four-domain classification is evaluated under chronological and log-isolated protocols.')
    s=s.replace('\\item TreeSHAP evidence is conserved across features, channels, uORB topics, and subsystems.','\\item Traceable TreeSHAP aggregation is tested by conservation and attribution-guided masking.')
    s=s.replace('\\item Strict isolation and controlled replay expose leakage sensitivity and detector-gated limits.','\\item Common-support paired replay reduces normal alarms with detection and latency limits reported.')
    s=s.replace('\\input{sections/section_3_methodology/3_4_px4_software_module_suspect_ranking}','\\input{sections/section_3_methodology/3_4_px4_software_module_suspect_ranking}\n\\input{sections/section_3_methodology/3_5_paired_replay_extension}')
    s=s.replace('\\input{sections/section_4_experiments_results/4_4_strict_external_capability_boundaries}','\\input{sections/section_4_experiments_results/4_4_strict_external_capability_boundaries}\n\\input{sections/section_4_experiments_results/4_5_controlled_paired_replay}')
    s=s.replace('OpenAI Codex (GPT-5-based Codex agent, accessed in August 2026) to generate inference-only recalculation code, assist with statistical interpretation, and revise the language and structure of the manuscript.','OpenAI Codex during August--September 2026 to assist with analysis and replay-experiment code, result interpretation, manuscript revision, and figure preparation.')
    s=s.replace('The authors\' analysis source code and a public machine-readable Supplement are not provided. Aggregate numerical results, the complete semantic mapping, software versions, exclusion rules, split counts, and statistical settings are included in the article and its appendices. Subject to third-party licenses, selected frozen configurations, split manifests, the 180-edge table, per-seed predictions, and derived machine-readable reports may be obtained from the corresponding author on reasonable request for confidential editorial or peer-review assessment.','The accompanying Supplementary Material reports corrected replay protocols, complete auxiliary comparisons, and per-trial outcomes. The analysis repository is identified as \\url{https://github.com/lbexplorer/HS-AeroTS}; artifact availability and the revision-specific source manifest are documented with the submission package. Raw replay outputs and trained model files are not implied to be included by this repository reference. The article and appendices provide the complete semantic mapping, software versions, exclusion rules, split counts, and statistical settings. Requests for additional artifacts remain subject to the underlying data and software licenses.')
    s=s.replace('\\authorcontributions{','\\supplementary{Supplementary Material: corrected replay validity and source roles; semantic-map sensitivity; corrected development comparisons; transfer per-mutation and per-run results; complete calibration and reference ablations; resource-limited baselines and reproducibility details.}\n\n\\authorcontributions{')
    put('main.tex',s)
    p=section('appendices','appendix_b_reproducibility_details');s=old(p)
    s=s.replace('Controlled-replay intervals used 5000 crossed cluster resamples of three source logs and four mutation types.','Historical replay intervals used incomplete input runs and are excluded from the revised capability results. Corrected replay counts and their source-flight identities are provided descriptively in the Supplementary Material; no historical interval is reused.')
    s=s.replace('No model was retrained or tuned.','No supervised model was retrained or tuned for this revision. The separate replay residual and calibration variants are described in Section~\\ref{sec:paired_replay_method} and the Supplementary Material; they do not alter the real-flight models.')
    put(p,s)
    print('Content revision applied from archived sources')

if __name__=='__main__':main()
