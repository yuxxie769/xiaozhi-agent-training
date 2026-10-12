"""固定开发任务各跑四遍，复用原后端入口；默认只检查，--execute 才请求模型。

不重试到通过、不把缺失评分当成模型答错。每次执行使用新批次目录，保留所有尝试。
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re
from types import SimpleNamespace

import run_backend_evaluation as backend
from generate_evaluation_seeds import read_json, sha256_file, write_json

ROOT = Path(__file__).resolve().parents[1]
REPEATS = 4


def check_development(project, development):
    report = read_json(development / 'generation-report.json')
    if report['purpose'] != 'development_diagnostics_not_final_test' or report['repeats'] != REPEATS:
        raise ValueError('不是四次重复诊断的开发任务版本')
    for name, expected in report['artifact_sha256'].items():
        if Path(name).name != name or sha256_file(development / name) != expected:
            raise ValueError(f'开发任务文件校验失败：{name}')
    seeds, presets, binding = backend.checked_inputs(project / 'config.json', project / 'data/prepared', development)
    # 后端入口复制当前 prepared 内容；先与开发快照核对，防止无声替换输入。
    for name in ('system-prompt.txt', 'tools.json'):
        if sha256_file(development / name) != sha256_file(project / 'data/prepared' / name):
            raise ValueError(f'开发任务与当前训练版本不一致：{name}')
    if presets != read_json(development / 'preset-snapshots.json'):
        raise ValueError('设备快照不一致')
    tasks = read_json(development / 'tasks.json')
    expected = {(s, r['seed_id']) for s, rows in seeds.items() for r in rows}
    actual = [(t['scenario'], t['sample_id']) for t in tasks]
    if len(actual) != 40 or len(set(actual)) != 40 or set(actual) != expected:
        raise ValueError('任务清单与 40 条种子不一致')
    return tasks, binding


def summarize(tasks, reports):
    """reports 按第 1～4 次排列；None 表示该次未产生可用评分。"""
    if len(reports) != REPEATS:
        raise ValueError('必须提供四个尝试位置，未完成的位置使用 None')
    known = {(t['scenario'], t['sample_id']) for t in tasks}
    attempts = {key: [] for key in known}
    for report in reports:
        indexed = {}
        for row in (report or {}).get('samples', []):
            key = (row.get('scenario'), row.get('sample_id'))
            if key not in known or key in indexed:
                raise ValueError(f'评分样本未知或重复：{key}')
            indexed[key] = row
        for key in known:
            row = indexed.get(key)
            status = (row or {}).get('status')
            checks = (row or {}).get('checks', [])
            # 一旦含未完成检查，整条不得进入通过/失败分母。
            invalid = any(c.get('status') not in ('pass', 'fail', 'skip') for c in checks)
            attempts[key].append(status if status in ('pass', 'fail') and not invalid else 'unscored')
    results = []
    for task in tasks:
        statuses = attempts[(task['scenario'], task['sample_id'])]
        passed, completed = statuses.count('pass'), REPEATS - statuses.count('unscored')
        category = 'incomplete' if completed < REPEATS else ('all_fail' if passed == 0 else 'all_pass' if passed == REPEATS else 'mixed')
        results.append({**task, 'attempt_statuses': statuses, 'completed': completed,
                        'passed': passed, 'category': category})
    complete = sum(r['completed'] for r in results)
    return {'status': 'complete' if complete == len(tasks) * REPEATS else 'incomplete',
            'planned': len(tasks) * REPEATS, 'completed': complete,
            'unscored': len(tasks) * REPEATS - complete,
            'categories': dict(Counter(r['category'] for r in results)), 'tasks': results}


def render_summary(summary):
    counts = summary['categories']
    return ('# 四次重复诊断\n\n'
            f"已评分 {summary['completed']}/{summary['planned']} 条；未评分 {summary['unscored']} 条。\n\n"
            f"4 次全过：{counts.get('all_pass', 0)} 题；1～3 次通过：{counts.get('mixed', 0)} 题；"
            f"4 次全错：{counts.get('all_fail', 0)} 题；未完成：{counts.get('incomplete', 0)} 题。\n\n"
            '只对四次都完成评分的任务分类。运行失败或没有评分的任务不算 0/4。\n\n'
            '混合通过说明表现不稳定，可进一步检查是否适合构造偏好对；四次失败也不能证明模型完全不会。'
            'DPO 仍需同一输入下有可信正确答案和明确错误答案，并核查训练示范、工具返回和评分证据。'
            '天气是在线返回，结果差异未必只来自模型。\n')


def execute(args):
    tasks, binding = check_development(args.project, args.development_dir)
    if not args.execute:
        print(f'离线检查通过：{len(tasks)} 题 × {REPEATS} 次 = {len(tasks)*REPEATS} 条；未调用模型。')
        return 0
    if not all((args.server_dir, args.server_python, args.eval_config, args.run_id)):
        raise ValueError('--execute 需要后端目录、Python、eval-config 和新的 run-id')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', args.run_id):
        raise ValueError('run-id 格式无效')
    output = args.results_dir / args.run_id
    if output.exists() or any((args.server_dir / 'tmp/model-eval-runs' / f'{args.run_id}-r{i}').exists() for i in range(1, REPEATS+1)):
        raise ValueError('批次已存在，请换 run-id；不覆盖或重抽历史尝试')
    for path in (args.server_python, args.eval_config, args.server_dir / 'text-client/generate_conversations.py', args.server_dir / 'text-client/score_results.py'):
        if not path.is_file():
            raise ValueError(f'缺少文件：{path}')
    output.mkdir(parents=True)
    record = {'status': 'running', 'development_dir': str(args.development_dir),
              'development_manifest_sha256': sha256_file(args.development_dir / 'generation-report.json'),
              'prepared_data': binding, 'model_version_label': args.model_version,
              'model_version_note': '用户填写的部署标记；不是权重身份的自动证明',
              'repeat_runs': []}
    reports = [None] * REPEATS
    write_json(output / 'run.json', record)
    process_failed = False
    try:
        for i in range(REPEATS):
            child_id = f'{args.run_id}-r{i+1}'
            child = SimpleNamespace(server_dir=args.server_dir, server_python=args.server_python,
                eval_config=args.eval_config, run_id=child_id, stage='sft',
                config=args.project / 'config.json', prepared_dir=args.project / 'data/prepared',
                seeds_dir=args.development_dir, results_dir=output / 'repeats')
            code = backend.run(child)
            score_path = child.results_dir / child_id / 'scores.json'
            if score_path.exists():
                reports[i] = read_json(score_path)
            record['repeat_runs'].append({'repeat': i+1, 'run_id': child_id,
                'returncode': code, 'result_directory': str(child.results_dir / child_id)})
            write_json(output / 'run.json', record)
            if code:
                # 停止后仍保留并汇总本次已完成样本，避免服务故障时继续请求余下轮次。
                process_failed = True
                break
    finally:
        summary = summarize(tasks, reports)
        write_json(output / 'summary.json', summary)
        (output / 'report.md').write_text(render_summary(summary), encoding='utf-8')
        record['status'] = 'complete' if summary['status'] == 'complete' and not process_failed else 'incomplete'
        write_json(output / 'run.json', record)
    return 0 if record['status'] == 'complete' else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project', type=Path, default=ROOT)
    p.add_argument('--development-dir', type=Path, default=ROOT / 'data/sft-readiness/v1/development')
    p.add_argument('--results-dir', type=Path, default=ROOT / 'data/sft-readiness/v1/runs')
    p.add_argument('--server-dir', type=Path)
    p.add_argument('--server-python', type=Path)
    p.add_argument('--eval-config', type=Path)
    p.add_argument('--run-id')
    p.add_argument('--model-version', default='未提供部署版本')
    p.add_argument('--execute', action='store_true', help='实际调用模型及原工具环境；默认仅离线检查')
    args = p.parse_args(argv)
    for name in ('project', 'development_dir', 'results_dir', 'server_dir', 'eval_config'):
        if getattr(args, name) is not None:
            setattr(args, name, getattr(args, name).resolve())
    # 保留虚拟环境 Python 的符号链接，不能 resolve 成全局解释器。
    if args.server_python:
        args.server_python = args.server_python.absolute()
    try:
        return execute(args)
    except (OSError, ValueError, KeyError) as exc:
        p.exit(2, f'诊断入口检查失败：{exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
