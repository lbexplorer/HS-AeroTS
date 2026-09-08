"""P15: freeze normal calibration, predict without truth, then score separately."""
from pathlib import Path
import argparse
from datetime import datetime,timezone
import hashlib
import json
import numpy as np
import pandas as pd
import yaml
from evaluate_independent import mapping
from hs_aerots.paired_replay import matched_difference,predict_paired
from hs_aerots.channel_gate import channel_values,fit_channels,persistent_channels,predict_channels

ROOT=Path(__file__).resolve().parents[2]
P9=ROOT/'reports/p9/paired_residual'
OUT=ROOT/'reports/p15_channel_gate'
SEAL=P9/'independent/sealed'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def layout():
    topics,codes,modules,allocation=mapping(SEAL)
    fd=pd.read_csv(SEAL/'feature_dictionary.csv')
    channels=list(dict.fromkeys(fd.channel))
    fc=fd.channel.map({c:i for i,c in enumerate(channels)}).to_numpy(int)
    ct=np.array([topics.index(fd.loc[fd.channel.eq(c),'topic'].iloc[0]) for c in channels])
    noise=np.load(SEAL/'noise_2019-01-18__08_39_38.npy')
    return topics,codes,modules,allocation,channels,fc,ct,noise

def paths(dataset):
    if dataset=='development':
        return dict(reference_cache=P9/'corrected_reference',normal_cache=P9/'corrected_normal',
            reference_manifest=P9/'ekf_generic_repair/reference/run_manifest.tsv',
            normal_manifest=P9/'ekf_generic_repair/normal/run_manifest.tsv')
    return dict(reference_cache=P9/'independent/reference_cache',normal_cache=P9/'independent/normal_cache',
        reference_manifest=P9/'independent/reference/run_manifest.tsv',normal_manifest=P9/'independent/normal/run_manifest.tsv')

def pairs(dataset,normal_only=False):
    p=paths(dataset)
    manifest=pd.read_csv(p['reference_manifest'],sep='\t',usecols=['run_id'])
    normal=pd.read_csv(p['normal_manifest'],sep='\t',usecols=['run_id'])
    support={}
    for group in ['reference','normal']:
        cover=pd.read_csv(p[f'{group}_cache']/'topic_time_coverage.csv')
        support[group]=cover[cover.topic.eq('sensor_combined')].set_index('run_id').last_s.to_dict()
    groups=[('normal',normal.run_id)]
    if not normal_only:groups.append(('reference',manifest.loc[manifest.run_id.str.endswith('__fault'),'run_id']))
    for group,ids in groups:
        for rid in ids:
            ref_id=rid.rsplit('__',1)[0]+'__baseline'
            a=dict(np.load(p[f'{group}_cache']/'cache'/f'{rid}.npz'))
            b=dict(np.load(p['reference_cache']/'cache'/f'{ref_id}.npz'))
            d,t,valid=matched_difference(a['features'],a['times'],b['features'],b['times'],support[group][rid],support['reference'][ref_id])
            if len(t)<3:raise ValueError(f'Insufficient joint support: {dataset}:{rid}')
            yield dict(dataset=dataset,group=group,run_id=rid,source='__'.join(rid.split('__')[1:3]),
                delta=d,times=t+float(a.get('clock_origin_from_header_s',0.)))

def freeze():
    OUT.mkdir(exist_ok=True)
    assert not (OUT/'protocol.json').exists(),'Do not overwrite a frozen experiment'
    *_,channels,fc,ct,noise=layout()
    normal=list(pairs('development',normal_only=True))
    values=[channel_values(p['delta'],noise,fc,len(channels)) for p in normal]
    events=[];folds=[]
    for source in sorted({p['source'] for p in normal}):
        fit=[v for p,v in zip(normal,values) if p['source']!=source]
        center,scale=fit_channels(fit)
        np.savez_compressed(OUT/f'calibration_excluding_{source}.npz',center=center,scale=scale)
        folds.append(dict(heldout_source=source,fit_sources=sorted({p['source'] for p in normal if p['source']!=source})))
        for p,v in zip(normal,values):
            if p['source']!=source:continue
            score=persistent_channels(np.maximum(0,(v-center)/scale)).max()
            events.append(dict(run_id=p['run_id'],source=source,event_maximum=float(score)))
    threshold=max(1.,sorted(e['event_maximum'] for e in events)[-2])
    center,scale=fit_channels(values)
    np.savez_compressed(OUT/'calibration.npz',center=center,scale=scale)
    pd.DataFrame(events).to_csv(OUT/'normal_crossfit_events.csv',index=False)
    pd.DataFrame(dict(channel=channels,center=center,scale=scale)).to_csv(OUT/'channel_calibration.csv',index=False)
    protected=[ROOT/'src/hs_aerots/paired_replay.py',ROOT/'src/hs_aerots/replay_detection.py',
        ROOT/'src/hs_aerots/channel_gate.py',Path(__file__),ROOT/'configs/p15_channel_gate.yaml']
    protected+=list(SEAL.glob('*.npy'))+[SEAL/'feature_dictionary.csv',SEAL/'topic_module_mapping.csv',SEAL/'modules.json']
    protected+=[p for p in (ROOT/'reports/p14_within_flight_calibration').glob('*') if p.is_file()]
    protocol=dict(config=yaml.safe_load((ROOT/'configs/p15_channel_gate.yaml').read_text()),
        threshold=threshold,sealed_at_utc=datetime.now(timezone.utc).isoformat(),folds=folds,
        calibration_sha256=sha(OUT/'calibration.npz'),faults_used=False,transfer_data_used=False,
        detection_schedule='First three available windows; no onset gating or target self-calibration',
        scope='Previously examined transfer flights; exploratory, not independent confirmation',
        deployment_scale='All development normals; threshold from leave-source-out normals; limited-sample crossfit/deployment mismatch disclosed',
        protected_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in protected})
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2),encoding='utf-8')
    print(json.dumps(dict(threshold=threshold,normal_events=events),indent=2))

def verify():
    p=json.loads((OUT/'protocol.json').read_text())
    assert sha(OUT/'calibration.npz')==p['calibration_sha256']
    for path,digest in p['protected_sha256'].items():assert sha(ROOT/path)==digest,path
    return p

def predict():
    protocol=verify();assert not (OUT/'prediction_freeze.json').exists()
    topics,codes,modules,allocation,channels,fc,ct,noise=layout()
    fit=dict(np.load(OUT/'calibration.npz'))
    folder=OUT/'predictions';folder.mkdir(exist_ok=True)
    index=[]
    for dataset in ['development','transfer']:
        for i,p in enumerate(pairs(dataset)):
            v=channel_values(p['delta'],noise,fc,len(channels))
            new=predict_channels(v,fit['center'],fit['scale'],protocol['threshold'],ct,allocation)
            old=predict_paired(p['delta'],noise,codes,allocation,26.47158145904541)
            path=folder/f'{dataset}_{i:02d}.npz'
            np.savez_compressed(path,times=p['times'],**new,old_gate=old['gate'],old_ranks=old['ranks'])
            index.append({k:p[k] for k in ['dataset','group','run_id','source']}|
                dict(file=path.relative_to(OUT).as_posix(),sha256=sha(path)))
    pd.DataFrame(index).to_csv(OUT/'prediction_index.csv',index=False)
    (OUT/'prediction_freeze.json').write_text(json.dumps(dict(index_sha256=sha(OUT/'prediction_index.csv'),
        protocol_sha256=sha(OUT/'protocol.json'),truth_read=False),indent=2))
    print('48 targets predicted and sealed without labels/onset')

def score():
    protocol=verify()
    seal=json.loads((OUT/'prediction_freeze.json').read_text())
    assert sha(OUT/'prediction_index.csv')==seal['index_sha256']
    assert sha(OUT/'protocol.json')==seal['protocol_sha256']
    topics,codes,modules,allocation,channels,fc,ct,noise=layout()
    truth={d:pd.read_csv(paths(d)['reference_manifest'],sep='\t').set_index('run_id') for d in ['development','transfer']}
    rows=[];windows=[];ranking=[]
    for r in pd.read_csv(OUT/'prediction_index.csv').itertuples():
        path=OUT/r.file;assert sha(path)==r.sha256;p=dict(np.load(path));time=p['times'];post=time>=30
        condition='normal' if r.group=='normal' else 'fault'
        target=truth[r.dataset].loc[r.run_id,'ground_truth_module'] if condition=='fault' else None
        for method,gkey,rkey in [('original_primary','old_gate','old_ranks'),('channel_gate_fixed_rank','gate','old_ranks'),('channel_gate_new_rank','gate','ranks')]:
            gate=p[gkey];detected=bool((gate&post).any())
            rank=float(p[rkey][modules.index(target)]) if target and detected else np.inf
            rows.append(dict(dataset=r.dataset,source_log=r.source,run_id=r.run_id,condition=condition,
                mutation_id=truth[r.dataset].loc[r.run_id,'mutation_id'],method=method,detected=detected,
                any_alarm=bool(gate.any()),pre_onset_alarm=bool((gate&~post).any()),
                normal_post30_alarm=bool((gate&post).any()),first_alarm_s=float(time[gate][0]) if gate.any() else None,
                delay_s=float(time[gate&post][0]-30) if detected else None,observation_end_s=float(time[-1]),
                rank=rank if np.isfinite(rank) else None,**{f'top{k}':int(rank<=k) for k in [1,3,5]},mrr=1/rank if np.isfinite(rank) else 0))
        for i,t in enumerate(time):
            windows.append(dict(dataset=r.dataset,group=r.group,run_id=r.run_id,time_s=t,score=p['scores'][i],
                threshold=protocol['threshold'],alarm=bool(p['gate'][i]),strongest_channel=channels[int(p['channel_scores'][i].argmax())]))
        for j,m in enumerate(modules):ranking.append(dict(dataset=r.dataset,group=r.group,run_id=r.run_id,module=m,score=p['module_scores'][j],rank=p['ranks'][j]))
    frame=pd.DataFrame(rows);frame.to_csv(OUT/'results_by_run.csv',index=False)
    summaries=[]
    for (dataset,method),d in frame.groupby(['dataset','method']):
        f=d[d.condition=='fault'];n=d[d.condition=='normal'];normal=n.set_index('run_id').any_alarm.to_dict()
        clean=sum(r.detected and not r.pre_onset_alarm and not normal[r.run_id.rsplit('__',1)[0]+'__baseline'] for r in f.itertuples())
        summaries.append(dict(dataset=dataset,method=method,fault_runs=len(f),detected=int(f.detected.sum()),
            normal_alarms=int(n.any_alarm.sum()),normal_runs=len(n),pre_onset=int(f.pre_onset_alarm.sum()),
            clean_fault_only=int(clean),**{k:float(f[k].mean()) for k in ['top1','top3','top5','mrr']},
            delay_median_s=float(f.delay_s.median()),delay_max_s=float(f.delay_s.max())))
    pd.DataFrame(summaries).to_csv(OUT/'summary.csv',index=False)
    frame[frame.condition=='fault'].groupby(['dataset','method','mutation_id'])[['detected','top1','top3','top5','mrr','delay_s']].mean().to_csv(OUT/'by_mutation.csv')
    pd.DataFrame(windows).to_csv(OUT/'window_predictions.csv',index=False)
    pd.DataFrame(ranking).to_csv(OUT/'module_rankings.csv',index=False)
    print(pd.DataFrame(summaries).to_string(index=False))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['freeze','predict','score'],required=True)
    args=parser.parse_args();globals()[args.phase]()

if __name__=='__main__':main()
