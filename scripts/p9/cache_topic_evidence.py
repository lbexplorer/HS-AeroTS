"""Reuse cached features for the existing P8 publisher-only propagation ablation."""
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from hs_aerots.explainability import _predict_contributions

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/p9/stage1_reassessment/native_replay'

def main():
    dictionary=pd.read_csv(ROOT/'reports/p2/feature_dictionary.csv')
    topics=list(dict.fromkeys(dictionary.topic.tolist()))
    codes=dictionary.topic.map({t:i for i,t in enumerate(topics)}).to_numpy()
    model=joblib.load(ROOT/'reports/p3/model_runs/seed0/stage2_lightgbm.joblib')
    model.set_params(n_jobs=2)
    for path in sorted((OUT/'cache').glob('*.npz')):
        d=dict(np.load(path))
        _,signed=_predict_contributions(model,d['features'],256)
        values=np.zeros((len(signed),len(topics)))
        for j,code in enumerate(codes): values[:,code]+=np.abs(signed[:,j])
        np.savez_compressed(path,**{**d,'topics':values})
    print('Cached topic evidence for 24 runs; no truth used')

if __name__=='__main__':main()
