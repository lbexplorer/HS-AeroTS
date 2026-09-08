from pathlib import Path
import importlib.util
import sys
from types import SimpleNamespace
import numpy as np

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts/p9'
sys.path.insert(0,str(SCRIPTS))
spec=importlib.util.spec_from_file_location('joint_support',SCRIPTS/'build_joint_replay_cache.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def test_support_does_not_extrapolate_or_bridge_long_gaps():
    times=np.r_[np.arange(10)/10,10+np.arange(10)/10]
    grid=np.array([-.1,.5,5.,10.5,12.])
    _,valid=module.supported_interp(grid,times,np.ones(len(times)))
    np.testing.assert_array_equal(valid,[False,True,False,True,False])

def test_shared_sampling_removes_only_sampling_difference_and_preserves_bias(monkeypatch):
    times=np.arange(601,dtype=np.int64)*100000
    def read(path,**kwargs):
        keep=np.arange(601) if str(path)=='target' else np.arange(0,601,2)
        ts=times[keep]
        signal=np.sin(ts/1e6)
        z=np.ones(len(keep))*4 if str(path)=='target' else np.zeros(len(keep))
        data=[SimpleNamespace(name='sensor_combined',data={'timestamp':ts,'gyro_rad[0]':signal}),
              SimpleNamespace(name='vehicle_local_position',data={'timestamp':ts,'z':z})]
        return SimpleNamespace(start_timestamp=0,data_list=data)
    monkeypatch.setattr(module,'ULog',read)
    result,diagnostics=module.build_pair('target','reference',0,0,
        ['sensor_combined.gyro_rad[0]','vehicle_local_position.z'],np.zeros(2),np.ones(2))
    assert result['channel_valid'].all()
    np.testing.assert_allclose(result['delta'][:,0::2],0,atol=1e-6)
    np.testing.assert_allclose(result['delta'][:,1],4,atol=1e-6)
    assert all(d['shared_packets_used'] for d in diagnostics)
