import numpy as np
import pytest
from hs_aerots.channel_gate import fit_channels,persistent_channels,predict_channels

def test_alternating_channels_cannot_trigger_event():
    v=np.array([[9,0],[0,9],[9,0],[0,9.]])
    p=predict_channels(v,np.zeros(2),np.ones(2),3,np.arange(2),np.eye(2))
    assert not p['gate'].any()

def test_weak_channel_survives_unrelated_normal_scale():
    c,s=fit_channels([np.array([[100.,0.]]*6)])
    p=predict_channels(np.array([[100.,5.]]*6),c,s,3,np.arange(2),np.eye(2))
    assert p['ranks'][1]==1 and np.isinf(p['ranks'][0])
    np.testing.assert_array_equal(p['gate'],[0,0,1,1,1,1])

def test_prefix_is_causal():
    v=np.array([[0.,0.]]*4+[[7.,0.]]*4)
    a=persistent_channels(v)
    b=persistent_channels(np.r_[v,np.ones((4,2))*100])
    np.testing.assert_array_equal(a,b[:len(a)])

def test_tied_publishers_stay_tied():
    p=predict_channels(np.ones((6,1))*10,np.zeros(1),np.ones(1),3,np.array([0]),np.array([[.5,.5]]))
    np.testing.assert_array_equal(p['ranks'],[2,2])

def test_nonfinite_is_not_silent_normal():
    with pytest.raises(ValueError):fit_channels([np.ones((4,1))*np.nan])
