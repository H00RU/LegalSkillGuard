"""Test cross-hypothesis evidence under a scope-preserving change to a defined term."""

import argparse
import base64
from bisect import bisect_right
from collections import Counter
from copy import deepcopy
import fcntl
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from statistics import mean

import jsonschema

from experiments.convergence_formal_train_fit import ORDINARY, pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_cni_linked_evidence import DATASET, REVIEWS, materials as source_reviews
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from legal_skill_guard.paired_interfaces.control_answers import decode_native, source_bundle, wire_schema
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.client import request_payload
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision5_CNI_definition_alias_20261119'
POINTER = HANDOFF / 'revision5_CNI_definition_alias_current.json'
TERM = 'Representatives'
ALIAS = 'Review Participants'
TASKS = ('nda-5', 'nda-7')
ROLES = ('incumbent', 'candidate')


def renamed_document(text, spans, definition, operative):
    if ALIAS in text or not re.search(r'(?<!\w)Representatives(?!\w)', text[slice(*spans[definition])]):
        raise ValueError('Require the exact previously reviewed single definition')
    matches = list(re.finditer(r'\bRepresentatives\b', text))
    if not any(text[a:b].count(TERM) for i, (a, b) in enumerate(spans) if i in operative):
        raise ValueError('The operative permission must refer to the defined term')
    if any(m.start() < p < m.end() for m in matches for span in spans for p in span):
        raise ValueError('Evidence index boundary splits a defined term')
    ends = [m.end() for m in matches]
    lengths = len(ALIAS) - len(TERM)
    shifted = [[a + lengths * bisect_right(ends, a), b + lengths * bisect_right(ends, b)] for a, b in spans]
    revised = re.sub(r'\bRepresentatives\b', ALIAS, text)
    assert revised.replace(ALIAS, TERM) == text
    assert all(revised[a:b] == re.sub(r'\bRepresentatives\b', ALIAS, text[x:y])
               for (a, b), (x, y) in zip(shifted, spans, strict=True))
    return revised, shifted, len(matches)


def replace_wire(payload, text, spans, revised, corrected):
    messages = deepcopy(payload['messages'])
    user, = (m for m in messages if m['role'] == 'user')
    doc = json.loads(user['content'])
    public = doc['public']
    old_key, = public['shared_documents']
    old = public['shared_documents'][old_key]
    assert old['source_text'] == text and old['sentence_spans'] == spans
    assert old_key == digest({'source_text': text, 'sentence_spans': spans})
    for ascii_only in (False, True):
        if json.dumps(doc, ensure_ascii=ascii_only) == user['content']:
            break
    else:
        raise ValueError('Cannot preserve the original serialized wire layout')
    new_key = digest({'source_text': revised, 'sentence_spans': corrected})
    old['source_text'], old['sentence_spans'] = revised, corrected
    for row in old['evidence_units']:
        i = row['id']
        a, b = spans[i]
        assert row['start'] == a and row['end'] == b and row['text'] == text[a:b]
        x, y = corrected[i]
        row.update(start=x, end=y, text=revised[x:y])
    public['shared_documents'] = {new_key: old}
    for view in public['native_views']:
        assert view['public']['document_ref'] == old_key
        view['public']['document_ref'] = new_key
    user['content'] = json.dumps(doc, ensure_ascii=ascii_only)
    return messages


def consume(source, schema, result):
    if result['finish_reason'] != 'stop':
        return None
    try:
        value = json.loads(result['content'])
        jsonschema.validate(value, schema)
        answers, evidence = decode_native(DATASET, source_bundle(source), value['value'])
        return {key: {'answer': answers[key], 'evidence': evidence[key]} for key in TASKS}
    except (KeyError, TypeError, ValueError, jsonschema.ValidationError):
        return None


def materials():
    review_spec, cases = source_reviews()
    fit = ROOT / read(pointer(3))['artifact_root']
    lock = read(fit / 'binding.json')
    terminal = read(fit / 'terminal.json')
    decisions = read(fit / 'matched_decisions.json')
    decision = decisions['teacher'][ORDINARY][DATASET]
    assert fit.name == digest(lock) and terminal['matched_decisions_sha256'] == digest(decisions)
    assert decision['selected'] == 'candidate' and decision['native_utility_delta'] > 0
    assert not terminal['TEST_opened']
    assert all(sha(fit / 'source_snapshot' / f) == h for f, h in lock['source_sha256'].items())
    directory = fit / 'candidates' / ORDINARY / DATASET
    pay = read(directory / 'measurements.json')
    regress = read(directory / 'prior_TRAIN_regression.json')
    assert digest(regress) == decision['earlier_TRAIN_regression']['evidence_sha256']
    assert digest(pay['predictions']) == decision['predictions_sha256']
    trials = []
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for pos, entry in cases.items():
            group, definition, operative, _ = REVIEWS[pos]
            if group != 'linked' or pos[0] > 3:
                continue
            source, view = entry['source'], entry['view']
            key = source['key']
            assert source['project_split'] == 'train'
            text, spans = view['public']['source_text'], view['public']['sentence_spans']
            assert all(v['public']['source_text'] == text and v['public']['sentence_spans'] == spans for v in source['views'])
            a_text, a_spans, count = renamed_document(text, spans, definition, operative)
            edited = {**source, 'views': [{**v, 'public': {**v['public'], 'source_text': a_text,
                                                          'sentence_spans': a_spans}} for v in source['views']]}
            required = sorted({definition, *operative})
            actual = {'source': source, 'edited': edited, 'text': text, 'spans': spans, 'renamed': a_text,
                      'shifted': a_spans, 'occurrences': count, 'required': required, 'archives': {}}
            old, new = ((entry['prior']['result'], pay['predictions'][key]) if pos[0] == 3 else
                        (regress['before'][key], regress['candidate'][key]))
            for role, raw in zip(ROLES, (old, new), strict=True):
                trace, = (t for part in raw['reads'] for t in part['execution']['traces'] if 'physical_call_id' in t)
                call = trace['physical_call_id']
                physical_wire(db, {key}, call, key)
                paid = json.loads(db.execute('select result from calls where id=?', (call,)).fetchone()[0])
                assert paid['content'] == trace['raw_content']
                wire = read(Path(paid['artifact_directory']) / 'wire_request.json')
                blob = base64.b64decode(wire['body_b64'], validate=True)
                payload = json.loads(blob)
                schema = payload['response_format']['json_schema']['schema']
                assert schema['properties']['value'] == wire_schema(DATASET, source_bundle(source))
                assert schema['properties']['value'] == wire_schema(DATASET, source_bundle(edited))
                result = consume(source, schema, paid)
                assert result == {k: {'answer': raw['native'][k]['answer'],
                                      'evidence': raw['native'][k]['evidence_sentence_ids']} for k in TASKS}
                base_messages = replace_wire(payload, text, spans, text, spans)
                assert base_messages == payload['messages']
                assert json.dumps(request_payload(review_spec['executor'], messages=base_messages,
                                                  thinking=False, schema=schema), ensure_ascii=False).encode() == blob
                actual['archives'][role] = {'id': call, 'payload': payload, 'v': result,
                                            'wire_sha256': wire['body_sha256']}
            trials.append(actual)
    assert len(trials) == 2
    files = [Path(__file__).relative_to(ROOT), 'experiments/convergence_revision5_cni_linked_evidence.py',
             'legal_skill_guard/paired_interfaces/control_answers.py', 'legal_skill_guard/skill_evolution/native.py',
             'legal_skill_guard/skill_evolution/clients.py', 'legal_skill_guard/rr/client.py']
    binding = {'study': 'CNI_shared_disclosure_scope_defined_term_alias', 'TRAIN_only': True,
               'prior_fit_terminal_sha256': sha(fit / 'terminal.json'), 'trial_sha256': digest(trials),
               'source_files': {str(f): sha(ROOT / f) for f in files}, 'executor': review_spec['executor'],
               'grading_file': review_spec['grading_file'], 'grading_file_sha256': review_spec['grading_file_sha256'],
               'hypotheses': list(TASKS), 'independent_mothers': len(trials), 'planned_calls': len(trials)*len(ROLES),
               'forecast': 'Meaning-preserving alias substitution can expose unstable evidence for either permission '
                           'when the original policy cites the prohibition or omits the separate definition.',
               'same_information_control': 'Invert the exact alpha-renaming before reading; reuse original paid responses.',
               'direct_support_control': 'Use the verified operative permission with its linked membership definition.'}
    return binding, trials


def settlement(out, binding, trials, readings, ledger):
    path = ROOT / binding['grading_file']
    assert path.parent.name == 'train' and sha(path) == binding['grading_file_sha256']
    native = read(path)
    rows = {r: {condition: [] for condition in ('original', 'alias', 'direct_link')} for r in ROLES}
    invariance = {r: Counter() for r in ROLES}
    for trial, paid in zip(trials, readings, strict=True):
        key = trial['source']['key']
        for role in ROLES:
            old, revised = trial['archives'][role]['v'], paid[role]['answer']
            for task in TASKS:
                a, b = old[task], revised[task] if revised is not None else {'answer': None, 'evidence': []}
                invariance[role]['labels'] += a['answer'] == b['answer']
                invariance[role]['evidence_sets'] += set(a['evidence']) == set(b['evidence'])
                direct = {'answer': 'Entailment', 'evidence': trial['required']}
                view, = (v for v in trial['source']['views'] if v['id'] == task)
                for name, item in (('original', a), ('alias', b), ('direct_link', direct)):
                    score = grade_view(DATASET, view, native[key][task], item['answer'], item['evidence'])
                    assert score['grade'] is not None
                    rows[role][name].append({'exact': score['grade'], 'evidence_f1': score['evidence_f1'],
                                            'source_support': set(trial['required']) <= set(item['evidence'])
                                            and item['answer'] == 'Entailment'})
    summary = {role: {name: {k: mean(row[k] for row in values) for k in values[0]}
                      for name, values in conditions.items()} for role, conditions in rows.items()}
    return {'status': 'settled_CNI_definition_alias_TRAIN', 'new_requests': len(trials)*len(ROLES),
            'original_paid_responses': len(trials)*len(ROLES), 'original_mothers': len(trials),
            'tasks_per_role': len(trials)*len(TASKS), 'native_results': summary, 'invariance': invariance,
            'tokens': {role: sum(r[role]['tokens'] for r in readings) for role in ROLES},
            'direct_reversion_reuses_exact_original_calls': True, 'ledger': ledger,
            'predictions_sha256': sha(out / 'predictions.json'), 'runner_sha256': sha(Path(__file__))}


def run(phase):
    binding, trials = materials()
    out = HOME / digest(binding)
    immutable_json(out / 'binding.json', binding)
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json')), flush=True)
        return
    if phase == 'prepare':
        write_status(out, {'status': 'prepared', 'planned_calls': binding['planned_calls']}, POINTER)
        print(str(out.relative_to(ROOT)), flush=True)
        return
    assert ROOT / read(POINTER)['artifact_root'] == out
    lock = (out / 'driver.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for name, expected in binding['source_files'].items():
        path = out / 'source_snapshot' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with path.open('xb') as stream:
                stream.write((ROOT/name).read_bytes())
        assert sha(path) == expected
    identity = 'convergence-revision5-CNI-definition-alias-' + out.name[:16]
    ledger = EvolutionLedger(LEDGER, run_id=identity, sources={
        'train': [t['source']['key'] for t in trials], 'dev': [], 'test': []}, binding=binding)
    reader = FrozenExecutor(ledger, out, binding['executor'])
    reader.readiness()
    records = []
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        for n, trial in enumerate(trials):
            pair = {}
            for role in (ROLES if n % 2 == 0 else ROLES[::-1]):
                call = f'{identity}:{n}:{role}'
                old = trial['archives'][role]['payload']
                schema = old['response_format']['json_schema']['schema']
                messages = replace_wire(old, trial['text'], trial['spans'], trial['renamed'], trial['shifted'])
                expected = json.dumps({**old, 'messages': messages}, ensure_ascii=False).encode()
                assert expected == json.dumps(reader.payload(messages=messages, thinking=False, schema=schema),
                                              ensure_ascii=False).encode()
                key = trial['source']['key']
                write_status(out, {'status': 'running', 'settled_pairs': n, 'current_call': call}, POINTER)
                result = reader.generate(call, source=key, purpose='skill_actor', messages=messages,
                                         thinking=False, schema=schema)
                physical_wire(db, {key}, call, key)
                wire = read(Path(result['artifact_directory']) / 'wire_request.json')
                assert base64.b64decode(wire['body_b64'], validate=True) == expected
                pair[role] = {'answer': consume(trial['edited'], schema, result),
                              'tokens': result['usage']['total_tokens'], 'id': call}
                immutable_json(out / 'reads' / f'{n}_{role}.json', pair[role])
                print(json.dumps({'settled': f'{n}:{role}', 'decoded': pair[role]['answer'] is not None}), flush=True)
            records.append(pair)
        counts = dict(db.execute('select status,count(*) from calls group by status'))
        assert not counts.get('reserved')
    immutable_json(out / 'predictions.json', records)
    terminal = settlement(out, binding, trials, records, counts)
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'settled_pairs': len(records)}, POINTER)
    print(json.dumps(terminal), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    run(parser.parse_args().phase)
