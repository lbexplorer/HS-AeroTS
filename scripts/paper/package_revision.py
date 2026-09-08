"""Package review sources and exact table inputs without raw data or models."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'reports/paper_finalization_20260908'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    files=set()
    for folder in ('paper/sections','paper/figures','paper/Definitions','paper/generated','paper/templates'):
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and p.suffix.lower() in {'.tex','.pdf','.png','.jpg','.eps','.cls','.sty','.bst','.bib'}:files.add(p)
    for name in ('paper/main.tex','paper/supplement.tex','paper/README.md','paper/generate_revision_assets.py',
        'scripts/paper/generate_primary_tables.py','scripts/paper/order_bibliography.py',
        'scripts/mtcl_uav/run_reproduction.py','configs/mtcl_uav_reproduction.yaml',
        'reports/mtcl_uav_reproduction/README.md','reports/mtcl_uav_reproduction/input_audit.json',
        'reports/mtcl_uav_reproduction/smoke_check.json'):
        files.add(ROOT/name)
    for name in ('COMPLETION_REPORT.md','TASKS.md','REVISION_PLAN.md','CITATION_AND_AVAILABILITY_AUDIT.md',
        'table_source_ledger.json','primary_table_source_ledger.json','protected_artifacts_before.json',
        'protected_artifacts_verification.json','metadata_preservation.json','final_qa.json'):
        files.add(OUT/name)
    for name in ('table_source_ledger.json','primary_table_source_ledger.json'):
        data=json.loads((OUT/name).read_text(encoding='utf-8'))
        for rel,expected in data['sources_sha256'].items():
            p=ROOT/rel;assert sha(p)==expected,rel;files.add(p)
    manifest={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)}
    m=OUT/'revision_source_manifest.json';m.write_text(json.dumps(manifest,indent=2),encoding='utf-8');files.add(m)
    dest=ROOT/'paper/build/HS-AeroTS_revision_v1.1_sources.zip'
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(files):z.write(p,p.relative_to(ROOT))
    with zipfile.ZipFile(dest) as z:assert z.testzip() is None
    qa=json.loads((OUT/'final_qa.json').read_text())
    for source,name in [('main','HS-AeroTS_Drones_revision_v1.1'),('supplement','HS-AeroTS_Supplement_v1.1')]:
        assert sha(ROOT/f'paper/build/{name}.pdf')==qa[source]['sha256'],'PDF changed after QA'
    report={'files':len(files),'source_zip_sha256':sha(dest),'zip_bytes':dest.stat().st_size,
            'source_zip':str(dest),'main_pages':qa['main']['pages'],'supplement_pages':qa['supplement']['pages']}
    (OUT/'release_manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
