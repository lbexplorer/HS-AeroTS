# 文献与公开范围核验记录

日期：2026-09-08。共核实 26 项 DOI 元数据及 4 项 GitHub 公共接口响应。元数据核验不等于逐篇全文复审。

| DOI | 标题 | 卷 | 页码/文章编号（元数据原值） |
|---|---|---|---|
| 10.1007/s10846-025-02267-8 | Fault Detection and Diagnosis Methodologies for Unmanned Aerial Vehicles: State-of-the-Art | 111 |  |
| 10.1016/bs.adcom.2018.03.015 | Mutation Testing Advances: An Analysis and Survey |  | 275-378 |
| 10.1038/s42256-019-0138-9 | From local explanations to global understanding with explainable AI for trees | 2 | 56-67 |
| 10.1109/access.2026.3716292 | Anomaly Management in Unmanned Aerial Vehicles: A Systematic Literature Review | 14 | 117991-118010 |
| 10.1109/icdm.2008.17 | Isolation Forest |  | 413-422 |
| 10.1109/icra.2015.7140074 | PX4: A node-based multithreaded open source robotics framework for deeply embedded platforms |  | 6235-6240 |
| 10.1109/icra.2019.8794286 | Automatic Real-time Anomaly Detection for Autonomous Aerial Vehicles |  | 5679-5685 |
| 10.1109/icse.2017.62 | Evaluating and Improving Fault Localization |  | 609-620 |
| 10.1109/tim.2025.3571126 | Multiscale Transformers With Contrastive Learning for UAV Anomaly Detection | 74 | 1-15 |
| 10.1109/tim.2026.3718566 | A Dynamics-Constrained Probabilistic Method for Adaptive Anomaly Detection in UAVs | 75 | 3521111-3521111 |
| 10.1109/tkde.2021.3112126 | Current Time Series Anomaly Detection Benchmarks are Flawed and are Creating the Illusion of Progress |  | 1-1 |
| 10.1109/tse.2016.2521368 | A Survey on Software Fault Localization | 42 | 707-740 |
| 10.1145/1143844.1143874 | The relationship between Precision-Recall and ROC curves |  | 233-240 |
| 10.1145/2939672.2939778 | "Why Should I Trust You?" |  | 1135-1144 |
| 10.1145/3292500.3330672 | Robust Anomaly Detection for Multivariate Time Series through Stochastic Recurrent Neural Network |  | 2828-2837 |
| 10.1145/3447548.3467166 | TimeSHAP: Explaining Recurrent Models through Sequence Perturbations |  | 2565-2573 |
| 10.1145/581396.581397 | Visualization of test information to assist fault localization |  | 467 |
| 10.1177/0278364920966642 | ALFA: A dataset for UAV fault and anomaly detection | 40 | 515-520 |
| 10.1371/journal.pone.0118432 | The Precision-Recall Plot Is More Informative than the ROC Plot When Evaluating Binary Classifiers on Imbalanced Datasets | 10 | e0118432 |
| 10.14778/3514061.3514067 | TranAD | 15 | 1201-1214 |
| 10.14778/3554821.3554873 | TimeEval | 15 | 3678-3681 |
| 10.1609/aaai.v33i01.33011409 | A Deep Neural Network for Unsupervised Anomaly Detection and Diagnosis in Multivariate Time Series Data | 33 | 1409-1416 |
| 10.1609/aaai.v35i5.16523 | Graph Neural Network-Based Anomaly Detection in Multivariate Time Series | 35 | 4027-4035 |
| 10.1609/aaai.v39i18.34096 | GCAD: Anomaly Detection in Multivariate Time Series from the Perspective of Granger Causality | 39 | 19041-19049 |
| 10.3390/drones6110330 | UAV Fault Detection Methods, State-of-the-Art | 6 | 330 |
| 10.3390/machines9090197 | A Survey on Fault Diagnosis and Fault-Tolerant Control Methods for Unmanned Aerial Vehicles | 9 | 197 |

新 baseline 的出版信息已通过出版社向 Crossref 登记的元数据确认，MTCL 另与作者仓库引文一致。LDC-P-VAE 的 IEEE 全文页面本轮不可读取；未利用二手摘要为其增加细节或性能论断。

关键主张核验范围：

- MTCL 模型与损失：作者公开仓库固定 commit 的模型和实验源码；官方默认评估中测试分数参与阈值、真值调整预测的事实由源码直接核实。
- UAV-SEAD 与 AeroTSBoost：原作者 arXiv 条目；保留前者数据定义和后者实现来源身份。
- TreeSHAP：Nature Machine Intelligence 的原文摘要支持树模型解释和局部到整体聚合；不据此声称物理因果。
- PX4：官方 uORB 文档支持发布/订阅接口；静态图不是编译或运行时因果图的限定来自本地实现与任务定义。
- GCAD：AAAI 原始条目确认其 Granger 视角；本地 VAR(1) 不冒称 GCAD 原架构复现。
- ALFA：AirLab 原始数据页面确认其物理故障类别；不能直接映射到本文四域标签。
- 其他旧引文保留已有文献池记录，本轮不声称重读了全部 38 篇全文；删除需要排他性证据的“没有诊断/代码证据”表述。

公开仓库：GitHub 无认证接口确认 lbexplorer/HS-AeroTS 为 public，main=264d1f70ef78bba19d56eed1b8b9fd679056db84。该树含 corrected_results/summary.csv，但没有 P15 路径；论文已明确区分已公开 P9 与本地后续分析。本次未推送 GitHub。

原引用 Jones et al. 的 DOI 10.1145/581339.581397 在 Crossref 返回别名 10.1145/581396.581397，标题与作者一致，原出版社资源 URL 仍指向 581339.581397；保留原条目，避免把别名误判为另一论文。ALFA online-first 2020 与卷期出版 2021 不冲突。
