"""Inference with sealed parameters; a separate scoring pass reads fault truth.

No fitting is permitted here. Predictions are serialized and hashed before scoring.
"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
import pandas as pd
from hs_aerots.paired_replay import matched_difference, predict_paired, sustained_score
from hs_aerots.sitl_injection import _windows_path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / 'reports/p9/paired_residual/independent'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def verify_seal(base):
    expected = json.loads((base / 'sealed/sha256.json').read_text())
    for rel, digest in expected.items():
        assert sha(ROOT / rel) == digest, f'Frozen input changed: {rel}'
    return expected

def mapping(seal):
    fd = pd.read_csv(seal / 'feature_dictionary.csv')
    topics = list(dict.fromkeys(fd.topic))
    codes = fd.topic.map({t:i for i,t in enumerate(topics)}).to_numpy(int)
    modules = json.loads((seal / 'modules.json').read_text())
    edges = pd.read_csv(seal / 'topic_module_mapping.csv')
    allocation = np.zeros((len(topics), len(modules)))
    for i, topic in enumerate(topics):
        mapped = edges.loc[edges.topic.eq(topic) & edges.role.eq('publisher'), 'module'].unique()
        for module in mapped: allocation[i,modules.index(module)] = 1 / len(mapped)
    assert len(modules) == 54 and len(codes) == 87*18
    return topics, codes, modules, allocation

def infer_pair(target, reference, target_end, reference_end, noise, codes, allocation, threshold):
    # Only observables and frozen parameters cross this prediction boundary.
    delta, times, valid = matched_difference(target['features'], target['times'],
        reference['features'], reference['times'], target_end, reference_end)
    if len(times) < 3: raise ValueError('Insufficient joint sensor support')
    prediction = predict_paired(delta, noise, codes, allocation, threshold, consecutive=3)
    prediction['times'] = times
    prediction['clock_offset'] = float(target.get('clock_origin_from_header_s', 0.))
    prediction['residual_maximum'] = float(sustained_score(prediction['scores'],3).max())
    return prediction

def inference(base):
    verify_seal(base)
    seal = base / 'sealed'
    protocol = json.loads((seal / 'protocol.json').read_text())
    topics, codes, modules, allocation = mapping(seal)
    # Restrict manifest access to transport/pairing fields; no truth columns.
    columns = ['run_id','output_ulog']
    refs = pd.read_csv(base / 'reference/run_manifest.tsv', sep='\t', usecols=columns)
    normal = pd.read_csv(base / 'normal/run_manifest.tsv', sep='\t', usecols=columns)
    assert len(refs)==24 and len(normal)==12
    source_ids = {s['log_key'].replace('/','__') for s in protocol['sources']}
    assert {'__'.join(r.split('__')[1:3]) for r in refs.run_id} == source_ids
    cache = {}
    ends = {}
    for group, frame in [('reference',refs),('normal',normal)]:
        root = base / f'{group}_cache'
        cover = pd.read_csv(root / 'topic_time_coverage.csv')
        ends[group] = cover[cover.topic.eq('sensor_combined')].set_index('run_id').last_s.to_dict()
        cache[group] = {r:dict(np.load(root/'cache'/f'{r}.npz')) for r in frame.run_id}
    dest = base/'predictions'
    dest.mkdir(exist_ok=True)
    refs = refs.set_index('run_id')
    jobs = []
    for group, frame in [('reference', refs.reset_index()),('normal',normal)]:
        for row in frame.itertuples():
            if group=='reference' and row.run_id.endswith('__baseline'): continue
            ref_id = row.run_id.rsplit('__',1)[0]+'__baseline'
            target_path = _windows_path(ROOT, row.output_ulog)
            reference_path = _windows_path(ROOT, refs.loc[ref_id,'output_ulog'])
            target_hash, ref_hash = sha(target_path), sha(reference_path)
            assert target_path.resolve()!=reference_path.resolve() and target_hash!=ref_hash
            jobs.append((group,row.run_id,ref_id,target_hash,ref_hash))
    records=[]
    for calibration in json.loads((seal/'calibration.json').read_text()):
        key=calibration['held_out_source']
        noise=np.load(seal/f'noise_{key}.npy')
        threshold=calibration['threshold']
        for i,(group,run_id,ref_id,target_hash,ref_hash) in enumerate(jobs):
            p=infer_pair(cache[group][run_id], cache['reference'][ref_id],
                ends[group][run_id], ends['reference'][ref_id],noise,codes,allocation,threshold)
            path=dest/f'{key}__pair{i:02d}.npz'
            np.savez_compressed(path,**p)
            records.append(dict(calibration=key,primary=key==protocol['primary_calibration'],
                group=group,run_id=run_id,reference_id=ref_id,threshold=threshold,
                target_sha256=target_hash,reference_sha256=ref_hash,
                prediction_file=path.relative_to(base).as_posix(),prediction_sha256=sha(path)))
    pd.DataFrame(records).to_csv(base/'prediction_index.csv',index=False)
    (base/'prediction_freeze.json').write_text(json.dumps(dict(
        prediction_index_sha256=sha(base/'prediction_index.csv'),
        evaluator_sha256=sha(Path(__file__)),truth_accessed_by_inference=False),indent=2))
    print(f'Serialized {len(records)} fixed-parameter predictions before scoring')

def metrics(frame):
    faults=frame[frame.condition.eq('fault')]; normal=frame[frame.condition.eq('normal')]
    delays=faults.loc[faults.detected,'detection_delay_s']
    normal_alarms=normal.set_index('run_id').any_alarm.to_dict()
    clean=[bool(r.detected and not r.pre_onset_alarm and not normal_alarms[r.run_id.rsplit('__',1)[0]+'__baseline']) for r in faults.itertuples()]
    return dict(fault_runs=len(faults),detected_runs=int(faults.detected.sum()),
        detector_recall=float(faults.detected.mean()),normal_runs=len(normal),
        normal_false_alarm_runs=int(normal.any_alarm.sum()),normal_false_alarm_rate=float(normal.any_alarm.mean()),
        normal_source_flights=int(normal.source_log.nunique()),normal_false_alarm_source_flights=int(normal.loc[normal.any_alarm,'source_log'].nunique()),
        fault_pre_onset_alarm_runs=int(faults.pre_onset_alarm.sum()),clean_fault_only_detected_runs=sum(clean),
        **{k:float(faults[k].mean()) for k in ['top1','top3','top5','mrr']},
        delay_detected_n=len(delays),misses=len(faults)-len(delays),
        delay_median_s=float(delays.median()),delay_min_s=float(delays.min()),delay_max_s=float(delays.max()))

def score(base):
    verify_seal(base)
    index_path=base/'prediction_index.csv'
    assert sha(index_path)==json.loads((base/'prediction_freeze.json').read_text())['prediction_index_sha256']
    index=pd.read_csv(index_path)
    topics,_,modules,_=mapping(base/'sealed')
    # Only this pass joins mutation labels, module truth and onset for evaluation.
    truth=pd.read_csv(base/'reference/run_manifest.tsv',sep='\t').set_index('run_id')
    onset=json.loads((base/'sealed/protocol.json').read_text())['onset_evaluation_only_s']
    rows=[]; rankings=[]; windows=[]
    for item in index.itertuples():
        path=base/item.prediction_file
        assert sha(path)==item.prediction_sha256
        p=dict(np.load(path));gate=p['gate'];times=p['times']+float(p['clock_offset']);post=times>=onset
        condition='normal' if item.group=='normal' else 'fault'
        detected=bool((gate&post).any()); alarm=bool(gate.any())
        target=truth.loc[item.run_id,'ground_truth_module'] if condition=='fault' else None
        rank=float(p['ranks'][modules.index(target)]) if target is not None and detected else np.inf
        rows.append(dict(calibration=item.calibration,primary=item.primary,run_id=item.run_id,
            source_log='__'.join(item.run_id.split('__')[1:3]),condition=condition,
            mutation_id=truth.loc[item.run_id,'mutation_id'],threshold=item.threshold,
            any_alarm=alarm,detected=detected,pre_onset_alarm=bool((gate&~post).any()),
            first_alarm_s=float(times[gate][0]) if alarm else None,
            detection_delay_s=float(times[gate&post][0]-onset) if detected else None,
            observation_end_s=float(times[-1]),residual_maximum=float(p['residual_maximum']),
            strongest_topic=topics[int(p['topic_evidence'].argmax())] if alarm else None,
            ground_truth_rank=rank if np.isfinite(rank) else None,
            **{f'top{k}':int(rank<=k) for k in (1,3,5)},mrr=1/rank if np.isfinite(rank) else 0.))
        for j,module in enumerate(modules): rankings.append(dict(calibration=item.calibration,group=item.group,
            run_id=item.run_id,module=module,score=float(p['module_scores'][j]),rank=float(p['ranks'][j])))
        for i,t in enumerate(times): windows.append(dict(calibration=item.calibration,group=item.group,
            run_id=item.run_id,time_s=t,score=p['scores'][i],threshold=item.threshold,alarm=bool(gate[i]),
            strongest_topic=topics[int(p['topics'][i].argmax())]))
    frame=pd.DataFrame(rows)
    frame.to_csv(base/'results_by_run.csv',index=False)
    summary=pd.DataFrame([dict(calibration=k,primary=bool(d.primary.iloc[0]),**metrics(d)) for k,d in frame.groupby('calibration')])
    summary.to_csv(base/'summary.csv',index=False)
    pd.DataFrame([dict(calibration=k,mutation_id=m,**metrics(d)) for (k,m),d in frame.groupby(['calibration','mutation_id'])]).to_csv(base/'by_mutation.csv',index=False)
    pd.DataFrame([dict(calibration=k,source_log=s,**metrics(d)) for (k,s),d in frame.groupby(['calibration','source_log'])]).to_csv(base/'by_source.csv',index=False)
    pd.DataFrame(rankings).to_csv(base/'module_rankings.csv',index=False)
    pd.DataFrame(windows).to_csv(base/'window_predictions.csv',index=False)
    print(summary.to_string(index=False))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base',type=Path,default=DEFAULT)
    parser.add_argument('--phase',choices=['predict','score'],required=True)
    args=parser.parse_args()
    (inference if args.phase=='predict' else score)(args.base)

if __name__=='__main__':main()
