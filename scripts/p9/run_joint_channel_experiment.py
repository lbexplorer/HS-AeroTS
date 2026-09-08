"""Same frozen channel calibration rule, with the audited joint-support frontend."""
import argparse
import json
import numpy as np
import pandas as pd
import run_channel_experiment as experiment

OUT=experiment.ROOT/'reports/p15_joint_support'

def pairs(dataset,normal_only=False):
    frame=pd.read_csv(OUT/'cache_index.csv')
    frame=frame[frame.dataset.eq(dataset)]
    if normal_only:frame=frame[frame.group.eq('normal')]
    for r in frame.itertuples():
        data=dict(np.load(OUT/r.file))
        yield dict(dataset=dataset,group=r.group,run_id=r.run_id,source=r.source,
            delta=data['delta'],times=data['times'])

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['freeze','predict','score'],required=True)
    args=parser.parse_args();experiment.OUT=OUT;experiment.pairs=pairs
    getattr(experiment,args.phase)()
    if args.phase=='freeze':
        # Seal the additional frontend before any new target predictions.
        path=OUT/'protocol.json';p=json.loads(path.read_text())
        p['frontend']='Shared packet support with channel validity; full-channel coverage reported separately'
        for f in [experiment.ROOT/'scripts/p9/build_joint_replay_cache.py',experiment.ROOT/'scripts/p9/run_joint_channel_experiment.py',OUT/'frontend_spec.json',OUT/'cache_index.csv']:
            p['protected_sha256'][f.relative_to(experiment.ROOT).as_posix()]=experiment.sha(f)
        path.write_text(json.dumps(p,indent=2),encoding='utf-8')

if __name__=='__main__':main()
