"""用临时后端脚本验证调用链，不启动正式评测或推理服务。"""

import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_backend_evaluation as entry

# 子进程替身只写测试轨迹；它检查入口的参数和输入副本。
GENERATOR = """
import argparse, json
from pathlib import Path
p = argparse.ArgumentParser()
for key in ('scenario','environment','eval-config','seeds','system-prompt-file','tools-file','output-dir','tool-backend','preset-snapshots'):
    p.add_argument('--' + key)
a = p.parse_args()
assert a.environment == 'model_eval'
assert len(json.loads(Path(a.tools_file).read_text())) == 9
assert Path(a.system_prompt_file).read_text().strip()
if a.scenario == 'home_switch':
    assert a.tool_backend == 'simulated'
    assert json.loads(Path(a.preset_snapshots).read_text())
settings = json.loads(Path(a.eval_config).read_text())
if settings.get('crash') == a.scenario:
    raise SystemExit(2)
seeds = json.loads(Path(a.seeds).read_text())
partial = settings.get('partial') == a.scenario
rows = [{'sample_id': s['seed_id'], 'context': {'scenario': a.scenario}} for s in seeds[:1] if partial] if partial else [{'sample_id': s['seed_id'], 'context': {'scenario': a.scenario}} for s in seeds]
out = Path(a.output_dir)
out.mkdir(parents=True)
(out / 'conversations.json').write_text(json.dumps(rows))
(out / 'generation-report.json').write_text(json.dumps({'planned': len(seeds), 'saved': len(rows)}))
raise SystemExit(1 if partial else 0)
"""
SCORER = """
import argparse, json
from pathlib import Path
p = argparse.ArgumentParser()
for key in ('scenario','eval-config','output-dir'):
    p.add_argument('--' + key)
p.add_argument('--input', action='append')
p.add_argument('--generation-report', action='append')
a = p.parse_args()
assert a.scenario == 'auto'
settings = json.loads(Path(a.eval_config).read_text())
if settings.get('scorer_crash'):
    raise SystemExit(2)
rows = [r for path in a.input for r in json.loads(Path(path).read_text())]
reports = [json.loads(Path(path).read_text()) for path in a.generation_report]
planned = sum(r['planned'] for r in reports)
complete = planned == len(rows) and all(r['process_returncode'] == 0 for r in reports)
out = Path(a.output_dir)
out.mkdir(parents=True)
(out / 'scores.json').write_text(json.dumps({'status': 'complete' if complete else 'incomplete', 'summary': {'planned': planned, 'completed': len(rows)}}))
(out / 'scoring-report.md').write_text('report')
(out / 'scoring-failures.md').write_text('failures')
for scene in ('weather', 'home_switch'):
    (out / scene).mkdir()
    (out / scene / 'scores.json').write_text('{}')
    (out / scene / 'scoring-failures.md').write_text(scene)
raise SystemExit(0 if complete else 1)
"""


class BackendEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 使用现有 120 条种子与 556 条训练样本做真实版本校验，仍不调用模型。
        cls.inputs = entry.checked_inputs(
            ROOT / "config.json",
            ROOT / "data/prepared",
            ROOT / "data/evaluation-seeds/v3",
        )

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="backend with spaces ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.server = self.root / "server with spaces"
        client = self.server / "text-client"
        client.mkdir(parents=True)
        (client / "generate_conversations.py").write_text(GENERATOR)
        (client / "score_results.py").write_text(SCORER)
        self.config = self.root / "eval config.json"
        self.config.write_text("{}")
        self.result = self.root / "results with spaces"

    def run_entry(self, run_id="test"):
        with patch.object(
            entry, "checked_inputs", return_value=copy.deepcopy(self.inputs)
        ), redirect_stdout(io.StringIO()):
            return entry.main(
                [
                    "--server-dir",
                    str(self.server),
                    "--server-python",
                    sys.executable,
                    "--eval-config",
                    str(self.config),
                    "--run-id",
                    run_id,
                    "--results-dir",
                    str(self.result),
                ]
            )

    def test_success_and_report_copy_with_space_paths(self):
        self.assertEqual(self.run_entry(), 0)
        report = entry.read_json(self.result / "test/run.json")
        self.assertEqual(report["summary"], {"planned": 120, "completed": 120})
        self.assertEqual(report["environment"], "model_eval")
        self.assertEqual(report["backend_python"], str(Path(sys.executable).absolute()))
        self.assertTrue(
            (self.result / "test/home_switch/scoring-failures.md").is_file()
        )
        self.assertFalse(list(self.result.rglob("conversations.json")))
        batch = Path(report["backend_directory"])
        for name in ("system-prompt.txt", "tools.json"):
            self.assertEqual(
                (batch / "inputs" / name).read_bytes(),
                (ROOT / "data/prepared" / name).read_bytes(),
            )
        self.assertEqual(
            (self.result / "test/scores.json").read_bytes(),
            (batch / "scoring/scores.json").read_bytes(),
        )

    def test_partial_generation_still_scores_other_scene(self):
        self.config.write_text(json.dumps({"partial": "weather"}))
        self.assertEqual(self.run_entry(), 1)
        report = entry.read_json(self.result / "test/run.json")
        self.assertEqual(report["summary"], {"planned": 120, "completed": 61})
        self.assertEqual(report["generation"]["home_switch"]["process_returncode"], 0)

    def test_generation_crash_and_total_crash_return_report(self):
        self.config.write_text(json.dumps({"crash": "weather"}))
        self.assertEqual(self.run_entry(), 1)
        report = entry.read_json(self.result / "test/run.json")
        self.assertEqual(report["summary"]["completed"], 60)
        self.config.write_text(json.dumps({"scorer_crash": True}))
        self.assertEqual(self.run_entry("scorer-fails"), 1)
        self.assertIn(
            "未完成", (self.result / "scorer-fails/scoring-report.md").read_text()
        )

    def test_existing_batch_is_not_overwritten(self):
        self.run_entry()
        path = self.result / "test/run.json"
        original = path.read_bytes()
        with self.assertRaises(SystemExit):
            self.run_entry()
        self.assertEqual(path.read_bytes(), original)

    def test_changed_seed_is_rejected_before_creating_batch(self):
        import shutil

        seeds = self.root / "seeds"
        shutil.copytree(ROOT / "data/evaluation-seeds/v3", seeds)
        (seeds / "weather-seeds.json").write_text("[]")
        with self.assertRaisesRegex(ValueError, "校验失败"):
            entry.checked_inputs(ROOT / "config.json", ROOT / "data/prepared", seeds)
        self.assertFalse((self.server / "tmp").exists())

    def test_invalid_batch_id_rejected(self):
        with self.assertRaises(SystemExit):
            self.run_entry("../overwrite")


if __name__ == "__main__":
    unittest.main()
