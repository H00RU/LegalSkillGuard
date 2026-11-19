"""Replay native ContractNLI citations when two roles use one original span."""

import json
from pathlib import Path
import sqlite3
from statistics import mean

import jsonschema

from experiments import convergence_revision5_cni_definition_membership as membership
from experiments import convergence_revision5_cni_linked_evidence as linked
from experiments import convergence_revision5_cni_signed_scope as signed
from experiments.convergence_pilot_b0 import BASE, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_maud_zero_evidence import response
from legal_skill_guard.paired_interfaces.control_answers import decode_native, source_bundle
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.client import request_payload
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision5_CNI_colocated_citation_20261119'
TABLE = ROOT / 'reports/legal_skill_convergence_20261117/paper/tables/REVISION5_CNI_COLOCATED_CITATION_20261119.json'


def canonical_citations(value):
    permission = list(dict.fromkeys(value['permission_spans']))
    definition = value['definition_span']
    # This field is for a separate definition. An inline reference still cites
    # the entire original permission span, including its local definition.
    return {**value, 'permission_spans': permission,
            'definition_span': None if definition in permission else definition}


def archived_stage(module, snapshot_field):
    stage = ROOT / read(module.POINTER)['artifact_root']
    binding = read(stage / 'binding.json')
    assert digest(binding) == stage.name
    for name, expected in binding[snapshot_field].items():
        assert sha(stage / 'source_snapshot' / name) == sha(ROOT / name) == expected
    return stage, binding


def archived_native(db, source, prior):
    trace, = (item for readout in prior['reads'] for item in readout['execution']['traces'])
    raw, wire = response(db, source['key'], trace['physical_call_id'])
    assert raw['finish_reason'] == 'stop' and raw['content'] == trace['raw_content']
    prompt, = (json.loads(message['content']) for message in wire['messages'] if message['role'] == 'user')
    bundle = source_bundle({**source, 'evidence_presentation': 'explicit_zero_based_spans'})
    assert prompt == {name: bundle[name] for name in ('answer_schema', 'public')}
    value = json.loads(raw['content'])
    jsonschema.validate(value, wire['response_format']['json_schema']['schema'])
    answers, citations = decode_native(linked.DATASET, bundle, value['value'])
    saved = prior['native'][linked.TASK]
    answer, evidence = answers[linked.TASK], citations[linked.TASK]
    assert answer == saved['answer'] and evidence == saved['evidence_sentence_ids']
    return answer, evidence


def linked_replay(db):
    stage, binding = archived_stage(linked, 'source_sha256')
    inputs = read(stage / 'cases.json')
    assert digest(inputs) == binding['pair_inputs_sha256']
    current, cases = linked.materials()
    assert current == binding and list(cases.values()) == inputs
    old = dict(zip(cases, read(stage / 'paired_reads.json'), strict=True))
    grade_path = ROOT / binding['grading_file']
    assert grade_path.parent.name == 'train' and sha(grade_path) == binding['grading_file_sha256']
    grades = read(grade_path)
    old_scores = linked.summarize(cases, old, grades)
    assert old_scores == read(stage / 'terminal.json')['scores']
    assets = dict(zip(binding['roles'], linked.disclosure.assets(), strict=True))
    normalized, changed, direct = {}, [], []
    for position, case in cases.items():
        source, view, spans = (case[k] for k in ('source', 'view', 'spans'))
        assert source['project_split'] == 'train'
        key = source['key']
        payload = {'document': view['public']['source_text'],
                   'native_spans': [{'id': i, 'text': span} for i, span in enumerate(spans)]}
        normalized[position] = {}
        for role, row in old[position].items():
            raw, wire = response(db, key, row['physical_call_id'])
            layout = linked.plan(assets[role], spans)
            _, schema, instructions = layout
            messages = [{'role': 'system', 'content': instructions},
                        {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}]
            assert wire == request_payload(binding['executor'], messages=messages, thinking=False, schema=schema)
            assert raw['finish_reason'] == 'stop'
            value = json.loads(raw['content'])
            jsonschema.validate(value, schema)
            new_value = canonical_citations(value)
            try:
                archived = linked.decode(layout, spans, raw['content'])
            except ValueError:
                assert new_value != value and not row['native']['wire_valid']
            else:
                assert archived == row['native']
            revised = linked.decode(layout, spans, json.dumps(new_value))
            normalized[position][role] = {**row, 'native': revised}
            if revised != row['native']:
                changed.append({'position': list(position), 'role': role,
                                'original_permission': value['permission_spans'],
                                'original_definition': value['definition_span'],
                                'normalized': revised})
        answer, evidence = archived_native(db, source, case['prior']['result'])
        direct.append(grade_view(linked.DATASET, view, grades[key][linked.TASK], answer, evidence))
    return {'terminal_sha256': sha(stage / 'terminal.json'), 'paired_responses': 2 * len(cases),
            'archived': old_scores, 'canonicalized': linked.summarize(cases, normalized, grades),
            'archived_native_reader': {'responses_verified': len(direct),
                                       'exact': sum(row['grade'] for row in direct),
                                       'evidence_f1': mean(row['evidence_f1'] for row in direct)},
            'changed': changed}


def other_citations(db):
    """Check whether the related multi-hypothesis readers returned duplicate IDs."""
    comparisons = {}
    for module, section, field in ((membership, 'definition_membership', 'sources'),
                                   (signed, 'signed_scope', 'sources_sha256')):
        stage, binding = archived_stage(module, field)
        if module is membership:
            cases = read(stage / 'case_material.json')
            assert digest(cases) == binding['ordered_cohort_sha256']
            queries = [module.query(case, role) for case in cases for role in sorted(module.ROLES)]
            assert digest(queries) == binding['wires_sha256']
        else:
            current, cases = module.materials()
            assert current == binding
            assets = dict(zip(module.ROLES, module.layouts()[1], strict=True))
        predictions = read(stage / 'predictions.json')
        count = duplicate_lists = 0
        for case, pair in zip(cases, predictions, strict=True):
            for role, record in pair.items():
                raw, wire = response(db, case['source'], record.get('physical_call_id', record.get('id')))
                if module is membership:
                    messages, schema = module.query(case, role)
                    assert module.decode(case, role, raw) == (record['predictions'], record['error'])
                else:
                    messages, schema = module.contract(assets[role], case)
                    assert module.decode(assets[role], case, raw) == record['answer']
                assert wire == request_payload(binding['executor'], messages=messages, thinking=False, schema=schema)
                assert raw['finish_reason'] == 'stop'
                value = json.loads(raw['content'])
                duplicate_lists += sum(len(ids) != len(set(ids)) for ids in value['evidence'].values())
                count += 1
        comparisons[section] = {'terminal_sha256': sha(stage / 'terminal.json'),
                                'physical_responses_verified': count, 'duplicate_evidence_lists': duplicate_lists}
    return comparisons


def run():
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        assert not ledger.get('reserved')
        evidence = linked_replay(db)
        secondary = other_citations(db)
        assert ledger == dict(db.execute('select status,count(*) from calls group by status'))
    result = {'status': 'settled_revision5_CNI_colocated_citation_TRAIN', 'partition': 'TRAIN',
              'new_model_requests': 0, 'continuous_ledger': ledger,
              'runner_sha256': sha(Path(__file__)), 'linked': evidence, 'other_comparisons': secondary}
    immutable_json(HOME / 'summary.json', result)
    immutable_json(TABLE, result)
    print(json.dumps({'status': result['status'], 'changed': evidence['changed'],
                      'archived_native_reader': evidence['archived_native_reader'],
                      'other_comparisons': secondary, 'continuous_ledger': ledger}), flush=True)


if __name__ == '__main__':
    run()
