"""Audit the actual exported SFT rows without a model or a new semantic judge.

Checks all source bindings and reruns existing deterministic scoring rules.
Old LLM judgments are reported as historical evidence, never as a fresh rescore.
Produces traceable examples for human semantic review and a targeted coverage summary.
"""
from __future__ import annotations
import argparse
import copy
import importlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluation'))
from generate_evaluation_seeds import load_prepared_inputs, read_json, read_jsonl, sha256_file
from prepare_training_data import validate_score

TOPICS = {
    'home_reference': ('home_switch', ['T03','T04','T05','T06','T11','T15'], '多轮指代、改口和列表选择'),
    'home_clarify': ('home_switch', ['T07','T08','T10','T11','T14'], '缺少设备或动作时澄清'),
    'home_control': ('home_switch', ['T01','T03','T04','T06','T12','T15'], '按需控制、回读和停止'),
    'home_cancel_error': ('home_switch', ['T17','T18','T19','T20'], '取消、状态不可用和控制错误'),
    'weather_dates': ('weather', ['S02','S06','S19','S20','S21','S22'], '日期对应及多轮城市、日期切换'),
    'weather_context': ('weather', ['S05','S11','S12','S15','S24'], '组合请求、澄清、更正和取消'),
}

def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')

def scoring_conversation(original, messages):
    """只转换评分副本的参数格式，避免改动训练正文或源轨迹。"""
    row = copy.deepcopy(original)
    row['messages'] = copy.deepcopy(messages)
    for message in row['messages']:
        for call in message.get('tool_calls', []):
            if isinstance(call['function']['arguments'], dict):
                call['function']['arguments'] = json.dumps(call['function']['arguments'], ensure_ascii=False)
    return row

def audit(project, output):
    sources, binding = load_prepared_inputs(project/'config.json', project/'data/prepared')
    meta = read_jsonl(project/'data/prepared/metadata.jsonl')
    train = read_jsonl(project/'data/prepared/train.jsonl')
    source_maps = {sc: {x['sample_id']:x for x in data['conversations']} for sc,data in sources.items()}
    scores = {sc: {x['sample_id']:x for x in read_json(project/data['source']['scores'])['samples']} for sc,data in sources.items()}
    adapters = {sc: importlib.import_module(sc+'_scoring') for sc in sources}
    records, examples = [], []
    for item in meta:
        sc, sid = item['scenario'], item['source_sample_id']
        original = source_maps[sc][sid]
        historical = scores[sc][sid]
        # This verifies existing evidence against source messages; it does not ask a judge.
        validate_score(original, historical, sc)
        row = scoring_conversation(original, train[item['row_index']]['messages'])
        state = adapters[sc].analyze(row)
        checks, _, _ = adapters[sc].plan_checks(row, state)
        deterministic = []
        for check in checks.values():
            if check['method'] not in ('rule','program'):
                continue
            turn = state['turns'][check['turn']-1]
            status, reason, proof = adapters[sc].rule_check(
                check['check_id'], turn, adapters[sc].expectation(row['seed'],turn,state),state)
            deterministic.append({'turn':check['turn'],'check_id':check['check_id'],
                'status':status,'reason':reason,'evidence':proof})
        tools = Counter(c['function']['name'] for m in row['messages'] for c in m.get('tool_calls',[]))
        records.append({'id':item['id'],'scenario':sc,'sample_id':sid,'row_index':item['row_index'],
            'template_id':row['seed']['template_id'],'variant_id':row['seed'].get('variant_id','basic'),
            'variable_group_id':row['seed']['variable_group_id'],
            'user_turns':row['seed']['user_turns'],'turns':len(row['seed']['user_turns']),
            'historical_score_status':historical['status'],
            'historical_semantic_checks':[{k:c.get(k) for k in ('turn','check_id','status','reason','evidence')}
                for c in historical['checks'] if c['method']=='llm'],
            'deterministic_checks':deterministic,'tool_counts':dict(tools),
            'prepared_row_sha256':item['normalized_sha256']})
    topics = {}
    for name,(sc,templates,title) in TOPICS.items():
        matching=[r for r in records if r['scenario']==sc and r['template_id'] in templates]
        topics[name]={'name':title,'samples':len(matching),
            'semantic_groups':len({(r['template_id'],r['variable_group_id']) for r in matching}),
            'distinct_user_dialogues':len({tuple(r['user_turns']) for r in matching}),
            'templates':dict(Counter(r['template_id'] for r in matching)),
            'variants':dict(Counter(r['variant_id'] for r in matching)),
            'deterministic_failures':sum(any(c['status']=='fail' for c in r['deterministic_checks']) for r in matching)}
    # A fixed, inspectable sample across failure-relevant templates (not just the shortest rows).
    review_templates={'home_switch':['T01','T04','T05','T06','T07','T08','T10','T11','T12','T14','T17','T19','T20'],
                      'weather':['S02','S05','S06','S11','S12','S15','S19','S20','S21','S22','S24']}
    for sc,templates in review_templates.items():
        for template in templates:
            matches=[r for r in records if r['scenario']==sc and r['template_id']==template]
            # Prefer P2 when available; choose centrally by ID rather than cherry-picking by quality.
            matches.sort(key=lambda r:r['sample_id'])
            candidates=[r for r in matches if r['sample_id'].endswith('P2')] or matches
            chosen=candidates[len(candidates)//2]
            original=source_maps[sc][chosen['sample_id']]
            examples.append({'id':chosen['id'],'row_index':chosen['row_index'], 'template_id':template,
                'scenario':sc,'seed':original['seed'],'context':original['context'],
                'messages':train[chosen['row_index']]['messages'],
                'deterministic_checks':chosen['deterministic_checks'],
                'historical_semantic_checks':chosen['historical_semantic_checks']})
    if output.exists():raise ValueError('Use a new output directory; audit artifacts are immutable')
    output.mkdir(parents=True)
    (output/'samples.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records))
    write_json(output/'review-examples.json',examples)
    summary={'status':'programmatic_audit_complete_semantic_review_pending','prepared_binding':binding,
        'total':len(records),'scenarios':dict(Counter(r['scenario'] for r in records)),
        'checks_rerun':sum(len(r['deterministic_checks']) for r in records),
        'deterministic_failed_samples':[r['id'] for r in records if any(c['status']=='fail' for c in r['deterministic_checks'])],
        'scoring_format_adapter':'Argument objects serialized to JSON strings in memory only; train.jsonl unchanged',
        'historical_scores_reused_not_rescored':len(records),'topics':topics,
        'manual_review_selected':len(examples),
        'scorer_sha256':{sc:sha256_file(Path(adapters[sc].__file__)) for sc in adapters},
        'limits':['Historical semantic pass labels are not new semantic verification.',
                  'Coverage counts overlap across topics and do not prove capability.',
                  'This audits local prepared data, not unprovided GPU training logs or checkpoint lineage.']}
    write_json(output/'audit.json',summary)
    print(json.dumps({k:summary[k] for k in ('total','scenarios','checks_rerun','deterministic_failed_samples','manual_review_selected')},ensure_ascii=False))
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,default=ROOT)
    p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args();audit(args.project.resolve(),args.output_dir.resolve())
