# HS-AeroTS 实验清单（第二轮后）

## 本轮已完成

| ID | 工作 | 输出 | 状态 |
|---|---|---|---|
| E1 | matching-commit-only uORB/module 重算 | 1,393 个匹配异常窗、模块排名、Figure 4(d) | 完成 |
| E3 | 显式 uORB declaration/role 审计 | 244 occurrences；role agreement/explicit-edge recall | 完成（限定范围） |
| E4 | SHAP 随机遮蔽配对 CI 与 donor 敏感性 | 五种子、20 随机重复、1,000 flight-log bootstraps | 完成 |
| E5 | propagation 与 degree sensitivity | producer/consumer/bidirectional/topic/random；degree-normalized | 完成 |
| E6a | 现有 replay 依赖结构分析 | 5,000 次双向聚类 bootstrap；per-log/per-mutation | 完成 |
| E7 | 近期 CATCH 参考 | 官方模型核心、87 通道、相同固定划分、三种子 | 完成（预算受限） |
| E8 | purged 多种子与方法配对统计 | Stage 1/2/Cascade/Direct 五种子；fixed/purged 配对 CI | 完成 |

## 当前投稿不要求补做，但会进一步增强的实验

1. **独立专家 semantic mapping（高价值）**
   至少两名不查看 SHAP 的 PX4/UAV 状态估计专家独立标注 87 个通道，报告 rubric、冲突裁决和 kappa。只有完成后才能把 Consistency@K 从“作者映射敏感性”提升为外部语义一致性证据。

2. **扩大 replay benchmark（高价值）**
   增加独立源日志、PX4 版本、模块和故障机制，并建立不重叠的 development/test mutation split。继续保留 detector-gated 0 分规则。

3. **宏与运行时 uORB 审计**
   覆盖宏生成、模板、句柄跨函数保存、运行时订阅和实际 topic activity；与当前 explicit-only 图比较遗漏率和排序变化。

4. **更充分的近期基线预算**
   若希望提出竞争性 SOTA 主张，应扩大 CATCH 训练样本/epoch 并加入至少一个完整官方 GCAD 类实现，预注册调参预算。当前论文不提出该主张，因此不是本轮投稿阻断项。

5. **replay matched-baseline/onset-window 敏感性**
   比较使用/不使用 matched-baseline subtraction、不同 onset 与背景窗。该项可增强条件排名解释，但不会改变 detector gate 0/12 的端到端边界。

## 不在本轮范围

- 公共源代码仓库、公开复现包或 DOI 发布：用户明确不计划公开源码。
- 动态 uORB/执行追踪扩展：作为后续研究方向。
- 任何未经实际运行的实验数字、结果或参考文献：禁止写入论文。
