"""Synthetic resource probe, never a reported experiment score."""
from pathlib import Path
import sys,time,json
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'third_party/MTCL-UAV'))
import torch
from models.MTCL import Model
torch.set_num_threads(4)
torch.manual_seed(0)
cfg=SimpleNamespace(layer_nums=3,num_nodes=87,pred_len=96,seq_len=96,k=2,
    num_experts_list=[4,4,4],patch_size_list=[[16,12,8,32],[12,8,6,4],[8,6,4,2]],
    d_model=16,d_ff=16,residual_connection=1,revin=1,gpu=0,batch_norm=1,temp=2)
out=[]
for batch in [4,8,16]:
    try:
        torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats()
        model=Model(cfg).cuda();opt=torch.optim.Adam(model.parameters(),lr=.001)
        x=torch.randn(batch,96,87,device='cuda');times=[]
        for i in range(2):
            torch.cuda.synchronize();t=time.perf_counter();opt.zero_grad()
            y,bal,con=model(x);loss=(y-x).square().mean()+bal+.1*con
            assert torch.isfinite(loss),loss
            loss.backward();opt.step();torch.cuda.synchronize();times.append(time.perf_counter()-t)
        r={'batch':batch,'seconds':times,'memory_mb':torch.cuda.max_memory_allocated()/2**20,'parameters':sum(p.numel() for p in model.parameters())}
        out.append(r);print(json.dumps(r),flush=True)
        del model,opt,x,y,bal,con,loss
    except Exception as e:
        out.append({'batch':batch,'error':repr(e)});print(repr(e),flush=True);break
(ROOT/'reports/paper_finalization_20260908/mtcl_resource_probe.json').write_text(json.dumps(out,indent=2))
