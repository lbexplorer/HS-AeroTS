"""Read-only numerical reproduction of uploaded P14; no parameter selection."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
INPUT=ROOT/'reports/p14_within_flight_calibration'
OUTPUT=ROOT/'reports/p15_topic_calibration_plan'

def main():
    protocol=json.loads((INPUT/'protocol.json').read_text())
    sealed=json.loads((INPUT/'prediction_freeze.json').read_text())
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    hashes={name:sha(INPUT/name)==digest for name,digest in sealed['files'].items()}
    hashes['protocol.json']=sha(INPUT/'protocol.json')==sealed['protocol_sha256']
    windows=pd.read_csv(INPUT/'window_predictions.csv')
    runs=pd.read_csv(INPUT/'self_calibration_by_run.csv').set_index(['dataset','run_id'])
    rows=[];formula_error=0.;gate_mismatches=0
    for (dataset,rid),g in windows.groupby(['dataset','run_id']):
        g=g.sort_values('time_s');time=g.time_s.to_numpy();raw=g.raw_score.to_numpy()
        c=raw[(time>=15)&(time<25)];median=float(np.median(c));mad=float(np.median(abs(c-median)))
        scale=max(1.4826*mad,.05*abs(median),.05)
        z=np.maximum(0,(raw-median)/scale)
        formula_error=max(formula_error,float(np.max(abs(z-g.normalized_score))))
        mask=time>=30;post=z[mask];gate=np.zeros(len(post),bool)
        events=np.min(np.lib.stride_tricks.sliding_window_view(post,3),axis=1)
        gate[2:]=events>protocol['threshold']
        full=np.zeros(len(g),bool);full[mask]=gate
        gate_mismatches+=int(np.sum(full!=g.alarm.to_numpy()))
        r=runs.loc[(dataset,rid)]
        assert np.isclose(scale,r.scale) and np.isclose(median,r['median'])
        rows.append(dict(dataset=dataset,run_id=rid,condition='fault' if rid.endswith('__fault') else 'normal',
            calibration_windows=len(c),event_maximum=float(events.max()),detected=bool(gate.any())))
    frame=pd.DataFrame(rows)
    normal=frame[(frame.dataset=='development')&(frame.condition=='normal')]
    threshold=max(3.,float(normal.event_maximum.nlargest(2).iloc[-1]))
    independent=frame[frame.dataset=='independent']
    faults=independent[independent.condition=='fault'];normal_test=independent[independent.condition=='normal']
    # Descriptive feasibility bound only; these values are not proposed thresholds.
    candidates=np.unique(np.r_[0.,independent.event_maximum.to_numpy()])
    frontier=[(int((normal_test.event_maximum>t).sum()),int((faults.event_maximum>t).sum())) for t in candidates]
    audit=dict(input_hash_checks=hashes,targets_checked=len(frame),maximum_formula_error=formula_error,
        causal_gate_mismatches=gate_mismatches,threshold_recomputed=threshold,
        threshold_matches=bool(np.isclose(threshold,protocol['threshold'])),
        independent_faults_detected=int(faults.detected.sum()),independent_normal_alarms=int(normal_test.detected.sum()),
        calibration_windows=sorted(frame.calibration_windows.unique().tolist()),
        overlap_fraction=1-8/96,
        diagnostic_only_max_recall_count_at_most_two_normal_alarms=max(r for f,r in frontier if f<=2),
        diagnostic_only_min_normal_alarms_at_least_eight_faults=min(f for f,r in frontier if r>=8),
        implementation_files_present={p:(ROOT/p).exists() for p in protocol['implementation_sha256']},
        note='No P14 files changed, no new gate fitted, no replay or SHAP run. Feasibility counts are post-hoc descriptions, not independent performance.')
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT/'p14_numerical_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print(json.dumps(audit,indent=2))

if __name__=='__main__':main()
