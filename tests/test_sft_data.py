"""训练入口的回归测试：坏数据不能静默跳过，试跑必须含最长轨迹。"""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sft_data import (AssistantOnlyCollator, TrainConfig, assert_batch_preserved,
                      check_inputs, load_config, read_jsonl, select_smoke_indices)


class SFTInputTests(unittest.TestCase):
    def test_thinking_cannot_be_enabled_accidentally(self):
        values = json.loads((ROOT / "train-sft.json").read_text())
        values["enable_thinking"] = True
        with self.assertRaisesRegex(ValueError, "非思考"):
            TrainConfig(**values)

    def test_bad_or_blank_jsonl_is_not_silently_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.jsonl"
            path.write_text('{"messages": []}\n\n')
            with self.assertRaises(json.JSONDecodeError):
                read_jsonl(path)

    def test_smoke_contains_longest_of_each_scene_and_is_repeatable(self):
        records = [{"scenario": "a" if i < 5 else "b", "tokens": i + 100} for i in range(10)]
        first = select_smoke_indices(records, 5, 42)
        self.assertEqual(first, select_smoke_indices(records, 5, 42))
        self.assertEqual(len(set(first)), 5)
        self.assertTrue({4, 9}.issubset(first))
        with self.assertRaises(ValueError):
            select_smoke_indices(records, 1, 42)

    def test_paths_resolve_relative_to_config(self):
        _, prepared, tokenizer = load_config(ROOT / "train-sft.json")
        self.assertEqual(prepared, ROOT / "data/prepared")
        self.assertEqual(tokenizer, ROOT / "tokenizer")

    def test_tampered_training_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            prepared = Path(directory) / "prepared"
            shutil.copytree(ROOT / "data/prepared", prepared)
            with (prepared / "train.jsonl").open("a") as stream:
                stream.write('{}\n')
            with self.assertRaisesRegex(ValueError, "prepared_artifact_changed:train.jsonl"):
                check_inputs(prepared, ROOT / "tokenizer")


@unittest.skipUnless(importlib.util.find_spec("torch"), "需要 PyTorch CPU 或 GPU 环境")
class CollatorTests(unittest.TestCase):
    def test_padding_keeps_eos_and_all_existing_masks(self):
        # 特意让 EOS 与 padding 使用同一个 ID；有效 EOS 不能被误屏蔽。
        rows = [dict(input_ids=[1, 2, 9], attention_mask=[1, 1, 1], labels=[-100, 2, 9]),
                dict(input_ids=[3, 9], attention_mask=[1, 1], labels=[-100, 9])]
        batch = AssistantOnlyCollator(9)(rows)
        assert_batch_preserved(batch, rows)
        self.assertEqual(batch["labels"].tolist(), [[-100, 2, 9], [-100, 9, -100]])
        batch["labels"][0, 0] = 1
        with self.assertRaisesRegex(ValueError, "trainer_changed_labels"):
            assert_batch_preserved(batch, rows)

    def test_empty_loss_target_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "没有可学习"):
            AssistantOnlyCollator(0)([dict(input_ids=[1], attention_mask=[1], labels=[-100])])


if __name__ == "__main__":
    unittest.main()
