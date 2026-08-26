# HS-AeroTS 投稿准备度第二轮报告

> 历史报告：本文档记录 P12 状态。P13 最终状态见 `HS-AeroTS_submission_readiness_final.md`；其中已关闭本文件所列的 CRediT 与 Acknowledgments 占位问题。

日期：2026-08-25
目标期刊：MDPI *Drones*
范围：完成固件一致性、映射审计、统计/敏感性和近期基线四项工作；不公开源代码，不制作公共复现包。

## 结论

四项科学补强均已执行，原稿中的跨版本模块汇总、单种子 purged 结果、未聚类回放区间和无配对区间的 SHAP 遮蔽主张均已替换。论文的最强结论现被限定为：HS-AeroTS 提供可追踪的异常检测、故障域诊断与版本一致的架构检查证据，不构成因果根因定位或可靠的 detector-gated 软件故障定位。

作者姓名、顺序、单位、共同第一作者、通讯作者、通讯邮箱、无外部资助和无利益冲突声明已补齐，并加入 Highlights。稿件仍需补充 CRediT 和 Acknowledgments 后提交。源码不公开已在 Data Availability 中如实声明；配置、划分清单和派生报告仅承诺可供编辑/审稿人保密核查。

## 1. 固件一致的模块映射

- 选定 PX4 提交：`82aa24adfca29321cfd1209e287eab6c2b16780e`；源码提交已核验一致。
- 固定测试集 34,059 个窗口中，14,419 个（42.34%）来自匹配固件；Stage 2 的 3,602 个异常测试窗中，1,393 个（38.67%）匹配。
- 模块证据仅从这 1,393 个异常窗重算，不再把其他固件的证据传播到单一图。
- producer-only 前五位为 `ekf2`、`mavlink`、`sensors`、`position_estimator_inav`、`load_mon`，SHAP 份额分别为 0.2274、0.2068、0.1036、0.0708、0.0663。
- 度数归一化后首位变为 `position_estimator_inav`，`load_mon` 为第二、`ekf2` 为第三、`mavlink` 降至第六。该敏感性排除了“稳定根因排名”的表述。

证据文件：`reports/p12/commit_matched/`。

## 2. 映射审计

### 通道到子系统

- 用不读取 SHAP 值的 PX4 消息/字段语义规则建立 document-derived 映射。
- 与原字符串规则相比，76/87 个通道一致，11 个通道改变。
- 新映射下总体 Consistency@1 为 `0.2500 ± 0.0056`，随机基线为 0.1707。
- External Position 为 0.0363（随机 0.0345）；Global Position 为 0.0349（随机 0.1379）；Altitude 为 0.3779（随机 0.1724）；Mechanical/Electrical 为 0.8788（随机 0.5402）。
- 因 External 接近随机、Global 低于随机，Consistency@K 已降格为作者定义映射敏感性，不再作为独立解释有效性真值。

### uORB 解析

- 审计覆盖全部 18 个研究主题的 244 个无歧义、同语句显式声明/调用，其中 publisher 130 个、subscriber 114 个。
- 在这一预先限定的显式范围内，role agreement 和 explicit-edge recall 均为 1.000。
- 结论不扩展到宏生成、间接保存或运行时创建的关系。

证据文件：`reports/p12/semantic_mapping/` 和 `reports/p12/uorb_audit/`。

## 3. 统计与敏感性

- Purged Stage 1 五种子 AUPRC：`0.6006 ± 0.0062`。
- Purged Stage 2 五种子 Macro-F1：`0.7944 ± 0.0049`。
- Purged Cascade 五种子 Macro-F1：`0.5683 ± 0.0177`；Direct Five-Class：`0.6024 ± 0.0049`。
- Purged 的配对 Direct–Cascade 差值为 0.0340，95% flight-log bootstrap CI `[-0.0047, 0.0762]`，不支持稳定差异。
- Fixed chronological 的配对 Direct–Cascade 差值为 -0.0303，95% CI `[-0.0524, -0.0086]`；该方向不能外推到更严格协议。
- SHAP 相对随机遮蔽的 Macro-F1 降幅优势在 k=10 为 0.0404，95% CI `[0.0102, 0.0713]`；k=100 为 0.2646 `[0.2052, 0.3300]`。
- 联合训练窗 donor 替换在 k=10 和 k=100 的降幅为 0.0516 `[0.0277, 0.0752]` 和 0.4955 `[0.4604, 0.5283]`。方向稳定，但仍不是因果试验。
- 回放采用 5,000 次双向聚类 bootstrap，独立重采样 3 个源日志和 4 种变异。bidirectional Top-1/3/5 的区间分别为 `[0,0.583]`、`[0,0.750]`、`[0,0.750]`；MRR 区间为 `[0.0455,0.6790]`。

证据文件：`reports/p12/statistics/`。

## 4. 近期基线

- CATCH 使用官方模型核心及已核验提交 `3647c69be5eb56649b072596cf89098e689e20c3`。
- 使用全部 87 个原始通道和相同 fixed chronological 划分；3 个种子；每种子 4,096 个正常训练窗；1,024 个正常验证窗；两轮训练。
- 三种子 AUPRC 为 `0.2094 ± 0.0038`，AUROC 为 `0.7318 ± 0.0052`，验证阈值 F1 为 `0.2992 ± 0.0038`，日志感知事件 F1 为 `0.2537 ± 0.0040`。
- 该执行消除了旧基线的 18-topic 聚合，但仍是预算受限、无监督正常训练与监督 LightGBM 之间的任务比较，不支持“全面优于 CATCH”的结论。

证据文件：`reports/p12/baselines/catch_full_channels/`。

## 仍保留的边界

### Major

1. semantic mapping 仍是作者定义而非外部专家裁决；已通过降低主张而非伪造标注解决投稿阻断。
2. 回放只有 3 个源日志、4 类变异和 12 个 fault runs；双向聚类区间很宽，且 detector gate 仍为 0/12。
3. 静态 uORB 图不表示运行时激活、调度、消息速率或间接物理反馈。
4. CATCH 的计算预算受限，不能据此形成无条件 SOTA 排名。

### Editorial / Author action

1. `[AUTHOR ACTION REQUIRED]`：五位作者的 CRediT 分工与 Acknowledgments。
2. Funding 已填写为无外部资助；Conflicts of Interest 已填写为全体作者无冲突。
3. 提交系统中确认源码不公开政策与 Data Availability 文本一致；若编辑要求匿名材料核查，可保密提供配置、划分清单和派生报告，但不承诺公开分析源码。

## 投稿决定

科学内容决定：**可投稿，需完成作者元数据后提交**。
证据强度决定：支持检测、故障域诊断和架构检查证据；不支持因果模块定位、跨固件总体模块排名或可靠端到端软件故障定位。
