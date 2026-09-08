"""Retry only unresolved public metadata queries sequentially."""
from pathlib import Path
import json,time,sys
sys.path.insert(0,str(Path(__file__).parent))
from audit_external_sources import get
p=Path(__file__).resolve().parents[2]/'reports/paper_finalization_20260908/external_metadata_audit.json'
d=json.loads(p.read_text(encoding='utf-8'))
for i,r in enumerate(d['results']):
    if 'error' in r:
        fresh=get(r['url']);fresh['previous_error']=r['error'];d['results'][i]=fresh
        print(json.dumps({'url':r['url'],'status':fresh.get('status'),'error':fresh.get('error')},ensure_ascii=True),flush=True)
        time.sleep(1)
p.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf-8')
