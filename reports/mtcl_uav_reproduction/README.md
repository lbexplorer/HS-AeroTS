# MTCL-UAV 正式复现准备

状态：2026-09-08，仅完成准备与接口验证，未执行正式训练或测试集评分。用户确认当前只有本机算力，本轮先完成复现准备。

## 文献和实现

- Hu et al., *Multiscale Transformers With Contrastive Learning for UAV Anomaly Detection*, IEEE TIM 74, 1–15 (2025), [DOI](https://doi.org/10.1109/TIM.2025.3571126)。
- 作者公开仓库：[WindchaserHG/MTCL-UAV](https://github.com/WindchaserHG/MTCL-UAV)，原 SteelHu 地址重定向到该仓库；固定 commit `9a9d4c90c8942023331c0d61ac813b87afb3243a`。模型源码未改动。
- LDC-P-VAE：Yang, Zhang, Wang and Miao, IEEE TIM 75, 3521111 (2026), [DOI](https://doi.org/10.1109/TIM.2026.3718566)。IEEE 向 Crossref 存入的书目信息已核实；本轮未取得可核验的官方实现或全文，因此只写已核实的研究方向和出版信息，不写其具体性能或“无代码”的绝对判断。

## 本文适配协议

固定 `configs/mtcl_uav_reproduction.yaml`。采用完整 87 通道、96 点输入，输出为同窗重建；二元标签完全复用 Stage 1 的窗口及 horizon 标签，不能把输出长度 96 误写为预测 horizon 96。官方三层、每层四专家、Top-2 路由、各 patch 尺度、16 维模型与前馈层、RevIN、平衡损失和 0.1 倍对比损失保留。

官方示例为 100 epochs；入口默认值 1 epoch 不是充分训练依据。准备配置最多 100 epochs、30 次未改善早停、Adam 0.001 和 OneCycleLR。现有显存限制将 batch 从示例 128 降为 8，必须披露该差异；不缩小通道、不抽样训练集，也不删减网络层数。

每个划分仅以其全部正常训练窗口拟合重建模型；模型选择用该划分正常验证窗口的重建加对比损失。归一化复用对应 Stage 1 的训练集 scaler（允许训练集异常参与已有 scaler，因此不能声称全流程仅使用健康数据）。验证集完整标签用于选择最大 F1 阈值，与 Stage 1 一致。最终测试只加载选定模型和阈值，窗口分数为跨时间及通道平均重建平方误差。报告 AUPRC、AUROC、验证阈值 F1、按日志隔离的 Event-F1；不使用调整后的点级预测，不把 test-best F1 作为正式指标。

官方默认流程与本文不兼容的部分：

1. `data_provider/data_loader.py` 的 ALFA 分支在 train+test 上拟合 scaler。
2. `exp/exp_anomaly_detection.py` 在 train+test 分数上计算百分位阈值。
3. 同一文件用 `adjustment(gt,pred)` 根据测试真值区间扩展报警。
4. 原训练入口每轮读取测试损失；本文训练阶段不读取测试样本，测试只在模型与阈值冻结后执行。

因此，目标是“官方模型在本文统一协议下的复现”，不是原论文数据集分数的逐字复刻。其正常重建训练与监督 LightGBM 的标签使用不同，应在比较表中说明。

## 已完成检查

- `input_audit.json`：三套划分计数、输入文件 SHA-256、航次重叠与窗口数值一致性。
- `smoke_check.json`：仅 4 个正常训练窗口的前向、损失、梯度与推理分数有限性检查；没有读取测试特征或输出 benchmark 分数。
- 本机：RTX 3060 Laptop 6GB、PyTorch 2.8.0+cu128。官方所列 PyTorch 1.10.1+cu111 未在此环境使用；数值一致性不能据此推定。
- 合成输入探测：batch=8 的稳定训练步约 2.006 s；143,329 个正常训练窗口约需 17,917 步，约 10 小时/epoch，尚未计入读取及验证开销。仅 2 步测量，实际耗时会变动。batch=16 出现显存压力和严重延迟，探测已停止，无训练产物。
- GPU 完整训练循环、长期收敛、多种子结果及严格协议性能尚未验证。

## 运行入口

在项目根目录执行；正式训练需要另行安排持续运行时间。以下训练命令本轮未运行。

```powershell
.venv/Scripts/python.exe scripts/mtcl_uav/run_reproduction.py audit
.venv/Scripts/python.exe scripts/mtcl_uav/run_reproduction.py smoke
.venv/Scripts/python.exe scripts/mtcl_uav/run_reproduction.py train --protocol chronological --seed 0
```

正式结果应覆盖预先声明的 seeds 0–4，并保留 chronological、purged 和 leave_log_out 对照。先做 chronological 的单种子运行与收敛诊断，不能据测试优劣决定是否完成或报告其他种子。长任务应后台启动并记录 PID 和日志。当前入口保留每 epoch 的 best/last checkpoint 和历史；为避免误覆盖，已存在训练目录会拒绝重启，尚未实现断点续训，因此正式长跑前还需补充并验证恢复功能。

内部计划将该方法设为主要 published baseline 的正式复现目标。按用户最新要求，当前论文仅在相关工作中介绍该方法，不呈现复现进度或待补结果说明，不填入性能表，不替换原方法分数。
