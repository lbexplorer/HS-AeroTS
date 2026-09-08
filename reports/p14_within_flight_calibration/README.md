# P14 Within-flight self-calibrated detection gate

日期：2026-09-07。状态：一次性开发冻结、独立集预测、计分与失败分析均已完成。未修改论文，未重跑 replay，未训练模型，未重算 SHAP 或模块排名。

**结论：本次实现显著降低了误报的点估计，但过度牺牲故障召回，不满足实验目标，不晋升为主 gate。** Independent 正常误报由 11/12 降至 2/12，故障 Recall 却由 12/12 降至 3/12。此处“显著降低”仅指幅度大，不表示统计显著；只有三个源航次，不能据此确认总体收益。冻结后没有继续调整参数。

## 1. 实现与范围

本实验对现有 P9 **标量 residual score** 做 self-calibration。该 score 已由原流程执行 feature noise normalization、channel/topic 最大值聚合。本实验不重新提取 residual，不改变上述聚合，不引入逐 topic 新特征。

输入：

- 开发集：`reports/p9/paired_residual/corrected_results/window_predictions.csv`。
- 独立集：`reports/p9/paired_residual/independent/window_predictions.csv` 中原 primary calibration `2019-01-18__08_39_38`。
- optimized 对照：`reports/p9/paired_residual/independent/optimized_gate_candidates/development_quantile_q0.9_e1_w15/`。
- 排名：独立集原 `module_rankings.csv` 的 primary calibration；预测阶段不读取排名或真实模块。

每个 replay target 分别使用自身分数校准，包括正常目标。参考正常 replay 仍由原 P9 提供；self-calibration 没有取消 matched-reference 前提。12 个故障与 12 个正常目标来自三条源航次，不能当成 24 条独立航次。

协议：

1. `0–15 s` 不校准、不检测。
2. 使用窗口结束时间落在 `[15,25) s` 的分数计算 median 和 MAD。
3. `25–30 s` 不更新校准、不触发报警。
4. `>=30 s` 正式检测；跨越 30 秒以前的高分不累计到连续触发中。

公式：

```text
m = median(score[15 <= time_s < 25])
MAD = median(abs(score_calibration - m))
scale = max(1.4826 * MAD, 0.05 * abs(m), 0.05)
z(t) = max(0, (score(t) - m) / scale)
alarm(t) = 最近连续 3 个正式检测窗口均满足 z > threshold
```

连续触发复用 `hs_aerots.replay_detection.sustained_gate`，在第三个超阈值窗口才报警，不回溯标记。MAD 系数、两个尺度下限、最少八个校准窗口和阈值选择规则在独立预测前固定，没有选择多个候选方案。实际 48 个开发/独立目标全部校准有效；独立目标每条均为 13 个校准窗口，6/24 条使用尺度下限。

## 2. 阈值冻结

冻结时间：`2026-09-07T05:32:06.067502+00:00`。

仅对 12 个 **development 正常目标**，先按上述方式进行自身校准，再计算各正常目标 30 秒后的“连续三窗口最小值”的全程最大值。阈值取这些运行最大值的第二大值，并设下限 3：

```text
threshold = max(3, second_largest(development_normal_event_maxima))
          = 30.691756916624588
```

因比较为严格 `>`，此规则允许至多 1/12 开发正常目标报警；这是沿用原开发候选 1/12 误报水平的预设经验目标，不是总体误报保证。没有使用 development fault 结果选择阈值，也没有使用 independent score 或 fault 结果选择阈值。

最高两个开发正常运行最大值为：

| 开发正常目标 | self-calibrated event maximum |
|---|---:|
| Land Detector / 2019-01-25 | 33.5565 |
| EKF2 / 2019-03-06 | 30.6918 |

冻结后才预测开发故障和 independent 目标。预测文件先落盘并 SHA-256 封存，再读取已有标签和模块排名计分。`protocol.json` 保存阈值、规则、实现与开发输入哈希；`prediction_freeze.json` 保存预测和独立分数输入哈希。程序拒绝覆盖已有协议和预测封存。

冻结后的开发集检查：Fault Recall **11/12**，Normal False Alarms **1/12**，Pre-onset Alarms **0/12**，干净故障独有检出 **10/12**。开发排名仅沿用已有可用排名，新检出的原未排序运行仍按无排名计分，未补算排名。

## 3. 三种 gate 的主对比：统一冻结排名

为遵守“只改变 gate、module ranking 保持不变”，三种 gate **全部采用同一份原 frozen gate 的离线模块排名**。gate 在正式检测区间没有报警时，Top-k 与倒数排名计零；有报警时使用原名次。没有根据新 gate 选择新的 SHAP 窗口或重新排序。因此这里衡量的是固定候选排名的检测可用性，不是重新评估新报警时刻的定位证据或在线定位时延。

| Gate | Fault Recall | Normal False Alarms | Pre-onset Alarms | Top-1 | Top-3 | Top-5 | MRR |
|---|---:|---:|---:|---:|---:|---:|---:|
| 当前 frozen gate | 12/12 (100.0%) | 11/12 (91.7%) | 10/12 | 6/12 | 9/12 | 9/12 | 0.6369 |
| 已有 optimized q90 + 15 s warm-up | 12/12 (100.0%) | 11/12 (91.7%) | 9/12 | 6/12 | 9/12 | 9/12 | 0.6369 |
| P14 within-flight self-calibrated | **3/12 (25.0%)** | **2/12 (16.7%)** | **0/12*** | **1/12** | **3/12** | **3/12** | **0.1667** |

`*` P14 的正式检测从 30 秒开始，Pre-onset Alarms 为零由协议强制产生，不能作为自主识别故障起点或消除初始化误报的独立证据。

**为什么 optimized 的排名指标与旧报告不同？** 历史 optimized 实现按其 gate 聚合了原 Stage 2 SHAP 模块证据，历史 Top-1/3/5 为 **4/12、5/12、5/12**，MRR **0.4116**。上表为了隔离 gate 效应，统一使用 frozen 模块排名；其历史结果保存在 `historical_published_metrics.csv`，原实验文件未被更改。两个旧 gate 的检测、正常误报及提前报警计数均从原逐窗口文件复现，并与历史汇总一致。

## 4. 共同检测时间范围对照

P14 的报警机会比旧 gate 少，因此额外将两个旧 gate 的既有报警也只在 `>=30 s` 区间计分，不重新调阈值或重算排名：

| Gate | Fault Recall | Normal False Alarms after 30 s | Top-3 | MRR |
|---|---:|---:|---:|---:|
| Frozen，仅计 30 s 后 | 12/12 | 10/12 | 9/12 | 0.6369 |
| Optimized，仅计 30 s 后 | 12/12 | 11/12 | 9/12 | 0.6369 |
| P14 | 3/12 | 2/12 | 3/12 | 0.1667 |

误报下降并非仅由排除早期报警造成。但在统一时间范围后，干净故障独有检出为 frozen **2/12**、optimized **1/12**、P14 **2/12**，P14 相对 frozen 并未增加这种具有对照特异性的检出数。

## 5. 分 mutation 与失败机制

| Mutation | P14 检出 | 配对正常误报 | 固定排名 Top-3 |
|---|---:|---:|---:|
| Commander | 0/3 | 0/3 | 0/3 |
| EKF2 | 1/3 | 1/3 | 1/3 |
| INAV | 0/3 | 0/3 | 0/3 |
| Land Detector | 2/3 | 1/3 | 2/3 |

三个源航次各检出 1/4 个故障，故障召回下降并非只集中在单一航次。实际三次检出的延迟为 EKF2 **8.4226 s**、Land Detector **2.0183 s / 2.0242 s**；这是检测时间，不能解释为固定离线模块排名在该时刻已经完成。

### 5.1 降低误报的代价是较高的运行内有效阈值

将阈值还原到原始 score 空间，可写成 `m + 30.6918 * scale`。Commander 三条的有效阈值分别为 **106.07、164.04、132.52**，而注入后的原始持续分数最大值只有 **65.46、75.37、79.53**，因此全部漏检。INAV 的三个标准化持续最大值为 **0.778、16.006、16.500**，均未超过冻结阈值。

这说明自校准确实抑制了一批正常残差，却没有让故障偏离在同一个分数空间中充分突出。不能把低误报单独当成方法成功。

### 5.2 短正常段包含的运行差异被当成了正常尺度

EKF2 / 2018-12-20 的校准中位数约 **208.09**、MAD 约 **71.24**，还原后的原始阈值约 **3449.54**，而注入后的持续最大分数约 **879.56**，故障被大尺度掩盖。

EKF2 / 2018-12-25 的校准中位数约 **226.68**，注入后的原始持续最大分数约 **117.54**，单向正偏离标准化得到的持续最大值为 **0**。对“相对校准阶段分数升高”的 gate 而言，该运行缺少可检出的持续升高；这是标量 score 的观测结果，不能据此说 mutation 未生效。

### 5.3 仍有正常后段偏离校准段

剩余误报为 EKF2 / 2018-12-25 正常目标、Land Detector / 2018-12-20 正常目标，标准化持续最大值分别为 **119.08、38.92**。二者都使用尺度下限，早期短段的稳定不能代表后续全程稳定。MAD 校准不能自动解决飞行阶段变化、初始化差异或匹配参考差异。

### 5.4 标量聚合的限制

本次先保留原 max-topic score，再进行运行内标准化。最大分数可能在不同 topic 之间切换，校准段主导 topic 的波动尺度可能抑制故障 topic 的较弱变化。这与已有 P9 审计相符，但本次没有重新计算逐 topic 残差，因此只作为机制解释，未验证逐 topic self-calibration 的收益。负结果只针对这里冻结的标量实现，不等于排除所有 within-flight 校准方法。

## 6. 统计与时间协议边界

- 正常误报减少 **9/12**，Fault Recall 也减少 **9/12**，均为 75 个百分点；这是观察到的权衡，未达到“降低误报同时保持较好检测”的目标。
- 三个源航次聚类的探索性配对符号翻转比较，误报变化和召回变化的双侧 p 值均为 **0.25**。三组数据统计分辨率很低，不将运行级 12 个配对当成 12 条独立航次，也不声称统计显著。
- 每条运行只有 13 个校准分数，窗口长度 9.6 秒、步长 0.8 秒，高度重叠。这里按**分数窗口结束时间**选取校准；最早校准分数的原始观测包含 warm-up 尾段。为保持原特征不变，没有重提取完全落在 15–25 秒内的窗口，因后者仅约一个窗口，无法可靠估计 MAD。
- 开发 CSV 使用源对齐 elapsed clock，独立 CSV 使用目标 ULog header elapsed clock。审计确认所有独立目标为原规则的等间隔网格；转换为源网格不改变任何 15–25 秒校准窗口或 30 秒后检测窗口的成员归属。没有以此重新选择阈值或生成另一套预测。
- 已知 30 秒后才可能进入正式检测，以及已知 15–25 秒正常，是用户指定的额外先验。本实验不能支持未知 onset 的自主在线检测，不能评价正式检测开始前发生的故障。
- 当前 independent 航次已被历史 P9 查看，且存在历史 P2 标准化器训练暴露；这是一项在既有集上的预先冻结后续消融，不是全新盲测。
- 既有一条 mutation 效应检查失败仍保留在 12 条故障的主分母中。未删除难例或无有效排名的运行。

## 7. 是否值得进入论文正文

**不建议作为正向方法改进或替代原 gate。** 它没有同时保持低误报与较好 Recall，不能作为新增可靠诊断主张。

如果论文需要回答“为何不直接用每航次故障前正常段校准”，可以在正文消融或 Discussion 中用一小段报告 **11/12 → 2/12 正常误报、12/12 → 3/12 故障检出**，完整协议和表格放补充材料。这是对简单自校准方案局限的负结果，而不是优于原方法的证据。若篇幅有限，优先作为补充实验保存。本任务未修改论文。

没有继续调整 MAD 系数、尺度下限、校准区间、聚合方式或阈值。未来若研究逐 topic 稳健残差，需要单独立项和新的确认数据，不能据当前 independent 结果再挑最佳参数。

## 8. 复现与验证

环境：当前 Python 3.12、NumPy 2.5.1；不需要 pandas、训练环境或 raw ULog 缓存。

```powershell
# 在全新输出目录首次执行；已有协议/预测会拒绝覆盖。
python -X utf8 scripts/p14/run_experiment.py --phase freeze
python -X utf8 scripts/p14/run_experiment.py --phase predict
python -X utf8 scripts/p14/run_experiment.py --phase score
python -X utf8 scripts/p14/analyze_results.py

$env:PYTHONPATH = Join-Path (Get-Location).Path 'src'
python -X utf8 -m unittest discover -s tests -p test_within_flight_gate.py -v
```

Windows 默认 GBK 读取 UTF-8 中文路径清单时曾使首次计分的最后一个完整性核验步骤退出；随后以 `-X utf8` 重执行同一计分命令完成核验。实现、阈值和已封存预测未改变，此次重试不是调参或重新预测。

- 7 项行为测试通过：未来分数不得改变校准、warm-up 不拟合、MAD 为零处理、最少窗口数、异常校准值鲁棒性、连续触发及 30 秒边界。
- 独立的直接公式与逐三窗口检查复核了全部 independent 预测，结果一致。
- 768 个原受版本控制文件 SHA-256 前后完全一致，包括现有实验报告、模型、配置、SHAP/排名产物与原实现。
- 本次新增代码只在 `src/hs_aerots/within_flight_gate.py`、`scripts/p14/` 和对应测试；结果只写入本目录。

## 9. 产物索引

| 文件 | 用途 |
|---|---|
| `protocol.json` | 冻结阈值、时间协议、实现及开发输入哈希 |
| `development_normal_calibration.csv` | 12 个开发正常对照的阈值来源 |
| `development_summary.csv` | 冻结后的开发集检查 |
| `prediction_freeze.json` | 先预测后计分的封存记录 |
| `window_predictions.csv` | 开发与独立集逐窗口预测 |
| `self_calibration_by_run.csv` | 每条运行 median、MAD、scale 与有效性 |
| `comparison_fixed_rank.csv` | 三种 gate 的统一排名主表 |
| `historical_published_metrics.csv` | 两个旧 gate 的原报告指标 |
| `comparison_post30_common_exposure.csv` | 统一计分时间范围对照 |
| `comparison_by_source.csv` / `comparison_by_mutation.csv` | 分组结果 |
| `results_by_run.csv` | 三种 gate 逐运行结果 |
| `failure_analysis_by_run.csv` | 有效阈值与实际持续分数对照 |
| `source_cluster_comparison.csv` | 三航次聚类的探索性比较 |
| `verification.json` / `analysis_checks.json` | 完整性与预测复核 |
| `protected_inputs_before.json` | 768 个原文件保护清单 |
