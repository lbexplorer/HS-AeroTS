"""Read-only artifact verification and PDF presentation QA for the revision."""
from pathlib import Path
import hashlib, json, re, subprocess
from PIL import Image, ImageDraw
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'reports/paper_finalization_20260908'
BUILD = ROOT / 'paper/build'

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()

def expand(path):
    txt = path.read_text(encoding='utf-8')
    return re.sub(r'\\input\{([^}]+)\}', lambda m: expand(ROOT/'paper'/(m[1]+'.tex')), txt)

def main():
    old = json.loads((OUT/'protected_artifacts_before.json').read_text())
    missing = [p for p in old if not (ROOT/p).exists()]
    changed = [p for p, value in old.items() if (ROOT/p).exists() and sha(ROOT/p) != value]
    audit = {'protected_count': len(old), 'missing': missing, 'changed': changed,
             'scope': 'Files enumerated in protected_artifacts_before.json; excludes large feature/prediction caches.'}
    (OUT/'protected_artifacts_verification.json').write_text(json.dumps(audit,indent=2), encoding='utf-8')
    assert not missing and not changed, audit
    checks = {}
    for source, name in [('main','HS-AeroTS_Drones_revision_v1.1'),('supplement','HS-AeroTS_Supplement_v1.1')]:
        txt = expand(ROOT/f'paper/{source}.tex')
        refs = set(re.findall(r'\\(?:ref|eqref)\{([^}]+)\}', txt))
        labels = re.findall(r'\\label\{([^}]+)\}', txt)
        cites = {c.strip() for group in re.findall(r'\\cite\{([^}]+)\}', txt) for c in group.split(',')}
        bib = set(re.findall(r'\\bibitem\{([^}]+)\}', txt))
        log = (BUILD/(name+'.log')).read_text(errors='replace')
        pdf = BUILD/(name+'.pdf')
        reader = PdfReader(pdf)
        text = '\n\n'.join(f'PAGE {i+1}\n'+(p.extract_text() or '') for i,p in enumerate(reader.pages))
        qa = BUILD/'revision_qa'/source
        qa.mkdir(parents=True, exist_ok=True)
        (qa/'extracted.txt').write_text(text, encoding='utf-8')
        checks[source] = {'pages': len(reader.pages), 'sha256': sha(pdf),
             'missing_references': sorted(refs-set(labels)), 'missing_citations': sorted(cites-bib),
             'duplicate_labels': sorted({l for l in labels if labels.count(l)>1}),
             'overfull_boxes': len(re.findall('Overfull',log)),
             'undefined_warnings': re.findall(r'^.*(?:undefined|Rerun to get|Token not allowed).*$' ,log,re.M)}
        subprocess.run(['pdftoppm','-r','100','-png',str(pdf),str(qa/'page')],check=True)
        images = sorted(p for p in qa.glob('page-*.png')
                        if 1 <= int(p.stem.split('-')[-1]) <= len(reader.pages))
        for j in range(0,len(images),4):
            board = Image.new('RGB',(1400,2040),'#dedede')
            draw = ImageDraw.Draw(board)
            for k,p in enumerate(images[j:j+4]):
                im=Image.open(p).convert('RGB'); im.thumbnail((685,980))
                x=(k%2)*700+(700-im.width)//2; y=(k//2)*1020+25
                board.paste(im,(x,y)); draw.text((x,y-18),f'{source} {p.stem}',fill='black')
            board.save(qa/f'contact-{j//4+1:02d}.jpg',quality=90)
    (OUT/'final_qa.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    print(json.dumps({'artifacts':audit,'pdfs':checks},indent=2))

if __name__ == '__main__': main()
