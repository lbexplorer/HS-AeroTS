"""Check replay extraction against stored P2 features and scores, without fitting."""
from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
from hs_aerots.sitl_injection import _windows_from_ulog, load_config

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/p9/stage1_reassessment'

def main():
    c=load_config(ROOT/'configs/p9_sitl_injection.yaml')
    paths=c['paths']; fd=ROOT/'data/processed/p2/features_original'
    channels=(ROOT/paths['core_channels']).read_text().splitlines()
    mean,std=[np.load(ROOT/paths[k]) for k in ('scaler_mean','scaler_std')]
    model=joblib.load(ROOT/paths['stage1_model']); model.set_params(n_jobs=2)
    stage2=joblib.load(ROOT/paths['stage2_model'])
    dictionary=pd.read_csv(ROOT/paths['feature_dictionary'])
    dictionary['stage1_gain']=model.booster_.feature_importance(importance_type='gain')
    dictionary['stage2_gain']=stage2.booster_.feature_importance(importance_type='gain')
    gain=dictionary.groupby('channel')[['stage1_gain','stage2_gain']].sum()
    (gain/gain.sum()).to_csv(OUT/'model_channel_gain_share.csv')
    groups=pd.read_csv(ROOT/'reports/p2/group_dictionary.csv')
    rows=[]
    for path in c['experiment']['replay_logs']:
        key='/'.join(Path(path).with_suffix('').parts[-2:])
        group=int(groups.loc[groups.log_key.eq(key),'group'].iloc[0])
        x,t=_windows_from_ulog(ROOT/path,channels,mean,std)
        scores=model.predict_proba(x)[:,1]
        row={'log_key':key,'windows':len(x),'score_min':float(scores.min()),'score_max':float(scores.max()),
             'score_median':float(np.median(scores))}
        for split in ('train','validation','test'):
            selected=np.load(fd/f'group_{split}.npy')==group
            starts=np.load(fd/f'start_{split}.npy')[selected]
            cached=np.load(fd/f'x_{split}.npy',mmap_mode='r')[selected]
            row[f'{split}_windows']=int(selected.sum())
            row[f'{split}_feature_max_abs_error']=float(np.max(np.abs(x[starts//8]-cached)))
        rows.append(row)
    pd.DataFrame(rows).to_csv(OUT/'source_feature_parity.csv',index=False)
    saved=pd.read_csv(ROOT/'reports/p2/baseline_runs/seed0/val_scores.csv')
    xv=np.load(fd/'x_validation.npy',mmap_mode='r')
    predicted=model.predict_proba(xv)[:,1]
    score_col='score' if 'score' in saved else 'y_score'
    # Fail visibly if the saved score schema changes.
    error=float(np.max(np.abs(predicted-saved[score_col].to_numpy())))
    (OUT/'model_prediction_parity.json').write_text(json.dumps({'validation_windows':len(xv),'saved_score_max_abs_error':error},indent=2))
    print(pd.DataFrame(rows).to_string(index=False)); print('validation score error',error)

if __name__=='__main__': main()
