import numpy as np
from hs_aerots.reference_bank import bank_scale,nearest_reference

def test_target_does_not_change_healthy_scale():
    healthy=np.zeros((6,2));valid=np.ones((6,2),bool)
    scale,_=bank_scale(healthy,valid)
    a,_=nearest_reference(np.ones((6,2))*3,np.ones((6,2))*4,valid,valid,scale)
    b,_=nearest_reference(np.ones((6,2))*30,np.ones((6,2))*40,valid,valid,scale)
    np.testing.assert_array_equal(b,10*a)
    np.testing.assert_array_equal(scale,[1,1])

def test_invalid_reference_is_not_zero_distance():
    a=np.array([[0.,0.]])
    b=np.array([[5.,9.]])
    result,valid=nearest_reference(a,b,np.array([[False,False]]),np.array([[True,False]]),np.ones(2))
    np.testing.assert_array_equal(result,[[5,0]])
    np.testing.assert_array_equal(valid,[[True,False]])

def test_unobserved_bank_channel_remains_unavailable():
    scale,count=bank_scale(np.ones((6,2)),np.array([[True,False]]*6))
    assert scale[0]==1 and np.isinf(scale[1]) and count[1]==0
