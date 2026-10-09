"""End-to-end acceptance on the saved source batch, without calling a model."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import prepare_training_data as prep


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


class DatasetAcceptanceTests(unittest.TestCase):
    def test_seed_generator_reads_independent_size_without_generating_seeds(self):
        import generate_evaluation_seeds as gen
        config = prep.read_json(ROOT / 'config.json')
        self.assertNotIn('test_fraction', config)
        self.assertNotIn('split_seed', config)
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(gen, 'apportion_groups', side_effect=RuntimeError('stop-before-generation')) as quotas:
                with self.assertRaisesRegex(RuntimeError, 'stop-before-generation'):
                    gen.main(['--config', str(ROOT / 'config.json'), '--output-dir', str(Path(directory) / 'unused')])
                self.assertEqual(quotas.call_args.args[1], config['evaluation_seed_fraction'])
                self.assertFalse((Path(directory) / 'unused').exists())

    def test_full_batch_fidelity_accounting_and_reproducibility(self):
        config = prep.read_json(ROOT / 'config.json')
        source_files = sorted((ROOT / 'data/raw').rglob('*.json'))
        before = {str(p): prep.file_hash(p) for p in source_files}
        sources = {}
        for source in config['sources']:
            for sample in prep.read_json(ROOT / source['conversations']):
                sources[f"{source['scenario']}:{sample['sample_id']}"] = sample
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / 'one', Path(directory) / 'two'
            summary = prep.prepare(ROOT / 'config.json', first)
            prep.prepare(ROOT / 'config.json', second)
            self.assertEqual({p.name: p.read_bytes() for p in first.iterdir()},
                             {p.name: p.read_bytes() for p in second.iterdir()})
            self.assertEqual(summary['source_samples'], 599)
            self.assertEqual([summary[k] for k in ['train_samples', 'failed_samples', 'quarantine', 'duplicates']],
                             [556, 28, 15, 0])
            self.assertEqual(set(p.name for p in first.iterdir()), {
                'train.jsonl', 'failed.jsonl', 'review.jsonl', 'inventory.json', 'report.md',
                'metadata.jsonl', 'audit.jsonl', 'system-prompt.txt', 'manifest.json'})
            audit = rows(first / 'audit.jsonl')
            self.assertEqual({r['id'] for r in audit}, set(sources))
            self.assertTrue(all('split' not in r for r in audit))
            dataset, metadata = rows(first / 'train.jsonl'), rows(first / 'metadata.jsonl')
            self.assertEqual(len(dataset), len(metadata))
            prompt = (ROOT / 'system-prompt.txt').read_text(encoding='utf-8').rstrip()
            weather = prep.read_json(ROOT / config['weather_tool_source'])
            for meta, row in zip(metadata, dataset):
                original = sources[meta['id']]
                self.assertEqual(row, dataset[meta['row_index']])
                self.assertEqual(prep.digest(row), meta['normalized_sha256'])
                self.assertEqual(set(row), {'messages', 'tools'})
                self.assertEqual(row['tools'], original['context'].get('tool_definitions') or [weather])
                if meta['scenario'] == 'weather':
                    self.assertEqual(row['messages'][0]['content'], prompt)
                else:
                    marker = '本次可信设备目录（controllable为允许开关，未列设备不在本次允许范围）：'
                    block = marker + original['messages'][0]['content'].split(marker, 1)[1]
                    self.assertEqual(row['messages'][0]['content'], prompt + '\n\n' + block)
                self.assertEqual(len(row['messages']), len(original['messages']))
                id_map = {}
                for old, new in zip(original['messages'][1:], row['messages'][1:]):
                    self.assertEqual(old['role'], new['role'])
                    self.assertEqual(old.get('content'), new.get('content'))
                    self.assertEqual(len(old.get('tool_calls') or []), len(new.get('tool_calls') or []))
                    for oc, nc in zip(old.get('tool_calls') or [], new.get('tool_calls') or []):
                        id_map[oc['id']] = nc['id']
                        self.assertEqual(oc['function']['name'], nc['function']['name'])
                        args = oc['function']['arguments']
                        self.assertEqual(json.loads(args) if isinstance(args, str) else args, nc['function']['arguments'])
                    if old['role'] == 'tool':
                        self.assertEqual(id_map[old['tool_call_id']], new['tool_call_id'])
            for record in rows(first / 'review.jsonl'):
                self.assertEqual(record['reason'], 'runtime_injected_messages')
                self.assertTrue(sources[record['id']]['context']['internal_message_indices'])
            inv = prep.read_json(first / 'inventory.json')
            self.assertEqual(inv['sources']['scenario_counts'], {'weather': 300, 'home_switch': 299})
            self.assertEqual(inv['dialogue_structure']['by_scenario']['weather']['turn_counts'], {'1': 165, '2': 135})
            self.assertEqual(inv['dialogue_structure']['by_scenario']['home_switch']['turn_counts'], {'1': 87, '2': 197, '3': 15})
            for filename, checksum in summary['artifact_sha256'].items():
                self.assertEqual(prep.file_hash(first / filename), checksum)
        self.assertEqual(before, {str(p): prep.file_hash(p) for p in source_files})


if __name__ == '__main__':
    unittest.main()
