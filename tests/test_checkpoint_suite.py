"""Checkpoint 队列恢复逻辑的离线测试。"""

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_sft_checkpoint_suite import latest_resumable_checkpoint  # noqa: E402


def write_checkpoint(run, step, *, recorded_step=None, complete=True):
    checkpoint = run / f"checkpoint-{step}"
    checkpoint.mkdir(parents=True)
    (checkpoint / "trainer_state.json").write_text(
        json.dumps({"global_step": step if recorded_step is None else recorded_step})
    )
    if complete:
        (checkpoint / "optimizer.pt").write_bytes(b"optimizer")
        (checkpoint / "scheduler.pt").write_bytes(b"scheduler")
    return checkpoint


class CheckpointResumeTests(unittest.TestCase):
    def test_uses_latest_complete_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            write_checkpoint(run, 89)
            expected = write_checkpoint(run, 178)
            write_checkpoint(run, 267, complete=False)
            self.assertEqual(latest_resumable_checkpoint(run), expected)

    def test_rejects_partial_and_mismatched_checkpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            write_checkpoint(run, 89, complete=False)
            write_checkpoint(run, 178, recorded_step=177)
            (run / "checkpoint-not-a-step").mkdir()
            self.assertIsNone(latest_resumable_checkpoint(run))

    def test_corrupt_newer_checkpoint_falls_back_to_last_complete_one(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            expected = write_checkpoint(run, 89)
            corrupt = write_checkpoint(run, 178)
            (corrupt / "trainer_state.json").write_text("not json")
            self.assertEqual(latest_resumable_checkpoint(run), expected)


if __name__ == "__main__":
    unittest.main()
