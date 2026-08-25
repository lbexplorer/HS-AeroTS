# HS-AeroTS 未解决问题（第二轮后）

前一轮 Critical 的跨固件模块汇总已通过 matching-commit-only 重算关闭。以下项目不再阻断当前受限主张的投稿，但必须保留在正文边界或由作者在提交前处理。

## Major scientific boundaries

1. **semantic mapping 未经外部专家裁决**
   Document-derived 映射独立于 SHAP，但仍由作者规则定义。论文已把 Consistency@K 改为映射敏感性；External Position 接近随机、Global Position 低于随机的结果必须保留。若日后恢复“语义有效性”主张，仍需独立标注者和一致性统计。

2. **回放样本仍小**
   只有 3 个源日志 × 4 种变异。双向聚类 bootstrap 已处理当前交叉依赖，但区间很宽，且 detector gate 仍为 0/12。不得把 onset-conditioned 排名表述为端到端定位。

3. **uORB 审计范围有限**
   244 个显式无歧义 occurrence 的审计已完成，但宏生成、间接保存、模板展开和运行时创建的关系未被量化。模块排序仍是静态检查优先级。

4. **近期基线预算边界**
   CATCH 已使用官方模型核心、87 通道和相同固定划分，但仅有 4,096 个正常训练窗和两轮训练；GCAD 仍是线性非官方消融。不得宣称无条件 SOTA 优势。

5. **源码不公开的编辑风险**
   Data Availability 已如实声明源码不公开，并仅承诺可向编辑/审稿人保密提供配置、划分清单与派生报告。若期刊或审稿人要求公开代码，作者需决定是否接受该要求；不得填写虚假仓库地址。

## Editorial / Author action before submission

1. `[AUTHOR ACTION REQUIRED]`：填写作者姓名、单位、通信邮箱。
2. `[AUTHOR ACTION REQUIRED]`：填写 CRediT author contributions。
3. `[AUTHOR ACTION REQUIRED]`：填写 Funding；无资助时使用期刊规范的无资助声明。
4. `[AUTHOR ACTION REQUIRED]`：填写 Acknowledgments；无致谢时使用期刊规范声明。
5. 根据最终作者人数调整 MDPI class 的 `oneauthor` 选项。

## 当前允许的最强结论

HS-AeroTS 在声明的数据划分和计算预算下提供可追踪的 runtime anomaly detection、fault-domain diagnosis、SHAP evidence 和 matching-commit architecture-aware inspection evidence。它不证明跨固件总体模块排名、因果根因定位或可靠的 detector-gated software fault localization。
