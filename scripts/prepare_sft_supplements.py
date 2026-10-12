"""准备首批 80 个 SFT 补充任务；只做本地生成和排重，不请求模型。"""
from __future__ import annotations
import argparse
import copy
import json
import random
from collections import Counter
from pathlib import Path

from generate_evaluation_seeds import (
    Library, home_generator, generate_scenario, group_seeds, load_prepared_inputs,
    read_json, sha256_file, sha256_value, semantic_fingerprint, write_json,
)
from prepare_sft_diagnostics import exclusions

QUOTAS={'home_switch':{'T04':4,'T06':6,'T07':8,'T08':8,'T11':10,'T17':6,'T19':8,'T20':10},
        'weather':{'S11':5,'S15':5,'S20':5,'S22':5}}


def configuration_identity(config):
    """Ignore preset names, but preserve the order of the model-visible catalog."""
    value={k:copy.deepcopy(v) for k,v in config.items() if k not in {'preset','description','library_version'}}
    value['devices']=list(config['devices'].items())
    return value


def grounded_fingerprint(seed, presets):
    value={k:copy.deepcopy(v) for k,v in seed.items()
           if k not in {'seed_id','variable_group_id','question_pattern_id','user_turns'}}
    if 'preset' in value:
        value['preset']=configuration_identity(presets[value['preset']])
    return sha256_value(value)


def remap(value, mapping):
    if isinstance(value,dict):return {mapping.get(k,k):remap(v,mapping) for k,v in value.items()}
    if isinstance(value,list):return [remap(v,mapping) for v in value]
    return mapping.get(value,value) if isinstance(value,str) else value


def expand_presets(originals, rng):
    """Vary catalogs and state; retain the simulator's existing fault mechanisms."""
    expanded, lineage={},[]
    for name,original in sorted(originals.items()):
        for index in range(1,9):
            config=copy.deepcopy(original)
            new_name=f'{name}_sft_r1_{index:02d}'
            config['preset']=new_name
            config['description']=f'SFT补充配置：{name} 第{index}组'
            ids=list(config['devices']);rng.shuffle(ids)
            config['devices']={eid:config['devices'][eid] for eid in ids}
            rng.shuffle(config['candidates'])
            changed=[]
            locked={r['entity_id'] for r in config.get('rules',[])}
            for eid,device in config['devices'].items():
                if device['controllable'] and eid not in locked and rng.random()<0.5:
                    device['state']='off' if device['state']=='on' else 'on'
                    for patch in [config.get('initial',{}),config.get('turns',{}).get('1',{})]:
                        if eid in patch.get('states',{}):patch['states'][eid]=device['state']
                    changed.append(eid)
            moved=None
            if locked and index%2==0:
                first=sorted(locked)[0]
                candidates=[e for e,d in config['devices'].items() if d['controllable'] and e not in locked]
                if candidates:
                    other=rng.choice(candidates);mapping={first:other,other:first}
                    for key in ('initial','rules','turns'):
                        if key in config:config[key]=remap(config[key],mapping)
                    a,b=config['devices'][first],config['devices'][other]
                    a['state'],b['state']=b['state'],a['state']
                    moved={'from':first,'to':other}
            if configuration_identity(config)==configuration_identity(original):continue
            expanded[new_name]=config
            lineage.append({'preset':new_name,'derived_from':name,'changed_initial_devices':changed,
                            'moved_fault':moved,'configuration_sha256':sha256_value(configuration_identity(config))})
    return expanded,lineage


def select_group(group, number, scene):
    row=copy.deepcopy(sorted(group,key=lambda r:r['question_pattern_id'])[(number-1)%3])
    row['variable_group_id']=f"{row['template_id']}-R{number:03d}"
    row['seed_id']=row['variable_group_id']+'-'+row['question_pattern_id']
    return row


def prepare(project, output, random_seed=20261012):
    if output.exists():raise ValueError('请使用新补数目录，不覆盖旧任务')
    sources,binding=load_prepared_inputs(project/'config.json',project/'data/prepared')
    original_library=Library(sources['home_switch']['conversations_path'])
    originals={r['preset']:original_library.resolve(r['preset']) for r in original_library.list_presets(include_special=True)}
    added,lineage=expand_presets(originals,random.Random(random_seed))
    library=Library.from_snapshots(added)
    all_presets={**originals,**added}
    tasks={};report={'purpose':'sft_supplement_not_test','random_seed':random_seed,'baseline':binding,'scenarios':{}}
    for scene,quotas in QUOTAS.items():
        excluded,files=exclusions(project,scene,sources[scene]['conversations'])
        if scene=='weather':
            groups,stats=generate_scenario(scene,quotas,excluded,sources[scene]['conversations_path'],random_seed,100)
            selected=[select_group(rows,i,scene) for i,rows in enumerate(group_seeds(groups).values(),1)]
        else:
            used={grounded_fingerprint(s,all_presets) for s in excluded}
            selected=[];counts=Counter()
            for attempt in range(100):
                if all(counts[t]>=n for t,n in quotas.items()):break
                rows,_=home_generator.generate_seeds(library,templates=list(quotas),groups_per_template=10,random_seed=random_seed+attempt)
                for (template,_),group in sorted(group_seeds(rows).items()):
                    if counts[template]>=quotas[template]:continue
                    candidate=select_group(group,len(selected)+1,scene)
                    fp=grounded_fingerprint(candidate,all_presets)
                    if fp in used:continue
                    home_generator.validate_seed(candidate,library)
                    used.add(fp);selected.append(candidate);counts[template]+=1
            if dict(counts)!=quotas:raise ValueError('独立家居任务不足，不能降低排重要求')
        check=lambda s:grounded_fingerprint(s,all_presets) if scene=='home_switch' else semantic_fingerprint(s)
        old={check(s) for s in excluded};new=[check(s) for s in selected]
        if len(set(new))!=len(new) or set(new)&old:raise ValueError('任务排重失败')
        if dict(Counter(s['template_id'] for s in selected))!=quotas:raise ValueError('模板配额不一致')
        tasks[scene]=selected
        report['scenarios'][scene]={'tasks':len(selected),'template_counts':quotas,'excluded_records':len(excluded),
                                   'excluded_files':files,'grounded_overlap':0,'internal_duplicates':0}
    used_names={s['preset'] for s in tasks['home_switch']}
    output.mkdir(parents=True)
    for scene,rows in tasks.items():write_json(output/f'{scene}-seeds.json',rows)
    write_json(output/'preset-snapshots.json',{name:added[name] for name in sorted(used_names)})
    write_json(output/'preset-lineage.json',[r for r in lineage if r['preset'] in used_names])
    for name in ('system-prompt.txt','tools.json'):
        (output/name).write_bytes((project/'data/prepared'/name).read_bytes())
    report['artifact_sha256']={p.name:sha256_file(p) for p in sorted(output.iterdir())}
    write_json(output/'generation-report.json',report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    report=prepare(args.project.resolve(),args.output_dir.resolve())
    print(json.dumps({s:r['tasks'] for s,r in report['scenarios'].items()},ensure_ascii=False))


if __name__=='__main__':main()
