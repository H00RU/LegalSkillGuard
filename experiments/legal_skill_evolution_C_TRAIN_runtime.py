"""Materialize and execute the paid 24-source C function/rule update.

No second teacher, no new data, no mixed-study restart. The acquired source
program now owns its whole fragment interface; an older conversion wrapper
must not overwrite these newly learned functions. Prior libraries remain
available for actual-input attribution, never as supplied old Norm results.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import time

from experiments import legal_skill_evolution_C_TRAIN_completion as generation
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import observe
from legal_skill_guard.skill_evolution.relational_rules import validate_language
from legal_skill_guard.skill_evolution.scoped_grammar import constructors
from legal_skill_guard.skill_evolution.source_composition import validate_renderers, validate_template_constructors
from legal_skill_guard.skill_evolution.source_disposal_review import with_disposal_review
from legal_skill_guard.skill_evolution.source_observations import fact

ROOT=generation.ROOT
RUN='legal_skill_evolution_C_TRAIN_runtime_20261115'
OUT=ROOT/'artifacts'/RUN
prior=generation.prior


def read(path):return json.loads(path.read_text())


def prepare():
    p=deepcopy(generation.protocol());bundles=generation.compile_functions()
    for arm,bundle in bundles.items():
        library=bundle['library'];delta=bundle['rule_delta']
        if arm=='C':
            # The generated apply now returns complete acquired fragment channels.
            # Its preserved neural conversion is already part of learned code.
            library.pop('retained_fragment_library')
            language=library['language']
            extra=json.loads(delta['signature_additions_json'])
            assert all(s['kind']in ('derived','output')for s in extra.values())
            language['signatures'].update(extra)
            assert language['signatures']['fragment_query']=={'arguments':['term','query'],'kind':'observed'}
            for sort,values in json.loads(delta['constant_additions_json']).items():
                language['constants'][sort]=list(dict.fromkeys(language['constants'].get(sort,[])+values))
            for sort,values in [('operation',[o['name']for o in library['operations']]),
                ('choice',[c['name']for o in library['operations']for c in o['choices']]),
                ('constructor',list(constructors(library['spec']))),
                ('sort',sorted({c['sort']for c in library['spec']['constructors']}))]:
                language['constants'][sort]=list(dict.fromkeys(language['constants'].get(sort,[])+values))
            rules={r['id']:r for r in language['rules']}
            for identity in delta['removed_rule_ids']:del rules[identity]
            rules.update({r['id']:r for r in json.loads(delta['rule_edits_json'])})
            language['rules']=list(rules.values())
            renderers={r['predicate']:r for r in library['renderers']}
            renderers.update({r['predicate']:r for r in json.loads(delta['renderer_edits_json'])})
            library['renderers']=list(renderers.values());library['selected_rule_ids']=delta['suggested_rule_ids']
            assert set(library['selected_rule_ids'])<=set(rules)
            validate_language(language);validate_renderers(language,library['renderers'])
            validate_template_constructors(library['renderers'],library['spec'])
        else:
            assert not any(json.loads(delta[k])for k in ('signature_additions_json','constant_additions_json','rule_edits_json','renderer_edits_json'))
            assert not delta['removed_rule_ids']and not delta['suggested_rule_ids']
        immutable_json(OUT/arm/'candidate.json',library)
    p.update(run_id=RUN,generation_run=generation.RUN,fitting_wall_time_seconds=120,
        ledger_before=prior.g.previous.base.lineage.ledger_snapshot(),
        legacy_conversion_does_not_overwrite_new_learned_program=True)
    files=[Path(__file__),Path(generation.__file__),Path(generation.core.__file__)]+sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    files += [OUT/a/'candidate.json'for a in ('C','FreeTeacher')]
    files += [generation.OUT/n for n in ('protocol.json','raw_source_bank.json','TRAIN_grading.json','C/teacher.json','FreeTeacher/teacher.json')]
    p['source_sha256']={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files}
    immutable_json(OUT/'protocol.json',p)
    for f in files:
        target=OUT/'source_snapshot'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    print(json.dumps({'prepared':RUN,'original_TRAIN_sources':24,'teacher_requests':0}),flush=True)


def protocol():
    p=read(OUT/'protocol.json')
    for path,sha in p['source_sha256'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,path
    return p


def convert(library,raw):
    if 'source_revision' in library:
        # Each frozen producer performs its own current-source conversion.
        return deepcopy(raw)
    value=prior.g.program_concepts(library,raw)
    if 'source_concept_execution'not in value:return value
    links=[]
    for fragment in value['source_concept_execution']['program_output']['fragments']:
        for identity,root in value['legacy_roots'].items():
            if root['term']==fragment['term']:
                for query in fragment['query_ids']:
                    edge=fact('fragment_query',identity,query)
                    if edge not in links:links.append(edge)
    value['context']['facts']+=links
    value['fragment_query_provenance']={'edges':links,'from_actual_program_output':True,'new_legal_semantics':False}
    return value


def assess(library,observation,sid):
    source=read(generation.OUT/'raw_source_bank.json')[sid]['source']
    grading=read(generation.OUT/'TRAIN_grading.json')[sid]
    output=generation.core.evaluate_source(library,observation,source,None)['execution']['source_output']
    reviews=read(prior.g.previous.base.history.OUT/'teacher_task.json')['shared_partial_reviews']
    feedback=with_disposal_review(generation.core.checker(library,source,grading),sid,
        reviews.get('shared_reviewed_source_scope_checks')or[],library['spec']['decision_program'],
        authorization_review=reviews.get('shared_branch_authorization_review'))(output)
    frame=prior.g.previous.base.history.frame_review(sid,output)
    return {'source':sid,'feedback':feedback,'frame_review':frame,'source_output':output,
        'hard_source_pass':feedback.get('source_review_passed',True)and not frame['failures'],
        'native_correct':sum(bool(v['score']and v['score']['correct'])for v in feedback['views']),
        'native_total':len(feedback['views']),'unresolved':sum(not v['core_executed']for v in feedback['views'])}


def offline():
    p=protocol();rows=[]
    for arm in ('C','FreeTeacher'):
        library=read(OUT/arm/'candidate.json')
        for sid in p['sources']:
            path=prior.OUT/arm/'raw_observations'/(digest(sid)+'.json')
            if not path.exists():continue
            observation=convert(library,read(path));result=assess(library,observation,sid)
            immutable_json(OUT/'offline_paid_inputs'/arm/(digest(sid)+'.json'),result)
            rows.append({'arm':arm,'source':sid,'native':result['native_correct'],
                'source_pass':result['hard_source_pass'],'unresolved':result['unresolved']})
    immutable_json(OUT/'offline_paid_input_summary.json',{'rows':rows,'new_model_requests':0,
        'actual_ten_existing_sources_each_arm':True,'not_new_validation':True})
    print(json.dumps({'offline_rows':rows,'new_model_requests':0}),flush=True)


def collect():
    p=protocol();assert(OUT/'offline_paid_input_summary.json').exists()
    bank=read(generation.OUT/'raw_source_bank.json')
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p))
    client=FrozenExecutor(ledger,OUT,p['executor_profile'])
    for arm in ('C','FreeTeacher'):
        library=read(OUT/arm/'candidate.json')
        for sid in p['sources']:
            target=OUT/arm/'observations'/(digest(sid)+'.json')
            if target.exists():continue
            prior_path=prior.OUT/arm/'raw_observations'/target.name
            histories=[read(prior_path)]if prior_path.exists()else[];item=bank[sid]
            raw=observe(client,RUN+':'+arm+':'+digest(sid),sid,library,
                source_text=item['source']['views'][0]['public']['source_text'],units=item['units'],
                source_output=item['empty_upstream'],previous_observations=histories,
                save_event=lambda e:immutable_json(OUT/arm/'read_events'/(digest(e['call_id'])+'.json'),e))
            immutable_json(OUT/arm/'raw_observations'/target.name,raw)
            value=convert(library,raw);immutable_json(target,value)
            row=assess(library,value,sid);immutable_json(OUT/arm/'initial_rows'/target.name,row)
            print(json.dumps({'arm':arm,'source':sid,'native':row['native_correct'],
                'source_pass':row['hard_source_pass'],'new_E':raw['new_model_requests']}),flush=True)
    immutable_json(OUT/'all24_reads_collected.json',{'sources':p['sources'],'new_teacher_requests':0,
        'goal_complete':False,'new_DEV_TEST':False})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('prepare','offline','collect'));args=parser.parse_args()
    with(ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'prepare':prepare,'offline':offline,'collect':collect}[args.phase]()
