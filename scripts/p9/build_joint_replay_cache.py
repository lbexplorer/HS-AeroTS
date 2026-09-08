"""Recompute existing paired features on shared packet support; no new replay.

No channel or topic is selected by mutation. Exact packet timestamp overlap is
used when at least half the shorter stream is shared; regenerated streams retain
their own timestamps. Window validity requires both streams to cover the window.
"""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json
import numpy as np
import pandas as pd
from pyulog import ULog
from hs_aerots.baseline import descriptor_batch,window_count
from hs_aerots.sitl_injection import _windows_path
from run_channel_experiment import ROOT,SEAL,layout,paths

OUT=ROOT/'reports/p15_joint_support'

def supported_interp(grid,ts,values):
    good=np.isfinite(values)
    ts=ts[good];values=values[good]
    ts,indices=np.unique(ts,return_index=True);values=values[indices]
    if len(ts)<2:return np.zeros(len(grid)),np.zeros(len(grid),bool)
    vals=np.interp(grid,ts,values)
    right=np.clip(np.searchsorted(ts,grid,side='right'),1,len(ts)-1);left=right-1
    gap_limit=max(.1,5.*float(np.median(np.diff(ts))))
    valid=(grid>=ts[0])&(grid<=ts[-1])&((ts[right]-ts[left])<=gap_limit)
    return vals,valid

def build_pair(target,reference,origin_target,origin_ref,channels,mean,std):
    topic_names=list(dict.fromkeys(c.split('.',1)[0] for c in channels))
    logs=[ULog(str(p),message_name_filter_list=topic_names) for p in [target,reference]]
    data=[]
    for log in logs:
        datasets={}
        for d in log.data_list:
            if d.name not in datasets:datasets[d.name]=d.data
        data.append(datasets)
    origins=[origin_target,origin_ref]
    end=min((data[i]['sensor_combined']['timestamp'].astype(np.int64)[-1]-origins[i])/1e6 for i in range(2))
    grid=np.arange(int(np.floor(end*10))+1)/10
    aligned=[np.zeros((len(grid),len(channels)),np.float32) for _ in range(2)]
    valid=np.zeros_like(aligned[0],bool);diagnostics=[]
    for topic in topic_names:
        if any(topic not in d for d in data):continue
        ds=[d[topic] for d in data]
        ts=[ds[i]['timestamp'].astype(np.int64)-origins[i] for i in range(2)]
        common,ia,ib=np.intersect1d(ts[0],ts[1],return_indices=True)
        fraction=len(common)/max(1,min(len(ts[0]),len(ts[1])))
        shared=fraction>=.5 and len(common)>=2
        indices=[ia,ib] if shared else [np.arange(len(t)) for t in ts]
        clocks=[common/1e6,common/1e6] if shared else [t/1e6 for t in ts]
        diagnostics.append(dict(topic=topic,shared_fraction=fraction,shared_packets_used=shared))
        for j,channel in enumerate(channels):
            name,field=channel.split('.',1)
            if name!=topic or any(field not in d for d in ds):continue
            masks=[]
            for i in range(2):
                vals,mask=supported_interp(grid,clocks[i],np.asarray(ds[i][field],float)[indices[i]])
                aligned[i][:,j]=vals;masks.append(mask)
            valid[:,j]=masks[0]&masks[1]
    count=window_count(len(grid),96,12,8)
    starts=np.arange(count)*8;axis=starts[:,None]+np.arange(96)
    if count<3:raise ValueError('Too little common support')
    features=[descriptor_batch(((x-mean)/std)[axis]) for x in aligned]
    channel_valid=valid[axis].all(axis=1)
    delta=np.abs(features[0]-features[1]).astype(float)
    delta[:,~np.tile(channel_valid.any(axis=0),18)]=0
    delta*=np.tile(channel_valid,(1,18))
    # Origin-to-header offset retained solely as the evaluation clock convention.
    times=(starts+96)/10+(origin_target-int(logs[0].start_timestamp))/1e6
    return dict(delta=delta,times=times,channel_valid=channel_valid),diagnostics

def main():
    OUT.mkdir(exist_ok=True);folder=OUT/'cache';folder.mkdir(exist_ok=True)
    spec=OUT/'frontend_spec.json'
    assert not (OUT/'cache_index.csv').exists(),'Do not overwrite cache'
    spec.write_text(json.dumps(dict(sealed_at_utc=datetime.now(timezone.utc).isoformat(),
        source='Existing 72 replay outputs; unchanged raw data',shared_fraction_min=.5,
        gap_rule='max(0.1 s, 5 times median gap), both streams must support all 96 window samples',
        missing_channel='No evidence; invalid channel windows explicitly recorded, fault denominators retained',
        descriptors='Original 18 unchanged',selection='All 87 channels, no mutation/GT/onset input'),indent=2))
    channels=layout()[4]
    mean=np.load(SEAL/'scaler_mean.npy');std=np.load(SEAL/'scaler_std.npy')
    index=[];quality=[];topic_rows=[];hashes={}
    for dataset in ['development','transfer']:
        pp=paths(dataset)
        manifests={g:pd.read_csv(pp[f'{g}_manifest'],sep='\t',usecols=['run_id','output_ulog']).set_index('run_id') for g in ['reference','normal']}
        clocks={g:pd.read_csv(pp[f'{g}_cache']/'clock_alignment_audit.csv').set_index('run_id') for g in ['reference','normal']}
        for group in ['normal','reference']:
            for rid,row in manifests[group].iterrows():
                if group=='reference' and rid.endswith('__baseline'):continue
                ref_id=rid.rsplit('__',1)[0]+'__baseline'
                a=_windows_path(ROOT,row.output_ulog);b=_windows_path(ROOT,manifests['reference'].loc[ref_id,'output_ulog'])
                for p in [a,b]:
                    if str(p) not in hashes:hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
                assert hashes[str(a)]!=hashes[str(b)]
                result,diagnostics=build_pair(a,b,int(clocks[group].loc[rid,'origin_us']),
                    int(clocks['reference'].loc[ref_id,'origin_us']),channels,mean,std)
                destination=folder/f'{dataset}_{group}_{rid}.npz';np.savez_compressed(destination,**result)
                index.append(dict(dataset=dataset,group=group,run_id=rid,source='__'.join(rid.split('__')[1:3]),file=destination.relative_to(OUT).as_posix()))
                for j,c in enumerate(channels):quality.append(dict(dataset=dataset,group=group,run_id=rid,channel=c,
                    windows=len(result['times']),valid_windows=int(result['channel_valid'][:,j].sum())))
                for q in diagnostics:topic_rows.append(dict(dataset=dataset,group=group,run_id=rid,**q))
                print(f'Cached {dataset} {group} {rid}',flush=True)
    pd.DataFrame(index).to_csv(OUT/'cache_index.csv',index=False)
    pd.DataFrame(quality).to_csv(OUT/'channel_coverage.csv',index=False)
    pd.DataFrame(topic_rows).to_csv(OUT/'packet_support.csv',index=False)
    (OUT/'raw_input_sha256.json').write_text(json.dumps(hashes,indent=2))

if __name__=='__main__':main()
