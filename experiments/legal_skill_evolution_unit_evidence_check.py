"""Finite real-TRAIN transport repair audit and changed-interface probes.

No acquisition/DEV/TEST queue is launched. Historical responses stay immutable;
projecting an old choice to unit IDs is a diagnostic, never semantic recovery.
"""
import argparse
import base64
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

import jsonschema

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import source_spans
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema
from legal_skill_guard.skill_evolution.scoped_grammar import material_public
from legal_skill_guard.skill_evolution.semantic_execution import decode_answers as decode_quoted
from legal_skill_guard.skill_evolution.semantic_operations import ground_answers
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units, occurrences
from legal_skill_guard.skill_evolution.unit_evidence import (
    TRANSPORT, answer_schema, decode_answers, ground_selected_units, reading_messages)

ROOT = Path(__file__).resolve().parents[1]
RUN = 'legal_skill_evolution_selected_unit_evidence_20261113'
PARENT = ROOT / 'artifacts/legal_skill_evolution_open_acquisition_semantic_route_absence_encoded_20261113'
LEDGER = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
read = lambda path: json.loads(Path(path).read_text())


def ledger_rows():
    with sqlite3.connect('file:' + str(LEDGER) + '?mode=ro', uri=True) as db:
        return db.execute('select * from calls order by id').fetchall()


def audit():
    folder = ROOT / 'artifacts' / RUN
    if (folder / 'protocol.json').exists():
        return folder, read(folder / 'protocol.json')
    rows = ledger_rows()
    if any(row[6] == 'reserved' for row in rows):
        raise ValueError('Reconcile live physical requests before the next bound probe')
    public_path = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    public = {s['key']: s for s in read(public_path)}
    failures = []; checked = 0
    for stage in ('acquisition', 'reuse'):
        for arm in ('ConstraintAcquire', 'FreeUpdate'):
            library = read(PARENT / arm / 'compiled.json')
            for path in sorted((PARENT / stage / arm / 'events').glob('*.json')):
                event = read(path); result = event['result']
                physical = Path(result['artifact_directory'])
                request = read(physical / 'request.json')
                source = request['source']; pub = public[source]['views'][0]['public']
                units, _ = execution_source_units(pub['source_text'], source_spans(material_public(pub)))
                message = json.loads(request['payload']['messages'][1]['content'])
                queries = [{k: q[k] for k in ('id', 'operation', 'unit_ids')} for q in message['current_queries']]
                wire = read(physical / 'wire_request.json')
                if hashlib.sha256(base64.b64decode(wire['body_b64'])).hexdigest() != wire['body_sha256']:
                    raise ValueError('Historical wire identity changed')
                saved = next(r for r in rows if r[0] == request['id'])
                if saved[6] != 'completed' or json.loads(saved[8])['content'] != result['content']:
                    raise ValueError('A raw response differs from its completed physical ledger row')
                checked += 1
                try:
                    decode_quoted(library['operations'], queries, units, result['content'], scope=event['scope'],
                        complete_source_absence_choices=library.get('complete_source_absence_choices'))
                except (ValueError, jsonschema.ValidationError) as error:
                    raw = json.loads(result['content'])
                    selected = {'answers': {q['id']: {'choice': raw['answers'][q['id']]['choice'],
                        'evidence_unit_ids': list(dict.fromkeys(w['unit_id'] for w in raw['answers'][q['id']]['evidence']))}
                        for q in queries}}
                    candidate = ground_selected_units(library['operations'], queries, units, selected, scope=event['scope'],
                        complete_source_absence_choices=library.get('complete_source_absence_choices'))
                    by_unit = {u['id']: u['text'] for u in units}; bad = []
                    for qid, answer in raw['answers'].items():
                        for witness in answer['evidence']:
                            if occurrences(by_unit[witness['unit_id']], witness['quote']):
                                continue
                            bad.append({'query': qid, 'raw_witness': witness,
                                'actual_selected_unit': by_unit[witness['unit_id']],
                                'other_units_containing_raw_quote': [u['id'] for u in units
                                    if u['id'] != witness['unit_id'] and occurrences(u['text'], witness['quote'])]})
                    failures.append({'stage': stage, 'arm': arm, 'source': source,
                        'physical_call_id': request['id'], 'old_wire_sha256': wire['body_sha256'],
                        'old_event_file': str(path.relative_to(ROOT)), 'old_event_sha256': digest(event),
                        'operations': library['operations'], 'queries': queries, 'units': units,
                        'scope': event['scope'], 'absence_choices': library.get('complete_source_absence_choices'),
                        'raw_response': result['content'], 'original_error': str(error),
                        'invalid_witnesses': bad, 'unit_projection_diagnostic': candidate,
                        'choices_changed': False, 'source_semantics_certified': False,
                        'counts_as_recovered_reading_or_method_success': False})
    if len(failures) != 5:
        raise ValueError('Reconcile actual failure inventory, do not silently change the probe selection')
    probes = [next(v for v in failures if v['arm'] == arm and v['source'].startswith('ContractNLI:' + prefix))
        for arm, prefix in [('ConstraintAcquire', '5cad3f37'), ('FreeUpdate', 'e7b78d42')]]
    files = [Path(__file__).resolve(), *sorted((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py')),
             *sorted((ROOT / 'tests').glob('test_skill_evolution*.py'))]
    protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'transport': TRANSPORT, 'parent': str(PARENT.relative_to(ROOT)),
        'executor': read(ROOT / 'configs/legal_skill_evolution_formal_v5_20261111.json')['executor'],
        'sources': list(dict.fromkeys(v['source'] for v in probes)),
        'probes': [{'arm': v['arm'], 'source': v['source'], 'old_physical_call_id': v['physical_call_id']} for v in probes],
        'purpose': 'One changed-interface check per specified real failure: copied hyphenation and wrong-unit citation. Preserve actual semantic choices for review; no new teacher or score-guided repair.',
        'automatic_retries': 0, 'no_new_mechanical_budget_cap': True,
        'no_full_training_DEV_TEST_or_source_addition': True,
        'source_snapshot': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        'data_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [public_path, PARENT / 'protocol.json', *(PARENT / a / 'compiled.json' for a in ('ConstraintAcquire', 'FreeUpdate'))]}}
    immutable_json(folder / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in rows})
    immutable_json(folder / 'offline_audit.json', {'checked_actual_responses': checked, 'failures': failures,
        'new_model_requests': 0, 'no_semantic_recovery_claimed': True})
    immutable_json(folder / 'probe_inputs.json', probes)
    for path in files:
        dst = folder / 'source_snapshot' / path.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(path.read_bytes())
    immutable_json(folder / 'protocol.json', protocol)
    return folder, protocol


def probe():
    folder, protocol = audit()
    for name, expected in {**protocol['source_snapshot'], **protocol['data_sha256']}.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Bound probe input changed: ' + name)
    ledger = EvolutionLedger(LEDGER, run_id=RUN, sources={'train': protocol['sources'], 'dev': [], 'test': []}, binding=digest(protocol))
    client = FrozenExecutor(ledger, folder, protocol['executor'])
    for item in read(folder / 'probe_inputs.json'):
        dst = folder / 'probes' / (item['arm'] + '.json')
        if dst.exists():
            continue
        prompt = reading_messages(item['operations'], item['queries'], item['units'], scope=item['scope'])
        schema, _ = decoder_schema(answer_schema(item['operations'], item['queries']))
        result = client.generate(RUN + ':' + item['arm'] + ':' + digest(prompt), source=item['source'],
            purpose='skill_replay', messages=prompt, thinking=False, schema=schema)
        immutable_json(dst.with_suffix('.raw.json'), result)
        if result['finish_reason'] != 'stop':
            raise ValueError('Incomplete changed-interface probe; no unchanged retry')
        raw, grounded = decode_answers(item['operations'], item['queries'], item['units'], result['content'],
            scope=item['scope'], complete_source_absence_choices=item['absence_choices'])
        immutable_json(dst, {'source': item['source'], 'arm': item['arm'], 'raw_answer': raw,
            'grounded': grounded, 'source_semantics_certified': False, 'method_success_claimed': False})
        print(json.dumps({'arm': item['arm'], 'source': item['source'], 'answer': raw,
                          'elapsed_seconds': result['elapsed_seconds'], 'usage': result['usage']}), flush=True)
    before = read(folder / 'ledger_before_row_hashes.json'); after = ledger_rows()
    if any(digest(r) != before[r[0]] for r in after if r[0] in before):
        raise ValueError('An earlier physical ledger record changed')
    immutable_json(folder / 'ledger_after.json', {'earlier_rows_preserved': len(before),
        'current_total': len(after), 'new_rows': [r for r in after if r[0] not in before]})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['audit', 'probe']); args = parser.parse_args()
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.phase == 'audit':
            folder, protocol = audit()
            print(json.dumps({'run_id': protocol['run_id'], 'audit': str(folder / 'offline_audit.json')}))
        else:
            probe()
