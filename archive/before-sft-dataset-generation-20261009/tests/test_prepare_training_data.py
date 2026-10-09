import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

CLIENT = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(CLIENT))
import prepare_training_data as prep


TOOLS = [{"type": "function", "function": {"name": "get_weather", "parameters": {
    "type": "object", "properties": {"lang": {"type": "string"}}, "required": ["lang"],
}}}]


def sample():
    return {
        "sample_id": "a", "seed": {"seed_id": "a", "template_id": "S01", "user_turns": ["天气如何？"], "target_city": "SECRET_TARGET"},
        "context": {"trace_complete": True, "base_date": "2026-09-30", "timezone": "Asia/Shanghai", "simulator": {"secret": "HIDDEN_STATE"}},
        "messages": [
            {"role": "system", "content": "old prompt"},
            {"role": "user", "content": "天气如何？"},
            {"role": "assistant", "tool_calls": [{"id": "old", "index": 0, "type": "function", "function": {"name": "get_weather", "arguments": '{"lang":"zh_CN"}'}}]},
            {"role": "tool", "content": "晴", "tool_call_id": "old"},
            {"role": "assistant", "content": "晴。"},
        ],
    }


class PreparationTests(unittest.TestCase):
    def test_calls_and_results_are_linked_without_mutating_source(self):
        s = sample()
        before = copy.deepcopy(s)
        messages = prep.normalize_messages(s, TOOLS)
        self.assertEqual(s, before)
        call = messages[1]["tool_calls"][0]
        self.assertEqual(call["function"]["arguments"], {"lang": "zh_CN"})
        self.assertEqual(call["id"], messages[2]["tool_call_id"])
        self.assertNotIn("index", call)

    def test_missing_result_rejected(self):
        s = sample()
        del s["messages"][3]
        with self.assertRaisesRegex(prep.DataError, "missing_tool_response"):
            prep.normalize_messages(s, TOOLS)

    def test_orphan_result_rejected(self):
        s = sample()
        s["messages"][3]["tool_call_id"] = "other"
        with self.assertRaisesRegex(prep.DataError, "orphan"):
            prep.normalize_messages(s, TOOLS)

    def test_invalid_action_only_allowed_in_rejected_review(self):
        s = sample()
        s["messages"][2]["tool_calls"][0]["function"]["name"] = "invented_tool"
        with self.assertRaisesRegex(prep.DataError, "unknown_tool"):
            prep.normalize_messages(s, TOOLS)
        issues = []
        messages = prep.normalize_messages(s, TOOLS, issues)
        self.assertEqual(issues, [{"tool": "invented_tool", "reason": "unknown_tool"}])
        self.assertEqual(messages[1]["tool_calls"][0]["function"]["name"], "invented_tool")

    def test_missing_required_argument_not_repaired(self):
        s = sample()
        s["messages"][2]["tool_calls"][0]["function"]["arguments"] = "{}"
        with self.assertRaisesRegex(prep.DataError, "missing_required"):
            prep.normalize_messages(s, TOOLS)

    def test_runtime_prompt_cannot_be_silently_removed(self):
        s = sample()
        s["context"]["internal_message_indices"] = [4]
        with self.assertRaisesRegex(prep.DataError, "runtime_injected"):
            prep.normalize_messages(s, TOOLS)

    def test_source_system_hash_checked(self):
        s = sample()
        s["context"]["system_prompt_sha256"] = "wrong"
        with self.assertRaisesRegex(prep.DataError, "system_hash"):
            prep.normalize_messages(s, TOOLS)

    def test_no_hidden_context_in_model_input(self):
        text = prep.session_system(sample(), "shared", "weather")
        self.assertIn("2026-09-30", text)
        self.assertNotIn("SECRET_TARGET", text)
        self.assertNotIn("HIDDEN_STATE", text)

    def test_catalog_must_be_visible_and_cannot_include_hidden_state(self):
        s = sample()
        catalog = [{"entity_id": "light.a", "name": "灯", "controllable": True}]
        s["context"]["public_catalog"] = catalog
        s["messages"][0]["content"] += "\n本次可信设备目录（controllable为允许开关，未列设备不在本次允许范围）：\n" + json.dumps(catalog)
        self.assertIn("light.a", prep.session_system(s, "shared", "home_switch"))
        s["context"]["public_catalog"][0]["state"] = "on"
        with self.assertRaisesRegex(prep.DataError, "catalog_mismatch"):
            prep.session_system(s, "shared", "home_switch")

    def test_splits_keep_templates_and_duplicate_queries_together(self):
        entries = []
        for i in range(10):
            for variant in range(2):
                s = sample()
                s["seed"]["user_turns"] = ["same" if i < 2 else f"q{i}-{variant}"]
                entries.append({"scenario": "weather", "group": f"weather:S{i}", "sample": s})
        prep.assign_splits(entries, "seed", 0.2)
        self.assertEqual({e["split"] for e in entries}, {"train", "test"})
        for i in range(10):
            self.assertEqual(len({e["split"] for e in entries if e["group"] == f"weather:S{i}"}), 1)
        self.assertEqual(entries[0]["split"], entries[2]["split"])
        reversed_entries = copy.deepcopy(list(reversed(entries)))
        prep.assign_splits(reversed_entries, "seed", 0.2)
        self.assertEqual({e["group"]: e["split"] for e in entries}, {e["group"]: e["split"] for e in reversed_entries})

    def test_incomplete_scores_not_accepted_as_positive(self):
        import weather_scoring
        s = sample()
        score = {"seed_id": "a", "template_id": "S01", "status": "pass", "checks": []}
        with patch.object(weather_scoring, "analyze", return_value={}), patch.object(weather_scoring, "plan_checks", return_value=({"1:C01": {}}, [], [])):
            with self.assertRaisesRegex(prep.DataError, "incomplete"):
                prep.validate_score(s, score, "weather")

    def test_stale_score_evidence_rejected(self):
        import weather_scoring
        score = {"seed_id": "a", "template_id": "S01", "status": "pass", "checks": [
            {"turn": 1, "check_id": "C01", "status": "pass", "evidence": [{"message_index": 4, "quote": "雨"}]},
        ]}
        with patch.object(weather_scoring, "analyze", return_value={}), patch.object(weather_scoring, "plan_checks", return_value=({"1:C01": {}}, [], [])):
            with self.assertRaisesRegex(prep.DataError, "stale_score"):
                prep.validate_score(sample(), score, "weather")

    def test_output_directory_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(prep.DataError, "output_exists"):
                prep.prepare(CLIENT.parent / "config.json", directory)


if __name__ == "__main__":
    unittest.main()
