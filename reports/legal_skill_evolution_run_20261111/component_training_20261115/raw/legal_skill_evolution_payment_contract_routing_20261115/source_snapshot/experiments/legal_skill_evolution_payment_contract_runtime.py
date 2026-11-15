"""Frozen runtime for the acquired payment/service refinement and controls."""
import argparse
import ast
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

import jsonschema

from experiments import legal_skill_evolution_payment_contract_refinement as generation
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.source_effect_update import function_update
from legal_skill_guard.skill_evolution.span_compiler import validate_procedure

ROOT = generation.ROOT
RUN = 'legal_skill_evolution_payment_contract_routing_20261115'
OUT = ROOT / 'artifacts' / RUN
runtime = generation.runtime
read = generation.read


def lower_services(program):
    """Lower the actual pure JSON DFS without permitting recursive execution."""
    tree = ast.parse(program)
    nested = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    if len(nested) == len(tree.body):
        return program
    original = next(n for n in tree.body if n.name == '_services')
    canonical = json.loads(read(generation.OUT / 'FreeTeacher/teacher.json')['value']['base_components'][0]['contract_json'])
    reference = next(n for n in ast.parse(canonical['read_constraint_program']).body if n.name == '_services')
    assert ast.dump(original) == ast.dump(reference), 'Only the reviewed actual collector is lowered'
    replacement = '''def _services(value):
    result=[]
    todo=[value]
    while todo:
        node=todo.pop()
        if isinstance(node,list):
            todo.extend(node[::-1])
            continue
        if not isinstance(node,dict):
            continue
        event=node.get('actual_event_id') or node.get('event_id') or node.get('source_key')
        row=(event,node.get('worker'),node.get('employer'),node.get('kind') or node.get('service_kind'))
        if all(isinstance(x,str) and x for x in row) and row not in result:
            result.append(row)
        rows=node.get('facts')
        if isinstance(rows,list):
            events={}
            for fact in rows:
                if not isinstance(fact,dict) or not isinstance(fact.get('arguments'),list):
                    continue
                predicate=fact.get('predicate')
                args=fact.get('arguments')
                if len(args)==1 and predicate=='service_':
                    events.setdefault(args[0],{})
                elif len(args)==2:
                    slot=events.setdefault(args[0],{})
                    if predicate=='agent_': slot['worker']=args[1]
                    elif predicate=='patient_': slot['employer']=args[1]
                    elif predicate in ('purpose_','type_'): slot['kind']=args[1]
            for key,slot in events.items():
                row=(key,slot.get('worker'),slot.get('employer'),slot.get('kind'))
                if all(isinstance(x,str) and x for x in row) and row not in result:
                    result.append(row)
        todo.extend([child for child in list(node.values())[::-1] if isinstance(child,(dict,list))])
    return result
'''
    lowered = function_update(program, [replacement])
    validate_procedure(lowered, allow_helpers=True)
    # Execute only the reviewed pure collector, with the same restricted
    # builtins, to verify child order, duplicates and source-key preservation.
    probes = [None, {}, [], [{'event_id': 'event', 'worker': 'person', 'employer': 'org', 'kind': 'work'}],
        {'observed_related_source_events': [{'facts': [
            {'predicate': 'service_', 'arguments': ['service0']},
            {'predicate': 'agent_', 'arguments': ['service0', 'worker']},
            {'predicate': 'patient_', 'arguments': ['service0', 'employer']},
            {'predicate': 'type_', 'arguments': ['service0', 'work']}]}]},
        {'nested': [{'actual_event_id': 'first', 'worker': 'a', 'employer': 'b', 'kind': 'work'},
                    {'more': [{'actual_event_id': 'second', 'worker': 'c', 'employer': 'd', 'kind': 'service'}]}]}]
    outputs = []
    for source in (ast.unparse(original), replacement):
        scope = {'__builtins__': {'all': all, 'isinstance': isinstance, 'str': str, 'list': list,
                                  'dict': dict, 'len': len}}
        exec(compile(source, '<reviewed-pure-collector>', 'exec'), scope)
        outputs.append([scope['_services'](value) for value in probes])
    assert outputs[0] == outputs[1]
    immutable_json(OUT / 'offline_adapter_lowering' / (digest(program) + '.json'),
        {'original_program': program, 'lowered_program': lowered, 'collector_probes': probes,
         'original_outputs': outputs[0], 'lowered_outputs': outputs[1],
         'original_and_lowered_identical': True, 'new_model_calls': 0,
         'source_semantics_and_other_functions_unchanged': True})
    return lowered


def prepare():
    old = read(generation.OUT / 'protocol.json')
    for path, sha in old['source_sha256'].items():
        assert hashlib.sha256((generation.OUT / 'source_snapshot' / path).read_bytes()).hexdigest() == sha
    assert all((generation.OUT / arm / 'teacher.json').exists() for arm in ('Method', 'FreeTeacher'))
    p = deepcopy(old)
    p.update(run_id=RUN, generation_run=generation.RUN,
        generation_protocol_sha256=digest(old),
        runtime_change='Apply the same strict nominal binder to payment contracts that also enumerate plan events')
    immutable_json(OUT / 'TRAIN_grading.json', read(generation.OUT / 'TRAIN_grading.json'))
    for origin in (generation.OUT, ROOT / 'artifacts/legal_skill_evolution_payment_contract_runtime_20261115'):
        for channel in ('component_reads', 'relation_reads'):
            for file in (origin / channel).glob('*.json'):
                target=OUT / channel / file.name
                if not target.exists():immutable_json(target, read(file))
    files = [Path(__file__), Path(generation.__file__), Path(runtime.__file__),
             generation.OUT / 'common_library.json', OUT / 'TRAIN_grading.json']
    files += [generation.OUT / arm / 'teacher.json' for arm in ('Method', 'FreeTeacher')]
    files += sorted((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py'))
    p['source_sha256'] = {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    immutable_json(OUT / 'protocol.json', p)
    for file in files:
        target = OUT / 'source_snapshot' / file.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(file.read_bytes())
    libraries = generation.candidates(p, program_transform=lower_services)
    for name, library in libraries.items():
        immutable_json(OUT / 'candidate_libraries' / (name + '.json'), library)
    immutable_json(OUT / 'offline_proposal_validation.json', {'candidates': sorted(libraries),
        'new_model_calls': 0, 'not_whole_case_or_semantic_success': True})
    print(json.dumps({'prepared': RUN, 'candidates': sorted(libraries)}), flush=True)


def protocol():
    p = read(OUT / 'protocol.json')
    for file, sha in p['source_sha256'].items():
        assert hashlib.sha256((ROOT / file).read_bytes()).hexdigest() == sha, file
    return p


def fixed_generic(client, p, sid, source, kernel):
    target = OUT / 'fixed_generic' / (digest(sid) + '.json')
    if target.exists():
        return read(target)
    public = source['views'][0]['public']
    original = runtime.generic_schema(kernel, public)
    messages = runtime.render_messages(runtime.GENERIC_PROMPT + '\nShared native event meanings: ' + p['shared_native_event_encoding'],
        {'current_case': {k: public[k] for k in ('facts', 'question')},
         'current_legal_query': {k: kernel[k] for k in ('native_query', 'query_clause')}}, original)
    row = {'source': sid, 'condition': 'unchanged_fixed_generic_native_event_view', 'fallback': False}
    try:
        wire, _ = runtime.decoding_schema(original)
        assert client.tokenize(messages, thinking=False)['count'] + p['executor_profile']['max_tokens'] <= p['executor_profile']['context_tokens']
        response = client.generate(RUN + ':fixed_generic:' + digest(sid), source=sid,
            purpose='skill_actor', messages=messages, thinking=False, schema=wire)
        immutable_json(OUT / 'fixed_generic_raw' / (digest(sid) + '.json'), response)
        assert response['finish_reason'] == 'stop', 'Incomplete fixed generic observation'
        observation = json.loads(response['content'])
        jsonschema.validate(observation, original)
        grounded = runtime.generic_lower(observation, kernel, public)
        execution = runtime.execute_alternatives(kernel, grounded)
        reviewed = runtime.review(sid, grounded, complete_families=[n for n, a in kernel['fact_arities'].items() if a == 1])
        grading = read(OUT / 'TRAIN_grading.json')
        score = runtime.grade_view(source['dataset'], source['views'][0], grading[sid][source['views'][0]['id']], execution['answer'])
        row.update(observation=observation, grounded=grounded, execution=execution,
            source_review=reviewed, native_score=score,
            core_correct=execution['handled'] and score['correct'] and not reviewed['failures'],
            receipt={k: response.get(k) for k in ('usage', 'elapsed_seconds', 'finish_reason', 'cache_hit', 'reused_physical_call_id')})
    except Exception as error:
        row.update(error=type(error).__name__ + ': ' + str(error), core_correct=False)
    immutable_json(target, row)
    return row


def execute():
    p = protocol()
    public, kernels = runtime.previous.data()
    libraries = {n: read(OUT / 'candidate_libraries' / (n + '.json'))
                 for n in read(OUT / 'offline_proposal_validation.json')['candidates']}
    ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': p['sources'], 'dev': [], 'test': []}, binding=digest(p))
    client = FrozenExecutor(ledger, OUT, p['executor_profile'])
    client.exact_replay_roots = [runtime.OUT, generation.latest.OUT,
        ROOT / 'artifacts/legal_skill_evolution_generic_view_train_20261113']
    acquired, selected = [], {}
    for name, library in libraries.items():
        rows = [runtime.run_case(client, p, name, library, sid, public[sid]['views'][0]['public'], kernels[sid])
                for sid in p['acquisition_sources']]
        acquired.append({'candidate': name, 'rows': rows})
    for arm in ('Method', 'FreeTeacher'):
        best = min((v for v in acquired if v['candidate'].startswith(arm + '/')),
            key=lambda v: (-sum(r['core_correct'] for r in v['rows']),
                sum(r['source_failures'] for r in v['rows']),
                sum(x.get('elapsed_seconds') or 0 for r in v['rows'] for x in r['reads']), v['candidate']))
        selected[arm] = best['candidate']
    immutable_json(OUT / 'selected_before_reuse.json', {'selected': selected, 'acquisition_only': True})
    reuse = [runtime.run_case(client, p, name, libraries[name], sid, public[sid]['views'][0]['public'], kernels[sid])
             for name in selected.values() for sid in p['fixed_reuse_sources']]
    ordinary = [runtime.run_case(client, p, selected['Method'], libraries[selected['Method']], sid,
        public[sid]['views'][0]['public'], kernels[sid], policy='ordinary') for sid in p['fixed_reuse_sources']]
    generic = [fixed_generic(client, p, sid, public[sid], kernels[sid])
               for sid in p['acquisition_sources'] + p['fixed_reuse_sources']]
    immutable_json(OUT / 'result.json', {'acquisition': acquired, 'selected': selected,
        'fixed_reuse': reuse, 'same_contract_ordinary_reuse': ordinary, 'fixed_generic': generic,
        'goal_complete': False, 'DEV_TEST_loaded': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'execute'))
    args = parser.parse_args()
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        {'prepare': prepare, 'execute': execute}[args.phase]()
