"""MTCL official-core reproduction on immutable HS-AeroTS windows.

Commands: audit (no training), smoke (training-only interface check), train.
Formal training is explicitly invoked and never implied by an audit/smoke run.
"""
from pathlib import Path
from functools import lru_cache
from types import SimpleNamespace
import argparse, hashlib, json, math, random, subprocess, sys, time
import numpy as np
import pandas as pd
import yaml

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

def save_json(p,value):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,indent=2),encoding='utf-8')

def metadata(cfg,protocol,split):
    base=ROOT/cfg['protocols'][protocol]['features']
    return [np.load(base/f'{name}_{split}.npy',mmap_mode='r') for name in ('group','start','y')]

def source_path(value):
    # Existing dictionaries may contain paths from the original Windows host.
    normalized=str(value).replace('\\','/')
    marker='/data/'
    return ROOT/('data/'+normalized.split(marker,1)[1]) if marker in normalized else ROOT/normalized

class Windows:
    def __init__(self,cfg,protocol,split):
        self.groups,self.starts,self.labels=metadata(cfg,protocol,split)
        self.n=cfg['model']['seq_len'];self.cfg=cfg
        table=pd.read_csv(ROOT/cfg['protocols'][protocol]['groups'])
        self.paths={int(row.group):source_path(row.aligned_path) for row in table.itertuples()}
        base=ROOT/cfg['protocols'][protocol]['features']
        self.mean=np.load(base/'scaler_mean.npy').astype('float32')
        self.std=np.load(base/'scaler_std.npy').astype('float32')
        assert np.isfinite(self.mean).all() and np.isfinite(self.std).all() and (self.std>0).all()

    @lru_cache(maxsize=48)
    def shard(self,group):
        # Cache exact raw arrays once, independently of labels and split membership.
        src=self.paths[group]
        target=ROOT/self.cfg['cache_dir']/(hashlib.sha256(str(src.relative_to(ROOT)).encode()).hexdigest()[:20]+'.npy')
        if not target.exists():
            target.parent.mkdir(parents=True,exist_ok=True)
            with np.load(src,allow_pickle=False) as data:
                np.save(target,data['x'],allow_pickle=False)
        return np.load(target,mmap_mode='r')

    def batch(self,indices):
        out=np.empty((len(indices),self.n,len(self.mean)),dtype='float32')
        for i,idx in enumerate(indices):
            start=int(self.starts[idx]);x=self.shard(int(self.groups[idx]))[start:start+self.n]
            assert x.shape==out[i].shape
            out[i]=(x-self.mean)/self.std
        if not np.isfinite(out).all():raise ValueError('Nonfinite input; refusing silent repair.')
        return out

def official_model(cfg):
    repo=ROOT/cfg['repository_path']
    commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
    if commit!=cfg['official_commit']:raise ValueError('Official commit differs from prepared protocol.')
    dirty=subprocess.check_output(['git','-C',str(repo),'status','--porcelain','--untracked-files=no'],text=True)
    if dirty.strip():raise ValueError('Official tracked source modified.')
    sys.path.insert(0,str(repo))
    from models.MTCL import Model
    return Model(SimpleNamespace(**cfg['model']))

def audit(cfg,out):
    rows={};hashes={}
    for name,paths in cfg['protocols'].items():
        sets={};row={}
        for split in ('train','validation','test'):
            g,s,y=metadata(cfg,name,split)
            assert len(g)==len(s)==len(y)
            row[split]={'windows':len(y),'normal_windows':int((y==0).sum()),'logs':len(np.unique(g))}
            sets[split]=set(g.tolist())
            for kind in ('group','start','y'):
                p=ROOT/paths['features']/f'{kind}_{split}.npy';hashes[str(p.relative_to(ROOT))]=digest(p)
        row['train_test_log_overlap']=len(sets['train']&sets['test'])
        if name=='leave_log_out':
            assert all(not sets[a]&sets[b] for a,b in [('train','validation'),('train','test'),('validation','test')])
        for file in ('scaler_mean.npy','scaler_std.npy'):
            p=ROOT/paths['features']/file;hashes[str(p.relative_to(ROOT))]=digest(p)
        store=Windows(cfg,name,'train');idx=np.flatnonzero(store.labels==0)[:2]
        batch=store.batch(idx);assert batch.shape==(2,96,87)
        first=int(idx[0]);start=int(store.starts[first])
        with np.load(store.paths[int(store.groups[first])],allow_pickle=False) as original:
            np.testing.assert_array_equal(batch[0],(original['x'][start:start+96]-store.mean)/store.std)
        rows[name]=row
    save_json(out/'input_audit.json',{'status':'preparation_only','protocols':rows,'input_sha256':hashes})
    print(json.dumps(rows),flush=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command',choices=['audit','smoke','train'])
    ap.add_argument('--config',default='configs/mtcl_uav_reproduction.yaml')
    ap.add_argument('--protocol',choices=['chronological','purged','leave_log_out'],default='chronological')
    ap.add_argument('--seed',type=int,default=0)
    args=ap.parse_args();cfg=yaml.safe_load((ROOT/args.config).read_text(encoding='utf-8'));out=ROOT/cfg['report_dir']
    if args.command=='audit':audit(cfg,out);return
    import torch
    from hs_aerots.baseline import evaluate_scores
    assert torch.cuda.is_available(),'The pinned upstream core expects CUDA.'
    torch.set_num_threads(cfg['training']['cpu_threads'])
    random.seed(args.seed);np.random.seed(args.seed);torch.manual_seed(args.seed);torch.cuda.manual_seed_all(args.seed)
    torch.backends.cudnn.benchmark=False
    model=official_model(cfg).cuda();train=Windows(cfg,args.protocol,'train')
    tr=cfg['training'];idx=np.flatnonzero(train.labels==0);optimizer=torch.optim.Adam(model.parameters(),lr=tr['learning_rate'])
    if args.command=='smoke':
        chosen=idx[:4];x=torch.from_numpy(train.batch(chosen)).cuda()
        y,bal,con=model(x);loss=(y-x).square().mean()+bal+tr['lambda_contrastive']*con
        assert y.shape==x.shape and torch.isfinite(loss)
        loss.backward()
        assert all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters())
        optimizer.step();model.eval()
        with torch.no_grad():pred=model(x)[0];scores=(pred-x).square().mean((1,2))
        assert scores.shape==(4,) and torch.isfinite(scores).all()
        save_json(out/'smoke_check.json',{'status':'interface_check_only','protocol':args.protocol,'seed':args.seed,
             'source_split':'train','windows':4,'finite_loss_and_gradients':True,'test_data_accessed':False,
             'parameters':sum(p.numel() for p in model.parameters()),'torch':torch.__version__})
        print('Training-only interface check passed; no benchmark metrics produced.',flush=True);return
    assert args.seed in cfg['seeds']
    run=out/args.protocol/f'seed{args.seed}';run.mkdir(parents=True,exist_ok=True)
    if (run/'last.pt').exists():raise RuntimeError('Existing run: preserve checkpoints; use a separate report_dir to restart.')
    save_json(run/'protocol.json',{'configuration':cfg,'config_sha256':digest(ROOT/args.config),'status':'running'})
    validation=Windows(cfg,args.protocol,'validation');val_idx=np.flatnonzero(validation.labels==0)
    bs=tr['batch_size'];steps=math.ceil(len(idx)/bs)
    scheduler=torch.optim.lr_scheduler.OneCycleLR(optimizer,max_lr=tr['learning_rate'],steps_per_epoch=steps,epochs=tr['epochs'],pct_start=tr['pct_start'])
    best=float('inf');stale=0;history=[]
    for epoch in range(tr['epochs']):
        model.train();order=np.random.permutation(idx);total=0.;t=time.perf_counter()
        for step,lo in enumerate(range(0,len(order),bs)):
            x=torch.from_numpy(train.batch(order[lo:lo+bs])).cuda();optimizer.zero_grad(set_to_none=True)
            pred,bal,con=model(x);loss=(pred-x).square().mean()+bal+tr['lambda_contrastive']*con
            if not torch.isfinite(loss):raise FloatingPointError('Nonfinite loss; formal run invalid.')
            loss.backward();optimizer.step();scheduler.step();total+=float(loss.detach())*len(x)
            if step%100==0:print(json.dumps({'epoch':epoch+1,'step':step,'steps':steps,'elapsed_s':time.perf_counter()-t}),flush=True)
        model.eval();vtotal=0.
        with torch.no_grad():
            for lo in range(0,len(val_idx),bs):
                x=torch.from_numpy(validation.batch(val_idx[lo:lo+bs])).cuda();pred,_,con=model(x)
                vtotal+=float((pred-x).square().mean()+tr['lambda_contrastive']*con)*len(x)
        val=vtotal/len(val_idx)
        if not np.isfinite(val):raise FloatingPointError('Nonfinite validation criterion.')
        if val<best:best=val;stale=0;torch.save(model.state_dict(),run/'best.pt')
        else:stale+=1
        history.append({'epoch':epoch+1,'train_loss':total/len(idx),'validation_loss':val,'seconds':time.perf_counter()-t})
        save_json(run/'history.json',history)
        torch.save({'model':model.state_dict(),'optimizer':optimizer.state_dict(),'scheduler':scheduler.state_dict(),'epoch':epoch+1},run/'last.pt')
        if stale>=tr['patience']:break
    model.load_state_dict(torch.load(run/'best.pt',weights_only=True));model.eval()
    def score(store):
        values=[]
        with torch.no_grad():
            for lo in range(0,len(store.labels),bs):
                x=torch.from_numpy(store.batch(np.arange(lo,min(lo+bs,len(store.labels))))).cuda()
                pred=model(x)[0];values.extend((pred-x).square().mean((1,2)).cpu().tolist())
        values=np.asarray(values)
        if not np.isfinite(values).all():raise FloatingPointError('Nonfinite evaluation scores.')
        return values
    val_scores=score(validation)
    threshold=evaluate_scores(validation.labels,val_scores,validation.groups)['threshold']
    save_json(run/'frozen_threshold.json',{'threshold':threshold,'source':'validation','best_model_sha256':digest(run/'best.pt')})
    test=Windows(cfg,args.protocol,'test');test_scores=score(test)
    result=evaluate_scores(test.labels,test_scores,test.groups,threshold)
    result.pop('best_f1',None)  # Never present a test-optimized oracle as an operating metric.
    for split,store,scores in [('validation',validation,val_scores),('test',test,test_scores)]:
        pd.DataFrame({'group':store.groups,'start':store.starts,'label':store.labels,'score':scores}).to_csv(run/f'{split}_scores.csv',index=False)
    save_json(run/'metrics.json',{'status':'complete','protocol':args.protocol,'seed':args.seed,'epochs':len(history),'metrics':result})
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()
