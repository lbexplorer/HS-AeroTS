# HS-AeroTS 未解决问题（P13 投稿稿后）

P13 在零新实验条件下完成 Stage-1 gated、保守图过滤和 flight-level sampling uncertainty 三项有限复算。当前没有 Critical 问题，也没有正文占位符。以下限制不阻断以现有受限主张投稿，但必须保留在正文与投稿材料中。

## Major scientific boundaries

1. **semantic mapping 未经外部专家裁决**
   Document-derived 映射独立于 SHAP，但仍由作者规则定义。论文已把 Consistency@K 改为映射敏感性；External Position 接近随机、Global Position 低于随机的结果必须保留。若日后恢复“语义有效性”主张，仍需独立标注者和一致性统计。

2. **回放样本仍小**
   只有 3 个源日志 × 4 种变异。双向聚类 bootstrap 已处理当前交叉依赖，但区间很宽，且 detector gate 仍为 0/12。不得把 onset-conditioned 排名表述为端到端定位。

3. **uORB 缺少独立 gold audit**
   现有 `1.000` 结果仅是对明确同语句 occurrence 的 internal consistency check，不能作为独立解析器验证。宏生成、间接保存、模板展开和运行时创建的关系未被量化。

4. **没有实际 PX4 build-target graph**
   P13 的保守路径过滤把 180 条边/54 个模块缩减为 145 条边/36 个模块并保留全部 18 topics，但仍未解析 CMake、board manifest、条件编译、链接和运行时激活。输出只能称为 commit-level source-tree inspection candidates。

5. **近期基线预算边界**
   CATCH 已使用官方模型核心、87 通道和相同固定划分，但仅有 4,096 个正常训练窗和两轮训练；GCAD 仍是线性非官方消融。不得宣称无条件 SOTA 优势。

6. **源码与机器可读 Supplement 不公开的编辑风险**
   Data Availability 已如实声明源码不公开，并仅承诺可向编辑/审稿人保密提供配置、划分清单与派生报告。若期刊或审稿人要求公开代码，作者需决定是否接受该要求；不得填写虚假仓库地址。

## Editorial status before submission

1. 作者、单位、共同第一作者、通讯作者和邮箱已填写。
2. CRediT 已按作者确认的工作分工写入，不留占位符。
3. Funding 为无外部资助；IRB 和 Informed Consent 为 Not applicable；Conflicts of Interest 为无冲突。
4. Acknowledgments 无人员致谢，并披露 Codex 用于复算代码、统计解释和稿件修订；作者审核并承担全部责任。
5. Data Availability 如实声明第三方数据来源、源码不公开以及可向编辑/审稿人保密提供的材料范围。

## 当前允许的最强结论

HS-AeroTS 在声明的数据划分和计算预算下提供可追踪的 runtime anomaly detection、conditional fault-domain diagnosis、SHAP evidence 和 commit-level source-tree inspection evidence。它不证明跨固件总体模块排名、实际 build-target 模块图、因果根因定位或可靠的 detector-gated software fault localization。
