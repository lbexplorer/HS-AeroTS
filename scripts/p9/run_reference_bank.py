"""Freeze using new development healthy targets; no transfer fitting."""
import argparse
from pathlib import Path
import json
from datetime import datetime,timezone
import numpy as np
import pandas as pd
import yaml
import run_channel_experiment as common
from hs_aerots.channel_gate import persistent_channels,predict_channels

ROOT=common.ROOT
OUT=ROOT/'reports/p15_reference_bank'

def freeze():
    assert not (OUT/'protocol.json').exists()
    idx=pd.read_csv(OUT/'cache_index.csv');idx=idx[idx.dataset.eq('development')&idx.group.eq('normal')]
    assert len(idx)==12
    events=[]
    for r in idx.itertuples():
        p=dict(np.load(OUT/r.file))
        events.append(dict(run_id=r.run_id,source=r.source,event_maximum=float(persistent_channels(p['values']).max())))
    threshold=max(1.,sorted(e['event_maximum'] for e in events)[-2])
    pd.DataFrame(events).to_csv(OUT/'normal_calibration_events.csv',index=False)
    np.savez_compressed(OUT/'calibration.npz',center=np.zeros(87),scale=np.ones(87))
    files=[Path(__file__),ROOT/'scripts/p9/prepare_reference_bank.py',ROOT/'src/hs_aerots/reference_bank.py',
        ROOT/'src/hs_aerots/channel_gate.py',ROOT/'configs/p15_reference_bank.yaml',
        ROOT/'scripts/p9/build_joint_replay_cache.py',OUT/'cache_index.csv',OUT/'preregistered_protocol.yaml']
    files+=list((ROOT/'reports/p14_within_flight_calibration').glob('*.json'))
    p=dict(threshold=threshold,calibration_sha256=common.sha(OUT/'calibration.npz'),
        sealed_at_utc=datetime.now(timezone.utc).isoformat(),
        config=yaml.safe_load((ROOT/'configs/p15_reference_bank.yaml').read_text()),
        faults_used=False,transfer_targets_used=False,target_self_fit=False,
        normal_reference_budget='Two existing independent healthy references; newly executed third healthy replay is the held-out target',
        scope='Fresh normal repeats but previously examined source flights and faults; not unseen-flight confirmation',
        protected_sha256={f.relative_to(ROOT).as_posix():common.sha(f) for f in files})
    (OUT/'protocol.json').write_text(json.dumps(p,indent=2),encoding='utf-8')
    print(json.dumps(dict(threshold=threshold,normal_events=events),indent=2))

def predict():
    common.OUT=OUT;protocol=common.verify()
    assert not (OUT/'prediction_freeze.json').exists()
    topics,codes,modules,allocation,channels,fc,ct,noise=common.layout()
    folder=OUT/'predictions';folder.mkdir(exist_ok=True);rows=[]
    for i,r in enumerate(pd.read_csv(OUT/'cache_index.csv').itertuples()):
        p=dict(np.load(OUT/r.file))
        prediction=predict_channels(p['values'],np.zeros(87),np.ones(87),protocol['threshold'],ct,allocation)
        destination=folder/f'pair{i:02d}.npz'
        np.savez_compressed(destination,**prediction,times=p['times'],old_gate=p['old_gate'],old_ranks=p['old_ranks'])
        rows.append(dict(dataset=r.dataset,group=r.group,run_id=r.run_id,source=r.source,
            file=destination.relative_to(OUT).as_posix(),sha256=common.sha(destination)))
    pd.DataFrame(rows).to_csv(OUT/'prediction_index.csv',index=False)
    (OUT/'prediction_freeze.json').write_text(json.dumps(dict(index_sha256=common.sha(OUT/'prediction_index.csv'),
        protocol_sha256=common.sha(OUT/'protocol.json'),truth_read=False),indent=2))
    print('48 bank targets predicted and sealed')

def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['freeze','predict','score'],required=True)
    args=p.parse_args();common.OUT=OUT
    if args.phase=='score':common.score()
    else:globals()[args.phase]()

if __name__=='__main__':main()
