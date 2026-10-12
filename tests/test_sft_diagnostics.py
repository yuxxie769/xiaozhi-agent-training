"""离线验证开发任务隔离、评分汇总与调用入口；不访问模型或真实设备。"""
import copy
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_sft_demonstrations as audit
import prepare_sft_diagnostics as prepare
import run_sft_diagnostics as runner
from generate_evaluation_seeds import read_json, write_json, semantic_fingerprint, sha256_file, home_generator, Library


class DiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.development = ROOT / 'data/sft-readiness/v1/development'
        cls.tasks, cls.binding = runner.check_development(ROOT, cls.development)

    def test_argument_adapter_does_not_mutate_training_or_source(self):
        messages = [{'role': 'assistant', 'tool_calls': [{'function': {'name': 'get_weather', 'arguments': {'location': '北京'}}}]}]
        before = copy.deepcopy(messages)
        original = {'seed': {'template_id': 'S01'}, 'messages': []}
        row = audit.scoring_conversation(original, messages)
        self.assertEqual(messages, before)
        self.assertEqual(original['messages'], [])
        self.assertEqual(row['messages'][0]['tool_calls'][0]['function']['arguments'], '{"location": "北京"}')

    def test_forty_distinct_tasks_with_four_slots(self):
        plan = read_json(self.development / 'run-plan.json')
        self.assertEqual(len(self.tasks), 40)
        self.assertEqual(len(plan['attempts']), 160)
        self.assertEqual(len({(r['repeat'], r['scenario'], r['sample_id']) for r in plan['attempts']}), 160)
        self.assertEqual(plan['executed_trajectories'], 0)

    def test_excludes_all_sources_and_old_tests(self):
        for scene, count in [('weather', 16), ('home_switch', 24)]:
            rows = read_json(self.development / f'{scene}-seeds.json')
            excluded = [r['seed'] for r in read_json(ROOT / f'data/raw/{scene}/conversations.json')]
            for path in (ROOT / 'data/evaluation-seeds').glob(f'*/{scene}-seeds.json'):
                excluded += read_json(path)
            fingerprints = [semantic_fingerprint(r) for r in rows]
            self.assertEqual(len(rows), count)
            self.assertEqual(len(set(fingerprints)), count)
            self.assertFalse(set(fingerprints) & {semantic_fingerprint(r) for r in excluded})

    def test_reproduce_seeds_from_recorded_exclusions(self):
        report = read_json(self.development / 'generation-report.json')
        for scene, info in report['scenarios'].items():
            source = ROOT / f'data/raw/{scene}/conversations.json'
            excluded = [r['seed'] for r in read_json(source)]
            for saved in info['excluded_files']:
                excluded.extend(read_json(ROOT / saved['path']))
            groups, _ = prepare.generate_scenario(scene, prepare.QUOTAS[scene], excluded,
                source, report['random_seed'], 100)
            self.assertEqual(prepare.choose_tasks(groups, excluded),
                             read_json(self.development / f'{scene}-seeds.json'))

    def test_full_tools_and_prompt_preserved(self):
        self.assertEqual(len(read_json(self.development / 'tools.json')), 9)
        for name in ('tools.json', 'system-prompt.txt'):
            self.assertEqual(sha256_file(self.development / name), sha256_file(ROOT / 'data/prepared' / name))

    def test_presets_and_seed_validation(self):
        library = Library(ROOT / 'data/raw/home_switch/conversations.json')
        presets = read_json(self.development / 'preset-snapshots.json')
        for row in read_json(self.development / 'home_switch-seeds.json'):
            self.assertEqual(library.resolve(row['preset']), presets[row['preset']])
            home_generator.validate_seed(row, library)

    def test_duplicate_directory_rejected_without_change(self):
        before = sha256_file(self.development / 'generation-report.json')
        with self.assertRaises(ValueError):
            prepare.prepare(ROOT, self.development)
        self.assertEqual(sha256_file(self.development / 'generation-report.json'), before)

    def test_tamper_rejected(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'dev'
            shutil.copytree(self.development, path)
            (path / 'tools.json').write_text('[]')
            with self.assertRaises(ValueError):
                runner.check_development(ROOT, path)

    def sample_reports(self, statuses):
        task = self.tasks[0]
        return [None if status is None else {'samples': [{**task, 'status': status}]} for status in statuses]

    def test_four_categories(self):
        for statuses, category in [(['pass']*4, 'all_pass'), (['fail']*4, 'all_fail'),
                                  (['pass','fail','pass','fail'], 'mixed'),
                                  (['fail','fail','fail',None], 'incomplete')]:
            result = runner.summarize(self.tasks[:1], self.sample_reports(statuses))
            self.assertEqual(result['tasks'][0]['category'], category)

    def test_runtime_error_not_model_failure(self):
        result = runner.summarize(self.tasks[:1], self.sample_reports(['error',None,None,None]))
        self.assertEqual(result['completed'], 0)
        self.assertEqual(result['unscored'], 4)
        self.assertNotIn('all_fail', result['categories'])

    def test_incomplete_check_not_model_failure(self):
        reports = self.sample_reports(['fail']*4)
        reports[0]['samples'][0]['checks'] = [{'status': 'error'}]
        result = runner.summarize(self.tasks[:1], reports)
        self.assertEqual(result['completed'], 3)
        self.assertEqual(result['tasks'][0]['category'], 'incomplete')

    def test_unknown_and_duplicate_score_rejected(self):
        for duplicate in (False, True):
            reports = self.sample_reports(['pass']*4)
            if duplicate:
                reports[0]['samples'] *= 2
            else:
                reports[0]['samples'][0]['sample_id'] = 'unknown'
            with self.assertRaises(ValueError):
                runner.summarize(self.tasks[:1], reports)

    def test_default_never_calls_backend(self):
        with patch.object(runner.backend, 'run') as run, redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main([]), 0)
            run.assert_not_called()

    def run_fake(self, partial=False):
        with tempfile.TemporaryDirectory(prefix='diagnostic with spaces ') as tmp:
            base = Path(tmp)
            server = base / 'server with spaces'
            client = server / 'text-client'
            client.mkdir(parents=True)
            for name in ('generate_conversations.py', 'score_results.py'):
                (client / name).write_text('# test double')
            config = base / 'eval config.json'
            config.write_text('{}')
            args = SimpleNamespace(project=ROOT, development_dir=self.development, results_dir=base / 'results',
                execute=True, server_dir=server, server_python=Path(sys.executable), eval_config=config,
                run_id='test', model_version='test-only')
            def fake_backend(child):
                self.assertEqual(child.seeds_dir, self.development)
                self.assertEqual(child.stage, 'sft')
                out = child.results_dir / child.run_id
                out.mkdir(parents=True)
                rows = [{**t, 'status': 'pass'} for t in self.tasks]
                write_json(out / 'scores.json', {'samples': rows[:-1] if partial else rows})
                return 1 if partial else 0
            with patch.object(runner.backend, 'run', side_effect=fake_backend) as called:
                code = runner.execute(args)
                self.assertEqual(called.call_count, 1 if partial else 4)
                self.assertEqual(code, 1 if partial else 0)
            summary = read_json(args.results_dir / 'test/summary.json')
            self.assertEqual(summary['completed'], 39 if partial else 160)
            if partial:
                self.assertNotIn('all_fail', summary['categories'])
            with self.assertRaises(ValueError):
                runner.execute(args)

    def test_four_repeats_reuse_backend_and_protect_old_results(self):
        self.run_fake()

    def test_partial_failure_stops_and_returns_valid_scores(self):
        self.run_fake(partial=True)


if __name__ == '__main__':
    unittest.main()
