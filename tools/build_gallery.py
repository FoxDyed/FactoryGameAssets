"""Build public viewing copies; never modify the local art source collections."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
from urllib.parse import unquote, urlsplit
from PIL import Image, ImageOps
from enrich_catalog import enrich
from refresh_metadata import refresh

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / 'docs'
MEDIA = OUT / 'media'
IMAGE_EXT = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
VIDEO_EXT = {'.mp4', '.webm'}
CATEGORIES = ['Terrain', 'Units', 'Buildings', 'Resources', 'Props', 'Concept art', 'Studies']
SKIP_DIRS = {'.git', 'node_modules', '__pycache__', 'factorio', 'runtime-factorio',
             'screenshots-raw', 'vendor', 'cache', '.cache', 'frames', 'raw', 'textures',
             'model', 'models', 'history', 'normal', 'normals', 'depth', 'blender',
             'frames-body', 'frames-shadow', 'frame-cache', 'source-frames', 'body', 'shadow', 'shadows'}
RENDER_PARTS = {'preview', 'previews', 'review', 'renders', 'render', 'finished',
                'references', 'reference', 'concepts', 'runtime', 'decals', 'media',
                'sprites', 'images', 'comparison', 'comparisons', 'boards', 'screenshots'}

def pretty(value):
    value = re.sub(r'[-_]+', ' ', value)
    value = re.sub(r'\b20\d{6}\b', '', value)
    return re.sub(r'\s+', ' ', value).strip().capitalize()

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024*1024), b''): h.update(block)
    return h.hexdigest()

def walk(root, allowed, follow=True):
    """Follow only local source junctions, once; never traverse arbitrary targets."""
    seen = set()
    for directory, dirs, files in os.walk(root, followlinks=follow):
        path = Path(directory)
        real = path.resolve()
        if real in seen or not any(real.is_relative_to(a) for a in allowed):
            dirs[:] = []; continue
        seen.add(real)
        dirs[:] = sorted(d for d in dirs if d.lower() not in SKIP_DIRS and
                         (follow or not (path / d).is_junction()))
        for file in sorted(files): yield path / file

def category_for(path):
    value = str(path).lower()
    for key in ['terrain','units','buildings','resources','props']:
        if f'/{key}/' in value.replace('\\','/'): return key.title()
    if any(k in value for k in ['queen', 'ravager', 'sentinel', 'gatekeeper', 'spitter', 'unit-animation']): return 'Units'
    if any(k in value for k in ['terrain', 'meadows', 'barrens', 'grass', 'creep', 'edge-study']): return 'Terrain'
    if any(k in value for k in ['resource', 'genome']): return 'Resources'
    if any(k in value for k in ['hive', 'building']): return 'Buildings'
    return 'Studies'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--concepts', type=Path, required=True)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--inventory-only', action='store_true')
    parser.add_argument('--from-selection', type=Path, help='Resume a reviewed local selection without rescanning sources')
    parser.add_argument('--discovery', type=Path, help='Audited supplementary dynamic-gallery inventory')
    parser.add_argument('--animations', type=Path, default=HERE/'.local/animation-import.json')
    args = parser.parse_args()
    engine, concepts = args.engine.resolve(), args.concepts.resolve()
    allowed = [engine / 'experiments', engine / 'assets', concepts]
    MEDIA.mkdir(parents=True, exist_ok=True)
    (OUT/'data').mkdir(exist_ok=True)
    local = HERE / '.local'; local.mkdir(exist_ok=True)
    cache_path = local / 'media-cache.json'
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    tasks = {}; collections = []; coverage = []; issues = []
    discovered = json.loads(args.discovery.read_text(encoding='utf-8')) if args.discovery else {}
    public_sources = json.loads((HERE/'tools/gallery-sources.json').read_text(encoding='utf-8'))
    for entry in public_sources['galleries']:
        discovered.setdefault('galleries',[]).append({'path':str(engine/entry['path']), 'likely_gallery':True,
          'dynamic_media_refs':[{'resolved':str(engine/p),'exists':(engine/p).exists()} for p in entry['dynamic']]})

    def source_name(path):
        real = path.resolve()
        if real.is_relative_to(engine): return real.relative_to(engine).as_posix()
        return 'concept-art/' + real.relative_to(concepts).as_posix()

    def add_media(path, title=None):
        real = path.resolve()
        if not any(real.is_relative_to(a) for a in allowed): return None
        if not real.is_file() or real.suffix.lower() not in IMAGE_EXT | VIDEO_EXT: return None
        key = str(real)
        if key not in tasks: tasks[key] = {'path':real, 'title':title or pretty(path.stem), 'source':source_name(real)}
        return key

    def add_collection(title, category, source, keys, kind, description=''):
        keys = list(dict.fromkeys(k for k in keys if k))
        if not keys: return
        ident = hashlib.sha256(source.encode()).hexdigest()[:14]
        collections.append({'id':ident, 'title':title, 'category':category, 'source':source,
                            'kind':kind, 'description':description, '_keys':keys})

    if args.from_selection:
        selected=json.loads(args.from_selection.read_text(encoding='utf-8'))
        collections=selected['collections']
        animation_entries=json.loads(args.animations.read_text(encoding='utf-8')) if args.animations.exists() else []
        animation_lookup={str(Path(e['path']).resolve()):e for e in animation_entries}
        for key in selected['tasks']:
            path=Path(key)
            if key in animation_lookup:
                e=animation_lookup[key]
                tasks[key]={'path':path,'title':e['title'],'source':e['source'],'derivation':e}
            else:
                tasks[key]={'path':path,'title':path.stem if path.is_relative_to(concepts) else pretty(path.stem),'source':source_name(path)}
        included={c['source'] for c in collections}
        for g in public_sources['galleries']:
            coverage.append({'source':g['path'],'kind':'html','outcome':'included' if g['path'] in included else 'no surviving local gallery media'})
        for category in CATEGORIES[:5]:
            root=engine/'experiments/art-library'/category.lower()
            for asset in sorted(p for p in root.iterdir() if p.is_dir()):
                source=source_name(asset)
                coverage.append({'source':source,'kind':'asset','outcome':'included' if source in included else 'no surviving public preview'})
    else:
        # The on-disk library is authoritative; the older migration catalog is incomplete.
        library = engine / 'experiments/art-library'
        for cat in CATEGORIES[:5]:
            root = library / cat.lower()
            if not root.exists(): continue
            for asset in sorted(p for p in root.iterdir() if p.is_dir()):
                print('Indexing '+cat+'/'+asset.name, flush=True)
                keys = []
                for path in walk(asset, allowed):
                    if path.suffix.lower() not in IMAGE_EXT | VIDEO_EXT: continue
                    rel = path.relative_to(asset)
                    lower = rel.as_posix().lower(); parts = set(p.lower() for p in rel.parts[:-1])
                    # Individual animation frames, model maps, masks and raw pass buffers
                    # are source inputs; completed previews and sheets remain visible.
                    if any(p in parts for p in ['frames', 'raw', 'textures', 'masks', 'model', 'models', 'original-downloads']): continue
                    if re.search(r'(?:frame|decoded|pass)[_-]?\d|(?:^|[/_-])f\d{2,}|(?:^|[/_-])\d{3,}(?:[_-]|\.)', lower): continue
                    if re.search(r'direction-(?!00\.)(?:\d+)\.', path.name, re.I): continue
                    if any(p.startswith(('frames','raw-','shadow-','body-')) for p in parts): continue
                    if re.search(r'(?:normal|roughness|metallic|depth|albedo|shadow-only|body-only)', path.stem, re.I): continue
                    if re.search(r'[-_](?:body|shadow|fx)$', path.stem, re.I): continue
                    if len(rel.parts) > 1 and not (parts & RENDER_PARTS) and not re.search(r'preview|thumbnail|reference|overview',path.stem,re.I) and path.suffix.lower() not in VIDEO_EXT: continue
                    keys.append(add_media(path))
                add_collection(pretty(asset.name), cat, source_name(asset), keys, 'Asset',
                               'Concepts, renders and working previews. Original sources remain in the local art library.')
                coverage.append({'source':source_name(asset), 'kind':'asset', 'selected_media':len(set(keys))})

        for extra in public_sources.get('assets',[]):
            keys=[add_media(engine/p) for p in extra['paths']]
            existing=next((c for c in collections if c['source']==extra['source']),None)
            if existing: existing['_keys']=list(dict.fromkeys(existing['_keys']+[k for k in keys if k]))
            else: add_collection(extra['title'],extra['category'],extra['source'],keys,'Asset',
                                 'Original previews and finished views from the shared terrain study. Review status is unchanged.')

        # Rebuild every existing art gallery as a self-contained web collection. Never
        # execute or publish its private scripts, receipts or local filesystem links.
        if shutil.which('rg'):
            found=subprocess.run(['rg','--files',str(engine/'experiments'),'-g','*.html'],capture_output=True,text=True,check=True)
            html_paths=[Path(p) for p in found.stdout.splitlines()]
        else:
            html_paths = [p for p in walk(engine/'experiments', allowed, follow=False) if p.suffix.lower()=='.html']
        html_paths += [Path(g['path']) for g in discovered.get('galleries',[]) if g.get('likely_gallery') and Path(g['path']).is_relative_to(engine)]
        html_paths = list(dict.fromkeys(html_paths))
        discovery_by_path = {str(Path(g['path']).resolve()):g for g in discovered.get('galleries',[])}
        for path in sorted(html_paths):
            source = source_name(path)
            if any(k in source for k in ['progression-model', '/docs/', '/Evidence/', '/scripts/']):
                coverage.append({'source':source, 'kind':'html', 'outcome':'excluded: non-art report, vendor documentation or duplicate evidence'}); continue
            try: content=path.read_text(encoding='utf-8-sig')
            except UnicodeDecodeError: content=path.read_text(encoding='cp1252',errors='replace')
            title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.I|re.S)
            title = html.unescape(re.sub('<[^>]+>', '', title_match.group(1))).strip() if title_match else pretty(path.parent.name)
            refs = re.findall(r'''["']([^"'<>\n]+\.(?:png|jpe?g|webp|gif|mp4|webm))(?:[?#][^"']*)?["']''', content, re.I)
            # Extract CSS url(...) too. Dynamic galleries additionally supply their
            # already rendered nearby sheets, GIFs and videos below.
            refs += re.findall(r'url\([\"\']?([^\)\"\']+\.(?:png|jpe?g|webp|gif))', content, re.I)
            keys = []; missing = []
            for reference in discovery_by_path.get(str(path.resolve()),{}).get('dynamic_media_refs',[]):
                if reference.get('exists'):
                    candidate = Path(reference['resolved'])
                    # Frame sequences are represented by animation previews, not individual stills.
                    if not re.search(r'(?:frame|decoded)[_-]?\d|(?:^|[/_-])\d{3,}(?:[_-]|\.)', candidate.as_posix(), re.I):
                        keys.append(add_media(candidate))
            for ref in dict.fromkeys(refs):
                if '${' in ref or '{' in ref or '://' in ref or ref.startswith('data:'): continue
                candidate = path.parent / unquote(html.unescape(ref))
                key = add_media(candidate)
                if key: keys.append(key)
                elif not candidate.exists(): missing.append(ref)
            # Supplement gallery-local media, including dynamic animation sources.
            for nearby in walk(path.parent, allowed, follow=False):
                if nearby.suffix.lower() not in IMAGE_EXT | VIDEO_EXT: continue
                rel = nearby.relative_to(path.parent).as_posix().lower()
                if len(nearby.relative_to(path.parent).parts) > 3: continue
                if any(x in rel.split('/') for x in ['frames','raw','textures','model','masks','baseline']): continue
                if re.search(r'(?:frame|decoded)[_-]?\d|(?:^|[/_-])(?:f\d{2,}|\d{3,})(?:[_-]|\.)', rel): continue
                keys.append(add_media(nearby))
            add_collection(title, category_for(path), source, keys, 'Gallery',
                           'A web collection from the original study gallery. Historical comparisons retain their original context.')
            coverage.append({'source':source, 'kind':'html', 'title':title,
                             'selected_media':len(set(k for k in keys if k)),
                             'outcome':'included' if any(keys) else 'no surviving local gallery media',
                             'unavailable_references':missing})

        tower = engine/'assets/source/buildings/brood_hive_tower/generation'
        if tower.exists():
            add_collection('Brood hive tower', 'Buildings', 'assets/source/buildings/brood_hive_tower',
                           [add_media(p) for p in sorted(tower.glob('*reference.png'))], 'Asset',
                           'Preserved source references for the brood hive tower study.')

        # All archived concept images, with their descriptive names, including additions
        # newer than the original archive manifest. Acquisition metadata stays private.
        keys = [add_media(p, p.stem) for p in walk(concepts, allowed, follow=False)
                if p.suffix.lower() in IMAGE_EXT and '_archive_metadata' not in p.parts]
        add_collection('Factory Game Design', 'Concept art', 'concept-art', keys, 'Archive',
                       'The complete local concept-art collection: creatures, buildings, biomes and visual studies.')

        if args.animations.exists():
            animation_data=json.loads(args.animations.read_text(encoding='utf-8'))
            entries=animation_data if isinstance(animation_data,list) else animation_data.get('entries',[])
            for entry in entries:
                path=Path(entry['path']).resolve()
                if not path.is_relative_to((local/'animation-previews').resolve()):
                    raise ValueError('Animation preview outside the owned output directory')
                key=str(path)
                tasks[key]={'path':path,'title':entry['title'],'source':entry['source'],'derivation':entry}
                matching=[c for c in collections if c['source']==entry['gallerySource']]
                for collection in matching: collection['_keys'].insert(0,key)

    # Individual decoded playback frames add thousands of redundant stills.
    for c in collections:
        c['_keys']=[k for k in c['_keys'] if not re.search(r'loop-\d+|corpse-(?:body|shadow)-\d+',Path(k).name,re.I)]
    used_keys={k for c in collections for k in c['_keys']}
    tasks={k:v for k,v in tasks.items() if k in used_keys}
    conversion_locks={}
    print(f'Preparing {len(collections)} collections, {len(tasks)} source media files.', flush=True)
    (local/'selection.json').write_text(json.dumps({'collections':collections,'tasks':list(tasks),'coverage':coverage},indent=2),encoding='utf-8')
    if args.inventory_only: return

    def convert(task):
        path = task['path']; stat = path.stat(); key = str(path)
        signature = [stat.st_size, stat.st_mtime_ns, 3]
        old = cache.get(key)
        if old and old['signature']==signature and all((OUT/old['record'][k]).exists() and (OUT/old['record'][k]).stat().st_size>0 for k in ['url','thumb']):
            return key, old['record'], old
        sha = digest(path); ident = sha[:24]; ext = path.suffix.lower()
        record = {'id':ident, 'title':task['title'], 'source':task['source'], 'sha256':sha,
                  'originalBytes':stat.st_size}
        thumb = MEDIA / (ident+'-thumb.webp')
        if ext in VIDEO_EXT:
            target = MEDIA / (ident+'.mp4')
            if not target.exists() or not target.stat().st_size or not thumb.exists() or not thumb.stat().st_size:
                subprocess.run([args.ffmpeg,'-hide_banner','-loglevel','error','-y','-i',str(path),
                                '-vf','scale=960:720:force_original_aspect_ratio=decrease:force_divisible_by=2',
                                '-c:v','libx264','-crf','28','-preset','fast','-pix_fmt','yuv420p','-an',
                                '-movflags','+faststart',str(target)],check=True,timeout=240)
            if not thumb.exists() or not thumb.stat().st_size:
                subprocess.run([args.ffmpeg,'-hide_banner','-loglevel','error','-y','-i',str(target),
                                '-frames:v','1','-vf','scale=560:420:force_original_aspect_ratio=decrease',str(thumb)],
                               check=True,timeout=60)
            record.update(type='video', width=960, height=720)
        else:
            target = MEDIA / (ident+'.webp')
            with Image.open(path) as im:
                width,height = im.size
                animated = getattr(im, 'is_animated', False) and ext in {'.gif','.webp'}
                record.update(type='animation' if animated else 'image', width=width,height=height)
                if not thumb.exists() or not thumb.stat().st_size:
                    frame = ImageOps.exif_transpose(im).convert('RGBA'); frame.thumbnail((560,420))
                    frame.save(thumb, 'WEBP', quality=78, method=4)
                if not target.exists() or not target.stat().st_size:
                    if animated:
                        if task.get('derivation'):
                            shutil.copyfile(path,target)
                        else:
                            frames=[]; durations=[]
                            for n in range(im.n_frames):
                                im.seek(n); frame=im.convert('RGBA'); frame.thumbnail((960,960))
                                frames.append(frame.copy()); durations.append(im.info.get('duration',100))
                            frames[0].save(target,'WEBP',save_all=True,append_images=frames[1:],duration=durations,
                                           loop=0,quality=76,method=3)
                    else:
                        frame = ImageOps.exif_transpose(im).convert('RGBA'); frame.thumbnail((1800,1800))
                        frame.save(target,'WEBP',quality=86,method=4)
        record.update(url=target.relative_to(OUT).as_posix(), thumb=thumb.relative_to(OUT).as_posix())
        if task.get('derivation'):
            entry=task['derivation']
            record.update(derivedPreview=True, sha256=entry['sourceSha256'], previewSha256=sha,
                          provenanceNote=entry.get('note','Animated viewing copy reconstructed from the original study playback data.'))
        return key, record, {'signature':signature,'record':record}

    converted = {}; by_id = {}; count=0
    def safe_convert(item):
        try:
            with conversion_locks.setdefault(digest(item['path']),threading.Lock()):
                return convert(item), None
        except Exception as exc: return None, {'source':item['source'],'error':str(exc).replace(str(engine),'[engine]').replace(str(concepts),'[concepts]')}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result, error in pool.map(safe_convert,tasks.values()):
            if error: issues.append(error); continue
            key, record, cached=result
            converted[key]=record['id']; by_id.setdefault(record['id'],record); cache[key]=cached
            count+=1
            if count%100==0:
                print(f'Prepared {count}/{len(tasks)} media.', flush=True)
                cache_path.write_text(json.dumps(cache),encoding='utf-8')
    cache_path.write_text(json.dumps(cache),encoding='utf-8')
    for collection in collections:
        collection['items']=list(dict.fromkeys(converted[k] for k in collection.pop('_keys') if k in converted))
        # Covers favor finished renders and compositions, not masks/sprite sheets.
        def cover_score(ident):
            item=by_id[ident]; text=item['source'].lower()
            return (sum(w in text for w in ['preview','finished','scene','concept','reference'])-
                    3*sum(w in text for w in ['sheet','atlas','mask','strip']), -len(text))
        collection['cover']=max(collection['items'],key=cover_score) if collection['items'] else None
    collections=[c for c in collections if c['items']]
    # Prune only our generated, content-addressed web copies, never source media.
    referenced={record[k] for record in by_id.values() for k in ['url','thumb']}
    for path in MEDIA.iterdir():
        if path.is_file() and re.fullmatch(r'[0-9a-f]{24}(?:-thumb)?\.(?:webp|mp4)',path.name) and path.relative_to(OUT).as_posix() not in referenced:
            path.unlink()
    now=datetime.now(timezone.utc).isoformat()
    data={'updated':now, 'categories':CATEGORIES, 'collections':collections,'media':by_id}
    enrich(data,engine,concepts)
    refresh(data,engine,concepts)
    (OUT/'data/catalog.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    public_coverage = {'updated':now, 'collections':len(collections), 'uniqueMedia':len(by_id),
                'sourceMedia':len(tasks), 'coverage':coverage,'conversionErrors':issues,
                'scope':'Web viewing copies of current local art assets and surviving study gallery media. Editable originals, acquisition records, vendor packages and private URLs are not published. No new art approval or engine integration.',
                'limits':'Legacy gallery interfaces are presented as image/video collections. Individual render frames and technical buffers are represented by completed previews and sprite sheets. Deleted historical media cannot be republished.'}
    (OUT/'data/publication-report.json').write_text(json.dumps(public_coverage,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'collections':len(collections),'uniqueMedia':len(by_id),'conversionErrors':len(issues),
                      'mediaMiB':round(sum(p.stat().st_size for p in MEDIA.iterdir())/1048576,2)},indent=2))
    if issues: print('Inspect docs/data/publication-report.json for conversion failures.')

if __name__=='__main__': main()
