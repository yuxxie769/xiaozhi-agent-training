"""准备明确有问题的现有训练样本的重评输入，复用后端选择性评分入口。

默认只准备本地输入和清单，不请求模型。--execute 才会发送对话给配置中的
评分模型；调用前必须确认接收方及外发范围。旧数据与旧评分始终保持不变。
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_gate(server, validation):
    gate = read(validation)
    if gate.get('status') != 'passed' or gate.get('matched') != gate.get('planned'):
        raise ValueError('评分器真实模型验收未通过')
    for name in ('weather_scoring.py','home_switch_scoring.py','eval_scoring.py','eval_judge.py'):
        if sha(server/'text-client'/name) != gate['code_sha256'][name]:
            raise ValueError('评分器已改变，必须重新验收：'+name)
    return gate


TARGET_IDS = {"weather": {"S11-G03-P2", "S15-G03-P2"}, "home_switch": {"T14-G004-P2"}}


def prepare(project, server, validation, output):
    """只取已确认的 3 个问题样本；其余样本沿用历史评分。"""
    gate = check_gate(server, validation)
    if output.exists():
        raise ValueError('输出目录已存在，禁止覆盖历史重评输入')
    manifest = read(project/'data/prepared/manifest.json')
    for name, checksum in manifest['artifact_sha256'].items():
        if sha(project/'data/prepared'/name) != checksum:
            raise ValueError('旧训练数据校验失败：'+name)
    meta = [json.loads(line) for line in (project/'data/prepared/metadata.jsonl').read_text().splitlines()]
    if len(meta) != 556 or len({m['id'] for m in meta}) != 556:
        raise ValueError('本轮必须且仅处理原 556 条训练样本')
    bundles = {}
    provenance = {}
    for entry in read(project/'config.json')['sources']:
        scene = entry['scenario']
        path, scores_path = project/entry['conversations'], project/entry['scores']
        previous = next(s for s in manifest['sources'] if s['scenario']==scene)
        if sha(path)!=previous['conversations_sha256'] or sha(scores_path)!=previous['scores_sha256']:
            raise ValueError('源数据与旧训练集绑定不一致')
        training_ids = {m['source_sample_id'] for m in meta if m['scenario']==scene}
        ids = TARGET_IDS[scene]
        if not ids <= training_ids:
            raise ValueError('问题样本不在原训练集中')
        rows = [row for row in read(path) if row['sample_id'] in ids]
        scores = read(scores_path)
        scores['samples'] = [row for row in scores['samples'] if row['sample_id'] in ids]
        if {r['sample_id'] for r in rows}!=ids or {r['sample_id'] for r in scores['samples']}!=ids:
            raise ValueError('样本与评分不完整')
        # This is an input subset of an existing score file, not a new score.
        # The old whole-file binding cannot describe the newly selected JSON.
        scores.pop('revision',None)
        scores['subset_provenance']={'source_scores':str(scores_path),'sha256':sha(scores_path),
                                     'note':'沿用旧检查项作为重评输入；原汇总属于完整来源批次。'}
        bundles[scene]=(rows,scores)
        provenance[scene]={'count':len(rows),'original_conversations_sha256':sha(path),
                           'original_scores_sha256':sha(scores_path)}
    if sum(len(rows) for rows,_ in bundles.values())!=3:
        raise ValueError('重评数量无法对账')
    output.mkdir(parents=True)
    for scene,(rows,scores) in bundles.items():
        write(output/'inputs'/f'{scene}-conversations.json',rows)
        write(output/'inputs'/f'{scene}-source-scores.json',scores)
    plan={'status':'prepared_not_sent','planned_samples':3,'sources':provenance,
          'validation_sha256':sha(validation),'judge_identity':gate['judge_identity'],
          'baseline_manifest_sha256':sha(project/'data/prepared/manifest.json'),
          'input_sha256':{p.name:sha(p) for p in sorted((output/'inputs').iterdir())},
          'historical_judge_note':'家居保留完整模型指纹；天气旧评分只记录 deepseek-flash 名称，不能证明旧请求参数完全一致。'}
    write(output/'input-manifest.json',plan)
    return plan


def execute(server, server_python, config, validation, output):
    """仅显式执行时调用后端；不自行实现模型加载、评分或规则。"""
    check_gate(server,validation)
    plan=read(output/'input-manifest.json')
    if plan.get('planned_samples') != 3:
        raise ValueError('已取消全量重评；仅允许明确的 3 个问题样本')
    for name,checksum in plan['input_sha256'].items():
        if sha(output/'inputs'/name)!=checksum:
            raise ValueError('重评输入已改变：'+name)
    for scene in ('weather','home_switch'):
        destination=output/scene
        if destination.exists():
            raise ValueError('评分目录已存在，必须先核查旧执行记录，不自动覆盖或重复发送')
    results={}
    for scene in ('weather','home_switch'):
        command=[str(server_python),'-B',str(server/'text-client/revise_scores.py'),
                 '--scenario',scene,'--workers','2','--eval-config',str(config),
                 '--input',str(output/'inputs'/f'{scene}-conversations.json'),
                 '--source-scores',str(output/'inputs'/f'{scene}-source-scores.json'),
                 '--output-dir',str(output/scene)]
        if scene=='weather':command.append('--allow-legacy-model-name')
        with (output/f'{scene}.log').open('w') as log:
            result=subprocess.run(command,cwd=server,stdout=log,stderr=subprocess.STDOUT,check=False)
        results[scene]={'returncode':result.returncode,'scores':str(output/scene/'scores.json')}
        write(output/'execution.json',results)
        if result.returncode:
            return result.returncode
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--server-dir',type=Path,required=True)
    parser.add_argument('--validation',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--server-python',type=Path)
    parser.add_argument('--eval-config',type=Path)
    args=parser.parse_args()
    project,server,output=args.project.resolve(),args.server_dir.resolve(),args.output_dir.resolve()
    if not args.execute:
        plan=prepare(project,server,args.validation,output)
        print(json.dumps({'status':plan['status'],'planned':plan['planned_samples']},ensure_ascii=False))
        return 0
    if not args.server_python or not args.eval_config:
        parser.error('--execute 需要 --server-python 和 --eval-config')
    return execute(server,args.server_python.absolute(),args.eval_config.resolve(),args.validation,output)


if __name__=='__main__':
    raise SystemExit(main())
