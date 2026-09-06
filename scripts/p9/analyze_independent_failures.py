"""Post-test diagnostics only. Does not alter sealed predictions or fit parameters."""
from pathlib import Path
import numpy as np
import pandas as pd
from pyulog import ULog
from evaluate_independent import DEFAULT,ROOT,mapping,sustained_score
from hs_aerots.sitl_injection import _windows_path

def main():
    base=DEFAULT;seal=base/'sealed';out=base.parent/'optimization_audit';out.mkdir(exist_ok=True)
    topics,codes,modules,allocation=mapping(seal)
    noise=np.load(seal/'noise_2019-01-18__08_39_38.npy')
    index=pd.read_csv(base/'prediction_index.csv');index=index[index.primary]
    fd=pd.read_csv(seal/'feature_dictionary.csv');rows=[];topicrows=[]
    for r in index.itertuples():
        t=dict(np.load(base/f'{r.group}_cache/cache/{r.run_id}.npz'))
        b=dict(np.load(base/f'reference_cache/cache/{r.reference_id}.npz'))
        p=dict(np.load(base/r.prediction_file));tt=p['times']
        delta=np.abs(t['features'][np.isin(t['times'],tt)]-np.column_stack([
            np.interp(tt,b['times'],b['features'][:,j]) for j in range(len(noise))]))
        v=delta/noise
        peak=np.array([sustained_score(v[:,j],3).max() for j in range(len(noise))])
        for j in np.argsort(peak)[-5:][::-1]:
            rows.append(dict(group=r.group,run_id=r.run_id,feature=fd.feature.iloc[j],sustained_max=peak[j],noise=noise[j]))
        for i,topic in enumerate(topics):
            topicrows.append(dict(group=r.group,run_id=r.run_id,topic=topic,
                sustained_max=float(sustained_score(p['topics'][:,i],3).max()),
                evidence=float(p['topic_evidence'][i])))
    pd.DataFrame(rows).to_csv(out/'feature_drivers.csv',index=False)
    pd.DataFrame(topicrows).to_csv(out/'topic_evidence.csv',index=False)
    normal=pd.read_csv(base/'normal/run_manifest.tsv',sep='\t').set_index('run_id')
    ref=pd.read_csv(base/'reference/run_manifest.tsv',sep='\t').set_index('run_id')
    clocks={g:pd.read_csv(base/f'{g}_cache/clock_alignment_audit.csv').set_index('run_id') for g in ['normal','reference']}
    specs={'vehicle_attitude':['rollspeed','pitchspeed','yawspeed'],
           'sensor_combined':['gyro_rad[0]','accelerometer_m_s2[0]']}
    raw=[]
    for rid in normal.index:
        u={g:ULog(str(_windows_path(ROOT,m.loc[rid,'output_ulog'])),message_name_filter_list=list(specs))
           for g,m in [('normal',normal),('reference',ref)]}
        for topic,fields in specs.items():
            ds={g:next(d.data for d in log.data_list if d.name==topic) for g,log in u.items()}
            ts={g:d['timestamp'].astype(np.int64)-int(clocks[g].loc[rid,'origin_us']) for g,d in ds.items()}
            common,ni,ri=np.intersect1d(ts['normal'],ts['reference'],return_indices=True)
            for field in fields:
                diff=np.abs(ds['normal'][field][ni].astype(float)-ds['reference'][field][ri].astype(float))
                raw.append(dict(run_id=rid,topic=topic,field=field,normal_samples=len(ts['normal']),
                    reference_samples=len(ts['reference']),common_timestamps=len(common),
                    common_value_exact_fraction=float((diff==0).mean()) if len(diff) else None,
                    common_max_absolute_delta=float(diff.max()) if len(diff) else None,
                    normal_max_gap_ms=float(np.diff(ts['normal']).max()/1000),
                    reference_max_gap_ms=float(np.diff(ts['reference']).max()/1000)))
    pd.DataFrame(raw).to_csv(out/'passthrough_sample_audit.csv',index=False)
    print(pd.DataFrame(raw).groupby('topic')[['common_value_exact_fraction','normal_max_gap_ms','reference_max_gap_ms']].agg(['min','max']).to_string())
    print(pd.DataFrame(topicrows).query("group=='reference' and topic=='vehicle_local_position'").to_string(index=False))

if __name__=='__main__':main()
