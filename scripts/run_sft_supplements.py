"""用已选文字客户端模型生成一次补充示范，再调用后端评分。

所有模型解析、对话生成、模拟器和评分仍由后端实现。本入口只复制输入、
将当前文字客户端的有效参数显式传给 model_eval，并收集结果。
密钥只通过子进程环境传递；同一批次不覆盖、不重复生成失败题。
"""
from __future__ import annotations
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def invoke(command, server, log, environment):
    with log.open('w', encoding='utf-8') as stream:
        return subprocess.run(command, cwd=server, env=environment, stdout=stream,
                              stderr=subprocess.STDOUT, check=False).returncode


def run(args):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', args.run_id):
        raise ValueError('批次名称无效')
    project=args.project.resolve(); server=args.server_dir.resolve()
    repair=project/'data/sft-repair/v1'; source=repair/'supplements'
    sys.path.insert(0,str(project/'scripts'))
    from recheck_sft_data import check_gate, sha
    check_gate(server,repair/'scorer-validation/v4/validation.json')
    # Do not continue past the agreed repair gate with an unaccepted correction.
    for scene in ('weather','home_switch'):
        scored=read(repair/'targeted'/f'{scene}-corrected-scores/scores.json')
        if scored.get('errors') or any(row['status']!='pass' for row in scored['samples']):
            raise ValueError('修正版未全部通过评分，不能开始补数')
    manifest=read(source/'generation-report.json')
    for name, checksum in manifest['artifact_sha256'].items():
        if sha(source/name) != checksum:
            raise ValueError('补数输入校验失败：'+name)
    if sum(x['tasks'] for x in manifest['scenarios'].values())!=80:
        raise ValueError('补数数量必须为 80 个任务')
    # Fixed seed files are never regenerated here.
    batch=server/'tmp/model-eval-runs'/args.run_id
    returned=repair/'supplement-runs'/args.run_id
    if batch.exists() or returned.exists():
        raise ValueError('批次已存在，禁止覆盖或重抽')
    sys.path.insert(0,str(server/'text-client'))
    from eval_config import load_config, resolve_models
    from core.evaluation_model import model_identity, validate_override
    from core.providers.llm.openai.openai import LLMProvider
    original=load_config(args.eval_config)
    resolved=asyncio.run(resolve_models(original,roles=('scoring',)))
    selected=resolved[original['scoring']['model']]
    if selected['source']!='text_client_current':
        raise ValueError('此入口要求已选文字客户端模型')
    # Reuse the provider's parsing to preserve its effective request parameters.
    provider=LLMProvider(selected['config'])
    model={key:getattr(provider,key) for key in ('base_url','model_name','max_tokens',
            'temperature','top_p','frequency_penalty','stream','timeout',
            'allow_message_extras')}
    model.update(type='openai',extra_body=provider.extra_body or {},
                 default_headers=provider.default_headers or {},api_key=provider.api_key)
    validate_override(model)
    if model['default_headers']:
        raise ValueError('当前配置含自定义认证头，需要使用后端原有受保护配置引用')
    environment=os.environ.copy()
    environment['SFT_REPAIR_TEACHER_API_KEY']=model.pop('api_key')
    definition=dict(model,api_key_env='SFT_REPAIR_TEACHER_API_KEY')
    config={'schema_version':1,'connection':original['connection'],
            'models':{'teacher':definition,'judge':{'source':'text_client_current'}},
            'generation':{'model':'teacher','timeout':180,'retries':0},
            'scoring':dict(original['scoring'],model='judge')}
    batch.mkdir(parents=True); returned.mkdir(parents=True)
    shutil.copytree(source,batch/'inputs')
    config_file=batch/'teacher-config.json';write(config_file,config)
    write(batch/'teacher-provenance.json',{'selected_text_client_identity':selected['identity'],
        'explicit_effective_identity':model_identity(model),
        'note':'空字符串通过原 provider 解析成实际有效参数；身份指纹不同，不冒充原始配置指纹相同。'})
    # Each task appears in exactly one shard. A failed task is not regenerated.
    jobs=[]
    for scene,count in (('weather',1),('home_switch',3)):
        seeds=read(source/f'{scene}-seeds.json')
        for index in range(count):
            name=f'{scene}-{index+1}'; path=batch/'inputs'/f'{name}-seeds.json'
            write(path,seeds[index::count]);jobs.append((scene,name,path))
    write(batch/'run.json',{'status':'running','planned':80,'input_sha256':{
        f.name:sha(f) for f in sorted((batch/'inputs').iterdir()) if f.is_file()},
        'generation_retries':0,'shards':[name for _,name,_ in jobs]})
    def execute(job):
        scene,name,seeds=job; destination=batch/name;destination.mkdir()
        generation=destination/'generation'; scoring=destination/'scoring'
        command=[str(args.server_python),'-B',str(server/'text-client/generate_conversations.py'),
                 '--scenario',scene,'--environment','model_eval','--eval-config',str(config_file),
                 '--seeds',str(seeds),'--output-dir',str(generation),
                 '--system-prompt-file',str(batch/'inputs/system-prompt.txt'),
                 '--tools-file',str(batch/'inputs/tools.json'),
                 '--tool-backend','simulated' if scene=='home_switch' else 'real']
        if scene=='home_switch':
            command+=['--preset-snapshots',str(batch/'inputs/preset-snapshots.json')]
        code=invoke(command,server,destination/'generation.log',environment)
        conversations=generation/'conversations.json'
        score_code=None
        if conversations.exists() and read(conversations):
            score_code=invoke([str(args.server_python),'-B',str(server/'text-client/score_results.py'),
                '--scenario',scene,'--eval-config',str(config_file),'--input',str(conversations),
                '--output-dir',str(scoring)],server,destination/'scoring.log',environment)
        result={'scenario':scene,'shard':name,'generation_returncode':code,'scoring_returncode':score_code}
        write(destination/'execution.json',result)
        shutil.copytree(destination,returned/name)
        return result
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(execute,jobs))
    write(batch/'execution.json',results)
    for name in ('execution.json','teacher-provenance.json','run.json'):
        shutil.copy2(batch/name,returned/name)
    write(returned/'backend-location.json',{'path':str(batch)})
    print(json.dumps(results,ensure_ascii=False))
    return 1 if any(r['generation_returncode'] or r['scoring_returncode'] for r in results) else 0


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--server-dir',type=Path,required=True)
    p.add_argument('--server-python',type=Path,required=True)
    p.add_argument('--eval-config',type=Path,required=True)
    p.add_argument('--run-id',required=True)
    return run(p.parse_args())


if __name__=='__main__':
    raise SystemExit(main())
