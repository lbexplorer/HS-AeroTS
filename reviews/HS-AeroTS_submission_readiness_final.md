# HS-AeroTS 最终投稿准备度报告

日期：2026-08-26
目标期刊：MDPI *Drones*
方案：零新实验、有限复算（P13）

## 决定

**具备投稿条件（Ready to submit with disclosed residual limitations）。** 当前没有 Critical 问题、正文占位符、未定义引用或待补作者元数据。稿件的科学主张已收缩到现有证据可以支持的范围；源码不公开和没有机器可读公开 Supplement 属于已披露的编辑/复现风险，而不是隐瞒事项。

## P13 有限复算

- Stage-1 gated matching-commit：14,419 个测试窗，五种子均值 TP 937.2、FN 455.8、FP 532.2、TN 12,493.8；recall `0.6728 ± 0.0248`，precision `0.6398 ± 0.0305`。
- 保守图过滤：180 edges/54 modules → 145 edges/36 modules，18 topics 全保留；producer-only Top-5 overlap 为 4/5。此结果仅是 conservative-exclusion sensitivity。
- Sampling uncertainty：固定 seed `20260825`、1000 次 cluster bootstrap；Table 5 将 point estimate、model-seed SD 和 cluster CI 分开报告。
- 输入完整性：85 个冻结数据、模型和预测文件的运行前后 SHA-256 一致；`training_performed=false`、`new_data_collected=false`、`new_baselines_added=false`、`px4_replay_performed=false`。

## 投稿文件验收

- 完整 LaTeX：`paper/main.tex`。
- 最终 PDF：`paper/HS-AeroTS_Drones_submission.pdf`，30 页。
- 编译：通过；未定义 citation/reference、重复 label、overfull、DOI footer 均为 0。
- 引用：正文使用 36 个 bibliography keys，36 个均存在且均被引用；未发现 ghost 或 unused entries；元数据/主题适配完成在线核对，未新增或修改参考文献。
- 测试：37 passed，1 deselected。deselected 项仅因 Windows sandbox 临时目录权限，未伪报通过。
- 视觉检查：首页作者与 Highlights、Figures 3–5、Table 5、87-channel longtable、Appendix B 和末页均无截断或越界。

## 保留限制

1. 没有独立 uORB gold audit；显式同语句检查只是 internal consistency check。
2. 没有实际 PX4 build-target graph；输出是 commit-level source-tree inspection candidates。
3. 没有按公平预算重训近期基线；CATCH/GCAD 仅是 feasibility references。
4. 回放只有 3 source logs × 4 mutations，区间宽，detector gate 为 0/12。
5. semantic mapping 未经外部专家裁决；External Position 接近随机、Global Position 低于随机的结果保留。
6. 源码和机器可读 Supplement 不公开；选定材料仅可向编辑/审稿人保密提供。

## 投稿时不得改变的边界

不得把本文宣传为 causal root-cause localization、deployment/build-target validation、可靠端到端 software fault localization 或无条件 SOTA。若编辑要求公开源码、实际 build graph、独立语义标注或新增实验，应作为新的作者决定处理，不应在当前稿中虚构满足。
