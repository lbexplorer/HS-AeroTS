"""Paired channel calibration. Prediction has no onset or mutation arguments."""
import numpy as np
from .replay_detection import conservative_ranks

def channel_values(delta, noise, feature_channels, channel_count):
    delta=np.asarray(delta,float);noise=np.asarray(noise,float)
    if delta.ndim!=2 or np.any(noise<=0) or not np.isfinite(delta).all():
        raise ValueError('Invalid residuals/noise')
    result=np.zeros((len(delta),channel_count))
    for j,c in enumerate(feature_channels):
        result[:,c]=np.maximum(result[:,c],delta[:,j]/noise[j])
    return result

def fit_channels(normal_runs, quantile=.99, floor=1.):
    """Equal-run center; conservative normal tail envelope, not test self-fitting."""
    if not normal_runs or any(len(r)<3 or not np.isfinite(r).all() for r in normal_runs):
        raise ValueError('Complete independent healthy runs required')
    center=np.median([np.median(r,axis=0) for r in normal_runs],axis=0)
    upper=np.max([np.quantile(r,quantile,axis=0,method='higher') for r in normal_runs],axis=0)
    return center,np.maximum(upper-center,floor)

def persistent_channels(z, consecutive=3):
    z=np.asarray(z,float)
    if z.ndim!=2 or consecutive<1:raise ValueError('Invalid channel series')
    result=np.zeros_like(z)
    if len(z)>=consecutive:
        result[consecutive-1:]=np.lib.stride_tricks.sliding_window_view(z,consecutive,axis=0).min(axis=-1)
    return result

def predict_channels(values, center, scale, threshold, channel_topics, allocation, consecutive=3):
    if not np.isfinite(values).all() or np.any(scale<=0):raise ValueError('Invalid calibration/data')
    z=np.maximum(0,(values-center)/scale)
    persistent=persistent_channels(z,consecutive)
    channel_gate=persistent>threshold
    gate=channel_gate.any(axis=1)
    evidence=np.maximum(persistent-threshold,0.)
    topic_windows=np.zeros((len(values),allocation.shape[0]))
    for c,t in enumerate(channel_topics):
        topic_windows[:,t]=np.maximum(topic_windows[:,t],evidence[:,c])
    topic_evidence=topic_windows[gate].mean(axis=0) if gate.any() else np.zeros(allocation.shape[0])
    modules=topic_evidence@allocation
    return dict(gate=gate,scores=persistent.max(axis=1),channel_scores=persistent,
        topic_evidence=topic_evidence,module_scores=modules,ranks=conservative_ranks(modules))
