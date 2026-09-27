"""Preserve readable concept names and bounded review labels in public metadata."""
import argparse
import hashlib
import json
from pathlib import Path

def enrich(data, engine, concepts):
    for collection in data['collections']:
        if any(char in collection['title'] for char in ['\u00e2','\u00c3']):
            try: collection['title']=collection['title'].encode('cp1252').decode('utf-8')
            except (UnicodeEncodeError,UnicodeDecodeError): pass
        if collection['category']=='Concept art':
            collection['reviewState']='Concept archive'
            continue
        collection['reviewState']='Working study'
        source=engine/collection['source']
        base=source.parent if source.suffix else source
        for candidate in [base/'manifest.json',base.parent/'manifest.json']:
            if not candidate.is_file(): continue
            try:
                metadata=json.loads(candidate.read_text(encoding='utf-8-sig'))
                status=str(metadata.get('status','')).lower() if isinstance(metadata,dict) else ''
            except (ValueError,UnicodeError): continue
            if 'reject' in status: collection['reviewState']='Rejected study'; break
            if 'supersed' in status: collection['reviewState']='Historical study'; break
            if any(w in status for w in ['pending','awaiting']): collection['reviewState']='Awaiting review'; break
        if collection['kind']=='Gallery':
            collection['description']='Media from a working study gallery, including comparisons and earlier attempts. Original review and in-game status are unchanged.'
    # An archived concept's descriptive name takes precedence over generic labels
    # such as front, reference or preview on byte-identical study copies.
    archive=next((c for c in data['collections'] if c['source']=='concept-art'),None)
    if archive:
        ids=set(archive['items'])
        for path in concepts.rglob('*'):
            if path.is_file() and path.suffix.lower() in {'.png','.jpg','.jpeg','.webp'} and '_archive_metadata' not in path.parts:
                sha=hashlib.sha256(path.read_bytes()).hexdigest()
                if sha[:24] in ids:
                    item=data['media'][sha[:24]]
                    item['title']=path.stem
                    item['source']='concept-art/'+path.relative_to(concepts).as_posix()
    return data

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--engine',type=Path,required=True); p.add_argument('--concepts',type=Path,required=True)
    args=p.parse_args(); target=Path(__file__).resolve().parents[1]/'docs/data/catalog.json'
    data=enrich(json.loads(target.read_text(encoding='utf-8')),args.engine,args.concepts)
    target.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
