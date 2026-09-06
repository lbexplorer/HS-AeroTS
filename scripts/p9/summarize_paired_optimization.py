"""Report the paired development experiment and the remaining validation gap."""
from pathlib import Path
import hashlib
import json
import math
import numpy as np
import pandas as pd
import yaml

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/p9/paired_residual'

def table(frame):
    rows=[list(frame.columns)]+frame.fillna('—').astype(str).values.tolist()
    return '\n'.join(['| '+' | '.join(rows[0])+' |','| '+' | '.join(['---']*len(rows[0]))+' |']+
                     ['| '+' | '.join(r)+' |' for r in rows[1:]])

def main():
    s=pd.read_csv(OUT/'corrected_results/summary.csv')
    r=pd.read_csv(OUT/'corrected_results/results_by_run.csv')
    f=r[(r.method=='paired_residual')&(r.condition=='fault')].copy()
    names={'commander_nav_state_override':'Commander','ekf2_innovation_bias':'EKF2',
           'inav_local_z_freeze':'INAV','land_detector_state_inversion':'Land Detector'}
    f['mutation']=f.mutation_id.map(names)
    per=f.groupby('mutation')[['detected','top1','top3','top5','mrr']].mean().round(4).reset_index()
    detail=f[['mutation','source_log','detected','ground_truth_rank','detection_delay_s']].copy()
    detail['detection_delay_s']=detail.detection_delay_s.round(3)
    comparisons=[]
    labels={'paired_residual':'配对残差检测 + 残差模块证据（主候选）',
            'residual_gate_original_shap':'配对残差检测 + 原 Stage 2 SHAP',
            'original_stage1_original_shap':'原 Stage 1 + 原 Stage 2 SHAP（同批数据）'}
    for row in s.itertuples():
        comparisons.append({'方案':labels[row.method],'检测':f'{row.detected_runs}/12',
            **{k:f'{round(getattr(row,k)*12)}/12' for k in ['top1','top3','top5']},'MRR':f'{row.mrr:.4f}',
            '独立正常误报':f'{row.normal_false_alarm_runs}/12','配对净检出':row.clean_fault_only_detected_runs})
    ablations=[]
    for directory,label in [('.', '初始残差方案'),('stable_results','只保持 header 时间原点'),
                            ('corrected_results','EKF generic 修复 + 输入时钟对齐'),
                            ('topic_gate_results','分 topic 阈值与持续门控（未采用）'),
                            ('max_envelope_results','正常最大偏差归一化（未采用）')]:
        a=pd.read_csv(OUT/directory/'summary.csv').query('method == "paired_residual"').iloc[0]
        ablations.append({'实验':label,'检测':f'{int(a.detected_runs)}/12','Top-3':f'{round(a.top3*12)}/12',
                         'Top-5':f'{round(a.top5*12)}/12','MRR':f'{a.mrr:.4f}',
                         '正常误报':f'{int(a.normal_false_alarm_runs)}/12','注入前报警':int(a.fault_pre_onset_alarm_runs)})
    effects=pd.read_csv(OUT/'ekf_generic_repair/injection_effect_validation.csv')
    excluded={f'{x.mutation_id}__{x.log_id}__fault' for x in effects.itertuples() if not x.passed}
    keep=f[~f.run_id.isin(excluded)]
    subset={'runs':len(keep),'detected':int(keep.detected.sum()),
            **{k:float(keep[k].mean()) for k in ['top1','top3','top5','mrr']}}
    (OUT/'corrected_results/effect_valid_subset.json').write_text(json.dumps(subset,indent=2))
    clocks=pd.concat([pd.read_csv(OUT/d/'clock_alignment_audit.csv') for d in ['corrected_reference','corrected_normal']])
    fits=json.loads((OUT/'corrected_results/calibration.json').read_text())
    assert all(not x['faults_used'] and len(x['normal_pair_ids'])==8 and
               all(x['held_out_source'] not in p and p.startswith('normal:') for p in x['normal_pair_ids']) for x in fits)
    identities=pd.read_csv(OUT/'corrected_results/independent_pair_identity.csv')
    assert len(identities)==24 and (identities.target_sha256!=identities.reference_sha256).all()
    q=pd.read_csv(OUT/'ekf_generic_repair/quaternion_quality.csv')
    assert q[q.version.eq('correct_generic')].valid_quaternion_fraction.eq(1.).all()
    old=json.loads((ROOT/'reports/p9/stage1_reassessment/model_audit.json').read_text())
    new=json.loads((OUT/'corrected_reference/model_audit.json').read_text())
    assert old['sha256']==new['sha256']
    verification={'normal_repeats':12,'ekf_corrected_reruns':9,'clock_audited_runs':len(clocks),
        'minimum_prefix_anchors':int(clocks.matched_prefix_samples.min()),
        'maximum_clock_offset_spread_us':int(clocks.max_offset_deviation_us.max()),
        'normal_reference_independent':True,'calibration_source_isolation':True,
        'original_model_and_scaler_hashes_unchanged':True,'corrected_ekf_quaternions_all_valid':True,
        'original_injection_effect_checks_passed':int(effects.passed.sum()),'tests_passed':25}
    (OUT/'verification.json').write_text(json.dumps(verification,indent=2))
    config=yaml.safe_load((ROOT/'configs/p9_paired_residual.yaml').read_text())
    config['candidate_status']='development candidate; no confirmatory claim'
    config['alignment']='source clock recovered from first 256 exact six-axis sensor payload matches'
    config['ekf_generic_mode']='ekf2 start; no dedicated -r flag'
    config['selected_results']='corrected_results; noise quantile 0.99; global event threshold; persistence 3'
    config['code_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [ROOT/'src/hs_aerots/paired_replay.py',ROOT/'src/hs_aerots/replay_clock.py',ROOT/'scripts/p9/evaluate_paired_residual.py']}
    (OUT/'candidate_specification.yaml').write_text(yaml.safe_dump(config,sort_keys=False),encoding='utf-8')
    plan={'status':'prepared_not_executed','scope':'matched-reference controlled replay, not standalone online diagnosis',
        'candidate_specification':'reports/p9/paired_residual/candidate_specification.yaml',
        'separation':{'noise_fit':'P11 train Normal flights only','threshold_calibration':'separate P11 validation Normal flights only',
                      'confirmation':'untouched P11 test source flights; all conditions and repeats stay together'},
        'normal_flight_inventory_same_commit':{'train':249,'validation':64,'test':62},
        'mandatory_before_execution':['check field coverage and usable duration without consulting outcomes',
           'use P11 training-only scaler or fit a new scaler only to the selected normal training flights',
           'freeze missing-channel, failed-run, mutation-effect and tie policies',
           'freeze time-varying injection schedules and severities before reading their outcomes'],
        'proposed_acceptance_not_user_mandated':{'normal_flight_false_alarm_upper_95_one_sided':0.05,
          'paired_detector_recall_point_target':0.9,'gated_top3_point_target':0.8,
          'include_clustered_intervals':True,'include_per_mutation_minimum':True},
        'minimum_independent_zero_false_alarm_flights_for_5_percent_upper_bound':59,
        'no_retune_on_confirmation':True,'baseline_comparison':'same target normals and faults under identical preprocessing',
        'timing':'report false alarms per flight and per hour; report detection and localization delay including failures',
        'initial_compatibility_candidates':'reports/p9/paired_residual/proposed_independent_sources.csv'}
    (OUT/'next_validation_plan.yaml').write_text(yaml.safe_dump(plan,sort_keys=False),encoding='utf-8')
    report=f'''# P9 配对 replay 继续优化报告

## Material Passport

- 日期：2026-09-06。范围：用户选择的 matched-baseline 配对 replay 检测与定位。
- 执行：新增 12 条独立正常重复；针对 EKF 模式问题再跑 9 条 baseline/fault/normal；其余 replay 全部复用。
- 状态：开发性优化与复评完成；独立确认实验尚未执行。候选规格与下一阶段计划已保存。
- 未改变：原 PX4 commit、mutation 强度、源数据、P1–P4 划分与模型、旧结果；本轮新增配对残差扩展，不把新指标归到原 P2/P3 分类器。

## 当前判断

最值得保留的改进是 **输入时钟对齐 + 正确 generic replay 模式 + 正常重复校准的配对残差检测/定位**。在当前 12 个 fault 与 12 个独立正常 target 上，主候选为 **检测 10/12、Top-1 4/12、Top-3/5 10/12、MRR 0.5833、正常误报 1/12**。无注入前报警，配对净检出从原模型的 0 增至 9/12。

这比上轮“fault 和 baseline 都报警 10/12”更接近真实的故障区分：INAV、Land Detector 均能进入 Top-3。仍未达到可靠端到端诊断的确认性证据要求：两条 EKF 漏报，1 条正常对照误报，一条 Commander 仍未通过旧效应检查，且只涉及 3 条源航次。

## 已处理的根因

1. **正常参考不能和自身比较**。新建独立进程正常重复，目标 ULog 与 reference 的路径和 SHA-256 均不同。每折只用其他两条源航次的 8 对正常重复拟合噪声与阈值；目标航次全部条件留出。没有用故障前 30 秒当正常训练段，也没有用 mutation 类型或真实模块设置预测阈值。
2. **时间原点分支错误**。旧 `_ulog_time_bounds` 在结束时间无效时连起点一起换成最早 topic 时间，正常重复曾因此错位约 0.63 秒。新增保留有效 header 起点的可选分支，默认行为不变。进一步用最前 256 条传感器六轴 payload 与原始输入进行精确匹配，估计 generic replay 的常量时钟偏移；不使用故障效应、onset、动态时间规整或 fault 标签对齐。36 条记录均通过，最少匹配 {verification['minimum_prefix_anchors']} 条，最大偏移离散为 {verification['maximum_clock_offset_spread_us']} 微秒。报警时间换回 target 时钟后才和 30 秒注入时刻计分。
3. **EKF generic 模式错误**。旧 `ekf2 start -r` 的专用 replay 分支，在估计器更新失败时发布未初始化 `vehicle_attitude_s att`。这里 generic replay 无需该握手。旧 9 条 EKF 记录仅约 13.7%–19.1% 的姿态四元数有效；对三个条件一致去掉 `-r`、复用完全相同二进制后，9/9 条的姿态有效率均为 100%。未对坏四元数做有利于得分的删改或替换，直接修正执行模式并重跑。
4. **故障证据不应由分类器重要性决定是否存在**。保留全部 87 通道×18 描述符，将 target 与健康 reference 的绝对差按正常重复的特征噪声归一化。当前采用正常 99% 分位噪声、固定 0.05 下限和正常连续三窗事件最大值阈值。检测后的同一残差证据按原 P8 publisher 边传播，保留全部 54 个候选模块；不依据 mutation 挑通道或模块。
5. **不按最高命中率挑版本**。单独按 topic 校准、或改用每特征正常最大偏差，都产生 12/12 的漂亮命中，但正常误报也达到 8/12，全部保留为未采用的消融。没有按 mutation 拼接不同版本的最佳结果。

## 同一批修复后数据的公平比较

所有方法使用相同 fault、独立正常 target、健康 reference、有效时间覆盖和候选模块。这里原模型的定位数值与上轮历史报告不同，因为 EKF 执行模式和时间网格又得到修正；不能混作同一版本。

{table(pd.DataFrame(comparisons))}

“配对净检出”要求 fault 在注入后报警、没有注入前报警，且独立正常 target 不报警。该指标体现当前实验中的区分性，但不构成部署场景故障精确率。

## 按 mutation 与剩余失败

{table(per)}

{table(detail)}

- Commander 三条排名均为 1，约 1.2–2.0 秒触发；第一条仍有 baseline 自然进入 AUTO_LAND 的混淆。原效应检查仍为 11/12 通过，判据未放宽。
- EKF2 第一、第二条漏报。去掉坏姿态干扰后，先前部分“成功”消失，这是有效性修正应保留的结果。全局正常事件阈值受其他 topic 的正常偏差影响，限制了 innovation 偏置检测；第三条正常重复还有一次较晚的 estimator_status 相关误报。
- INAV 三条均检测并排名 2；延迟约 14.8、32.4、50.8 秒，尚不够及时。静态发布者映射与 mavlink 存在并列，不能把并列候选写成唯一根因。
- Land Detector 三条均检测并排名 2，约 1.2 秒触发；同样存在静态发布者归属不唯一的问题。

附加效应有效子集保留 11 条：检测 {subset['detected']}/11，Top-1/3/5 为 {round(subset['top1']*11)}/11、{round(subset['top3']*11)}/11、{round(subset['top5']*11)}/11，MRR {subset['mrr']:.4f}。主指标始终保留原 12 条。

## 完整开发轨迹

{table(pd.DataFrame(ablations))}

这些数据已参与开发判断，不再将它们称为独立确认测试集。有限正常样本下的最大值阈值只是开发启发式，不是具有已验证覆盖保证的 conformal 校准。

## 怎样进一步达到可支撑的可靠结论

### 第一优先：分开正常建模、阈值校准和独立测试

同一固件下目前有 375 条 Normal 源日志，沿用 P11 划分为 train 249、validation 64、test 62 条，具备继续做独立确认的原始数据基础；仍需先核查完整字段、时长和 replay 成功率。已仅按元数据固定三条初始兼容性候选，见 `proposed_independent_sources.csv`，尚未运行这些候选。

- 正常 train 航次估计特征/物理残差噪声；validation 航次的独立正常重复只校准最终事件阈值；test 航次及其所有重复、mutation、严重度不得进入前两阶段。
- 使用 P11 的训练专属标准化器或仅用选定正常 train 航次拟合新标准化器。当前 P2 标准化器曾见过这些源航次的正常数据，不能据当前实现宣称基础特征处理严格从未见过 test 航次。
- 控制“整段正常 replay 至少一次报警”的概率，并报告每小时误报；不能用窗口 99% 分位直接声称整段 1% 误报。多 topic/多时间尺度的最终最大事件分数必须在独立正常 validation 上联合校准。
- 在读取 test 结果前固定故障起点、强度范围、重复次数、失败计分、缺失通道与并列规则；测试失败不回调阈值。候选规格已写入 `candidate_specification.yaml`，下一阶段设计见 `next_validation_plan.yaml`。

例如希望在 95% 单侧置信水平下支持正常航次误报率不超过 5%，即使观察到零误报，独立 Bernoulli 假设下也至少需要 **59 条独立正常航次**。仅 12 个独立对照若零误报，上界仍约 22.1%；当前 12 对照又只有 3 个源航次，不能按 12 个独立航次使用该区间。本轮实际还发生了 1 次误报，更不能宣称达到 5% 要求。

### 第二优先：提高 EKF 检出和 INAV 响应速度，保持无真值调参

- 扩充覆盖不同飞行阶段的正常重复，建立 topic 条件噪声模型，再用独立校准集控制多 topic 联合误报；不能直接启用当前已失败的分 topic 阈值版本。
- 增加通用物理一致性残差，例如三个轴统一的 `位置变化率－对应速度`、创新残差相对正常波动等。所有轴/同类通道一起定义，仅用正常数据确定噪声，不为已知 z-freeze 单独写命中规则。
- 对新残差尝试预先固定的短/长时间尺度，并联合校准事件阈值。INAV 延迟的目标应单独预设，不能只看最终 Top-k；缺乏可观测偏离的静止区间应如实报告。

### 第三优先：把可验证的候选集合与唯一根因分开

目前 INAV、Land Detector 的 rank=2 包含并列发布者，可靠表述应为候选模块集合。若需要唯一模块结论，需要增加运行时 uORB 实际发布者/实例来源观测，并对所有模块统一采集；不能利用“本次启动的 mutation 模块”直接缩小候选集。置信不足时输出拒判或候选集合，另行报告其覆盖率和误定位率。

### 确认时应同时报告

Detector recall、正常航次/每小时误报、同一批 target 上的检测门控 Top-1/3/5、MRR、拒判率、检测及定位延迟、分 mutation 最差表现，以及以源航次为单位的区间。控制台完整结束、传感器覆盖、时钟锚点、物理量有效性和 mutation 效应检查必须先通过；执行失败与无效例单独计入分母/失败统计，不事后删除。

## 现在能写什么

可以写：在固定 controlled paired replay 开发样本上，该残差扩展以 10/12 检出、1/12 独立正常误报，获得 10/12 的检测门控 Top-3 候选覆盖，改善了原管线的样本内区分性；尚未进行独立确认或统计显著性检验。

暂不能写：已证明可靠通用端到端根因诊断、已满足部署误报要求、能在无 matched baseline 时在线诊断，或把这些新结果归属于未改变的原 P2/P3 两阶段分类器。

## 复现与验证

```powershell
wsl --distribution Ubuntu-20.04 --user root -- bash /mnt/d/UAV/scripts/p9/run_normal_repeats.sh
wsl --distribution Ubuntu-20.04 --user root -- bash /mnt/d/UAV/scripts/p9/rerun_ekf_generic_mode.sh
.venv/Scripts/python.exe scripts/p9/assemble_paired_repair.py
.venv/Scripts/python.exe scripts/p9/audit_stage1.py --manifest reports/p9/paired_residual/ekf_generic_repair/reference/run_manifest.tsv --output reports/p9/paired_residual/corrected_reference --preserve-header-start --source-clock
.venv/Scripts/python.exe scripts/p9/audit_stage1.py --manifest reports/p9/paired_residual/ekf_generic_repair/normal/run_manifest.tsv --output reports/p9/paired_residual/corrected_normal --preserve-header-start --source-clock
.venv/Scripts/python.exe scripts/p9/evaluate_paired_residual.py --reference-cache reports/p9/paired_residual/corrected_reference --normal-cache reports/p9/paired_residual/corrected_normal --reference-manifest reports/p9/paired_residual/ekf_generic_repair/reference/run_manifest.tsv --normal-manifest reports/p9/paired_residual/ekf_generic_repair/normal/run_manifest.tsv --output reports/p9/paired_residual/corrected_results
.venv/Scripts/python.exe scripts/p9/validate_injection_effects.py --manifest reports/p9/paired_residual/ekf_generic_repair/reference/run_manifest.tsv --output reports/p9/paired_residual/ekf_generic_repair/injection_effect_validation.csv
# 原检查仍会返回一条 Commander 未通过，预期保留。
.venv/Scripts/python.exe scripts/p9/summarize_paired_optimization.py
.venv/Scripts/python.exe -m pytest tests/test_paired_replay.py tests/test_replay_detection.py tests/test_sitl_injection.py tests/test_baseline.py -q -p no:cacheprovider
```

25 项相关测试通过；P2 三条源日志特征与历史缓存仍逐项相同，32,138 窗验证分数误差仍为 1.11e-16；模型与标准化哈希未变。完整验证记录见 `verification.json`。
'''
    (OUT/'README.md').write_text(report,encoding='utf-8')
    print('Wrote',OUT/'README.md')
    print(json.dumps(verification,indent=2))

if __name__=='__main__':main()
