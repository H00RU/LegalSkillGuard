"""Compare fixed and synthesized bindings for two native NDA effects."""

import argparse
from collections import Counter
import fcntl
from functools import lru_cache
import inspect
import json
from pathlib import Path
import sqlite3
from statistics import mean

import jsonschema

from experiments.convergence_formal_train_fit import ORDINARY
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_cni_linked_evidence import DATASET, span_inventory
from experiments.convergence_revision5_cni_partial_wire import checked_result
from experiments.convergence_revision5_cni_reverse_engineering import archive_context, collect
from experiments.convergence_revision5_maud_zero_evidence import response
from legal_skill_guard.paired_interfaces import residual
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.client import request_payload
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, record_schema
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision5_CNI_use_and_license_20261119'
POINTER = HANDOFF / 'revision5_CNI_use_and_license_current.json'
DONE = 'settled_CNI_paired_use_and_license_TRAIN'
TASKS = {'purpose_scope': 'nda-4', 'no_rights_grant': 'nda-15'}
ROLES = ('fixed', 'synthesized', 'direct')
YES, NO, ABSENT = 'Entailment', 'Contradiction', 'NotMentioned'

# Source-reviewed forms for coverage, not a random sample or new holdout.
# Two clauses can each support a qualified proposition. Evidence needs one
# complete combination, including the operative lead-in when split.
REVIEWS = {
    (1, 2): ((YES, ((14, 16),)), (YES, ((38,),))),
    (2, 0): ((ABSENT, ()), (ABSENT, ())),
    (2, 2): ((YES, ((65,),)), (YES, ((68,),))),
    (4, 1): ((ABSENT, ()), (ABSENT, ())),
    (5, 0): ((YES, ((25, 27),)), (YES, ((36, 37),))),
    (7, 0): ((YES, ((10,), (16,))), (YES, ((15, 16),))),
}
MEANINGS = {
    'use_limit_is_operative': 'operative language limits use to the stated purpose or an expressly authorized purpose',
    'use_limit_binds_received_information': 'that same limit governs the receiving party using the protected information',
    'unrestricted_use_is_granted': 'an operative grant lets the recipient use the received information outside the stated purpose',
    'withholding_is_operative': 'operative language withholds a right, ownership interest, or license created by this agreement',
    'withholding_reaches_received_information': 'that same withholding covers the confidential information or the IP rights associated with it',
    'substantive_right_is_granted': 'the agreement affirmatively grants a proprietary right or intellectual property license in the received information',
}
COMMON = (
    'Read the original agreement, native hypotheses, and span IDs. Identify the receiving party, '
    'the protected information, the legal act, and any scope limits or exceptions. A ban on disclosure '
    'or a rule requiring consent without a stated purpose does not itself restrict use to that purpose. '
    'Do not treat a limit on assigning the agreement or enforcing remedies as withholding a license in '
    'confidential information. A limited right to use the information for the stated purpose can coexist '
    'with the withholding of proprietary rights or licenses. When a clause is a numbered continuation '
    'or a sentence is split across consecutive spans, include the leading span if it supplies the '
    'subject, act, or negation. Check the complete agreement for competing operative terms. Use false '
    'for a checked absence and null for unresolved reading. Cite original IDs only. For a signed '
    'conclusion cite its operative language and required lead-in. For an absent or unresolved '
    'conclusion use no evidence IDs.'
)


def consume(values, _):
    purpose, rights = None, None
    if values['use_limit_is_operative'] == True and values['use_limit_binds_received_information'] == True:
        purpose = YES
    elif values['use_limit_is_operative'] == False or values['use_limit_binds_received_information'] == False:
        if values['unrestricted_use_is_granted'] is not None:
            purpose = NO if values['unrestricted_use_is_granted'] else ABSENT
    if values['withholding_is_operative'] == True and values['withholding_reaches_received_information'] == True:
        rights = YES
    elif values['withholding_is_operative'] == False or values['withholding_reaches_received_information'] == False:
        if values['substantive_right_is_granted'] is not None:
            rights = NO if values['substantive_right_is_granted'] else ABSENT
    return {'purpose_scope': purpose, 'no_rights_grant': rights}


@lru_cache(maxsize=1)
def layouts():
    procedure = inspect.getsource(consume)
    module = residual.FiniteModule.build(
        'purpose_and_license_binding', dict.fromkeys(MEANINGS, [True, False, None]), [{}], consume,
        consumer_sha256=digest(procedure), program_source=procedure,
        protected_status_fields=('unrestricted_use_is_granted', 'substantive_right_is_granted'),
        source_scope={'source_fields': ['source_text'], 'local_unit': 'operative use and license clauses',
                      'field_meanings': MEANINGS})
    fixed = [{'name': key, 'operation': 'field', 'field': key} for key in MEANINGS]
    features = []
    for start, name in ((0, 'purpose_limit_on_received_information'), (3, 'withholding_of_rights_in_received_information')):
        deps = set(list(MEANINGS)[start:start + 2])
        relation, = (r for r in residual.consumer_relations(module)
                     if r['expression']['op'] == 'and' and set(r['consumer_dependencies']) == deps)
        features.extend(({**relation, 'name': name}, fixed[start + 2]))
    assets = {
        'fixed': residual.compile_pair(module, fixed, operation='fixed_coordinates', layout='anchored'),
        'synthesized': residual.compile_pair(module, features, operation='consumer_relational_projection', layout='anchored'),
    }
    for asset in assets.values():
        for state in module.states:
            result = residual.decode(asset, residual.encode(asset['features'], state), {}, module_binding=module.binding)
            assert result['valid'] and result['outputs'] == consume(state, {})
    return module, assets


def contract(case, role):
    citations = {'type': 'array', 'maxItems': 12, 'items': {'type': 'integer', 'minimum': 0,
                 'maximum': len(case['data']['indexed_spans']) - 1}}
    if role == 'direct':
        fields = {'answers': record_schema(dict.fromkeys(TASKS, {'enum': [YES, NO, ABSENT, None]}))}
        instructions = ('Give the native classification for each question after applying the local legal tests. '
                        'Use Entailment or Contradiction for an established legal effect, NotMentioned for checked '
                        'absence, and null for unresolved scope.')
    else:
        asset = layouts()[1][role]
        fields = {'relations': record_schema({f['name']: {'enum': asset['domains'][f['name']]}
                                              for f in asset['features']})}
        instructions = '\n'.join(residual.reader_prompt(asset, verbalize_relations=True).splitlines()[4:])
    schema = record_schema({**fields, 'evidence': record_schema(dict.fromkeys(TASKS, citations))})
    user = json.dumps(case['data'], ensure_ascii=False, sort_keys=True)
    return [{'role': 'system', 'content': COMMON + '\n' + instructions}, {'role': 'user', 'content': user}], schema


def decode(case, role, result):
    empty = {kind: {'answer': None, 'evidence': []} for kind in TASKS}
    try:
        if result['finish_reason'] != 'stop':
            return empty, result['finish_reason']
        value = json.loads(result['content'])
        jsonschema.validate(value, contract(case, role)[1])
        if role == 'direct':
            answers = value['answers']
        else:
            module, assets = layouts()
            receipt = residual.decode(assets[role], value['relations'], {}, module_binding=module.binding)
            if not receipt['valid']:
                return empty, 'unresolved_wire'
            answers = receipt['outputs']
        out = {}
        for task, label in answers.items():
            evidence = sorted(set(value['evidence'][task]))
            spans = case['data']['indexed_spans']
            if any(not spans[i]['text'].strip() for i in evidence) or (label in (YES, NO) and not evidence):
                label = None
            out[task] = {'answer': label, 'evidence': evidence if label in (YES, NO) else []}
        return out, None
    except (ValueError, jsonschema.ValidationError):
        return empty, 'invalid_wire'


def materials():
    checkpoint, study, roster = archive_context()
    _, original, grade, terminals = collect(checkpoint, study, roster, 'train')
    candidates = layouts()[1]
    cases, physical = [], {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        for batch, cohort in enumerate(roster, 1):
            for ordinal, source in enumerate(s for s in cohort if s['dataset'] == DATASET):
                position = (batch, ordinal)
                if position not in REVIEWS:
                    continue
                assert source['project_split'] == 'train'
                key = source['key']
                _, archived = checked_result(db, source, original[ORDINARY][key], physical)
                views = {task: next(v for v in source['views'] if v['id'] == native) for task, native in TASKS.items()}
                anchor = views['purpose_scope']
                spans = span_inventory(anchor)
                assert all(span_inventory(v) == spans for v in views.values())
                review = dict(zip(TASKS, REVIEWS[position], strict=True))
                assert all(spans[i].strip() for _, alternatives in review.values() for a in alternatives for i in a)
                data = {'document': anchor['public']['source_text'],
                        'questions': {k: v['public']['question'] for k, v in views.items()},
                        'indexed_spans': [{'id': i, 'text': span} for i, span in enumerate(spans)]}
                entering = {task: {'answer': archived[t]['answer'], 'evidence': archived[t]['evidence_sentence_ids']}
                            for task, t in TASKS.items()}
                cases.append({'source': key, 'position': list(position), 'views': views, 'data': data,
                              'review': review, 'entering': entering})
    assert len(cases) == len(REVIEWS) == len(physical)
    files = (Path(__file__), Path(residual.__file__), Path(inspect.getfile(checked_result)),
             Path(inspect.getfile(collect)), Path(inspect.getfile(response)), Path(inspect.getfile(FrozenExecutor)),
             Path(inspect.getfile(request_payload)), Path(inspect.getfile(grade_view)))
    binding = {'study': 'CNI_native_purpose_and_license_binding', 'partition': 'TRAIN',
               'executor': study['executor'], 'cases_sha256': digest(cases), 'source_sha256':
               {str(p.relative_to(ROOT)): sha(p) for p in files}, 'ordered_cases': [c['position'] for c in cases],
               'archive_terminals': terminals, 'grade_path': str(grade.relative_to(ROOT)), 'grade_sha256': sha(grade),
               'wire_contracts_sha256': digest([contract(c, a) for c in cases for a in ROLES]),
               'versions': {r: a['version'] for r, a in candidates.items()}, 'planned_calls': len(ROLES) * len(cases),
               'calibration_batches': [1, 2], 'forward_batches': [4, 5, 7],
               'forecast': 'An operative-clause binding can reduce cross-clause polarity and object errors, particularly on split negation and shared proof spans.',
               'strong_controls': ['direct same-input read', 'original TRAIN program', 'reviewed source proof'],
               'selection': 'Rank fixed and synthesized on whole source-supported calibration tasks, prefer fixed on ties.'}
    return binding, cases


def measure(case, reading, grades):
    rows = {}
    for kind, task in TASKS.items():
        row = reading[kind]
        annotation = grades[case['source']][task]
        metric = grade_view(DATASET, case['views'][kind], annotation, row['answer'], row['evidence'])
        label, required = case['review'][kind]
        found = set(row['evidence'])
        grounded = row['answer'] == label and (not found if label == ABSENT else any(
            set(evidence) <= found <= {i for option in required for i in option} for evidence in required))
        rows[kind] = {'exact': bool(metric['grade']), 'evidence_f1': metric['evidence_f1'], 'source_supported': grounded}
    return rows


def score(cases, paid, grades):
    results = []
    for case, pair in zip(cases, paid, strict=True):
        reviewed = {kind: {'answer': label, 'evidence': sorted({i for option in options for i in option})}
                    for kind, (label, options) in case['review'].items()}
        conditions = {**{r: cell['decoded'] for r, cell in pair.items()}, 'entering': case['entering'], 'direct_source': reviewed}
        results.append({'position': case['position'], 'cells': {r: measure(case, v, grades) for r, v in conditions.items()}})
    stages = {'calibration': results[:3], 'forward': results[3:]}
    aggregate = {}
    for stage, rows in stages.items():
        aggregate[stage] = {}
        for role in rows[0]['cells']:
            metrics = [m for mother in rows for m in mother['cells'][role].values()]
            aggregate[stage][role] = {'exact': sum(x['exact'] for x in metrics),
                                      'evidence_f1': mean(x['evidence_f1'] for x in metrics),
                                      'source_supported': sum(x['source_supported'] for x in metrics), 'n': len(metrics)}
    choice = max(ROLES[:2], key=lambda r: aggregate['calibration'][r]['source_supported'])
    return aggregate, choice, results


def run(execute):
    binding, cases = materials()
    out = HOME / digest(binding)
    immutable_json(out / 'binding.json', binding)
    if (out / 'terminal.json').exists():
        print(out.relative_to(ROOT), flush=True)
        return
    if not execute:
        if POINTER.exists() and read(POINTER)['status'] == 'running':
            raise ValueError('Use the active experiment binding')
        write_status(out, {'status': 'prepared', 'planned_calls': binding['planned_calls']}, POINTER)
        print(out.relative_to(ROOT), flush=True)
        return
    assert ROOT / read(POINTER)['artifact_root'] == out
    lock = (out / 'driver.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for name, expected in binding['source_sha256'].items():
        path = out / 'source_snapshot' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with path.open('xb') as dest:
                dest.write((ROOT / name).read_bytes())
        assert sha(path) == expected
    identity = 'convergence-revision5-CNI-use-and-license-' + out.name[:16]
    ledger = EvolutionLedger(LEDGER, run_id=identity, sources={'train': [c['source'] for c in cases], 'dev': [], 'test': []}, binding=binding)
    reader = FrozenExecutor(ledger, out, binding['executor'])
    reader.readiness()
    paid, tokens, stops = [], Counter(), Counter()
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        for i, case in enumerate(cases):
            pair = {}
            shift = i % len(ROLES)
            for role in ROLES[shift:] + ROLES[:shift]:
                call = f'{identity}:{i}:{role}'
                messages, schema = contract(case, role)
                write_status(out, {'status': 'running', 'settled_pairs': i, 'current_call': call}, POINTER)
                result = reader.generate(call, source=case['source'], purpose='skill_actor', thinking=False,
                                         messages=messages, schema=schema)
                recorded, wire = response(db, case['source'], call)
                assert recorded == result and wire == request_payload(binding['executor'], messages=messages, thinking=False, schema=schema)
                output, error = decode(case, role, result)
                pair[role] = {'id': call, 'decoded': output, 'error': error}
                tokens[role] += result['usage']['total_tokens']
                stops[role] += int(error is None)
                immutable_json(out / 'responses' / f'{i}_{role}.json', pair[role])
                print(json.dumps({'case': i, 'arm': role, 'status': error}), flush=True)
            paid.append(pair)
        counts = dict(db.execute('select status,count(*) from calls group by status'))
        assert not counts.get('reserved')
    immutable_json(out / 'predictions.json', paid)
    grade = ROOT / binding['grade_path']
    assert grade.parent.name == 'train' and sha(grade) == binding['grade_sha256']
    scores, choice, rows = score(cases, paid, read(grade))
    summary = {'status': DONE, 'partition': 'TRAIN', 'native_scores': scores, 'calibrated_interface': choice,
               'paid_calls': binding['planned_calls'], 'token_totals': dict(tokens), 'valid_reads': dict(stops),
               'new_teacher_calls': 0, 'ledger': counts, 'finite_domain_states': len(layouts()[0].states),
               'runner_sha256': sha(Path(__file__)), 'case_results': rows, 'predictions_sha256': sha(out / 'predictions.json')}
    immutable_json(out / 'terminal.json', summary)
    write_status(out, {'status': DONE, 'settled_pairs': len(cases)}, POINTER)
    print(json.dumps({'native_scores': scores, 'calibrated_interface': choice, 'tokens': tokens}, sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    run(parser.parse_args().phase == 'run')
