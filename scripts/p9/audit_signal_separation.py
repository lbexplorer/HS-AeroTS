"""Post-hoc diagnostic of retained signal; never fits or changes a detector."""
import json
import numpy as np
import pandas as pd
from evaluate_independent import DEFAULT,ROOT,mapping,sustained_score

def main():
    base=DEFAULT;seal=base/'sealed'
    topics,_,_,_=mapping(seal)
    fd=pd.read_csv(seal/'feature_dictionary.csv')
    noise=np.load(seal/'noise_2019-01-18__08_39_38.npy')
    index=pd.read_csv(base/'prediction_index.csv');index=index[index.primary]
    rows=[]
    for r in index.itertuples():
        p=dict(np.load(base/r.prediction_file));time=p['times'];post=time+float(p['clock_offset'])>=30
        for topic in ['vehicle_status','ekf2_innovations','vehicle_local_position','vehicle_land_detected']:
            rows.append(dict(group=r.group,run_id=r.run_id,signal=topic,
                sustained_max=float(sustained_score(p['topics'][post,topics.index(topic)],3).max())))
        target=dict(np.load(base/f'{r.group}_cache/cache/{r.run_id}.npz'))
        ref=dict(np.load(base/f'reference_cache/cache/{r.reference_id}.npz'))
        pick=fd.channel.eq('vehicle_local_position.z').to_numpy()
        delta=np.abs(target['features'][np.isin(target['times'],time)][:,pick]-np.column_stack([
            np.interp(time,ref['times'],ref['features'][:,j]) for j in np.flatnonzero(pick)]))/noise[pick]
        rows.append(dict(group=r.group,run_id=r.run_id,signal='vehicle_local_position.z',
            sustained_max=float(sustained_score(delta[post].max(axis=1),3).max())))
    frame=pd.DataFrame(rows)
    out=ROOT/'reports/p15_topic_calibration_plan'
    frame.to_csv(out/'signal_separation_diagnostic.csv',index=False)
    summary=[]
    for mutation,signal in [('commander_nav_state_override','vehicle_status'),('ekf2_innovation_bias','ekf2_innovations'),
                            ('inav_local_z_freeze','vehicle_local_position.z'),('land_detector_state_inversion','vehicle_land_detected')]:
        normals=frame[(frame.group=='normal')&(frame.signal==signal)]
        faults=frame[(frame.group=='reference')&(frame.signal==signal)&frame.run_id.str.startswith(mutation+'__')]
        summary.append(dict(mutation=mutation,signal=signal,all_normal_max=float(normals.sustained_max.max()),
                            fault_min=float(faults.sustained_max.min()),fault_max=float(faults.sustained_max.max())))
    (out/'signal_separation_summary.json').write_text(json.dumps(dict(
        scope='Post-30s retrospective mechanism diagnostic; selected known affected signals for explanation only; not detector performance or proposed thresholds',
        rows=summary),indent=2),encoding='utf-8')
    print(pd.DataFrame(summary).to_string(index=False))

if __name__=='__main__':main()
