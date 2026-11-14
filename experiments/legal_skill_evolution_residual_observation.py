"""Program-directed factual read versus joint repair of the same learned view.

The existing exact source-absence observation is replayed with an explicit
semantic projection receipt; it is not a fresh model success or an automatic
cross-schema cache. Joint repair receives the same shared learned contract and
original pre-clarification state and may repair all fields in one call.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

import jsonschema

from experiments import legal_skill_evolution_temporal_contract_learning as prior
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import apply_adapter, execute_alternatives
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.literal_facts import literal_bindings
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.kernel_residual_reader import repair_step
from legal_skill_guard.skill_evolution.runtime import render_messages, decoder_schema


ROOT = prior.ROOT
RUN = 'legal_skill_evolution_residual_observation_20261114'
OUT = ROOT / 'artifacts' / RUN
JOINT = '''Re-read the current finite case and repair the supplied factual view.
You have the same complete learned observation contract as the program-directed
method. In this one read you may repair ALL coupled fields. Recheck every prior
null/unknown against the current text, preserving unknown only for actual failed
or ambiguous extraction. Completed finite-text extraction without a matching
statement is an empty record array. Do not infer a real-world negative or invent
an actor, event or ending date. Use the learned source-native event/state forms.
Do not answer the legal claim or change its rule. Return the complete factual
view under the supplied schema and use exact current-case witness quotes.
'''


def prepare():
    if (OUT / 'protocol.json').exists():
        return prior.read(OUT / 'protocol.json')
    parent = prior.read(prior.OUT / 'protocol.json')
    row = next(r for r in prior.read(prior.OUT / 'scored_results.json')['rows']
        if r['arm'] == 'ProgramGuided' and r['source'].split(':')[1].startswith('8175fcb9'))
    kernel = next(k for k in prior.read(prior.OUT / 'kernel_bank.json') if k['name'] == row['kernel'])
    kernel = deepcopy(kernel)
    fields = json.loads(kernel['input_fields_json'])
    for spec in fields.values():
        spec['type'] = prior.direct.nominal_type(spec['type'])
    kernel['input_fields_json'] = json.dumps(fields, ensure_ascii=False)
    contract = next(c for c in prior.read(prior.OUT / 'ProgramGuided/teacher.json')['value']['contracts'] if c['kernel_name'] == row['kernel'])
    case = next(c['source'] for c in prior.read(prior.direct.OUT / 'fixed_development_cases.json') if c['source']['key'] == row['source'])
    packet = {'source': case, 'kernel': kernel, 'contract': contract, 'original_observation': row['observation']}
    before = prior.base.old.rows(); assert not any(r[6] == 'reserved' for r in before)
    immutable_json(OUT / 'packet.json', packet)
    immutable_json(OUT / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in before})
    files = [Path(__file__), *[ROOT / ('legal_skill_guard/skill_evolution/' + n) for n in (
        'kernel_residual.py', 'kernel_residual_worker.py', 'observation_slice.py', 'kernel_residual_reader.py',
        'case_observation_contract.py', 'span_compiler.py', 'span_compiler_worker.py', 'calendar_ops.py', 'clients.py', 'ledger.py')]]
    for f in files:
        dst = OUT / 'source_snapshot' / f.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(f.read_bytes())
    p = {'run_id': RUN, 'same_goal': True, 'goal_complete': False, 'source': row['source'],
        'new_source_or_TEST': False, 'development_mechanism_only': True,
        'shared_learned_view_execution_isolation_not_independent_acquisition': True,
        'new_joint_model_requests_planned': 1, 'program_read_reuses_prior_paid_observation': True,
        'no_fresh_program_read_generation_claim': True, 'kernel_program_sha256': digest(kernel['program']),
        'packet_sha256': digest(packet), 'executor_profile': parent['executor_profile'],
        'source_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
    immutable_json(OUT / 'protocol.json', p)
    return p


def offline(p, packet):
    pub = packet['source']['views'][0]['public']
    old = ROOT / 'artifacts/legal_skill_evolution_missing_event_read_20261114'
    cached_p = prior.read(old / 'protocol.json'); cached = prior.read(old / 'observation.json')
    assert cached_p['source'] == p['source'] and cached_p['facts_sha256'] == digest(pub['facts'])
    assert cached['status'] == 'none_stated' and cached['value'] is None
    def read(action):
        # This is one explicit offline use of a previously checked empty-set
        # factual result, not approximate transport-cache matching. Positive
        # event records with different schemas are not reinterpreted.
        assert action['port'] == 'legal_separation_decrees'
        jsonschema.validate(cached, action['schema'])
        return cached, {'original_physical_call_id': 'legal_skill_evolution_missing_event_read_20261114:source_presence',
            'source_and_full_facts_hash_equal': True, 'same_decree_presence_scope': True,
            'empty_set_projection_has_no_member_or_date_semantics_to_invent': True,
            'new_physical_requests': 0, 'not_fresh_prompt_quality_validation': True}
    result = repair_step(packet['contract'], packet['kernel'], pub, packet['original_observation'], read)
    assert result['read_requested']
    immutable_json(OUT / 'program_directed_replay.json', result)
    print(json.dumps({'selected_port': result['action']['port'], 'source_view_path': result['action']['observation_path'],
        'execution': {'handled': result['execution']['handled'], 'answer': result['execution']['answer']},
        'new_physical_requests': 0}), flush=True)


def joint(p, packet):
    pub = packet['source']['views'][0]['public']
    schema = json.loads(packet['contract']['observation_schema_json'])
    system = JOINT + '\nLearned factual observation instruction:\n' + packet['contract']['observation_prompt']
    task = {'current_case': {k: pub[k] for k in packet['contract']['observation_context_fields']},
        'previous_factual_view': packet['original_observation'],
        'shared_binding_program': packet['contract']['binding_program'],
        'later_source_presence_read_not_supplied': True}
    immutable_json(OUT / 'joint_task.json', task)
    ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': [p['source']], 'dev': [], 'test': []}, binding=digest(p))
    response = FrozenExecutor(ledger, OUT, p['executor_profile']).generate(RUN + ':JointViewRepair',
        source=p['source'], purpose='skill_actor', thinking=False,
        messages=render_messages(system, task, schema), schema=decoder_schema(schema)[0])
    assert response['finish_reason'] == 'stop'
    value = json.loads(response['content']); jsonschema.validate(value, schema)
    grounded = apply_adapter(packet['contract'], packet['kernel'], pub, value,
        literal_context=literal_bindings({'public': pub}))
    result = execute_alternatives(packet['kernel'], grounded)
    ann = prior.read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    view = packet['source']['views'][0]
    immutable_json(OUT / 'joint_result.json', {'observation': value, 'grounded': grounded, 'execution': result,
        'native_score': grade_view(packet['source']['dataset'], view, ann[p['source']][view['id']], result['answer']),
        'logical_extra_reads': 1, 'new_physical_requests': 1, 'goal_complete': False})
    print(json.dumps({'joint_view_execution': {'handled': result['handled'], 'answer': result['answer']}}), flush=True)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['offline', 'joint'])
    phase = parser.parse_args().phase
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        p = prepare()
        for name, h in p['source_sha256'].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == h
        packet = prior.read(OUT / 'packet.json'); assert digest(packet) == p['packet_sha256']
        if phase == 'offline':
            offline(p, packet)
        else:
            joint(p, packet)


if __name__ == '__main__':
    main()
