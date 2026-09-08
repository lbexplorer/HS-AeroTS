"""Fetch public bibliographic/repository metadata without uploading research data."""
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor
import json,re,datetime,sys
sys.stdout.reconfigure(encoding='utf-8')

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/paper_finalization_20260908'
def get(url):
    try:
        with urlopen(Request(url,headers={'User-Agent':'HS-AeroTS-manuscript-audit/1.0'}),timeout=22) as r:
            data=r.read().decode('utf-8')
            return {'url':url,'final_url':r.url,'status':r.status,'data':json.loads(data)}
    except Exception as e:return {'url':url,'error':str(e)}

def main():
    txt=(ROOT/'paper/main.tex').read_text(encoding='utf-8')
    dois=set(re.findall(r'https://doi.org/([^}]+)',txt))|{'10.1109/TIM.2025.3571126','10.1109/TIM.2026.3718566'}
    urls=['https://api.crossref.org/works/'+quote(d,safe='') for d in sorted(dois)]
    urls += ['https://api.github.com/repos/lbexplorer/HS-AeroTS',
             'https://api.github.com/repos/lbexplorer/HS-AeroTS/git/trees/main?recursive=1',
             'https://api.github.com/repos/WindchaserHG/MTCL-UAV',
             'https://api.github.com/repos/WindchaserHG/MTCL-UAV/commits/main']
    with ThreadPoolExecutor(max_workers=6) as pool: results=list(pool.map(get,urls))
    payload={'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'results':results}
    (OUT/'external_metadata_audit.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding='utf-8')
    for r in results:
        if 'error' in r:print(r['url'],r['error'])
        elif 'crossref' in r['url']:
            d=r['data']['message'];print(json.dumps({k:d.get(k) for k in ['DOI','title','author','volume','page','published','resource']},ensure_ascii=False))
        else:
            d=r['data'];print(json.dumps({'url':r['url'],'private':d.get('private'),'sha':d.get('sha'),'tree_count':len(d.get('tree',[])),'p15_paths':[i['path'] for i in d.get('tree',[]) if 'p15' in i['path'].lower()]},ensure_ascii=False))
if __name__=='__main__':main()
