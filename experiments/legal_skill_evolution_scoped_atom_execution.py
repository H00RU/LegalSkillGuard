"""Finite execution of paid source-atom updates on the same two original TRAIN.

No new model request is made: all unchanged neural questions must be in actual
paid histories. The learned source parser and G are genuinely executed here.
"""
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_scoped_atom_acquisition as e
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.open_acquisition import observe,execute_source_program,fit,statement_fingerprint
from legal_skill_guard.skill_evolution.source_observations import encode_source_observations
from legal_skill_guard.skill_evolution.projected_composition_profiles import admissible_projected_compositions
from legal_skill_guard.skill_evolution.span_compiler import execute_json
from legal_skill_guard.skill_evolution.objects import digest


class NoNewRequests:
    def __init__(self,config):self.config=config
    def generate(self,*args,**kwargs):
        raise RuntimeError('This finite execution forbids new model calls; preserve and diagnose a genuinely new reading before dispatch')


def annotate(observation,arm):
    v=observation['visible_inputs'];support=set();anchors=[]
    for row in v['source_output']['statements']:
        if row['term'][0]==e.SCOPE_MARKER['name']:support.update(row['support_ids'])
    for a in v['answers']:
        if a.get('operation')==e.CONTROL[arm]['locator'] and a['choice']=='candidate_found':
            anchors.extend(w['unit_id'] for w in a['evidence'])
    mode='program' if anchors and set(anchors)<=support else 'neural'
    output=deepcopy(v['source_output'])
    marker={'term':[e.MODE_MARKER['name'],mode],
            'support_ids':sorted(set(anchors)) or [u['id'] for u in v['units']]}
    output['statements'].append(marker)
    result=encode_source_observations(observation['context']['id'],source_text=v['source_text'],units=v['units'],
        source_output=output,operations=v['operations'],queries=v['queries'],answers=v['answers'],scope=v['scope'],
        query_scopes=v['query_scopes'],complete_source_absence_choices=v.get('complete_source_absence_choices'))
    result['execution']=deepcopy(observation['execution'])
    trace=result['execution']['acquired_source_program'];trace['output_sha256']=digest(output)
    trace['statement_origins'][statement_fingerprint(marker)]='source_program_new_or_changed'
    trace['observer_added_computational_metadata_fingerprints']=[statement_fingerprint(marker)]
    result['execution']['disposal_backend']={'mode':mode,'locator_anchors':sorted(set(anchors)),
        'supported_units':sorted(support),'legal_fact':False,
        'fine_queries_already_issued_before_scope_coverage':[q['id'] for q in v['queries'] if q['operation'] in e.CONTROL[arm]['blocked']],
        'program_output_before_metadata_sha256':digest(v['source_output'])}
    return result


def run():
    p,_,public=e.setup();grading=e.read(e.prior.prior.GRADING)
    folder=e.OUT/'execution';before=e.prior.rows()
    assert not any(r[6]=='reserved' for r in before)
    sources=[Path(__file__),Path(e.__file__),e.ROOT/'experiments/legal_skill_evolution_scoped_atom_adapter.py',
        e.ROOT/'legal_skill_guard/skill_evolution/projected_composition_profiles.py',
        e.ROOT/'legal_skill_guard/skill_evolution/projected_composition_worker.py',
        e.ROOT/'tests/test_skill_evolution_projected_profiles.py']
    data=[e.OUT/'protocol.json',*[e.OUT/a/n for a in e.ARMS for n in ('teacher.json','compiled.json','canonical_proposal.json')]]
    protocol={'same_goal':True,'goal_complete':False,'sources':p['sources'],'new_model_requests_allowed':0,
        'unchanged_neural_questions_reuse_actual_paid_histories':True,'no_new_full_training_DEV_TEST_or_paper':True,
        'all23_C_rule_subsets_remain_selectable':True,'old_timeout_kept':True,
        'source_sha256':{str(f.relative_to(e.ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sources},
        'data_sha256':{str(f.relative_to(e.ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in data}}
    immutable_json(folder/'protocol.json',protocol)
    for source in sources:
        dst=folder/'source_snapshot'/source.relative_to(e.ROOT);dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():assert dst.read_bytes()==source.read_bytes()
        else:dst.write_bytes(source.read_bytes())
    for arm in e.ARMS:
        lib=e.read(e.OUT/arm/'compiled.json')
        for key in p['sources']:
            dst=folder/'acquisition'/arm/e.name_for(key)
            if dst.exists():continue
            pub,units,up=e.prior.prior.source_material(e.PARENT,public,key)
            old=e.read(e.OUT/'previous'/arm/'library.json')
            original=execute_json(old['source_program'],{'source_text':pub['source_text'],'source_spans':units,'source_output':up},{},allow_helpers=True)
            output,trace=execute_source_program(lib['source_program'],lib['spec'],source_text=pub['source_text'],units=units,source_output=up)
            assert output['statements'][:len(original['statements'])]==original['statements']
            extra=output['statements'][len(original['statements']):]
            for atom in extra:assert e.term_sort(atom['term'],e.constructors(lib['spec']))!='Norm'
            immutable_json(folder/'actual_atoms'/arm/e.name_for(key),{'source':key,'new_atoms':extra,
                'actual_source_execution':trace,'new_model_requests':0,'type_and_support_are_not_source_semantic_certification':True})
            history=[e.read(e.OUT/'history'/a/e.name_for(key))['observation'] for a in e.ARMS]
            raw=observe(NoNewRequests(p['executor_profile']),e.RUN+':execution:'+arm+':'+key,key,lib,
                source_text=pub['source_text'],units=units,source_output=up,previous_observations=history)
            immutable_json(folder/'raw_observations'/arm/e.name_for(key),raw)
            observation=annotate(raw,arm)
            direct=deepcopy(lib)
            if arm=='ConstraintAcquire':direct['selected_rule_ids']=lib['suggested_rule_ids']
            actual=e.prior.prior.evaluate_source(direct,observation,public[key],grading[key])
            result={'source':key,'observation':observation,'direct':actual}
            if arm=='ConstraintAcquire':
                profile=admissible_projected_compositions(lib,observation,e.prior.prior.checker(lib,public[key],grading[key]),timeout_seconds=90)
                immutable_json(folder/'profiles'/e.name_for(key),profile)
                if profile['status']!='complete':raise ValueError('Paid observation retained; incomplete exact profile cannot supervise G')
                result['profile']=profile
            immutable_json(dst,result)
            print(json.dumps({'arm':arm,'source':key,'backend':observation['execution']['disposal_backend']['mode'],
                'planned_queries':observation['execution']['planned_queries'],'new_requests':observation['execution']['new_physical_requests'],
                'correct':sum(bool(v['score'] and v['score']['correct']) for v in actual['feedback']['views'])}),flush=True)
    lib=e.read(e.OUT/'ConstraintAcquire/compiled.json')
    records=[e.read(folder/'acquisition/ConstraintAcquire'/e.name_for(k)) for k in p['sources']]
    learned,result=fit(lib,[e.prior.prior.attach_scored_theories(r['observation'],r['profile']) for r in records],
        prior_rule_ids=lib['suggested_rule_ids'],timeout_seconds=90)
    immutable_json(folder/'ConstraintAcquire/fit.json',result)
    if result['status']=='sat':
        immutable_json(folder/'ConstraintAcquire/learned.json',learned)
        for row in records:
            key=row['source'];immutable_json(folder/'ConstraintAcquire/fitted_execution'/e.name_for(key),
                e.prior.prior.evaluate_source(learned,row['observation'],public[key],grading[key]))
    assert before==e.prior.rows()
    immutable_json(folder/'TERMINAL_PRESERVATION.json',{'client_terminal':True,'goal_complete':False,'new_model_requests':0,
        'ledger_rows':len(before),'old_all_rows_unchanged':True,'reserved':0,'G_fit_status':result['status']})
    print(json.dumps({'complete_finite_execution':True,'new_model_requests':0,'G_fit_status':result['status']}),flush=True)


if __name__=='__main__':
    with (e.ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        run()
