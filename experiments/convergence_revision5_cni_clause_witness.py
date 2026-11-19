"""Complete ContractNLI evidence references to already-cited dependent clauses."""

from collections import Counter
from pathlib import Path
import re
import sqlite3
from statistics import mean

from experiments import convergence_revision5_cni_use_and_license as paired
from experiments.convergence_revision5_cni_reverse_engineering import ARMS
from experiments.convergence_revision5_cni_use_and_license_evidence import (
    RIGHTS, SPLIT_CONTINUATION, SPLIT_LEAD, THEREIN,
)
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.rr.checkpoint import immutable_json


HOME = paired.BASE / 'revision5_CNI_clause_witness_20261119'
TABLE = paired.ROOT / 'reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_CLAUSE_WITNESS_20261119.json'
MARKER = re.compile(r'^(?P<dotted>\d+(?:\.\d+)+)\.?\s+|^(?P<list>\([a-z]+\)|[a-z][.)])\s+', re.I)
ROMAN = dict(zip(('i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x'), range(1, 11), strict=True))
ACTION = re.compile(r'^(?:not\s+)?(?:to\s+|will\s+)?(?:use|be used)\b|^to maintain\b.{0,65}\band to use\b', re.I)
LIMIT = re.compile(r'\b(?:only|solely|except|other than)\b.{0,100}\bpurpose\w*\b|\bpurpose\w*\b.{0,70}\b(?:except|other than)\b', re.I)
OBJECT = re.compile(r'\b(?:confidential information|evaluation materials?)\b', re.I)
PARTY = re.compile(r'\b(?:part(?:y|ies)|recipient|entity|company|representatives?|you)\b', re.I)
STEM = re.compile(r'\b(?:undertakes?|agrees?|promises?|shall not|will not)\b', re.I)


def item(text):
    marker = MARKER.match(text)
    if marker is None:
        return (), text
    if dotted := marker['dotted']:
        prefix, ordinal = dotted.rsplit('.', 1)
        return ((prefix, int(ordinal)),), text[marker.end():]
    tag = marker['list'].lower()
    letter = tag.strip('().')
    style = tag.replace(letter, '*')
    positions = []
    if len(letter) == 1:
        positions.append((style + 'alpha', ord(letter) - ord('a') + 1))
    if letter in ROMAN:
        positions.append((style + 'roman', ROMAN[letter]))
    return tuple(positions), text[marker.end():]


def purposes(spans):
    indexed = [(i, s, *item(s)) for i, s in enumerate(spans) if s]
    witnesses = {}
    for position, (index, _, markers, phrase) in enumerate(indexed):
        if not (ACTION.search(phrase) and LIMIT.search(phrase)):
            continue
        valid = set()
        for style, ordinal in markers:
            start = position - ordinal
            if start < 0 or not all((style, n) in indexed[start + n][2] for n in range(1, ordinal)):
                continue
            head, stem, _, _ = indexed[start]
            if not (PARTY.search(stem) and STEM.search(stem)):
                continue
            # The object must occur in the governing stem or in the operative item.
            if not OBJECT.search(stem + ' ' + phrase):
                continue
            valid.add((head, index))
        if len(valid) == 1:
            witnesses[index], = valid
    return witnesses


def licenses(spans):
    witnesses = {}
    for i, (lead, leaf) in enumerate(zip(spans, spans[1:]), 1):
        split = (SPLIT_LEAD.search(lead) and not lead.endswith(('.', '!', '?', ';', ':'))
                 and SPLIT_CONTINUATION.search(leaf) and RIGHTS.search(leaf) and OBJECT.search(leaf))
        antecedent = (OBJECT.search(lead) and re.search(r'\b(?:remain\w*|is|are)\b.{0,60}\bproperty of\b', lead, re.I)
                      and THEREIN.search(leaf))
        if split or antecedent:
            witnesses[i] = (i - 1, i)
    return witnesses


def source_proofs(view):
    spans = [' '.join(s.split()) for s in paired.span_inventory(view)]
    return {'purpose_scope': purposes(spans), 'no_rights_grant': licenses(spans)}


def complete(reading, groups):
    if reading['answer'] != paired.YES:
        return reading, reading
    anchors = {groups[i] for i in reading['evidence'] if i in groups}
    if len(anchors) != 1:
        return reading, reading
    witness, = anchors
    return ({**reading, 'evidence': sorted(set(witness) | set(reading['evidence']))},
            {**reading, 'evidence': list(witness)})


def native_rows(source, result):
    return {kind: {'answer': result[task]['answer'], 'evidence': result[task]['evidence_sentence_ids']}
            for kind, task in paired.TASKS.items()}


def score(sources, readings, grade, proofs):
    rows = {mode: [] for mode in ('archived', 'completed', 'minimal')}
    cases = []
    for key, answers in readings.items():
        edits = {}
        for kind, task in paired.TASKS.items():
            views = [v for v in sources[key]['views'] if v['id'] == task]
            view, = views
            reading = answers[kind]
            extended, minimal = complete(reading, proofs[key][kind])
            results = (reading, extended, minimal)
            for mode, output in zip(rows, results, strict=True):
                assert output['answer'] == reading['answer']
                native = paired.grade_view(paired.DATASET, view, grade[key][task], output['answer'], output['evidence'])
                rows[mode].append({'source': key, 'view': kind, 'grade': native['evidence_f1']})
            edits[kind] = (reading != extended, reading != minimal)
        cases.append(edits)
    outcome = {mode: {kind: mean(row['grade'] for row in data if row['view'] == kind)
                      for kind in paired.TASKS} for mode, data in rows.items()}
    return {'mothers': len(readings), 'evidence_f1': outcome,
            'changed_task_outputs': {kind: [sum(x[kind][i] for x in cases) for i in range(2)] for kind in paired.TASKS},
            'paired_evidence_f1': {mode: paired_source_effect(rows['archived'], rows[mode]) for mode in ('completed', 'minimal')}}


def run():
    context = paired.archive_context()
    binding, pilot = paired.materials()
    stage = paired.ROOT / paired.read(paired.POINTER)['artifact_root']
    end = paired.read(stage / 'terminal.json')
    assert stage.name == paired.digest(binding) and end['status'] == paired.DONE
    assert end['predictions_sha256'] == paired.sha(stage / 'predictions.json')
    rows = paired.read(stage / 'predictions.json')
    assert all(paired.sha(stage / 'source_snapshot' / n) == h for n, h in binding['source_sha256'].items())
    grades = {}
    expectations = {}
    with sqlite3.connect(paired.LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        assert not ledger.get('reserved')
        for partition in ('train', 'dev'):
            sources, original, grade, terminals = paired.collect(*context, partition)
            proofs = {key: source_proofs(next(v for v in s['views'] if v['id'] == 'nda-4')) for key, s in sources.items()}
            known = {}
            readings = {arm: {} for arm in ARMS}
            for arm, collection in original.items():
                for key, row in collection.items():
                    _, replay = paired.checked_result(db, sources[key], row, known, dev=partition == 'dev')
                    readings[arm][key] = native_rows(sources[key], replay)
            grades[partition] = (sources, proofs, grade)
            expectations[partition] = {'arms': readings, 'original_terminals': terminals, 'physical_reads': len(known)}
        for case, pair in zip(pilot, rows, strict=True):
            for role, cell in pair.items():
                raw, wire = paired.response(db, case['source'], cell['id'])
                messages, schema = paired.contract(case, role)
                assert wire == paired.request_payload(binding['executor'], messages=messages, thinking=False, schema=schema)
                assert paired.decode(case, role, raw) == (cell['decoded'], cell['error'])
    results = {}
    for partition, (sources, proofs, grade) in grades.items():
        labels = paired.read(grade)
        results[partition] = {**{k: expectations[partition][k] for k in ('original_terminals', 'physical_reads')},
                              'source_coverage': dict(Counter(kind for p in proofs.values() for kind in p if p[kind])),
                              'arms': {arm: score(sources, r, labels, proofs) for arm, r in expectations[partition]['arms'].items()}}
    sources, proofs, grade = grades['train']
    labels = paired.read(grade)
    pilot_results = {role: score(sources, {case['source']: pair[role]['decoded'] for case, pair in zip(pilot, rows, strict=True)},
                                 labels, proofs) for role in paired.ROLES}
    final = {'status': 'settled_revision5_CNI_clause_witness_TRAIN_DEV', 'new_requests': 0,
             'runner_sha256': paired.sha(Path(__file__)), 'source_witness_policy': 'Same proof completion for all arms, only with an already cited operative leaf and a unique verified governing stem.',
             'paid_pilot_responses_verified': sum(len(x) for x in rows), 'original_pilot_terminal_sha256': paired.sha(stage / 'terminal.json'),
             'archived': results, 'pilot': pilot_results, 'ledger': ledger}
    immutable_json(HOME / 'terminal.json', final)
    immutable_json(TABLE, final)
    print({p: r['source_coverage'] for p, r in results.items()}, flush=True)


if __name__ == '__main__':
    run()
