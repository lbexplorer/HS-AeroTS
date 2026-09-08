"""Generate auditable P15 result tables. Never chooses or refits a detector."""
from pathlib import Path
import json
import hashlib
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/'reports/p15_channel_optimization'
LABELS={'p15_channel_gate':'通道校准，原缓存','p15_joint_support':'共同采样支持＋通道校准','p15_reference_bank':'双健康参考＋通道证据'}

def main():
    DEST.mkdir(exist_ok=True)
    # Check sealed predictions and implementation files before reporting outcomes.
    audits=[];peaks=[]
    def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
    for name in LABELS:
        folder=ROOT/'reports'/name
        protocol=json.loads((folder/'protocol.json').read_text())
        seal=json.loads((folder/'prediction_freeze.json').read_text())
        assert digest(folder/'protocol.json')==seal['protocol_sha256'],name
        assert digest(folder/'prediction_index.csv')==seal['index_sha256'],name
        assert digest(folder/'calibration.npz')==protocol['calibration_sha256'],name
        for file,expected in protocol['protected_sha256'].items():
            assert digest(ROOT/file)==expected,file
        index=pd.read_csv(folder/'prediction_index.csv')
        for r in index.itertuples():assert digest(folder/r.file)==r.sha256,r.file
        audits.append(dict(experiment=name,predictions_verified=len(index),
            protected_files_verified=len(protocol['protected_sha256']),threshold=protocol['threshold']))
        w=pd.read_csv(folder/'window_predictions.csv')
        n=w[w.group.eq('normal')]
        peak=n.loc[n.groupby(['dataset','run_id']).score.idxmax(),
            ['dataset','run_id','score','strongest_channel']].copy()
        peak['experiment']=name;peak['threshold']=protocol['threshold'];peaks.append(peak)
    pd.concat(peaks,ignore_index=True).to_csv(DEST/'final_audit.csv',index=False)
    (DEST/'integrity_check.json').write_text(json.dumps(audits,indent=2),encoding='utf-8')
    rows=[]
    for name,label in LABELS.items():
        p=ROOT/'reports'/name/'summary.csv'
        if p.exists():
            frame=pd.read_csv(p);frame['experiment']=name;frame['label']=label;rows.append(frame)
    full=pd.concat(rows,ignore_index=True);full.to_csv(DEST/'all_summaries.csv',index=False)
    lines=['# P15 通道校准、配对采样与健康参考实验','',
        '## Material Passport','',
        '- 本轮在已查看的六条源航次上实施机制驱动优化；三条原开发航次只用正常目标确定参数，另外三条作为已暴露迁移检查。',
        '- 复用原模型、标准化器、特征噪声、描述子、模块映射与全部故障 replay。新增仅为独立健康目标。',
        '- 预测先封存、后读取 onset/GT 计分。所有 87 通道统一处理，不设 mutation 专属权重或白名单。',
        '- 下列是探索性结果，不能称作新航次独立确认；原 P2 标准化器暴露、仅三条迁移源航次、一个 Commander 效应检查失败等限制继续保留。','',
        '## 第一组：相同既有正常目标','',
        '| 前端/方法 | 故障检出 | 正常误报 | 故障前报警 | 干净故障独有检出 | Top-1/3/5 | MRR | 检出延迟中位数/最大值 s |',
        '|---|---:|---:|---:|---:|---|---:|---|']
    selected=full[(full.dataset=='transfer') & (full.experiment!='p15_reference_bank') & (full.method!='channel_gate_fixed_rank')]
    for r in selected.itertuples():
        label=r.label if r.method=='channel_gate_new_rank' else ('原始前端＋原主门控' if r.experiment=='p15_channel_gate' else '共同采样支持＋原主门控')
        lines.append(f'| {label} | {r.detected}/12 | {r.normal_alarms}/12 | {r.pre_onset}/12 | {r.clean_fault_only}/12 | {round(r.top1*12)}/{round(r.top3*12)}/{round(r.top5*12)}（各分母12） | {r.mrr:.4f} | {r.delay_median_s:.3f}/{r.delay_max_s:.3f} |')
    lines+=['','通道校准恢复了 INAV 的正证据及第 2 名候选排名；Top-3/5 从 9/12 提升至 12/12，但正常误报仍有 8/12。共同采样支持修复配合原门控时正常误报降至 3/12，同时漏检 2 个故障；重新执行同一正常校准规则后门槛改变，通道门控误报为 9/12。这些结果均保留，不根据迁移结果回调阈值。','',
        '共同采样前端与通道校准两个分支分别估计各自阈值，分数空间和有效观测不同；不把差异全归因于某个单一参数。','',
        '## 第二组：新增正常目标，同一数据上的对照','']
    bank=full[(full.dataset=='transfer')&(full.experiment=='p15_reference_bank')]
    if len(bank):
        lines+=['两个健康参考为原 baseline 与原独立正常 replay；它们不再充当本组正常测试。新执行的第三次健康 replay 才是正常测试目标。故障仍是同一批已有 fault replay。正常目标与两个参考的文件 SHA-256 均不同。','',
            '| 方法 | 故障检出 | 新正常误报 | 故障前报警 | 干净检出 | Top-1/3/5 | MRR | 延迟中位数/最大值 s |',
            '|---|---:|---:|---:|---:|---|---:|---|']
        for r in bank.itertuples():
            name={'original_primary':'单参考、共同支持、原门控','channel_gate_fixed_rank':'双参考门控＋单参考固定排名','channel_gate_new_rank':'双参考门控＋双参考证据排名'}[r.method]
            lines.append(f'| {name} | {r.detected}/12 | {r.normal_alarms}/12 | {r.pre_onset}/12 | {r.clean_fault_only}/12 | {round(r.top1*12)}/{round(r.top3*12)}/{round(r.top5*12)} | {r.mrr:.4f} | {r.delay_median_s:.3f}/{r.delay_max_s:.3f} |')
        lines+=['','本组使用新的正常目标和额外健康参考预算，不能把它与第一组历史正常误报直接相减解释为算法收益。双参考是额外实验条件；必须披露部署需要的健康参考。']
    else:lines+=['尚未完成，不能报告结果。']
    lines+=['','## 分 mutation 与可用率','']
    base=pd.read_csv(ROOT/'reports/p15_joint_support/results_by_run.csv')
    base=base[(base.dataset=='transfer')&(base.method=='original_primary')]
    lines+=['### 共同采样支持＋原冻结门控：分类型瓶颈','',
        '| Mutation | 检出 | 配对正常误报 | 故障前报警 | Top-1/3/5 | MRR | 延迟中位数/最大值 s |',
        '|---|---:|---:|---:|---|---:|---|']
    for mutation,d in base.groupby('mutation_id'):
        f=d[d.condition=='fault'];n=d[d.condition=='normal']
        lines.append(f'| {mutation} | {int(f.detected.sum())}/3 | {int(n.any_alarm.sum())}/3 | {int(f.pre_onset_alarm.sum())}/3 | {int(f.top1.sum())}/{int(f.top3.sum())}/{int(f.top5.sum())} | {f.mrr.mean():.4f} | {f.delay_s.median():.3f}/{f.delay_s.max():.3f} |')
    lines+=['','这里的 EKF 3/3 检出均伴随故障前报警及对应正常报警，不能解释为成功识别了注入。INAV 漏检 2/3，剩余一次延迟 107.623 秒，不能写成及时检测。Commander 第二源航次的历史注入效果检查未通过，仍保留在 12 次试验分母中，其排名命中不能单独证明有效注入诊断。','']
    for name,label in LABELS.items():
        p=ROOT/'reports'/name/'by_mutation.csv'
        if not p.exists():continue
        frame=pd.read_csv(p);frame=frame[(frame.dataset=='transfer')&(frame.method=='channel_gate_new_rank')]
        lines += [f'### {label}','','| Mutation | Recall | Top-1/3/5 | MRR | 平均检出延迟 s |','|---|---:|---|---:|---:|']
        for r in frame.itertuples():lines.append(f'| {r.mutation_id} | {round(r.detected*3)}/3 | {round(r.top1*3)}/{round(r.top3*3)}/{round(r.top5*3)}（各分母3） | {r.mrr:.4f} | {r.delay_s:.3f} |')
        coverage=ROOT/'reports'/name/'channel_coverage.csv'
        if coverage.exists():
            q=pd.read_csv(coverage);q=q[q.dataset=='transfer'];fraction=q.valid_windows/q.windows
            lines+=['',f'迁移集全部通道—运行有效窗口占比：均值 {fraction.mean():.1%}，中位数 {fraction.median():.1%}；完整明细见 `{name}/channel_coverage.csv`。缺失/间隔过大的通道窗口不给证据，不能把它们解释为正常；故障主分母没有删减。']
    lines+=['','## 本轮决策与论文可用结论','',
        '**停止继续调整门控阈值和增加同类健康参考；暂不启动昂贵的新航次确认实验。** 预设探索性门槛为正常误报不超过 2/12、故障检出至少 8/12、无对应正常报警的检出至少 6/12。所有当前分支均未同时通过。共同支持＋原门控最接近这一目标，但 3/12 正常误报仍不满足门槛；门槛本身也不是统计可靠性证明。',
        '',
        '可以写入论文的是受控消融和局限性：在三条已暴露迁移源航次、12 个故障/12 个正常 replay 上，共同采样支持处理在原冻结检测阈值下将正常报警由 11/12 降至 3/12，故障检出由 12/12 变为 10/12，Top-1/3/5 为 6/12、10/12、10/12，MRR 为 0.6667。另一通道证据分支得到 Top-3/5 12/12、MRR 0.7500，但同时有 8/12 正常报警，不能拼接两个分支的最优指标作为一个方法的结果。',
        '',
        '当前证据支持“在配对、离线、受控 replay 条件下观察到部分模块候选排序能力，并识别出采样不一致对误报的影响”。它仍不足以支持“跨新航次低误报的可靠端到端诊断”，也不证明原 Stage 1 模型泛化已修复。本轮改动使用配对残差旁路，原模型没有重新训练。',
        '',
        '双参考新增了 24 次健康 replay（六条源航次各四次）；迁移评估中新正常误报 10/12，与同一批新正常目标上的单参考对照 3/12 相比反而更差。两条参考之间的差异不能充分覆盖第三次健康运行的波动，正常校准不能跨源航次稳定迁移。具体漂移通道及分数见 final_audit.csv。',
        '',
        '若后续继续开发，唯一有当前证据支持的优先事项是：先用已有健康原始 ULog 检查 EKF 正常残差的首个分歧，区分输入/发布时序差异与状态估计演化差异；以时间点残差和物理量单位检查 INAV 信号是否在原描述子取最大值时被正常波动淹没。只有明确定位一种可修复的前端误差，并在现有健康数据上证明减小该误差且不删除故障观察时间后，才启动新方法实验。不能根据 mutation 标签屏蔽通道、为 EKF/INAV 单独调门槛或利用真实 onset 截断正常段。',
        '',
        '真正的最终确认必须冻结完整方法，使用新的源航次，且相关标准化器/噪声估计也不得接触确认航次；按源航次而不是高度相关的 replay 数量报告样本独立性。当前三条迁移航次已被检查多次，新增同源正常 replay 不会使它们重新变成独立测试集。',
        '',
        '## 必须保留的解释边界','',
        '- 开发集部署参数用开发正常数据拟合；其零误报是拟合数据检查，不能当独立误报率。正常阈值来源另在各实验的 calibration/events 文件中记录。',
        '- 主召回按 onset 后是否存在报警计算，同时报告 onset 前报警和配对正常误报。持续报警导致的表面高召回不能当故障特异性。',
        '- 检出延迟仅对成功检出计算，遗漏故障单独保留。模块排名为全段门控证据的离线汇总，不是首次报警时已完成的定位。',
        '- 三窗口门控本身不看未来；共同采样前端使用完整日志的采样间隔统计及插值，因此本轮不证明整个流程可因果在线运行。',
        '- 共同支持有效率必须与性能一起解释。不同方法之间不能通过静默缩短观测时间获得低误报结论。',
        '- 无论最终数字如何，不改变原冻结 P9/P14 报告、不删除无效注入试验，不基于 GT 打破 publisher 并列。','',
        '## 复现','',
        '1. `run_channel_experiment.py --phase freeze/predict/score`：按三个独立命令执行。',
        '2. `build_joint_replay_cache.py` 后运行 `run_joint_channel_experiment.py --phase freeze/predict/score`。',
        '3. `run_bank_normals.sh` 新增健康回放；`prepare_reference_bank.py` 建缓存；`run_reference_bank.py --phase freeze/predict/score`。',
        '4. `summarize_channel_experiments.py` 生成本表。脚本均位于 `scripts/p9/`；已有封存协议/预测不得覆盖。',
        '- 长任务后台执行，stdout/stderr/PID 在对应报告目录；原始 ULog 和缓存不纳入 Git。','']
    (DEST/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    print(DEST/'README.md')

if __name__=='__main__':main()
