# P9 真实 ULog replay 与源码 mutation 结果

## 实验范围

- 固定 PX4 提交：`82aa24adfca29321cfd1209e287eab6c2b16780e`。
- 运行环境：WSL2 Ubuntu-20.04，仅 PX4 POSIX/SITL 编译依赖；未安装或运行 Gazebo、ROS、QGroundControl 和 NuttX 工具链。
- 输入：3 条真实 UAV-SEAD ULog。
- 注入：Commander 导航状态覆盖、EKF2 innovation 偏置、INAV 高度状态冻结、Land Detector `landed` stuck-at，共 4 个源码 mutation。
- 规模：24 次 replay（3 ULog × 4 mutation × baseline/fault），24 个输出 ULog 全部存在，12/12 个 mutation/log 效应检查通过，离线解析错误为 0。

## 定位结果

以下 Top-k、MRR 和 EXAM 是使用已知 30 秒注入时刻的 **onset-conditioned** 结果。模块分数由 fault-minus-matched-baseline 的绝对预测类别 TreeSHAP 经 P8 双向 uORB 边传播得到，共排序 54 个模块。

| Mutation | Ground-truth rank（3 logs） | Top-1 | Top-3 | Top-5 | MRR | Mean EXAM |
|---|---:|---:|---:|---:|---:|---:|
| Commander nav-state override | 43, 1, 2 | 0.333 | 0.667 | 0.667 | 0.5078 | 0.2840 |
| EKF2 innovation bias | 1, 27, 1 | 0.667 | 0.667 | 0.667 | 0.6790 | 0.1790 |
| INAV local-z freeze | 16, 11, 19 | 0 | 0 | 0 | 0.0687 | 0.2840 |
| Land Detector landed stuck-at | 38, 37, 19 | 0 | 0 | 0 | 0.0353 | 0.5802 |
| **Overall** | — | **0.250** | **0.333** | **0.333** | **0.3227** | **0.3318** |

Top-1/3/5 定位延迟中位数分别为 0.4、4.8 和 1.2 秒，对应有可观测命中的 run 数分别为 3、4 和 4。不同 K 的中位数基于不同成功子集，因此不要求单调。

## 必须保留的负结果

P2 Stage 1 固定阈值 `0.3374776883` 对 12 个 fault run 的检测召回为 **0**。因此检测门控下 Top-1/3/5、MRR 均为 0，检测延迟和门控定位延迟不可定义。论文中必须将这一结果表述为域移位下的端到端失败；不得把 onset-conditioned 指标描述为完整系统性能。

INAV 与 Land Detector 在 onset-conditioned 排名中也均未进入 Top-5，说明 P8 静态 topic→module 传播对这些局部状态故障的根因分辨力有限。该结果支持“模块嫌疑排序而非确定根因”的边界表述。

## 旧版 ULog replay 兼容说明

三条源 ULog 均缺少该 PX4 提交专用 EKF replay 所需的 `ekf2_timestamps`。EKF2 因此使用 generic replay，并在 baseline/fault 两个条件中运行同一发布适配插桩二进制；只有环境变量 `HS_P9_EKF_FAULT` 的激活值不同。baseline 在完整时间轴发布 0，fault 在 30 秒后发布 +20 innovation 偏置。该适配确保两条件的执行路径和持续时间匹配，但属于旧日志兼容层，论文应明确披露。

## 主要产物

- `run_manifest.tsv`：24 次运行、输入、模式、输出和退出码。
- `mutation_manifest.csv` 与 `mutation_patches/`：源码位置、变异类型和可复现补丁。
- `injection_effect_validation.csv`：12 个 mutation/log 效应检查。
- `localization_metrics.json`：总体 onset-conditioned 与检测门控指标。
- `localization_by_mutation.csv`：分 mutation 排名和指标。
- `replay_run_metrics.csv`：逐 run 排名、检测状态与延迟。
- `module_rankings.csv`：逐 run 的 54 模块完整排序。
- `completion_summary.json`：完成状态、限制与产物索引。

复现命令见项目根目录 `README.md`。新实验不得改变 P1–P4 的固定划分、模型或主评价口径。
