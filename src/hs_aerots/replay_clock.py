"""Recover generic replay's constant clock offset from unchanged input samples."""
from __future__ import annotations
import numpy as np

def estimate_origin(source_times,source_values,replay_times,replay_values,source_origin,
                    anchor_limit=256,minimum_matches=8):
    """Use an early observed sensor prefix and the prerecorded reference only.

    Exact payload matches avoid estimating alignment from mutation effects.
    Failure is explicit; do not use dynamic warping or post-onset alignment.
    """
    lookup={};duplicates=set()
    for t,row in zip(source_times,np.asarray(source_values,dtype=np.float32)):
        key=row.tobytes()
        if key in lookup:duplicates.add(key)
        else:lookup[key]=int(t)
    offsets=[]
    for t,row in zip(replay_times[:anchor_limit],np.asarray(replay_values[:anchor_limit],dtype=np.float32)):
        key=row.tobytes()
        if key in lookup and key not in duplicates and np.isfinite(row).all():
            offsets.append(int(t)-lookup[key])
    if len(offsets)<minimum_matches:raise ValueError('insufficient unique unchanged clock anchors')
    offset=int(np.median(offsets))
    deviation=max(abs(x-offset) for x in offsets)
    if deviation>1000:raise ValueError('replay is not a constant-offset time mapping')
    origin=int(source_origin)+offset
    if origin<0:raise ValueError('invalid replay clock origin')
    return origin,{'matched_prefix_samples':len(offsets),'max_offset_deviation_us':deviation,
                   'origin_us':origin,'anchor_limit':anchor_limit}
