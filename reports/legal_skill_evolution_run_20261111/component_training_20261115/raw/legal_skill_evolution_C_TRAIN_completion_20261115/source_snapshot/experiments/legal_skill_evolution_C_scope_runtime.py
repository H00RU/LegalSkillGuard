"""Execute the paid scope-learning proposals after one exact pure-code lowering.

The generation run and its failed locals() validation remain immutable. This
runtime lowers only an actual uninitialized-local guard without adding semantics
or introspection to the shared worker. No teacher retry, no neural config change.
"""
import argparse
import ast
import fcntl
import hashlib
import json
import time
from copy import deepcopy
from pathlib import Path

from experiments import legal_skill_evolution_C_scope_learning as g
from experiments.legal_skill_evolution_C_scope_learning import (
    validate_operations,validate_procedure,validate_language,validate_renderers,
    validate_template_constructors,signatures,constructors,retained)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import observe

ROOT=g.ROOT
RUN='legal_skill_evolution_C_scope_retained_20261115'
PREVIOUS_OUT=ROOT/'artifacts/legal_skill_evolution_C_scope_runtime_20261115'
OUT=ROOT/'artifacts'/RUN


def read(path):return json.loads(path.read_text())


def lower_context_guard(code):
    old="token in context_low if 'context_low' in locals() else ''"
    assert code.count(old)==1 and code.count('locals()')==1
    assert code.count('def apply(inputs, premises):')==1
    fixed=code.replace('def apply(inputs, premises):',"def apply(inputs, premises):\n    context_low = ''").replace(old,'token in context_low')
    validate_procedure(fixed,allow_helpers=True)
    return fixed


def compile_proposals():
    p=g.protocol();bank=read(g.OUT/'raw_source_bank.json');spec=read(g.OUT/'common_spec.json');libraries={}
    for arm in ('C','FreeTeacher'):
        v=deepcopy(read(g.OUT/arm/'teacher.json')['value'])
        if arm=='C':
            code=lower_context_guard(v['source_concept_program'])
            edits={
                'add_fragment(fragments, condition[0], support, condition[1])':
                    'add_fragment(fragments, condition[0], support, condition[1] + [clause_id])',
                "add_fragment(fragments, ['no_condition'], [unit], [condition_id])":
                    "add_fragment(fragments, ['no_condition'], [unit], [condition_id, clause_id])",
                "add_fragment(fragments, ['exception_set', exception], [unit], [exception_id])":
                    "add_fragment(fragments, ['exception_set', exception], [unit], [exception_id, clause_id])"}
            for before,after in edits.items():
                assert code.count(before)==1
                code=code.replace(before,after)
            v['source_concept_program']=code
        ops=v['operations'];validate_operations(ops,{s:bank[s]['source']['views'][0]['public']['source_text']for s in p['acquisition_sources']})
        scopes=json.loads(v['operation_scopes_json']);assert set(scopes)=={o['name']for o in ops}and all(s in ('window','focus_last')for s in scopes.values())
        validate_procedure(v['planner_program'],allow_helpers=True)
        lib={'operations':ops,'operation_scopes':scopes,'scope':'window','planner_program':v['planner_program'],
            'spec':spec,'complete_source_absence_choices':json.loads(v['absence_choices_json'])}
        if v['source_concept_program']:
            validate_procedure(v['source_concept_program'],allow_helpers=True);lib['source_concept_program']=v['source_concept_program']
        if v['free_composition_program']:
            assert arm=='FreeTeacher';validate_procedure(v['free_composition_program'],allow_helpers=True)
            assert not json.loads(v['rule_edits_json'])and not json.loads(v['renderer_edits_json'])and not v['suggested_rule_ids']
            lib['composition_program']=v['free_composition_program']
        else:
            seed=read(g.OUT/'seed_C.json')if arm=='C'else{'language':{'signatures':signatures(),'constants':{},'rules':[]},'renderers':[]}
            language=deepcopy(seed['language']);language['signatures']['term_type']={'arguments':['term','sort'],'kind':'observed'}
            additions=json.loads(v['signature_additions_json']);assert all(s['kind']in ('derived','output')for s in additions.values())
            language['signatures'].update(additions)
            for sort,values in json.loads(v['constant_additions_json']).items():language['constants'][sort]=list(dict.fromkeys(language['constants'].get(sort,[])+values))
            for sort,values in [('operation',[o['name']for o in ops]),('choice',[c['name']for o in ops for c in o['choices']]),('constructor',list(constructors(spec))),('sort',sorted({c['sort']for c in spec['constructors']}))]:
                language['constants'][sort]=list(dict.fromkeys(language['constants'].get(sort,[])+values))
            rules={r['id']:r for r in language['rules']}
            for identity in v['removed_rule_ids']:del rules[identity]
            edits=json.loads(v['rule_edits_json'])
            language['signatures']['fragment_query']={'arguments':['term','query'],'kind':'observed'}
            for rule in edits:
                anchors=[a['arguments'][0]for a in rule['body']if a['predicate']=='reader_query']
                assert len(anchors)==1
                roots=[a['arguments'][0]for a in rule['body']if a['predicate']=='legacy_root']
                for root in roots:
                    rule['body'].append({'predicate':'fragment_query','arguments':[root,anchors[0]],'sign':'positive'})
            rules.update({r['id']:r for r in edits});language['rules']=list(rules.values())
            renderers={r['predicate']:r for r in seed['renderers']};renderers.update({r['predicate']:r for r in json.loads(v['renderer_edits_json'])})
            validate_language(language);validate_renderers(language,list(renderers.values()));validate_template_constructors(list(renderers.values()),spec)
            assert set(v['suggested_rule_ids'])<=set(rules)
            lib.update(language=language,renderers=list(renderers.values()),selected_rule_ids=v['suggested_rule_ids'])
        old=read(retained.OUT/arm/'selected_before_reuse.json')['library']
        assert lib['planner_program']==old['planner_program'],'Neural planner must remain unchanged'
        assert lib['complete_source_absence_choices']==old['complete_source_absence_choices']
        by_name={o['name']:o for o in lib['operations']}
        for op in old['operations']:
            assert by_name[op['name']]==op,op['name']
            assert lib['operation_scopes'][op['name']]==old['operation_scopes'][op['name']]
        if arm=='C':lib['retained_fragment_library']=old['retained_fragment_library']
        libraries[arm]=lib
    return libraries


def combine_programs(old,new,kind):
    parts=[]
    for prefix,code in (('retained_',old),('proposed_',new)):
        tree=ast.parse(code);names={n.name for n in tree.body}
        class Rename(ast.NodeTransformer):
            def visit_FunctionDef(self,node):
                node.name=prefix+node.name;self.generic_visit(node);return node
            def visit_Name(self,node):
                if node.id in names:node.id=prefix+node.id
                return node
        parts.append(ast.unparse(Rename().visit(tree)))
    if kind=='C':
        tail="""
def apply(inputs,premises):
    old=retained_apply(inputs,premises)
    new=proposed_apply(inputs,premises)
    out={'queries':[],'answers':[],'fragments':[],'unresolved':[]}
    for key in out:
        for row in old[key]+new[key]:
            if key in ('queries','answers'):
                for known in out[key]:
                    if known['id']==row['id'] and known!=row:
                        raise ValueError('Conflicting acquired program identities')
            if row not in out[key]:out[key].append(row)
    return out
"""
    else:
        tail="""
def apply(inputs,premises):
    old=retained_apply(inputs,premises)
    new=proposed_apply(inputs,premises)
    rows=[]
    for row in old['statements']+new['statements']:
        if row not in rows:rows.append(row)
    unresolved=[]
    for value in old['unresolved']+new['unresolved']:
        if value not in unresolved:unresolved.append(value)
    return {'statements':rows,'complete':old['complete'] and new['complete'],'unresolved':unresolved}
"""
    result='\n\n'.join(parts)+tail
    validate_procedure(result,allow_helpers=True)
    return result


def prepare():
    p=deepcopy(g.protocol());libraries=compile_proposals()
    for arm,library in libraries.items():
        old=read(retained.OUT/arm/'selected_before_reuse.json')['library']
        field='source_concept_program'if arm=='C'else'composition_program'
        library['program_variants']={'New':library[field],'Old':old[field],
            'Union':combine_programs(old[field],library[field],arm)}
        immutable_json(OUT/arm/'candidate.json',library)
    p.update(run_id=RUN,generation_run=g.RUN,ledger_before=g.previous.base.lineage.ledger_snapshot(),
        repair='Preserve paid proposal and exact local lowering; compare New/Old/Union source programs equally for both arms using only development feedback; no new teacher',
        no_legal_semantics_added=True)
    files=[Path(__file__),Path(g.__file__),Path(retained.__file__),Path(retained.acquisition.__file__)]+sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    files += [OUT/a/'candidate.json'for a in ('C','FreeTeacher')]
    files += [g.OUT/n for n in ('protocol.json','raw_source_bank.json','TRAIN_grading.json','C/teacher.json','FreeTeacher/teacher.json')]
    p['source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files}
    immutable_json(OUT/'protocol.json',p)
    for f in files:
        target=OUT/'source_snapshot'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    print(json.dumps({'prepared':RUN,'new_teacher_requests':0}),flush=True)


def protocol():
    p=read(OUT/'protocol.json')
    for path,sha in p['source_sha256'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,path
    return p


def convert(library,raw):
    value=g.program_concepts(library,raw)
    if 'source_concept_execution'not in value:return value
    produced=value['source_concept_execution']['program_output']['fragments']
    preserved=value['source_concept_execution'].get('composed_fragments',{}).get('retained_other_fragments',[])
    links=[]
    for fragment in produced+preserved:
        for identity,root in value['legacy_roots'].items():
            if root['term']==fragment['term']:
                for query in fragment['query_ids']:
                    link=g.fact('fragment_query',identity,query)
                    if link not in links:links.append(link)
    value['context']['facts']+=links
    value['fragment_query_provenance']={'edges':links,'derived_from_actual_program_query_ids':True,
        'new_legal_semantics':False,'allows_no_cross_group_cartesian_products':True}
    return value


def execute(*,fit_only=False):
    p=protocol();bank=read(g.OUT/'raw_source_bank.json');results=[]
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p))
    client=FrozenExecutor(ledger,OUT,p['executor_profile'])
    for arm in ('C','FreeTeacher'):
        base=read(OUT/arm/'candidate.json');folder=OUT/arm
        field='source_concept_program'if arm=='C'else'composition_program'
        programs=base.pop('program_variants');variants={}
        for name,code in programs.items():
            lib=deepcopy(base);lib[field]=code;variants[name]=lib
        def raw_observation(sid):
            target=folder/'raw_observations'/(digest(sid)+'.json')
            if target.exists():return read(target)
            histories=[]
            for prior in (retained.OUT/arm/'raw_observations'/target.name,
                PREVIOUS_OUT/arm/'raw_observations'/target.name):
                if prior.exists():histories.append(read(prior))
            item=bank[sid]
            raw=observe(client,RUN+':'+arm+':'+digest(sid),sid,base,
                source_text=item['source']['views'][0]['public']['source_text'],units=item['units'],
                source_output=item['empty_upstream'],previous_observations=histories,
                save_event=lambda event:immutable_json(folder/'read_events'/(digest(event['call_id'])+'.json'),event))
            immutable_json(target,raw)
            if sid in p['acquisition_sources']:assert raw['new_model_requests']==0
            return raw
        def observation(name,sid):
            target=folder/'observations'/name/(digest(sid)+'.json')
            if target.exists():return read(target)
            value=convert(variants[name],raw_observation(sid))
            immutable_json(target,value);return value
        if (folder/'selected_before_reuse.json').exists():
            frozen=read(folder/'selected_before_reuse.json');name=frozen['program_variant'];library=frozen['library']
            nofit=read(folder/'NoFit_acquisition.json')
            observations={name:{sid:observation(name,sid)for sid in p['acquisition_sources']}}
        else:
            observations={name:{sid:observation(name,sid)for sid in p['acquisition_sources']}for name in variants}
            nofit=[g.assess(variants['New'],observations['New'][sid],sid)for sid in p['acquisition_sources']]
            best=None;trials=[];start=time.monotonic()
            if 'language'in base:
                names=[r['id']for r in base['language']['rules']];suggested=base['selected_rule_ids']
                costs={r['id']:r['cost']for r in base['language']['rules']}
                selections=[suggested,[],names]+[sorted(set(suggested)^{name})for name in names]
                schedule=[(name,ids)for ids in selections for name in variants];seen=set()
                for name,ids in schedule:
                    key=tuple(sorted(ids));identity=(name,key)
                    if identity in seen:continue
                    if len(trials)>=9 and time.monotonic()-start>=p['fitting_wall_time_seconds']:break
                    seen.add(identity);candidate=deepcopy(variants[name]);candidate['selected_rule_ids']=list(key)
                    rows=[g.assess(candidate,observations[name][sid],sid)for sid in p['acquisition_sources']]
                    valid=all(r['hard_source_pass']for r in rows)
                    rank=(-sum(r['native_correct']for r in rows),sum(costs[i]for i in key),len(programs[name]),len(key),key,name)
                    trials.append({'program_variant':name,'rule_ids':list(key),'rows':rows,'hard_source_pass':valid})
                    if valid and(best is None or rank<best[0]):best=(rank,name,candidate)
            else:
                for name,lib in variants.items():
                    rows=[g.assess(lib,observations[name][sid],sid)for sid in p['acquisition_sources']]
                    failures=sum(not r['hard_source_pass']for r in rows)
                    rank=(failures,-sum(r['native_correct']for r in rows),len(programs[name]),name)
                    trials.append({'program_variant':name,'rows':rows,'source_failures':failures})
                    if best is None or rank<best[0]:best=(rank,name,lib)
            immutable_json(folder/'fit_receipt.json',{'trials':trials,'new_model_requests':0,
                'both_arms_have_same_old_new_union_retention_operator':True,'optimization_complete':False})
            if best is None:
                immutable_json(folder/'unresolved.json',{'reason':'No source-valid retained candidate'});continue
            _,name,library=best
            immutable_json(folder/'selected_before_reuse.json',{'library':library,'program_variant':name,'acquisition_only':True})
            immutable_json(folder/'NoFit_acquisition.json',nofit)
        if fit_only:
            print(json.dumps({'arm':arm,'frozen_program_variant':name,'new_model_requests':0}),flush=True)
            continue
        acquisition=[g.assess(library,observations[name][sid],sid)for sid in p['acquisition_sources']]
        reuse=[g.assess(library,observation(name,sid),sid)for sid in p['fixed_reuse_sources']]
        attribution=[]
        for sid in p['fixed_reuse_sources']:
            row={'source':sid,'new_model_requests':0,'shared_actual_neural_inputs':True}
            for variant,lib in variants.items():
                candidate=deepcopy(library);candidate[field]=lib[field]
                row[variant+'_same_G']=g.assess(candidate,observation(variant,sid),sid)
            row['NoFit']=g.assess(variants['New'],observation('New',sid),sid);attribution.append(row)
        result={'arm':arm,'selected_program_variant':name,'acquisition':acquisition,'fixed_reuse':reuse,
            'NoFit_acquisition':nofit,'attribution':attribution,'goal_complete':False}
        immutable_json(folder/'result.json',result);results.append(result)
        print(json.dumps({'arm':arm,'variant':name,
            'acquisition':[(r['native_correct'],r['hard_source_pass'],r['unresolved'])for r in acquisition],
            'reuse':[(r['native_correct'],r['hard_source_pass'],r['unresolved'])for r in reuse]}),flush=True)
    if not fit_only:immutable_json(OUT/'result.json',{'arms':results,'goal_complete':False,'new_DEV_TEST':False})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('prepare','fit','execute'));args=parser.parse_args()
    with(ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'prepare':prepare,'fit':lambda:execute(fit_only=True),'execute':execute}[args.phase]()

