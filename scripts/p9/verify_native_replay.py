"""Verify completion and input coverage independently of mutation truth."""
from pathlib import Path
import json
import hashlib
import re
import pandas as pd
from pyulog import ULog
from hs_aerots.sitl_injection import load_config
from hs_aerots.baseline import _ulog_time_bounds

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/p9/stage1_reassessment/native_replay'

def main():
    c=load_config(ROOT/'configs/p9_sitl_injection.yaml')
    durations={}
    inputs={}
    for p in c['experiment']['replay_logs']:
        key='__'.join(Path(p).with_suffix('').parts[-2:])
        u=ULog(str(ROOT/p)); a,b=_ulog_time_bounds(u)
        durations[key]=(b-a)/1e6
        inputs[key]=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
    manifest=pd.read_csv(OUT/'run_manifest.tsv',sep='\t')
    coverage=pd.read_csv(OUT/'topic_time_coverage.csv')
    sensor=coverage[coverage.topic.eq('sensor_combined')].set_index('run_id')
    rows=[]
    for r in manifest.itertuples(index=False):
        text=(OUT/'consoles'/f'{r.run_id}.log').read_text(errors='replace')
        matched=re.search(r'Replay done \(published (\d+) msgs, ([\d.]+) s\)',text)
        key='__'.join(r.run_id.split('__')[1:3])
        last=float(sensor.loc[r.run_id,'last_s'])
        rows.append({'run_id':r.run_id,'replay_done':bool(matched),
            'published_messages':int(matched[1]) if matched else None,
            'replay_elapsed_s':float(matched[2]) if matched else None,
            'source_duration_s':durations[key],'sensor_last_s':last,
            'coverage_ok':last>=durations[key]-1.0,'exit_code':r.exit_code})
    frame=pd.DataFrame(rows)
    frame.to_csv(OUT/'replay_completeness.csv',index=False)
    hashes=(OUT/'input_binary_sha256.txt').read_text()
    identity=all(h in hashes for h in inputs.values())
    summary={'runs':len(frame),'all_replay_done':bool(frame.replay_done.all()),
        'all_sensor_coverage_ok':bool(frame.coverage_ok.all()),'inputs_byte_identical':identity,
        'exit_codes':sorted(frame.exit_code.unique().tolist()),'source_sha256':inputs}
    (OUT/'replay_validity.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
    if len(frame)!=24 or not identity or not frame.replay_done.all() or not frame.coverage_ok.all():
        raise SystemExit('Replay validity check failed')

if __name__=='__main__':main()
