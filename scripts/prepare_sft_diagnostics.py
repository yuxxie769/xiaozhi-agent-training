"""离线准备 40 个开发任务；复用原生成器，不调用模型或工具服务。"""
from __future__ import annotations

import argparse
import copy
from collections import Counter
from pathlib import Path
import shutil

from generate_evaluation_seeds import (
    Library, extract_seed_rows, generate_scenario, group_seeds,
    load_prepared_inputs, read_json, semantic_fingerprint, sha256_file,
    wording_fingerprints, write_json,
)

ROOT = Path(__file__).resolve().parents[1]
REPEATS = 4
# 每个变量组仅选一种表达，避免把三种同义问法误算成三个独立任务。
QUOTAS = {
    'weather': {'S05': 2, 'S06': 1, 'S11': 2, 'S12': 1, 'S15': 2,
                'S19': 2, 'S20': 1, 'S21': 2, 'S22': 2, 'S24': 1},
    'home_switch': {'T03': 1, 'T04': 2, 'T05': 1, 'T06': 3, 'T07': 2,
                    'T08': 2, 'T10': 2, 'T11': 2, 'T12': 2, 'T14': 2,
                    'T17': 2, 'T19': 2, 'T20': 1},
}


def exclusions(project, scene, source_rows):
    """包括未通过源数据和所有历史测试版本；只读，不修改正式测试题。"""
    rows = extract_seed_rows(source_rows)
    files = sorted((project / 'data/evaluation-seeds').glob(f'*/{scene}-seeds.json'))
    files += sorted((project / 'data/sft-readiness').glob(f'*/development/{scene}-seeds.json'))
    records = []
    for path in files:
        values = extract_seed_rows(read_json(path))
        rows.extend(values)
        records.append({'path': str(path.relative_to(project)),
                        'sha256': sha256_file(path), 'seeds': len(values)})
    return rows, records


def choose_tasks(groups, excluded):
    """轮换表达版本；同组有新文案时优先选新文案，不靠改 ID 绕过排重。"""
    old_wording = {fp for row in excluded for fp in wording_fingerprints(row)}
    used_wording = set()
    selected = []
    for index, ((template, _), rows) in enumerate(sorted(group_seeds(groups).items())):
        order = sorted(rows, key=lambda r: (int(r['question_pattern_id'][1:]) - 1 - index) % 3)
        candidates = [r for r in order if not wording_fingerprints(r) & (old_wording | used_wording)]
        row = copy.deepcopy((candidates or order)[0])
        row['variable_group_id'] = f'{template}-D{index + 1:03d}'
        row['seed_id'] = f"{row['variable_group_id']}-{row['question_pattern_id']}"
        selected.append(row)
        used_wording.update(wording_fingerprints(row))
    return selected


def prepare(project, output, random_seed=20261012):
    if output.exists():
        raise ValueError('开发任务目录已存在，请使用新版本，不覆盖旧任务')
    sources, binding = load_prepared_inputs(project / 'config.json', project / 'data/prepared')
    report = {'schema_version': 2, 'purpose': 'development_diagnostics_not_final_test',
              'status': 'offline_ready_not_executed', 'prepared_data': binding,
              'random_seed': random_seed, 'repeats': REPEATS,
              'generator_sha256': sha256_file(Path(__file__)), 'scenarios': {},
              'quota_note': 'T20 排除源数据与历史测试后，尝试 500 轮只找到 1 个新组合；将另 1 题配额转给 T06，多轮动作切换共 3 题。未放宽排重。'}
    all_seeds, tasks = {}, []
    for scene, quotas in QUOTAS.items():
        excluded, files = exclusions(project, scene, sources[scene]['conversations'])
        groups, stats = generate_scenario(scene, quotas, excluded,
            sources[scene]['conversations_path'], random_seed, 100)
        seeds = choose_tasks(groups, excluded)
        fingerprints = [semantic_fingerprint(row) for row in seeds]
        if len(fingerprints) != len(set(fingerprints)) or set(fingerprints) & {semantic_fingerprint(r) for r in excluded}:
            raise ValueError(f'{scene} 排重检查失败')
        old_wording = {fp for r in excluded for fp in wording_fingerprints(r)}
        overlaps = [r['seed_id'] for r in seeds if wording_fingerprints(r) & old_wording]
        all_seeds[scene] = seeds
        report['scenarios'][scene] = {
            'generated_seeds': len(seeds), 'template_counts': dict(Counter(r['template_id'] for r in seeds)),
            'source_conversations_sha256': sha256_file(sources[scene]['conversations_path']),
            'excluded_seed_rows': len(excluded), 'excluded_files': files,
            'wording_overlap_ids': overlaps, **stats,
        }
        tasks.extend({'scenario': scene, 'sample_id': r['seed_id'], 'template_id': r['template_id'],
                      'variant_id': r.get('variant_id', 'basic'), 'user_turns': r['user_turns'],
                      'semantic_sha256': semantic_fingerprint(r)} for r in seeds)
    library = Library(sources['home_switch']['conversations_path'])
    presets = {name: library.resolve(name) for name in sorted({r['preset'] for r in all_seeds['home_switch']})}
    # 全部检查完成后才创建目录；工具和提示词直接复制当前训练版本。
    output.mkdir(parents=True)
    for name in ('system-prompt.txt', 'tools.json'):
        shutil.copyfile(project / 'data/prepared' / name, output / name)
    write_json(output / 'preset-snapshots.json', presets)
    for scene, rows in all_seeds.items():
        path = output / f'{scene}-seeds.json'
        write_json(path, rows)
        report['scenarios'][scene]['output_sha256'] = sha256_file(path)
    write_json(output / 'tasks.json', tasks)
    write_json(output / 'run-plan.json', {
        'status': 'not_executed', 'tasks': len(tasks), 'repeats': REPEATS,
        'planned_trajectories': len(tasks) * REPEATS, 'executed_trajectories': 0,
        'attempts': [{'repeat': repeat, 'scenario': t['scenario'], 'sample_id': t['sample_id']}
                     for repeat in range(1, REPEATS + 1) for t in tasks],
    })
    report['artifact_sha256'] = {p.name: sha256_file(p) for p in sorted(output.iterdir()) if p.is_file()}
    report['limitations'] = [
        '排重依据既有语义字段指纹，不代表模板未见过或自然语言绝对独立。',
        '这是用于改进模型的开发集，不能继续当作独立最终测试集。',
        '天气沿用在线返回；重复结果也可能受工具数据变化影响。',
        '尚未请求模型，没有通过率，也没有生成 DPO 配对。',
    ]
    write_json(output / 'generation-report.json', report)
    lines = ['# 开发任务已准备', '', '40 个任务：天气 16、家居 24。每题重复 4 次，共计划 160 条轨迹；当前未执行。', '',
             '复用原场景生成器及评分规则。每个变量组只选一种表达，重点检查多轮更正、澄清、控制回读、错误处理和日期依据。', '',
             '已排除全部 599 条源轨迹和历史测试、开发版本中的相同语义字段组合。工具、提示词和设备快照已固定。', '']
    for scene, info in report['scenarios'].items():
        lines.append(f"- {scene}：{info['generated_seeds']} 题；语义字段组合重合 0；与历史文案完全重合 {len(info['wording_overlap_ids'])} 题（任务变量不同）。")
    lines += ['', *report['limitations'], '', '运行入口见上级 README.md。']
    (output / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=ROOT)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--random-seed', type=int, default=20261012)
    args = parser.parse_args()
    report = prepare(args.project.resolve(), args.output_dir.resolve(), args.random_seed)
    print({s: r['generated_seeds'] for s, r in report['scenarios'].items()})


if __name__ == '__main__':
    main()
