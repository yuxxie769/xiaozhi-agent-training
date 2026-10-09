import copy
import contextlib
import io
import json
import shutil
import tempfile
from unittest.mock import patch
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import generate_evaluation_seeds as gen


def seed(group="S01-G01", pattern="P1", city="深圳", wording="天气怎么样？"):
    return {
        "seed_id": f"{group}-{pattern}",
        "template_id": "S01",
        "variable_group_id": group,
        "question_pattern_id": pattern,
        "default_city": city,
        "target_city": city,
        "target_day": 0,
        "query_kind": "overview",
        "user_turns": [wording],
        "scenario_ids": ["T01"],
    }


class EvaluationSeedTests(unittest.TestCase):
    def test_semantic_fingerprint_ignores_ids_and_wording(self):
        first = seed()
        second = seed("S01-G99", "P3", wording="今天啥天气？")
        self.assertEqual(gen.semantic_fingerprint(first), gen.semantic_fingerprint(second))

    def test_semantic_fingerprint_changes_with_real_variable(self):
        self.assertNotEqual(
            gen.semantic_fingerprint(seed()),
            gen.semantic_fingerprint(seed(city="广州")),
        )

    def test_group_requires_three_patterns(self):
        with self.assertRaisesRegex(gen.GenerationError, "P1/P2/P3"):
            gen.group_seeds([seed()])

    def test_group_semantics_must_match(self):
        rows = [seed(pattern=f"P{i}", city="深圳" if i < 3 else "广州") for i in range(1, 4)]
        with self.assertRaisesRegex(gen.GenerationError, "语义字段不一致"):
            gen.group_seeds(rows)

    def test_template_counts_use_pass_status(self):
        report = {"samples": [
            {"template_id": "S01", "status": "pass"},
            {"template_id": "S01", "status": "fail"},
            {"template_id": "S02", "status": "pass"},
        ]}
        self.assertEqual(gen.template_counts(report), {"S01": 1, "S02": 1})
        self.assertEqual(gen.template_counts(report, "all"), {"S01": 2, "S02": 1})

    def test_apportionment_keeps_every_template_and_total(self):
        quotas, requested = gen.apportion_groups({"S01": 80, "S02": 20}, 0.3, 10)
        self.assertEqual(requested, 30)
        self.assertEqual(sum(quotas.values()), 10)
        self.assertGreater(quotas["S01"], quotas["S02"])
        self.assertGreaterEqual(min(quotas.values()), 1)

    def test_collision_rejects_source_semantics_before_wording(self):
        rows = [seed(pattern=f"P{i}", wording=f"问法{i}") for i in range(1, 4)]
        semantics, wording = gen.source_index([seed(wording="旧问法")])
        reason, _, _ = gen.candidate_collision(rows, semantics, set())
        self.assertEqual(reason, "source_semantic")

    def test_collision_allows_identical_wording_with_different_variables(self):
        rows = [seed(pattern=f"P{i}", city="广州", wording="相同问法") for i in range(1, 4)]
        semantics, wording = gen.source_index([seed(wording="相同问法")])
        reason, _, _ = gen.candidate_collision(rows, semantics, set())
        self.assertIsNone(reason)

    def test_rename_preserves_source_object(self):
        rows = [seed(pattern=f"P{i}", wording=f"问法{i}") for i in range(1, 4)]
        original = copy.deepcopy(rows)
        renamed = gen.rename_group(rows, 2)
        self.assertEqual(rows, original)
        self.assertEqual({x["variable_group_id"] for x in renamed}, {"S01-E002"})


class PreparedEvaluationTests(unittest.TestCase):
    ROOT = SCRIPTS.parent

    def test_quotas_use_exported_training_population_and_inventory(self):
        inputs, binding = gen.load_prepared_inputs(self.ROOT / 'config.json', self.ROOT / 'data/prepared')
        self.assertEqual(binding['source_samples'], 599)
        self.assertEqual(binding['training_samples'], 556)
        self.assertEqual(len(binding['target_tool_names']), 9)
        self.assertIn('tools.json', binding['artifact_sha256'])
        self.assertEqual(sum(inputs['weather']['counts'].values()), 283)
        self.assertEqual(sum(inputs['home_switch']['counts'].values()), 273)
        all_inputs, _ = gen.load_prepared_inputs(self.ROOT / 'config.json', self.ROOT / 'data/prepared', 'all')
        self.assertEqual(sum(all_inputs['home_switch']['counts'].values()), 299)
        self.assertEqual(all_inputs['weather']['counts'], inputs['weather']['inventory_template_counts'])

    def test_changed_prepared_artifacts_are_rejected(self):
        for name in ['inventory.json', 'train.jsonl', 'tools.json']:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                prepared = Path(directory) / 'prepared'
                shutil.copytree(self.ROOT / 'data/prepared', prepared)
                with (prepared / name).open('a') as output:
                    output.write(' ')
                with self.assertRaisesRegex(gen.GenerationError, '校验失败'):
                    gen.load_prepared_inputs(self.ROOT / 'config.json', prepared)

    def test_changed_raw_source_is_rejected(self):
        original = gen.sha256_file
        with patch.object(gen, 'sha256_file', side_effect=lambda path: 'changed' if Path(path).name == 'conversations.json' else original(path)):
            with self.assertRaisesRegex(gen.GenerationError, '数据准备版本不一致'):
                gen.load_prepared_inputs(self.ROOT / 'config.json', self.ROOT / 'data/prepared')

    def test_full_generation_is_repeatable_disjoint_and_preset_valid(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            outputs = [Path(directory) / 'a', Path(directory) / 'b']
            for output in outputs:
                gen.main(['--config', str(self.ROOT / 'config.json'), '--output-dir', str(output), '--random-seed', '20261009'])
            self.assertEqual({p.name: p.read_bytes() for p in outputs[0].iterdir()},
                             {p.name: p.read_bytes() for p in outputs[1].iterdir()})
            report = gen.read_json(outputs[0] / 'generation-report.json')
            for scenario in ['weather', 'home_switch']:
                source = self.ROOT / 'data/raw' / scenario / 'conversations.json'
                source_seeds = gen.extract_seed_rows(gen.read_json(source))
                generated = gen.read_json(outputs[0] / f'{scenario}-seeds.json')
                groups = gen.group_seeds(generated)
                self.assertEqual(len(generated), 60)
                self.assertEqual(len(groups), 20)
                self.assertEqual(len({r['seed_id'] for r in generated}), len(generated))
                semantics = {gen.semantic_fingerprint(group[0]) for group in groups.values()}
                self.assertEqual(len(semantics), len(groups))
                self.assertFalse(semantics & {gen.semantic_fingerprint(s) for s in source_seeds})
                self.assertEqual(gen.sha256_file(outputs[0] / f'{scenario}-seeds.json'), report['scenarios'][scenario]['output_sha256'])
                if scenario == 'home_switch':
                    library = gen.Library(source)
                    for row in generated:
                        gen.home_generator.validate_seed(row, library=library)

    def test_repeated_pattern_is_not_a_complete_group(self):
        rows = [seed(pattern=f'P{i}') for i in [1, 2, 3, 3]]
        with self.assertRaisesRegex(gen.GenerationError, '完整'):
            gen.group_seeds(rows)


if __name__ == "__main__":
    unittest.main()
