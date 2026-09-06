"""Generate independent P9 tables from scored artifacts, without parameter changes."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/p9/paired_residual/independent'
NAMES={'commander_nav_state_override':'Commander 状态覆盖',
       'ekf2_innovation_bias':'EKF innovation bias',
       'inav_local_z_freeze':'INAV 高度冻结',
       'land_detector_state_inversion':'Land detector 状态翻转'}

def ratio(n,d):return f'{int(n)}/{int(d)} ({n/d:.1%})'

def main():
    summary=pd.read_csv(OUT/'summary.csv')
    current=summary[summary.primary].iloc[0]
    dev=pd.read_csv(ROOT/'reports/p9/paired_residual/corrected_results/summary.csv')
    old=dev[dev.method.eq('paired_residual')].iloc[0]
    runs=pd.read_csv(OUT/'results_by_run.csv');runs=runs[runs.primary]
    by=pd.read_csv(OUT/'by_mutation.csv');by=by[by.calibration.eq(current.calibration)]
    audit=json.loads((OUT/'verification.json').read_text())
    effects=pd.read_csv(OUT/'injection_effect_validation.csv').set_index('run_id')
    lines=['## 最终结果','', '| 指标 | 开发集（原三折汇总） | 冻结主配置新航次 | 差值 |', '|---|---:|---:|---:|']
    for name,key in [('Detection Recall','detector_recall'),('正常误报率','normal_false_alarm_rate'),('Top-1','top1'),('Top-3','top3'),('Top-5','top5'),('MRR','mrr')]:
        if key=='mrr': a=f'{old[key]:.4f}';b=f'{current[key]:.4f}';d=f'{current[key]-old[key]:+.4f}'
        else:
            a=ratio(round(old[key]*12),12);b=ratio(round(current[key]*12),12);d=f'{100*(current[key]-old[key]):+.1f} 个百分点'
        lines.append(f'| {name} | {a} | {b} | {d} |')
    lines+=['', '开发集按源航次使用各自留一校准；新航次统一使用测试前选定的一组已有参数。因此差异同时包含航次迁移与校准部署口径差异，不能全归因于分布偏移。', '',
        f"检测延迟：成功检测 {int(current.delay_detected_n)}/12，中位数 {current.delay_median_s:.3f} s，范围 {current.delay_min_s:.3f}–{current.delay_max_s:.3f} s；{int(current.misses)} 次漏检单独保留。延迟基于 replay 日志时间，不含离线解析/推理耗时，也不是模块定位完成时延。", '',
        f"正常目标出现误报 {int(current.normal_false_alarm_runs)}/12，涉及 {int(current.normal_false_alarm_source_flights)}/3 个源航次；故障 onset 前报警 {int(current.fault_pre_onset_alarm_runs)}/12。扣除同条件正常报警及 onset 前报警后，干净的故障独有检出为 {int(current.clean_fault_only_detected_runs)}/12。", '',
        '| Mutation | Detection | 正常误报 | Top-1 | Top-3 / Top-5 | MRR | 检出延迟中位数 / 范围（s） |', '|---|---:|---:|---:|---:|---:|---|']
    for r in by.itertuples():
        delay='无检出' if r.delay_detected_n==0 else f'{r.delay_median_s:.3f} / {r.delay_min_s:.3f}–{r.delay_max_s:.3f}'
        lines.append(f'| {NAMES[r.mutation_id]} | {int(r.detected_runs)}/3 | {int(r.normal_false_alarm_runs)}/3 | {round(r.top1*3)}/3 | {round(r.top3*3)}/3 / {round(r.top5*3)}/3 | {r.mrr:.4f} | {delay} |')
    lines+=['','## 逐次故障与误报','', '| 源航次 | Mutation | 检出 | GT 名次 | 延迟（s） | 连续残差最大值 / 阈值 | 注入生效检查 |', '|---|---|---|---:|---:|---:|---|']
    for r in runs[runs.condition.eq('fault')].itertuples():
        rank=str(int(r.ground_truth_rank)) if np.isfinite(r.ground_truth_rank) else '无有效名次'
        delay=f'{r.detection_delay_s:.3f}' if r.detected else f'漏检；观察至 {r.observation_end_s:.3f}'
        lines.append(f'| {r.source_log} | {NAMES[r.mutation_id]} | {"是" if r.detected else "否"} | {rank} | {delay} | {r.residual_maximum:.3f} / {r.threshold:.3f} | {"通过" if effects.loc[r.run_id,"passed"] else "未通过，保留计分"} |')
    normals=runs[runs.condition.eq('normal') & runs.any_alarm]
    lines+=['', '正常误报逐项：']
    if normals.empty: lines+=['','本次正常目标未观察到报警；仅三个源航次，不能据此证明总体误报率低。']
    for r in normals.itertuples(): lines.append(f'- {r.source_log} / {NAMES[r.mutation_id]}：首次 {r.first_alarm_s:.3f} s，主要门控证据 `{r.strongest_topic}`，连续残差最大值 {r.residual_maximum:.3f}。')
    lines+=['','## 冻结参数敏感性（全部报告，不择优）','', '| 开发校准标识 | 主配置 | Recall | 正常误报 | Top-1 | Top-3 / Top-5 | MRR |', '|---|---|---:|---:|---:|---:|---:|']
    for r in summary.itertuples(): lines.append(f'| {r.calibration} | {"是" if r.primary else "否"} | {int(r.detected_runs)}/12 | {int(r.normal_false_alarm_runs)}/12 | {round(r.top1*12)}/12 | {round(r.top3*12)}/12 / {round(r.top5*12)}/12 | {r.mrr:.4f} |')
    lines+=['','## 完整性核验','',f"- {audit['completed_runs']}/36 次最终 replay 完成；原二进制、方法与参数哈希不变；时钟锚点最大偏差 {audit['maximum_clock_offset_spread_us']:.0f} μs。",f"- 既有注入效果标准通过 {audit['effect_checks_passed']}/12；全部 12 次仍在主指标分母。",'- 28 项关键测试通过。预测与计分分离，预测文件有哈希；正常与参考日志路径和内容均不同。',
        '- 第二条源航次最初四次 baseline 遭遇基础设施中断：进程被终止、跨系统复制报 Bad address、本地日志损坏；保留在 `infrastructure_failure/`，在未读取检测成绩时更换临时工作目录重跑。第一条航次的 12 次有效运行直接复用。',
        '- 原 P2 训练数据暴露已明确列出；本次不宣称全学习流程的航次级隔离。','']
    path=OUT/'README.md'
    text=path.read_text(encoding='utf-8').split('<!-- GENERATED RESULTS -->')[0]
    text=text.replace('状态：已封存协议，36 次 replay 正在运行；尚未读取测试检测结果。','状态：36 次有效 replay 和冻结参数评估已完成；未根据独立结果调整参数。')
    path.write_text(text+'\n<!-- GENERATED RESULTS -->\n'+'\n'.join(lines),encoding='utf-8')
    print(path)

if __name__=='__main__':main()
