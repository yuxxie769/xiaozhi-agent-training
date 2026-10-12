"""Offline checks for the recheck gate and immutable source selection."""
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'scripts'))
import recheck_sft_data as repair
SERVER=PROJECT.parent/'xiaozhi-esp32-server/main/xiaozhi-server'
VALIDATION=SERVER/'tmp/scorer-validation/factuality-20261012-v4/validation.json'


class RecheckTests(unittest.TestCase):
    def test_gate_requires_success_and_current_code(self):
        gate={'status':'failed','matched':47,'planned':48}
        with patch.object(repair,'read',return_value=gate):
            with self.assertRaises(ValueError):repair.check_gate(SERVER,VALIDATION)
        gate.update(status='passed',matched=48,code_sha256={n:'wrong' for n in
            ('weather_scoring.py','home_switch_scoring.py','eval_scoring.py','eval_judge.py')})
        with patch.object(repair,'read',return_value=gate):
            with self.assertRaises(ValueError):repair.check_gate(SERVER,VALIDATION)

    @unittest.skipUnless(VALIDATION.exists(),'Local accepted scoring validation is required for source-binding integration')
    def test_prepare_selects_exact_baseline_and_is_reproducible(self):
        before=repair.sha(PROJECT/'data/prepared/train.jsonl')
        with tempfile.TemporaryDirectory() as tmp, patch.object(repair.subprocess,'run',side_effect=AssertionError('offline stage must not launch a model')):
            first=Path(tmp)/'first';second=Path(tmp)/'second'
            a=repair.prepare(PROJECT,SERVER,VALIDATION,first)
            b=repair.prepare(PROJECT,SERVER,VALIDATION,second)
            self.assertEqual(a,b)
            self.assertEqual(a['planned_samples'],3)
            self.assertEqual(a['sources']['weather']['count'],2)
            self.assertEqual(a['sources']['home_switch']['count'],1)
            for name in a['input_sha256']:
                self.assertEqual((first/'inputs'/name).read_bytes(),(second/'inputs'/name).read_bytes())
            with self.assertRaises(ValueError):repair.prepare(PROJECT,SERVER,VALIDATION,first)
            selected=json.loads((first/'inputs/home_switch-conversations.json').read_text())
            raw={r['sample_id']:r for r in repair.read(PROJECT/'data/raw/home_switch/conversations.json')}
            for row in selected:self.assertEqual(row,raw[row['sample_id']])
        self.assertEqual(before,repair.sha(PROJECT/'data/prepared/train.jsonl'))

    def test_execution_rejects_tampered_inputs_without_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(repair,'check_gate'), patch.object(repair.subprocess,'run') as run:
            root=Path(tmp)
            repair.write(root/'input-manifest.json',{'planned_samples':3,'input_sha256':{'input.json':'old'}})
            repair.write(root/'inputs/input.json',{'changed':True})
            with self.assertRaises(ValueError):repair.execute(SERVER,Path(sys.executable),Path('config'),VALIDATION,root)
            run.assert_not_called()


if __name__=='__main__':unittest.main()
