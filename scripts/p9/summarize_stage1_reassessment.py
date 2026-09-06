"""Produce the Chinese reassessment report from saved, unmodified measurements."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/p9/stage1_reassessment'
NATIVE=OUT/'native_replay'

def table(frame):
    # Avoid adding a tabulate dependency to the experiment environment.
    rows=[list(frame.columns)]+frame.fillna('—').astype(str).values.tolist()
    return '\n'.join(['| '+' | '.join(rows[0])+' |','| '+' | '.join(['---']*len(rows[0]))+' |']+
                     ['| '+' | '.join(r)+' |' for r in rows[1:]])

def main():
    summaries=pd.read_csv(NATIVE/'reevaluation_summary.csv')
    runs=pd.read_csv(NATIVE/'reevaluation_by_run.csv')
    f=runs[(runs['mode']=='fixed_fresh')&(runs.condition=='fault')].copy()
    old=pd.read_csv(ROOT/'reports/p9/replay_run_metrics.csv').set_index('run_id')
    pub=pd.read_csv(NATIVE/'publisher_only/reevaluation_by_run.csv')
    pub=pub[(pub['mode']=='fixed_fresh')&(pub.condition=='fault')].set_index('run_id')
    effects=pd.read_csv(NATIVE/'injection_effect_validation.csv')
    passes={f'{r.mutation_id}__{r.log_id}__fault':r.passed for r in effects.itertuples()}
    f['legacy_effect_check']=f.run_id.map(passes)
    coverage=pd.read_csv(NATIVE/'topic_time_coverage.csv')
    last=coverage[coverage.topic=='sensor_combined'].set_index('run_id').last_s
    freshmax={}
    for r in f.run_id:
        d=np.load(NATIVE/'cache'/f'{r}.npz')
        freshmax[r]=float(d['scores'][d['times']<=last[r]].max())
    f['fresh_score_max']=f.run_id.map(freshmax)
    f.to_csv(NATIVE/'primary_fault_results.csv',index=False)
    keep=f[f.legacy_effect_check]
    sensitivity={'protocol':'fixed_fresh; original effect-check pass subset; sensitivity only',
        'runs':len(keep),'detector_recall':float(keep.detected.mean()),
        **{k:float(keep[k].mean()) for k in ['top1','top3','top5','mrr']}}
    (NATIVE/'effect_valid_subset_sensitivity.json').write_text(json.dumps(sensitivity,indent=2))
    names={'commander_nav_state_override':'Commander','ekf2_innovation_bias':'EKF2',
           'inav_local_z_freeze':'INAV','land_detector_state_inversion':'Land Detector'}
    def rank(value): return str(int(value)) if pd.notna(value) else '不可用'
    detail=[]
    for r in f.itertuples():
        detail.append({'mutation':names[r.mutation_id],'源日志':r.source_log,
            '旧门控排名':'未检出','新门控排名':rank(r.ground_truth_rank),
            '检测': '是' if r.detected else '否','有效窗最高分':f'{r.fresh_score_max:.4f}',
            'publisher-only排名':rank(pub.loc[r.run_id,'ground_truth_rank']),
            '原效应检查':'通过' if r.legacy_effect_check else '未通过'})
    comparisons=[]
    labels={'fixed_all':'本地输入，保留尾段（不推荐）','fixed_fresh':'本地输入 + 有效时间覆盖（主结果）',
            'calibrated_fresh':'正常 baseline 校准 + 连续 3 窗（消融）'}
    comparisons.append({'方案':'历史 P9','检测召回':'0/12','Top-1':'0/12','Top-3':'0/12','Top-5':'0/12','MRR':'0.0000','baseline 报警':'0/12'})
    for r in summaries.itertuples():
        comparisons.append({'方案':labels[r.mode],'检测召回':f'{r.detected_runs}/12',
            **{name:f'{round(getattr(r,key)*12)}/12' for name,key in [('Top-1','top1'),('Top-3','top3'),('Top-5','top5')]},
            'MRR':f'{r.mrr:.4f}','baseline 报警':f'{r.baseline_false_alarm_runs}/12'})
    by=f.groupby('mutation_id')[['detected','top1','top3','top5','mrr']].mean().reset_index()
    by['mutation_id']=by.mutation_id.map(names)
    for col in ['detected','top1','top3','top5','mrr']:by[col]=by[col].map(lambda x:f'{x:.4f}')
    report=f'''# P9 Stage 1 与端到端定位专项复核（2026-09-06）

## Material Passport

- 模式：实验执行、实现审计与描述性复评；本地完成，无外部数据上传。
- 状态：24/24 新 replay 完整结束，输入逐字节一致，推理与计分已完成；原注入效应判据为 11/12 通过。
- 范围：固定 PX4 commit、原 4 个 mutation、原 3 条 Normal 源航次、原 P2/P3 seed0 模型、原 P8 映射。P1–P8 未重跑，P1–P4 数据、划分、标准化、模型未修改。
- 证据：本目录 CSV/JSON、原始 ULog、源代码、replay 控制台和 SHA-256；所有数字均来自执行产物。

## 结论

0/12 的主要根因是 **旧 replay 没有按实验预期完整回放输入**，其影响又被离线填充掩盖。将字节一致的输入从 Windows 挂载盘暂存到 WSL 本地、继续复用原二进制，即可完成 replay。再禁止在基础传感器停止更新后的尾段做检测/定位，主结果为 **检测 10/12，Top-1/3/5 = 2/12、5/12、5/12，MRR = 0.3259**。

**当前仍不足以支撑可靠端到端故障诊断结论。** 同一规则对正常 baseline 也报警 10/12；所有被检出的 fault 均有对应 baseline 报警，新增“仅 fault 报警且无注入前报警”的配对数为 0。一个 Commander 条件没有通过原效应排他性判据。现有证据支持“恢复了完整 replay 上的检测与候选模块排序计算”，不能证明检测到了 mutation 本身。

## 根因逐项检查

1. **Replay 执行与分布偏移（主要原因）**：原 24 条日志的 `sensor_combined` 最后更新时间约 9.9–19.4 秒，而注入发生在 30 秒后；原控制台没有 `Replay done`，均为强制终止码 137。模块按运行时钟继续发布到约 85–115 秒，普通遥测却仅回放了开头部分。PX4 replay 的逐消息扫描/seek 经过 `/mnt/d` 时出现严重吞吐不足；本地输入的受控复现支持这一解释，但没有做独立 I/O profiler 测量。单条相同 baseline 从约 10.9 秒输入覆盖变为完整 68.8 秒，并在 68.816 秒报告 Replay done。新 24/24 均完整结束，基础传感器覆盖完整源航次，退出码 124 表示 replay 完成后由既定 timeout 结束驻留进程，并非回放未完成。
2. **预处理（掩盖执行问题）**：P2/P9 共用 `np.interp` 的端点延拓，原日志停止更新的通道被填充到运行末尾，产生大量常量和零差分描述符；这些不是新采集的遥测。18 topics 均存在，不能仅用“无缺失 topic/无解析错误”认定数据有效。新 P9 门控只接受 `sensor_combined` 仍有时间覆盖的窗口，匹配 baseline 也必须有覆盖。历史数据在该检查下有 0/12 条 fault 具备注入后有效窗口；不通过插值补造这一段。
3. **特征与标准化（排除错配）**：仍为 10 Hz、96 点窗口、8 点步长、12 点标签 horizon、87 通道、每通道 18 描述符。三个源日志重新提取的特征与 P2 train/validation/test 缓存逐项完全相同；无二次标准化、无特征排序变化，标准差为正、特征均有限。
4. **模型加载（排除错误模型/错误概率列）**：Stage 1 类别 `[0,1]`，1,566 个输入，best iteration 606；Stage 2 输入维度一致。原验证集 32,138 窗分数复现误差为 `1.11e-16`，模型/标准化/特征表哈希已记录。
5. **阈值**：旧 fault 的全局最高分只有 0.041404，远低于固定阈值 0.3374776883，因此均不触发。完整回放后，正常状态也会产生高分。仅降低旧阈值不能恢复缺失输入，也无法验证特异性。本次额外做正常数据校准：每次严格排除当前源航次及其所有 mutation，使用另外两条源航次的 8 条 baseline 的有效窗 99% 分位数；得到约 0.648828 或 0.960360，未读取 fault 标签/排名来拟合或选择阈值。
6. **时间聚合与计分**：主结果保持原单窗阈值，并增加有效覆盖限制；消融要求连续 3 个超阈值窗，第 3 窗才触发，不回填前两窗。所有排名按检测器实际门控的窗口计算，不使用 30 秒 onset 截取证据。onset 仅用于最后统计检测召回和延迟；真实模块仅在排名固定后查表计分。并列采用最差名次，零证据视为不可用，避免字母排序制造命中。窗口结束时间沿用 P9 的右端点口径；预处理仍是离线线性插值，因此不将这些延迟宣称为已验证在线实时性能。
7. **模型/定位能力**：训练标签是遥测异常类别，并非这四个源码 mutation。`landed` 的训练增益占比约为 Stage 1 0.0069%、Stage 2 0.0063%；这支持其在既有模型中作用很弱的解释，并非单凭 gain 就证明因果失效。双向 topic→module 传播还会把间接订阅者列为高嫌疑模块。

## 定量结果

以下均以原 12 个 fault 为分母；失败不删除。Top-k/MRR 均为检测门控指标，不是 onset-conditioned 上限。

{table(pd.DataFrame(comparisons))}

保留失效尾段会得到表面更高的 11/12 召回，因此不能据此报喜。正常校准+持续门控将 baseline 报警从 10/12 降到 4/12，但召回降到 3/12，未形成可用的召回/误报折中；没有继续用这 12 个 fault 调阈值。各方案 fault 的注入前报警均为 0，但注入后的正常飞行变化仍触发大量报警。

### 主结果按 mutation

{table(by)}

### 逐 run 变化

{table(pd.DataFrame(detail))}

- Commander：三条均恢复检测，双向映射排名均为 2；其中第一条 baseline 自然进入 AUTO_LAND，原效应检查要求 baseline 目标状态占比小于 10%，实测 30%，fault 为 100%。保留未通过状态，不降低门槛。其余两条该检查通过。
- EKF2：第一、第三条恢复检出且排名 1；第二条在有效窗口的分数未越过固定阈值，仍未检测。三条创新偏置效应均通过原检查。
- INAV：第一、第三条被检测，但排名 12、9，仍未进 Top-5；第二条只在无输入更新的尾段有报警，去掉尾段后不再算检出。三条高度冻结效应均通过检查，说明“故障注入存在”不等于现有分类器对它敏感。
- Land Detector：三条被检测，但双向排名 20、6、不可用；第三条真实模块没有正的差分 SHAP 证据。正常 baseline 同样报警，且该状态位的模型作用极弱，因此不能称为准确定位。

### 既有 publisher-only 映射消融

复用相同缓存特征和 Stage 2 TreeSHAP，只把 P8 边筛到 publisher，仍保留全部 54 个候选模块，没有指定真实模块或目标 topic。有效窗口下 Top-1/3/5 = **3/12、4/12、5/12**，MRR = **0.3225**；检测仍为 10/12。Commander 前两条升至 1，INAV 第三条升至 5，但 Commander 第三条退到 37，Land Detector 三条均无正证据。因此它只是不同错误之间的折中，未替换原双向主结果；不能逐 mutation 选表现更好的映射。若保留无输入更新尾段，publisher-only 会出现更漂亮的 6/12 Top-1，正说明时间有效性限制必须保留。

### 效应有效子集敏感性

原效应检查 11/12 通过。只在附加敏感性中去掉上述未通过的 Commander 条件：检测 **9/11**，Top-1/3/5 = **2/11、4/11、4/11**，MRR = **{sensitivity['mrr']:.4f}**。主表仍保留全部 12 条，阈值与预测不因该筛选重新拟合。不可把这次重跑描述为“12/12 效应检查全部通过”。

## 实验有效性与结论边界

- 输入逐字节一致，固定二进制 SHA-256 可追溯；没有新造遥测、替换故障状态、改注入强度或改 ground truth。
- baseline/fault 均使用本地暂存输入和相同执行规则。EKF 仍保留原有旧 ULog 发布适配器的限制，并非完整 closed-loop SITL。
- 三条源航次原本均标记 Normal，并已参与 P2 的 chronological 训练/验证/测试切片。正常校准做到 source-log 排除，**不意味着基础模型从未见过这些源航次**。
- 本次为原 P9 的开发性修复与复评，不是新独立测试集；12 个 run 来自仅 3 条源航次，不能当成 12 个独立航次做显著性或泛化声明。
- 原历史 0/12 和原报告完整保留。应把“纯粹域移位导致端到端失败”的旧解释修订为“回放吞吐/时间覆盖缺陷造成严重伪冻结分布，修复后仍有高误报与局部模块分辨不足”。
- 当前可支撑：完整 controlled replay 上可计算检测门控的模块嫌疑排序，部分 Commander/EKF 条件有较好的候选排名。当前不可支撑：具有可靠特异性的 mutation 检测、稳健端到端根因诊断或广泛真实故障泛化。

## 修改、复现与检查

最有效的修改是 `scripts/p9/rerun_native_inputs.sh` 的输入暂存位置调整：复用旧二进制和原输入，不需重跑 P1–P8。`src/hs_aerots/replay_detection.py` 实现真值隔离的门控、正常校准、时间匹配后的证据聚合及零证据处理。所有审计和评价产物由脚本生成。`validate_injection_effects.py` 仅增加可选输入/输出路径，原判据完全不变。

```powershell
# 已完成的 replay 可复用；脚本 all 会跳过已有完成行，不覆盖历史 P9。
wsl --distribution Ubuntu-20.04 --user root -- bash /mnt/d/UAV/scripts/p9/rerun_native_inputs.sh all
.venv/Scripts/python.exe scripts/p9/audit_stage1.py --manifest reports/p9/stage1_reassessment/native_replay/run_manifest.tsv --output reports/p9/stage1_reassessment/native_replay
.venv/Scripts/python.exe scripts/p9/evaluate_stage1_reassessment.py --audit reports/p9/stage1_reassessment/native_replay --manifest reports/p9/stage1_reassessment/native_replay/run_manifest.tsv
.venv/Scripts/python.exe scripts/p9/verify_native_replay.py
.venv/Scripts/python.exe scripts/p9/validate_injection_effects.py --log-root reports/p9/stage1_reassessment/native_replay/logs --output reports/p9/stage1_reassessment/native_replay/injection_effect_validation.csv
# 上一条应返回未通过：Commander 第一条的 baseline 目标状态占比 30%，不隐瞒该检查。
.venv/Scripts/python.exe scripts/p9/cache_topic_evidence.py
.venv/Scripts/python.exe scripts/p9/evaluate_stage1_reassessment.py --audit reports/p9/stage1_reassessment/native_replay --manifest reports/p9/stage1_reassessment/native_replay/run_manifest.tsv --mapping publisher
.venv/Scripts/python.exe scripts/p9/audit_source_parity.py
.venv/Scripts/python.exe scripts/p9/summarize_stage1_reassessment.py
.venv/Scripts/python.exe -m pytest tests/test_replay_detection.py tests/test_sitl_injection.py tests/test_baseline.py -q -p no:cacheprovider
```

关键检查：模型分数复现、源特征完全一致、输入哈希一致、24/24 回放完成/传感器时间覆盖通过、原效应判据 11/12 通过、门控因果性/零证据/形状校验与原 P9/P2 相关测试。
'''
    (OUT/'README.md').write_text(report,encoding='utf-8')
    print('Wrote',OUT/'README.md')

if __name__=='__main__':main()
