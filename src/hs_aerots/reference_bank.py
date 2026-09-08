"""Healthy-reference bank distances; target never estimates its own scale."""
import numpy as np

def bank_scale(healthy_distance, healthy_valid, quantile=.99, floor=1.):
    count=healthy_valid.sum(axis=0)
    scale=np.full(healthy_distance.shape[1],np.inf)
    for c in range(len(scale)):
        values=healthy_distance[healthy_valid[:,c],c]
        if len(values)>=3:
            scale[c]=max(floor,float(np.quantile(values,quantile,method='higher')))
    return scale,count

def nearest_reference(first,second,valid_first,valid_second,scale):
    if first.shape!=second.shape:raise ValueError('Reference distances must share a time grid')
    distance=np.minimum(np.where(valid_first,first,np.inf),np.where(valid_second,second,np.inf))
    valid=(valid_first|valid_second)&np.isfinite(scale)[None,:]
    result=np.zeros_like(distance)
    np.divide(distance,scale,out=result,where=valid)
    if not np.isfinite(result).all():raise ValueError('Invalid bank distance')
    return result,valid
