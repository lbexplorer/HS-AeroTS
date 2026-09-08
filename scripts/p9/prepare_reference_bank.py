"""Prepare bank targets using two existing healthy replays and a new healthy test."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from pyulog import ULog
from build_joint_replay_cache import build_pair
from run_channel_experiment import ROOT,SEAL,layout,paths
from hs_aerots.paired_replay import predict_paired
from hs_aerots.channel_gate import channel_values
from hs_aerots.reference_bank import bank_scale,nearest_reference
from hs_aerots.replay_clock import estimate_origin
from hs_aerots.sitl_injection import _windows_path

OUT=ROOT/'reports/p15_reference_bank'
JOINT=ROOT/'reports/p15_joint_support'

def clock(path,rid):
    source='__'.join(rid.split('__')[1:3]);date,time=source.split('__')
    a=ULog(str(ROOT/'data/raw/uav_sead/ulg_files'/date/(time+'.ulg')),message_name_filter_list=['sensor_combined'])
    b=ULog(str(path),message_name_filter_list=['sensor_combined'])
    aa=next(d.data for d in a.data_list if d.name=='sensor_combined')
    bb=next(d.data for d in b.data_list if d.name=='sensor_combined')
    fields=[f'{kind}[{i}]' for kind in ['gyro_rad','accelerometer_m_s2'] for i in range(3)]
    return estimate_origin(aa['timestamp'],np.column_stack([aa[f] for f in fields]),
        bb['timestamp'],np.column_stack([bb[f] for f in fields]),a.start_timestamp)

def main():
    assert not (OUT/'cache_index.csv').exists()
    folder=OUT/'cache';folder.mkdir(exist_ok=True)
    topics,codes,modules,allocation,channels,fc,ct,noise=layout()
    mean=np.load(SEAL/'scaler_mean.npy');std=np.load(SEAL/'scaler_std.npy')
    fresh=pd.read_csv(OUT/'healthy_repeats/run_manifest.tsv',sep='\t',usecols=['run_id','output_ulog']).set_index('run_id')
    assert len(fresh)==24
    index=[];quality=[];identities=[];clocks=[]
    for dataset in ['development','transfer']:
        pp=paths(dataset)
        manifests={g:pd.read_csv(pp[f'{g}_manifest'],sep='\t',usecols=['run_id','output_ulog']).set_index('run_id') for g in ['normal','reference']}
        origins={g:pd.read_csv(pp[f'{g}_cache']/'clock_alignment_audit.csv').set_index('run_id').origin_us.to_dict() for g in ['normal','reference']}
        for baseline in manifests['normal'].index:
            r0=_windows_path(ROOT,manifests['reference'].loc[baseline,'output_ulog'])
            r1=_windows_path(ROOT,manifests['normal'].loc[baseline,'output_ulog'])
            bank=dict(np.load(JOINT/'cache'/f'{dataset}_normal_{baseline}.npz'))
            healthy_distance=channel_values(bank['delta'],noise,fc,len(channels))
            scale,count=bank_scale(healthy_distance,bank['channel_valid'])
            np.savez_compressed(folder/f'bank_{dataset}_{baseline}.npz',scale=scale,count=count)
            for group in ['normal','reference']:
                rid=baseline if group=='normal' else baseline.rsplit('__',1)[0]+'__fault'
                target=_windows_path(ROOT,fresh.loc[baseline,'output_ulog']) if group=='normal' else _windows_path(ROOT,manifests['reference'].loc[rid,'output_ulog'])
                th,r0h,r1h=[hashlib.sha256(p.read_bytes()).hexdigest() for p in [target,r0,r1]]
                assert len({th,r0h,r1h})==3
                if group=='normal':
                    origin,audit=clock(target,rid);clocks.append(dict(dataset=dataset,run_id=rid,**audit))
                    first,_=build_pair(target,r0,origin,int(origins['reference'][baseline]),channels,mean,std)
                else:
                    origin=int(origins['reference'][rid])
                    first=dict(np.load(JOINT/'cache'/f'{dataset}_reference_{rid}.npz'))
                second,_=build_pair(target,r1,origin,int(origins['normal'][baseline]),channels,mean,std)
                times,ia,ib=np.intersect1d(first['times'],second['times'],return_indices=True)
                assert len(times)>=3
                v0=channel_values(first['delta'][ia],noise,fc,len(channels))
                v1=channel_values(second['delta'][ib],noise,fc,len(channels))
                values,valid=nearest_reference(v0,v1,first['channel_valid'][ia],second['channel_valid'][ib],scale)
                old=predict_paired(first['delta'][ia],noise,codes,allocation,26.47158145904541)
                destination=folder/f'{dataset}_{group}_{rid}.npz'
                np.savez_compressed(destination,values=values,times=times,valid=valid,old_gate=old['gate'],old_ranks=old['ranks'])
                index.append(dict(dataset=dataset,group=group,run_id=rid,source='__'.join(rid.split('__')[1:3]),file=destination.relative_to(OUT).as_posix()))
                identities.append(dict(dataset=dataset,group=group,run_id=rid,target_sha256=th,reference0_sha256=r0h,reference1_sha256=r1h))
                for j,c in enumerate(channels):quality.append(dict(dataset=dataset,group=group,run_id=rid,channel=c,
                    windows=len(times),valid_windows=int(valid[:,j].sum()),bank_normal_windows=int(count[j])))
                print(f'Prepared {dataset} {group} {rid}',flush=True)
    pd.DataFrame(index).to_csv(OUT/'cache_index.csv',index=False)
    pd.DataFrame(quality).to_csv(OUT/'channel_coverage.csv',index=False)
    pd.DataFrame(identities).to_csv(OUT/'independent_target_identity.csv',index=False)
    pd.DataFrame(clocks).to_csv(OUT/'healthy_clock_alignment.csv',index=False)

if __name__=='__main__':main()
