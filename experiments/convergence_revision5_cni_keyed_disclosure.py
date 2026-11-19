"""Read disclosure force and object on the same original ContractNLI clause key."""

import argparse
from collections import Counter
import fcntl
from functools import lru_cache
import inspect
import json
from pathlib import Path
import re
import sqlite3
from statistics import mean

import jsonschema

from experiments import convergence_revision5_cni_agreement_object as common
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_maud_zero_evidence import response
from legal_skill_guard.paired_interfaces import residual
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.client import request_payload
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, record_schema
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision5_CNI_keyed_disclosure_20261119'
POINTER = HANDOFF / 'revision5_CNI_keyed_disclosure_current.json'
ROLES = ('fixed', 'synthesized', 'direct')
DONE = 'settled_revision5_CNI_keyed_disclosure_TRAIN'
RELEVANT = re.compile(r'\b(?:disclos\w*|publish\w*|advertis\w*|announc\w*|keep\w*|confiden\w*|'
                      r'publicity|not to discuss|news release)\b', re.I)
NEGATED_SUBJECT = re.compile(r'\bneither party\b[^.;]{0,110}\bshall\b[^.;]{0,140}\b' + common.PUBLIC_ACT, re.I)
FIELDS = {
    'fact_is_object': 'the object within this group is the existence of the agreement, participation in its discussions, or whether those negotiations took place',
    'contains_restriction': 'the group contains an operative restriction on public or onward disclosure by a contracting party',
    'contains_unrestricted_grant': 'the group grants an operative unrestricted right of public or onward disclosure to a contracting party',
}
SYSTEM = (
    'Use the entire agreement and original native span IDs. A true fact of negotiation means whether '
    'an agreement was made or talks took place. Information exchanged during the talks, obligations to '
    'notify a counterparty, the terms alone, use limitations, licensing and termination are distinct. '
    'A party that may disclose technical data does not thereby have permission to announce the agreement. '
    'An operative nondisclosure provision can contain exceptions. Match effect and subject to the same '
    'marked clause group. Fields about an unrestricted grant exclude consent-conditioned exceptions. '
    'Use the neighboring original span only if it completes the clause or its reference. '
    'A marked group is a place to check. Use checked absence only after considering the whole document. '
    'If you find an operative event restriction or grant outside the marked groups, set outside_scope '
    'and cite the original span IDs so that the common scope check can defer this case.'
)


def consume(state, _):
    return {'event_restriction': state['fact_is_object'] == True and state['contains_restriction'] == True,
            'event_grant': state['fact_is_object'] == True and state['contains_unrestricted_grant'] == True}


@lru_cache(maxsize=1)
def layouts():
    source = inspect.getsource(consume)
    module = residual.FiniteModule.build(
        'clause_keyed_disclosure_event', dict.fromkeys(FIELDS, [True, False]), [{}], consume,
        consumer_sha256=digest(source), program_source=source,
        source_scope={'source_fields': ['source_text'], 'local_unit': 'one original clause group',
                      'field_meanings': FIELDS})
    fixed = [{'name': name, 'operation': 'field', 'field': name} for name in FIELDS]
    generated = residual.consumer_relations(module)
    relations = []
    for field, name in (('contains_restriction', 'event_restriction'), ('contains_unrestricted_grant', 'event_grant')):
        feature, = (r for r in generated if r['expression']['op'] == 'and' and
                    set(r['consumer_dependencies']) == {'fact_is_object', field})
        relations.append({**feature, 'name': name})
    assets = {name: residual.compile_pair(module, features, operation='clause_keyed_'+name, layout='anchored')
              for name, features in (('fixed', fixed), ('synthesized', relations))}
    for asset in assets.values():
        for state in module.states:
            assert residual.decode(asset, residual.encode(asset['features'], state), {}, module_binding=module.binding)['outputs'] == consume(state, {})
    return module, assets


def eligible_groups(view):
    family, checked = common.compile_scope(view)
    if checked is not None or family == 'ambiguous':
        return {}
    spans = [common.archive.clean(t) for t in common.archive.span_inventory(view)]
    # An explicit negated subject has a direct source proof. Leave it with the shared rule.
    if any((match := NEGATED_SUBJECT.search(t)) and common.EVENT.search(t[match.end():]) for t in spans):
        return {}
    return {f'clause_{i}': [k for k in range(max(0, i-1), min(len(spans), i+2)) if spans[k]]
            for i, text in enumerate(spans) if common.EVENT_CUE.search(text) and RELEVANT.search(text)}


def contract(case, role):
    ids = {'type': 'array', 'maxItems': 12, 'items': {'type': 'integer', 'minimum': 0,
           'maximum': len(case['public']['indexed_spans']) - 1}}
    shared = {'outside_scope': {'type': 'boolean'}, 'outside_evidence': ids, 'whole_document_checked': {'type': 'boolean'}}
    if role == 'direct':
        fields = {'answer': {'enum': ['Entailment', 'Contradiction', 'NotMentioned', None]},
                  'evidence': ids}
        prompt = ('Answer the benchmark question directly. Entailment means an operative prohibition, '
                  'Contradiction means an operative unrestricted grant, and NotMentioned means neither was found. '
                  'Cite the relevant original spans, including any support outside the marked groups. '
                  'Use null if unresolved.')
    else:
        asset = layouts()[1][role]
        coordinates = {f['name']: {'enum': asset['domains'][f['name']]} for f in asset['features']}
        fields = {'groups': record_schema({key: record_schema({'fields': record_schema(coordinates),
                                                              'evidence': ids, 'unresolved': {'type': 'boolean'}})
                                           for key in case['public']['groups']})}
        prompt = ('Read each local group keyed by its clause ID. Give false only when checked. '
                  'If a field is uncertain, mark unresolved and cite only original IDs in the same group.\n'
                  + '\n'.join(residual.reader_prompt(asset, verbalize_relations=True).splitlines()[4:]))
    return [{'role': 'system', 'content': SYSTEM + '\n' + prompt},
            {'role': 'user', 'content': json.dumps(case['public'], ensure_ascii=False, sort_keys=True)}], record_schema({**shared, **fields})


def decode(case, role, raw):
    def output(answer, evidence=()):
        return {'answer': answer, 'evidence_sentence_ids': sorted(set(evidence))}

    if raw['finish_reason'] != 'stop':
        return output(None), raw['finish_reason']
    try:
        obj = json.loads(raw['content'])
        jsonschema.validate(obj, contract(case, role)[1])
        if not obj['whole_document_checked']:
            return output(None), 'scope_deferred'
        if role == 'direct':
            if obj['answer'] in ('Entailment', 'Contradiction') and not obj['evidence']:
                return output(None), 'missing_evidence'
            return output(obj['answer'], obj['evidence'] if obj['answer'] in ('Entailment', 'Contradiction') else ()), None
        if obj['outside_scope']:
            return output(None), 'scope_deferred'
        module, assets = layouts()
        signs = {'event_restriction': set(), 'event_grant': set()}
        unresolved = False
        for key, row in obj['groups'].items():
            certified = residual.decode(assets[role], row['fields'], {}, module_binding=module.binding)
            assert certified['valid']
            if row['unresolved'] or not set(row['evidence']) <= set(case['public']['groups'][key]):
                unresolved = True
                continue
            for part, present in certified['outputs'].items():
                if present and row['evidence']:
                    signs[part].update(row['evidence'])
                elif present:
                    unresolved = True
        supported = [s for s, evidence in signs.items() if evidence]
        if len(supported) > 1 or (not supported and unresolved):
            return output(None), 'unresolved_sign'
        if supported:
            sign, = supported
            return output('Entailment' if sign == 'event_restriction' else 'Contradiction', signs[sign]), None
        return output('NotMentioned'), None
    except (ValueError, jsonschema.ValidationError):
        return output(None), 'invalid_wire'


def materials():
    ctx = common.archive.archive_context()
    sources, old, grade, terminals = common.archive.collect(*ctx, 'train')
    cases, prior = [], {}
    for position, (key, source) in enumerate(sources.items()):
        view, = (v for v in source['views'] if v['id'] == common.TASK)
        groups = eligible_groups(view)
        if not groups:
            continue
        spans = common.archive.span_inventory(view)
        cases.append({'key': key, 'position': position, 'view': view,
                      'public': {'document': view['public']['source_text'], 'question': view['public']['question'],
                                 'indexed_spans': [{'id': i, 'text': text} for i, text in enumerate(spans)],
                                 'groups': groups}})
        prior[key] = {arm: {f: source_output['native'][common.TASK][f] for f in ('answer', 'evidence_sentence_ids')}
                      for arm, records in old.items() for source_output in [records[key]]}
    assert all(sources[row['key']]['project_split'] == 'train' for row in cases)
    files = (Path(__file__), Path(common.__file__), Path(residual.__file__), Path(inspect.getfile(FrozenExecutor)),
             Path(inspect.getfile(response)), Path(inspect.getfile(request_payload)))
    spec = {'study': 'clause_keyed_event_disclosure', 'partition': 'train', 'executor': ctx[1]['executor'],
            'source_sha256': {str(f.relative_to(ROOT)): sha(f) for f in files}, 'cases': digest(cases),
            'wire_sha256': digest([contract(c, role) for c in cases for role in ROLES]),
            'grade': str(grade.relative_to(ROOT)), 'grade_sha256': sha(grade), 'original_terminals': terminals,
            'planned_calls': len(cases)*len(ROLES), 'selected_positions': [c['position'] for c in cases],
            'selection': 'All TRAIN views with unresolved shared-rule scope and eligible event/act co-occurrence.'}
    return spec, cases, prior


def settle(out, spec, cases, bank, prior, ledger):
    path = ROOT/spec['grade']
    assert path.parent.name == 'train' and sha(path) == spec['grade_sha256']
    trusted = read(path)
    rows = {role: [] for role in (*ROLES, *next(iter(prior.values())).keys())}
    for case, paid in zip(cases, bank, strict=True):
        outputs = {**prior[case['key']], **{arm: data['answer'] for arm,data in paid.items()}}
        for role, answer in outputs.items():
            metric = grade_view('ContractNLI', case['view'], trusted[case['key']][common.TASK],
                                answer['answer'], answer['evidence_sentence_ids'])
            rows[role].append({'source': case['key'], 'view': common.TASK,
                               'grade': metric['grade'], 'evidence_f1': metric['evidence_f1']})
    scores = {role: {'correct': int(sum(r['grade'] for r in values)), 'evidence_f1': mean(r['evidence_f1'] for r in values)}
              for role, values in rows.items()}
    summary = {'status': DONE, 'partition': 'train', 'mothers': len(cases), 'scores': scores,
               'executor_calls': spec['planned_calls'], 'executor_tokens_by_arm': {r: sum(x[r]['tokens'] for x in bank) for r in ROLES},
               'teacher_calls': 0, 'ledger': ledger, 'cases': spec['selected_positions'],
               'paired_synthesized_minus_controls': {r: paired_source_effect(rows[r], rows['synthesized']) for r in ROLES if r != 'synthesized'},
               'scope_status_counts_by_arm': {r: dict(Counter(x[r]['status'] or 'valid' for x in bank)) for r in ROLES},
               'source_sha256': spec['source_sha256'], 'predictions_sha256': sha(out/'predictions.json')}
    immutable_json(out/'terminal.json', summary)
    write_status(out, {'status': DONE, 'settled_mothers': len(cases)}, POINTER)
    print(json.dumps(summary, sort_keys=True), flush=True)


def run(execute):
    spec, cases, prior = materials()
    out = HOME/digest(spec)
    immutable_json(out/'binding.json', spec)
    if (out/'terminal.json').exists():
        print(out.relative_to(ROOT), flush=True)
        return
    if not execute:
        assert not POINTER.exists() or read(POINTER)['status'] != 'running'
        write_status(out, {'status': 'prepared', 'planned_calls': spec['planned_calls']}, POINTER)
        print(out.relative_to(ROOT), spec['planned_calls'], spec['selected_positions'], flush=True)
        return
    assert ROOT/read(POINTER)['artifact_root'] == out
    gate = (out/'dispatch.lock').open('a')
    fcntl.flock(gate, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for name, digest_value in spec['source_sha256'].items():
        copy = out/'source_snapshot'/name
        copy.parent.mkdir(parents=True, exist_ok=True)
        if not copy.exists():
            with copy.open('xb') as handle:
                handle.write((ROOT/name).read_bytes())
        assert sha(copy) == digest_value
    run_id = 'convergence-revision5-CNI-keyed-' + out.name[:16]
    ledger = EvolutionLedger(LEDGER, run_id=run_id, sources={'train': [r['key'] for r in cases], 'dev': [], 'test': []}, binding=spec)
    actor = FrozenExecutor(ledger, out, spec['executor'])
    actor.readiness()
    bank = []
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro', uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        for i, case in enumerate(cases):
            row = {}
            start = i % len(ROLES)
            for role in ROLES[start:] + ROLES[:start]:
                call = f'{run_id}:{i}:{role}'
                write_status(out, {'status': 'running', 'settled_mothers': i, 'call': call}, POINTER)
                messages, schema = contract(case, role)
                actual = actor.generate(call, source=case['key'], purpose='skill_actor', messages=messages,
                                        thinking=False, schema=schema)
                raw, wire = response(db, case['key'], call)
                assert {k: v for k,v in actual.items() if k != 'cache_hit'} == raw
                assert wire == request_payload(spec['executor'], messages=messages, thinking=False, schema=schema)
                answer, status = decode(case, role, raw)
                row[role] = {'answer': answer, 'physical_id': call, 'tokens': raw['usage']['total_tokens'], 'status': status}
                immutable_json(out/'responses'/f'{i}_{role}.json', row[role])
            print(json.dumps({'done_train_mother': i+1, 'total': len(cases)}), flush=True)
            bank.append(row)
        counts = dict(db.execute('select status,count(*) from calls group by status'))
        assert not counts.get('reserved')
    immutable_json(out/'predictions.json', bank)
    settle(out, spec, cases, bank, prior, counts)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare','run'))
    run(parser.parse_args().phase == 'run')
