# HS-AeroTS-FL：面向 MDPI *Drones* 的精简论文大纲

## 论文定位

- **文章类型**：MDPI *Drones* Article。正文采用 Introduction、Related Work、Methodology、Experimental Setup、Results、Discussion、Conclusions 七个部分；其中 Methodology 和 Experimental Setup 对应期刊常见的 Materials and Methods。
- **论文主线**：**异常检测 → 故障域诊断 → SHAP 可解释证据 → PX4 软件模块嫌疑度 → 严格验证与能力边界**。
- **核心术语**：使用 `software-module suspect ranking` 和 `architecture-aware diagnostic evidence`；不使用“root-cause localization”作为主要贡献表述。
- **建议规模**：正文约 8--10 个排版页，5 张核心图、5 张核心表；完整配置、逐类指标、逐 run replay 结果放入 Supplementary Materials。

## Research Questions（精简为 3 个）

- **RQ1：** HS-AeroTS-FL 能否在真实 PX4 UAV 遥测上完成运行时异常检测，并将已检测异常区分为四类故障域？
- **RQ2：** 分层 SHAP 和 PX4 uORB 映射能否形成具有守恒性、必要性和可追溯性的 architecture-aware diagnostic evidence，并输出软件模块嫌疑度排序？
- **RQ3：** 在严格数据隔离、外部数据和受控 PX4 mutation replay 下，该证据链的泛化能力和能力边界是什么？

## 证据组织原则

- **主结果**：P1--P4 的数据、异常检测、故障域诊断和 SHAP 解释；P11 作为严格隔离主验证。
- **支撑验证**：P6 ALFA 外部二元检测、P7 Uncategorized 航次级弱标签筛查、P8 固件匹配的 uORB 映射。
- **严格性分析**：P10 purged 和 P11 leave-log-out；不单独按 P1--P11 展开成项目报告。
- **能力边界**：P9 必须报告 detector-gated `0/12` 检测召回；onset-conditioned 排名只能作为条件性模块证据。
- **明确不主张**：P10/P11 不支持 Cascade 稳定优于 Direct Five-Class；静态 topic-to-module 映射不等于根因证明。

## Outline-only Evidence Map

| 论文主张 | 放置位置 | 直接证据 | 必须同时呈现的限定 |
|---|---|---|---|
| 真实遥测可支持运行时异常检测 | 5.1、6.1 | P1/P2、P11 Stage 1 | leave-log-out AUPRC 低于固定 chronological |
| 明确异常窗口可进行四类故障域诊断 | 5.1、6.1 | P3、P11 Stage 2 | Stage 2 是 anomaly-only 任务，不等于完整在线诊断 |
| SHAP 可形成可追溯诊断证据 | 5.2、6.1 | P4 守恒、masking、Consistency@K | External Position 一致性接近随机基线；不作因果解释 |
| uORB 映射可生成模块嫌疑度 | 3.4、5.2、6.1 | P8 映射覆盖和守恒 | 静态、版本相关，属于 suspect ranking |
| 完整链路能力受域偏移限制 | 5.3、6.3、6.4 | P9、P10、P11 | P9 detector-gated recall 为 0/12；不能用 onset-conditioned 结果替代 |

该表用于写作和审稿自检，不作为正文新增表格；正文中的 Table 1--5 保持不变。

# Front Matter（投稿前补齐，不计入正文七章）

## Highlights（*Drones* 要求）

- **Main findings**：用不超过两条要点概括真实遥测检测、故障域诊断和 SHAP/uORB 证据链。
- **Implications**：用不超过两条要点说明模块嫌疑度的工程用途及 P9 `0/12` detector-gated 边界。

## Abstract 与 Keywords

- Abstract 控制在约 200 words 以内，按 Background、Methods、Results、Conclusion 的顺序组织为单段；只使用正文已报告的结果。
- Keywords 控制为 3--10 个，建议围绕 UAV telemetry、runtime anomaly detection、fault-domain diagnosis、explainable machine learning、PX4、uORB、software-module suspect ranking。

# 1. Introduction

## 1.1 工程问题

- 说明飞行遥测异常检测只能回答“是否异常”，而飞控工程诊断还需要故障域、可解释遥测证据和 PX4 模块检查线索。
- 说明真实飞行标签表示运行时异常或故障域，不应直接解释为 PX4 源代码缺陷。
- **对应证据**：P1 数据审计、P2 异常检测、P3 故障域诊断。

## 1.2 研究缺口与本文方案

- 异常检测、故障诊断和软件架构证据通常分开评价。
- 特征重要性通常没有形成从 telemetry channel 到 PX4 module 的可追溯链路。
- 软件模块排名如果没有严格的检测门控和 mutation ground truth，容易被误读为根因结论。
- 本文提出 HS-AeroTS-FL，将运行时异常、四类故障域、SHAP 证据和版本匹配的 PX4 uORB 依赖组织为一条诊断证据链。

## 1.3 研究问题与贡献

- 列出 RQ1--RQ3。
- **贡献 1**：真实 PX4 遥测上的可复现异常检测和故障域诊断协议。
- **贡献 2**：从统计特征、channel、topic、subsystem 到 module 的 SHAP/uORB 可追溯证据链。
- **贡献 3**：通过严格划分、外部数据和受控 replay 量化证据链的有效范围，而不是夸大其模块定位能力。

**Figure 1：** HS-AeroTS-FL 总体框架，合并展示模型链路、SHAP/uORB 证据链和三类验证分支。

**Table 1：** RQ、对应实验、主要指标和证据层级。

# 2. Related Work

## 2.1 UAV 遥测异常检测与故障诊断

- 回顾飞行日志、状态估计量、多源遥测、窗口化时间序列和类别不平衡处理。
- 介绍 AeroTSBoost-compatible 检测基线，以及从二元异常到故障域诊断的级联思路。
- 说明本文使用 Macro-F1、Balanced Accuracy、per-class Recall 和 AUPRC，而不是只使用 Accuracy。

## 2.2 可解释时间序列模型

- 回顾 TreeSHAP、分层聚合、masking、随机基线和 Consistency@K。
- 强调解释证据应同时接受数值守恒、必要性和标签一致性检验。

## 2.3 PX4 架构感知诊断证据

- 介绍 PX4 模块化架构和 uORB publisher/subscriber 关系。
- 将本文定位为 architecture-aware diagnostic evidence 和 software-module suspect ranking。
- 明确静态依赖传播不是因果根因分析。

## 2.4 本文区别

- 将真实遥测诊断和软件架构证据放入同一可审计框架。
- 同时报告严格隔离和失败结果，避免只展示条件性正向排名。

**Table 2：** 相关工作与本文在异常检测、故障域诊断、解释验证和软件模块证据四个维度上的比较；具体引用投稿前核实。

# 3. Methodology

## 3.1 数据预处理与特征表示

- UAV-SEAD 是主数据集；P1 得到 1,389 条可用日志、1,892,063 条对齐的 10 Hz 记录和 87 个核心通道。
- 使用覆盖率不低于 60% 的核心通道；原始 ULog 只读使用，派生数据由脚本和配置生成。
- 每个窗口包含 96 个采样点，步长为 8，horizon 为 12；87 个通道使用 18 个统计描述符，共 1,566 个特征。
- 标准化统计量仅由训练数据计算。

## 3.2 分层异常检测与故障域诊断

- **Stage 1**：类别平衡 LightGBM 输出运行时异常概率。
- **Stage 2**：仅对具有明确异常类别标签的窗口诊断 External Position、Global Position、Altitude 和 Mechanical/Electrical。
- **Cascade**：Stage 1 未超过验证阈值时输出 Normal，否则调用 Stage 2。
- **Direct Five-Class**：Normal 加四类故障域的直接多分类对照。
- 主要指标：Stage 1 使用 AUPRC/AUROC；Stage 2 和完整分类使用 Macro-F1、Balanced Accuracy、Macro Recall 和逐类指标。

## 3.3 SHAP 可解释证据

- 对 Stage 2 预测类别使用 TreeSHAP 贡献。
- 按“统计特征 → channel → PX4 topic → subsystem”聚合绝对贡献。
- 使用贡献守恒、SHAP Top-k masking 与随机 masking、Consistency@K 和 Hit@K 验证证据质量。
- Shared 通道不视为特定故障域的匹配证据；External Position 的较弱一致性必须单独报告。

## 3.4 PX4 软件模块嫌疑度

- 从日志固件信息选择多数版本 commit `82aa24ad...`，扫描匹配 PX4 源码中的 uORB publisher/subscriber。
- 将 topic 级 SHAP 质量沿静态依赖传播为 module-level suspect ranking。
- P8 建立 18 个 topic、180 条映射边和 54 个模块的证据图，且贡献守恒通过。
- 输出为版本相关、架构感知的诊断证据，不称为 root-cause localization。

**Figure 2：** 从遥测特征到故障域、topic 和软件模块嫌疑度的证据链。

**Table 3：** 核心数据、窗口、特征、模型和映射配置；完整参数放 Supplementary Table S1。

# 4. Experimental Setup

## 4.1 数据与实验角色

- **UAV-SEAD**：训练、检测和故障域诊断主数据。
- **ALFA**：只用于 zero-shot 二元异常检测外部参考。
- **Uncategorized**：只用于航次级弱标签筛查。
- **PX4 replay**：唯一具有已知源码 mutation module ground truth 的实验。

## 4.2 划分与统计协议

- 固定 chronological：P2/P3 的复现基线。
- Purged：边界两侧移除 14 个窗口，检验时间邻近影响。
- Leave-log-out：970/206/213 条完整 flight logs 分配到 train/validation/test。
- 使用五种子和 1,000 次 flight-log-level bootstrap；不将随机 window-level split 作为主结果。

## 4.3 Controlled replay 与评价分层

- 固定 PX4 commit 和 Ubuntu-20.04，不使用 Gazebo、ROS、QGroundControl 或 NuttX。
- 3 条真实 ULog、4 类源码 mutation、24 次 replay，其中 12 次 fault run；第 30 秒注入故障。
- mutation 涵盖 Commander、EKF2、INAV 和 Land Detector。
- 分别报告 onset-conditioned ranking 和 detector-gated ranking，后者才反映完整检测门控链路。
- 说明 EKF2 因源 ULog 缺少 `ekf2_timestamps` 使用通用 replay 发布适配器。
- 记录 Python、LightGBM、PyULog、PX4 commit 和运行环境版本；说明代码、配置、派生报告和受许可限制的原始数据的可用性。
- 明确所有阈值由 validation 数据选择，bootstrap 单位为 flight log，而非 window。

**Table 4：** 实验协议总表，合并主实验、严格性实验、外部验证和 replay 验证；P1--P11 的阶段编号只作为来源索引，不作为正文结构。

# 5. Results

## 5.1 真实遥测检测与故障域诊断

- 固定 chronological Stage 1：AUPRC `0.7522 ± 0.0039`，AUROC `0.9512 ± 0.0006`，最优 F1 `0.6924 ± 0.0056`。
- Stage 2 LightGBM：Macro-F1 `0.8980 ± 0.0020`，Balanced Accuracy `0.8863 ± 0.0021`。
- 报告四类故障域的逐类 Recall/F1 和与 Random Forest、majority、stratified random 的比较。
- 固定协议 Cascade Macro-F1 为 `0.6902 ± 0.0071`，说明 Stage 1 错误会传递到完整级联结果。

## 5.2 SHAP 证据和软件模块嫌疑度

- SHAP 聚合最大守恒误差不超过 `7.11 × 10^-15`。
- Consistency@1 为 `0.3705 ± 0.0109`，随机基线为 `0.1703`。
- Top-100 SHAP masking 的 Macro-F1 下降约 `0.2683`，同规模随机 masking 约 `0.0037`。
- P8 的 18/18 topic 映射、180 条边和 54 个模块支持形成 architecture-aware diagnostic evidence，但不支持因果根因结论。
- External Position 的类别级 Consistency@1 接近随机基线，作为解释层限制报告。

## 5.3 严格验证、外部验证与能力边界

- **P10 purged**：Stage 1 AUPRC `0.5936`，Stage 2 Macro-F1 `0.7983`，Cascade `0.5444`，Direct Five-Class `0.5962`。
- **P11 leave-log-out**：Stage 1 AUPRC `0.6296 ± 0.0023`，Stage 2 Macro-F1 `0.9041 ± 0.0029`；Cascade `0.5962 ± 0.0048`，Direct Five-Class `0.6092 ± 0.0043`。
- Cascade 与 Direct 的差值 95% CI 为 `[-0.0282, 0.0438]`，不支持 Cascade 稳定优于 Direct Five-Class。
- **ALFA**：二元 AUPRC `0.3181 ± 0.0086`、AUROC `0.6679 ± 0.0069`，仅作外部检测参考。
- **P9**：onset-conditioned Top-1/3/5 为 `0.250/0.333/0.333`，MRR `0.3227`；但 detector-gated 检测召回为 `0/12`，detector-gated Top-1/3/5 和 MRR 均为 0。
- 结论：当前系统支持条件性 module suspect ranking，不支持端到端软件模块定位。

**Figure 3：** Stage 1、Stage 2、Cascade 和 Direct Five-Class 在固定、purged、leave-log-out 协议下的主要指标。

**Figure 4：** SHAP masking、Consistency@K 和随机基线，突出 External Position 的类别级限制。

**Figure 5：** P9 onset-conditioned 与 detector-gated 结果对照，明确显示 `0/12` 检测门控召回。

**Table 5：** 主结果汇总：异常检测、故障域诊断、SHAP 验证、严格协议、ALFA 和 P9 边界结果。

# 6. Discussion

## 6.1 论文主发现

- 真实 PX4 遥测支持运行时异常检测，明确标签的异常窗口支持四类故障域诊断。
- SHAP 证据总体满足守恒和 masking 必要性，但类别级一致性并不均匀。
- uORB 静态映射可以把 topic 证据组织为版本相关的软件模块嫌疑度。

## 6.2 层级模型和严格协议的解释

- Stage 2 anomaly-only 结果说明故障域信息具有可学习性，但 Cascade 受 Stage 1 错误传播影响。
- P10/P11 显示严格隔离后性能下降，且不支持 Cascade 的稳定性能优势。
- 因此层级设计的贡献应强调诊断组织、证据可追溯性和工程检查线索，而不是性能优越性。

## 6.3 P9 负结果和能力边界

- 真实飞行训练分布与受控源码 mutation replay 之间存在 domain shift。
- onset-conditioned ranking 依赖已知故障起点和 matched baseline；它不能替代在线异常检测。
- `0/12` detector-gated recall 是当前方法从运行时异常到软件模块嫌疑度的关键边界。

## 6.4 局限与后续工作

- UAV-SEAD 缺少全面源码级 ground truth；P8 是静态依赖证据。
- P9 仅含 3 条源日志、4 类 mutation 和 12 个 fault run，并存在 EKF2 replay 适配限制。
- External Position 一致性较弱；ALFA 不能验证四类故障域迁移；Uncategorized 没有时间范围。
- 后续工作：扩大独立 mutation benchmark，补充真实模块 ground truth，研究不污染测试集的 domain adaptation，并引入动态架构证据。

# 7. Conclusions

## 7.1 结论要点

- HS-AeroTS-FL 建立了从真实 PX4 遥测异常检测到故障域诊断、SHAP 证据和软件模块嫌疑度的可复现链路。
- P8 支持版本相关的 architecture-aware diagnostic evidence，但静态 topic-to-module 映射不证明根因。
- P10/P11 表明严格划分下性能下降，且不支持 Cascade 稳定优于 Direct Five-Class。
- P9 的 `0/12` detector-gated recall 明确限制了当前系统的端到端模块诊断能力。

## 7.2 建议术语

- 使用：`runtime anomaly diagnosis`、`fault-domain diagnosis`、`architecture-aware diagnostic evidence`、`software-module suspect ranking`。
- 避免：`reliable PX4 root-cause localization`、`end-to-end software fault localization`。

# 8. Supplementary Materials 与投稿前检查

## 8.1 放入 Supplementary Materials 的内容

- S1：完整模型、窗口和特征配置。
- S2：P1 通道、标签和数据审计清单。
- S3：P3/P11 完整逐类指标与混淆矩阵。
- S4：P8 完整 topic-module 映射边和传播模式结果。
- S5：P9 mutation manifest、逐 run ranking 和 replay 环境检查。
- S6：P5 CATCH 资源适配和线性 VAR(1) Granger/预测误差消融；明确不是官方 GCAD 复现。

## 8.2 投稿前必须核对

- 主文、摘要和结论中都保留 P9 `0/12` detector-gated 负结果。
- P10/P11 的严格结果与固定 chronological 结果同时报告，不隐藏性能下降。
- Cascade 不写成已证明优于 Direct Five-Class。
- SHAP 一致性不写成因果证明；External Position 弱一致性不省略。
- ALFA、Uncategorized 和 P9 的标签/评价范围保持准确。
- UAV-SEAD、AeroTSBoost、ALFA、CATCH 和 PX4 的最终参考文献逐条核实。

## 8.3 MDPI *Drones* 后置声明清单

- Author Contributions（CRediT）。
- Funding；若无外部资助，明确写明无外部资助。
- Data Availability Statement；说明 UAV-SEAD、ALFA、PX4、代码、配置、派生报告和许可限制。
- Acknowledgments。
- Conflicts of Interest。
- AI-use disclosure：按实际使用情况说明 AI 是否参与研究设计、数据分析、图表或论文准备；不得将 AI 列为作者。

## 8.4 最终一致性判定

- **结构完整**：七个正文一级章节符合用户指定结构，并可映射到 *Drones* 的 Materials and Methods Article 结构。
- **主线完整**：RQ1 对应检测/诊断，RQ2 对应 SHAP/uORB 证据，RQ3 对应严格验证和能力边界。
- **证据完整**：每项核心主张均有对应 P 阶段结果和限定条件。
- **图表受控**：正文 5 Figure、5 Table；P5、逐类指标、逐 run 清单和完整配置进入 Supplementary Materials。
- **结论克制**：不声称 root-cause localization，不声称 Cascade 稳定优于 Direct Five-Class，不隐藏 P9 `0/12`。
- **剩余工作性质**：后续主要是补齐参考文献、前置/后置声明、图表实际制作和 Supplementary 文件，不再需要重构论文大纲。
