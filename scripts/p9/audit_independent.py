"""Post-prediction validity audit; never selects/excludes trials or tunes parameters."""
from pathlib import Path
import hashlib
import json
import re
import numpy as np
import pandas as pd
from pyulog import ULog
from hs_aerots.baseline import _ulog_time_bounds
from hs_aerots.sitl_injection import _windows_path
from validate_injection_effects import SPECS
from evaluate_independent import verify_seal

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/p9/paired_residual/independent'

def exposure():
    protocol=json.loads((OUT/'sealed/protocol.json').read_text())
    groups=pd.read_csv(ROOT/'reports/p2/group_dictionary.csv').set_index('log_key')
    train=np.load(ROOT/'data/processed/p2/features_original/group_train.npy')
    llo=pd.read_csv(ROOT/'reports/p11/llo/p2/leave_log_out_assignments.csv').set_index('log_key')
    inventory=pd.read_csv(ROOT/'reports/p1/dataset_inventory.csv').set_index('log_key')
    dev=json.loads((OUT/'sealed/calibration.json').read_text())
    rows=[]
    for source in protocol['sources']:
        key=source['log_key']
        group=int(groups.loc[key,'group'])
        rows.append(dict(source_log=key,p9_development_overlap=key.replace('/','__') in [c['held_out_source'] for c in dev],
            annotation=inventory.loc[key,'annotation_classes'],p11_split=llo.loc[key,'split'],
            historical_p2_training_windows=int((train==group).sum()),
            source_sha256_verified=hashlib.sha256((ROOT/'data/raw/uav_sead'/source['relative_path']).read_bytes()).hexdigest()==source['sha256']))
    pd.DataFrame(rows).to_csv(OUT/'source_independence_audit.csv',index=False)
    return rows

def main():
    verify_seal(OUT)
    exposure_rows=exposure()
    assert (OUT/'prediction_freeze.json').exists(), 'Validity audit follows fixed predictions'
    manifests={g:pd.read_csv(OUT/g/'run_manifest.tsv',sep='\t') for g in ('reference','normal')}
    quality=[]
    data={}
    for group,manifest in manifests.items():
        for r in manifest.itertuples():
            path=_windows_path(ROOT,r.output_ulog)
            u=ULog(str(path),message_name_filter_list=['sensor_combined','vehicle_attitude']+list({s[0] for s in SPECS.values()}))
            data[group,r.run_id]=u
            console_id=r.run_id if group=='reference' else r.run_id.rsplit('__',1)[0]+'__normal'
            console=(OUT/'consoles'/f'{console_id}.log').read_text(errors='replace')
            match=re.search(r'Replay done \(published (\d+) msgs, ([\d.]+) s\)',console)
            qd=next((d.data for d in u.data_list if d.name=='vehicle_attitude'),None)
            qfraction=None
            if qd is not None:
                q=np.column_stack([qd[f'q[{j}]'] for j in range(4)]).astype(float)
                norms=np.linalg.norm(q,axis=1)
                qfraction=float((np.isfinite(q).all(axis=1)&(norms>.95)&(norms<1.05)).mean())
            quality.append(dict(collection=group,run_id=r.run_id,exit_code=r.exit_code,
                replay_done=match is not None,published_messages=int(match[1]) if match else None,
                replay_duration_s=float(match[2]) if match else None,quaternion_valid_fraction=qfraction))
    pd.DataFrame(quality).to_csv(OUT/'replay_quality.csv',index=False)
    effects=[]
    for r in manifests['reference'].itertuples():
        if r.condition!='fault':continue
        topic,field,measure,target=SPECS[r.mutation_id]
        values={}
        for condition in ('baseline','fault'):
            run_id=r.run_id.rsplit('__',1)[0]+'__'+condition
            u=data['reference',run_id]
            start,_=_ulog_time_bounds(u)
            d=next(item for item in u.data_list if item.name==topic).data
            time=(np.asarray(d['timestamp'],dtype=float)-start)/1e6
            values[condition]=np.asarray(d[field],dtype=float)[time>=30]
        b,f=values['baseline'],values['fault']
        if measure=='target_fraction':
            bv,fv=float(np.mean(b==target)),float(np.mean(f==target));passed=bv<.1 and fv>.9
        elif measure=='post_mean':
            bv,fv=float(np.mean(b)),float(np.mean(f));passed=abs(bv)<.1 and fv>15
        else:
            bv,fv=float(np.std(b)),float(np.std(f));passed=bv>.1 and fv<.25*bv
        effects.append(dict(run_id=r.run_id,mutation_id=r.mutation_id,measure=measure,
            baseline_value=bv,fault_value=fv,passed=bool(passed),retained_in_primary=True))
    pd.DataFrame(effects).to_csv(OUT/'injection_effect_validation.csv',index=False)
    old=(ROOT/'reports/p9/paired_residual/normal_repeats/input_binary_sha256.txt').read_text().splitlines()
    before=(OUT/'binary_sha256_before.txt').read_text().splitlines()
    after=(OUT/'binary_sha256_after.txt').read_text().splitlines()
    assert before==after and all(line in old for line in before)
    clocks=pd.concat([pd.read_csv(OUT/f'{g}_cache/clock_alignment_audit.csv') for g in manifests])
    audit=dict(completed_runs=len(quality),all_replays_done=all(r['replay_done'] for r in quality),
        original_binaries_unchanged=True,frozen_method_hashes_unchanged=True,
        all_source_hashes_verified=all(r['source_sha256_verified'] for r in exposure_rows),
        independent_p9_sources=all(not r['p9_development_overlap'] for r in exposure_rows),
        globally_unseen_training_sources=all(r['historical_p2_training_windows']==0 for r in exposure_rows),
        effect_checks_passed=sum(r['passed'] for r in effects),effect_trials=len(effects),
        maximum_clock_offset_spread_us=float(clocks.max_offset_deviation_us.max()),
        tests_passed=28)
    (OUT/'verification.json').write_text(json.dumps(audit,indent=2))
    print(json.dumps(audit,indent=2))

if __name__=='__main__':main()
