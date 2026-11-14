"""Matched residual/ordinary reads on subsequent real TRAIN cases.

Only the method's one frozen pre-update contract is compared. Eligibility never
uses the label. Invalid initial bindings, unsupported traces, native mistakes,
and already handled cases remain distinct; no synthetic obstruction is added.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_mixed_case_actor as actor
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_read_comparison import compare_reads
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema, render_messages


ROOT = actor.ROOT
RUN = 'legal_skill_evolution_mixed_residual_reads_20261114'
OUT = ROOT / 'artifacts' / RUN
read = actor.read


def prepare():
    path = OUT / 'protocol.json'
    if path.exists():
        return read(path)
    prior = actor.prepare()
    files = [__file__, str(ROOT / 'legal_skill_guard/skill_evolution/case_read_comparison.py'),
        str(ROOT / 'legal_skill_guard/skill_evolution/conversion_residual.py'),
        str(ROOT / 'legal_skill_guard/skill_evolution/conversion_residual_worker.py')]
    protocol = {'run_id': RUN, 'sources': prior['sources'], 'batches': prior['batches'],
        'executor_profile': prior['executor_profile'], 'same_goal': True,
        'current_method': 'ProgramGuided', 'same_frozen_contract_and_initial_observation': True,
        'one_matched_read_opportunity_per_policy': True, 'eligibility_uses_label': False,
        'source_sha256': {str(Path(p).resolve().relative_to(ROOT)):
            hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in files},
        'native_backend_trace_is_actual_conversion_stage_not_Prolog_proof': True,
        'TEST_opened': False, 'thinking': False, 'goal_complete': False}
    immutable_json(path, protocol)
    return protocol


def run(batch):
    protocol = prepare()
    for name, expected in protocol['source_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': protocol['sources'], 'dev': [], 'test': []}, binding=digest(protocol))
    client = FrozenExecutor(ledger, OUT, protocol['executor_profile'])
    public = {s['key']: s for s in read(actor.learned.parent.OUT / 'SARA_corrected_TRAIN_views.json')}
    kernels = {r['source']: r['kernel'] for r in read(actor.learned.parent.OUT / 'SARA_native_kernel_bank.json')}
    library = read(actor.learned.OUT / f'B{batch-1}/ProgramGuided/library.json')
    components = {c['id']: c for c in library['components']}
    paths = []
    for sid in [k for k in protocol['batches'][batch-1] if k in public]:
        target = OUT / f'B{batch}/' / (digest(sid) + '.json')
        paths.append(target)
        if target.exists():
            continue
        original = read(actor.learned.OUT / f'B{batch}/ProgramGuided/initial_results' / (digest(sid) + '.json'))
        ids = original['actual_component_ids']
        observation = original.get('observation')
        if 'grounded' not in original:
            immutable_json(target, {'source': sid, 'batch': batch, 'eligible': False,
                'reason': 'Invalid initial binding is a separate observation/conversion failure',
                'original_error': original.get('error'), 'original_row_sha256': digest(original),
                'new_model_calls': 0, 'not_a_residual_success': True})
            continue
        schema = record_schema({cid: json.loads(components[cid]['schema_json']) for cid in ids})
        contract = {'binding_program': library['binding_program'], 'observation_schema_json': json.dumps(schema),
            'observation_prompt': '\n\n'.join(components[cid]['prompt'] for cid in ids), 'requires_neural_read': bool(ids)}
        pub, kernel = public[sid]['views'][0]['public'], kernels[sid]

        def dispatch(policy, action):
            task = {'current_case': {k: pub[k] for k in ('facts', 'question')},
                'current_legal_query': {k: kernel[k] for k in ('native_query', 'query_clause')},
                'current_observation': observation, 'existing_unresolved_messages': original['grounded']['unresolved']}
            messages = render_messages(action['prompt'], task, action['schema'])
            count = client.tokenize(messages, thinking=False)['count']
            if count + protocol['executor_profile']['max_tokens'] > protocol['executor_profile']['context_tokens']:
                raise ValueError('Complete matched read exceeds fixed context; no truncation')
            response = client.generate(RUN + f':B{batch}:' + policy + ':' + sid,
                source=sid, purpose='skill_actor', thinking=False, messages=messages,
                schema=decoder_schema(action['schema'])[0])
            if response['finish_reason'] != 'stop':
                raise ValueError('Matched read truncated: ' + response['finish_reason'])
            return json.loads(response['content']), {k: response[k]
                for k in ('usage', 'elapsed_seconds', 'finish_reason')}

        result = compare_reads(contract, kernel, pub, deepcopy(observation), dispatch)
        immutable_json(target, {'source': sid, 'batch': batch, 'original_row_sha256': digest(original),
            'library_sha256': digest(library), **result, 'native_score_does_not_certify_factual_semantics': True})
        print(json.dumps({'matched_read_case': sid, 'eligible': result['eligible'],
            'policies': {k: {'handled': v['execution']['handled'], 'physical_reads': len(v['calls'])}
                for k, v in result['policies'].items()}}), flush=True)
    # Only after both policies' immutable execution records exist, load TRAIN
    # grading. No score or preferred policy enters eligibility or dispatch.
    grading = read(actor.learned.parent.PREPARED / 'grading.json')
    scored = []
    for path in paths:
        value = read(path)
        source = public[value['source']]
        row = {'source': value['source'], 'eligible': value['eligible'], 'policies': {}}
        for policy, outcome in value.get('policies', {}).items():
            row['policies'][policy] = {'execution': outcome['execution'],
                'native_score': grade_view(source['dataset'], source['views'][0],
                    grading[source['key']][source['views'][0]['id']], outcome['execution']['answer']),
                'physical_reads': len(outcome['calls']), 'error': outcome.get('error')}
        scored.append(row)
    immutable_json(OUT / f'B{batch}/scored_results.json', {'rows': scored,
        'goal_complete': False, 'not_an_innovation_certificate': True})
