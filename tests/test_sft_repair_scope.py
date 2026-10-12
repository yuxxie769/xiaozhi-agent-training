"""Regression checks for the user's targeted repair and evidence-review boundary."""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import prepare_training_data as prep
import recheck_sft_data as repair


class RepairScopeTests(unittest.TestCase):
    def test_bulk_execution_is_rejected_before_any_model_request(self):
        with patch.object(repair,'check_gate'),patch.object(repair,'read',return_value={'planned_samples':556}),patch.object(repair.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'已取消全量重评'):
                repair.execute(Path('/server'),Path('/python'),Path('/config'),Path('/validation'),Path('/output'))
            run.assert_not_called()

    def test_only_three_assistant_bodies_are_replaced(self):
        root=ROOT/'data/sft-repair/v1/targeted'
        if not root.exists():self.skipTest('Local repair artifacts are required')
        edits=json.loads((root/'edits.json').read_text())
        self.assertEqual({e['sample_id'] for e in edits},{'T14-G004-P2','S11-G03-P2','S15-G03-P2'})
        for scene in ('weather','home_switch'):
            originals=prep.indexed(prep.read_json(root/'inputs'/f'{scene}-conversations.json'))
            corrected=prep.indexed(prep.read_json(root/'inputs'/f'{scene}-corrected.json'))
            for edit in (e for e in edits if e['scenario']==scene):
                old=originals[edit['sample_id']];new=copy.deepcopy(corrected[edit['sample_id']]);index=edit['message_index']
                self.assertEqual(old['messages'][index]['role'],'assistant')
                self.assertEqual(new['messages'][index]['content'],edit['replacement'])
                new['messages'][index]['content']=edit['original']
                self.assertEqual(new,old)

    def test_evidence_review_is_bound_to_exact_source(self):
        entry={'id':'weather:new','sample':{'sample_id':'new'},'require_evidence_review':True}
        with self.assertRaisesRegex(prep.DataError,'missing_evidence_review'):
            prep.check_evidence_review(entry,{})
        review={'decision':'accept','source_sample_sha256':prep.digest(entry['sample']),'reason':'日期与工具逐项一致'}
        prep.check_evidence_review(entry,{entry['id']:review})
        entry['sample']['messages']=['changed']
        with self.assertRaisesRegex(prep.DataError,'source_mismatch'):
            prep.check_evidence_review(entry,{entry['id']:review})

    def test_quarantine_is_not_a_score_override(self):
        entry={'id':'weather:new','sample':{},'require_evidence_review':True}
        reviews={entry['id']:{'decision':'quarantine','source_sample_sha256':prep.digest({}),'reason':'将当前降水量当成整日无雨'}}
        with self.assertRaisesRegex(prep.DataError,'evidence_review:'):
            prep.check_evidence_review(entry,reviews)
        prep.check_evidence_review(dict(entry,require_evidence_review=False),{})


if __name__=='__main__':unittest.main()
