"""Learn a supported G after the raw-source C path's actual gate failure.

Only generic single-choice guard deletion is added to the frozen hypothesis
bias. No legal rule, corrected reader answer or new source enters the host.
The original raw acquisition, strong free teacher and all expenses remain.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import time

from experiments import legal_skill_evolution_C_direct_acquisition as base
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import observe
from legal_skill_guard.skill_evolution.relational_rules import validate_language
from legal_skill_guard.skill_evolution.source_observations import encode_source_observations

ROOT=base.ROOT
RUN='legal_skill_evolution_C_guard_learning_20261115'
OUT=ROOT/'artifacts'/RUN


def expanded(library):
    result=deepcopy(library);rules=result['language']['rules'];edits=[]
    for original in library['language']['rules']:
        if library['language']['signatures'][original['head']['predicate']]['kind']!='output':continue
        choices=[i for i,a in enumerate(original['body'])if a['predicate']=='query_choice'and a['sign']=='positive']
        # Every alternative still requires actual acquired semantic choices.
        if len(choices)<2:continue
        for i in choices:
            rule=deepcopy(original);rule['id']=original['id']+'__omit_choice_'+str(i)
            rule['cost']=original['cost']+1
            del rule['body'][i]
            trial=deepcopy(result['language']);trial['rules']=[rule]
            try:validate_language(trial)
            except ValueError:continue
            rules.append(rule);edits.append({'original':original['id'],'candidate':rule['id'],
                'omitted_atom':original['body'][i],'no_observation_changed':True})
    validate_language(result['language'])
    return result,edits


def fit():
    p=base.protocol();library,edits=expanded(base.compile_proposals()['C'])
    observations={sid:base.read(base.OUT/'C/observations'/(digest(sid)+'.json'))for sid in p['acquisition_sources']}
    original=library['selected_rule_ids'];costs={r['id']:r['cost']for r in library['language']['rules']}
    # The previous complete local search had no source-valid hypothesis.
    # New alternatives are generated uniformly, without inspecting case IDs,
    # native labels, clause words or the known missing target's predicate.
    candidates=[original,[]]
    candidates += [sorted((set(original)-{e['original']})|{e['candidate']})for e in edits]
    start=time.monotonic();trials=[];best=None;seen=set()
    def check(ids):
        nonlocal best
        key=tuple(sorted(ids))
        if key in seen:return
        seen.add(key);candidate=deepcopy(library);candidate['selected_rule_ids']=list(key)
        rows=[base.assess(candidate,observations[s],s)for s in p['acquisition_sources']]
        rank=(-sum(r['native_correct']for r in rows),sum(costs[i]for i in key),len(key),key)
        valid=all(r['hard_source_pass']for r in rows)
        trials.append({'rule_ids':list(key),'rows':rows,'hard_source_pass':valid,'rank':rank})
        if valid and(best is None or rank<best[0]):best=(rank,candidate)
    for ids in candidates:
        if trials and time.monotonic()-start>=p['fitting_wall_time_seconds']:break
        check(ids)
    # Source/native checks, rather than syntactic inactivity, govern pruning.
    if best:
        for identity in list(best[1]['selected_rule_ids']):
            if time.monotonic()-start>=p['fitting_wall_time_seconds']:break
            check(set(best[1]['selected_rule_ids'])-{identity})
    immutable_json(OUT/'fit_receipt.json',{'candidate_edits':edits,'trials':trials,
        'optimization_complete':False,'finite_local_selection':True,'new_model_calls':0,
        'unchanged_source_checks':True,'fit_seconds':time.monotonic()-start})
    if best is None:
        immutable_json(OUT/'unresolved.json',{'reason':'No source-valid G in expanded tested bias','new_model_calls':0})
        print(json.dumps({'source_valid_G':False}),flush=True);return
    immutable_json(OUT/'selected_before_reuse.json',{'library':best[1],
        'acquisition_only_selection':True,'reuse_not_consulted_by_fit':True,
        'previous_B8_exposure_disclosed':True,'new_model_calls':0})
    files=[Path(__file__),Path(base.__file__),Path(base.history.__file__)]+sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py'))
    files+=[base.OUT/n for n in ('protocol.json','raw_source_bank.json','TRAIN_grading.json','C/teacher.json','FreeTeacher/teacher.json')]
    protocol={**deepcopy(p),'run_id':RUN,'previous_run':base.RUN,'ledger_before':base.lineage.ledger_snapshot(),
        'frozen_library_sha256':digest(best[1]),'source_sha256':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()for f in files}}
    immutable_json(OUT/'protocol.json',protocol)
    for f in files:
        target=OUT/'source_snapshot'/f.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
    print(json.dumps({'source_valid_G':True,'native_acquisition':-best[0][0],
        'selected_rules':best[1]['selected_rule_ids'],'offline_trials':len(trials)}),flush=True)


def run():
    p=base.read(OUT/'protocol.json')
    for path,sha in p['source_sha256'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,path
    library=base.read(OUT/'selected_before_reuse.json')['library'];original=base.compile_proposals()['C']
    assert digest(library)==p['frozen_library_sha256']
    ledger=EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train':p['sources'],'dev':[],'test':[]},binding=digest(p))
    client=FrozenExecutor(ledger,OUT,p['executor_profile']);bank=base.read(base.OUT/'raw_source_bank.json')
    rows=[]
    for sid in p['acquisition_sources']+p['fixed_reuse_sources']:
        target=OUT/'observations'/(digest(sid)+'.json')
        prior=base.OUT/'C/observations'/target.name
        if target.exists():observation=base.read(target)
        elif prior.exists():
            observation=base.read(prior);immutable_json(target,observation)
        else:
            item=bank[sid]
            observation=observe(client,RUN+':C:'+digest(sid),sid,library,
                source_text=item['source']['views'][0]['public']['source_text'],units=item['units'],
                source_output=item['empty_upstream'],
                save_event=lambda event:immutable_json(OUT/'read_events'/(digest(event['call_id'])+'.json'),event))
            immutable_json(target,observation)
        actual=base.assess(library,observation,sid);nofit=base.assess(original,observation,sid)
        v=observation['visible_inputs']
        no_concepts=encode_source_observations(sid,source_text=v['source_text'],units=v['units'],
            source_output=v['source_output'],operations=v['operations'],queries=v['queries'],answers=[],
            scope=v['scope'],query_scopes=v['query_scopes'],
            complete_source_absence_choices=v.get('complete_source_absence_choices'))
        # An intervention, never an actual cached reading or fit input.
        no_concepts['counterfactual_only']=True
        no_phi=base.assess(library,no_concepts,sid)
        row={'source':sid,'phase':'acquisition'if sid in p['acquisition_sources']else'fixed_reuse',
            'C':actual,'NoFit':nofit,'NoConcept':no_phi,
            'source_norm_count':len(actual['source_output']['statements']),
            'actual_composition_uses':actual['source_output'].get('composition_uses',[])}
        immutable_json(OUT/'rows'/(digest(sid)+'.json'),row);rows.append(row)
        print(json.dumps({'source':sid,'C':actual['native_correct'],'source_pass':actual['hard_source_pass'],
            'NoFit':nofit['native_correct'],'NoFit_source_pass':nofit['hard_source_pass'],'NoConcept':no_phi['native_correct']}),flush=True)
    immutable_json(OUT/'result.json',{'rows':rows,'independent_FreeTeacher':base.read(base.OUT/'FreeTeacher/result.json'),
        'goal_complete':False,'new_DEV_TEST':False,'no_concept_is_offline_intervention':True})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('fit','execute'));args=parser.parse_args()
    with(ROOT/'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+')as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        {'fit':fit,'execute':run}[args.phase]()
