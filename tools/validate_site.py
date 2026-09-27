"""Check the public package, link closure and gallery/media coverage."""
import json
from pathlib import Path
import re
from collections import Counter
from datetime import date
from PIL import Image

root=Path(__file__).resolve().parents[1]/'docs'
catalog=json.loads((root/'data/catalog.json').read_text(encoding='utf-8'))
report=json.loads((root/'data/publication-report.json').read_text(encoding='utf-8'))
assert not report['conversionErrors'],report['conversionErrors']
ids=set()
for collection in catalog['collections']:
    assert collection['id'] not in ids
    ids.add(collection['id'])
    assert collection['items'] and collection['cover'] in collection['items']
    for ident in collection['items']: assert ident in catalog['media']
paths=set()
for ident,item in catalog['media'].items():
    assert re.fullmatch(r'[0-9a-f]{24}',ident)
    assert re.fullmatch(r'[0-9a-f]{64}',item['sha256'])
    assert item['demoStatus'] in {'in-demo','not-in-demo','unknown'}
    assert item['demoEvidence'] and item['createdDateEvidence']
    assert item['createdDateBasis'] in {'recorded','estimated','unknown'}
    assert (item['createdDate'] is None) == (item['createdDateBasis']=='unknown')
    if item['createdDate']: assert date.fromisoformat(item['createdDate']).isoformat()==item['createdDate']
    for key in ['url','thumb']:
        path=(root/item[key]).resolve()
        assert path.is_relative_to(root.resolve()) and path.is_file(),path
        assert path.stat().st_size>0
        assert path.stat().st_size<95*1024*1024, path
        paths.add(path)
        if path.suffix=='.webp':
            with Image.open(path) as im: im.verify()
    assert not re.search(r'(^[A-Za-z]:|https?://|token=|signature=)',item['source'])
for snapshot,key in [('demo','demoStatus'),('creationDates','createdDateBasis')]:
    actual=Counter(item[key] for item in catalog['media'].values())
    assert all(actual[status]==amount for status,amount in catalog[snapshot]['counts'].items())
if catalog['demo']['verification']=='verified': assert re.fullmatch(r'[0-9a-f]{64}',catalog['demo']['packageSha256'])
for path in root.rglob('*'):
    if path.is_file() and path.suffix in {'.html','.css','.js','.json'}:
        content=path.read_text(encoding='utf-8')
        assert not re.search(r'(?:C:[\\/]+Users|file:///|api_key|X-Amz-Signature|Bearer\s+[A-Za-z0-9]|ghp_[A-Za-z0-9]|sk-[A-Za-z0-9]{20})',content,re.I),path
html=(root/'index.html').read_text(encoding='utf-8')
for ref in re.findall(r'(?:src|href)="([^"#]+)"',html):
    if '://' not in ref and ref!='./': assert (root/ref).exists(),ref
size=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
assert size<950*1024*1024,f'Site exceeds safe Pages size: {size}'
assert not set((root/'media').iterdir())-paths, 'Unreferenced generated media must be removed before publishing'
print(json.dumps({'status':'passed','collections':len(ids),'uniqueMedia':len(catalog['media']),
                  'validatedFiles':len(paths),'siteMiB':round(size/1048576,2)},indent=2))
