# HS-AeroTS-FL 第一轮只读审查报告

审查日期：2026-08-25
目标期刊：MDPI *Drones*
工作流：academic-pipeline Stage 2.5 → Stage 3（只审查，不修改原稿）
审查对象：`paper/main.tex`、全部分节 LaTeX、`paper/main.pdf`、P1–P11 冻结报告、配置、实现与测试；外部核验仅使用期刊官网及 DOI/出版社/会议/arXiv/OpenReview 元数据。

## 总结性结论

- **Stage 2.5 完整性门控：FAIL。** 36/36 条参考文献均被正文引用，未发现 orphan reference、dangling citation 或明显虚构条目；主要论文数值与 P1–P11 报告总体一致。阻断项是“version-matched”软件映射主张没有覆盖产生总体 SHAP 排名的大多数测试样本。
- **Drones 适配性：主题高度适配，当前投稿准备度不足。** UAV 安全、真实遥测、故障诊断和 PX4 工程证据均属于期刊读者兴趣范围；但补充材料缺失、数据可用性陈述不可执行、方法细节与统计报告不足，会妨碍复现性审查。
- **同行评审建议：Major Revision。** 核心研究可以保留，负结果披露尤其值得肯定；但软件版本匹配、SHAP/uORB 有效性、最新基线、统计不确定性和补充材料必须在投稿前实质修复。
- **结论过度程度：总体克制，但局部仍过度。** 论文正确否认因果根因定位和端到端定位能力；过度主要集中在“version-matched”“useful software-module suspect rankings”“necessary evidence”以及跨版本总体模块排名。

## 1. 主张—证据—引用一致性审计

### 审计覆盖

- 注册参考文献：36；正文唯一 citation keys：36；未发现未引用参考文献、悬空引用或重复 `bibitem`。
- 引用真实性：36 条均有 DOI、正式会议/期刊页面、arXiv、OpenReview、JMLR、NeurIPS/PMLR 或 PX4 官方文档元数据支撑；未发现明显虚构参考文献。
- 数值表面：摘要、Results、Discussion、Conclusion 与 P1–P11 的主指标进行了交叉核对。
- 代码/配置表面：划分、训练集标准化、验证集阈值、SHAP 排名、遮蔽、bootstrap、uORB 静态扫描与 replay ranking 进行了只读检查。

### Critical

#### C1. “Version-matched”总体软件模块排名与实际样本版本不一致

- **位置**：Abstract；§1.2；§1.3 Contribution 2；§2.3–2.4；§3.4；§5.2 第 4 段与 Figure 4(d)；§6.1；§7。
- **证据**：数据包含 7 个固件提交，静态图只对应多数提交 `82aa24ad...`（562/1389 logs）。固定测试集 34,059 窗口中仅 14,419（42.3%）来自该提交；3,602 个 Stage-2 异常测试窗口中仅 1,393（38.7%）匹配。Figure 4(d) 却使用跨全部测试异常窗口汇总的 topic SHAP，再传播到单一提交的图。
- **问题**：对大多数窗口而言，模块关系不是“version-matched”。这直接削弱论文核心贡献之一，并可能改变模块集合、publisher/subscriber 边和排名。
- **具体修改方案**：
  1. 首选：为每个实际 firmware commit 构建独立 uORB 图，逐日志按 commit 传播，再在明确的跨版本规则下汇总；报告每版本覆盖率和排名稳定性。
  2. 最低可接受方案：Figure 4(d) 及总体模块排名仅使用 `82aa24ad...` 匹配窗口重新计算，并把适用范围限定为该版本；其他版本列为 out-of-scope。
  3. Abstract、贡献、Discussion 和 Conclusion 同步把“version-matched”限定到实际匹配子集。
  4. 在补充材料提供 `test window → log → firmware commit → mapping graph` 的追踪清单。

### Major

#### M1. SHAP label-consistency 的“ground-truth subsystem”并非独立真值

- **位置**：§3.3；§5.2 第 3 段；Figure 4(b,c)；§6.1；§6.4。
- **证据**：`channel_subsystem_mapping.csv` 由 `diagnosis.py::subsystem_for_channel()` 的字符串规则生成，例如 `.x/.y/.vx/.vy` 被分到 Global Position，多个 actuator/battery/attitude token 被分到 Mechanical/Electrical；Shared 被强制视为不匹配。没有领域专家盲审、PX4 message-definition 依据、互评一致性或外部标注。
- **问题**：Consistency@K 衡量的是 SHAP 与作者规则的一致程度，而不是与独立物理故障真值的一致程度；称其为 mapped ground truth 容易形成循环验证。External Position 只有 3/87 个专属通道，其随机 Consistency@1 为 0.0345，观察值 0.0363 几乎无增益，进一步暴露映射敏感性。
- **具体修改方案**：将其改称“predefined semantic mapping consistency”；公开完整映射依据；至少进行双人独立标注与一致性统计，或基于 PX4 官方 message/estimator 文档建立可审计规则；对 Shared 处理、类映射规模和替代映射做敏感性分析。

#### M2. SHAP masking 只能支持模型依赖，当前“necessary”措辞偏强且统计比较不完整

- **位置**：RQ2、Table 1、§2.2、§3.3、§5.2 第 2 段、Figure 4(a)、§6.1、§7。
- **证据**：验证集决定全局 top-k；测试输入用训练样本中位数替换；模型不重训。SHAP 组每个 k 仅 5 个 seed 值，随机组为 5×20=100 次，论文只给均值±SD，没有按 seed 配对差值 CI 或检验。
- **问题**：遮蔽可能产生 off-manifold 输入，且未重训 masking 与 ROAR 类“信息必要性”不同；两组方差单位也不同。结果支持“prediction relevance under this perturbation”，不能单独证明诊断证据必要性或解释正确性。
- **具体修改方案**：收窄主张；报告每 seed 的 SHAP-vs-random 配对差值及 flight-log cluster bootstrap CI；增加合理替换策略敏感性（条件采样、同日志正常段或 retraining-based removal，至少一种）；明确随机重复嵌套在 seed 内，不能把 100 次当独立模型重复。

#### M3. uORB 静态解析与传播的正确性验证不足

- **位置**：§3.4；§5.2 第 4 段；Figure 4(d)；§6.1、§6.4。
- **证据**：扫描器以每个 `ORB_ID` 前 500 字符内最近 API hint 判断 publisher/subscriber，并把源码路径前三层作为 module；同一 topic 的证据在所有连接 module 间均匀分配。没有对实际 PX4 commit 的人工 gold set、precision/recall、宏展开/别名覆盖或运行时激活验证。
- **问题**：“18/18 topics covered、180 edges、54 modules”只证明扫描器产生了边，不证明边完整或角色正确；高连接度 module 可能因结构性 degree bias 获得排名。
- **具体修改方案**：抽样建立真实 commit 的人工审计集，报告 role/edge precision、recall 和遗漏类型；增加 degree-normalized、publisher-prioritized 等传播敏感性；清楚列出静态扫描无法覆盖的宏、模板、动态实例和 runtime activation。

#### M4. 已完成的 mapping ablation 未进入论文，当前传播模式选择缺乏证据说明

- **位置**：§3.4、§5.2、§5.3 replay、Figure 4(d)、Figure 5。
- **证据**：P9 ablation 中 bidirectional Top-3/5=0.333/0.333，producer-only=0.500/0.500，topic-only=0.500/0.500，random mapping=0.083/0.167；MRR 分别为 0.323、0.414、0.373、0.150，CI 很宽。论文只展示 aggregate producer-only 模块图，却以 bidirectional replay 作为主模块定位指标，未解释模式选择。
- **问题**：架构传播并未明显优于 topic-only，且 producer-only 在小样本上数值更高。遗漏该消融使“uORB 模块映射的增益”证据不完整。
- **具体修改方案**：把完整消融及 CI 加入主文或补充材料；预先指定主传播模式及工程理由；不要按最好结果事后选模式；讨论 topic-only 与 module mapping 的增量价值是否得到支持。

#### M5. replay 样本的依赖结构与不确定性未在正文充分报告

- **位置**：§4.3、Table 4、§5.3 第 5–6 段、Figure 5、§6.3–6.4。
- **证据**：12 fault runs 来自 3 个 source logs × 4 mutations，并非 12 个完全独立实验单位；正文只报点估计，不报 P9 已有 bootstrap CI。相同 source log、相同 mutation family 造成双向聚类；当前报告以 fault run 为 bootstrap unit。
- **问题**：Top-1=0.25、Top-3/5=0.333 的精度很低，CI 宽；逐 run bootstrap 低估或误表征结构不确定性。“useful ranking”尚未被稳定性证据充分支撑。
- **具体修改方案**：正文报告所有 CI；按 source log 和 mutation family 做分层/双向敏感性，至少逐 log、逐 mutation 展示结果；将结论改为“preliminary conditional ranking signal”；明确不存在独立 development/test mutation split。

#### M6. “最新基线”在 Related Work 出现，但没有形成可审查的主实验比较

- **位置**：§2.1、§4、Table 4、§5.1–5.3。
- **证据**：论文讨论 CATCH (ICLR 2025) 和 GCAD (AAAI 2025)，项目 P5 也有结果；但 Experimental Setup 和 Results 完全不呈现这些结果。Stage 1 主文只与 RF/多数/随机及 AeroTSBoost reference values 比较。2026 年已有进一步 MTSAD 与 foundation-model benchmark 文献，至少需要说明适用性和排除理由。
- **问题**：读者无法判断 LightGBM 选择相对近期序列/图/频域方法的竞争性。P5 的 CATCH 是 18-topic、4096 正常窗资源适配，GCAD 是线性 Granger 消融而非官方复现；这些限制不能靠省略解决。
- **具体修改方案**：报告 P5，但严格标注非等价资源适配和非官方 GCAD 消融；或者预先给出排除标准并避免暗示完整 SOTA 比较。优先加入同划分、同 87-channel/18-topic 输入预算、同 AUPRC 实现的至少一个近期强基线；对 2026 新方法做相关性说明，不要求为不适用方法编造实验。

#### M7. 统计报告不足以支撑多数比较性措辞

- **位置**：§4.2、§5 全部、Figures 3–5、Abstract。
- **证据**：固定 protocol 报 5 seeds 均值±SD，但 seeds 不是独立数据重复；purged 只有 1 seed；除 LLO Direct-minus-Cascade 外，多数比较无 paired CI。P9 正文无 CI；SHAP random repeats 与 model seeds 混用。正文还报告 independently optimized test-set F1，虽明确区分，但容易被当作可部署性能。
- **问题**：当前不确定性主要反映初始化，而非对 unseen flights 的抽样不确定性。
- **具体修改方案**：以 flight log 为单位给主要指标和方法差值 CI；purged 至少多 seed 或明确“single-run sensitivity”；将 test-optimized F1 降为 oracle/diagnostic upper-bound，主表突出 validation-threshold 指标；报告 bootstrap 方法、seed、聚类单位和 paired resampling 细节。

#### M8. Supplementary Table S1 与 Supplementary Materials 实际缺失

- **位置**：§3.2、§3.3、§4.2、Table 4 caption/note；PDF pp. 9–12。
- **证据**：工作区无 Supplementary Table S1 或任何 supplement 文件，但正文至少四次承诺完整 hyperparameters、masking settings、per-run settings 和 class-specific results 在补充材料中。
- **问题**：不可验证的交叉引用破坏复现性，也不符合 *Drones* 对完整实验细节和 controls 的要求。
- **具体修改方案**：创建并提交真实 supplement，至少包含全部 YAML 参数、软件/库版本、每 seed/per-run 指标、阈值、类分布、映射表、ablation、CI、mutation manifest 与运行命令；若不提供，则删去所有承诺并把必要内容移入主文。

#### M9. Data Availability Statement 不可执行

- **位置**：Back matter `\dataavailability{...}`。
- **证据**：只说材料“documented in the accompanying project repository”，无 repository 名称、URL/DOI、release/tag/commit、许可、不可公开数据的访问方式或最小复现集。
- **问题**：*Drones* 要求提供支持结果的数据位置，并鼓励公开代码、参数和最小数据集；当前声明无法让审稿人访问或复现。
- **具体修改方案**：给出持久仓库 URL/DOI、版本 tag/commit、数据集原始来源与许可、不能再分发的原始 ULog 获取步骤、派生 manifest/配置/脚本位置及 checksum；逐项说明可用性限制。

#### M10. HS-AeroTS-FL 名称中的 “FL” 与论文能力边界冲突

- **位置**：Title metadata/Abstract 首次出现；全稿方法名。
- **证据**：未展开 FL。领域读者可能理解为 Federated Learning 或 Fault Localization；论文又明确否认 end-to-end software fault localization。
- **问题**：方法名会持续诱发超出证据的解读。
- **具体修改方案**：首次出现时明确定义缩写；如果 FL 指 fault localization，建议改名为不宣称 localization 的名称（如 diagnostic evidence / suspect ranking），或在标题与摘要立即限定为非因果、非端到端定位。

### Minor

#### m1. 图表编号与出现顺序错误

- **位置**：PDF pp. 4, 8, 12, 14, 16；Figure 4 在 Figure 3 之前，Table 2 后直接出现 Table 4；源码手工 `\setcounter`。
- **修改方案**：按首次出现自动连续编号；补入真正 Figure 2/Table 3 或删除手动 counter；重编译检查交叉引用。

#### m2. 投稿占位符未完成

- **位置**：首页 Author/Affiliation/email；Author Contributions；Funding=`To be completed`; Acknowledgments=`To be completed`。
- **修改方案**：投稿前全部替换；若无经费/致谢，使用期刊规定的明确声明，不保留占位文本。

#### m3. 章节命名与期刊模板可进一步对齐

- **位置**：§3 “Methodology”、§4 “Experimental Setup”。
- **修改方案**：合并或明确映射为 “Materials and Methods”，以便符合 *Drones* Article 的常规结构；不是科学性问题。

#### m4. Discussion 与近年工作对话不足

- **位置**：§6.1–6.4。
- **修改方案**：除总结自身结果外，讨论为何与 AeroTSBoost 的 ALFA protocol/result 不同、为何近期序列模型在该资源/划分下可能不占优，以及静态架构证据相对传统 software fault localization 的增量和边界。

## 2. Drones 期刊适配性评估

### 适配结论

**主题适配：高。方法与证据适配：中。投稿准备度：低至中。**

适配理由：

- 研究直接面向 UAV/PX4、真实飞行遥测、状态估计异常、fault-domain diagnosis 与工程安全。
- 包含真实数据、外部数据、严格划分和 controlled mutation replay，符合期刊偏好的实验验证导向。
- 论文的最有价值特征是明确报告 negative result，而不是把 onset-conditioned ranking 冒充在线能力。

主要期刊风险：

- *Drones* Article 要求足以复现的完整实验细节、最新且相关的参考文献、可访问的数据/代码说明；当前 Supplement S1 和可执行 Data Availability 缺失。
- 软件工程模块排名是可接受的跨学科延伸，但必须始终由 UAV 运行安全问题主导，不能把静态源码连接包装为已验证的 fault localization。
- “Methodology + Experimental Setup”可以被编辑接受，但建议与 “Materials and Methods”结构对齐。

**期刊适配建议：保留 Drones 作为目标期刊；完成 Major Revision 后再投稿。**

## 3. 完整同行评审

### Reviewer A — Journal Fit / Editorial

- **建议**：Major Revision。
- **核心判断**：选题与 *Drones* 高度相关，真实 PX4 遥测和诚实的 detector-gated 负结果具有明显编辑价值。当前最大问题是核心“version-matched”表述不真实覆盖总体证据，且 supplement/data availability 不完整。
- **优点**：研究问题清楚；证据层级边界写得好；摘要同时呈现 fixed、LLO 与 0/12 负结果。
- **主要意见**：修复 C1、M8、M9；把贡献从“完整定位链”稳定限定为“分层诊断证据链”。

### Reviewer B — Methodology / Statistics

- **建议**：Major Revision。
- **核心判断**：训练集标准化、验证阈值、LLO 与 flight-log bootstrap 显示良好泄漏意识；没有发现把随机 window split 作为主结果。统计推断仍不足，尤其是 single-seed purged、seed SD、replay 依赖和 masking 重复层级。
- **优点**：LLO 以完整 log 隔离；Cascade vs Direct 有 paired flight-log CI；test-optimized F1 与 frozen-threshold F1 被区分。
- **主要意见**：修复 M2、M5、M7；主结论应以 LLO/cluster uncertainty 为中心，fixed chronological 仅作为 reproduction baseline。

### Reviewer C — UAV Fault Diagnosis / Time-Series Domain

- **建议**：Major Revision。
- **核心判断**：四类 UAV-SEAD diagnosis 与 ALFA/Uncategorized 的任务边界清楚，但近期强基线只在 Related Work 中出现，主实验无法支持广泛竞争性判断。
- **优点**：AUPRC、Macro-F1、Balanced Accuracy 和 per-class recall 的选择合理；不把 ALFA 映射成四类；不把 Uncategorized 报成 point/event 指标。
- **主要意见**：修复 M6；解释 UAV-SEAD 和 AeroTSBoost/ALFA 的 protocol 差异；报告类级 LLO 结果与严格协议下的 baseline fairness。

### Reviewer D — Explainability / PX4 Software Architecture

- **建议**：Major Revision。
- **核心判断**：feature→channel→topic→subsystem 的可追踪设计具有工程价值，守恒检查也正确；但守恒只验证算术，不能验证语义。subsystem mapping、uORB role scan 与 uniform propagation 都缺独立有效性证据。
- **优点**：论文反复否认 SHAP 因果性和静态图根因性；External Position near-random 结果没有隐藏。
- **主要意见**：修复 C1、M1、M3、M4；加入 mapping audit、跨版本处理和传播 ablation。

### Reviewer E — Devil’s Advocate

- **最强反论点**：如果单一 PX4 图只匹配 38.7% 的 SHAP 异常测试窗口，且 semantic consistency 由作者启发式映射定义，那么“architecture-aware, version-matched diagnostic evidence”可能主要是可追踪的后处理，而不是被独立验证的诊断贡献。
- **可反驳部分**：论文没有声称因果根因定位，并用 mutation ground truth 做了初步条件排名测试；因此问题可通过限制分析范围、补充跨版本图、加入独立映射验证与完整消融来修复，不必直接 Reject。
- **不可忽略部分**：在修复前，C1 阻断 Accept/Minor Revision。

### 编辑综合决定

**Decision: Major Revision。** 不是 Reject，因为主要真实遥测结果、严格隔离实验和 detector-gated 负结果均可保留，且核心缺陷具备可修复路径。下一轮应优先验证以下四个验收条件：

1. 总体模块排名只使用真正匹配的 firmware，或实现逐 commit 映射；
2. subsystem/uORB mapping 有独立审计与 ablation；
3. supplement、数据/代码可用性和统计 CI 完整；
4. 最新基线的纳入或排除有透明、同口径的依据。

## 4. 方法与实验专项审查

### 真实/实验支撑

- **PASS WITH MAJOR LIMITATION**：P2/P3/P10/P11/P9 主数值可由冻结报告追踪，摘要和结论保留了关键负结果。
- **FAIL（软件总体排名）**：跨版本总体 SHAP → 单版本模块图不满足 version-matched 条件。

### 数据泄漏

- 未发现标准化使用 validation/test 数据：scaler 只从训练窗口覆盖的样本计算。
- 阈值在 validation 选定并冻结用于 test；这一点合格。
- fixed chronological 仍让同一 flight log 出现在 train/val/test，且重叠窗口共享局部工况；论文已经用 purge 和 LLO 暴露该风险。建议把 LLO 作为主要 generalization claim，fixed 仅作 reproduction。
- SHAP top-k 排名来自 validation、替换值来自 train，未发现直接 test ranking leakage。

### 最新基线

- 最近且最贴近数据/任务的 AeroTSBoost (2026) 已引用并复现其性能层级。
- 主实验缺少近期序列/频域方法的公平结果；已有 P5 不应隐藏，但必须注明 CATCH 资源适配和 GCAD 非官方复现。
- 2026 通用 MTSAD/foundation-model 文献可用于说明 baseline landscape，但只有在输入、监督和评价协议可比时才应要求新增实验。

### 消融实验

- 已有：purged/LLO、Cascade vs Direct、SHAP vs random masking、producer/consumer/bidirectional/topic/random mapping（后者未写入论文）。
- 缺失或未充分报告：firmware-matched vs unmatched；mapping mode 增益；degree normalization；semantic mapping alternatives；matched-baseline subtraction 的敏感性；replay 按 log/mutation 分层。

### 统计报告

- 合格点：5 seeds、LLO paired bootstrap、flight-log 作为主要 bootstrap unit。
- 不足：多数主张仅 seed SD；purged single seed；P9 CI 不入正文；cluster dependence 未处理；SHAP random repeats 与 seed 重复层级未区分。

### SHAP 有效性

- 守恒误差 `7.11e-15` 仅验证分组求和正确。
- masking 支持该模型在该替换协议下依赖 top-ranked features，不证明物理原因。
- Consistency@K 依赖作者映射，不能称独立 ground truth；External Position 基本随机。
- 建议继续使用“diagnostic evidence”而非 explanation correctness/causality，并加入映射独立验证。

### uORB 模块映射有效性

- 有利证据：commit 固定、18 topics 全有至少一个 edge、controlled mutations 提供已知模块。
- 反证/限制：总体样本大多不匹配 commit；静态 parser 未量化准确度；uniform allocation 有 degree bias；topic-only/producer-only ablation 不弱于主 bidirectional；detector-gated 0/12。
- 当前允许的最强结论：在特定 PX4 commit 和已知 onset/matched baseline 条件下，静态 topic→module 传播产生初步、低样本的 suspect-ranking signal；不支持部署级 end-to-end localization。

### 结论是否过度

- **不过度的部分**：否认 causal root cause；否认 detector-gated capability；否认 Cascade 稳定优于 Direct；保留 External Position near-random。
- **需要降级的部分**：跨全数据的 “version-matched”；“useful” module ranking；“necessary” SHAP evidence；“complete mapping coverage”若被理解为正确性而非非空边覆盖。

## 建议的修订优先级

1. **Priority 0 / Critical**：解决跨 firmware 的 C1，并重算/限缩所有 module ranking claims。
2. **Priority 1 / Major**：补全 mapping validity、ablation、replay/SHAP 统计与最新基线说明。
3. **Priority 2 / Major**：提交 Supplement S1 和可执行 Data Availability。
4. **Priority 3 / Minor**：修复图表编号、占位符、章节名称与缩写。

## 本轮未做事项

- 未修改任何 manuscript、figure、table、reference 或实验结果。
- 未编造或补写实验、结果或参考文献。
- 未把外部搜索到的新论文当作稿件已有证据。
- 测试只读复核中，25 项通过；`test_parse_uorb_source_roles` 因当前沙箱临时目录权限无法完成 setup，不能据此判定测试失败或通过。
