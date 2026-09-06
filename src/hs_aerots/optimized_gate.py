"""Normal-calibrated feature/topic gate used only for P9 experiments."""
from __future__ import annotations
import numpy as np
from .paired_replay import sustained_score
from .replay_detection import sustained_gate

def fit_gate(normal_deltas, times, codes, topic_count, *, warmup_s=15.,
             topic_quantile=.9, aggregation='quantile', event_quantile=1.,
             noise_quantile=.99, floor=.05, consecutive=3, minimum=3.):
    values=np.concatenate(normal_deltas)
    noise=np.maximum(np.quantile(values,noise_quantile,axis=0,method='higher'),floor)
    maxima=[]
    for delta,t in zip(normal_deltas,times):
        scores=_topics(delta/noise,codes,topic_count,aggregation,topic_quantile).max(axis=1)
        scores=scores[np.asarray(t)>=warmup_s]
        events=sustained_score(scores,consecutive)
        if len(events): maxima.append(float(events.max()))
    if not maxima: raise ValueError('normal controls too short')
    threshold=max(minimum,float(np.quantile(maxima,event_quantile,method='higher')))
    return noise,threshold,maxima

def predict_gate(delta,noise,codes,threshold,*,topic_quantile=.9,
                 aggregation='quantile',warmup_s=15.,times=None,consecutive=3):
    topics=_topics(delta/noise,codes,int(codes.max())+1,aggregation,topic_quantile)
    gate=sustained_gate(topics.max(axis=1),threshold,consecutive)
    if times is not None: gate &= np.asarray(times)>=warmup_s
    return topics,gate
def _topics(scaled,codes,count,aggregation,quantile):
    out=np.zeros((len(scaled),count))
    for code in range(count):
        members=scaled[:,codes==code]
        if aggregation=='quantile': out[:,code]=np.quantile(members,quantile,axis=1,method='higher')
        elif aggregation=='mean_top':
            n=max(1,int(np.ceil(members.shape[1]*(1-quantile))))
            out[:,code]=np.sort(members,axis=1)[:,-n:].mean(axis=1)
        else: out[:,code]=members.max(axis=1)
    return out
