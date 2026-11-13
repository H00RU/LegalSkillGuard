"""Audit the actual comparison; no model, new data, grades or program repairs.

Losslessly decode dispatched teacher requests, compare information/seed/config,
and replay actual fact bindings with law-free calendar-call instrumentation.
Deletion probes change a copied diagnostic input only. They are not recovered
predictions, scores, new TRAIN examples, or additional correctness requirements.
"""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3

from experiments.legal_skill_evolution_callable_rule_audit import trace
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.callable_rules import entry_program
from legal_skill_guard.skill_evolution.source_python import CALENDAR_CALLS, validate
from legal_skill_guard.skill_evolution.teacher_transport import unpack

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT/'artifacts/legal_skill_evolution_boundary_refinement_20261113'
RUN = ROOT/'artifacts/legal_skill_evolution_boundary_refinement_role_grounding_20261113'
OUT = ROOT/'artifacts/legal_skill_evolution_boundary_comparison_audit_20261113'


def read(path):
    return json.loads(path.read_text())


def sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def instrument_calendar_calls(program):
    """Name pure forwarding functions so the existing tracer sees public calls."""
    signatures = {'calendar_year':['value'], 'year_days':['year'],
        'inclusive_year_overlap_days':['start','end','year'],
        'elapsed_year_overlap_days':['start','end','year']}
    tree=ast.parse(program)
    existing={node.name for node in tree.body}
    replacements={name:'audit_public_'+name for name in CALENDAR_CALLS}
    assert not existing & set(replacements.values())
    class Instrument(ast.NodeTransformer):
        def visit_Call(self,node):
            self.generic_visit(node)
            if isinstance(node.func,ast.Name) and node.func.id in replacements:
                node.func.id=replacements[node.func.id]
            return node
    tree=Instrument().visit(tree)
    for name,params in signatures.items():
        arguments=','.join(params)
        tree.body.extend(ast.parse('def '+replacements[name]+'('+arguments+'):\n    return '+name+'('+arguments+')\n').body)
    result=ast.unparse(ast.fix_missing_locations(tree))
    validate(result)
    return result,set(replacements.values())


def snapshot():
    db=sqlite3.connect('file:'+str(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')+'?mode=ro',uri=True)
    return {table:[list(r) for r in db.execute('select * from '+table+' order by 1')]
            for table in ('calls','meta','oracle_views')}


def run():
    before=snapshot()
    requests={};tasks={};information={}
    protocol=read(RUN/'protocol.json')
    public={s['key']:s for s in read(ROOT/protocol['public_manifest'])}
    for arm in ('BoundaryRefine','FreeReflect','PrimitiveGiven'):
        folder=(PREFLIGHT if arm!='PrimitiveGiven' else RUN)/arm
        request=read(next((folder/'calls').glob('*/request.json')))
        decoded=unpack(json.loads(request['user_prompt']))
        assert decoded==read(folder/'input.json')
        assert request['system_prompt']==read(folder/'system.json')['system']
        assert not any(public[key]['views'][0]['public']['question'] in json.dumps(decoded,ensure_ascii=False)
                       for key in protocol['transfer_sources'])
        assert not any(public[key]['views'][0]['public']['facts'] in json.dumps(decoded,ensure_ascii=False)
                       for key in protocol['transfer_sources'])
        requests[arm]=request;tasks[arm]=decoded
        information[arm]={'decoded_actual_input_sha256':sha(decoded),'config_sha256':sha(request['config']),
            'output_schema_sha256':sha(request['output_schema']),
            'system_sha256':sha(request['system_prompt']),
            'seed_sha256':sha(decoded.get('actual_seed')),
            'law_sha256':sha(decoded['law_material']),
            'current_feedback_sha256':sha(decoded['old_TRAIN_factual_feedback']),
            'matches_preserved_decoded_input':True,'later_case_texts_and_questions_absent':True}
    assert tasks['BoundaryRefine']==tasks['FreeReflect']
    assert requests['BoundaryRefine']['config']==requests['FreeReflect']['config']
    assert requests['BoundaryRefine']['output_schema']==requests['FreeReflect']['output_schema']
    assert requests['BoundaryRefine']['system_prompt']!=requests['FreeReflect']['system_prompt']
    assert tasks['PrimitiveGiven']['law_material']==tasks['BoundaryRefine']['law_material']
    assert tasks['PrimitiveGiven']['old_TRAIN_factual_feedback']==tasks['BoundaryRefine']['old_TRAIN_factual_feedback']
    assert tasks['PrimitiveGiven']['host_contract']!=tasks['BoundaryRefine']['host_contract']
    observations=[]
    for file in sorted((RUN/'execution').glob('*/*/*/result.json')):
        record=read(file);arm=record['arm'];library=read(RUN/arm/'library.json')
        program=entry_program(library,record['plan']['unit'])
        instrumented,names=instrument_calendar_calls(program)
        bindings={**record['plan']['query_arguments'],**record['case_values']}
        original=trace(program,{'facts':bindings})
        replay=trace(instrumented,{'facts':bindings})
        assert original['result']==replay['result']
        assert replay['result']=={k:record['result'][k] for k in ('value','used_units','open_dependencies')}
        def calendar(execution):
            return [c for c in execution['calls'] if c['function'] in names]
        deletion=[]
        for field in record['case_values']:
            probe=deepcopy(bindings);probe.pop(field)
            try:
                result=trace(instrumented,{'facts':probe})
                if result['result']!=replay['result'] or bool(calendar(result))!=bool(calendar(replay)):
                    deletion.append({'removed_actual_observation':field,'diagnostic_result':result['result'],
                        'calendar_calls':calendar(result),'diagnostic_only_not_a_recovered_prediction':True})
            except ValueError as error:
                deletion.append({'removed_actual_observation':field,'diagnostic_error':str(error),
                    'diagnostic_only_not_a_recovered_prediction':True})
        item={'stage':record['stage'],'arm':arm,'source':record['source'],
            'original_execution_exactly_reproduced':True,'instrumentation_result_identical':True,
            'actual_input_sha256':sha(bindings),'calendar_calls':calendar(replay),
            'deletion_probes':deletion,'original_raw_result_not_rewritten':True}
        observations.append(item)
        immutable_json(OUT/'replay'/record['stage']/arm/file.parent.name/'execution.json',replay)
    assert snapshot()==before
    result={'same_goal_active_incomplete':True,'new_model_requests':0,'ledger_all_tables_unchanged':True,
        'ledger_calls':len(before['calls']),'input_audit':information,
        'matched_pair_actual_tasks_seed_law_feedback_and_config_identical':True,
        'actual_difference_in_matched_pair':'Teacher system recipe only; resulting programs and fact schemas differ. This is a one-draw whole-artifact comparison, not a controlled removal of a distinct implemented learning operator.',
        'third_arm_limitations':['No earlier151 seed-supervision history.',
            'Receives updated host-role-grounding contract while the first two settled teachers saw the earlier contract. All three execute through the same corrected host.'],
        'replications_per_teacher_condition':1,'later_cases':3,
        'new_source_roots_were_acquired_from_supplied_law_before_reading_cases':True,
        'not_independent_evidence_of_learned_operation_transfer_to_unseen_law':True,
        'candidate_and_control_both_implement_raw_observation_computation_refinement':True,
        'cannot_attribute_artifact_score_gap_to_presence_vs_absence_of_refinement':True,
        'selector_was_offline_only_not_a_tested_online_intervention':True,
        'replays':observations,
        'conclusion':'Physical execution, matched pair information and recorded artifact outcomes are verified. No mechanism ablation, stable effect estimate, matched-lifetime third-arm claim, or general direction rejection follows. Retain scores and stop expanding this failed artifact; keep the legal-learning problem fixed while specifying an actual controlled algorithm.'}
    immutable_json(OUT/'comparison_audit.json',result)
    print(json.dumps({'matched_inputs_identical':True,'all12_actual_executions_reproduced':True,
        'actual_calendar_calls_by_arm':{arm:sum(len(x['calendar_calls']) for x in observations if x['arm']==arm)
            for arm in information},'ledger_calls_unchanged':len(before['calls']),'new_model_requests':0},ensure_ascii=False))


if __name__=='__main__':
    run()
