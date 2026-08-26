# HS-AeroTS 第二轮同行评审报告

审查日期：2026-08-26
目标期刊：MDPI *Drones*
审查对象：当前 `paper/main.tex`、全部分节 LaTeX、编译 PDF、第一轮审稿与修订记录、P12 冻结报告及相关实现代码
审查模式：第二轮独立复审（只审查，不修改论文）

## 复审协议说明

仓库没有 academic-research-suite 当前 re-review 合同要求的机器可验证 `revision-roadmap/1.0`、`author-adjudication/1.0`、原稿冻结快照、`revision-evidence-bundle/1.0` 和 apply-report chain。因此，本报告不能宣称是合同式 R&R 验收，也不能机械证明每项修改与原稿字节级对应。本轮采用可执行的降级路径：以第一轮人类可读报告为固定 yardstick，独立核查当前稿、冻结结果和实现，并明确区分“第一轮问题关闭情况”与“第二轮新发现”。

本轮未运行外部模型或跨模型复审。复审与前期修订处于同一模型家族，存在对同一评价偏好的相关误差风险。

## 总体决定

**建议：Major Revision（投稿前再修订一次）。**

第一轮唯一 Critical 问题，即把跨固件 SHAP 汇总传播到单一 PX4 commit 图，已经通过 matching-commit-only 重算实质关闭。数据泄漏控制、purged/leave-log-out 设计、SHAP 遮蔽配对区间、回放双向聚类区间、传播消融和 detector-gated 负结果也明显改善。当前没有发现足以单独否定全部论文的 Critical 缺陷。

但稿件仍有七项 Major 问题。其中三项直接影响核心架构证据：真实飞行解释和模块排名仍以 ground-truth anomaly windows 作 oracle conditioning；uORB `1.000` 审计与被审计解析器使用同源 API hint，不构成独立验证；静态图未按实际 PX4 build target 过滤，内部结果已出现 `src/examples/*`、测试和其他平台路径。其余问题涉及 Consistency@K 可复现定义、近期基线公平性、关键指标的 sampling uncertainty 和 *Drones* 要求的复现材料。

## 一、第一轮问题关闭情况

| 第一轮 ID | 第二轮判定 | 核查结论 |
|---|---|---|
| C1 跨固件模块排名 | **FULLY ADDRESSED** | §3.4 和 §5.2 明确只保留 matching-commit 日志；P12 报告确认使用 1,393 个异常测试窗，Figure 4(d) 已重绘。 |
| M1 semantic mapping 被当作 ground truth | **PARTIALLY ADDRESSED** | 主张已降为 author-defined mapping sensitivity，External/Global 负面结果保留；但完整映射及精确定义未随稿提供。 |
| M2 SHAP “necessary” 与统计不足 | **FULLY ADDRESSED（在声明边界内）** | 增加 flight-log paired CI 和 training-row donor sensitivity，并明确仅支持 prediction relevance。 |
| M3 uORB parser 有效性 | **PARTIALLY ADDRESSED** | 新增 244-occurrence 审计，但该审计与解析器使用同源规则，且未检查 build-target relevance，见本轮 M2、M3。 |
| M4 propagation ablation 缺失 | **FULLY ADDRESSED** | Table 4（`tab:mapping_ablation`）报告五种传播/控制模式及两向聚类区间。 |
| M5 replay 依赖与区间 | **FULLY ADDRESSED FOR CURRENT DATA** | 3 source logs × 4 mutation types 的 two-way cluster bootstrap 已报告，宽区间和样本限制未隐藏。 |
| M6 最新基线 | **PARTIALLY ADDRESSED** | 官方 CATCH model core 已运行，但仅 4,096 个正常窗、2 epochs；GCAD 仍非官方线性消融，见本轮 M5。 |
| M7 统计报告 | **PARTIALLY ADDRESSED** | 方法差值与遮蔽已有 cluster CI；关键 AUPRC/Macro-F1 仍主要只有 seed SD，见本轮 M6。 |
| M8 Supplement 缺失 | **NOT FULLY ADDRESSED** | 虚假 Supplement 引用已删除，但必要配置、映射、边表和逐 seed 结果既未入主文，也无 Supplement，见本轮 M7。 |
| M9 Data Availability | **PARTIALLY ADDRESSED** | 第三方数据 URL/revision/license 与 PX4 commit 已具体化；派生材料仅承诺保密提供，仍有可复现性风险。 |
| M10 “FL” 命名冲突 | **FULLY ADDRESSED** | 全稿已改为 HS-AeroTS。 |
| m1 图表编号 | **FULLY ADDRESSED** | Figure 1--5、Table 1--4 顺序连续。 |
| m2 投稿元数据 | **PARTIALLY ADDRESSED** | 作者、单位、通讯、Funding、COI 已填写；CRediT 和 Acknowledgments 仍为占位符。 |
| m3 章节名 | **FULLY ADDRESSED** | 已采用 Materials and Methods / Experimental Protocols。 |
| m4 Discussion 对话不足 | **FULLY ADDRESSED WITH BOUNDARIES** | 已讨论 CATCH/GCAD 公平性、静态图限制和 detector-gated failure。 |

## 二、Critical 问题

**本轮未发现新的 Critical 问题。** 这不等于当前稿件可接收；以下 Major 问题共同阻止“可直接投稿”的结论。

## 三、Major 问题

### M1. 真实飞行解释与模块排名仍由真实标签异常窗进行 oracle conditioning

- **位置**：§3.3；§3.4；§5.2 第 1、4 段；Figure 4；§6.1；§7；Highlights 第 3 条。
- **证据锚点**：`dataset: fixed chronological test — SHAP/Consistency 使用 3,602 个 ground-truth anomalous Stage-2 windows；matching-commit module aggregation 使用其中 1,393 个`。实现中的 `stage2_subset(test["x"], test["binary"], test["type"])` 直接以真实 binary/type 标签选择窗口，未先应用 Stage 1 detector gate。
- **问题**：稿件将 HS-AeroTS 描述为从 runtime detector 到 fault-domain/architecture evidence 的链，但真实飞行解释与总体模块排名评价绕过了 Stage 1 的漏检和误报。它们验证的是“已知真实异常窗条件下”的 Stage 2/SHAP 行为，不是 deployed cascade 实际触发的证据质量。controlled replay 已严格区分 onset-conditioned 与 detector-gated，真实飞行部分也应使用相同的证据层级语言。
- **为什么重要**：Stage 1 在 leave-log-out 下是主要瓶颈，且 replay 为 0/12；oracle gating 会系统性高估下游证据链的可用范围。
- **具体修改方案**：
  1. 保留当前结果，但统一命名为 **ground-truth-anomaly-conditioned explanation/module analysis**。
  2. 使用现有预测重新报告 Stage-1-gated 分析：至少给出 matching-commit 的 detected true anomalies、missed anomalies、false positives 数量；对 detected true anomalies 重新计算 SHAP/模块排名及稳定性。
  3. 对 false positives 单独报告 Stage 2 类别和模块 suspect 分布，避免只展示理想真异常样本。
  4. 若不做重算，则删除/降级 Abstract、Highlights、§6.1 和 Conclusion 中暗示完整 runtime chain 已在真实飞行上验证的措辞。

### M2. uORB “1.000 audit” 不是独立有效性验证

- **位置**：§3.4 第 2 段；§5.2 第 4 段；§6.1 第 3 段；§7 第 2 段。
- **证据锚点**：`dataset: reports/p12/uorb_audit/explicit_declaration_audit.csv — reference_role 与 parser_role`；实现中 `reference_role` 由 logical statement 内的 `PUBLISH_HINTS/SUBSCRIBE_HINTS` 决定，`parser_role` 又由同一 hint family 在 500-character context 内决定。
- **问题**：所谓 reference 与 parser 不是独立来源。两者共享同一 API hint 词表，只是上下文边界略有差异，因此 `role agreement = 1.000` 和 explicit-edge recall 更接近规则自洽检查，而非人工 gold set、AST/编译语义或独立实现验证。
- **为什么重要**：正文把该结果用于支持 parser 的有效性，会让读者误以为 publisher/subscriber role 和 edge 已被外部/独立核验。
- **具体修改方案**：
  1. 最佳方案：由不查看 parser 输出的审查者对预先抽样的 occurrences 独立标注 role/module，报告抽样规则、混淆矩阵、precision、recall、agreement 和分歧裁决。
  2. 可替代方案：用 AST/clang tooling、PX4 构建生成信息或另一独立解析器生成 reference，并进行逐边比较。
  3. 若本轮不补独立审计，把 `validated approximation`、`supported the parser` 和 `1.000 audit` 改为 **internal consistency check on explicit same-statement occurrences**，不得将其作为外部有效性证据。

### M3. 静态图未按实际飞控 build target 过滤，包含明显非部署模块

- **位置**：§3.4；§5.2 第 4 段；Figure 4(d)；§6.4。
- **证据锚点**：`dataset: reports/p12/commit_matched/completion_summary.json — top producer modules include src/examples/hwtest, src/examples/uuv_example_app, src/platforms/qurt/tests/muorb and POSIX/Bebop platform paths`。
- **问题**：当前扫描基于整个 PX4 source tree at commit，而不是对应 ULog 的 board/airframe/build configuration。未编译、仅示例、测试或其他平台模块仍能获得 SHAP evidence，说明“commit matched”不等于“deployment matched”。这些边会稀释 topic evidence，并可能改变真实飞控模块的名次。
- **为什么重要**：软件模块 suspect ranking 是论文的核心工程贡献；候选集合若包含不可能在目标固件中运行的实体，排名的工程可执行性会显著下降。
- **具体修改方案**：
  1. 从 ULog/构建元数据确定 board、target 和 firmware build；构建或读取对应 CMake/Ninja compiled target graph。
  2. 仅保留该 target 实际编译进入固件的 modules/source objects；明确排除 examples、tests 和不兼容 platform directories。
  3. 重新计算 180 edges、54 modules、degree sensitivity、Figure 4(d) 与 replay ablation，并报告过滤前后差异。
  4. 若无法恢复 build target，至少做 conservative exclusion sensitivity，并把表述改为 **commit-level source-tree candidate ranking**，不能称 deployment-specific graph。

### M4. Consistency@K/Hit@K 缺少论文内的精确定义和可审计映射

- **位置**：§3.3 第 4 段；§5.2 第 3 段；Figure 4(b,c)；Data Availability Statement。
- **证据锚点**：`absence: §3.3 and supplementary surfaces — expected equations for Consistency@K, Hit@K, random baseline and the complete 87-channel mapping; checked Methods, Results, back matter, repository paper files`。
- **问题**：正文只描述“channel matching”，没有说明 Consistency@K 是 top-k 中匹配通道的平均比例、Hit@K 是任一匹配命中，Shared 如何进入分母，random baseline 为何对 strict Consistency 不随 K 变化。Methods 提到 Hit@K，但 Results 没有报告或解释它。完整 87-channel document-derived mapping 也未作为主文/Supplement 提供。
- **为什么重要**：这是解释有效性讨论的核心负面结果；在源码不公开的政策下，论文必须自行给出足够定义和映射，读者才能复算。
- **具体修改方案**：加入正式方程、类别映射、Shared 规则、随机无放回期望式和统计汇总方式；把完整 mapping 作为 Supplementary CSV/Table；报告 Hit@K 或删除对它的承诺。

### M5. 最新基线仍不足以支撑主文中的竞争性比较

- **位置**：§4.1 第 2 段；Table 3（Protocol table）的 CATCH 行；§5.1 第 4 段；§6.2 第 4 段。
- **证据锚点**：`text: §4.1 "4096 normal training windows" and "two epochs"`; `text: §5.1 "Both references were below the supervised LightGBM detector"`。
- **问题**：CATCH 虽使用官方 model core 和全部 87 通道，但训练预算极小且没有收敛证据；GCAD 不是官方架构。与使用全部监督标签、1,566 个手工统计特征的 LightGBM 直接并列，仍容易被视为 under-trained/strawman comparison。当前实验只能说明这些特定受限执行较弱，不能完成“近期强基线”要求。
- **为什么重要**：HS-AeroTS 的检测器不是新模型，检测性能却支撑整个下游链；审稿人会要求证明选择 LightGBM 不是由不公平预算造成。
- **具体修改方案**：
  1. 首选：为至少一个近期官方方法采用预先声明且足以收敛的训练/调参预算，报告学习曲线、最佳 epoch、验证选择规则和 compute cost。
  2. 增加同一 1,566-feature 表示上的 XGBoost/CatBoost/Isolation Forest 等强而公平的 task-matched reference，用于区分“表示贡献”与“LightGBM 选择”。
  3. 若不补实验，把 CATCH/GCAD 移为 feasibility reference，删除“below the detector”的比较性强调，并明确论文不评价 detector SOTA。

### M6. 关键性能估计仍缺 flight-level sampling uncertainty

- **位置**：Abstract；§4.2；§5.1；§5.3；Figures 3--5。
- **证据锚点**：`absence: primary detector and diagnostic result tables — expected flight-log clustered confidence intervals for AUPRC/Macro-F1 key estimates; checked Abstract, §4.2, §5.1, §5.3 and figures`。
- **问题**：当前主要 AUPRC、Stage 2 Macro-F1、Cascade/Direct Macro-F1、ALFA 和 Uncategorized 指标仍主要报告 seed mean ± SD。论文自己正确指出 seed SD 只反映训练波动，但没有为多数核心估计提供 flight/sequence-level sampling CI。只有方法差值、masking 和 replay 有 cluster CI。
- **为什么重要**：大量重叠 windows 不构成独立样本；没有 log-level uncertainty，读者无法判断主指标对 flight population 的稳定性。
- **具体修改方案**：对 fixed、purged、leave-log-out 的主指标按完整 flight log 进行 cluster bootstrap，并在 seeds 内配对后汇总；ALFA 按 sequence/fault family 重采样；Uncategorized 按 flight 重采样。主表同时报告 point estimate、seed SD 和 sampling CI，并清楚区分两者。

### M7. *Drones* 所需的复现信息仍未形成可提交材料

- **位置**：§3.1--3.4；§4；Protocol table；Data Availability Statement；Supplementary Materials 缺失。
- **证据锚点**：`absence: submission package — expected exact split manifest/checksum, full hyperparameters/software versions, semantic mapping, uORB edge list/audit, mutation manifest and per-seed metrics; checked paper/, main.tex back matter and supplementary files`。
- **问题**：源码可以不公开，但论文当前也不公开关键非源码工件，且仅表示可向编辑/审稿人保密提供。主文只有部分 LightGBM 参数，缺少完整 configs、依赖版本、CATCH architecture/tuning settings、87-channel mapping、180-edge table、mutation definitions和 per-run/per-seed records。
- **为什么重要**：*Drones* 要求方法足够详细，并要求公开全部实验 controls、在可能情况下提供完整数据。删除不存在的 Supplement 引用解决了交叉引用错误，却没有解决可复现性本身。
- **具体修改方案**：在不公开分析源码的前提下，提交一个非代码 Supplement：
  - S1 exact configs、software/library versions、random seeds；
  - S2 dataset revision、file inventory、split manifest/hash 和 class/window counts；
  - S3 87-channel semantic mapping 与 feature dictionary；
  - S4 matching-commit topic-role-module edges、build filter 和 audit records；
  - S5 mutation manifest、per-run ranks、per-seed metrics 与 CI settings。
  Data Availability 应逐项说明哪些随 Supplement 公开、哪些仅用于保密核查及限制原因。

## 四、Minor 问题

### m1. 投稿占位符尚未清除

- **位置**：Back Matter，Author Contributions 与 Acknowledgments。
- **问题**：仍包含两个 `[AUTHOR ACTION REQUIRED]`，提交系统/PDF 不可保留。
- **修改方案**：由作者确认 CRediT 分工；无致谢时写明 `Acknowledgments: Not applicable.` 或按期刊模板省略该段。

### m2. 建议加入不适用的伦理声明

- **位置**：Back Matter。
- **问题**：研究不涉及人或动物，但当前没有 Institutional Review Board Statement / Informed Consent Statement。
- **修改方案**：按 MDPI 模板分别填写 `Not applicable.`，避免编辑部在技术检查阶段询问。

### m3. Figure 4 的误差条定义不够逐面板明确

- **位置**：Figure 4 caption。
- **问题**：caption 仅说 “seed standard deviations where reported”，但 panel (a) 的 bars、panel (b,c) 的 bars 与正文 flight-log CI 属于不同不确定性口径。
- **修改方案**：逐 panel 明确 bars 是 seed SD 还是其他区间，并说明正文 CI 与图中 bars 不同。

### m4. 运行环境和依赖版本未报告

- **位置**：§4.1--4.3。
- **问题**：除 PX4 commit 和 replay OS 外，LightGBM、SHAP、Python、CATCH/PyTorch/CUDA 等版本缺失。
- **修改方案**：加入简短 Software Environment 段或放入 Supplement S1。

### m5. “complete internal analysis records”措辞略强

- **位置**：§5.2 末段。
- **问题**：Data Availability 仅承诺若干工件可能保密提供，并未保证完整分析记录公开可得。
- **修改方案**：改为 “selected frozen configurations, split manifests, and derived records may be made available...” 并与 Data Availability 完全一致。

## 五、数据泄漏专项结论

### 未发现的泄漏

- split assignment 在标准化之前；训练均值/标准差只来自训练 windows 覆盖的样本。
- Stage 1 operating threshold 在 validation 上选择并冻结到 test。
- SHAP top-k ranking 来自 validation anomaly windows，mask replacement 来自 training windows。
- leave-log-out 以完整 flight log 隔离；purged gap 为 14 windows，等于 `ceil((96+12)/8)`，足以隔开该实现中的窗口+标签 horizon 重叠。

### 仍需明确的“oracle information”

- Stage 2、Consistency、SHAP aggregate 和 matching-commit module ranking 使用 ground-truth anomaly/type labels 选取窗口。这不是 train/test leakage，但属于 evaluation-time oracle conditioning，必须与 deployable detector-gated chain 分开报告（见 M1）。

## 六、方法与实验专项结论

### 真实/实验支撑

- 主数值与 P12 冻结摘要一致，未发现稿件凭空增加实验结果。
- controlled replay 明确保留 0/12 detector-gated 负结果，是当前稿件最可信的能力边界之一。
- matching-commit-only 重算真实关闭了第一轮 C1，但 build-target relevance 尚未建立。

### SHAP 有效性

- conservation 是算术守恒检查，不是解释正确性证明；稿件对此表述正确。
- paired masking 和 donor sensitivity 支持 predictor reliance under perturbation，且主张已适当降级。
- semantic consistency 明显 mapping-dependent，External near-random、Global below-random 的负结果必须继续保留。

### uORB 模块映射

- commit 一致性和传播消融已有改善。
- 当前最大残留问题是 audit circularity、全源码树候选污染和缺少实际 build/runtime activation 约束。
- producer-only/topic-only 数值并不弱于 bidirectional，稿件没有声称唯一最佳模式，这一点处理合理。

### 统计报告

- paired method CI、masking flight-log CI、replay two-way cluster CI 均比第一轮完整。
- three-source-log × four-mutation 的 replay CI 极宽；稿件已承认低分辨率，不应再做显著性或稳定优势推断。
- 关键绝对性能仍需 cluster sampling CI（M6）。

### 最新基线

- 文献已包含 2025 CATCH、2025 GCAD 和 2026 UAV anomaly review/AeroTSBoost，时效性尚可。
- 实验基线的训练公平性仍不足（M5），不能把预算受限结果当近期强基线已解决。

## 七、结论是否过度

### 已得到良好控制的表述

- 不宣称 causal root cause localization。
- 不宣称 Cascade 在严格协议下稳定优于 Direct Five-Class。
- 不隐藏 External/Global semantic-map failure。
- 不把 onset-conditioned replay 当 detector-gated localization。

### 仍需降级或补证据的表述

- “runtime anomaly scores to architecture-aware evidence chain”需要说明真实飞行 architecture analysis 是 ground-truth-anomaly-conditioned。
- “explicit-declaration audit supported/validated the parser”需要降为 internal consistency，除非加入独立 reference。
- “matching-commit graph”不能让读者误解为 matching deployment build；当前只是 commit-level whole-source-tree graph。

## 八、Devil's Advocate 最强反论点

当前论文最强的反论点是：architecture-aware 层可能仍主要是一套可追踪但受 oracle labels、whole-source-tree graph 和同源 parser audit 支配的后处理。matching-commit 修复消除了跨版本错配，却没有证明候选模块实际编入目标固件，也没有证明 1.000 audit 独立于解析规则。与此同时，真实飞行模块排名只在 ground-truth anomaly windows 上生成，而完整 detector 在 replay 上为 0/12。因而，现有证据稳健支持“条件化的 inspection-oriented evidence organization”，但尚不足以支持“已验证的 runtime detector-to-module evidence chain”。这一反论点可以通过 Stage-1-gated real-flight analysis、build-target filtering 和独立 uORB edge audit直接回应，无需改变原始数据。

## 九、投稿前最低关闭条件

1. **必须关闭 M1**：明确 oracle conditioning，并补 Stage-1-gated real-flight subset 分析或全面降级 chain claim。
2. **必须关闭 M2/M3**：把 uORB audit 降为 internal consistency，且过滤/敏感性处理非 build-target modules；最佳方案是独立审计并按 build graph 重算。
3. **必须关闭 M4**：给出 Consistency/Hit/random baseline 方程和完整 mapping。
4. **必须处理 M5**：补公平近期基线，或把预算受限 CATCH/GCAD 从竞争性比较降为 feasibility references。
5. **必须关闭 M6/M7**：补关键 cluster CI 和非代码 Supplement/reproducibility tables。
6. 清除 CRediT、Acknowledgments 和伦理声明占位问题。

完成以上内容后，稿件可进入一次短的投稿前终审；在当前状态下不建议立即提交。

## 十、核验记录

- LaTeX 当前可成功编译为 25 页 PDF；未发现未定义引用或明显版面阻断。
- 自动测试：29 passed，1 deselected。被排除的是 `test_parse_uorb_source_roles`，原因是当前 Windows 沙箱的 pytest 临时目录权限错误；不能将其记为通过或失败。
- 参考文献/当前期刊要求核查：*Drones* 当前 Instructions for Authors 要求 Article 包含 Materials and Methods、最新相关文献、Author Contributions、Funding、COI 等必要部分，并要求方法足够详细、公开全部实验 controls、在可能情况下提供完整数据；2026 年起 Highlights 为投稿必需部分。当前稿件已包含 Highlights，但复现材料和 CRediT 尚未完成。
- 本轮未修改 manuscript、figures、tables、raw data、model outputs 或 references。
