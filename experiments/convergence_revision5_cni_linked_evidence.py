"""Compare fixed and synthesized recipient binding with typed cross-clause citations."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import sqlite3

import jsonschema

from experiments.convergence_formal_b1_observe import POINTER as FIRST_OBSERVE, load_roster
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import cni_disclosure_relational as disclosure
from legal_skill_guard.paired_interfaces import indexed_relational_read as indexed, residual
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, record_schema
from legal_skill_guard.skill_evolution.objects import digest


DATASET = 'ContractNLI'
ARM = 'common_teacher_skill_learning'
TASK = disclosure.TASK
HOME = BASE / 'revision5_CNI_linked_evidence_20261119'
POINTER = HANDOFF / 'revision5_CNI_linked_evidence_current.json'
DONE = 'completed_revision5_CNI_linked_evidence_TRAIN'
RUNNER = 'experiments/convergence_revision5_cni_linked_evidence.py'
DEFINITION = re.compile(
    r'\brepresentatives\b[”"’\')]|\brepresentatives\b.{0,18}\bshall\s+(?:mean|include)|'
    r'\brepresentatives\b.{0,18}\bmeans?\b', re.I)
USE = re.compile(r'\b(?:its|their|such|those|of\s+the)\s+Representatives\b|\bto\b.{0,35}\bRepresentatives\b', re.I)
ACT = re.compile(r'\b(?:reveal\w*|disclos\w*|provid\w*|given|access|shar\w*|divulg\w*)\b', re.I)
# Source-only reviews. The two linked permissions include the other party's receiving role.
# Internal sharing in B2 does not identify employees or use the defined Representatives class.
REVIEWS = {
    (1, 0): ('linked', 30, {58, 59}, {58, 59}),
    (2, 1): ('implicit', None, set(), set()),
    (3, 0): ('linked', 4, {13}, {11, 12, 13, 14, 15, 16, 17}),
    (6, 2): ('local', None, {10}, {10, 12}),
    (8, 0): ('local', None, {14}, {14}),
    (8, 1): ('local', None, {49}, {49}),
}
COMMON = (
    'Read who can share the same confidential information, what class of people may receive it, and the '
    'legal force of the provision. Read the full contract with original zero-based native span IDs. '
    'For each span reference, use the ID from the input. In permission_spans cite the operative language '
    'for the permission or prohibition. Include its lead-in if it supplies a subject or an exception. '
    'When that provision uses a defined recipient class and employee membership depends on the separate '
    'definition, cite the definition in definition_span. Otherwise set definition_span to null. '
    'Resolve the group as used by that permission, including its possessor and any role limits. '
    'A definition elsewhere, a disclosure by a different actor, or a duty to notify someone is not a grant. '
    'Preserve unknown facts. Cite only the spans needed to support the reading. Return the provided JSON object.'
)


def span_inventory(view):
    public = view['public']
    text = public['source_text']
    return [text[a:b] for a, b in public['sentence_spans']]


def in_cohort(spans):
    normalized = [' '.join(span.split()) for span in spans]
    return (any(DEFINITION.search(s) and re.search(r'\bemployees?\b', s, re.I) for s in normalized)
            and any(ACT.search(s) and USE.search(s) for s in normalized))


def plan(asset, spans):
    fields, values = indexed.encoded_relations(asset)
    variants = tuple(values.values())
    choices = {name: {'enum': list(dict.fromkeys(row[name] for row in variants))} for name in fields}
    span = {'type': 'integer', 'minimum': 0, 'maximum': len(spans)-1}
    cited = {'type': 'array', 'items': span, 'maxItems': 3}
    schema = record_schema({'relations': record_schema(choices), 'permission_spans': cited,
                            'definition_span': {'anyOf': [span, {'type': 'null'}]}})
    instructions = '\n'.join(residual.reader_prompt(asset, verbalize_relations=True).splitlines()[4:])
    return asset, schema, COMMON+'\n'+instructions


def decode(layout, spans, reply):
    asset, schema, _ = layout
    raw = json.loads(reply)
    jsonschema.validate(raw, schema)
    permission = raw['permission_spans']
    definition = raw['definition_span']
    evidence = [*permission, *([definition] if definition is not None else [])]
    if len(set(evidence)) != len(evidence) or any(not spans[i].strip() for i in evidence):
        raise ValueError('Each evidence ID must denote a distinct nonempty original span')
    outcome = residual.decode(asset, raw['relations'], {}, module_binding=asset['module_binding'])
    if not outcome['valid']:
        raise ValueError('The recorded reading is outside the certified domain')
    answer = outcome['outputs']['classification']
    if answer is not None and not permission:
        raise ValueError('An operative conclusion requires at least one cited permission span')
    return {'answer': answer, 'evidence': sorted(evidence) if answer is not None else [],
            'permission_spans': permission, 'definition_span': definition, 'wire_valid': True}


def preflight(assets):
    module = disclosure.module()
    for state in module.states:
        expect = disclosure.consume(state, {})['classification']
        for asset in assets:
            reading = residual.encode(asset['features'], state)
            actual = residual.decode(asset, reading, {}, module_binding=asset['module_binding'])['outputs']['classification']
            if actual != expect:
                raise ValueError('The linked-evidence wire must preserve the original finite consumer')


def materials():
    root = ROOT/read(BOOTSTRAP)['artifact_root']
    study = read(root/'binding.json')
    roster = load_roster(study)
    journal = TrainingJournal(root, study, roster)
    cases, archived = {}, []
    grade = {}
    for batch, group in enumerate(roster, 1):
        sources = [s for s in group if s['dataset'] == DATASET]
        stage = ROOT/read(FIRST_OBSERVE if batch == 1 else observe_pointer(batch))['artifact_root']
        prior = read(stage/'binding.json')
        path = prior['native_grade_paths'][DATASET]
        grade[path] = prior['native_grade_sha256'][path]
        receipt = journal._observations(ARM, batch)
        archived.append(sha(stage/'terminal.json'))
        for ordinal, source in enumerate(sources):
            view, = (v for v in source['views'] if v['id'] == TASK)
            spans = span_inventory(view)
            if not in_cohort(spans):
                continue
            record = read(journal.directory(ARM, batch)/'predictions'/(digest(source['key'])+'.json'))
            if digest(record) != receipt['predictions'][source['key']] or source['project_split'] != 'train':
                raise ValueError('The common-program evidence must bind the verified original TRAIN observation')
            cases[batch, ordinal] = {'source': source, 'view': view, 'spans': spans, 'prior': record}
    if set(cases) != set(REVIEWS):
        raise ValueError('Reconcile the source-reviewed cohort before issuing a request')
    grade_path, = grade
    paths = {RUNNER,
             'legal_skill_guard/paired_interfaces/cni_disclosure_relational.py',
             'legal_skill_guard/paired_interfaces/indexed_relational_read.py',
             'legal_skill_guard/paired_interfaces/residual.py',
             'legal_skill_guard/rr/client.py',
             'legal_skill_guard/skill_evolution/clients.py',
             'legal_skill_guard/skill_evolution/ledger.py',
             'legal_skill_guard/skill_evolution/native.py'}
    for pos, case in cases.items():
        group, definition, required, allowed = REVIEWS[pos]
        if definition is not None and (not DEFINITION.search(' '.join(case['spans'][definition].split()))
                                       or not re.search(r'\bemployees?\b', case['spans'][definition], re.I)):
            raise ValueError('Membership audit no longer binds the original text')
        if not all(case['spans'][i].strip() for i in allowed) or not required <= allowed:
            raise ValueError('Permission audit must bind original nonempty native spans')
        assert group in ('linked', 'local') if required else group == 'implicit'
    binding = {'study': 'revision5_CNI_linked_citation_TRAIN', 'executor': study['executor'],
               'ordered_original_train_sha256': study['TRAIN_ordered_batches_sha256'],
               'original_observation_terminal_sha256': archived,
               'roles': ['fixed_coordinates', 'synthesized_binding'],
               'pair_inputs_sha256': digest(list(cases.values())), 'paired_calls': 2*len(cases),
               'grading_file': grade_path, 'grading_file_sha256': grade[grade_path],
               'primary_metric': 'unconditional evidence F1',
               'qualification': 'retain native exact and source-grounded permission',
               'source_sha256': {p:sha(ROOT/p) for p in sorted(paths)}, 'TRAIN_only': True}
    return binding, cases


def outputs_for(case, assets, reader, run_id):
    source, view, spans = (case[k] for k in ('source','view','spans'))
    payload = {'document': view['public']['source_text'],
               'native_spans': [{'id': i, 'text': text} for i, text in enumerate(spans)]}
    user = json.dumps(payload, ensure_ascii=False)
    for role, asset in zip(('fixed_coordinates', 'synthesized_binding'), assets, strict=True):
        layout = plan(asset, spans)
        _, schema, instructions = layout
        call_id = f'{run_id}:{digest(source["key"])}:{role}'
        result = reader.generate(call_id, source=source['key'], purpose='skill_actor', thinking=False,
                                 messages=[{'role':'system','content':instructions},{'role':'user','content':user}],
                                 schema=schema)
        try:
            if result['finish_reason'] != 'stop':
                raise ValueError('A nonterminal read cannot supply grounded evidence')
            output = decode(layout, spans, result['content'])
        except (ValueError, jsonschema.ValidationError):
            output = {'answer':None, 'evidence':[], 'permission_spans':[], 'definition_span':None, 'wire_valid':False}
        yield role, {'physical_call_id':call_id, 'native': output}


def summarize(cases, values, grade):
    scores = defaultdict(list)
    for pos, case in cases.items():
        group, definition, required, allowed = REVIEWS[pos]
        native = grade[case['source']['key']][TASK]
        for role, record in values[pos].items():
            out = record['native']
            found = set(out['permission_spans'])
            grounded = (out['wire_valid'] and out['answer'] == 'Entailment' and bool(required) and
                        required <= found <= allowed and out['definition_span'] == definition)
            scored = grade_view(DATASET, case['view'], native, out['answer'], out['evidence'])
            scores[role].append({'stratum':group, 'exact':bool(scored['grade']), 'f1':scored['evidence_f1'],
                                 'grounded_permission':grounded, 'wire_valid':out['wire_valid'],
                                 'resolved':out['answer'] is not None})
    return dict(scores)


def run(execute):
    binding, cases = materials()
    assets = disclosure.assets()
    preflight(assets)
    stage = HOME/digest(binding)
    if (stage/'terminal.json').exists():
        print(json.dumps(read(stage/'terminal.json'),sort_keys=True),flush=True)
        return
    if execute and (not POINTER.exists() or ROOT/read(POINTER)['artifact_root'] != stage):
        raise ValueError('Prepare one exact binding before dispatch')
    immutable_json(stage/'binding.json', binding)
    immutable_json(stage/'cases.json', list(cases.values()))
    if not execute:
        if POINTER.exists() and read(POINTER)['status'] == 'running':
            raise ValueError('Leave the live comparison bound')
        write_status(stage, {'status':'prepared','planned_calls':binding['paired_calls']}, POINTER)
        print(json.dumps({'stage':str(stage.relative_to(ROOT)), 'pairs':len(cases)}),flush=True)
        return
    for p, version in binding['source_sha256'].items():
        dest = stage/'source_snapshot'/p
        dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():
            with dest.open('xb') as stream:
                stream.write((ROOT/p).read_bytes())
        if sha(dest) != version:
            raise ValueError('The execution binding requires the exact archived sources')
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status = 'reserved'").fetchone():
            raise ValueError('Reconcile the existing reservation before dispatch')
    run_id = 'convergence-revision5-CNI-linked-'+stage.name[:16]
    ids = [c['source']['key'] for c in cases.values()]
    ledger = EvolutionLedger(LEDGER,run_id=run_id,sources={'train':ids,'dev':[],'test':[]},binding=binding)
    reader = FrozenExecutor(ledger,stage,binding['executor'])
    reader.readiness()
    values = {}
    write_status(stage,{'status':'running','completed_pairs':0},POINTER)
    for pos, case in cases.items():
        values[pos] = dict(outputs_for(case,assets,reader,run_id))
        write_status(stage,{'status':'running','completed_pairs':len(values)},POINTER)
    immutable_json(stage/'paired_reads.json', list(values.values()))
    grade = ROOT/binding['grading_file']
    if sha(grade) != binding['grading_file_sha256']:
        raise ValueError('The original TRAIN grader must remain bound')
    with ledger.transaction() as db:
        rows = db.execute('select id,status,result from calls where id like ?', (run_id+':%',)).fetchall()
    physically_settled = {i:json.loads(r) for i,s,r in rows if s=='completed'}
    requested = {r['physical_call_id'] for pair in values.values() for r in pair.values()}
    if set(physically_settled) != requested or len(requested) != binding['paired_calls']:
        raise ValueError('Only the matched settled physical reads enter the comparison')
    done = {'status':DONE, 'scores':summarize(cases, values, read(grade)), 'executor_calls':len(requested),
            'executor_tokens':sum(r['usage']['total_tokens'] for r in physically_settled.values()),
            'new_teacher_calls':0,'DEV_or_TEST_opened':False,
            'native_hypothesis':TASK, 'same_complete_document_and_public_spans':True}
    immutable_json(stage/'terminal.json',done)
    write_status(stage,{'status':DONE,'physical_reads':len(requested)},POINTER)
    print(json.dumps(done,sort_keys=True),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','run'))
    run(parser.parse_args().phase=='run')
