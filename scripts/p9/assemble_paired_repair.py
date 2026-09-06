"""Create composite manifests: reuse unaffected runs and replace only repaired EKF."""
from pathlib import Path
import numpy as np
import pandas as pd
from pyulog import ULog
from hs_aerots.sitl_injection import _windows_path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/p9/paired_residual/ekf_generic_repair'

def main():
    rows=list((OUT/'rows').glob('*.tsv'))
    assert len(rows)==9,'all nine repaired EKF runs must complete'
    originals={'reference':ROOT/'reports/p9/stage1_reassessment/native_replay/run_manifest.tsv',
               'normal':ROOT/'reports/p9/paired_residual/normal_repeats/run_manifest.tsv'}
    quality=[]
    for name,path in originals.items():
        m=pd.read_csv(path,sep='\t')
        for i,r in m.iterrows():
            if r.mutation_id!='ekf2_innovation_bias':continue
            old=_windows_path(ROOT,r.output_ulog)
            new=OUT/name/'logs'/f'{r.run_id}.ulg'
            assert new.exists()
            m.loc[i,'output_ulog']=str(new)
            m.loc[i,'exit_code']=124
            for version,ulogpath in [('old_dedicated_flag',old),('correct_generic',new)]:
                u=ULog(str(ulogpath),message_name_filter_list=['vehicle_attitude'])
                d=next(x for x in u.data_list if x.name=='vehicle_attitude').data
                q=np.column_stack([d[f'q[{j}]'] for j in range(4)]).astype(float)
                norms=np.linalg.norm(q,axis=1)
                valid=np.isfinite(q).all(axis=1)&np.isfinite(norms)&(norms>.95)&(norms<1.05)
                quality.append({'collection':name,'run_id':r.run_id,'version':version,
                                'samples':len(q),'valid_quaternion_fraction':float(valid.mean())})
        m.to_csv(OUT/name/'run_manifest.tsv',index=False,sep='\t')
    pd.DataFrame(quality).to_csv(OUT/'quaternion_quality.csv',index=False)
    print(pd.DataFrame(quality).to_string(index=False))

if __name__=='__main__':main()
