# 项目开发约束

## 当前任务

本项目研究目标是基于真实 PX4 多源遥测实现 **异常检测 → 子系统诊断 → 可解释证据** 的完整链路，拟定方法为 HS-AeroTS。

阶段状态：**P1–P10 已完成（2026-08-21）**。P1/P2 验收规模保持为 1,389 条日志、1,892,063 行、87 通道和 218,537 个窗口；P2 五种子 AUPRC 为 0.7522±0.0039，P3 四类诊断 Macro-F1 为 0.8980±0.0020。P8 已按多数固件提交建立 18 个 topic 到 54 个 PX4 模块的静态映射。P9 完成 3 条真实 ULog、4 个 PX4 源码 mutation 的 24 次 replay：onset-conditioned Top-1/3/5 为 0.250/0.333/0.333，MRR 0.3227、EXAM 0.3318；固定 P2 阈值检测召回为 0，必须作为端到端负结果报告。P10 五种子直接五分类 Macro-F1 为 0.6599±0.0029；14-window purged 敏感性下 Stage 1 AUPRC、Stage 2 Macro-F1、级联 Macro-F1 分别为 0.5936、0.7983、0.5444。

当前优先事项：

1. **结果维护与论文整合**：保持 P1–P7 配置、来源版本和负结果限制可追溯；新实验不得改变 P1–P4 的固定划分与主口径。
2. **P1–P4 产物维护**：不得手改原始数据或派生表；如解析、窗口、标签或解释协议发生变化，须由命令重新生成并复核各阶段基准规模与主指标。
3. **P9 结果维护**：保持 Ubuntu-20.04、固定 PX4 commit、无 Gazebo/ROS/QGroundControl/NuttX 的轻量 replay 协议；区分 onset-conditioned 定位指标与检测门控端到端指标，不得用前者掩盖 Stage 1 对 12 个 fault run 零检出的限制。

P4 的 External Position 类证据一致性接近按映射规模计算的随机基线，后续增强不得掩盖该限制；应优先检查映射覆盖和跨子系统间接效应。

P5 的 CATCH 结果是官方模型主体在 18 个 topic 聚合序列上的资源适配，GCAD 仅为无官方代码条件下的线性 Granger 消融，不得写成官方 GCAD 复现。P6 只报告跨数据集二元异常检测。P7 的 Uncategorized 标签没有时间范围，只允许航次级弱标签筛查，不得报告点级或 Event-F1。

## 必要约束

- 统一使用“运行时异常”“状态估计相关异常”和“子系统级诊断”等表述，不将 UAV-SEAD 标签称为 PX4 源代码 bug 或代码级故障定位。
- 数据划分必须以 flight log 为隔离单位，采用 chronological、purged 或 leave-log-out 方案；禁止将随机 window-level split 作为主实验结果。
- 原始数据只读保存；清洗、对齐、窗口和特征产物必须可由脚本与配置重新生成，不手工修改中间数据。
- 数据划分、通道列表、窗口参数、特征参数、随机种子和模型参数均需配置化并随实验结果记录。
- 类别不平衡时优先使用 class weight 或 balanced sampling；异常检测以 AUPRC 为主，子系统诊断以 Macro-F1、Balanced Accuracy 和 per-class Recall 为主，不单独用 Accuracy 下结论。
- Stage 1 与 Stage 2 必须共享明确的数据与标签协议；所有 baseline 使用相同划分和评测实现，避免比较口径不一致。
- 维护“统计特征 → telemetry channel → PX4 topic → subsystem”的显式映射；SHAP 聚合必须能追溯到原始信号，并用 Top-k Masking 和 Consistency@K 验证。
- `topic→module` 静态依赖只表示证据传播和软件模块嫌疑度，不等同于根因；只有具有已知注入模块的隔离 SITL run 可报告软件模块故障定位 Top-k/MRR/EXAM。
- 固定 chronological 主结果必须同时报告 P10 purged 敏感性；不得用固定划分的较高绝对指标掩盖严格隔离下的性能下降。
- 优先复现和最小可投稿版本，不在基线未稳定前引入复杂网络或无关功能。
- 新增代码应提供最小可运行入口、必要注释和对应测试；提交结果前至少完成数据泄漏检查、配置记录和关键指标复核。
