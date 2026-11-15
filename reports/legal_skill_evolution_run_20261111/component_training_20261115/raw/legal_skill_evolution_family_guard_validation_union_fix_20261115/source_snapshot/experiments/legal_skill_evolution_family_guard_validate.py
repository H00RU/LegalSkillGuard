"""Validate learned family repairs, then one fixed TRAIN reuse and ablation.

No new source, teacher or DEV access. Reusing unchanged observations is explicit
incremental execution, never a claim of a newly generated whole-case response.
"""
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

import jsonschema

from experiments import legal_skill_evolution_family_source_guard as acquisition
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import execute_alternatives, validate_adapter
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.decoder_constraints import decoding_schema
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.literal_statutory_givens import constrain
from legal_skill_guard.skill_evolution.native_case_encoding import FACTUAL_ENCODING
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.observation_component_library import component_value, convert, observation_schema, validate
from legal_skill_guard.skill_evolution.runtime import render_messages

train = acquisition.train
ROOT = train.ROOT
OUT = ROOT / 'artifacts/legal_skill_evolution_family_guard_validation_union_fix_20261115'
RUN = OUT.name
CID = acquisition.COMPONENT


def read(path):
    return train.read(path)


def source_check(sid, parts):
    failures = []
    for part in parts:
        facts = part['facts']
        if sid.startswith('SARA_v2_Binary:1ff7'):
            forbidden = {'son_', 'daughter_', 'father_', 'mother_', 'brother_', 'sister_', 'sibling_', 'birth_', 'residence_'}
            if any(f['predicate'] in forbidden for f in facts):
                failures.append('Marriage, income and separate returns do not establish kinship, residence or birth')
        if sid.startswith(('SARA_v2_Binary:a519', 'SARA_v2_Binary:5c29')):
            def has(predicate, args):
                return {'predicate': predicate, 'arguments': args} in facts
            son_pairs = []
            for f in facts:
                if f['predicate'] == 'son_':
                    event = f['arguments'][0]
                    son_pairs += [(a['arguments'][1], b['arguments'][1]) for a in facts for b in facts
                        if a['predicate'] == 'agent_' and b['predicate'] == 'patient_'
                        and a['arguments'][0] == b['arguments'][0] == event]
            expected = {('Bob', 'Alice'), ('Charlie', 'Bob')} if sid.startswith('SARA_v2_Binary:a519') else {('Bob', 'Alice')}
            if not expected <= set(son_pairs):
                failures.append('Explicit original source son roles omitted or reversed')
    return failures


def material():
    protocol = read(acquisition.OUT / 'protocol.json')
    bank = train.actor.acquisition.previous.parent.OUT
    public = {s['key']: s for s in read(bank / 'SARA_corrected_TRAIN_views.json')}
    kernels = {r['source']: train.actor.acquisition.current_case_interface(r['kernel'])
        for r in read(bank / 'SARA_native_kernel_bank.json')}
    cp = read(train.OUT / 'B8/checkpoint.json')
    bases = {a: read(ROOT / cp['libraries'][a]['path']) for a in train.ARMS}
    return protocol, public, kernels, bases


def prepare():
    protocol, public, kernels, bases = material()
    bank, rejected = {}, []
    task = read(acquisition.OUT / 'teacher_task.json')
    for arm in train.ARMS:
        current = next(c for c in bases[arm]['components'] if c['id'] == CID)
        bank[arm + '/retained'] = bases[arm]
        response = read(acquisition.OUT / arm / 'teacher.json')
        for i, edit in enumerate(response['value']['candidates']):
            name = arm + '/' + str(i)
            try:
                assert edit['id'] == CID, 'An edit must target the actual family component'
                assert edit['parent_component_hash'] in set(task['actual_parent_hash_by_arm'].values()), 'Parent is not an actual supplied component'
                assert bases['CoverageRecombine']['shared_helpers'] == bases['FreeGlobalUpdate']['shared_helpers'], 'Cross-parent reuse requires identical actual helper semantics'
                assert set(edit['error_feedback_ids']) <= set(task['error_feedback_by_id']), 'Unknown error-feedback identity'
                validate_adapter(bases[arm]['shared_helpers'] + '\n\n' + edit['conversion_program'],
                    excluded_source_ids=protocol['sources'])
                library = deepcopy(bases[arm])
                index = next(i for i, c in enumerate(library['components']) if c['id'] == CID)
                library['components'][index].update(deepcopy(edit))
                validate(library, next(iter(kernels.values())))
                bank[name] = library
            except (AssertionError, ValueError, KeyError, SyntaxError, jsonschema.SchemaError) as e:
                rejected.append({'candidate': name, 'error': str(e)})
    files = []
    for name, library in bank.items():
        path = OUT / 'candidate_libraries' / (name + '.json')
        immutable_json(path, library)
        files.append(path)
    wire_cases = []
    for name, library in bank.items():
        for sid in protocol['current_repair_acquisition'] + protocol['fixed_reuse_excluded_from_this_task']:
            schema = constrain(observation_schema(library, [CID]), public[sid]['views'][0]['public'], kernels[sid])
            jsonschema.Draft202012Validator.check_schema(schema)
            wire_cases.append({'candidate': name, 'source': sid, 'wire_schema': decoding_schema(schema)[0]})
    immutable_json(OUT / 'wire_cases.json', {'cases': wire_cases, 'new_model_calls': 0})
    files.append(OUT / 'wire_cases.json')
    files += [Path(__file__), acquisition.OUT / 'protocol.json', acquisition.OUT / 'teacher_task.json']
    files += [acquisition.OUT / arm / 'teacher.json' for arm in train.ARMS]
    files += sorted((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py'))
    result = {'run_id': RUN, 'same_goal': True, 'acquisition_sources': protocol['current_repair_acquisition'],
        'fixed_reuse_sources': protocol['fixed_reuse_excluded_from_this_task'],
        'sources': protocol['sources'], 'executor_profile': protocol['executor_profile'],
        'candidates': list(bank), 'rejected': rejected, 'teacher_calls': 0,
        'selected_component_only_then_same_component_compiler_ablation': True,
        'full_case_other_observations_reused_not_regenerated': True,
        'partial_source_checks_not_full_semantic_certification': True,
        'original_B8_exposure_not_a_new_blind_split': True, 'DEV_TEST_accessed': False,
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        'goal_complete': False}
    immutable_json(OUT / 'protocol.json', result)
    for path in files:
        target = OUT / 'source_snapshot' / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(path.read_bytes())
    return result, bank, public, kernels


def uncompiled_read(client, protocol, library, sid, source, kernel):
    target = OUT / 'same_component_uncompiled.json'
    if target.exists():
        return read(target)
    component = next(c for c in library['components'] if c['id'] == CID)
    original = observation_schema(library, [CID])
    schema = constrain(original, source['views'][0]['public'], kernel, source_tokens=False)
    projected = constrain(original, source['views'][0]['public'], kernel)
    if digest(schema) == digest(projected):
        row = {'dispatched': False, 'reason': 'No acquired source-token constraint engaged'}
    else:
        public = source['views'][0]['public']
        prompt = component['prompt'] + '\nShared native event meanings: ' + FACTUAL_ENCODING
        task = {'current_case': {k: public[k] for k in ('facts', 'question')},
            'current_legal_query': {k: kernel[k] for k in ('native_query', 'query_clause')},
            'component_meanings': {CID: component['meaning']}}
        messages = render_messages(prompt, task, schema)
        assert client.tokenize(messages, thinking=False)['count'] + client.config['max_tokens'] <= client.config['context_tokens']
        response = client.generate(RUN + ':same_contract_without_source_compilation:' + sid,
            source=sid, purpose='skill_actor', thinking=False, messages=messages,
            schema=decoding_schema(schema)[0])
        row = {'dispatched': True, 'source': sid, 'same_library_hash': digest(library),
            'same_prompt_and_case_only_source_projection_removed': True,
            'finish_reason': response['finish_reason']}
        try:
            assert response['finish_reason'] == 'stop'
            value = json.loads(response['content'])
            jsonschema.validate(value, original)
            parts = [component_value(library, component, kernel, public, view) for view in value[CID]['views']]
            row.update(value=value, parts=parts, source_failures=source_check(sid, parts),
                complete_alternatives=all(p['complete'] for p in parts))
        except (AssertionError, ValueError, jsonschema.ValidationError) as error:
            row['error'] = type(error).__name__ + ': ' + str(error)
    immutable_json(target, row)
    return row


def whole_case_results(selected, bank, family_results, public, kernels):
    replay = read(ROOT / 'artifacts/legal_skill_evolution_observation_TRAIN_replay_20261115/result.json')['rows']
    grading = read(train.actor.acquisition.previous.parent.PREPARED / 'grading.json')
    output = []
    for arm, name in selected.items():
        library = bank[name]
        for family in family_results[name]:
            sid = family['source']
            if sid.startswith('SARA_v2_Binary:1ff7'):
                before = read(ROOT / 'artifacts/legal_skill_evolution_literal_guard_probe_20261115' / arm / 'after.json')
            else:
                before = next(r for r in replay if r['candidate'] == arm and r['source'] == sid)
            observation = deepcopy(before['observation'])
            observation[CID] = family['value'][CID]
            grounded = convert(library, before['plan']['component_ids'], kernels[sid],
                public[sid]['views'][0]['public'], observation)
            execution = execute_alternatives(kernels[sid], grounded)
            row = train.scored({**before, 'candidate': name, 'grounded': grounded,
                'execution': execution, 'observation': observation}, public, grading)
            output.append({'arm': arm, 'source': sid, 'selected': name,
                'before_execution': before['execution'], 'after': row,
                'incremental_family_read_plus_unchanged_paid_other_components': True,
                'not_a_new_whole_case_read_or_blind_evaluation': True})
    immutable_json(OUT / 'incremental_whole_cases.json', {'rows': output,
        'native_answers_scoring_only_after_execution': True, 'goal_complete': False})


def evaluate(client, protocol, library, name, sid, source, kernel):
    path = OUT / 'family_results' / name / (digest(sid) + '.json')
    if path.exists():
        return read(path)
    component = next(c for c in library['components'] if c['id'] == CID)
    value, receipt = train.actor.read_component(client, {'executor_profile': protocol['executor_profile'],
        'shared_native_event_encoding': FACTUAL_ENCODING}, sid, component, kernel,
        source['views'][0]['public'], purpose='skill_actor')
    parts = [component_value(library, component, kernel, source['views'][0]['public'], view)
             for view in value[CID]['views']]
    result = {'source': sid, 'candidate': name, 'value': value, 'receipt': receipt,
        'parts': parts, 'source_failures': source_check(sid, parts),
        'complete_alternatives': all(p['complete'] for p in parts),
        'no_native_answer_supplied': True, 'not_full_case_execution': True}
    immutable_json(path, result)
    return result


def main():
    protocol = read(OUT / 'protocol.json')
    assert read(OUT / 'offline_grammar_ready.json')['all_compiled']
    for path, sha in protocol['source_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha, path
    _, public, kernels, bases = material()
    bank = {name: read(OUT / 'candidate_libraries' / (name + '.json')) for name in protocol['candidates']}
    ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': protocol['sources'], 'dev': [], 'test': []}, binding=digest(protocol))
    client = FrozenExecutor(ledger, OUT, protocol['executor_profile'])
    for cache in (ROOT / 'artifacts/legal_skill_evolution_observation_TRAIN_replay_20261115/component_reads',
                  ROOT / 'artifacts/legal_skill_evolution_family_guard_validation_20261115/component_reads'):
        for path in cache.glob('*.json'):
            immutable_json(OUT / 'component_reads' / path.name, read(path))
    results = {}
    for name, library in bank.items():
        results[name] = [evaluate(client, protocol, library, name, sid, public[sid], kernels[sid])
            for sid in protocol['acquisition_sources']]
    selected = {}
    for arm in train.ARMS:
        names = [n for n in bank if n.startswith(arm + '/')]
        name = min(names, key=lambda n: (sum(len(r['source_failures']) for r in results[n]),
            sum(not r['complete_alternatives'] for r in results[n]), n != arm + '/retained', n))
        selected[arm] = name
        for sid in protocol['fixed_reuse_sources']:
            evaluate(client, protocol, bank[name], name, sid, public[sid], kernels[sid])
    immutable_json(OUT / 'selected.json', {'selected': selected,
        'acquisition_scores': {n: {'source_failures': sum(len(r['source_failures']) for r in rows),
            'incomplete': sum(not r['complete_alternatives'] for r in rows)} for n, rows in results.items()},
        'reuse_not_used_for_selection': True, 'goal_complete': False})
    whole_case_results(selected, bank, results, public, kernels)
    method = selected['CoverageRecombine']
    acquisition_rows = results[method]
    if all(not r['source_failures'] and r['complete_alternatives'] for r in acquisition_rows):
        sid = next(s for s in protocol['acquisition_sources'] if s.startswith('SARA_v2_Binary:1ff7'))
        uncompiled_read(client, protocol, bank[method], sid, public[sid], kernels[sid])
    print(json.dumps({'selected': selected}), flush=True)


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'prepare':
        p, _, _, _ = prepare()
        print(json.dumps({'candidates': p['candidates'], 'rejected': p['rejected']}), flush=True)
    else:
        with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            main()
