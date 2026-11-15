"""Incremental source-semantic acquisition on the fixed12 TRAIN mothers.

Reuses the existing compiler, planner, evidence reader, relational learner and
native consumer. Positive binding is an acquired program, never a host NDA rule.
The preselected next4 mothers remain outside acquisition and are scored last.
"""
import argparse
import ast
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

import jsonschema

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.acquisition_proposal import compile_proposal
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.direct_composition_profiles import admissible_direct_compositions
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native_theory_feedback import contract_checker
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import observe, fit, execute_source_program
from legal_skill_guard.skill_evolution.semantic_operations import prepare_queries
from legal_skill_guard.skill_evolution.program_composition_profiles import admissible_program_compositions
from legal_skill_guard.skill_evolution.source_observations import encode_source_observations, signatures
from legal_skill_guard.skill_evolution.source_effect_update import function_update
from legal_skill_guard.skill_evolution.span_compiler import METHODS, CALLS, execute_json
from legal_skill_guard.skill_evolution.teacher_transport import (
    INSTRUCTION, PROGRAM_INSTRUCTION, pack, unpack, pack_programs, unpack_programs)
from legal_skill_guard.skill_evolution.theory_supervision import admissible_theories, attach_scored_theories
from legal_skill_guard.inference.codex_cli_client import (
    strict_output_schema_issues, render_structured_codex_prompt, CODEX_TURN_INPUT_CHARACTER_LIMIT)
from experiments.legal_skill_evolution_diagnosed_update_train import SCHEMA, source_material
from experiments.legal_skill_evolution_joint_acquisition_train import COMMON
from experiments.legal_skill_evolution_open_acquisition_train import C_SPEC, evaluate_source, functions

ROOT = Path(__file__).resolve().parents[1]
RUN = 'legal_skill_evolution_positive_binding_typed_20261114'
OUT = ROOT / 'artifacts' / RUN
READING_PARENT = ROOT / 'artifacts/legal_skill_evolution_positive_binding_delta_20261114'
TEACHER_PARENT = ROOT / 'artifacts/legal_skill_evolution_positive_binding_20261114'
PARENT = ROOT / 'artifacts/legal_skill_evolution_query_refinement_20261114'
PROBE = ROOT / 'artifacts/legal_skill_evolution_frozen_acquirer_probe_20261114'
DECISION = PROBE / 'next_acquisition_decision.json'
PUBLIC = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
GRADING = PUBLIC.with_name('grading.json')
LEDGER = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
ARMS = ('ConstraintAcquire', 'FreeUpdate')
read = lambda p: json.loads(p.read_text())
name_for = lambda key: key.replace(':', '_') + '.json'
FREE_SCHEMA = deepcopy(SCHEMA)
del FREE_SCHEMA['properties']['composition']
FREE_SCHEMA['required'].remove('composition')
FREE_SCHEMA['properties']['composition_functions'] = {'type': 'array', 'items': {'type': 'string'}}
FREE_SCHEMA['required'].append('composition_functions')

FREE_SPEC = r'''Use the strongest ordinary source-program update from the same
complete information. This retry changes OUTPUT SERIALIZATION ONLY: instead of
reprinting a complete composition module, composition_functions is an array of
complete pure functions that add/replace functions in the supplied actual
shared_actual_initial_library.composition_program. [] preserves that program.
You may replace apply and any/all helpers, add arbitrary pure helpers or use the
same neural architecture. This supports every self-contained complete program
available before, while allowing unchanged helper reuse. Do not deliberately
weaken the program, avoid neural reads that would help, or retain a known broken
gate. No generic source classifier or native answer is supplied by the host.
The host assembles the actual complete program with function_update and runs
the unchanged typed/provenance/native pipeline. The original full-program input
and600-second timeout remain preserved and charged. No legal information or
capability was removed; C's already paid result is reused and is NOT provided
as new supervision to this independent update.

The assembled apply(inputs,premises) receives inputs={source_text,source_spans,
source_output,semantic_answers}, premises={}; return exactly
{statements:[{term:<typed current constructor list>,support_ids:[current IDs]}],
complete:bool,unresolved:[string]}. All previously available source_functions,
planners, operations, constructors and consumer updates remain available.
Return renderers_json='[]', suggested_rule_ids=[]. Weights/scorer are unchanged.
All function strings must be complete pure functions; unchanged source, planner
or consumer helpers need not be printed. Do not add imports or inspect native
questions in source code. The native consumer remains the separate final step.
'''

DOMAIN = r'''This is one incremental acquisition on12 original TRAIN contracts,
not a new dataset or an extension of the scored four-contract experiment.
The same actual common initial library, raw sources, native TRAIN supervision,
previous independently acquired C and Free programs, actual readings, source
outputs, native results, exact finite diagnostic and PARTIAL source reviews are
supplied to BOTH arms. The preselected next4 mothers/materials/labels are absent.
The current common initial program is a genuine paid asset, not correct facts.

The concrete missing capability is POSITIVE SOURCE-SEMANTIC BINDING. Current C
has only disclosure/disposal broad scouts. Its three selected rules preserve
existing roots and emit complete-source absence. candidate_found can correctly
locate an operative clause yet cannot construct a missing permission/disposal
norm. The pure source_program runs BEFORE neural reads and receives no current
semantic_answers. Current-G refitting cannot recover the missing fields: even
independent per-mother current-G choices on the last4 actual observations reach
only1/16. This is a local current-output/reading failure, not a representation
collision and not a proof that open acquisition is impossible.

Complete the actual discovery -> finer role/effect/trigger/scope reading ->
source-bound typed norm path, using a few reusable atomic concepts or a genuinely
appropriate source-program update. For C the claimed concept/composition path
must have positive outputs, not just retain a regex parser and add absence
answers. A native-answer classifier disguised as a source concept is forbidden.
The planner can run multiple rounds with ACTUAL semantic_answers, use returned
evidence to choose finer windows, and explicitly request contextual definitions.
Its inputs source_spans are {id,text}; no source start/end offsets are promised.
Only supported actual field readings reach G; unknown/unread must not become
False/no_exception/zero. Original raw source and all common abilities remain
available; don't remove a strong asset to manufacture an effect.

Keep actor ownership, permission/prohibition with exceptions, request versus
termination triggers, action/trigger association and copy/backup qualifications.
A prohibition except recipients can state a real permission for those recipients.
Source originals can be elliptical: do not fill omitted words merely to match
native labels. Do not confuse employees of controlled companies with employees
of the recipient, nor treat a generic prohibition as proof no permission exists.
All-material disposal is not an EXPLICIT no-retention sentence; native legal
consequences can be handled in the consumer while preserving the source norm.
Partial reviews reject stated errors only; unreviewed fields are not false.

source_functions add/replace complete pure functions in the actual common
source_program. apply(inputs,premises) receives inputs={source_text,source_spans:
[{id,text}],source_output:<actual common incoming>}, premises={}. Return exactly
{statements:[{term:<typed constructor list>,support_ids:[current IDs]}],
complete:bool,unresolved:[string]}. The same source functions are available to
Free. Source code/planner do not receive a native question. All helpers must be
included as complete pure functions; no imports/nested functions/lambda/network.
Do not hard-code per-contract/company IDs, native labels, or specific current
unit/query/term identities into a reusable G. Term scalar types are text or
explicitly acquired finite scalar domains, not an implicit undeclared sort.

Both arms may revise source functions, neural concepts, planners, consumers and
the rule vocabulary; Free can use the strongest complete pure program or the
same neural architecture. Do not deliberately weaken its full update or C's
suggested_rule_ids. Direct roles, full raw parsing, correct-policy cache and
whole repair/history reuse remain available equally. Existing strict native
scoring/type/provenance/source checks are not relaxed. The U core exists, but
there is no acquired reusable phi/G source-parameter dictionary: do not claim U
ran or pad it with a static constructor/interface fix.

Observations are canonically compacted: full visible_inputs and all execution
metadata are retained; only context facts/unknown_groups and term tables exactly
reconstructible by the supplied encoder are omitted. context id and explicit
required/forbidden partial constraints are retained. A full-object roundtrip
was checked for all original24 observations and all12 common initial executions.
Reconstructed facts are deterministic encoding, not new semantic supervision.
'''


def rows():
    with sqlite3.connect('file:' + str(LEDGER) + '?mode=ro', uri=True) as db:
        return db.execute('select * from calls order by id').fetchall()


def compact_observation(observation):
    compact = deepcopy(observation)
    compact['context'] = {k: observation['context'][k] for k in ('id', 'required', 'forbidden')}
    for key in ('legacy_roots', 'term_nodes', 'term_supports'):
        compact.pop(key)
    return compact


def restore_observation(source, compact):
    v = compact['visible_inputs']
    rebuilt = encode_source_observations(source, **v)
    rebuilt['context'].update(deepcopy(compact['context']))
    for key, value in compact.items():
        if key != 'context':
            rebuilt[key] = deepcopy(value)
    return rebuilt


def old_record(key, arm):
    variant = 'C_active' if arm == 'ConstraintAcquire' else 'Free_active'
    if key in read(PARENT / 'protocol.json')['acquisition_sources']:
        row = read(PARENT / 'acquisition' / variant / name_for(key))
        actual = read(PARENT / variant / 'fitted_execution' / name_for(key))
        return {'source': key, 'observation': row['observation'], **actual}
    variant = 'C_eager' if arm == 'ConstraintAcquire' else 'Free_eager'
    row = read(PROBE / 'unscored' / variant / name_for(key))
    actual = read(PROBE / 'scores' / variant / name_for(key))
    return {'source': key, 'observation': row['observation'], **actual}


def offline():
    if not (OUT / 'offline_check.json').exists():
        assert read(TEACHER_PARENT / 'TEACHER_BOUNDARY_PRESERVATION.json')['run_boundary_terminal']
        # Preserve the complete actual task and paid C; no acquisition repeats.
        for path in TEACHER_PARENT.rglob('*.json'):
            relative = path.relative_to(TEACHER_PARENT)
            if relative.parts[0] in {'initial', 'history', 'upstream', 'shared_source_outputs', 'shared'} or str(relative) in {
                    'base.json', 'grammar.json', 'teacher_task.json', 'offline_check.json', 'offline_program_transport.json'}:
                immutable_json(OUT / relative, read(path))
        for name in ('teacher.json', 'compiled.json', 'compilation_receipt.json',
                     'offline_candidate_check.json', 'offline_positive_interface.json'):
            immutable_json(OUT / 'ConstraintAcquire' / name, read(TEACHER_PARENT / 'ConstraintAcquire' / name))
        immutable_json(OUT / 'ConstraintAcquire/teacher_reuse.json', {
            'physical_call_id': TEACHER_PARENT.name + ':ConstraintAcquire:teacher',
            'new_physical_requests': 0, 'paid_proposal_and_compiled_library_unchanged': True})
    if (OUT / 'offline_check.json').exists():
        print('Original exact-observation/compile check preserved; no repeat.'); return
    assert read(PROBE / 'TERMINAL_PRESERVATION.json')['fixed_probe_complete']
    before = rows(); assert not any(r[6] == 'reserved' for r in before)
    decision = read(DECISION); keys = decision['next_acquisition_sources']
    public = {s['key']: s for s in read(PUBLIC) if s['key'] in keys}
    grading = {k: v for k, v in read(GRADING).items() if k in keys}
    for item in ('base.json', 'grammar.json', 'shared/initial_library.json'):
        immutable_json(OUT / item, read(PARENT / item))
    initial = read(OUT / 'shared/initial_library.json'); tasks = []; roundtrips = []
    for key in keys:
        source = public[key]
        assert len({v['public']['source_text'] for v in source['views']}) == 1
        pub, units, upstream = source_material(OUT, public, key)
        o = observe(object(), RUN + ':offline:initial:' + key, key, initial,
            source_text=pub['source_text'], units=units, source_output=upstream)
        actual = {'source': key, 'observation': o, **evaluate_source(initial, o, source, grading[key])}
        immutable_json(OUT / 'initial' / name_for(key), actual)
        previous = {}
        for arm in ARMS:
            old = old_record(key, arm)
            immutable_json(OUT / 'history' / arm / name_for(key), old)
            compact = compact_observation(old['observation'])
            assert restore_observation(key, compact) == old['observation']
            roundtrips.append({'source': key, 'arm': arm, 'full_observation_exact': True})
            previous[arm] = {**old, 'observation': compact}
        compact = compact_observation(o); assert restore_observation(key, compact) == o
        tasks.append({'source': source, 'native_TRAIN_supervision': grading[key],
            'actual_common_initial': {**actual, 'observation': compact}, 'actual_previous': previous})
    parent_source = ROOT / 'artifacts/legal_skill_evolution_source_functions_20261114'
    compile_checks = []
    for arm in ARMS:
        proposal = read(parent_source / arm / 'teacher.json')['value']
        compiled, _ = compile_proposal(initial, proposal, arm, public,
                                       source_functions=proposal['source_functions'])
        assert compiled == read(parent_source / arm / 'compiled.json')
        compile_checks.append({'arm': arm, 'actual_old_proposal_recompiles_exactly': True})
    libraries = {arm: read(PARENT / variant / 'learned.json') for arm, variant in
                 [('ConstraintAcquire', 'C_active'), ('FreeUpdate', 'Free_active')]}
    libraries = {a: {k: v for k, v in lib.items() if k != 'fit'} for a, lib in libraries.items()}
    task = {'tasks': tasks, 'shared_actual_initial_library': initial,
        'actual_previous_libraries_both_available': libraries,
        'actual_current_space_diagnosis': read(PROBE / 'postscore_diagnosis/result.json'),
        'actual_partial_source_reviews': read(PROBE / 'postscore_source_review.json'),
        'inherited_partial_retention_reviews': read(ROOT / 'artifacts/legal_skill_evolution_diagnosed_update_scalar_20261114/partial_retention_source_review.json'),
        'common_observed_signatures': {**signatures(), 'keep_root': {'arguments': ['term'], 'kind': 'output'}},
        'fact_encoder_source': (ROOT / 'legal_skill_guard/skill_evolution/source_observations.py').read_text(),
        'no_future_sources_materials_or_labels': True}
    text = json.dumps(task, ensure_ascii=False)
    assert not any(s['key'] in text for s in decision['next_frozen_reuse_sources'])
    packed = pack(task); assert unpack(packed) == task
    immutable_json(OUT / 'teacher_task.json', task)
    immutable_json(OUT / 'offline_check.json', {'roundtrip_exact': roundtrips,
        'common_initial_roundtrips': 12, 'compile_checks': compile_checks,
        'shared_value_transport_exact': True, 'packed_characters': len(json.dumps(packed, ensure_ascii=False, separators=(',', ':'))),
        'new_model_requests': 0, 'old_rows_unchanged': len(before)})
    assert rows() == before
    print(json.dumps({'actual_observation_roundtrips': 24, 'common_initial': 12,
        'old_compile_exact': compile_checks, 'packed_characters': len(json.dumps(packed, ensure_ascii=False, separators=(',', ':'))),
        'new_model_requests': 0}), flush=True)


def canonical_free_proposal(previous, raw):
    jsonschema.validate(raw, FREE_SCHEMA)
    proposal = {k: deepcopy(v) for k, v in raw.items() if k != 'composition_functions'}
    changes = functions(raw['composition_functions'])
    proposal['composition'] = function_update(previous['composition_program'], changes)
    return proposal


def delta_check():
    """Prove the new serialization on a real independently acquired program."""
    initial = read(OUT / 'shared/initial_library.json')
    old = read(ROOT / 'artifacts/legal_skill_evolution_source_functions_20261114/FreeUpdate/teacher.json')['value']
    raw = {k: deepcopy(v) for k, v in old.items() if k != 'composition'}
    raw['composition_functions'] = functions([old['composition']])
    proposal = canonical_free_proposal(initial, raw)
    old_tree = ast.parse(old['composition']); assembled = ast.parse(proposal['composition'])
    old_functions = {n.name: ast.dump(n, include_attributes=False) for n in old_tree.body}
    assembled_functions = {n.name: ast.dump(n, include_attributes=False) for n in assembled.body}
    assert all(assembled_functions[k] == v for k, v in old_functions.items())
    unused = set(assembled_functions) - set(old_functions)
    loaded = {n.id for n in ast.walk(old_tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    assert not unused.intersection(loaded)
    checks = []
    for key in read(DECISION)['next_acquisition_sources']:
        row = read(OUT / 'history/FreeUpdate' / name_for(key)); v = row['observation']['visible_inputs']
        inputs = {'source_text': v['source_text'], 'source_spans': v['units'],
                  'source_output': v['source_output'], 'semantic_answers': v['answers']}
        direct = execute_json(old['composition'], inputs, {}, allow_helpers=True)
        delta = execute_json(proposal['composition'], inputs, {}, allow_helpers=True)
        assert delta == direct == row['execution']['source_output']
        checks.append({'source': key, 'actual_paid_output_exactly_preserved': True})
    immutable_json(OUT / 'offline_Free_delta_check.json', {
        'checks': checks, 'all_old_function_ASTs_unchanged': True,
        'retained_extra_helpers_not_referenced': sorted(unused),
        'old_full_program_characters': len(old['composition']),
        'delta_serialization_preserves_complete_program_capability': True,
        'new_model_requests': 0, 'C_paid_result_not_dispatched_again': True})
    print('Free function-update schema:12 actual paid outputs exact; all original function ASTs retained, no semantic/value adapter.', flush=True)


def transport():
    task = read(OUT / 'teacher_task.json'); packed = pack_programs(task)
    assert unpack_programs(packed) == task
    immutable_json(OUT / 'offline_program_transport.json', {
        'original_complete_task_sha256': digest(task), 'full_object_roundtrip_exact': True,
        'programs_comments_source_labels_actual_readings_unchanged': True,
        'original_reference_transport_characters': read(OUT / 'offline_check.json')['packed_characters'],
        'complete_program_shared_characters': len(json.dumps(packed, ensure_ascii=False, separators=(',', ':'))),
        'new_model_requests': 0})
    print(json.dumps(read(OUT / 'offline_program_transport.json')), flush=True)


def source_checks():
    """Index the already recorded partial judgments; add no legal source fact."""
    previous = read(PROBE / 'postscore_source_review.json')
    reviews = []
    for row in previous['actual_source_reviews']:
        prefix = row['source'].split(':')[1][:4]
        terms = []
        if prefix in ('4607', '6fce', 'e82b'):
            terms.append(['complete_source_no_disclosure_permission'])
        if prefix == '8fb3':
            terms.append(['complete_source_no_disposal_obligation'])
        reviews.append({'source': row['source'], 'forbidden_subterms': terms,
            'actual_source_evidence': row['evidence'],
            'partial_only_unreviewed_fields_not_false': True})
    immutable_json(OUT / 'partial_source_checks.json', reviews)


def prepare():
    if (OUT / 'protocol.json').exists(): return read(OUT / 'protocol.json')
    proof = read(OUT / 'offline_check.json'); compression = read(OUT / 'offline_program_transport.json'); delta_proof = read(OUT / 'offline_Free_delta_check.json'); source_checks(); before = rows()
    assert not any(r[6] == 'reserved' for r in before)
    decision = read(DECISION); prior = read(PROBE / 'protocol.json')
    files = [Path(__file__), ROOT / 'experiments/legal_skill_evolution_diagnosed_update_train.py',
             ROOT / 'experiments/legal_skill_evolution_open_acquisition_train.py',
             ROOT / 'experiments/legal_skill_evolution_joint_acquisition_train.py',
             *sorted((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py')),
             *sorted((ROOT / 'tests').glob('test_skill_evolution*.py'))]
    data = [PUBLIC, GRADING, DECISION, OUT / 'teacher_task.json', OUT / 'offline_check.json', OUT / 'offline_program_transport.json', OUT / 'partial_source_checks.json', OUT / 'offline_Free_delta_check.json',
            READING_PARENT / 'TRAIN_FAILURE_BOUNDARY_PRESERVATION.json', OUT / 'offline_scalar_repair.json',
            TEACHER_PARENT / 'TEACHER_BOUNDARY_PRESERVATION.json',
            OUT / 'base.json', OUT / 'grammar.json', OUT / 'shared/initial_library.json',
            *sorted((OUT / 'initial').glob('*.json')), *sorted((OUT / 'history').glob('*/*.json'))]
    p = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'acquisition_sources': decision['next_acquisition_sources'],
        'reuse_sources': [s['key'] for s in decision['next_frozen_reuse_sources']],
        'independent_acquisition_mothers': 12, 'independent_reuse_mothers': 4,
        'native_views_per_mother': 4, 'previous_probe_unchanged': True,
        'purpose': 'Acquire the missing positive source binding path; same-information independent Free update',
        'executor_profile': prior['executor_profile'],
        'teacher_profile': read(PARENT / 'protocol.json')['teacher_profile'],
        'U_dictionary': [], 'teacher_dispatch': 'serial', 'automatic_retries': 0,
        'no_new_full_training_DEV_TEST_or_paper': True,
        'offline_proof_sha256': digest(proof), 'program_transport_sha256': digest(compression),
        'Free_delta_proof_sha256': digest(delta_proof), 'C_paid_teacher_reused': True,
        'reading_parent': READING_PARENT.name, 'both_paid_proposals_reused': True,
        'scalar_repair_sha256': digest(read(OUT / 'offline_scalar_repair.json')),
        'Free600s_failed_request_preserved': True,
        'source_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        'data_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in data}}
    for file in files:
        dst = OUT / 'source_snapshot' / file.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(file.read_bytes())
    immutable_json(OUT / 'ledger_before_row_hashes.json', {r[0]: digest(r) for r in before})
    immutable_json(OUT / 'protocol.json', p)
    return p


def setup():
    p = prepare()
    for path, expected in {**p['source_sha256'], **p['data_sha256']}.items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != expected:
            raise ValueError('Frozen scientific source/input changed: ' + path)
    ledger = EvolutionLedger(LEDGER, run_id=RUN,
        sources={'train': p['acquisition_sources'] + p['reuse_sources'], 'dev': [], 'test': []}, binding=digest(p))
    return p, ledger, {s['key']: s for s in read(PUBLIC)}


def teacher_request(arm):
    p, ledger, _ = setup(); task = read(OUT / 'teacher_task.json')
    system = COMMON + '\n' + DOMAIN + '\n' + (C_SPEC if arm == 'ConstraintAcquire' else FREE_SPEC)
    system += '\n' + INSTRUCTION + '\n' + PROGRAM_INSTRUCTION + '\nAllowed pure attributes: ' + ','.join(sorted(METHODS))
    system += '\nAllowed pure calls: ' + ','.join(sorted(CALLS))
    user = json.dumps(pack_programs(task), ensure_ascii=False, separators=(',', ':'))
    schema = SCHEMA if arm == 'ConstraintAcquire' else FREE_SCHEMA
    args = {'source_ids': p['acquisition_sources'], 'system_prompt': system, 'user_prompt': user, 'output_schema': schema}
    issues = strict_output_schema_issues(schema); size = len(render_structured_codex_prompt(system, user))
    immutable_json(OUT / arm / 'preflight.json', {'schema_issues': issues, 'input_characters': size,
        'task_sha256': digest(task), 'request_sha256': digest(args), 'new_model_requests': 0})
    if issues or size > CODEX_TURN_INPUT_CHARACTER_LIMIT:
        raise ValueError('Fix complete transport/schema offline before dispatch')
    return p, ledger, args


def acquire():
    for arm in ARMS:
        if (OUT / arm / 'teacher.json').exists(): continue
        p, ledger, args = teacher_request(arm)
        result = FrozenTeacher(ledger, OUT, p['teacher_profile']).propose(RUN + ':' + arm + ':teacher', **args)
        immutable_json(OUT / arm / 'teacher.json', result)
        print(json.dumps({'arm': arm, 'paid_proposal_saved': True}), flush=True)


def compile_all():
    p, _, public = setup()
    for arm in ARMS:
        if (OUT / arm / 'compiled.json').exists(): continue
        raw = read(OUT / arm / 'teacher.json')['value']
        proposal = canonical_free_proposal(read(OUT / 'shared/initial_library.json'), raw) if arm == 'FreeUpdate' else raw
        jsonschema.validate(proposal, SCHEMA)
        lib, receipt = compile_proposal(read(OUT / 'shared/initial_library.json'), proposal, arm,
            {k: public[k] for k in p['acquisition_sources']}, source_functions=proposal['source_functions'])
        immutable_json(OUT / arm / 'compiled.json', lib)
        immutable_json(OUT / arm / 'canonical_proposal.json', proposal)
        immutable_json(OUT / arm / 'compilation_receipt.json', receipt)
        print(json.dumps({'arm': arm, 'compiled': True, 'operations': len(lib['operations'])}), flush=True)


def inspect_compiled():
    """Check actual deterministic source/planner inputs before any new reading."""
    p, _, public = setup()
    for arm in ARMS:
        library = read(OUT / arm / 'compiled.json'); checks = []
        for key in p['acquisition_sources']:
            pub, units, upstream = source_material(OUT, public, key)
            output, event = execute_source_program(library['source_program'], library['spec'],
                source_text=pub['source_text'], units=units, source_output=upstream)
            queries = prepare_queries(library['planner_program'], library['operations'],
                pub['source_text'], units, answers=[], source_output=output)
            checks.append({'source': key, 'typed_source_program_output_sha256': digest(output),
                'source_statement_count': len(output['statements']), 'planned_before_any_new_read': queries,
                'source_program_trace': event, 'this_is_not_a_neural_semantic_certificate': True})
        record = {'checks': checks, 'new_model_requests': 0,
                  'operation_names': [o['name'] for o in library['operations']]}
        if arm == 'ConstraintAcquire':
            record['rule_count'] = len(library['language']['rules'])
            record['rendered_root_constructors'] = [r['term'][0] for r in library['renderers']]
        immutable_json(OUT / arm / 'offline_candidate_check.json', record)
        print(json.dumps({'arm': arm, 'actual_source_and_initial_planner_checks': len(checks),
                          'new_model_requests': 0}), flush=True)


def checker(library, source, annotation):
    native = contract_checker(library['spec'], source, annotation)
    forbidden = [term for review in read(OUT / 'partial_source_checks.json')
                 if review['source'] == source['key'] for term in review['forbidden_subterms']]
    def contains(value, term):
        return value == term or isinstance(value, list) and any(contains(v, term) for v in value)
    def callback(output):
        feedback = native(output)
        violations = [t for t in forbidden if any(contains(row['term'], t) for row in output['statements'])]
        feedback.update({'source_review_passed': not violations, 'explicit_source_review_violations': violations,
                         'partial_source_review_not_full_truth': True})
        if violations: feedback.update(accepted=False, reason='explicit_partial_source_counterevidence')
        return feedback
    return callback


def run_stage(reuse=False, probe=False, arms=ARMS):
    p, ledger, public = setup(); stage = 'reuse' if reuse else 'acquisition'
    if reuse and not (OUT / 'library_freeze.json').exists(): raise ValueError('Freeze both acquired libraries first')
    grading = None if reuse else read(GRADING)
    for arm in arms:
        library = read(OUT / arm / ('learned.json' if reuse else 'compiled.json'))
        if not reuse and not probe and (OUT / arm / 'learned.json').exists(): continue
        keys = p['reuse_sources'] if reuse else p['acquisition_sources']
        if probe: keys = p['acquisition_sources'][-4:-2]
        client = FrozenExecutor(ledger, OUT, p['executor_profile'])
        client.exact_replay_roots = (READING_PARENT,)
        for key in keys:
            dst = OUT / stage / arm / name_for(key)
            if dst.exists(): continue
            pub, units, upstream = source_material(OUT, public, key)
            histories = []
            if not reuse:
                histories = [read(OUT / 'history' / a / name_for(key))['observation'] for a in ARMS]
                histories.append(read(OUT / 'initial' / name_for(key))['observation'])
            counterpart = OUT / stage / 'ConstraintAcquire' / name_for(key)
            if arm == 'FreeUpdate' and counterpart.exists(): histories.append(read(counterpart)['observation'])
            observation = observe(client, RUN + ':' + stage + ':' + arm + ':' + key, key, library,
                source_text=pub['source_text'], units=units, source_output=upstream, previous_observations=histories,
                save_event=lambda e: immutable_json(OUT / stage / arm / 'events' / (digest(e['call_id']) + '.json'), e))
            immutable_json(OUT / stage / arm / 'observations' / name_for(key), observation)
            actual = evaluate_source(library, observation, public[key], None if reuse else grading[key]) if reuse or arm == 'FreeUpdate' else None
            if actual is None:
                direct = deepcopy(library); direct['selected_rule_ids'] = library['suggested_rule_ids']
                actual = {'NoFit': evaluate_source(direct, observation, public[key], grading[key])}
                direct_bodies = all(library['language']['signatures'][a['predicate']]['kind'] == 'observed'
                    for rule in library['language']['rules'] for a in rule['body'])
                enumerator = admissible_theories if observation['context']['unknown_groups'] else \
                    admissible_direct_compositions if direct_bodies else admissible_program_compositions
                profile = enumerator(library, observation, checker(library, public[key], grading[key]), timeout_seconds=90)
                immutable_json(OUT / arm / 'profiles' / name_for(key), profile)
                if profile['status'] != 'complete':
                    immutable_json(OUT / arm / 'preserved_before_incomplete_profile' / name_for(key), {'observation': observation})
                    raise ValueError('Actual reads preserved; repair deterministic profile search before further generation')
                actual['profile'] = profile
            immutable_json(dst, {'source': key, 'observation': observation, **actual})
            print(json.dumps({'stage': stage, 'arm': arm, 'source': key,
                'planned_queries': observation['execution']['planned_queries'],
                'new_requests': observation['execution']['new_physical_requests']}), flush=True)
        if not reuse and not probe:
            records = [read(OUT / stage / arm / name_for(k)) for k in p['acquisition_sources']]
            if arm == 'ConstraintAcquire':
                library, result = fit(library, [attach_scored_theories(r['observation'], r['profile']) for r in records],
                    prior_rule_ids=library['suggested_rule_ids'], timeout_seconds=90)
                immutable_json(OUT / arm / 'fit.json', result)
                if result['status'] != 'sat': raise ValueError('Inspect actual hard constraints; do not generate another proposal blindly')
                for row in records:
                    key = row['source']
                    immutable_json(OUT / arm / 'fitted_execution' / name_for(key), evaluate_source(library, row['observation'], public[key], grading[key]))
            immutable_json(OUT / arm / 'learned.json', library)
    if not reuse and not probe:
        immutable_json(OUT / 'library_freeze.json', {'libraries': {a: digest(read(OUT / a / 'learned.json')) for a in ARMS},
            'next4_labels_not_used': True, 'goal_complete': False})


def score():
    p, _, public = setup()
    assert all((OUT / 'reuse' / a / name_for(k)).exists() for a in ARMS for k in p['reuse_sources'])
    grading = read(GRADING)
    for arm in ARMS:
        library = read(OUT / arm / 'learned.json')
        direct = deepcopy(library)
        if arm == 'ConstraintAcquire': direct['selected_rule_ids'] = library['suggested_rule_ids']
        for key in p['reuse_sources']:
            observation = read(OUT / 'reuse' / arm / name_for(key))['observation']
            actual = evaluate_source(library, observation, public[key], grading[key])
            if arm == 'ConstraintAcquire': actual['NoFit'] = evaluate_source(direct, observation, public[key], grading[key])
            immutable_json(OUT / 'reuse_scores' / arm / name_for(key), actual)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['offline', 'transport', 'delta-check', 'prepare', 'preflight', 'acquire', 'compile', 'inspect', 'probe-c', 'probe', 'train', 'reuse', 'score'])
    phase = parser.parse_args().phase
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if phase == 'offline': offline()
        elif phase == 'transport': transport()
        elif phase == 'delta-check': delta_check()
        elif phase == 'prepare': prepare()
        elif phase == 'preflight':
            for arm in ARMS: teacher_request(arm)
        elif phase == 'acquire': acquire()
        elif phase == 'compile': compile_all()
        elif phase == 'inspect': inspect_compiled()
        elif phase == 'probe-c': run_stage(probe=True, arms=('ConstraintAcquire',))
        elif phase == 'score': score()
        else: run_stage(reuse=phase == 'reuse', probe=phase == 'probe')
