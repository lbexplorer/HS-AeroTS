import numpy as np
from hs_aerots.paired_replay import matched_difference,fit_normal_residuals,predict_paired,sustained_score
from hs_aerots.paired_replay import predict_paired_topics,fit_topic_thresholds
from hs_aerots.baseline import _ulog_time_bounds
from hs_aerots.replay_clock import estimate_origin
import pytest

def test_no_extrapolation_past_either_sensor_support():
    d,t,v=matched_difference(np.ones((5,2)),np.arange(5),np.zeros((3,2)),np.arange(1,4),4,2)
    np.testing.assert_array_equal(t,[1,2])
    np.testing.assert_array_equal(d,np.ones((2,2)))

def test_bias_in_unused_classifier_channel_is_still_observable():
    codes=np.array([0,1]); allocation=np.eye(2)
    noise,threshold,_=fit_normal_residuals([np.zeros((8,2))],codes,2)
    delta=np.zeros((8,2));delta[3:,1]=2
    p=predict_paired(delta,noise,codes,allocation,threshold)
    np.testing.assert_array_equal(p['gate'],[0,0,0,0,0,1,1,1])
    assert p['ranks'][1]==1 and np.isinf(p['ranks'][0])

def test_normal_noise_calibration_suppresses_repeated_nuisance():
    delta=np.full((8,2),20.)
    noise,threshold,_=fit_normal_residuals([delta],np.array([0,1]),2)
    assert not predict_paired(delta,noise,np.array([0,1]),np.eye(2),threshold)['gate'].any()

def test_short_runs_do_not_join_into_an_event():
    assert len(sustained_score(np.ones(2),3))==0

def test_prediction_prefix_does_not_depend_on_future_target():
    d=np.zeros((8,2));d[3:,1]=2
    noise=np.ones(2)*.05
    a=predict_paired(d,noise,np.array([0,1]),np.eye(2),3)
    b=predict_paired(np.r_[d,np.ones((10,2))*100],noise,np.array([0,1]),np.eye(2),3)
    np.testing.assert_array_equal(a['gate'],b['gate'][:len(d)])

def test_bad_end_timestamp_cannot_move_paired_time_origin():
    class Dataset:
        data={'timestamp':np.array([632750,94000000],dtype=np.uint64)}
    class Log:
        start_timestamp=1201
        last_timestamp=2**64-2
        data_list=[Dataset()]
    assert _ulog_time_bounds(Log(),preserve_header_start=True)==(1201,94000000)
    assert _ulog_time_bounds(Log())==(632750,94000000)

def test_clock_uses_unchanged_sensor_prefix_despite_missing_first_samples():
    times=np.arange(50)*4000+1_000_000
    values=np.arange(300,dtype=np.float32).reshape(50,6)
    origin,audit=estimate_origin(times,values,times[3:]-500_000,values[3:],900_000)
    assert origin==400_000 and audit['max_offset_deviation_us']==0

def test_clock_rejects_ambiguous_or_corrupted_anchors():
    with pytest.raises(ValueError):
        estimate_origin(np.arange(20),np.zeros((20,6)),np.arange(20),np.zeros((20,6)),0)

def test_switching_topics_cannot_fake_persistent_evidence():
    delta=np.array([[9.,0.],[0.,9.],[9.,0.],[0.,9.]])
    p=predict_paired_topics(delta,np.ones(2),np.arange(2),np.eye(2),np.ones(2)*3)
    assert not p['gate'].any()

def test_noisy_topic_cannot_raise_threshold_of_stable_topic():
    threshold=fit_topic_thresholds([np.array([[50.,0.]]*5)],np.ones(2),np.arange(2),2)
    np.testing.assert_array_equal(threshold,[50.,3.])
