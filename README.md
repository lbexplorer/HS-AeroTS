# HS-AeroTS-FL

## Start Here

- `PROJECT_OVERVIEW.md`: compact AI-friendly project summary, methods,
  experiments, results, and scientific limits.
- `reports/p9/INDEX.md`: P9 report and artifact index.
- `docs/INDEX.md`: archived research plans, paper materials, and references.
- `AGENT.md`: project-specific engineering and evidence constraints.

P1–P13 及 P9 后续独立验证已经完成。主数据源为 UAV-SEAD；P9 是 Ubuntu-20.04 下的 Controlled PX4 ULog Replay with Source-Level Mutations，不是完整 closed-loop SITL，且不安装或运行 Gazebo、ROS、QGroundControl 与 NuttX。后续实验和投稿阶段复算独立保存，不改变已冻结的上游结果。

## 环境

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e .
```

## P1 流程

```powershell
# 仅下载 mapping.json 覆盖的标注日志；原始数据不会提交到版本库
hs-aerots-data download

# 解析所有标注 ULog，生成 reports/p1 下的数据清单与数据字典
hs-aerots-data inventory --workers 4

# 使用覆盖率不低于 60% 的核心通道，将指定日志对齐到 10 Hz
hs-aerots-data align "<mapping中的日志键>" --output data/processed/smoke.csv.gz
```

P1 完成证据集中保存在 `reports/p1/`：

- `download_manifest.csv`：标注键与官方仓库文件的匹配情况；
- `dataset_inventory.csv`：每个日志的可读性、时长、topic 和通道数量；
- `annotations.csv`：可直接读取的日志级类别与异常时间区间；
- `data_dictionary.csv`：通道、topic、字段类型、日志覆盖率及核心通道标记；
- `data_dictionary_all_numeric.csv`：原始 ULog 中全部数值字段的审计字典；
- `core_channels.txt`：覆盖率不低于 60% 的 AeroTSBoost 候选通道；
- `summary.json`：P1 汇总和 87 通道一致性检查。
- `source_versions.json`：数据、官方工具与解析库的固定版本；
- `upstream_smoke_test.json`：官方 ULog→CSV 工具的实测结果。
- `alignment_smoke_test.json`：87 通道、10 Hz 对齐和异常区间的端到端验收结果。

原始 ULog 只读使用。所有 CSV、清单和统计结果均由命令重新生成，不手工修改。

核心通道筛选复现 AeroTSBoost 公开预处理脚本：先限制状态估计相关 topic/field，剔除日志内无有效变化的字段，再保留出现在至少 60% 成功转换日志中的通道。缺失的整列在对齐后填 0；后续标准化统计只能由训练集计算。

## P2 AeroTSBoost 基线

配置文件为 `configs/p2_aerotsboost.yaml`。默认协议是按每条 flight log 内部时间顺序进行 70%/15%/15% 划分，不使用随机 window-level split。

```powershell
# 生成 87 通道、10 Hz 的紧凑对齐缓存
hs-aerots-baseline prepare-aligned --workers 4

# 仅用训练窗口拟合标准化统计，生成每通道 18 个描述符
hs-aerots-baseline build-features

# 运行五种子、类别平衡的 LightGBM 主基线
hs-aerots-baseline train --seeds 0 1 2 3 4
```

P2 完成证据位于 `reports/p2/`：`feature_summary.json` 记录规模一致性检查，`feature_dictionary.csv` 提供 1,566 个特征到通道/topic 的映射，`seed_metrics.csv` 和 `baseline_summary.json` 保存五种子结果。模型和逐窗口分数位于 `reports/p2/baseline_runs/`，可由上述命令重新生成。

## P3 Stage 2 子系统诊断

P3 沿用 P2 的特征和 per-log chronological 划分，不重新随机划分窗口。仅选择标签为异常且具有明确类别的窗口，诊断为 External Position、Global Position、Altitude 或 Mechanical/Electrical。

```powershell
hs-aerots-diagnosis --config configs/p3_stage2.yaml --seeds 0 1 2 3 4
```

命令运行五种子 multiclass LightGBM、Random Forest、多数类和分层随机对照；随后连接对应种子的 P2 检测器生成 HS-AeroTS 两阶段级联结果，并运行一个直接五分类 LightGBM 对照。

P3 证据位于 `reports/p3/`：`completion_summary.json` 保存验收结论，`method_summary.csv` 保存模型汇总，`per_class_metrics.csv` 保存各类 Precision/Recall/F1，`channel_subsystem_mapping.csv` 为 P4 提供通道到子系统的显式映射。

## P4 分层 SHAP 聚合与定量解释

P4 固定使用 P3 的五个 Stage 2 LightGBM 模型，并通过 LightGBM 原生贡献值计算精确 TreeSHAP。绝对贡献按“统计特征 → telemetry channel → PX4 topic → subsystem”逐级求和。Top-k 排名仅由验证集确定，遮蔽替代值仅由训练集抽样中位数生成，测试集只用于最终评估。

```powershell
hs-aerots-explain --config configs/p4_explainability.yaml
```

主要产物位于 `reports/p4/`：

- `shap_*_importance.csv`：五种子汇总的 feature、channel、topic 和 subsystem 重要性、贡献占比及单位特征强度；
- `masking_results.csv`：K=10/25/50/100 的验证集 SHAP Top-k 遮蔽与 20 次同规模随机遮蔽对照；
- `consistency_at_k.csv`：总体、正确预测子集和各异常类别的 Consistency@K、Hit@K、贡献质量占比及精确随机基线；
- `window_evidence_seed0.csv`：种子 0 每个测试窗口的 Top-10 通道证据；
- `explanation_protocol.json` 与 `completion_summary.json`：无泄漏协议和 P4 验收结论。

五种子结果显示：聚合守恒误差不超过 `7.11e-15`；Consistency@1 为 `0.3705±0.0109`，高于随机基线 `0.1703`；Top-100 SHAP 遮蔽使 Macro-F1 平均下降 `0.2683`，同规模随机遮蔽仅下降 `0.0037`。External Position 的类别级 Consistency@1 仅略高于随机基线，使用这些解释时必须保留这一限制。

## P5 CATCH / GCAD 增强基线

```powershell
# 需另行安装 CUDA 版 PyTorch 与 requirements-p5.txt
hs-aerots-deep all --config configs/p5_deep_baselines.yaml
```

CATCH 调用官方模型主体，保持 P2 固定窗口和 chronological split；受 6 GB 显存约束，87 通道按 PX4 topic 聚合为 18 维，并从正常训练窗确定性抽样 4,096 个窗口。三种子 AUPRC 约为 `0.1930`，明显低于 P2 主基线。GCAD 未发现官方代码，项目只提供明确标注的线性 VAR(1) Granger/预测误差消融（AUPRC `0.1991`），不得引用为原论文模型的复现结果。证据见 `reports/p5/`。

## P6 ALFA 外部验证

```powershell
hs-aerots-alfa --config configs/p6_alfa.yaml build-features
hs-aerots-alfa --config configs/p6_alfa.yaml evaluate
```

官方 ALFA processed CSV 经 MD5 校验后，映射 16 个共享物理通道并复用 P2 的 10 Hz、96/8/12 窗口协议。46 条有 ground truth 的序列生成 5,273 个窗口。UAV-SEAD 验证集固定阈值下，五种子外部 AUPRC 为 `0.3181±0.0086`，AUROC 为 `0.6679±0.0069`，F1 为 `0.3121±0.0006`，log-aware Event-F1 为 `0.7071±0.0320`。仅作二元异常检测，不映射子系统类别。证据见 `reports/p6/`。

## P7 Unknown Fault

```powershell
hs-aerots-unknown --config configs/p7_unknown_fault.yaml
```

Uncategorized 航次从训练中整组排除；固定 P2 测试切片上，以航次 top-10% 窗口均分作弱标签筛查。五种子航次级 AUPRC 为 `0.2784±0.0046`、AUROC 为 `0.6610±0.0049`、F1 为 `0.3307±0.0142`，未知召回率为 `0.4118±0.0314`。因其没有异常时间范围，不能报告点级或 Event-F1。证据见 `reports/p7/`。

## P8 PX4 软件模块映射

```powershell
hs-aerots-map --config configs/p8_software_mapping.yaml
```

该阶段只读扫描 1,389 条 ULog 的 `ver_sw`，固定占比最高的 PX4 提交 `82aa24ad...`（562 条日志），从官方源码解析 uORB 发布/订阅关系。18/18 个 P4 topic 均有映射，共 180 条边、54 个模块；三种传播模式均通过贡献守恒。静态依赖只用于生成模块嫌疑度，不宣称根因。

## P9 Controlled PX4 ULog Replay with Source-Level Mutations

配对 replay 后续优化与独立新源航次验证已完成。开发集配对残差结果为检测 10/12、Top-1/3/5 为 4/12、10/12、10/12、MRR 0.5833、正常误报 1/12；独立集冻结主配置检测 12/12，但正常误报 11/12，且多数故障在 onset 前报警。Normal-only 门控优化未能同时保持低误报、较高 Recall 和稳定排名，因此不晋升为主方法。完整结果见 [P9 报告索引](reports/p9/INDEX.md)。

2026-09-06 专项复评已修复旧 replay 从 Windows 挂载盘读取时回放不完整的问题。复用原输入、二进制和模型，仅重跑 P9 并排除无输入更新尾段后：detector recall 为 10/12，门控 Top-1/3/5 为 2/12、5/12、5/12，MRR 为 0.3259；但 baseline 也报警 10/12，原注入效应检查为 11/12 通过，仍不能支撑可靠端到端诊断。新复现命令及完整证据见 [P9 专项报告](reports/p9/stage1_reassessment/README.md)。以下为历史流程与原始结果，予以保留。

```powershell
hs-aerots-sitl prepare --config configs/p9_sitl_injection.yaml
hs-aerots-sitl check --config configs/p9_sitl_injection.yaml

# 在提升权限的 Ubuntu-20.04 WSL 中构建并运行全部真实 ULog replay
wsl --distribution Ubuntu-20.04 --user root -- bash /mnt/d/UAV/scripts/p9/run_replay_pipeline.sh

# 回到 Windows 环境计算定位指标并验证注入效应
hs-aerots-sitl evaluate --config configs/p9_sitl_injection.yaml
python scripts/p9/validate_injection_effects.py
```

在固定 PX4 提交 `82aa24ad...` 上完成 Commander 导航状态覆盖、EKF2 innovation 偏置、INAV 高度状态冻结和 Land Detector `landed` stuck-at 四类源码 mutation。3 条真实 UAV-SEAD ULog 共形成 24 次 baseline/fault replay，12/12 个 mutation/log 效应检查通过，解析错误为 0。

已知 30 秒 onset 条件下，fault-minus-matched-baseline TreeSHAP 模块排名的 Top-1/3/5 为 `0.250/0.333/0.333`，MRR 为 `0.3227`，mean EXAM 为 `0.3318`；Top-1/3/5 定位延迟中位数为 `0.4/4.8/1.2 s`。但 P2 固定阈值对 12 个 fault run 的检测召回为 `0`，所以检测门控 Top-k/MRR 均为 `0`，检测与门控定位延迟不可定义。这是必须保留的端到端负结果，onset-conditioned 指标不能写成完整系统性能。源 ULog 缺少旧版专用 replay 所需的 `ekf2_timestamps`，因此 EKF2 使用两条件共享、仅由环境开关激活故障的通用 replay 发布适配器；详见 `reports/p9/completion_summary.json`。

## P10 两项低成本补实验

```powershell
# 固定 P2 划分上的直接五分类五种子
hs-aerots-diagnosis --config configs/p10_direct_five_seeds.yaml

# 严格 purged 端到端敏感性（复用只读 aligned cache）
hs-aerots-baseline --config configs/p10_purged_p2.yaml prepare-aligned --workers 1
hs-aerots-baseline --config configs/p10_purged_p2.yaml build-features
hs-aerots-baseline --config configs/p10_purged_p2.yaml train --seeds 0
hs-aerots-diagnosis --config configs/p10_purged_p3.yaml --seeds 0
hs-aerots-robustness --config configs/p10_robustness.yaml
```

直接五分类五种子 Macro-F1 为 `0.6599±0.0029`。在每个边界两侧剔除 14 个窗口后，Stage 1 AUPRC 为 `0.5936`，Stage 2 Macro-F1 为 `0.7983`，级联 Macro-F1 为 `0.5444`，直接五分类 Macro-F1 为 `0.5962`。`reports/p10/protocol_comparison.csv` 同时给出 1,000 次航次级 bootstrap 95% CI。Purging 降低了所有主要指标，并使 Cascade 与 Direct Five-Class 的排序相对固定划分发生反转：严格 purged 协议下 Direct Five-Class 更高。因此固定划分结果必须与该敏感性结果同时报告。

## P11 Leave-log-out 严格实验

P11 将每条 flight log 完整分配到 train、validation 或 test，固定为 970/206/213 条日志，不允许同一航次跨集合。复用 P2 只读对齐缓存，结果写入 `reports/p11/llo/`。

```powershell
hs-aerots-baseline --config configs/p11_leave_log_out_p2.yaml build-features
hs-aerots-baseline --config configs/p11_leave_log_out_p2.yaml train --seeds 0 1 2 3 4
hs-aerots-baseline --config configs/p11_leave_log_out_p2.yaml train-random-forest --seeds 0 1 2 3 4
hs-aerots-diagnosis --config configs/p11_leave_log_out_p3.yaml --seeds 0 1 2 3 4
python scripts/p11/aggregate_llo.py
```

五种子结果为：Stage 1 LightGBM AUPRC `0.6296±0.0023`，二元 Random Forest AUPRC `0.5645±0.0041`，Stage 2 LightGBM Macro-F1 `0.9041±0.0029`，Stage 2 Random Forest Macro-F1 `0.8741±0.0028`，HS-AeroTS Cascade 五分类 Macro-F1 `0.5962±0.0048`，Direct Five-Class Macro-F1 `0.6092±0.0043`。按 213 条测试 flight log 进行 1,000 次 bootstrap；完整 95% CI 见 `reports/p11/llo/p2/summary_5seeds_bootstrap.json` 和 `reports/p11/llo/p3/method_summary_5seeds_bootstrap.csv`。Direct Five-Class 比 Cascade 高 `0.0130` Macro-F1，但配对差值 95% CI 为 `[-0.0282, 0.0438]`，包含 0；严格 LLO 下不支持两者存在稳定性能差异，更不支持 Cascade 优于 Direct Five-Class 的性能主张。
