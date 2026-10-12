"""Check the actual repaired dataset against immutable v1 inputs and reviews."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import prepare_training_data as prep


def jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def by_id(directory):
    rows = jsonl(directory / 'train.jsonl')
    meta = jsonl(directory / 'metadata.jsonl')
    return {record['id']: rows[record['row_index']] for record in meta}


@unittest.skipUnless((ROOT/'data/prepared-v2/train.jsonl').exists(), 'Repaired export is not available yet')
class RepairedDatasetTests(unittest.TestCase):
    def test_only_the_three_approved_old_samples_change(self):
        before = by_id(ROOT/'data/prepared')
        after = by_id(ROOT/'data/prepared-v2')
        expected = {'home_switch:T14-G004-P2','weather:S11-G03-P2','weather:S15-G03-P2'}
        self.assertTrue(set(before) <= set(after))
        self.assertEqual({key for key, row in before.items() if row != after[key]}, expected)
        for key in expected:
            old, new = before[key], after[key]
            self.assertEqual(old['tools'], new['tools'])
            self.assertEqual(len(old['messages']), len(new['messages']))
            differences = [(a,b) for a,b in zip(old['messages'],new['messages']) if a != b]
            self.assertEqual(len(differences),1)
            a,b = differences[0]
            self.assertEqual(a['role'],'assistant')
            self.assertEqual({k:v for k,v in a.items() if k!='content'},
                             {k:v for k,v in b.items() if k!='content'})

    def test_old_exclusions_and_original_files_are_preserved(self):
        checks = prep.read_json(ROOT/'data/sft-repair/v1/original-files.json')
        for name, checksum in checks.items():
            self.assertEqual(prep.file_hash(ROOT/name),checksum,name)
        for name in ('failed.jsonl','review.jsonl'):
            before = {row['id'] for row in jsonl(ROOT/'data/prepared'/name)}
            after = {row['id'] for row in jsonl(ROOT/'data/prepared-v2'/name)}
            self.assertTrue(before <= after)

    def test_new_training_rows_have_accepted_source_bound_reviews(self):
        old_ids = set(by_id(ROOT/'data/prepared'))
        reviews = prep.read_json(ROOT/'data/sft-repair/v1/supplements/evidence-reviews.json')
        for row in jsonl(ROOT/'data/prepared-v2/metadata.jsonl'):
            if row['id'] not in old_ids:
                self.assertEqual(reviews[row['id']]['decision'],'accept')
                self.assertEqual(reviews[row['id']]['source_sample_sha256'],row['original_sample_sha256'])
                self.assertEqual(row['evidence_review'],reviews[row['id']])

    def test_export_is_byte_reproducible_without_model_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'prepared'
            prep.prepare(ROOT/'data/sft-repair/v1/derived/config.json', output)
            original = ROOT/'data/prepared-v2'
            self.assertEqual({p.name for p in original.iterdir()}, {p.name for p in output.iterdir()})
            for p in original.iterdir():
                self.assertEqual(p.read_bytes(),(output/p.name).read_bytes(),p.name)


if __name__ == '__main__':
    unittest.main()
