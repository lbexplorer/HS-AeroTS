"""Reevaluate cached replay inference; truth is used only after prediction."""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
import yaml
from hs_aerots.replay_detection import (sustained_gate, normal_threshold,
    gated_module_scores, conservative_ranks)

ROOT = Path(__file__).resolve().parents[2]

def source_id(run_id):
    return '__'.join(run_id.split('__')[1:3])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--audit', default='reports/p9/stage1_reassessment')
    parser.add_argument('--manifest', default='reports/p9/run_manifest.tsv')
    parser.add_argument('--mapping', choices=['bidirectional','publisher'], default='bidirectional')
    args = parser.parse_args()
    out = ROOT / args.audit
    protocol = yaml.safe_load((ROOT/'configs/p9_stage1_reassessment.yaml').read_text())
    manifest = pd.read_csv(ROOT/args.manifest, sep='\t')
    if len(manifest) != 24 or manifest.condition.eq('fault').sum() != 12:
        raise ValueError('Refusing partial-run evaluation: all 24 runs are required')
    modules = json.loads((out/'modules.json').read_text())
    cache = {r:dict(np.load(out/'cache'/f'{r}.npz')) for r in manifest.run_id}
    coverage = pd.read_csv(out/'topic_time_coverage.csv')
    last_sensor = coverage.loc[coverage.topic.eq('sensor_combined')].set_index('run_id').last_s.to_dict()
    if args.mapping=='publisher':
        dictionary=pd.read_csv(ROOT/'reports/p2/feature_dictionary.csv')
        topics=list(dict.fromkeys(dictionary.topic.tolist()))
        edges=pd.read_csv(ROOT/'reports/p8/topic_module_mapping.csv')
        matrix=np.zeros((len(topics),len(modules)))
        for i,topic in enumerate(topics):
            mapped=edges.loc[edges.topic.eq(topic)&edges.role.eq('publisher'),'module'].unique()
            for module in mapped: matrix[i,modules.index(module)]=1/len(mapped)
        for d in cache.values(): d['modules']=d['topics']@matrix
        out=out/'publisher_only'
        out.mkdir(exist_ok=True)
        protocol['mapping']='existing P8 publisher-only; all original 54 candidates retained; exploratory ablation'
    fixed = json.loads((ROOT/'reports/p2/baseline_runs/seed0/metrics.json').read_text())['val_threshold']
    baselines = manifest.loc[manifest.condition.eq('baseline'),'run_id'].tolist()
    predictions, calibrations = [], []
    # Normal-only fit and truth-blind prediction. No mutation/module/onset access.
    for mode, fresh, calibrated, consecutive in [('fixed_all',False,False,1),
            ('fixed_fresh',True,False,1),('calibrated_fresh',True,True,protocol['gate']['consecutive'])]:
        for run_id in manifest.run_id:
            target_source = source_id(run_id)
            calibration_ids = [r for r in baselines if source_id(r) != target_source]
            assert all(source_id(r) != target_source for r in calibration_ids)
            threshold = normal_threshold([cache[r]['scores'][cache[r]['times'] <= last_sensor[r]] for r in calibration_ids],
                protocol['normal_calibration']['quantile']) if calibrated else fixed
            d=cache[run_id]
            valid = d['times'] <= last_sensor[run_id] if fresh else np.ones(len(d['times']),bool)
            gate=sustained_gate(d['scores'],threshold,consecutive) & valid
            ref_id=run_id.rsplit('__',1)[0]+'__baseline'
            b=cache[ref_id]
            # Use elapsed-time interpolation, rather than row-count truncation.
            matched = np.column_stack([np.interp(d['times'],b['times'],b['modules'][:,j]) for j in range(len(modules))])
            supported=(d['times']>=b['times'][0])&(d['times']<=b['times'][-1])
            if fresh: supported &= d['times']<=last_sensor[ref_id]
            localization_gate=gate&supported
            aggregate=gated_module_scores(d['modules'],matched,localization_gate)
            ranks=conservative_ranks(aggregate)
            predictions.append({'mode':mode,'run_id':run_id,'threshold':threshold,'times':d['times'],
                'gate':gate,'localization_gate':localization_gate,'ranks':ranks,'scores':aggregate,'valid':valid})
            calibrations.append({'mode':mode,'run_id':run_id,'held_out_source':target_source,'threshold':threshold,
                'calibration_run_ids':';'.join(calibration_ids) if calibrated else '',
                'fault_data_used_in_fit':False})
    # Ground-truth evaluation starts here. It cannot change saved predictions.
    onset=protocol['evaluation']['injection_start_s']
    truth=manifest.set_index('run_id')
    rows, ranking_rows, window_rows=[],[],[]
    for pred in predictions:
        r=truth.loc[pred['run_id']]
        times,gate=pred['times'],pred['gate']
        post=times>=onset
        post_alarm=bool((gate&post).any())
        rank=float(pred['ranks'][modules.index(r.ground_truth_module)]) if post_alarm and r.condition=='fault' else np.inf
        rows.append({'mode':pred['mode'],'run_id':pred['run_id'],'source_log':source_id(pred['run_id']),
            'condition':r.condition,'mutation_id':r.mutation_id,'threshold':pred['threshold'],
            'any_alarm':bool(gate.any()),'pre_onset_alarm':bool((gate&~post).any()),'detected':post_alarm,
            'detection_delay_s':float(times[gate&post][0]-onset) if post_alarm else None,
            'fresh_post_windows':int((pred['valid']&post).sum()),'gated_windows':int(gate.sum()),
            'ground_truth_rank':rank if np.isfinite(rank) else None,
            'top1':float(rank<=1),'top3':float(rank<=3),'top5':float(rank<=5),
            'mrr':float(1/rank) if np.isfinite(rank) else 0.})
        for j,mod in enumerate(modules):
            ranking_rows.append({'mode':pred['mode'],'run_id':pred['run_id'],'module':mod,
                'score':pred['scores'][j],'rank':pred['ranks'][j] if np.isfinite(pred['ranks'][j]) else None})
        for i,t in enumerate(times):
            window_rows.append({'mode':pred['mode'],'run_id':pred['run_id'],'time_s':t,'score':cache[pred['run_id']]['scores'][i],
                'threshold':pred['threshold'],'valid':pred['valid'][i],'detector_gate':gate[i],
                'localization_gate':pred['localization_gate'][i]})
    runs=pd.DataFrame(rows)
    summaries=[]
    for mode,part in runs.groupby('mode',sort=False):
        f=part[part.condition.eq('fault')]; b=part[part.condition.eq('baseline')]
        baseline_alarms=b.set_index('run_id').any_alarm.to_dict()
        clean=f.detected & ~f.pre_onset_alarm & np.array([
            not baseline_alarms[r.rsplit('__',1)[0]+'__baseline'] for r in f.run_id])
        summary={'mode':mode,'fault_runs':len(f),'detected_runs':int(f.detected.sum()),
            'detector_recall':float(f.detected.mean()),
            **{k:float(f[k].mean()) for k in ['top1','top3','top5','mrr']},
            'baseline_false_alarm_runs':int(b.any_alarm.sum()),'baseline_false_alarm_rate':float(b.any_alarm.mean()),
            'fault_pre_onset_alarm_runs':int(f.pre_onset_alarm.sum()),
            'clean_fault_only_detected_runs':int(clean.sum()),
            'fresh_post_supported_fault_runs':int(f.fresh_post_windows.gt(0).sum())}
        summaries.append(summary)
    runs.to_csv(out/'reevaluation_by_run.csv',index=False)
    pd.DataFrame(summaries).to_csv(out/'reevaluation_summary.csv',index=False)
    runs[runs.condition.eq('fault')].groupby(['mode','mutation_id'])[['detected','top1','top3','top5','mrr']].mean().to_csv(out/'reevaluation_by_mutation.csv')
    pd.DataFrame(calibrations).to_csv(out/'calibration_audit.csv',index=False)
    pd.DataFrame(ranking_rows).to_csv(out/'blind_module_rankings.csv',index=False)
    pd.DataFrame(window_rows).to_csv(out/'window_predictions.csv',index=False)
    (out/'reevaluation_protocol.json').write_text(json.dumps(protocol,indent=2))
    print(pd.DataFrame(summaries).to_string(index=False))

if __name__=='__main__': main()
