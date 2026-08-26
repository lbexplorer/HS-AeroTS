# HS-AeroTS-FL 第一轮修订记录

修订日期：2026-08-25
目标期刊：MDPI *Drones*
依据：`HS-AeroTS-FL_round1_review.md`
工作流：academic-research-suite `/ars-revision`
上一轮决定：Major Revision

## 修订边界

- 未修改原始实验数据、P1–P11 冻结报告、模型输出或参考文献。
- 只把已有冻结结果补入论文，并收窄证据不足的主张。
- 所有需要作者身份信息、公开仓库信息、新标注、新实验或重新计算才能关闭的问题，均在正文或本记录中标为 `[AUTHOR ACTION REQUIRED]`。
- 修订后的 LaTeX 已成功编译为 24 页 PDF；无未定义引用、未定义文献或 LaTeX overfull 警告。

## 逐项修改记录

| ID | 等级 | 原问题 | 已完成修改 | 修改位置 | 状态 |
|---|---|---|---|---|---|
| C1 | Critical | 单一多数提交图被表述为全样本 “version-matched” | 全稿改为 “majority-commit/static commit-specific graph”；补充 7 commits、562/1389 logs、42.3% 全部测试窗及 38.7% 异常测试窗覆盖率；明确 Figure 3(d) 仍是跨版本探索性结果；摘要、讨论、结论同步降级 | Abstract；§1.1–1.3；§2.3–2.4；§3.4；§5.2；Figure 3(d) caption；§6.1、§6.4；§7 | **PARTIAL**：需按 commit 重算或只在匹配子集重算 |
| M1 | Major | subsystem “ground truth” 实为字符串启发式 | 改称 predefined semantic mapping；明确没有独立标注、Shared 处理及 External Position 近随机结果；不再将 Consistency@K 解释为独立真值一致性 | §2.2；§3.3；§5.2；Figure 3(b,c) caption；§6.4；§7 | **PARTIAL**：需独立专家标注与一致性统计 |
| M2 | Major | SHAP masking 的 “necessary” 主张过强，比较缺少配对不确定性 | RQ2、Related Work、Methods、Results、Discussion 改为 prediction relevance / perturbation sensitivity；明确训练中位数替换可能 off-manifold，seed SD 不是 flight-log CI | §1.3；§2.2；§3.3；§5.2；§6.4 | **PARTIAL**：需配对 flight-log CI 和 on-manifold/conditional perturbation |
| M3 | Major | uORB 静态解析器和均匀传播缺少有效性验证 | 披露 500-character nearest API hint、可能遗漏宏/间接关系、角色误判、未有人工 gold set；说明 uniform allocation 的 degree bias | §3.4；§6.4 | **PARTIAL**：需人工 edge/role 审计及传播敏感性 |
| M4 | Major | 已完成 P9 mapping ablation 未进入论文 | 新增完整传播消融 Table 4：bidirectional、producer-only、consumer-only、topic-only、random mapping，含 Top-1/3/5 与 MRR 的 95% CI；明确未能确定唯一最佳模式 | §3.4；§5.2；Table 4 | **RESOLVED（报告层面）** |
| M5 | Major | replay 点估计无 CI，忽略 3 logs × 4 mutations 依赖 | 在正文补入 bidirectional Top-k、MRR、EXAM 的 95% CI；表格给各传播模式 CI；明确 run-bootstrap 未消除共享 log/mutation 依赖 | §4.2；§5.2 Table 4；§5.3；§6.4 | **PARTIAL**：需 clustered/hierarchical 分析及更大独立样本 |
| M6 | Major | 近期 CATCH/GCAD 仅在 Related Work 出现，结果被省略 | Methods 披露 CATCH 的 18-topic/4096 normal-window/3-seed 资源适配和 GCAD linear VAR(1) 非官方消融；Results 报告 CATCH 三 seed AUPRC 及 GCAD AUPRC；禁止据此宣称优于官方方法；Discussion 增加公平性说明 | §4.1；§5.1；§6.2 | **PARTIAL**：需至少一个官方、同划分、同预算近期基线 |
| M7 | Major | seed SD、single-seed purged、test-optimized F1 与多数比较的统计口径不足 | 明确 seed SD 仅反映训练波动；purged 是 single-run sensitivity；test-optimized F1 标为 oracle descriptive value；LLO 保持主要 unseen-log 证据；补 replay CI 局限 | §4.2；§5.1；§5.3；§6.2、§6.4 | **PARTIAL**：需 purged 多 seed、主比较的 paired flight-log CI |
| M8 | Major | 不存在的 Supplementary Table S1 / Supplementary Materials | 删除全部虚假 supplement 承诺；把核心超参数保留于 Table 3 注释；将冻结配置和 per-run records 统一指向 Data Availability 中的 analysis package；P9 消融移入主文 | §3.2–3.3；§4.2；Table 3；§5.2 | **RESOLVED（引用完整性）** |
| M9 | Major | Data Availability 不可执行 | 声明第三方数据与 PX4 属性、P1–P11 配置/manifest/scripts/reports 范围；加入 URL/DOI、release/commit、license、访问说明的作者动作标记 | Data Availability Statement | **PARTIAL**：作者必须提供实际公开地址与版本 |
| M10 | Major | “FL” 未定义，可能误导为 federated learning 或已验证 fault localization | 首次出现处明确 FL 不表示 federated learning，亦不得解释为已验证 fault localization；加入确认展开或改名标记 | §1.2 | **PARTIAL**：作者需最终命名决定 |
| m1 | Minor | Figure/Table 编号跳号、逆序 | 删除手工 counters；使用现有 methodological-pipeline 图补入 Figure 2；最终图号 1–5、表号 1–4 连续 | `main.tex`；§5.2–5.3 | **RESOLVED** |
| m2 | Minor | 作者、单位、经费、致谢占位符 | 所有模糊占位符替换为明确 `[AUTHOR ACTION REQUIRED]`；CRediT、funding、acknowledgments 均给出需要填写的内容类型 | 首页；Back Matter | **PARTIAL**：需作者填写 |
| m3 | Minor | 章节名与 *Drones* 常规结构不齐 | “Methodology” 改为 “Materials and Methods”；“Experimental Setup” 改为 “Experimental Protocols” | 主文 §3–4 标题 | **RESOLVED** |
| m4 | Minor | Discussion 与近期工作对话不足 | 新增对 CATCH/GCAD 资源限制、官方实现、公平比较条件的讨论；继续将架构证据与传统 fault localization 区分 | §6.2；§6.4 | **RESOLVED（基于现有证据）** |

## 结构与呈现变化

- 新增 Figure 2：使用工作区已有 methodological-pipeline 图，不生成或修改实验结果。
- 新增 Table 4：P9 冻结 mapping ablation 及原有 bootstrap CI。
- Figure 3(d) 的 caption 明示只有 38.7% 异常测试窗与所选 commit 匹配。
- Results 新增 P5 受限基线段落，但明确禁止将其解释为官方方法的公平排名。
- Methods、Results、Discussion、Conclusion 对同一证据边界使用一致措辞。

## 完整性核验

- `latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex`：通过。
- PDF：24 页。
- 未定义 citation/reference：0。
- 新增参考文献：0。
- 新增或改写原始实验数值：0；仅转录冻结 P5/P9 报告中的已有值。

## 第二轮投稿准备修订（2026-08-25）

本轮实际运行并写入新结果，未修改或编造原始实验数据：

| 项目 | 完成内容 | 结果与边界 | 状态 |
|---|---|---|---|
| C1 固件一致性 | 仅对提交 `82aa24ad...` 匹配的 1,393 个异常测试窗重算 topic→module 证据；重绘 Figure 4(d) | 38.67% 异常窗可用于该提交；度数归一化改变首位模块 | **RESOLVED**：删除跨版本总体排名主张 |
| M1 semantic map | 建立不读取 SHAP 的 document-derived 映射并重算全部 Consistency@K | 11/87 通道改变；External 近随机、Global 低于随机 | **RESOLVED BY CLAIM REDUCTION**：仅作映射敏感性，独立专家标注留作未来工作 |
| M2 SHAP masking | 五种子 × 20 随机重复；flight-log bootstrap；增加 joint training-donor 替换 | k=100 SHAP advantage 0.2646，95% CI [0.2052,0.3300]；donor drop 0.4955 [0.4604,0.5283] | **RESOLVED**（非因果边界保留） |
| M3 uORB parser | 审计 18 topics 的全部 244 个无歧义显式同语句 occurrence | 限定范围内 role agreement 与 explicit-edge recall 均为 1.000；宏/运行时边不在范围内 | **RESOLVED WITH SCOPE** |
| M5 replay dependence | 5,000 次 source-log × mutation-type 双向聚类 bootstrap | bidirectional Top-3 CI 扩展为 [0,0.75]；小集群局限保留 | **RESOLVED FOR CURRENT DATA** |
| M6 recent baseline | 官方 CATCH 模型核心、87 通道、相同固定划分、3 seeds | AUPRC 0.2094±0.0038；预算/监督差异完整披露 | **RESOLVED AS BUDGETED REFERENCE** |
| M7 statistics | purged Stage 1/2/Cascade/Direct 五种子；fixed/purged 配对日志 bootstrap | purged Direct–Cascade 0.0340，95% CI [-0.0047,0.0762] | **RESOLVED** |
| M9 availability | 删除公共仓库/DOI 要求 | 源码不公开；配置、划分与派生报告仅可保密提供 | **RESOLVED TO USER POLICY** |
| M10 naming | 全文将 HS-AeroTS-FL 改为 HS-AeroTS | 消除 FL 歧义 | **RESOLVED** |

第二轮新增/更新的主要证据目录：`reports/p12/commit_matched/`、`semantic_mapping/`、`uorb_audit/`、`statistics/`、`baselines/catch_full_channels/`。完整数字与投稿决定见 `HS-AeroTS_submission_readiness_round2.md`。

## 投稿元数据修订（2026-08-26）

- 写入五位作者的姓名、顺序和单位编号；Jiao Wu 与 Bo Liu 标记为共同第一作者，Junsheng Wu 标记为通讯作者。
- 按多作者稿件将 MDPI class 切换为 `moreauthors`，并加入 equal-contribution 脚注。
- Funding 填写为无外部资助；Conflicts of Interest 填写为全体作者无冲突。
- Data Availability 按实际使用的数据源写入 UAV-SEAD Hugging Face repository/revision、ALFA Figshare article/file、PX4-Autopilot commit 和相应许可边界；明确本研究分析源码不公开。
- 单位 1--3 的英文名称与地址、Jiao Wu 的邮箱及 Junsheng Wu 的通讯邮箱已按作者提供的信息写入，并使用 MDPI 原生 `\addhighlights` 区块加入四条证据受限的 Highlights。
- 尚待作者提供：五位作者的 CRediT 分工，以及 Acknowledgments。

## P13 零新实验、有限复算与投稿稿修订（2026-08-26）

本轮不采集数据、不训练或调参模型、不增加基线、不运行 PX4/SITL replay。统一复算器只读取冻结预测、模型、SHAP、uORB 边表和分组信息；85 个受保护输入在运行前后 SHA-256 完全一致。

| ID | 原 Major 问题 | 本轮处理 | 稿件位置 | 状态 |
|---|---|---|---|---|
| M1 | 条件化解释与部署链混用 | 报告 Stage-1-gated TP/FN/FP/TN；单列 detected true anomalies 与 false-positive suspect distribution；保留 ground-truth-anomaly-conditioned 分析但不混称 | Abstract；§1.2；§3.4；§5.2；§6；§7 | **ADDRESSED** |
| M2 | uORB `1.000 audit` 被当作独立验证 | 全文统一为 explicit same-statement internal consistency check，明确没有独立 gold audit | §3.4；§5.2；§6.4 | **MITIGATED**；残余限制保留 |
| M3 | whole-source-tree 图含明显不适用路径 | 按 PX4FMU_V2 + NuttX 做 conservative-exclusion sensitivity；180/54 降至 145/36，保留 18 topics；报告排除规则、Top-K overlap、排名变化和 degree-normalized sensitivity | §3.4；§5.2；Appendix B.3；Figure 3(d) | **MITIGATED**；不称 build graph |
| M4 | Consistency/Hit/weighted consistency/随机基线定义不完整 | 加入正式公式；Shared 固定为 non-match；随机基线为无放回精确基线 | §3.3 | **ADDRESSED** |
| M5 | 近期基线可能被解释为优越性证据 | CATCH 与 GCAD 统一定位为 budget-constrained feasibility references，禁止比较排名、superiority 或 SOTA 主张 | §4.1；§4.4；§5.1；§6.2 | **MITIGATED**；公平重训仍缺失 |
| M6 | seed SD 与 sampling uncertainty 混淆 | fixed/purged/leave-log-out/ALFA/Uncategorized 增加 cluster-bootstrap CI；Table 5 同时报告 point estimate、seed SD、95% cluster CI；图注逐项定义误差条 | §4.2；§5.1；§5.3；Table 5；Figures 3–5 | **ADDRESSED** |
| M7 | 无公开 Supplement 导致方法细节不足 | 正文附录加入完整 87-channel mapping、软件版本、bootstrap、过滤、split/window/log 摘要；Data Availability 如实说明保密材料范围 | Appendix A–B；Data Availability | **MITIGATED**；不提供机器可读公开 Supplement |

其他完成项：标题收缩为 commit-level inspection evidence；作者元数据、Highlights、CRediT、Funding、IRB、Informed Consent、Data Availability、AI-use Acknowledgments 与 Conflicts of Interest 全部填写；submit 模式 DOI footer 已抑制。

验证：新增 8 项单元测试；全套可运行测试为 37 passed、1 deselected（Windows sandbox 临时目录权限）；最终 LaTeX 为 30 页，无未定义 citation/reference、重复 label、overfull 或 DOI footer；渲染后检查首页、Figures 3–5、Table 5、Appendices A–B 和末页通过。
