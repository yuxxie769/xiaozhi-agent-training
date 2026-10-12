"""合并三条正文修订与验收后的补充示范，调用现有离线导出器。

旧原始文件和旧训练集始终只读。没有全量重评：其余原评分逐条沿用，
新版评分只来自问题样本和本次新增任务，每条评分保留来源校验值。
"""
from __future__ import annotations
import argparse
import copy
import importlib
import json
import os
from pathlib import Path
import sys

from prepare_training_data import prepare, digest, file_hash, indexed, read_json


def save_once(path, value):
    """允许完全相同的离线重现，不覆盖不同内容的历史文件。"""
    content=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
    if path.exists() and path.read_text(encoding='utf-8')!=content:
        raise ValueError('已有文件内容不同：'+str(path))
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(content,encoding='utf-8')


def build(project, run, output):
    repair=project/'data/sft-repair/v1'
    for name,checksum in read_json(repair/'original-files.json').items():
        if file_hash(project/name)!=checksum:
            raise ValueError('原数据被修改：'+name)
    run_results=read_json(run/'execution.json')
    if len(run_results)!=4 or len({r['shard'] for r in run_results})!=4:
        raise ValueError('补数分片执行记录不完整')
    reviews=read_json(repair/'supplements/evidence-reviews.json')
    edits=read_json(repair/'targeted/edits.json')
    if {e['sample_id'] for e in edits}!={'T14-G004-P2','S11-G03-P2','S15-G03-P2'}:
        raise ValueError('只允许已确认的三条原文修订')
    config=read_json(project/'config.json')
    # Keep config paths relative so the independent project can move to a training server.
    derived = repair/'derived'
    for key in ('system_prompt','target_tools','target_tools_provenance','weather_tool_source'):
        if key in config:config[key]=os.path.relpath(project/config[key], derived)
    config['evidence_reviews']='../supplements/evidence-reviews.json'
    config['sources']=[]
    provenance=[];generation_errors=[];new_ids=set()
    merged={}
    for scene in ('weather','home_switch'):
        raw=project/f'data/raw/{scene}/conversations.json'
        scores=project/f'data/raw/{scene}/scores.current.json'
        rows=read_json(raw);originals=indexed(rows)
        old_report=read_json(scores);by_id=indexed(old_report['samples'])
        corrected=indexed(read_json(repair/'targeted/inputs'/f'{scene}-corrected.json'))
        corrected_path=repair/'targeted'/f'{scene}-corrected-scores/scores.json'
        corrected_report=read_json(corrected_path)
        correction_scores=indexed(corrected_report['samples'])
        if corrected_report.get('errors') or set(corrected)!=set(correction_scores):
            raise ValueError('修正版评分不完整')
        for edit in (e for e in edits if e['scenario']==scene):
            key=edit['sample_id'];expected=copy.deepcopy(originals[key])
            index=edit['message_index']
            if expected['messages'][index]['content']!=edit['original']:
                raise ValueError('原文不匹配')
            expected['messages'][index]['content']=edit['replacement']
            if expected!=corrected[key] or correction_scores[key]['status']!='pass':
                raise ValueError('修订超出正文范围或未通过')
        for index,row in enumerate(rows):
            key=row['sample_id'];changed=key in corrected
            if changed:
                rows[index]=corrected[key];by_id[key]=correction_scores[key]
            origin=corrected_path if changed else scores
            provenance.append({'id':scene+':'+key,'kind':'corrected_rescored' if changed else 'historical_reused',
                               'scores':str(origin),'scores_sha256':file_hash(origin)})
        errors=[]
        for result in run_results:
            if result['scenario']!=scene:continue
            shard=run/result['shard'];g=read_json(shard/'generation/generation-report.json')
            generated=read_json(shard/'generation/conversations.json')
            if len(generated)!=g['saved'] or g['started']!=g['planned']:
                raise ValueError('生成数量不一致')
            generation_errors.extend(dict(e,scenario=scene,shard=result['shard']) for e in g['errors'])
            score_path=shard/'scoring/scores.json';report=read_json(score_path)
            if report.get('status')=='error':raise ValueError('分片评分入口未完成')
            current=indexed(report['samples']);errors+=report['errors']
            generated_ids={row['sample_id'] for row in generated}
            error_ids={row['sample_id'] for row in report['errors']}
            if set(current) & error_ids or set(current) | error_ids != generated_ids:
                raise ValueError('评分与错误记录无法对应生成样本')
            for row in generated:
                key=row['sample_id'];namespaced=scene+':'+key
                if key in originals or namespaced in new_ids:raise ValueError('新增样本ID冲突')
                if namespaced not in reviews or reviews[namespaced]['source_sample_sha256']!=digest(row):
                    raise ValueError('新增样本尚未完成对应证据核对')
                new_ids.add(namespaced);rows.append(row)
                if key in current:by_id[key]=current[key]
                provenance.append({'id':namespaced,'kind':'new_scored' if key in current else 'new_scoring_error',
                                   'scores':str(score_path),'scores_sha256':file_hash(score_path)})
        adapter=importlib.import_module(scene+'_scoring')
        report={'schema_version':2,'rubric_version':'mixed_historical_and_revised_factuality',
                'judge':{'source':'per_sample_provenance','note':'历史未重评项与本次评分分别记录，不代表全量采用新版判分'},
                'samples':list(by_id.values()),'errors':errors,
                'summary':adapter.aggregate_report(list(by_id.values()),errors,len(rows)),
                'score_provenance_note':'详见同目录 score-provenance.json；历史评分逐条保持原样。'}
        merged[scene]=(rows,report)
    if len(new_ids)+len(generation_errors)!=80:
        raise ValueError('80 次生成尝试无法对账')
    if set(reviews)!=new_ids:raise ValueError('证据复核记录与新增轨迹不一一对应')
    derived=repair/'derived'
    for scene,(rows,report) in merged.items():
        source=derived/f'{scene}-conversations.json';score=derived/f'{scene}-scores.json'
        save_once(source,rows)
        report['revision']={'conversations_sha256':file_hash(source),'kind':'curated_merge_not_full_rejudging'}
        save_once(score,report)
        config['sources'].append({'scenario':scene,'conversations':source.name,'scores':score.name,
            'score_policy':'仅三条问题样本修正版和新增样本采用本轮评分；其余历史评分沿用，未全量重评。'})
    save_once(derived/'score-provenance.json',provenance)
    save_once(derived/'generation-errors.json',generation_errors)
    save_once(derived/'config.json',config)
    summary=prepare(derived/'config.json',output)
    audit=[json.loads(line) for line in (output/'audit.jsonl').read_text().splitlines()]
    old_meta=[json.loads(line) for line in (project/'data/prepared/metadata.jsonl').read_text().splitlines()]
    old_ids={row['id'] for row in old_meta};now={row['id'] for row in audit if row['disposition']=='passed_sample'}
    new_kept=now & new_ids
    counts={'original_training':556,'original_unchanged_kept':len((now & old_ids)-{e['scenario']+':'+e['sample_id'] for e in edits}),
            'original_revised_kept':len(now & {e['scenario']+':'+e['sample_id'] for e in edits}),'original_removed':sorted(old_ids-now),
            'new_planned':80,'new_generated':len(new_ids),'new_generation_errors':len(generation_errors),
            'new_training':len(new_kept),'total_training':summary['train_samples'],
            'failed':summary['failed_samples'],'review':summary['quarantine'],'duplicates':summary['duplicates'],
            'new_dispositions':{kind:sum(row['id'] in new_ids and row['disposition']==kind for row in audit)
                                 for kind in ('passed_sample','failed_sample','quarantine','duplicate')}}
    save_once(derived/'reconciliation.json',counts)
    print(json.dumps(counts,ensure_ascii=False))
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    build(args.project.resolve(),args.run_dir.resolve(),args.output_dir.resolve())


if __name__=='__main__':main()
