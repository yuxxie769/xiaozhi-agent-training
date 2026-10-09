import copy
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


if __name__ == "__main__":
    unittest.main()
