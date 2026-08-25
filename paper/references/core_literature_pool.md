# HS-AeroTS-FL Core Literature Pool

Last verified: 2026-08-25

This pool is the controlled citation source for Sections 1--3. It contains 40 core references selected for direct relevance rather than as a generic bibliography. Before final submission, recheck publication status, author order, volume, issue, pages, DOI, and access dates. In particular, UAV-SEAD and AeroTSBoost are currently arXiv preprints.

## A. UAV Telemetry, Fault Diagnosis, and PX4 Architecture (10)

| Key | Reference | Primary role | Planned placement | Verified source |
|---|---|---|---|---|
| `kabaoglu2026uavsead` | Kabaoglu and Sariel, “UAV-SEAD: State Estimation Anomaly Dataset for UAVs,” arXiv:2602.13900, 2026. | Main real-flight dataset and four anomaly domains | 1.1, 3.1, 4.1 | [arXiv](https://arxiv.org/abs/2602.13900) |
| `wei2026aerotsboost` | Wei et al., “AeroTSBoost: Temporal-Statistical Boosting for Real-World UAV Telemetry Anomaly Mining,” arXiv:2605.25639, 2026. | Closest detector and feature protocol | 1.1, 2.1, 3.1–3.2 | [arXiv](https://arxiv.org/abs/2605.25639) |
| `keipour2021alfa` | Keipour, Mousaei, and Scherer, “ALFA: A Dataset for UAV Fault and Anomaly Detection,” *IJRR*, 40(2), 515–520, 2021. | External real-flight fault dataset | 1.1, 2.1, 4.1 | [DOI](https://doi.org/10.1177/0278364920966642) |
| `keipour2019automatic` | Keipour, Mousaei, and Scherer, “Automatic Real-Time Anomaly Detection for Autonomous Aerial Vehicles,” *ICRA*, 5679–5685, 2019. | Online UAV anomaly detection and ALFA antecedent | 1.1, 2.1 | [DOI](https://doi.org/10.1109/ICRA.2019.8794286) |
| `fourlas2021survey` | Fourlas and Karras, “A Survey on Fault Diagnosis and Fault-Tolerant Control Methods for Unmanned Aerial Vehicles,” *Machines*, 9(9), 197, 2021. | UAV fault-diagnosis taxonomy | 1.1, 2.1 | [DOI](https://doi.org/10.3390/machines9090197) |
| `puchalski2022uav` | Puchalski and Giernacki, “UAV Fault Detection Methods, State-of-the-Art,” *Drones*, 6(11), 330, 2022. | Real-flight versus simulation evidence and fault types | 1.1, 2.1 | [DOI](https://doi.org/10.3390/drones6110330) |
| `adaika2025fdd` | Adaika et al., “Fault Detection and Diagnosis Methodologies for Unmanned Aerial Vehicles: State-of-the-Art,” *J. Intell. Robot. Syst.*, 111, 63, 2025. | Recent UAV FDD survey | 1.1, 2.1 | [DOI](https://doi.org/10.1007/s10846-025-02267-8) |
| `tan2026anomaly` | Tan et al., “Anomaly Management in Unmanned Aerial Vehicles: A Systematic Literature Review,” *IEEE Access*, 14, 117991–118010, 2026. | Full anomaly-management lifecycle and benchmark gaps | 1.1–1.2, 2.4 | [DOI](https://doi.org/10.1109/ACCESS.2026.3716292) |
| `meier2015px4` | Meier, Honegger, and Pollefeys, “PX4: A Node-Based Multithreaded Open Source Robotics Framework for Deeply Embedded Platforms,” *ICRA*, 6235–6240, 2015. | PX4 modular publish–subscribe architecture | 1.1–1.2, 2.3, 3.4 | [DOI](https://doi.org/10.1109/ICRA.2015.7140074) |
| `px4uorbdocs2026` | PX4 Development Team, “uORB Messaging” and “uORB Publication/Subscription Graph,” official documentation. | Primary technical source for uORB semantics and graph | 2.3, 3.4 | [uORB](https://docs.px4.io/main/en/middleware/uorb) / [graph](https://docs.px4.io/main/en/middleware/uorb_graph) |

## B. Time-Series Anomaly Detection, Models, and Evaluation (18)

| Key | Reference | Primary role | Planned placement | Verified source |
|---|---|---|---|---|
| `ke2017lightgbm` | Ke et al., “LightGBM: A Highly Efficient Gradient Boosting Decision Tree,” *NeurIPS*, 2017. | Stage 1 and Stage 2 learner | 2.1, 3.2 | [NeurIPS](https://proceedings.neurips.cc/paper_files/paper/2017/hash/6449f44a102fde848669bdd9eb6b76fa-Abstract.html) |
| `liu2008isolation` | Liu, Ting, and Zhou, “Isolation Forest,” *ICDM*, 413–422, 2008. | Classical anomaly-detection baseline family | 2.1 | [DOI](https://doi.org/10.1109/ICDM.2008.17) |
| `ruff2018deep` | Ruff et al., “Deep One-Class Classification,” *ICML*, PMLR 80:4393–4402, 2018. | Deep one-class anomaly detection | 2.1 | [PMLR](https://proceedings.mlr.press/v80/ruff18a) |
| `zhang2019mscred` | Zhang et al., “A Deep Neural Network for Unsupervised Anomaly Detection and Diagnosis in Multivariate Time Series Data,” *AAAI*, 33(1), 1409–1416, 2019. | Reconstruction and inter-sensor modeling | 2.1 | [DOI](https://doi.org/10.1609/aaai.v33i01.33011409) |
| `su2019omnianomaly` | Su et al., “Robust Anomaly Detection for Multivariate Time Series through Stochastic Recurrent Neural Network,” *KDD*, 2828–2837, 2019. | Probabilistic recurrent detector | 2.1 | [DOI](https://doi.org/10.1145/3292500.3330672) |
| `audibert2020usad` | Audibert et al., “USAD: UnSupervised Anomaly Detection on Multivariate Time Series,” *KDD*, 3395–3404, 2020. | Adversarial autoencoder detector | 2.1 | [DOI](https://doi.org/10.1145/3394486.3403392) |
| `zhao2020mtadgat` | Zhao et al., “Multivariate Time-Series Anomaly Detection via Graph Attention Network,” *ICDM*, 841–850, 2020. | Temporal and channel graph attention | 2.1 | [DOI](https://doi.org/10.1109/ICDM50108.2020.00093) |
| `deng2021gdn` | Deng and Hooi, “Graph Neural Network-Based Anomaly Detection in Multivariate Time Series,” *AAAI*, 35(5), 4027–4035, 2021. | Learned sensor dependency graph | 2.1–2.2 | [DOI](https://doi.org/10.1609/aaai.v35i5.16523) |
| `tuli2022tranad` | Tuli, Casale, and Jennings, “TranAD: Deep Transformer Networks for Anomaly Detection in Multivariate Time Series Data,” *PVLDB*, 15(6), 1201–1214, 2022. | Transformer anomaly detection and diagnosis | 2.1 | [DOI](https://doi.org/10.14778/3514061.3514067) |
| `xu2022anomaly` | Xu et al., “Anomaly Transformer: Time Series Anomaly Detection with Association Discrepancy,” *ICLR*, 2022. | Association-based transformer detector | 2.1 | [OpenReview](https://openreview.net/forum?id=LzQQ89U1qm_) |
| `wu2025catch` | Wu et al., “CATCH: Channel-Aware Multivariate Time Series Anomaly Detection via Frequency Patching,” *ICLR*, 2025. | Official CATCH baseline context | 2.1, Supplementary S6 | [OpenReview](https://openreview.net/forum?id=m08aK3xxdJ) |
| `liu2025gcad` | Liu, Gao, and Jiao, “GCAD: Anomaly Detection in Multivariate Time Series from the Perspective of Granger Causality,” *AAAI*, 39(18), 19041–19049, 2025. | Official GCAD context; distinguish from linear ablation | 2.1, Supplementary S6 | [DOI](https://doi.org/10.1609/aaai.v39i18.34096) |
| `wenig2022timeeval` | Wenig, Schmidl, and Papenbrock, “TimeEval: A Benchmarking Toolkit for Time Series Anomaly Detection Algorithms,” *PVLDB*, 15(12), 3678–3681, 2022. | Reproducible TSAD benchmarking | 2.1, 4.2 | [DOI](https://doi.org/10.14778/3554821.3554873) |
| `wu2023benchmarks` | Wu and Keogh, “Current Time Series Anomaly Detection Benchmarks Are Flawed and Are Creating the Illusion of Progress,” *IEEE TKDE*, 35(3), 2421–2429, 2023. | Split leakage and benchmark validity | 1.2, 2.1, 4.2 | [DOI](https://doi.org/10.1109/TKDE.2021.3112126) |
| `tatbul2018precision` | Tatbul et al., “Precision and Recall for Time Series,” *NeurIPS*, 2018. | Range/event-aware evaluation | 2.1, 4.2 | [NeurIPS](https://proceedings.neurips.cc/paper/2018/hash/8f468c873a32bb0619eaeb2050ba45d1-Abstract.html) |
| `saito2015precision` | Saito and Rehmsmeier, “The Precision–Recall Plot Is More Informative than the ROC Plot When Evaluating Binary Classifiers on Imbalanced Datasets,” *PLOS ONE*, 10(3), e0118432, 2015. | Justification for AUPRC emphasis | 2.1, 3.2, 4.2 | [DOI](https://doi.org/10.1371/journal.pone.0118432) |
| `davis2006relationship` | Davis and Goadrich, “The Relationship Between Precision–Recall and ROC Curves,” *ICML*, 233–240, 2006. | PR/ROC metric theory | 2.1, 4.2 | [DOI](https://doi.org/10.1145/1143844.1143874) |
| `lavin2015nab` | Lavin and Ahmad, “Evaluating Real-Time Anomaly Detection Algorithms—The Numenta Anomaly Benchmark,” arXiv:1510.03336, 2015. | Timely/event-aware anomaly scoring context | 2.1, 4.2 | [arXiv](https://arxiv.org/abs/1510.03336) |

## C. Explainable Machine Learning and Attribution Validation (8)

| Key | Reference | Primary role | Planned placement | Verified source |
|---|---|---|---|---|
| `lundberg2017shap` | Lundberg and Lee, “A Unified Approach to Interpreting Model Predictions,” *NeurIPS*, 2017. | SHAP foundation | 2.2, 3.3 | [NeurIPS](https://proceedings.neurips.cc/paper/2017/hash/8a20a8621978632d76c43dfd28b67767-Abstract.html) |
| `lundberg2020trees` | Lundberg et al., “From Local Explanations to Global Understanding with Explainable AI for Trees,” *Nature Machine Intelligence*, 2, 56–67, 2020. | Exact tree attribution and global aggregation | 2.2, 3.3 | [DOI](https://doi.org/10.1038/s42256-019-0138-9) |
| `bento2021timeshap` | Bento et al., “TimeSHAP: Explaining Recurrent Models through Sequence Perturbations,” *KDD*, 2565–2573, 2021. | Sequential SHAP comparison | 2.2 | [DOI](https://doi.org/10.1145/3447548.3467166) |
| `ribeiro2016lime` | Ribeiro, Singh, and Guestrin, “Why Should I Trust You?: Explaining the Predictions of Any Classifier,” *KDD*, 1135–1144, 2016. | Model-agnostic local explanations | 2.2 | [DOI](https://doi.org/10.1145/2939672.2939778) |
| `sundararajan2017axiomatic` | Sundararajan, Taly, and Yan, “Axiomatic Attribution for Deep Networks,” *ICML*, PMLR 70:3319–3328, 2017. | Attribution axioms and completeness | 2.2 | [PMLR](https://proceedings.mlr.press/v70/sundararajan17a.html) |
| `adebayo2018sanity` | Adebayo et al., “Sanity Checks for Saliency Maps,” *NeurIPS*, 2018. | Quantitative explanation sanity checks | 2.2, 3.3 | [NeurIPS](https://proceedings.neurips.cc/paper/2018/hash/294a8ed24b1ad22ec2e7efea049b8737-Abstract.html) |
| `hooker2019benchmark` | Hooker et al., “A Benchmark for Interpretability Methods in Deep Neural Networks,” *NeurIPS*, 2019. | Removal-based faithfulness and random baselines | 2.2, 3.3 | [NeurIPS](https://proceedings.neurips.cc/paper/2019/hash/fe4b8556000d0f0cae99daa5c5c5a410-Abstract.html) |
| `hedstrom2023quantus` | Hedström et al., “Quantus: An Explainable AI Toolkit for Responsible Evaluation of Neural Network Explanations and Beyond,” *JMLR*, 24(34), 1–11, 2023. | Explanation-evaluation taxonomy | 2.2, 3.3 | [JMLR](https://www.jmlr.org/papers/v24/22-0142.html) |

## D. Software Fault Localization and Mutation Evidence (4)

| Key | Reference | Primary role | Planned placement | Verified source |
|---|---|---|---|---|
| `wong2016survey` | Wong et al., “A Survey on Software Fault Localization,” *IEEE TSE*, 42(8), 707–740, 2016. | Fault-localization definitions, spectra, and ranking metrics | 1.2, 2.3 | [DOI](https://doi.org/10.1109/TSE.2016.2521368) |
| `jones2002visualization` | Jones, Harrold, and Stasko, “Visualization of Test Information to Assist Fault Localization,” *ICSE*, 467–477, 2002. | Suspiciousness ranking antecedent | 2.3 | [DOI](https://doi.org/10.1145/581339.581397) |
| `pearson2017evaluating` | Pearson et al., “Evaluating and Improving Fault Localization,” *ICSE*, 609–620, 2017. | Top-k evaluation and artificial-versus-real fault validity | 2.3, 4.3 | [DOI](https://doi.org/10.1109/ICSE.2017.62) |
| `papadakis2019mutation` | Papadakis et al., “Mutation Testing Advances: An Analysis and Survey,” *Advances in Computers*, 112, 275–378, 2019. | Controlled source mutation methodology and limitations | 2.3, 4.3 | [DOI](https://doi.org/10.1016/bs.adcom.2018.03.015) |

## Citation-use rules

1. Cite original papers for method definitions; use surveys only for taxonomy or field-level synthesis.
2. Do not cite UAV-SEAD labels as source-code bug ground truth.
3. Do not use PX4/uORB documentation to claim causality; it supports only version-specific publish–subscribe dependencies.
4. Cite both the positive method source and the relevant evaluation/limitation source when discussing explainability or anomaly benchmarks.
5. Treat UAV-SEAD and AeroTSBoost as preprints until their publication status is rechecked.
6. Add papers beyond this pool only when a paragraph contains a claim not covered here or when a direct recent competitor must be included.
