"""Archive manuscript and fingerprint frozen experiment artifacts before revision."""
from pathlib import Path
import hashlib,json,zipfile

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/paper_finalization_20260908'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(2**20),b''):h.update(block)
    return h.hexdigest()

def main():
    OUT.mkdir(exist_ok=True)
    archive=OUT/'pre_revision_manuscript.zip'
    if not archive.exists():
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for p in (ROOT/'paper').rglob('*'):
                if p.is_file():z.write(p,p.relative_to(ROOT))
    manifest=OUT/'protected_artifacts_before.json'
    if not manifest.exists():
        files=[]
        for folder in [ROOT/'reports',ROOT/'configs',ROOT/'src']:
            for p in folder.rglob('*'):
                if not p.is_file() or OUT in p.parents:continue
                if p.suffix.lower() in {'.csv','.json','.yaml','.yml','.py','.joblib','.npy','.npz'}:
                    # Feature/prediction caches are already separately sealed; include
                    # models and scalers, but not multi-GB transient replay caches.
                    if p.suffix in {'.npy','.npz'} and not any(t in p.name for t in ['scaler','noise','calibration']):continue
                    files.append(p)
        records={p.relative_to(ROOT).as_posix():sha(p) for p in files}
        manifest.write_text(json.dumps(records,indent=2),encoding='utf-8')
    print(json.dumps({'archive':str(archive),'protected_files':len(json.loads(manifest.read_text()))}))

if __name__=='__main__':main()
