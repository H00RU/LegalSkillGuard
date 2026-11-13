"""No-model replay of one genuine installed TRAIN edit through learned U.

This is an implementation/boundary check with shared acquired declarations,
not unseen-source acquisition or evidence of independent method advantage.
It never launches a lawyer/teacher, full training, DEV or TEST.
"""
import argparse
import ast
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.joint_updates import learn, learn_guard, apply, candidates, _fragment, _walk, _tree
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.source_effect_update import function_update
from legal_skill_guard.skill_evolution.span_compiler import execute_json, occurrences, validate_procedure
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION, pack
from experiments.legal_skill_evolution_role_TRAIN import physical_snapshot

ROOT = Path(__file__).resolve().parents[1]
RUN = 'legal_skill_evolution_joint_update_real_replay_20261113'
LEGAL_RUN = 'legal_skill_evolution_joint_update_legal_annotation_20261113'
read = lambda path: json.loads(Path(path).read_text())


def paths(code, value):
    return [[*p, 'fields', 'value'] for p, n in _walk(_fragment(code))
            if n['ast'] == 'Constant' and type(n['fields']['value']) is type(value)
            and n['fields']['value'] == value]


def run():
    folder = ROOT / 'artifacts' / RUN
    inventory_path = ROOT / 'reports/legal_skill_evolution_run_20261111/semantic_learning_evidence/real_revision_inventory.json'
    inventory = read(inventory_path)
    event = next(e for e in inventory['fixed_Full_revision_proposals']
        if e['batch'] == 6 and e['skill_id'] == 'domestic_main_or_first_bag_total')
    if not event['installed_version_changed']:
        raise ValueError('A rejected/unchanged proposal cannot become an installed positive edit')
    old, new = event['old'], event['installed_new']
    source = new['premises']['domestic_economy_base_schedule']['origin']['source_id']
    public = {s['key']: s for s in read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    if source not in public or public[source]['split'].lower() != 'train':
        raise ValueError('Only the actual original TRAIN event is allowed')
    view = public[source]['views'][0]; text = view['public']['source_text']
    before_counts = physical_snapshot(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3')
    signatures = {'declared_field': ['role', 'field'], 'source_scalar': ['role', 'weight'],
        'interface_label': ['role', 'label']}
    facts = []; slots = {}; evidence = []; roles = []
    old_literals = [n.value for n in ast.walk(ast.parse(old['procedure'])) if isinstance(n, ast.Constant)]
    extras = []
    for n in ast.walk(ast.parse(new['procedure'])):
        if isinstance(n, ast.Constant) and not any(type(n.value) is type(v) and n.value == v for v in old_literals):
            if not any(type(n.value) is type(v) and n.value == v for v in extras):extras.append(n.value)
    for i, value in enumerate(extras):
        if isinstance(value, str) and value in {*new['inputs'], *new['premises']}:
            predicate, sort, role = 'declared_field', 'field', value
            declaration = new['inputs'].get(value, new['premises'].get(value))
            if value in new['premises']:
                origin = declaration['origin']
                if not occurrences(text, origin['quote']):
                    raise ValueError('A declaration does not quote the current policy')
            evidence.append({'role': role, 'basis': 'actual acquired field declaration',
                'declaration': declaration})
        elif type(value) in (int, float):
            candidates = [(k, v) for k, v in old['premises'].items()
                if type(v.get('value')) is type(value) and v.get('value') == value
                and occurrences(text, v['origin']['quote'])]
            if len(candidates) != 1:
                raise ValueError('A new literal needs a unique actual source scalar')
            role, declaration = candidates[0]; predicate, sort = 'source_scalar', 'weight'
            evidence.append({'role': role, 'basis': 'actual scalar declaration and current verbatim policy',
                'declaration': declaration})
        else:
            # These spellings are current acquired input categories. They are
            # not task answers or invented current legal values.
            if not isinstance(value, str):raise ValueError('Unsupported new program literal')
            current_question = new['inputs']['route_fee_region']['question']
            if not occurrences(text, value) and not occurrences(current_question, value):
                raise ValueError('A label spelling is absent from the source/input declaration')
            role = value; predicate, sort = 'interface_label', 'label'
            evidence.append({'role': role, 'basis': 'verbatim source or acquired input-choice spelling'})
        roles.append(role);facts.append({'predicate': predicate, 'arguments': [role, value]})
        slots['parameter_' + str(i)] = {'sort': sort, 'positions': [[i, 1]],
            'before_paths': paths(old['procedure'], value), 'after_paths': paths(new['procedure'], value)}
    example = {'event_id': 'actual_Full_B6_installed_airline_update', 'source_facts': facts,
        'source_slots': slots, 'before': old['procedure'], 'after': new['procedure']}
    update = learn([example], signatures, source_constants={'role': roles})
    update = learn_guard(update, [example], [], [])
    result = apply(update, facts, old['procedure'])
    if result['status'] != 'applied':raise ValueError('The real installed edit did not instantiate')
    validate_procedure(result['program'])
    # The comparison isolates update execution. It gives ordinary patch reuse
    # the same current declarations, whole real repair and source information.
    baseline = function_update(old['procedure'], [new['procedure']])
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        reads = []
        for call, raw in db.execute("select id,result from calls where source=? and role='executor' and status='completed' order by reserved_at", (source,)):
            record = json.loads(raw)
            if 'route_fee_region' not in record.get('content', ''):continue
            value = json.loads(record['content'])
            if set(new['inputs']) <= set(value) and all(value[k].get('status') == 'known' for k in new['inputs']):
                reads.append((call, {k: value[k]['value'] for k in new['inputs']}))
    if len(reads) != 1:raise ValueError('Need the actual unambiguous cached actor reading, not inferred case inputs')
    call, inputs = reads[0]
    grading = read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')[source]
    annotation = grading[view['id']]
    results = {}
    for arm, code, spec in [('NoUpdate', old['procedure'], old), ('JointU', result['program'], new),
                             ('FullRepairReuse', baseline, new)]:
        premises = {k: deepcopy(v['value']) for k, v in spec['premises'].items()}
        output = execute_json(code, inputs, premises)
        results[arm] = {'output': output, 'score': grade_view('RuleArena_Airline', view, annotation, output['answer'])}
    if results['JointU'] != results['FullRepairReuse']:
        raise ValueError('The learned implementation differs from the same-information actual repair')
    after_counts = physical_snapshot(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3')
    if before_counts != after_counts:raise ValueError('An offline replay must not append model requests')
    receipt = {'source': source, 'event': example['event_id'], 'new_model_requests': 0,
        'actual_prior_actor_request': call, 'shared_acquisition_and_reader_information': True,
        'independent_unseen_source_or_acquisition_evidence': False,
        'independent_method_advantage': False, 'guard_negative_examples': 0,
        'scope': 'same-policy actual installed TRAIN edit replay; not the primary legal contribution result',
        'actual_application': result, 'results': results,
        'ledger_before': before_counts, 'ledger_after': after_counts,
        'before_sha256': digest(old), 'installed_after_sha256': digest(new)}
    immutable_json(folder / 'source_code_example.json', example)
    immutable_json(folder / 'source_binding_evidence.json', evidence)
    immutable_json(folder / 'learned_update.json', update)
    immutable_json(folder / 'actual_replay_result.json', receipt)
    print(json.dumps({k: v for k, v in receipt.items() if k in ('new_model_requests',
        'independent_method_advantage', 'results', 'scope')}, ensure_ascii=False))


def acquire_legal(*, preflight=False):
    """One real teacher acquisition of legal source/code correspondence.

    Uses only the same six already supplied TRAIN mothers. It cannot see the
    fixed reuse pair, DEV/TEST or new cases. A concrete missing relation is a
    valid diagnosis, not a fabricated edit or a new research direction.
    """
    folder = ROOT / 'artifacts' / LEGAL_RUN
    if (folder / 'teacher.json').exists():
        print('Existing paid legal annotation preserved; no duplicate teacher request');return
    current = ROOT / 'artifacts/legal_skill_evolution_open_acquisition_semantic_route_absence_encoded_20261113'
    protocol = read(current / 'protocol.json');sources = protocol['acquisition_sources']
    task_path = folder / 'teacher_input.json'
    if task_path.exists():
        task = read(task_path)
    else:
        public = {s['key']: s for s in read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
        observations = []
        for arm in ('ConstraintAcquire', 'FreeUpdate'):
            for key in sources:
                path = current / 'acquisition' / arm / 'observations' / (key.replace(':', '_') + '.json')
                if not path.exists():continue
                observation = read(path)
                # The full source and actual judgments are retained. The
                # typed pattern interface uses actual non-JSON base facts;
                # omitted redundant JSON triples are not invented negatives.
                facts = [f for f in observation['context']['facts'] if not f['predicate'].startswith('json_')
                    and f['predicate'] not in ('source_text', 'unit_text', 'evidence_quote')]
                observations.append({'source': key, 'arm': arm,
                    'visible_inputs': observation['visible_inputs'], 'actual_pattern_facts': facts})
        previous = ROOT / 'artifacts/legal_skill_evolution_open_acquisition_native_loss_20261113'
        pairs = []
        for arm in ('ConstraintAcquire', 'FreeUpdate'):
            old = read(previous / arm / 'learned.json');new = read(current / arm / 'compiled.json')
            for name in ('planner_program', 'composition_program'):
                if name in old and name in new and old[name] != new[name]:
                    pairs.append({'event_id': arm + '_semantic_route_v3_' + name,
                        'arm': arm, 'component': name, 'before': old[name], 'after': new[name]})
            if old['spec']['decision_program'] != new['spec']['decision_program']:
                pairs.append({'event_id': arm + '_semantic_route_v3_decision', 'arm': arm,
                    'component': 'decision_program', 'before': old['spec']['decision_program'],
                    'after': new['spec']['decision_program']})
        from legal_skill_guard.skill_evolution.source_observations import signatures
        task = {'objective': 'Produce one executable legal source/code update example for the supplied joint PBE learner; if actual witnessed relations are insufficient, specify exactly the necessary acquired source relation and observation program.',
            'learner_source': (ROOT / 'legal_skill_guard/skill_evolution/joint_updates.py').read_text(),
            'software_interface_examples_not_legal_evidence': (ROOT / 'tests/test_skill_evolution_joint_updates.py').read_text(),
            'actual_same_seed_revision_pairs': pairs,
            'original_TRAIN_sources': [public[k] for k in sources],
            'actual_observations': observations,
            'source_signatures': {k: v['arguments'] for k, v in signatures().items()
                if not k.startswith('json_') and k not in ('source_text', 'unit_text', 'evidence_quote')},
            'acquired_constructor_definitions': read(current / 'ConstraintAcquire/compiled.json')['spec']['constructors'],
            'known_boundary': 'One genuine Airline edit has been learned/replayed, but full repair reuse is identical. That is implementation evidence only. We need the legal source/target relation, not just renamed ports or copied repair text.',
            'no_reuse_pair_DEV_TEST_or_new_sources': True}
        task = json.loads(json.dumps(task, ensure_ascii=False, sort_keys=True))
        immutable_json(task_path, task)
    schema = record_schema({'status': {'type': 'string', 'enum': ['annotated_real_edit', 'needs_source_relations']},
        **{k: {'type': 'string'} for k in ('examples_json', 'source_signatures_json', 'source_constants_json',
            'candidate_guards_json', 'positive_application_json', 'negative_application_json',
            'new_required_observations_json', 'rationale')}})
    system = '''You are the existing legal skill teacher, acquiring a concrete source-conditioned update program for the current C/U methods. Do not use tools. No new research direction, new/synthetic cases, native labels as source facts, source-ID applicability tests, or invented legal rules.
The supplied before/after pairs are actual same-seed legal program revisions. Select ONE supported local AST edit (or a small genuinely corresponding group) from these pairs. Examples must use actual before/after subtrees, actual source_facts selected verbatim from a supplied source's actual_pattern_facts, and source_slots with exact nominal types, witnessed argument positions, and actual AST paths. Include source_key and parent_revision_event_id in each example for provenance. A source role used by the new code must be genuinely source-specific and observed, not merely a global constructor/API name. Equal spellings alone do not establish legal identity. All current source/code parameter values must come from those observations. New program constants must not smuggle current actors, law values or missing meanings. Preserve unknown/unread as unknown. Do not label an unchanged old score as a negative application. Guard candidates use the same actual relational interface, positive observations, consistent roles/types and declared semantic constants. Use [] for an absent negative/application/guard set. Do not manufacture multiple independent events by cutting one revision into several functions.
The exact runnable learner and software interface examples are supplied. It currently replaces one local AST subtree, supports typed source parameters, old-code copies, relational guards and hygienic new locals. The implementation is not a proof of legal semantics. If a real edit needs currently missing source roles/relations or unsupported coupled code changes, do not fabricate a compatible example. Return status=needs_source_relations, empty example arrays, and new_required_observations_json specifying the minimal concrete relation/atomic acquired operation, grounded examples from the supplied TRAIN source, required scope, output values that could bind the actual code parameter, and exactly which real edit it would support. No broad design essay. The original legal tasks and scoring remain; observations must read source semantics, never answer a native hypothesis. Explicitly distinguish a new required observation from a fact already observed.
All *_json strings must decode to their named JSON collection/object: examples/guards/positive/negative/new_required_observations are arrays, signatures/constants are objects. rationale explains actual source/code correspondence, unproven parts and the exact next execution. These are candidate annotations; no contribution success or source truth is pre-certified.
''' + INSTRUCTION
    request = {'source_ids': sources, 'system_prompt': system,
        'user_prompt': json.dumps(pack(task), ensure_ascii=False), 'output_schema': schema}
    before_counts = physical_snapshot(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3')
    if any(c.get('reserved', 0) for c in before_counts.values()):
        raise ValueError('Reconcile the actual running request before legal acquisition')
    scientific = [Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/joint_updates.py',
        ROOT / 'tests/test_skill_evolution_joint_updates.py', task_path]
    binding = {'run_id': LEGAL_RUN, 'source_ids': sources, 'request_sha256': digest(request),
        'scientific_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in scientific},
        'same_goal': True, 'no_new_data_DEV_TEST_full_training': True, 'teacher_retries': 0}
    immutable_json(folder / 'protocol.json', binding)
    for path in scientific:
        target = folder / 'source_snapshot' / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True);target.write_bytes(path.read_bytes())
    from legal_skill_guard.inference.codex_cli_client import (strict_output_schema_issues,
        render_structured_codex_prompt, CODEX_TURN_INPUT_CHARACTER_LIMIT)
    issues = strict_output_schema_issues(schema)
    characters = len(render_structured_codex_prompt(system, request['user_prompt']))
    if issues or characters > CODEX_TURN_INPUT_CHARACTER_LIMIT:
        raise ValueError('Fix legal annotation schema/input before dispatch: ' + str(issues))
    immutable_json(folder / 'request_preflight.json', {'request_sha256': digest(request),
        'strict_schema_issues': issues, 'complete_input_characters': characters,
        'source_count': len(sources), 'new_model_requests': 0})
    if preflight:
        print(json.dumps({'preflight': True, 'characters': characters, 'schema_issues': issues,
            'source_count': len(sources), 'new_model_requests': 0}));return
    ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=LEGAL_RUN,
        sources={'train': sources, 'dev': [], 'test': []}, binding=digest(binding))
    config = read(ROOT / 'configs/legal_skill_evolution_formal_v5_20261111.json')['teacher']
    immutable_json(folder / 'ledger_before.json', before_counts)
    teacher = FrozenTeacher(ledger, folder, config)
    result = teacher.propose(LEGAL_RUN + ':teacher:legal_source_code_correspondence', **request)
    immutable_json(folder / 'teacher.json', result)
    immutable_json(folder / 'ledger_after.json', physical_snapshot(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'))
    print(json.dumps({'status': result['value']['status'], 'request_characters': len(request['user_prompt']),
        'new_physical_teacher_requests': 0 if result.get('ledger_cache_hit') else 1}, ensure_ascii=False))


def replay_legal():
    """Bind the real consumer edit to already acquired legal IR.

    The previous annotation input exposed upstream observations, not the actual
    learned source theory. Re-encode that existing theory instead of paying a
    model to repeat its normalized constructor tag. This is a same-source,
    shared-acquisition update replay, not independent acquisition/transfer.
    """
    from legal_skill_guard.skill_evolution.source_observations import encode_source_observations, fact, signatures
    from legal_skill_guard.skill_evolution.native_theory_feedback import contract_checker
    folder = ROOT / 'artifacts' / LEGAL_RUN / 'legal_ir_candidate_replay'
    task = read(folder.parent / 'teacher_input.json')
    response = read(folder.parent / 'teacher.json')['value']
    required = json.loads(response['new_required_observations_json'])
    edit = required[0]['supports_real_edit']
    pair = next(p for p in task['actual_same_seed_revision_pairs'] if p['event_id'] == edit['parent_revision_event_id'])
    source = required[0]['grounded_train_examples'][0]['source_key']
    current = ROOT / 'artifacts/legal_skill_evolution_open_acquisition_semantic_route_absence_encoded_20261113'
    row = read(current / 'acquisition/FreeUpdate' / (source.replace(':', '_') + '.json'))
    actual_theory = row['execution']['source_output'];visible = row['observation']['visible_inputs']
    library = read(current / 'FreeUpdate/compiled.json')
    counts_before = physical_snapshot(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3')
    encoded = encode_source_observations(source, source_text=visible['source_text'], units=visible['units'],
        source_output=actual_theory, operations=visible['operations'], queries=visible['queries'],
        answers=visible['answers'], scope=visible['scope'], query_scopes=visible['query_scopes'],
        complete_source_absence_choices=library.get('complete_source_absence_choices'))
    facts = encoded['context']['facts']
    roots = [f['arguments'][0] for f in facts if f['predicate'] == 'term_constructor'
        and f['arguments'][1] == 'disposal_obligation']
    witnesses = []
    for root in roots:
        for edge in facts:
            if edge['predicate'] != 'term_child' or edge['arguments'][:2] != [root, 2]:continue
            trigger = edge['arguments'][2]
            if fact('term_constructor', trigger, 'trigger_alternative') not in facts:continue
            for child in facts:
                if child['predicate'] != 'term_child' or child['arguments'][:2] != [trigger, 0]:continue
                endpoint = child['arguments'][2]
                for tag in facts:
                    if tag['predicate'] == 'term_constructor' and tag['arguments'][0] == endpoint:
                        witnesses.append([fact('term_constructor', root, 'disposal_obligation'), edge,
                            fact('term_constructor', trigger, 'trigger_alternative'), child, tag])
    if len(witnesses) != 1:raise ValueError('The real acquired disposal trigger must have one unambiguous witnessed path')
    witness = witnesses[0];tag = witness[-1]['arguments'][1]
    if tag not in required[0]['atomic_operation']['output_values']:
        raise ValueError('The actually acquired IR does not supply the requested code tag')
    # Verify the teacher selected an actual old/new subtree, not a hypothetical
    # program. The source graph above supplies the value; it is never fabricated
    # from the teacher's desired output or from a native task label.
    for side in ('before', 'after'):
        if _fragment(edit[side]) not in [_tree(n) for n in ast.walk(ast.parse(pair[side]))]:
            raise ValueError('The annotated local edit is not in the actual '+side+' program')
    slots = {'root': {'sort': 'term', 'positions': [[0, 0], [1, 0]]},
        'trigger': {'sort': 'term', 'positions': [[1, 2], [2, 0], [3, 0]]},
        'endpoint': {'sort': 'term', 'positions': [[3, 2], [4, 0]]},
        'endpoint_tag': {'sort': 'constructor', 'positions': [[4, 1]],
            'before_paths': [], 'after_paths': edit['source_slot']['after_paths']}}
    example = {'event_id': pair['event_id'], 'source_facts': witness, 'source_slots': slots,
        'before': edit['before'], 'after': edit['after']}
    sig = signatures();used = {f['predicate']: sig[f['predicate']]['arguments'] for f in witness}
    update = learn([example], used, source_constants={
        'constructor': ['disposal_obligation', 'trigger_alternative'], 'position': [0, 2]})
    proposed = candidates([update], facts, pair['before'])
    if len(proposed) != 1:raise ValueError('The source-backed local legal update did not uniquely apply')
    result = proposed[0]
    validate_procedure(result['program'], allow_helpers=True)
    previous_path = folder.parent / 'legal_ir_replay/actual_legal_replay.json'
    if previous_path.exists():
        previous_replay = read(previous_path)
        if (previous_replay['source_theory_sha256'] != digest(actual_theory)
                or previous_replay['parent_revision_event_id'] != pair['event_id']
                or ast.dump(ast.parse(previous_replay['actual_application']['program'])) != ast.dump(ast.parse(result['program']))):
            raise ValueError('Reuse grades only for the exact same source theory, revision and executable AST')
        results = deepcopy(previous_replay['results'])
    else:
        public = {s['key']: s for s in read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
        grading = read(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')[source]
        results = {}
        for arm, code in [('NoUpdate', pair['before']), ('JointU', result['program']), ('FullRepairReuse', pair['after'])]:
            spec = deepcopy(library['spec']);spec['decision_program'] = code
            results[arm] = contract_checker(spec, public[source], grading)(actual_theory)
    counts_after = physical_snapshot(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3')
    if counts_before != counts_after:raise ValueError('Legal IR replay must not add model requests')
    receipt = {'source': source, 'parent_revision_event_id': pair['event_id'], 'new_model_requests': 0,
        'source_provider': 'actual learned source theory with actual source provenance; not desired teacher facts',
        'source_theory_sha256': digest(actual_theory), 'source_binding': result['source_binding'],
        'actual_application': result, 'results': results, 'ledger_before': counts_before, 'ledger_after': counts_after,
        'same_source_training_reconstruction': True, 'new_source_transfer_established': False,
        'all_legal_semantics_verified': False, 'independent_gain_established': False,
        'requested_extra_label_read_performed': False,
        'source_pattern_limit': 'one witnessed disposal/alternative/first-endpoint path, not a learned general endpoint classifier or applicability boundary'}
    receipt['counterfactual_grades_exactly_reused_from'] = 'legal_ir_replay/actual_legal_replay.json' if previous_path.exists() else None
    immutable_json(folder / 'actual_encoded_ir.json', encoded)
    immutable_json(folder / 'source_code_example.json', example)
    immutable_json(folder / 'learned_update.json', update)
    immutable_json(folder / 'actual_legal_replay.json', receipt)
    scientific = [Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/joint_updates.py',
        ROOT / 'legal_skill_guard/skill_evolution/native.py', ROOT / 'legal_skill_guard/skill_evolution/native_theory_feedback.py',
        ROOT / 'legal_skill_guard/skill_evolution/source_observations.py', ROOT / 'tests/test_skill_evolution_joint_updates.py']
    immutable_json(folder / 'implementation_binding.json', {
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in scientific},
        'source_theory_sha256': digest(actual_theory), 'acquired_library_sha256': digest(library),
        'actual_source_code_example_sha256': digest(example), 'new_model_requests': 0, 'goal_complete': False})
    for path in scientific:
        target = folder / 'source_snapshot' / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True);target.write_bytes(path.read_bytes())
    print(json.dumps({'new_model_requests': 0, 'source': source,
        'actual_source_parameter': tag, 'legal_consumer_edit_applied': result['status'],
        'native': {arm: [(v['view'], v['core_executed'], (v.get('score') or {}).get('correct'))
            for v in feedback['views']] for arm, feedback in results.items()},
        'independent_gain_established': False}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser();parser.add_argument('phase', nargs='?', default='replay',
        choices=['replay', 'preflight-legal', 'acquire-legal', 'replay-legal'])
    args = parser.parse_args()
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.phase == 'replay':run()
        elif args.phase == 'replay-legal':replay_legal()
        else:acquire_legal(preflight=args.phase == 'preflight-legal')
