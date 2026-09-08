"""Order the manual bibliography by first citation, retaining entries verbatim."""
from pathlib import Path
import re
PAPER=Path(__file__).resolve().parents[2]/'paper'
def expand(s):
    return re.sub(r'\\input\{([^}]+)\}',lambda m:expand((PAPER/(m[1]+'.tex')).read_text(encoding='utf-8')),s)
def main():
    p=PAPER/'main.tex';txt=p.read_text(encoding='utf-8')
    start=txt.index('\\begin{thebibliography}{999}')+len('\\begin{thebibliography}{999}')
    end=txt.index('\\end{thebibliography}',start)
    entries={m[1]:m[0].strip() for m in re.finditer(r'\\bibitem\{([^}]+)\}.*?(?=\\bibitem|\Z)',txt[start:end],re.S)}
    keys=list(dict.fromkeys(k.strip() for m in re.findall(r'\\cite\{([^}]+)\}',expand(txt[:start])) for k in m.split(',')))
    assert set(keys)==set(entries),(set(keys)-set(entries),set(entries)-set(keys))
    p.write_text(txt[:start]+'\n'+'\n'.join(entries[k] for k in keys)+'\n'+txt[end:],encoding='utf-8')
    print(f'Ordered {len(keys)} references by first citation.')
if __name__=='__main__':main()
