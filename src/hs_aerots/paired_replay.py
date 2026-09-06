"""Normal-only paired replay residuals; prediction accepts no fault truth."""
from __future__ import annotations
import numpy as np
from .replay_detection import sustained_gate, conservative_ranks

def matched_difference(delta, target_times, reference, reference_times, target_support_end, reference_support_end):
    target=np.asarray(delta,dtype=float); reference=np.asarray(reference,dtype=float)
    tt=np.asarray(target_times,dtype=float); rt=np.asarray(reference_times,dtype=float)
    if target.ndim!=2 or reference.ndim!=2 or target.shape[1]!=reference.shape[1]: raise ValueError('incompatible features')
    if len(tt)!=len(target) or len(rt)!=len(reference) or not len(rt): raise ValueError('invalid feature time axes')
    if np.any(np.diff(tt)<=0) or np.any(np.diff(rt)<=0): raise ValueError('time axes must increase')
    valid=(tt>=rt[0])&(tt<=min(rt[-1],target_support_end,reference_support_end))
    times=tt[valid]
    matched=np.column_stack([np.interp(times,rt,reference[:,j]) for j in range(reference.shape[1])])
    residual=np.abs(target[valid]-matched)
    if not np.isfinite(residual).all(): raise ValueError('nonfinite residuals')
    return residual,times,valid

def topic_residuals(delta,noise,feature_topic_codes,topic_count):
    scaled=delta/noise; values=np.zeros((len(delta),topic_count))
    for j,code in enumerate(feature_topic_codes): values[:,code]=np.maximum(values[:,code],scaled[:,j])
    return values

def sustained_score(scores,consecutive):
    if consecutive<1: raise ValueError('invalid persistence')
    if len(scores)<consecutive:return np.empty(0)
    return np.min(np.lib.stride_tricks.sliding_window_view(scores,consecutive),axis=1)

def fit_normal_residuals(normal_deltas,feature_topic_codes,topic_count,quantile=.99,floor=.05,consecutive=3,minimum_threshold=3.):
    if not normal_deltas or floor<=0: raise ValueError('independent normal controls required')
    values=np.concatenate(normal_deltas)
    if not len(values) or not np.isfinite(values).all():raise ValueError('empty/invalid normal residuals')
    noise=np.maximum(np.quantile(values,quantile,axis=0,method='higher'),floor); maxima=[]
    for delta in normal_deltas:
        events=sustained_score(topic_residuals(delta,noise,feature_topic_codes,topic_count).max(axis=1),consecutive)
        if len(events):maxima.append(float(events.max()))
    if not maxima:raise ValueError('normal controls too short')
    return noise,float(max(minimum_threshold,max(maxima))),maxima

def predict_paired(delta,noise,feature_topic_codes,allocation,threshold,consecutive=3):
    topics=topic_residuals(delta,noise,feature_topic_codes,allocation.shape[0]); scores=topics.max(axis=1)
    gate=sustained_gate(scores,threshold,consecutive); excess=np.maximum(topics-threshold,0.)
    aggregate=excess[gate].mean(axis=0) if gate.any() else np.zeros(allocation.shape[0])
    modules=aggregate@allocation
    return {'scores':scores,'gate':gate,'topics':topics,'topic_evidence':aggregate,'module_scores':modules,'ranks':conservative_ranks(modules)}

def fit_topic_thresholds(normal_deltas,noise,codes,topic_count,consecutive=3,minimum=3.):
    threshold=np.full(topic_count,minimum,dtype=float)
    for delta in normal_deltas:
        values=topic_residuals(delta,noise,codes,topic_count)
        for j in range(topic_count):
            events=sustained_score(values[:,j],consecutive)
            if len(events):threshold[j]=max(threshold[j],float(events.max()))
    return threshold

def predict_paired_topics(delta,noise,codes,allocation,threshold,consecutive=3):
    values=topic_residuals(delta,noise,codes,allocation.shape[0])
    gates=np.column_stack([sustained_gate(values[:,j],threshold[j],consecutive) for j in range(values.shape[1])])
    gate=gates.any(axis=1); scaled=values/threshold; excess=np.maximum(scaled-1,0.)*gates
    aggregate=excess[gate].mean(axis=0) if gate.any() else np.zeros(values.shape[1]); modules=aggregate@allocation
    return {'scores':scaled.max(axis=1),'gate':gate,'topics':scaled,'topic_evidence':aggregate,'module_scores':modules,'ranks':conservative_ranks(modules)}
