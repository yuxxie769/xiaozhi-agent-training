import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from prepare_sft_supplements import (configuration_identity,grounded_fingerprint,
    prepare,Library,home_generator,QUOTAS)


class SupplementTests(unittest.TestCase):
    def test_preset_rename_does_not_create_new_task(self):
        cfg={'preset':'old','description':'old','devices':{'light.one':{'name':'一号灯','state':'off','controllable':True}},'candidates':['light.one']}
        renamed=copy.deepcopy(cfg);renamed.update(preset='new',description='new')
        a={'preset':'old','template_id':'T04','target':{'entity_id':'light.one'}}
        b={**a,'preset':'new','seed_id':'different'}
        configs={'old':cfg,'new':renamed}
        self.assertEqual(grounded_fingerprint(a,configs),grounded_fingerprint(b,configs))
        renamed['devices']['light.one']['state']='on'
        self.assertNotEqual(grounded_fingerprint(a,configs),grounded_fingerprint(b,configs))

    def test_snapshot_library_returns_defensive_copies(self):
        cfg={'preset':'new','devices':{'light.one':{'name':'灯','state':'off','controllable':True}},'candidates':['light.one']}
        lib=Library.from_snapshots({'new':cfg})
        copy_cfg=lib.resolve('new');copy_cfg['devices']['light.one']['state']='on'
        self.assertEqual(lib.resolve('new')['devices']['light.one']['state'],'off')

    def test_full_preparation_reproduces_all_eighty(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/'a',Path(tmp)/'b'
            first=prepare(ROOT,a);second=prepare(ROOT,b)
            self.assertEqual(first,second)
            for path in a.iterdir():self.assertEqual(path.read_bytes(),(b/path.name).read_bytes())
            self.assertEqual(first['scenarios']['home_switch']['tasks'],60)
            self.assertEqual(first['scenarios']['weather']['tasks'],20)
            snapshots=json.loads((a/'preset-snapshots.json').read_text())
            library=Library.from_snapshots(snapshots)
            for seed in json.loads((a/'home_switch-seeds.json').read_text()):
                home_generator.validate_seed(seed,library)
            with self.assertRaises(ValueError):prepare(ROOT,a)


if __name__=='__main__':unittest.main()
