# P9 冻结方法的新源航次验证

状态：36 次有效 replay 和冻结参数评估已完成；未根据独立结果调整参数。

本次遵循用户最新要求，冻结现有方法、阈值、噪声尺度、P2 标准化器及 P8 映射，不执行此前计划中的重新拟合。封存时间、参数选择规则、输入哈希见 `sealed/protocol.json` 和 `sealed/sha256.json`。

## 预先固定的设计

- 三个源航次：2018-12-19/07_49_17、2018-12-20/07_47_50、2018-12-25/08_44_40。
- 依据 Normal 标签、相同固件、完整核心字段、60–150 秒长度、不同日期与字典序选择；没有利用检测分数或 mutation 结果。
- 每航次四类 mutation，每类各运行参考正常、故障、独立正常目标；总计 12 个故障目标、12 个正常目标、12 个参考，共 36 次 replay。
- 使用开发阶段原有二进制与注入强度/时间，generic replay；EKF 继续使用已修复的 `ekf2 start`，不启用 `-r`。
- 87 通道 × 18 描述子，10 Hz、96 点窗口、8 点步长；首 256 个不变传感器样本恢复源时钟；仅比较双方真实传感器支持范围。
- 主配置固定为开发阶段已有最高数值阈值 26.47158145904541，配套 `noise_2019-01-18__08_39_38.npy`；另外两组原有配置仅作敏感性结果，不能事后择优。不同噪声向量意味着最高数值阈值不必然具有最小误报率。
- 不重新拟合噪声、不降低阈值；连续三窗口门控、正残差证据、既有 publisher 均分映射、54 个候选模块、并列最差名次均不变。
- 预测阶段不读取真实 onset、mutation 类型或真实模块。预测文件先写出并哈希，随后单独计分。排名使用全程已门控窗口，不能根据真实 onset 截取证据。
- 注入生效检查失败或漏检均保留在 12 个故障的主分母中；无自减正常对照，无测试结果驱动的替换源日志或重跑。

## 独立性边界

三个源航次均未参与 P9 开发，且均为 P11 leave-log-out test。但原 P2 chronological 训练包含它们各 67、98、115 个窗口，原 P2 标准化器也受对应正常片段影响。因此本次只能验证冻结 P9 配对残差方法向新源航次的迁移，不能称为整条学习流程完全未见航次的验证。详见 `source_independence_audit.csv`。

12 个正常目标来自三个源航次，不能按 12 个独立航次解释。正常 replay 均需对应的匹配参考；本实验不验证脱离参考的在线诊断，也不验证未见 mutation 类型。模块排名在完整 replay 后汇总，检测延迟不等同于定位完成延迟。

## 复现入口

已存在的封存文件禁止覆盖；`freeze_independent.py` 在第一次 replay 前运行一次即可。

```powershell
.venv/Scripts/python.exe scripts/p9/freeze_independent.py
wsl -d Ubuntu-20.04 -u root -- bash /mnt/d/UAV/scripts/p9/run_independent.sh
.venv/Scripts/python.exe scripts/p9/audit_stage1.py --manifest reports/p9/paired_residual/independent/reference/run_manifest.tsv --output reports/p9/paired_residual/independent/reference_cache --preserve-header-start --source-clock
.venv/Scripts/python.exe scripts/p9/audit_stage1.py --manifest reports/p9/paired_residual/independent/normal/run_manifest.tsv --output reports/p9/paired_residual/independent/normal_cache --preserve-header-start --source-clock
.venv/Scripts/python.exe scripts/p9/evaluate_independent.py --phase predict
.venv/Scripts/python.exe scripts/p9/evaluate_independent.py --phase score
.venv/Scripts/python.exe scripts/p9/audit_independent.py
.venv/Scripts/python.exe -m pytest tests/test_p9_independent.py tests/test_paired_replay.py tests/test_replay_detection.py tests/test_sitl_injection.py tests/test_baseline.py -q -p no:cacheprovider
```

长任务应后台执行并记录 PID/stdout/stderr。本次 replay 使用 `runner.pid`、`runner.stdout.log`、`runner.stderr.log`；每次 replay 的完整日志另存 `consoles/`。超时退出 124 仅在存在 `Replay done` 且产出 ULog 时可视作正常结束，另核查真实传感器支持与时钟恢复。

<!-- GENERATED RESULTS -->
## 最终结果

| 指标 | 开发集（原三折汇总） | 冻结主配置新航次 | 差值 |
|---|---:|---:|---:|
| Detection Recall | 10/12 (83.3%) | 12/12 (100.0%) | +16.7 个百分点 |
| 正常误报率 | 1/12 (8.3%) | 11/12 (91.7%) | +83.3 个百分点 |
| Top-1 | 4/12 (33.3%) | 6/12 (50.0%) | +16.7 个百分点 |
| Top-3 | 10/12 (83.3%) | 9/12 (75.0%) | -8.3 个百分点 |
| Top-5 | 10/12 (83.3%) | 9/12 (75.0%) | -8.3 个百分点 |
| MRR | 0.5833 | 0.6369 | +0.0536 |

开发集按源航次使用各自留一校准；新航次统一使用测试前选定的一组已有参数。因此差异同时包含航次迁移与校准部署口径差异，不能全归因于分布偏移。

检测延迟：成功检测 12/12，中位数 2.023 s，范围 0.419–54.819 s；0 次漏检单独保留。延迟基于 replay 日志时间，不含离线解析/推理耗时，也不是模块定位完成时延。

正常目标出现误报 11/12，涉及 3/3 个源航次；故障 onset 前报警 10/12。扣除同条件正常报警及 onset 前报警后，干净的故障独有检出为 1/12。

| Mutation | Detection | 正常误报 | Top-1 | Top-3 / Top-5 | MRR | 检出延迟中位数 / 范围（s） |
|---|---:|---:|---:|---:|---:|---|
| Commander 状态覆盖 | 3/3 | 3/3 | 3/3 | 3/3 / 3/3 | 1.0000 | 2.024 / 2.022–2.025 |
| EKF innovation bias | 3/3 | 3/3 | 3/3 | 3/3 / 3/3 | 1.0000 | 0.423 / 0.419–5.225 |
| INAV 高度冻结 | 3/3 | 3/3 | 0/3 | 0/3 / 0/3 | 0.0476 | 17.223 / 2.821–54.819 |
| Land detector 状态翻转 | 3/3 | 2/3 | 0/3 | 3/3 / 3/3 | 0.5000 | 1.218 / 0.424–1.226 |

## 逐次故障与误报

| 源航次 | Mutation | 检出 | GT 名次 | 延迟（s） | 连续残差最大值 / 阈值 | 注入生效检查 |
|---|---|---|---:|---:|---:|---|
| 2018-12-19__07_49_17 | Commander 状态覆盖 | 是 | 1 | 2.024 | 65.456 / 26.472 | 通过 |
| 2018-12-20__07_47_50 | Commander 状态覆盖 | 是 | 1 | 2.022 | 75.373 / 26.472 | 未通过，保留计分 |
| 2018-12-25__08_44_40 | Commander 状态覆盖 | 是 | 1 | 2.025 | 79.526 / 26.472 | 通过 |
| 2018-12-19__07_49_17 | EKF innovation bias | 是 | 1 | 0.423 | 738.084 / 26.472 | 通过 |
| 2018-12-20__07_47_50 | EKF innovation bias | 是 | 1 | 0.419 | 879.556 / 26.472 | 通过 |
| 2018-12-25__08_44_40 | EKF innovation bias | 是 | 1 | 5.225 | 226.737 / 26.472 | 通过 |
| 2018-12-19__07_49_17 | INAV 高度冻结 | 是 | 无有效名次 | 2.821 | 45.759 / 26.472 | 通过 |
| 2018-12-20__07_47_50 | INAV 高度冻结 | 是 | 无有效名次 | 54.819 | 52.319 / 26.472 | 通过 |
| 2018-12-25__08_44_40 | INAV 高度冻结 | 是 | 7 | 17.223 | 79.526 / 26.472 | 通过 |
| 2018-12-19__07_49_17 | Land detector 状态翻转 | 是 | 2 | 1.226 | 171.765 / 26.472 | 通过 |
| 2018-12-20__07_47_50 | Land detector 状态翻转 | 是 | 2 | 1.218 | 171.765 / 26.472 | 通过 |
| 2018-12-25__08_44_40 | Land detector 状态翻转 | 是 | 2 | 0.424 | 171.765 / 26.472 | 通过 |

正常误报逐项：
- 2018-12-19__07_49_17 / Commander 状态覆盖：首次 11.233 s，主要门控证据 `vehicle_attitude`，连续残差最大值 122.517。
- 2018-12-20__07_47_50 / Commander 状态覆盖：首次 89.616 s，主要门控证据 `vehicle_attitude`，连续残差最大值 44.351。
- 2018-12-25__08_44_40 / Commander 状态覆盖：首次 11.217 s，主要门控证据 `vehicle_attitude`，连续残差最大值 79.526。
- 2018-12-19__07_49_17 / EKF innovation bias：首次 11.218 s，主要门控证据 `estimator_status`，连续残差最大值 807.108。
- 2018-12-20__07_47_50 / EKF innovation bias：首次 12.818 s，主要门控证据 `estimator_status`，连续残差最大值 797.790。
- 2018-12-25__08_44_40 / EKF innovation bias：首次 11.220 s，主要门控证据 `vehicle_local_position`，连续残差最大值 157.974。
- 2018-12-19__07_49_17 / INAV 高度冻结：首次 11.230 s，主要门控证据 `vehicle_attitude`，连续残差最大值 122.138。
- 2018-12-20__07_47_50 / INAV 高度冻结：首次 16.820 s，主要门控证据 `vehicle_attitude`，连续残差最大值 51.222。
- 2018-12-25__08_44_40 / INAV 高度冻结：首次 11.217 s，主要门控证据 `sensor_combined`，连续残差最大值 48.051。
- 2018-12-19__07_49_17 / Land detector 状态翻转：首次 11.231 s，主要门控证据 `vehicle_attitude`，连续残差最大值 125.066。
- 2018-12-25__08_44_40 / Land detector 状态翻转：首次 11.216 s，主要门控证据 `vehicle_attitude`，连续残差最大值 79.526。

## 冻结参数敏感性（全部报告，不择优）

| 开发校准标识 | 主配置 | Recall | 正常误报 | Top-1 | Top-3 / Top-5 | MRR |
|---|---|---:|---:|---:|---:|---:|
| 2019-01-18__08_39_38 | 是 | 12/12 | 11/12 | 6/12 | 9/12 / 9/12 | 0.6369 |
| 2019-01-25__17_38_05 | 否 | 12/12 | 11/12 | 6/12 | 9/12 / 10/12 | 0.6675 |
| 2019-03-06__08_02_26 | 否 | 12/12 | 11/12 | 6/12 | 9/12 / 12/12 | 0.6750 |

## 完整性核验

- 36/36 次最终 replay 完成；原二进制、方法与参数哈希不变；时钟锚点最大偏差 0 μs。
- 既有注入效果标准通过 11/12；全部 12 次仍在主指标分母。
- 28 项关键测试通过。预测与计分分离，预测文件有哈希；正常与参考日志路径和内容均不同。
- 第二条源航次最初四次 baseline 遭遇基础设施中断：进程被终止、跨系统复制报 Bad address、本地日志损坏；保留在 `infrastructure_failure/`，在未读取检测成绩时更换临时工作目录重跑。第一条航次的 12 次有效运行直接复用。
- 原 P2 训练数据暴露已明确列出；本次不宣称全学习流程的航次级隔离。
