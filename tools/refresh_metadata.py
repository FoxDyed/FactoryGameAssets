"""Refresh gallery creation dates and current-demo evidence without re-encoding media."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from date_metadata import attach_creation_dates
from demo_metadata import attach_demo_metadata


def refresh(data, engine, concepts):
    attach_creation_dates(data, engine, concepts)
    attach_demo_metadata(data, engine)
    data['updated'] = datetime.now(timezone.utc).isoformat()
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--concepts', type=Path, required=True)
    args = parser.parse_args()
    target = Path(__file__).resolve().parents[1] / 'docs/data/catalog.json'
    data = refresh(json.loads(target.read_text(encoding='utf-8')), args.engine, args.concepts)
    target.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(json.dumps({'creationDates': data['creationDates'], 'demo': data['demo']}, indent=2))
