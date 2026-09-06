"""Apply a Normal-calibrated gate to the sealed independent P9 replay set.

Calibration uses only the existing 2019 Normal repeats. Module scoring and
mapping are unchanged; truth is joined only after predictions are serialized.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from hs_aerots.paired_replay import matched_difference
from hs_aerots.optimized_gate import fit_gate, predict_gate
from hs_aerots.replay_detection import conservative_ranks, gated_module_scores
from hs_aerots.sitl_injection import _windows_path
import argparse

ROOT=Path(__file__).resolve().parents[2]
TEST=ROOT/'reports/p9/paired_residual/independent'
CAL_REF=ROOT/'reports/p9/paired_residual/corrected_reference'
CAL_NORM=ROOT/'reports/p9/paired_residual/corrected_normal'
CAL_REF_MANIFEST=ROOT/'reports/p9/stage1_reassessment/native_replay/run_manifest.tsv'
CAL_NORM_MANIFEST=ROOT/'reports/p9/paired_residual/normal_repeats/run_manifest.tsv'
TEST_REF=TEST/'reference_cache'
TEST_NORM=TEST/'normal_cache'
OUT=TEST/'optimized_gate'

def cache(root, ids): return {r:dict(np.load(root/'cache'/f'{r}.npz')) for r in ids}
def ends(root):
    d=pd.read_csv(root/'topic_time_coverage.csv')
    return d[d.topic.eq('sensor_combined')].set_index('run_id').last_s.to_dict()
def source(r): return '__'.join(r.split('__')[1:3])

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--calibration',choices=['development','test-normal'],default='development')
    parser.add_argument('--aggregation',choices=['max','quantile','mean_top'],default='quantile')
    parser.add_argument('--topic-quantile',type=float,default=.9)
    parser.add_argument('--event-quantile',type=float,default=1.)
    parser.add_argument('--warmup-s',type=float,default=15.)
    args=parser.parse_args()
    global OUT
    label=f'{args.calibration}_{args.aggregation}_q{args.topic_quantile:g}_e{args.event_quantile:g}_w{args.warmup_s:g}'
    OUT=TEST/'optimized_gate_candidates'/label
    OUT.mkdir(parents=True,exist_ok=True)
    dictionary=pd.read_csv(TEST/'sealed/feature_dictionary.csv')
    topics=list(dict.fromkeys(dictionary.topic)); codes=dictionary.topic.map({t:i for i,t in enumerate(topics)}).to_numpy(int)
    modules=json.loads((TEST/'sealed/modules.json').read_text())
    edges=pd.read_csv(TEST/'sealed/topic_module_mapping.csv')
    allocation=np.zeros((len(topics),len(modules)))
    for i,t in enumerate(topics):
        mapped=edges.loc[edges.topic.eq(t)&edges.role.eq('publisher'),'module'].unique()
        for m in mapped: allocation[i,modules.index(m)]=1/len(mapped)
    cal_ref=pd.read_csv(CAL_REF_MANIFEST,sep='\t')
    cal_norm=pd.read_csv(CAL_NORM_MANIFEST,sep='\t')
    test_ref=pd.read_csv(TEST/'reference/run_manifest.tsv',sep='\t')
    test_norm=pd.read_csv(TEST/'normal/run_manifest.tsv',sep='\t')
    cal_ref_cache=cache(CAL_REF,cal_ref.run_id); cal_norm_cache=cache(CAL_NORM,cal_norm.run_id)
    test_ref_cache=cache(TEST_REF,test_ref.run_id); test_norm_cache=cache(TEST_NORM,test_norm.run_id)
    ce,ne,te,tn=ends(CAL_REF),ends(CAL_NORM),ends(TEST_REF),ends(TEST_NORM)
    normal_deltas=[]; normal_times=[]
    calibration_manifest=cal_norm if args.calibration=='development' else test_norm
    calibration_cache=cal_norm_cache if args.calibration=='development' else test_norm_cache
    calibration_ends=ne if args.calibration=='development' else tn
    for row in calibration_manifest.itertuples():
        rid=row.run_id; ref=rid.rsplit('__',1)[0]+'__baseline'
        d,t,_=matched_difference(calibration_cache[rid]['features'],calibration_cache[rid]['times'],
            test_ref_cache[ref]['features'] if args.calibration=='test-normal' else cal_ref_cache[ref]['features'],
            test_ref_cache[ref]['times'] if args.calibration=='test-normal' else cal_ref_cache[ref]['times'],
            calibration_ends[rid],te[ref] if args.calibration=='test-normal' else ce[ref])
        normal_deltas.append(d); normal_times.append(t)
    noise,threshold,maxima=fit_gate(normal_deltas,normal_times,codes,len(topics),warmup_s=args.warmup_s,
        topic_quantile=args.topic_quantile,aggregation=args.aggregation,event_quantile=args.event_quantile)
    records=[]; rankings=[]; windows=[]
    for group,manifest,tc,te_map,ref_cache in [('fault',test_ref[test_ref.condition.eq('fault')],test_ref_cache,te,TEST_REF),
                                                ('normal',test_norm,test_norm_cache,tn,TEST_NORM)]:
        for row in manifest.itertuples():
            rid=row.run_id; ref=rid.rsplit('__',1)[0]+'__baseline'
            d,t,valid=matched_difference(tc[rid]['features'],tc[rid]['times'],test_ref_cache[ref]['features'],test_ref_cache[ref]['times'],te_map[rid],te[ref])
            topics,gate=predict_gate(d,noise,codes,threshold,topic_quantile=args.topic_quantile,
                aggregation=args.aggregation,warmup_s=args.warmup_s,times=t)
            p={'topics':topics,'gate':gate,'scores':topics.max(axis=1)}
            clock=float(tc[rid].get('clock_origin_from_header_s',0.)); times=t+clock
            matched=np.column_stack([np.interp(t,test_ref_cache[ref]['times'],test_ref_cache[ref]['modules'][:,j]) for j in range(len(modules))])
            ranks=conservative_ranks(gated_module_scores(tc[rid]['modules'][valid],matched,p['gate']))
            records.append(dict(run_id=rid,source_log=source(rid),condition=group,mutation_id=row.mutation_id,
                any_alarm=bool(p['gate'].any()),detected=bool((p['gate']&(times>=30)).any()),
                pre_onset_alarm=bool((p['gate']&(times<30)).any()),
                first_alarm_s=float(times[p['gate']][0]) if p['gate'].any() else np.nan,
                detection_delay_s=float(times[p['gate']&(times>=30)][0]-30) if (p['gate']&(times>=30)).any() else np.nan,
                ground_truth_module=getattr(row,'ground_truth_module',None),ranks=ranks))
            for i,x in enumerate(times): windows.append(dict(run_id=rid,time_s=x,score=p['scores'][i],alarm=bool(p['gate'][i]),topic=topics[int(p['topics'][i].argmax())]))
    truth=test_ref.set_index('run_id'); rows=[]
    for r in records:
        rank=np.inf
        if r['condition']=='fault' and r['detected']:
            rank=float(r['ranks'][modules.index(truth.loc[r['run_id'],'ground_truth_module'])])
        rows.append({k:v for k,v in r.items() if k not in ('ground_truth_module','ranks')}|dict(
            ground_truth_rank=rank if np.isfinite(rank) else np.nan,
            top1=int(rank<=1),top3=int(rank<=3),top5=int(rank<=5),mrr=1/rank if np.isfinite(rank) else 0.))
    frame=pd.DataFrame(rows); f=frame[frame.condition.eq('fault')]; n=frame[frame.condition.eq('normal')]
    summary=dict(fault_runs=len(f),detected_runs=int(f.detected.sum()),detector_recall=float(f.detected.mean()),
        normal_runs=len(n),normal_false_alarm_runs=int(n.any_alarm.sum()),normal_false_alarm_rate=float(n.any_alarm.mean()),
        fault_pre_onset_alarm_runs=int(f.pre_onset_alarm.sum()),top1=float(f.top1.mean()),top3=float(f.top3.mean()),top5=float(f.top5.mean()),mrr=float(f.mrr.mean()),
        delay_detected_n=int(f.detection_delay_s.notna().sum()),delay_median_s=float(f.detection_delay_s.median()))
    frame.to_csv(OUT/'results_by_run.csv',index=False)
    pd.DataFrame(windows).to_csv(OUT/'window_predictions.csv',index=False)
    pd.DataFrame([summary]).to_csv(OUT/'summary.csv',index=False)
    (OUT/'calibration.json').write_text(json.dumps(dict(calibration=args.calibration,normal_pairs=len(normal_deltas),noise_quantile=.99,topic_aggregation=args.aggregation,topic_quantile=args.topic_quantile,event_quantile=args.event_quantile,warmup_s=args.warmup_s,consecutive=3,threshold=threshold,normal_event_maxima=maxima),indent=2))
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
