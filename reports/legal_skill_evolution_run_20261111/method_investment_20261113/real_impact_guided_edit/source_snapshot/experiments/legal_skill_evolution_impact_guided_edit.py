"""One fixed real TRAIN repair with/without the learned impact requirements.

Both teachers receive the same library, real history/graphs, source feedback and
edit capacity. The generated footprint is additional derived input to U only.
No new source, model profile, executor request or full experiment is introduced.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

import jsonschema

from experiments import legal_skill_evolution_source_gap_acquisition as e
from experiments import legal_skill_evolution_impact_scope_learning as learning
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import observe
from legal_skill_guard.skill_evolution.relational_rules import language_identity
from legal_skill_guard.skill_evolution.repair_impact_learning import generation_scope
from legal_skill_guard.skill_evolution.scoped_grammar import CONSTRUCTOR, constructors
from legal_skill_guard.skill_evolution.source_composition import validate_renderers, validate_template_constructors
from legal_skill_guard.skill_evolution.source_effect_update import function_update
from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION, PROGRAM_INSTRUCTION, pack_programs, unpack_programs


RUN = 'legal_skill_evolution_impact_guided_edit_20261114'
OUT = e.ROOT / 'artifacts' / RUN
ARMS = ('ImpactGuided', 'FreeHistory')
BASE = e.OUT / 'unbound_provenance_replay/library.json'
SCHEMA = record_schema({'rationale': {'type': 'string'},
    'new_constructors': {'type': 'array', 'items': CONSTRUCTOR},
    'source_functions': {'type': 'array', 'items': {'type': 'string'}},
    'decision_functions': {'type': 'array', 'items': {'type': 'string'}},
    'composition_json': {'type': ['string', 'null']},
    'renderers_json': {'type': ['string', 'null']},
    'selected_rule_ids': {'type': ['array', 'null'], 'items': {'type': 'string'}}})


class NoCalls:
    def generate(self, *args, **kwargs):
        raise AssertionError('This actual source path needs no executor request')


def rows():
    with sqlite3.connect('file:' + str(e.previous.prior.prior.LEDGER) + '?mode=ro', uri=True) as db:
        return db.execute('select * from calls order by id').fetchall()


def target_event():
    path = next((e.OUT / 'unbound_pure_preview/ConstraintAcquire').glob('*62fd*.json'))
    original = e.read(path)
    terms = original['actual']['execution']['source_output']['statements']
    norms = [(i, r) for i, r in enumerate(terms) if r['term'][0] == 'prohibition' and r['support_ids'] == [31]]
    assert len(norms) == 2 and norms[0][1]['term'][:4] == norms[1][1]['term'][:4]
    assert norms[0][1]['term'][4][0] == 'add_exception' and norms[1][1]['term'][4] == ['no_exceptions']
    actor = norms[0][1]['term'][1]
    assert actor[0] == 'participant_union' and len(actor) == 3
    units = original['observation']['visible_inputs']['units']
    source = next(u for u in units if u['id'] == 31)
    assert 'except as expressly authorized in writing' in source['text'] and 'as required to analyze' in source['text']
    proof = [learning.ref(path, ['actual', 'execution', 'source_output', 'statements', i]) for i, _ in norms]
    unit_index = next(i for i, u in enumerate(units) if u['id'] == 31)
    proof.append(learning.ref(path, ['observation', 'visible_inputs', 'units', unit_index]))
    event = learning.event('prospective_qualified_prohibition', 'not_yet_edited', [original['source']])
    learning.node(event, 'qualification', 'source_constraint', 'condition', proof, seed=True)
    learning.node(event, 'qualified_actors', 'legal_group', 'qualified_group', proof)
    learning.edge(event, 'qualification', 'qualified_actors', 'qualifies_group', proof)
    for mi, member in enumerate(actor[1:]):
        key = 'member:' + str(mi)
        learning.node(event, key, 'legal_participant', 'member', proof)
        learning.edge(event, 'qualified_actors', key, 'has_member', proof)
    for ri, (index, row) in enumerate(norms):
        key = 'norm:' + str(ri)
        learning.node(event, key + ':condition', 'legal_field', 'condition', proof)
        learning.node(event, key + ':actor', 'legal_field', 'actor', proof, value=row['term'][1], supported=True)
        for mi in range(len(actor) - 1):
            learning.edge(event, 'member:' + str(mi), key + ':condition', 'has_condition', proof)
            learning.edge(event, 'member:' + str(mi), key + ':actor', 'has_actor', proof)
        if row['term'][4] == ['no_exceptions']:
            next(n for n in event['graph']['nodes'] if n['id'] == key + ':condition')['counterevidence'] = {
                'evidence_ref': proof,
                'judgment': 'The expressly qualified restriction cannot simultaneously assert an unconditional restriction on the same actors/action under this same clause.'}
    event['partial_source_review'] = {'source': original['source'], 'unit_id': 31,
        'quote': source['text'], 'forbidden_unconditional_norm': norms[1][1],
        'supported_existing_qualified_norm': norms[0][1],
        'partial_only': True, 'unreviewed_fields_are_not_false': True}
    assert not event['judgments']
    learning.check_refs(event)
    return event


def task_data():
    protocol = e.read(e.OUT / 'protocol.json')
    keys = protocol['acquisition_sources']
    public = {r['key']: r for r in e.read(e.previous.prior.prior.PUBLIC)}
    assert all(public[k]['split'] == 'train' for k in keys)
    event = target_event()
    history = e.read(learning.OUT / 'actual_events.json')
    model = e.read(learning.OUT / 'learned_impact.json')
    for h in history:
        assert event['mother_sources'][0] not in h['mother_sources']
    tasks = []
    for key in keys:
        record = e.read(e.OUT / 'unbound_pure_preview/ConstraintAcquire' / e.name_for(key))
        pub, units, _ = e.previous.prior.prior.source_material(e.previous.PARENT, public, key)
        tasks.append({'source_id': key, 'source_text': pub['source_text'], 'units': units,
            'actual_before_feedback': record['actual']['feedback'],
            'role': 'repair' if key == event['mother_sources'][0] else 'previously_fixed_retention_context'})
    semantic_history = [e.read(learning.IMPACT / 'actual_e82b_action_specific_source_repair.json'),
        e.read(learning.IMPACT / 'actual_MAUD_inquiry_target_repair.json')]
    task = {'actual_current_library': e.read(BASE), 'tasks': tasks,
        'actual_historical_impact_graphs_and_reviews': history,
        'historical_concrete_semantic_and_component_observations': semantic_history,
        'current_source_program_dependency_graph': event,
        'unknown_or_unreviewed_is_not_false_or_a_keep_invariant': True,
        'not_an_independent_acquisition_comparison': True}
    return protocol, keys, public, task, generation_scope(model, event)


COMMON = '''Repair one actual source defect in the supplied current acquired library.
Both arms have the same actual full source texts, source/program library, actual
before executions, historical real repairs/graphs/feedback and full joint edit
capacity. All are original TRAIN. Do not use tools, external data, TEST, source
or company ID branches, native-label output in source code, or invented cases.
The current repair target is a real coexisting qualified and unconditional
prohibition from the SAME expressly qualified source clause. The unconditional
assertion loses actual written-authorization and purpose exceptions. Correct
the current actual path while retaining valid source-supported abilities. Do
not reverse a prohibition into a permission or infer an unstated disposal duty.
Native answers may remain unchanged: the consumer currently ignores this
exception distinction. Source correctness, actual mechanism use, preservation
and costs will be reported separately. Unreviewed is unknown, not negative.

Return complete pure Python function definitions replacing/adding actual
functions in source_program and/or spec.decision_program; [] leaves that module
unchanged. Shared helpers may be replaced. New constructors require truthful
meanings and types. composition_json can be a complete replacement language
JSON object; renderers_json a complete replacement renderer array; null retains
each. selected_rule_ids null retains existing selection. Full joint revisions
are allowed, but only make necessary justified changes; do not rewrite a whole
module merely to restate unchanged helpers. Source apply(inputs,premises) sees
source_text, source_spans (id,text), and the common source_output. Preserve the
current pure interface and exact evidence. No imports, nested def, lambdas,
network/files, exceptions-as-defaults, guessed missing rules or fallback answers.
All new candidate outputs must pass the existing nominal types and actual
execution. You may freely use or improve on all historical repair strategies,
source graphs, full correct patches and semantic checks in the supplied history.
'''


def prepare():
    if (OUT / 'protocol.json').exists():
        return e.read(OUT / 'protocol.json')
    old, keys, public, task, scope = task_data()
    assert not any(r[6] == 'reserved' for r in rows())
    assert not e.strict_output_schema_issues(SCHEMA)
    base = task['actual_current_library']
    function_update(base['source_program'], []); function_update(base['spec']['decision_program'], [])
    assert unpack_programs(pack_programs(task)) == task
    assert any(r['role'] == 'condition' for r in scope['recheck'])
    assert len(scope['preserve_supported']) == 2
    immutable_json(OUT / 'common_task.json', task)
    immutable_json(OUT / 'learned_generation_scope.json', scope)
    immutable_json(OUT / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in rows()})
    files = [Path(__file__), Path(learning.__file__),
        *sorted((e.ROOT / 'legal_skill_guard/skill_evolution').glob('*.py')),
        e.ROOT / 'tests/test_skill_evolution_repair_impact_learning.py',
        e.ROOT / 'tests/test_skill_evolution_repair_impact_contracts.py']
    p = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'acquisition_sources': keys, 'target_source': task['current_source_program_dependency_graph']['mother_sources'][0],
        'history_sources': sorted({s for h in task['actual_historical_impact_graphs_and_reviews'] for s in h['mother_sources']}),
        'executor_profile': old['executor_profile'], 'teacher_profile': old['teacher_profile'],
        'planned_independent_teacher_edits': 2, 'planned_executor_requests': 0,
        'same_information_history_and_joint_edit_capacity': True,
        'derived_impact_requirements_added_only_to_ImpactGuided': True,
        'training_graph_annotations_shared_and_offline_origin_disclosed': True,
        'no_new_full_training_DEV_TEST_or_paper': True,
        'source_sha256': {str(f.relative_to(e.ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        'data_sha256': {str(f.relative_to(e.ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in [OUT / 'common_task.json', OUT / 'learned_generation_scope.json', learning.OUT / 'learned_impact.json']}}
    assert all(s in public and public[s]['split'] == 'train' for s in p['history_sources'])
    for f in files:
        target = OUT / 'source_snapshot' / f.relative_to(e.ROOT)
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(f.read_bytes())
    immutable_json(OUT / 'protocol.json', p)
    return p


def setup():
    p = prepare()
    for name, value in {**p['source_sha256'], **p['data_sha256']}.items():
        assert hashlib.sha256((e.ROOT / name).read_bytes()).hexdigest() == value, name
    ledger = EvolutionLedger(e.previous.prior.prior.LEDGER, run_id=RUN,
        sources={'train': sorted(set(p['acquisition_sources'] + p['history_sources'])), 'dev': [], 'test': []}, binding=digest(p))
    return p, ledger


def request(arm):
    p, ledger = setup(); task = e.read(OUT / 'common_task.json')
    system = COMMON
    if arm == 'ImpactGuided':
        task['learned_impact_generation_requirements'] = e.read(OUT / 'learned_generation_scope.json')
        system += '\nUse the actual learned impact requirements when constructing and checking the edit. Recheck does not require changing a still-correct value; preserve refers to semantics, not old AST.\n'
    else:
        system += '\nUse the full real history, graphs, source feedback and correct patches freely to independently determine repair impact and the best repair.\n'
    system += INSTRUCTION + '\n' + PROGRAM_INSTRUCTION
    system += '\nAllowed pure attributes: ' + ','.join(sorted(e.METHODS))
    system += '\nAllowed pure calls: ' + ','.join(sorted(e.CALLS))
    user = json.dumps(pack_programs(task), ensure_ascii=False, separators=(',', ':'))
    size = len(e.render_structured_codex_prompt(system, user))
    assert size <= e.CODEX_TURN_INPUT_CHARACTER_LIMIT
    immutable_json(OUT / arm / 'preflight.json', {'request_characters': size,
        'schema_issues': e.strict_output_schema_issues(SCHEMA),
        'common_task_sha256': digest(e.read(OUT / 'common_task.json')),
        'generation_scope_consumed': arm == 'ImpactGuided'})
    return p, ledger, {'source_ids': sorted(set(p['acquisition_sources'] + p['history_sources'])),
        'system_prompt': system, 'user_prompt': user, 'output_schema': SCHEMA}


def acquire_one(arm):
    if (OUT / arm / 'teacher.json').exists():
        return
    p, ledger, args = request(arm)
    result = FrozenTeacher(ledger, OUT, p['teacher_profile']).propose(RUN + ':' + arm + ':teacher', **args)
    immutable_json(OUT / arm / 'teacher.json', result)
    print(json.dumps({'arm': arm, 'actual_teacher_edit_saved': True}), flush=True)


def compile_edit(raw):
    jsonschema.validate(raw, SCHEMA)
    library = deepcopy(e.read(BASE))
    library['spec']['constructors'].extend(raw['new_constructors']); constructors(library['spec'])
    library['source_program'] = function_update(library['source_program'], raw['source_functions'])
    library['spec']['decision_program'] = function_update(library['spec']['decision_program'], raw['decision_functions'])
    if raw['composition_json'] is not None:
        library['language'] = json.loads(raw['composition_json'])
    if raw['renderers_json'] is not None:
        library['renderers'] = json.loads(raw['renderers_json'])
    if raw['selected_rule_ids'] is not None:
        library['selected_rule_ids'] = raw['selected_rule_ids']
    language_identity(library['language']); validate_renderers(library['language'], library['renderers'])
    validate_template_constructors(library['renderers'], library['spec'])
    assert set(library['selected_rule_ids']) <= {r['id'] for r in library['language']['rules']}
    return library


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['preflight', 'acquire'])
    phase = parser.parse_args().phase
    with (e.ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        for arm in ARMS:
            request(arm)
        if phase == 'acquire':
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(acquire_one, ARMS))


if __name__ == '__main__':
    main()
