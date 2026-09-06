import numpy as np
import pytest
from hs_aerots.replay_detection import sustained_gate, normal_threshold, gated_module_scores, conservative_ranks

def test_persistence_is_causal_and_resets():
    np.testing.assert_array_equal(sustained_gate(np.array([.9,.9,.9,.1,.9,.9]),.5), [0,0,1,0,0,0])

def test_threshold_uses_supplied_normal_data_only():
    assert normal_threshold([np.array([.1,.2]),np.array([.3,.4])]) == .4
    with pytest.raises(ValueError): normal_threshold([])

def test_aggregation_does_not_backdate_or_use_onset():
    values=np.array([[100.,0.],[0.,8.],[10.,0.]])
    result=gated_module_scores(values,np.zeros_like(values),np.array([False,True,False]))
    np.testing.assert_array_equal(result,[0.,8.])

def test_zero_and_tied_evidence_cannot_win_alphabetically():
    np.testing.assert_array_equal(conservative_ranks(np.array([2.,2.,0.])),[2.,2.,np.inf])

def test_future_scores_cannot_change_past_gate():
    prefix=np.array([.2,.9,.8,.7])
    for suffix in (np.zeros(20),np.ones(20)):
        np.testing.assert_array_equal(sustained_gate(np.r_[prefix,suffix],.5)[:len(prefix)],
                                      sustained_gate(prefix,.5))

def test_mismatched_reference_shapes_fail_closed():
    with pytest.raises(ValueError):
        gated_module_scores(np.zeros((3,2)),np.zeros((2,2)),np.ones(3,bool))
