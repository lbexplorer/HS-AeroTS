"""Cross-flight development evaluation with independent healthy replay targets."""
from pathlib import Path
import argparse
import json
import hashlib
import numpy as np
import pandas as pd
import yaml
from hs_aerots.paired_replay import (matched_difference,fit_normal_residuals,predict_paired,
                                    fit_topic_thresholds,predict_paired_topics)
from hs_aerots.replay_detection import gated_module_scores,conservative_ranks,sustained_gate
from hs_aerots.sitl_injection import _windows_path

ROOT=Path(__file__).resolve().parents[2]
REFERENCE=ROOT/'reports/p9/stage1_reassessment/native_replay'
OUT=ROOT/'reports/p9/paired_residual'
NORMAL=OUT/'normal_repeats'

def source_id(run_id):return '__'.join(run_id.split('__')[1:3])

def load_cache(root,ids):
    return {r:dict(np.load(root/'cache'/f'{r}.npz')) for r in ids}

def supports(root):
    d=pd.read_csv(root/'topic_time_coverage.csv')
    return d[d.topic.eq('sensor_combined')].set_index('run_id').last_s.to_dict()

def main():
    global OUT
    parser=argparse.ArgumentParser()
    parser.add_argument('--reference-cache',type=Path,default=REFERENCE)
    parser.add_argument('--normal-cache',type=Path,default=NORMAL)
    parser.add_argument('--output',type=Path,default=OUT)
    parser.add_argument('--reference-manifest',type=Path,default=REFERENCE/'run_manifest.tsv')
    parser.add_argument('--normal-manifest',type=Path,default=NORMAL/'run_manifest.tsv')
    parser.add_argument('--topic-gate',action='store_true')
    parser.add_argument('--noise-quantile',type=float,default=None)
    parser.add_argument('--topic-aggregation',choices=['max','quantile','mean_top'],default='max')
    parser.add_argument('--topic-quantile',type=float,default=.9)
    parser.add_argument('--event-quantile',type=float,default=1.0)
    parser.add_argument('--warmup-s',type=float,default=0.)
    args=parser.parse_args()
    OUT=args.output
    config=yaml.safe_load((ROOT/'configs/p9_paired_residual.yaml').read_text())
    OUT.mkdir(parents=True,exist_ok=True)
    manifest=pd.read_csv(args.reference_manifest,sep='\t')
    controls=pd.read_csv(args.normal_manifest,sep='\t')
    assert len(controls)==12 and controls.condition.eq('baseline').all()
    baselines=manifest.loc[manifest.condition.eq('baseline'),'run_id'].tolist()
    faults=manifest.loc[manifest.condition.eq('fault'),'run_id'].tolist()
    assert set(controls.run_id)==set(baselines)
    cache=load_cache(args.reference_cache,manifest.run_id)
    healthy=load_cache(args.normal_cache,controls.run_id)
    ends=supports(args.reference_cache); normal_ends=supports(args.normal_cache)
    config['reference_feature_audit']=str(args.reference_cache)
    config['normal_feature_audit']=str(args.normal_cache)
    config['topic_specific_persistence']=args.topic_gate
    if args.noise_quantile is not None:config['calibration']['noise_quantile']=args.noise_quantile
    dictionary=pd.read_csv(ROOT/'reports/p2/feature_dictionary.csv')
    topics=list(dict.fromkeys(dictionary.topic.tolist()))
    codes=dictionary.topic.map({t:i for i,t in enumerate(topics)}).to_numpy(int)
    modules=json.loads((REFERENCE/'modules.json').read_text())
    edges=pd.read_csv(ROOT/'reports/p8/topic_module_mapping.csv')
    allocation=np.zeros((len(topics),len(modules)))
    for i,topic in enumerate(topics):
        mapped=edges.loc[edges.topic.eq(topic)&edges.role.eq('publisher'),'module'].unique()
        for module in mapped:allocation[i,modules.index(module)]=1/len(mapped)
    assert len(modules)==config['localization']['candidate_count']
    pairs={}; identity=[]
    for condition,ids,target_cache,target_root,target_ends in [
            ('normal',baselines,healthy,NORMAL,normal_ends),('fault',faults,cache,REFERENCE,ends)]:
        for run_id in ids:
            ref_id=run_id.rsplit('__',1)[0]+'__baseline'
            target_manifest=controls if condition=='normal' else manifest
            target_path=_windows_path(ROOT,target_manifest.set_index('run_id').loc[run_id,'output_ulog'])
            ref_path=_windows_path(ROOT,manifest.set_index('run_id').loc[ref_id,'output_ulog'])
            assert target_path.resolve()!=ref_path.resolve()
            th=hashlib.sha256(target_path.read_bytes()).hexdigest()
            rh=hashlib.sha256(ref_path.read_bytes()).hexdigest()
            assert th!=rh,'target must not be a copied reference'
            d,b=target_cache[run_id],cache[ref_id]
            delta,times,valid=matched_difference(d['features'],d['times'],b['features'],b['times'],target_ends[run_id],ends[ref_id])
            assert len(times)>=3
            pair_id=condition+':'+run_id
            pairs[pair_id]={'delta':delta,'times':times,'source':source_id(run_id),'run_id':run_id,
                           'condition':condition,'target':d,'reference':b,'valid':valid}
            identity.append({'pair_id':pair_id,'target_sha256':th,'reference_sha256':rh,'same_file':False})
    predictions=[];fit_rows=[]
    original_threshold=json.loads((ROOT/'reports/p2/baseline_runs/seed0/metrics.json').read_text())['val_threshold']
    for source in sorted(set(p['source'] for p in pairs.values())):
        calibration=[k for k,p in pairs.items() if p['condition']=='normal' and p['source']!=source]
        assert len(calibration)==8
        cc=config['calibration'];consecutive=config['detector']['consecutive_windows']
        noise,threshold,maxima=fit_normal_residuals([pairs[k]['delta'] for k in calibration],codes,len(topics),
            cc['noise_quantile'],cc['standardized_descriptor_noise_floor'],consecutive,cc['minimum_threshold'],
            args.topic_aggregation,args.topic_quantile,args.event_quantile,args.warmup_s,
            [pairs[k]['times'] for k in calibration])
        np.save(OUT/f'noise_{source}.npy',noise)
        topic_threshold=None
        if args.topic_gate:
            topic_threshold=fit_topic_thresholds([pairs[k]['delta'] for k in calibration],noise,codes,len(topics),
                                                 consecutive,cc['minimum_threshold'])
        fit_rows.append({'held_out_source':source,'normal_pair_ids':calibration,'normal_event_maxima':maxima,
                         'threshold':threshold,'faults_used':False,
                         'topic_thresholds':dict(zip(topics,topic_threshold.tolist())) if args.topic_gate else None})
        for pair_id,p in pairs.items():
            if p['source']!=source:continue
            pred=(predict_paired_topics(p['delta'],noise,codes,allocation,topic_threshold,consecutive,
                                        args.topic_aggregation,args.topic_quantile,args.warmup_s,p['times'])
                  if args.topic_gate else predict_paired(p['delta'],noise,codes,allocation,threshold,consecutive,
                                                         args.topic_aggregation,args.topic_quantile,args.warmup_s,p['times']))
            b=p['reference']; d=p['target'];t=p['times']
            matched=np.column_stack([np.interp(t,b['times'],b['modules'][:,j]) for j in range(len(modules))])
            shap_scores=gated_module_scores(d['modules'][p['valid']],matched,pred['gate'])
            original_gate=sustained_gate(d['scores'][p['valid']],original_threshold,1)
            original_scores=gated_module_scores(d['modules'][p['valid']],matched,original_gate)
            pred.update({'pair_id':pair_id,'run_id':p['run_id'],'condition':p['condition'],
                         'source':source,'times':t,'threshold':1.0 if args.topic_gate else threshold,'shap_scores':shap_scores,
                         'shap_ranks':conservative_ranks(shap_scores),'original_gate':original_gate,
                         'original_ranks':conservative_ranks(original_scores)})
            predictions.append(pred)
    # Frozen predictions above. Only scoring below can access onset/true modules.
    truth=manifest.set_index('run_id')
    onset=config['evaluation_only']['onset_s']
    rows=[];rank_rows=[];window_rows=[]
    for p in predictions:
        clock_offset=float(pairs[p['pair_id']]['target'].get('clock_origin_from_header_s',0.))
        t=p['times']+clock_offset;post=t>=onset
        target=truth.loc[p['run_id'],'ground_truth_module'] if p['condition']=='fault' else None
        for method,key in [('paired_residual','ranks'),('residual_gate_original_shap','shap_ranks'),
                           ('original_stage1_original_shap','original_ranks')]:
            g=p['original_gate'] if method=='original_stage1_original_shap' else p['gate']
            alarm=bool(g.any());detected=bool((g&post).any())
            rank=float(p[key][modules.index(target)]) if target is not None and detected else np.inf
            rows.append({'method':method,'pair_id':p['pair_id'],'run_id':p['run_id'],'source_log':p['source'],
                'condition':p['condition'],'mutation_id':truth.loc[p['run_id'],'mutation_id'],
                'threshold':original_threshold if method=='original_stage1_original_shap' else p['threshold'],
                'any_alarm':alarm,'detected':detected,
                'pre_onset_alarm':bool((g&~post).any()),'first_alarm_s':float(t[g][0]) if alarm else None,
                'detection_delay_s':float(t[g&post][0]-onset) if detected else None,
                'ground_truth_rank':rank if np.isfinite(rank) else None,
                **{f'top{k}':float(rank<=k) for k in (1,3,5)},'mrr':1/rank if np.isfinite(rank) else 0.})
        for j,module in enumerate(modules):rank_rows.append({'pair_id':p['pair_id'],'module':module,
            'score':p['module_scores'][j],'rank':p['ranks'][j] if np.isfinite(p['ranks'][j]) else None})
        for i,t in enumerate(p['times']):window_rows.append({'pair_id':p['pair_id'],'time_s':t,'score':p['scores'][i],
            'threshold':p['threshold'],'alarm':p['gate'][i],'strongest_topic':topics[int(p['topics'][i].argmax())]})
    runs=pd.DataFrame(rows);summaries=[]
    for method,d in runs.groupby('method',sort=False):
        f=d[d.condition.eq('fault')];n=d[d.condition.eq('normal')]
        false=n.set_index('run_id').any_alarm.to_dict()
        clean=f.detected&~f.pre_onset_alarm&np.array([not false[r.rsplit('__',1)[0]+'__baseline'] for r in f.run_id])
        summaries.append({'method':method,'fault_runs':len(f),'detected_runs':int(f.detected.sum()),
            'detector_recall':float(f.detected.mean()),**{k:float(f[k].mean()) for k in ['top1','top3','top5','mrr']},
            'normal_false_alarm_runs':int(n.any_alarm.sum()),'normal_runs':len(n),
            'normal_false_alarm_rate':float(n.any_alarm.mean()),'fault_pre_onset_alarm_runs':int(f.pre_onset_alarm.sum()),
            'clean_fault_only_detected_runs':int(clean.sum())})
    runs.to_csv(OUT/'results_by_run.csv',index=False)
    pd.DataFrame(summaries).to_csv(OUT/'summary.csv',index=False)
    runs[runs.condition.eq('fault')].groupby(['method','mutation_id'])[['detected','top1','top3','top5','mrr']].mean().to_csv(OUT/'by_mutation.csv')
    pd.DataFrame(rank_rows).to_csv(OUT/'module_rankings.csv',index=False)
    pd.DataFrame(window_rows).to_csv(OUT/'window_predictions.csv',index=False)
    pd.DataFrame(identity).to_csv(OUT/'independent_pair_identity.csv',index=False)
    (OUT/'calibration.json').write_text(json.dumps(fit_rows,indent=2))
    (OUT/'protocol.json').write_text(json.dumps(config,indent=2))
    print(pd.DataFrame(summaries).to_string(index=False))

if __name__=='__main__':main()
