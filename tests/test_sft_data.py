"""训练入口的回归测试：坏数据不能静默跳过，试跑必须含最长轨迹。"""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sft_data import (AssistantOnlyCollator, TrainConfig, assert_batch_preserved,
                      check_inputs, load_config, read_jsonl, select_smoke_indices, sha256)
from train_sft import configure_wandb, training_argument_values, verify_local_model_dir


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

    def test_current_training_config_uses_repaired_data_and_expected_epoch_steps(self):
        config, prepared, _ = load_config(ROOT / "train-sft-v5.json")
        ids = json.loads((ROOT / config.oversample_ids_file).read_text())["ids"]
        metadata = [json.loads(line) for line in (prepared / "metadata.jsonl").read_text().splitlines()]
        self.assertEqual(len(metadata), 606)
        self.assertEqual(len(ids), 53)
        self.assertTrue(set(ids) <= {row["id"] for row in metadata})
        effective = len(metadata) + (config.oversample_factor - 1) * len(ids)
        self.assertEqual(effective, 712)
        args = training_argument_values(config, "/tmp/unused", "train", effective)
        self.assertEqual(args["save_steps"], 89)
        self.assertEqual(args["save_total_limit"], 3)

    def test_wandb_config_overrides_stale_server_project(self):
        config, _, _ = load_config(ROOT / "train-sft-v5.json")
        with patch.dict("os.environ", {"WANDB_API_KEY": "test", "WANDB_PROJECT": "stale"}, clear=True):
            self.assertTrue(configure_wandb(config))
            self.assertEqual(__import__("os").environ["WANDB_PROJECT"], config.wandb_project)
            self.assertEqual(__import__("os").environ["WANDB_LOG_MODEL"], "false")

    def test_training_cli_requires_explicit_config(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/train_sft.py"),
             "--mode", "preflight", "--output-dir", "/tmp/not-created-by-argparse"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--config", result.stderr)

    def test_tampered_training_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            prepared = Path(directory) / "prepared"
            shutil.copytree(ROOT / "data/prepared", prepared)
            with (prepared / "train.jsonl").open("a") as stream:
                stream.write('{}\n')
            with self.assertRaisesRegex(ValueError, "prepared_artifact_changed:train.jsonl"):
                check_inputs(prepared, ROOT / "tokenizer")

    def test_local_model_must_match_snapshot_and_contain_all_shards(self):
        snapshot = json.loads((ROOT / "tokenizer/snapshot.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "model"
            model.mkdir()
            for name in snapshot["files"]:
                shutil.copy2(ROOT / "tokenizer" / name, model / name)
            first = model / "weights-1.safetensors"
            second = model / "weights-2.safetensors"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            index = model / "model.safetensors.index.json"
            index.write_text(json.dumps({
                "weight_map": {"a": "weights-1.safetensors", "b": "weights-2.safetensors"}
            }))
            snapshot["weights"] = {
                "index": {"name": index.name, "bytes": index.stat().st_size,
                          "sha256": sha256(index)},
                "files": {path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
                          for path in (first, second)},
            }
            result = verify_local_model_dir(model, snapshot)
            self.assertEqual(result["local_model_dir"], str(model.resolve()))
            self.assertEqual(set(result["weight_files"]),
                             {"weights-1.safetensors", "weights-2.safetensors"})
            (model / "config.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "local_model_snapshot_mismatch:config.json"):
                verify_local_model_dir(model, snapshot)


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
