import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from date_metadata import attach_creation_dates
from demo_metadata import attach_demo_metadata


class MetadataTests(unittest.TestCase):
    def test_creation_dates_do_not_use_archive_or_copy_dates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for folder, metadata in {
                'art/recorded': {'files': [{'sha256': 'a'*64, 'created_at': '2026-09-23T01:02:03Z'}]},
                'art/estimated': {'created_date': '2026-09-24'},
                'concepts/archive': {'export_date': '2026-09-26', 'updated_at': '2026-09-27'},
            }.items():
                path = root/folder
                path.mkdir(parents=True)
                (path/'manifest.json').write_text(json.dumps(metadata), encoding='utf-8')
            sources = ['art/recorded/picture.png','art/estimated/runtime/picture.png',
                       'art/estimated/sources/reference.png','concept-art/archive/picture.png',
                       'experiments/study-20260921/revision/picture.png']
            data = {'media': {str(i): {'source': s,'sha256': 'a'*64} for i,s in enumerate(sources)}}
            attach_creation_dates(data, root, root/'concepts')
            result = [(i['createdDate'],i['createdDateBasis']) for i in data['media'].values()]
            self.assertEqual(result, [('2026-09-23','recorded'),('2026-09-24','estimated'),
                                     (None,'unknown'),(None,'unknown'),('2026-09-21','estimated')])

    def test_package_change_clears_stale_demo_memberships(self):
        data = {'media': {'a': {'demoStatus': 'in-demo'}}}
        with patch('demo_metadata._verified_index', side_effect=ValueError('changed')):
            attach_demo_metadata(data, Path('.'))
        self.assertEqual(data['media']['a']['demoStatus'],'unknown')
        self.assertEqual(data['demo']['verification'],'unverified')

    def test_packaged_but_inactive_is_not_a_positive(self):
        data = {'media': {'a': {'sha256':'a'*64,'source':'preview.png'},
                          'b': {'sha256':'b'*64,'source':'old.png'},
                          'c': {'sha256':'c'*64,'source':'retired.png'}}}
        with patch('demo_metadata._verified_index', return_value=(
            {'verification':'verified'}, {'a'*64:[('graphics/current.png','active.lua')]}, {'c'*64}, {'b'*64}
        )):
            attach_demo_metadata(data, Path('.'))
        self.assertEqual([i['demoStatus'] for i in data['media'].values()],['in-demo','unknown','not-in-demo'])


if __name__ == '__main__':
    unittest.main()
