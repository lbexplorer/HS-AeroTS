"""Read-only model/data audit; cache P9 inference without consulting fault truth."""
from pathlib import Path
import argparse
import hashlib
import json
import joblib
import numpy as np
import pandas as pd
from pyulog import ULog
from hs_aerots.baseline import TOPIC_FIELDS, _ulog_time_bounds
from hs_aerots.replay_clock import estimate_origin
from hs_aerots.sitl_injection import (_windows_from_ulog, _windows_path,
    _allocation_matrix, _windows_to_modules, load_config)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'reports/p9/stage1_reassessment'

def main():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='configs/p9_sitl_injection.yaml')
    parser.add_argument('--output', default='reports/p9/stage1_reassessment')
    parser.add_argument('--manifest', default=None)
    parser.add_argument('--preserve-header-start', action='store_true')
    parser.add_argument('--source-clock', action='store_true')
    args = parser.parse_args()
    OUT = ROOT / args.output
    OUT.mkdir(parents=True, exist_ok=True)
    cache = OUT / 'cache'
    cache.mkdir(exist_ok=True)
    c = load_config(ROOT / args.config)['paths']
    if args.manifest:
        c['run_manifest'] = args.manifest
    channels = (ROOT / c['core_channels']).read_text().splitlines()
    mean, std = (np.load(ROOT / c[k]) for k in ('scaler_mean', 'scaler_std'))
    s1, s2 = (joblib.load(ROOT / c[k]) for k in ('stage1_model', 'stage2_model'))
    s1.set_params(n_jobs=2)
    s2.set_params(n_jobs=2)
    fd = pd.read_csv(ROOT / c['feature_dictionary'])
    topics, modules, codes, alloc = _allocation_matrix(fd, pd.read_csv(ROOT / c['topic_module_mapping']))
    model_audit = {'stage1_classes': s1.classes_.tolist(), 'stage1_features': s1.n_features_in_,
                   'stage1_best_iteration': s1.best_iteration_, 'stage2_features': s2.n_features_in_,
                   'channels':len(channels), 'scaler_finite': bool(np.isfinite(mean).all() and np.isfinite(std).all()),
                   'scaler_positive':bool((std>0).all()),
                   'feature_order_valid': fd.feature.tolist() == [f'{d}__{ch}' for d in fd.descriptor.drop_duplicates() for ch in channels],
                   'feature_protocol': {'frequency_hz':10.,'window_size':96,'stride':8,'horizon':12,
                                        'preserve_header_start':args.preserve_header_start,
                                        'source_clock':args.source_clock,
                                        'preprocessing':'unchanged P2 align_log_arrays and descriptor_batch'},
                   'sha256': {k:hashlib.sha256((ROOT/c[k]).read_bytes()).hexdigest() for k in ('stage1_model','stage2_model','scaler_mean','scaler_std','feature_dictionary','core_channels')}}
    (OUT/'model_audit.json').write_text(json.dumps(model_audit, indent=2))
    manifest = pd.read_csv(ROOT / c['run_manifest'], sep='\t')
    rows, coverage, clocks = [], [], []
    for row in manifest.itertuples(index=False):
        path = _windows_path(ROOT, row.output_ulog)
        origin=None
        u = ULog(str(path), message_name_filter_list=list(TOPIC_FIELDS))
        if args.source_clock:
            source_id=row.run_id.split('__')[1:3]
            source=ULog(str(ROOT/'data/raw/uav_sead/ulg_files'/source_id[0]/(source_id[1]+'.ulg')),
                        message_name_filter_list=['sensor_combined'])
            a=next(d for d in source.data_list if d.name=='sensor_combined').data
            b=next(d for d in u.data_list if d.name=='sensor_combined').data
            fields=[f'{kind}[{i}]' for kind in ('gyro_rad','accelerometer_m_s2') for i in range(3)]
            origin,clock=estimate_origin(a['timestamp'],np.column_stack([a[f] for f in fields]),
                b['timestamp'],np.column_stack([b[f] for f in fields]),source.start_timestamp)
            clocks.append({'run_id':row.run_id,**clock})
        x, t = _windows_from_ulog(path, channels, mean, std, preserve_header_start=args.preserve_header_start,
                                 start_override_us=origin)
        scores = s1.predict_proba(x)[:,list(s1.classes_).index(1)]
        mv = _windows_to_modules(x, s2, codes, alloc)
        start, stop = _ulog_time_bounds(u, preserve_header_start=args.preserve_header_start)
        if origin is not None:start=origin
        seen = set()
        for d in u.data_list:
            if d.name in seen or 'timestamp' not in d.data: continue
            seen.add(d.name)
            ts = np.asarray(d.data['timestamp'],dtype=float)
            valid = (ts>=start)&(ts<=stop)
            tv = ts[valid]
            coverage.append({'run_id':row.run_id,'topic':d.name,'samples':len(ts),'valid_samples':len(tv),
                'first_s':float((tv.min()-start)/1e6) if len(tv) else None,
                'last_s':float((tv.max()-start)/1e6) if len(tv) else None,
                'missing_channels': ';'.join(ch for ch in channels if ch.startswith(d.name+'.') and ch.split('.',1)[1] not in d.data)})
        rows.append({'run_id':row.run_id,'condition':row.condition,'windows':len(x),'start_us':start,'duration_s':(stop-start)/1e6,
            'score_min':scores.min(),'score_median':np.median(scores),'score_max':scores.max(),
            'feature_finite':bool(np.isfinite(x).all()),'zero_feature_fraction':float((x==0).mean()),
            'missing_topics':';'.join(set(topics)-seen)})
        np.savez_compressed(cache/f'{row.run_id}.npz',features=x,times=t,scores=scores,modules=mv,
                            clock_origin_from_header_s=(start-int(u.start_timestamp))/1e6)
        print(row.run_id, 'windows',len(x),'score range',float(scores.min()),float(scores.max()),flush=True)
    pd.DataFrame(rows).to_csv(OUT/'score_audit.csv',index=False)
    pd.DataFrame(coverage).to_csv(OUT/'topic_time_coverage.csv',index=False)
    (OUT/'modules.json').write_text(json.dumps(modules))
    if clocks:pd.DataFrame(clocks).to_csv(OUT/'clock_alignment_audit.csv',index=False)

if __name__ == '__main__': main()
