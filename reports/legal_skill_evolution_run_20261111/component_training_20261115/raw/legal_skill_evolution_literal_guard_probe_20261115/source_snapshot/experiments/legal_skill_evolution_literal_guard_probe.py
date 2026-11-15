"""One paired TRAIN validation of a source-literal generation guard repair.

Existing observations and libraries are retained verbatim. Only the generation
schema and the common source-premise check change. No teacher, DEV or TEST.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

import jsonschema

from experiments import legal_skill_evolution_mixed_component_training as train
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.decoder_constraints import decoding_schema
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.literal_statutory_givens import constrain
from legal_skill_guard.skill_evolution.native_case_encoding import FACTUAL_ENCODING
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.observation_component_library import observation_schema


ROOT = train.ROOT
RUN = 'legal_skill_evolution_literal_guard_probe_20261115'
OUT = ROOT / 'artifacts' / RUN
REPLAY = ROOT / 'artifacts/legal_skill_evolution_observation_TRAIN_replay_20261115'
DB = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
COMPONENTS = {'CoverageRecombine': 'source_economic_legal_ledger_b8',
              'FreeGlobalUpdate': 'explicit_legal_givens'}


def ledger_rows():
    with sqlite3.connect('file:' + str(DB) + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute('select * from calls order by id')]


def material():
    protocol = train.read(train.OUT / 'protocol.json')
    bank = train.actor.acquisition.previous.parent.OUT
    public = {s['key']: s for s in train.read(bank / 'SARA_corrected_TRAIN_views.json')}
    kernels = {r['source']: train.actor.acquisition.current_case_interface(r['kernel'])
               for r in train.read(bank / 'SARA_native_kernel_bank.json')}
    source = next(sid for sid in public if sid.startswith('SARA_v2_Binary:1ff7d9'))
    assert source in protocol['sources'] and public[source]['split'] == 'train'
    checkpoint = train.read(train.OUT / 'B8/checkpoint.json')
    libraries = {arm: train.read(ROOT / checkpoint['libraries'][arm]['path']) for arm in train.ARMS}
    rows = train.read(REPLAY / 'result.json')['rows']
    before = {arm: next(r for r in rows if r['candidate'] == arm and r['source'] == source)
              for arm in train.ARMS}
    return protocol, public, kernels, source, libraries, before


def offline():
    protocol, public, kernels, source, libraries, before = material()
    sid_valid = next(s for s in public if s.startswith('SARA_v2_Binary:a519'))
    saved = train.read(REPLAY / 'result.json')['rows']
    cases = []
    for arm, cid in COMPONENTS.items():
        component = next(c for c in libraries[arm]['components'] if c['id'] == cid)
        original = observation_schema(libraries[arm], [cid])
        revised = constrain(original, public[source]['views'][0]['public'], kernels[source])
        value = {cid: before[arm]['observation'][cid]}
        assert jsonschema.Draft202012Validator(original).is_valid(value)
        assert not jsonschema.Draft202012Validator(revised).is_valid(value)
        matches = [train.read(p) for p in (train.OUT / 'component_reads').glob('*.json')
                   if train.read(p)['source'] == source and train.read(p)['value'] == value]
        assert matches
        raw = train.read(train.OUT / 'raw_responses' / (matches[0]['wire_input_sha256'] + '.json'))
        cases.append({'source': source, 'arm': arm, 'component_id': cid,
            'old_raw_content': raw['content'], 'old_schema': original, 'schema': revised,
            'wire_schema': decoding_schema(revised)[0], 'expected_new_host_valid': False,
            'raw_value_not_repaired_or_credited_as_new_generation': True})
    arm, cid = 'CoverageRecombine', COMPONENTS['CoverageRecombine']
    row = next(r for r in saved if r['source'] == sid_valid and r['candidate'] == arm)
    value = {cid: row['observation'][cid]}
    revised = constrain(observation_schema(libraries[arm], [cid]), public[sid_valid]['views'][0]['public'], kernels[sid_valid])
    jsonschema.validate(value, revised)
    paid = next(train.read(p) for p in (train.OUT / 'component_reads').glob('*.json')
                if train.read(p)['source'] == sid_valid and train.read(p)['value'] == value)
    raw = train.read(train.OUT / 'raw_responses' / (paid['wire_input_sha256'] + '.json'))
    cases.append({'source': sid_valid, 'arm': arm, 'component_id': cid,
        'old_raw_content': raw['content'], 'schema': revised,
        'wire_schema': decoding_schema(revised)[0], 'expected_new_host_valid': True})
    immutable_json(OUT / 'offline_cases.json', {'cases': cases, 'new_model_calls': 0,
        'rejected_raw_outputs_retained': True, 'not_new_method_success': True})
    files = [Path(__file__), Path(train.actor.__file__)]
    files += sorted((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py'))
    files += [train.OUT / 'protocol.json', train.OUT / 'B8/checkpoint.json', REPLAY / 'result.json']
    files += [ROOT / checkpoint['path'] for checkpoint in train.read(train.OUT / 'B8/checkpoint.json')['libraries'].values()]
    bound = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    immutable_json(OUT / 'protocol.json', {'same_goal': True, 'run_id': RUN,
        'sources': protocol['sources'], 'selected_original_TRAIN_source': source,
        'component_one_read_per_arm': COMPONENTS, 'libraries': {a: digest(l) for a, l in libraries.items()},
        'executor_profile': protocol['executor_profile'], 'teacher_calls': 0,
        'other_exact_paid_TRAIN_reads_reused': True, 'DEV_TEST_accessed': False,
        'changed_problem': 'Source literal-given guards also restrict generation; original semantic checks remain.',
        'source_sha256': bound, 'goal_complete': False})
    for path in files:
        target = OUT / 'source_snapshot' / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert target.read_bytes() == path.read_bytes()
        else:
            target.write_bytes(path.read_bytes())
    print(json.dumps({'offline_real_failure_cases': len(cases), 'new_model_calls': 0}), flush=True)


def run():
    protocol = train.read(OUT / 'protocol.json')
    assert train.read(OUT / 'offline_grammar.json')['all_expected_outcomes']
    for path, sha in protocol['source_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha, path
    _, public, kernels, source, libraries, before = material()
    rows_before = ledger_rows()
    assert not any(r['status'] == 'reserved' for r in rows_before)
    immutable_json(OUT / 'ledger_before.json', {r['id']: digest(tuple(r.values())) for r in rows_before})
    for path in (REPLAY / 'component_reads').glob('*.json'):
        immutable_json(OUT / 'component_reads' / path.name, train.read(path))
    ledger = EvolutionLedger(DB, run_id=RUN,
        sources={'train': protocol['sources'], 'dev': [], 'test': []}, binding=digest(protocol))
    client = FrozenExecutor(ledger, OUT, protocol['executor_profile'])
    client.exact_replay_roots = [OUT]
    actor_protocol = {'executor_profile': protocol['executor_profile'],
        'shared_native_event_encoding': FACTUAL_ENCODING, 'shared_public_pure_calculation': True}
    summaries = {}
    for arm in train.ARMS:
        row = train.actor.execute_one(client, actor_protocol, arm, libraries[arm], source,
            kernels[source], public[source], 'same_paid_TRAIN_case', purpose='skill_actor')
        immutable_json(OUT / arm / 'after.json', row)
        cid = COMPONENTS[arm]
        summaries[arm] = {
            'before_handled': before[arm]['execution']['handled'], 'after_handled': row['execution']['handled'],
            'before_unresolved': before[arm].get('grounded', {}).get('unresolved'),
            'after_unresolved': row.get('grounded', {}).get('unresolved'), 'error': row.get('error'),
            'before_given_records': before[arm]['observation'][cid]['views'][0]['exact_givens'],
            'after_given_records': row.get('observation', {}).get(cid, {}).get('views', [{}])[0].get('exact_givens'),
            'source_guard_repair_not_independent_contribution': True}
    after = ledger_rows()
    saved = train.read(OUT / 'ledger_before.json')
    assert all(digest(tuple(r.values())) == saved[r['id']] for r in after if r['id'] in saved)
    added = [r for r in after if r['id'] not in saved]
    assert all(r['role'] == 'executor' and r['id'].startswith(RUN + ':') for r in added)
    immutable_json(OUT / 'result.json', {'summary': summaries, 'new_requests': added,
        'all_previous_ledger_rows_unchanged': True, 'teacher_calls': 0,
        'libraries_unchanged': True, 'source': source, 'no_DEV_TEST_or_native_answers_in_reader': True,
        'not_a_complete_method_validation': True, 'goal_complete': False})
    print(json.dumps({'summary': summaries, 'new_executor_requests': len(added)}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('offline', 'run'))
    args = parser.parse_args()
    if args.phase == 'offline':
        offline()
    else:
        with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            run()
