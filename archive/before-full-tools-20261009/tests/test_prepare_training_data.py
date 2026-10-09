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
        self.assertEqual(text, "shared")
        self.assertNotIn("Asia/Shanghai", text)
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

    def test_dates_are_not_required_or_added(self):
        s = sample()
        del s["context"]["base_date"]
        s["context"]["timezone"] = "not-a-timezone"
        self.assertEqual(prep.session_system(s, "shared", "weather"), "shared")

    def test_catalog_visible_text_and_order_preserved(self):
        s = sample()
        catalog = [{"entity_id": "light.z", "name": "灯二", "aliases": ["乙", "甲"], "controllable": True},
                   {"entity_id": "light.a", "name": "灯一", "controllable": False}]
        block = "本次可信设备目录（controllable为允许开关，未列设备不在本次允许范围）：\n" + json.dumps(catalog, ensure_ascii=False, indent=3) + "\n"
        s["messages"][0]["content"] = "old rules\n" + block
        s["context"]["public_catalog"] = copy.deepcopy(catalog)
        self.assertEqual(prep.session_system(s, "shared", "home_switch"), "shared\n\n" + block)
        s["context"]["public_catalog"].reverse()
        with self.assertRaisesRegex(prep.DataError, "catalog_mismatch"):
            prep.session_system(s, "shared", "home_switch")

    def test_inventory_counts_raw_traces_and_ignores_internal_user_turn(self):
        a = sample()
        a["seed"].update(variable_group_id="G1", question_pattern_id="P1", scenario_ids=["A", "A", "B"])
        b = copy.deepcopy(a)
        b["seed"].pop("question_pattern_id")
        b["messages"].append({"role": "user", "content": "INTERNAL"})
        b["context"]["internal_message_indices"] = [5]
        entries = [{"source_index": 0, "scenario": "weather", "sample": x} for x in [a, b]]
        inv = prep.build_inventory(entries, [{"source_index": 0, "scenario": "weather", "conversations": "raw.json"}])
        self.assertEqual(set(inv), {"schema_version", "definitions", "sources", "task_coverage", "dialogue_structure"})
        self.assertEqual(inv["sources"]["total"], 2)
        cov = inv["task_coverage"]["weather"]
        self.assertEqual(cov["question_pattern_id"], {"P1": 1, "未提供": 1})
        self.assertEqual(cov["scenario_ids"], {"A": 2, "B": 2})
        stats = inv["dialogue_structure"]["all"]
        self.assertEqual(stats["single_turn"], 2)
        self.assertEqual(stats["turn_counts"], {1: 2})
        self.assertEqual(stats["message_count_per_trace"], {"count": 2, "min": 5, "median": 5.5, "p90": 6, "max": 6})
        body = sum(len(m.get("content", "")) for m in a["messages"])
        self.assertEqual(stats["body_characters_per_trace"]["median"], body + 4)
        self.assertEqual(stats["argument_characters_per_call"]["min"], len('{"lang":"zh_CN"}'))
        self.assertEqual(prep.distribution([]), {"count": 0, "min": None, "median": None, "p90": None, "max": None})
        self.assertEqual(prep.distribution(list(range(1, 11)))["p90"], 9)

    def test_duplicate_provenance_failed_action_and_review_are_separate(self):
        rows = []
        for key in "abcde":
            row = sample()
            row["sample_id"] = row["seed"]["seed_id"] = key
            rows.append(row)
        rows[2]["messages"][2]["tool_calls"][0]["function"]["name"] = "invented_tool"
        rows[3]["context"]["internal_message_indices"] = [4]
        # The same text with a different available tool set is not an exact duplicate.
        rows[4]["context"]["tool_definitions"] = TOOLS + [{"type": "function", "function": {
            "name": "unused", "parameters": {"type": "object", "properties": {}}}}]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prep.write_json(root / "raw.json", rows)
            prep.write_json(root / "scores.json", {"samples": []})
            prep.write_json(root / "tool.json", TOOLS[0])
            (root / "prompt.txt").write_text("shared", encoding="utf-8")
            prep.write_json(root / "config.json", {"system_prompt": "prompt.txt", "weather_tool_source": "tool.json", "sources": [
                {"scenario": "weather", "conversations": "raw.json", "scores": "scores.json", "score_policy": "latest"}]})
            with patch.object(prep, "validate_score", side_effect=lambda sample, *_: [{"check_id": "bad"}] if sample["sample_id"] == "c" else []):
                summary = prep.prepare(root / "config.json", root / "out")
            self.assertEqual([summary[k] for k in ["train_samples", "failed_samples", "quarantine", "duplicates"]], [2, 1, 1, 1])
            audit = [json.loads(line) for line in (root / "out/audit.jsonl").read_text().splitlines()]
            self.assertEqual(audit[1]["duplicate_of"], "weather:a")
            failed = json.loads((root / "out/failed.jsonl").read_text())
            self.assertEqual(failed["invalid_actions"], [{"tool": "invented_tool", "reason": "unknown_tool"}])
            self.assertEqual(failed["trajectory"]["messages"][2]["tool_calls"][0]["function"]["name"], "invented_tool")

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
