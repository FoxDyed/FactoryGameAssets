"""Creation dates from source records, never archive/export or filesystem dates."""
from collections import Counter
from datetime import date, datetime, timezone
from functools import lru_cache
import json
from pathlib import Path
import re

CREATION_KEYS = ('created_date', 'created_at', 'createdAt', 'creation_date', 'creationDate', 'generated_at', 'rendered_at')
DATE_PATTERN = re.compile(r'(?<!\d)(20\d{2})[-_]?([01]\d)[-_]?([0-3]\d)(?!\d)')


def iso_day(value):
    if not isinstance(value, str):
        return None
    match = DATE_PATTERN.match(value)
    if not match:
        return None
    try:
        result = date(*map(int, match.groups()))
        return result.isoformat() if result <= datetime.now(timezone.utc).date() else None
    except ValueError:
        return None


def creation_value(record):
    return next(((key, iso_day(record[key])) for key in CREATION_KEYS
                 if key in record and iso_day(record[key])), None)


def recorded_file_date(value, sha):
    """A nested per-file creation timestamp must describe this exact source."""
    if isinstance(value, dict):
        created = creation_value(value)
        if created and sha in (value.get('sha256'), value.get('hash')):
            return created
        for child in value.values():
            result = recorded_file_date(child, sha)
            if result:
                return result
    elif isinstance(value, list):
        for child in value:
            result = recorded_file_date(child, sha)
            if result:
                return result
    return None


def attach_creation_dates(data, engine, concepts):
    engine, concepts = Path(engine).resolve(), Path(concepts).resolve()

    @lru_cache(maxsize=None)
    def read_manifest(path):
        if not path.is_file() or path.stat().st_size > 10_000_000:
            return None
        try:
            value = json.loads(path.read_text(encoding='utf-8-sig'))
            return value if isinstance(value, dict) else None
        except (ValueError, UnicodeError):
            return None

    for item in data['media'].values():
        source = item['source']
        is_concept = source.startswith('concept-art/')
        root = concepts if is_concept else engine
        path = root / (source.removeprefix('concept-art/') if is_concept else source)
        path = path.resolve()
        chosen = None
        if path.is_relative_to(root):
            # Only nearby artwork manifests; broader project dates do not describe
            # individual media. Collection dates are explicitly estimates.
            for base in path.parents:
                if base == root or base.name in {'experiments', 'art-library', 'assets', 'source'}:
                    break
                for name in ('manifest.json', 'metadata.json', 'render-manifest.json'):
                    manifest_path = base / name
                    manifest = read_manifest(manifest_path)
                    if not manifest:
                        continue
                    label = ('concept-art/' if is_concept else '') + manifest_path.relative_to(root).as_posix()
                    exact = recorded_file_date(manifest, item['sha256'])
                    if exact:
                        chosen = (exact[1], 'recorded', f'Creation date recorded for this source hash in {label} ({exact[0]}).')
                        break
                    scoped = creation_value(manifest)
                    if not scoped and iso_day(manifest.get('date')):
                        scoped = ('date', iso_day(manifest['date']))
                    # Imported references and acquisition sources can predate a set.
                    relative_parts = set(path.relative_to(base).parts[:-1])
                    if not chosen and scoped and not relative_parts.intersection({'reference', 'references', 'sources', 'source', 'concepts'}):
                        chosen = (scoped[1], 'estimated', f'Estimated from the containing artwork manifest {label} ({scoped[0]}); no individual creation timestamp is recorded.')
                if chosen:
                    break
        if not chosen:
            # The deepest dated study is a useful estimate, never an exact date.
            dates = [iso_day(match.group()) for match in DATE_PATTERN.finditer(source)]
            dates = [day for day in dates if day]
            if dates and not is_concept:
                chosen = (dates[-1], 'estimated', 'Estimated from the dated source study path; later revisions may have been made after this date.')
        if not chosen:
            chosen = (None, 'unknown', 'No artwork creation date is recorded. Archive, export, upload and file-copy dates are not used.')
        item['createdDate'], item['createdDateBasis'], item['createdDateEvidence'] = chosen
    counts = Counter(item['createdDateBasis'] for item in data['media'].values())
    dated = sorted(item['createdDate'] for item in data['media'].values() if item['createdDate'])
    data['creationDates'] = {
        'counts': {key: counts[key] for key in ('recorded', 'estimated', 'unknown')},
        'earliest': dated[0] if dated else None, 'latest': dated[-1] if dated else None,
        'policy': 'Recorded source creation dates take priority. Study or set dates are estimates. Export, upload and filesystem dates are never treated as creation dates.'
    }
    return data
