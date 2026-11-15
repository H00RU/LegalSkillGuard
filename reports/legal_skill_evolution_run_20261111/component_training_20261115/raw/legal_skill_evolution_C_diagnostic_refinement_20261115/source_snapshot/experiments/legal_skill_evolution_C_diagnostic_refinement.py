"""Close C's diagnosis/acquisition loop on paid original TRAIN observations.

Four actual failure parents develop the update. The remaining twenty original
TRAIN parents are replayed only after selection. Both teachers see the same
source/supervision/diagnostic procedure and independently update their own code.
This is incremental reuse, not cold-start acquisition or a new blind split.
"""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import fcntl
import hashlib
import json
import sqlite3
from pathlib import Path

from experiments import legal_skill_evolution_C_TRAIN_runtime as current
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.relational_rules import validate_language
from legal_skill_guard.skill_evolution.scoped_grammar import constructors
from legal_skill_guard.skill_evolution.semantic_operations import validate_operations
from legal_skill_guard.skill_evolution.source_composition import validate_renderers, validate_template_constructors
from legal_skill_guard.skill_evolution.source_effect_update import function_update
from legal_skill_guard.skill_evolution.span_compiler import execute_json, CALLS, METHODS
from legal_skill_guard.skill_evolution.teacher_transport import pack_programs, unpack_programs, INSTRUCTION, PROGRAM_INSTRUCTION

ROOT = current.ROOT
RUN = 'legal_skill_evolution_C_diagnostic_refinement_20261115'
OUT = ROOT / 'artifacts' / RUN
PARENTS = ('5cad3f37', '6fce8464', 'd9360f2a', 'e82b951a')
SYSTEM = current.generation.SYSTEM + '''

This continuation addresses a METHOD gap, not a request to accumulate lexical
patches. Four pre-fixed original TRAIN parents provide actual failures. The
remaining 20 original TRAIN parents are excluded from this update task and are
replayed only after freezing. Earlier teacher/B8 exposure to all 24 is disclosed;
this is incremental cross-parent reuse, not blind generalization.

The supplied diagnosis executes deletions/singletons of ACTUAL source roots with
the unchanged consumer. It is a relaxed output-interface probe, not a proof of
all-G satisfiability or source correctness. An observed matching selection may
still be legally wrong; a missing witness only holds for the enumerated probes.
Do not infer a missing English concept, correct label or legal rule from it.

C must use the actual diagnostics to choose where to change the learned skill:
retain a valid source concept if composition alone is the error; refine source
concepts/attachment/guards if coarse or mistaken neural choices cannot supply a
valid frame. Existing neural choices are fallible proposals. They must not
override a source-scoped distinction. Learn a reusable processing algorithm,
not a table of the four contracts. Keep independent producing clause queries;
sharing evidence windows is not sufficient to join permission/condition parts.
The host will select only on the four acquisition parents, then freeze before
the other twenty; do not silently suppress unknowns or legal effects to pass.

FreeTeacher has the SAME full source, supervision and diagnostic algorithm applied
to its OWN outputs. Independently learn your strongest ordinary source compiler.
You may exploit every diagnostic, repair strategy, helper and source distinction.
No artificial restriction prevents reproducing C's advantage. No other arm's
learned program/output is supplied. All source and correctness rules above apply.

Do not treat confidentiality SURVIVAL after return as retention permission; an
open heading's recipients are specified by its actual child clauses, not an
unrestricted-third-party default. Negation with an explicit except-list is not
a prohibition ON those listed recipients. A coarse neural recipient class is
not evidence for every member when the current source states a narrower class.
These are source-reading distinctions, not instructions to output any answer.
Keep actual disclosure prohibitions and their exceptions separate from positive
permissions. Preserve correct retained skills outside the diagnosed operation.
No new neural operations/planner/examples/configuration; appended program-only
operations remain allowed as in the original API. No decision consumer changes.
'''


def read(path):
    return json.loads(path.read_text())


def ledger_counts():
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as c:
        return c.execute('select role,status,count(*) from calls group by role,status').fetchall()


def initial(arm):
    if arm == 'C':
        return read(ROOT / 'artifacts/legal_skill_evolution_C_TRAIN_fit_owner_scope_20261115/selected.json')['library']
    return read(ROOT / 'artifacts/legal_skill_evolution_source_operator_alignment_20261115/FreeTeacher/aligned_candidate.json')


def saved_rows(arm):
    if arm == 'C':
        return {r['source']: r for r in read(ROOT / 'artifacts/legal_skill_evolution_C_TRAIN_fit_owner_scope_20261115/source_rows.json')}
    return {r['source']: r for f in (ROOT / 'artifacts/legal_skill_evolution_source_operator_alignment_20261115/FreeTeacher/NoFit').glob('*.json')
            if f.name != 'summary.json' for r in [read(f)]}


def root_diagnosis(library, row, source, grading):
    """Finite causal probes; neither an accepted edit nor a global SAT claim."""
    statements = row['source_output']['statements']
    n = len(statements)
    full = list(range(n))
    roots = [full] + [[i] for i in full] + [[j for j in full if j != i] for i in full] + [[]]
    roots = list({tuple(r): r for r in roots}.values())
    program = library['spec']['decision_program']
    tree = ast.parse(program)
    entrypoints = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'apply']
    assert len(entrypoints) == 1
    entrypoints[0].name = 'consumer_apply'
    batch = ast.unparse(tree) + '''

def apply(inputs,premises):
    results=[]
    for roots in inputs['root_sets']:
        results.append(consumer_apply(inputs['case'],{'nodes':inputs['nodes'],'roots':roots}))
    return {'results':results}
'''
    nodes = [{'id': i, 'term': s['term'], 'child_ids': []} for i, s in enumerate(statements)]
    feedback = {v['view']: v for v in row['feedback']['views']}
    diagnostics = []
    for view in source['views']:
        actual = feedback[view['id']]
        if actual['score'] and actual['score']['correct']:
            continue
        result = execute_json(batch, {'case': {'task_id': view['id'], 'question': view['public']['question']},
            'nodes': nodes, 'root_sets': roots}, {}, allow_helpers=True)['results']
        assert result[0] == actual['execution']['value'], (row['source'], view['id'])
        matches = [{'roots': r, 'value': v} for r, v in zip(roots, result)
                   if v['handled'] and v.get('used_nodes') and grade_view('ContractNLI', view, grading[view['id']], v['answer'])['correct']]
        diagnostics.append({'view': view['id'], 'actual': result[0], 'probes': len(roots),
            'matching_observed_root_selections': matches,
            'diagnosis': 'observed_root_selection_may_help_source_validity_unproven' if matches else
                         'no_witness_in_singleton_or_single_deletion_probes',
            'not_a_proof_about_all_G_or_full_semantics': True})
    return {'source': row['source'], 'source_roots': statements, 'views': diagnostics,
            'actual_consumer_execution_parity': True, 'new_model_calls': 0}


def prepare():
    before = ledger_counts()
    assert not any(status == 'reserved' for _, status, _ in before)
    old = read(current.OUT / 'protocol.json')
    bank = read(current.generation.OUT / 'raw_source_bank.json')
    grading = read(current.generation.OUT / 'TRAIN_grading.json')
    acquisition = [next(s for s in old['sources'] if ':' + pre in s) for pre in PARENTS]
    reuse = [s for s in old['sources'] if s not in acquisition]
    assert len(acquisition) == 4 and len(reuse) == 20
    assert all(bank[s]['source']['split'] == 'train' for s in old['sources'])
    p = {k: deepcopy(old[k]) for k in ('sources', 'executor_profile', 'teacher_profile')}
    p.update(run_id=RUN, acquisition_sources=acquisition, fixed_reuse_sources=reuse,
        previous_all24_teacher_and_B8_exposure_disclosed=True,
        no_new_executor_requests=True, no_new_DEV_TEST=True, goal_complete=False,
        ledger_before=before, candidate_selection='acquisition hard source checks, native correctness, complexity; ties retain old')
    immutable_json(OUT / 'TRAIN_grading.json', {s: grading[s] for s in acquisition})
    for arm in ('C', 'FreeTeacher'):
        library = initial(arm); rows = saved_rows(arm)
        field = 'source_concept_program' if arm == 'C' else 'composition_program'
        diagnoses = []
        cases = []
        for sid in acquisition:
            diagnosis = root_diagnosis(library, rows[sid], bank[sid]['source'], grading[sid])
            diagnoses.append(diagnosis)
            raw = read(current.OUT / arm / 'raw_observations' / (digest(sid) + '.json'))
            cases.append({'source': sid, 'full_source_text': bank[sid]['source']['views'][0]['public']['source_text'],
                'source_units': bank[sid]['units'], 'native_TRAIN_supervision': grading[sid],
                'native_hypotheses': [{'id': v['id'], 'question': v['public']['question']} for v in bank[sid]['source']['views']],
                'actual_own_visible_inputs': raw['visible_inputs'], 'actual_own_feedback': rows[sid]['feedback'],
                'actual_own_diagnosis': diagnosis})
        task = {'acquisition_sources': cases, 'previous_own_library': library,
                'previous_source_program': library[field], 'public_calls': sorted(CALLS),
                'public_methods': sorted(METHODS), 'other_twenty_sources_excluded_from_update': True,
                'decision_consumer_unchanged': True, 'previous_all24_exposure_disclosed': True}
        immutable_json(OUT / arm / 'initial_library.json', library)
        immutable_json(OUT / arm / 'diagnoses.json', diagnoses)
        immutable_json(OUT / arm / 'teacher_task.json', task)
        packed = pack_programs(task, extra_program_fields=('source_concept_program', 'previous_source_program'))
        assert unpack_programs(packed) == task
        chars = len(json.dumps(packed, ensure_ascii=False, separators=(',', ':')))
        assert chars < 1048576
        immutable_json(OUT / arm / 'transport_check.json', {'exact_roundtrip': True, 'chars': chars, 'no_task_content_omitted': True})
    files = [Path(__file__), Path(current.__file__), Path(current.generation.__file__)]
    files += sorted((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py'))
    files += sorted(OUT.glob('*/*.json')) + [OUT / 'TRAIN_grading.json']
    p['source_sha256'] = {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    immutable_json(OUT / 'protocol.json', p)
    for f in files:
        target = OUT / 'source_snapshot' / f.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(f.read_bytes())
    assert ledger_counts() == before
    print(json.dumps({'prepared': RUN, 'diagnoses_from_actual_outputs': True, 'new_model_calls': 0}), flush=True)


def protocol():
    p = read(OUT / 'protocol.json')
    for path, sha in p['source_sha256'].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha, path
    return p


def acquire():
    p = protocol()
    ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': p['sources'], 'dev': [], 'test': []}, binding=digest(p), teacher_concurrency=2)
    client = FrozenTeacher(ledger, OUT, p['teacher_profile'])
    def one(arm):
        if (OUT / arm / 'teacher.json').exists():
            return
        packed = pack_programs(read(OUT / arm / 'teacher_task.json'), extra_program_fields=('source_concept_program', 'previous_source_program'))
        value = client.propose(RUN + ':' + arm + ':diagnostic_update', source_ids=p['acquisition_sources'],
            system_prompt=SYSTEM + '\nYour arm: ' + arm + '\n' + INSTRUCTION + '\n' + PROGRAM_INSTRUCTION,
            user_prompt=json.dumps(packed, ensure_ascii=False, separators=(',', ':')),
            output_schema=current.generation.SCHEMA)
        immutable_json(OUT / arm / 'teacher.json', value)
        print(json.dumps({'teacher_saved': arm}), flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        for job in [pool.submit(one, arm) for arm in ('C', 'FreeTeacher')]:
            job.result()


def updated(arm):
    p = protocol(); library = read(OUT / arm / 'initial_library.json')
    delta = read(OUT / arm / 'teacher.json')['value']
    field = 'source_concept_program' if arm == 'C' else 'composition_program'
    library[field] = function_update(library[field], delta['source_functions'])
    new = delta['program_operations']
    assert not {o['name'] for o in new} & {o['name'] for o in library['operations']}
    bank = read(current.generation.OUT / 'raw_source_bank.json')
    validate_operations(new, {s: bank[s]['source']['views'][0]['public']['source_text'] for s in p['acquisition_sources']})
    scopes = json.loads(delta['program_operation_scopes_json'])
    assert set(scopes) == {o['name'] for o in new} and all(v in ('window', 'focus_last') for v in scopes.values())
    library['operations'] += new; library['operation_scopes'].update(scopes)
    if arm == 'C':
        language = library['language']
        signatures = json.loads(delta['signature_additions_json'])
        assert all(s['kind'] in ('derived', 'output') for s in signatures.values())
        language['signatures'].update(signatures)
        for sort, values in json.loads(delta['constant_additions_json']).items():
            language['constants'][sort] = list(dict.fromkeys(language['constants'].get(sort, []) + values))
        for sort, values in [('operation', [o['name'] for o in library['operations']]),
                ('choice', [c['name'] for o in library['operations'] for c in o['choices']]),
                ('constructor', list(constructors(library['spec'])))]:
            language['constants'][sort] = list(dict.fromkeys(language['constants'].get(sort, []) + values))
        rules = {r['id']: r for r in language['rules']}
        for identity in delta['removed_rule_ids']:
            del rules[identity]
        rules.update({r['id']: r for r in json.loads(delta['rule_edits_json'])})
        language['rules'] = list(rules.values())
        renderers = {r['predicate']: r for r in library['renderers']}
        renderers.update({r['predicate']: r for r in json.loads(delta['renderer_edits_json'])})
        library['renderers'] = list(renderers.values())
        validate_language(language); validate_renderers(language, library['renderers'])
        validate_template_constructors(library['renderers'], library['spec'])
        assert set(delta['suggested_rule_ids']) <= set(rules)
    else:
        assert not new and not scopes
        assert not delta['removed_rule_ids'] and not delta['suggested_rule_ids']
        assert all(not json.loads(delta[k]) for k in ('signature_additions_json', 'constant_additions_json', 'rule_edits_json', 'renderer_edits_json'))
    return library, delta


def evaluate():
    p = protocol(); before = ledger_counts(); result = {}; selected = {}
    originals = {arm: saved_rows(arm) for arm in ('C', 'FreeTeacher')}
    for arm in ('C', 'FreeTeacher'):
        base = read(OUT / arm / 'initial_library.json'); library, delta = updated(arm)
        candidates = {'Before': base, 'UpdatedSuggested': deepcopy(library)}
        if arm == 'C':
            candidates['UpdatedSuggested']['selected_rule_ids'] = delta['suggested_rule_ids']
            candidates['UpdatedPreviousG'] = deepcopy(library)
            candidates['UpdatedPreviousG']['selected_rule_ids'] = [n for n in base['selected_rule_ids']
                if n in {r['id'] for r in library['language']['rules']}]
            candidates['UpdatedAllG'] = deepcopy(library)
            candidates['UpdatedAllG']['selected_rule_ids'] = [r['id'] for r in library['language']['rules']]
        seen = {}; evaluated = {}
        for name, candidate in candidates.items():
            if digest(candidate) in seen:
                continue
            seen[digest(candidate)] = name; rows = []
            immutable_json(OUT / arm / 'candidates' / (name + '.json'), candidate)
            for sid in p['acquisition_sources']:
                if name == 'Before':
                    row = originals[arm][sid]
                else:
                    raw = read(current.OUT / arm / 'raw_observations' / (digest(sid) + '.json'))
                    row = current.assess(candidate, current.convert(candidate, raw), sid)
                immutable_json(OUT / arm / 'acquisition' / name / (digest(sid) + '.json'), row)
                rows.append(row)
            valid = all(r['hard_source_pass'] for r in rows)
            evaluated[name] = {'source_valid': valid, 'native_correct': sum(r['native_correct'] for r in rows),
                'native_total': 16, 'unresolved': sum(r['unresolved'] for r in rows)}
            print(json.dumps({'arm': arm, 'candidate': name, **evaluated[name]}), flush=True)
        def rank(name):
            score = evaluated[name]
            costs = sum(r['cost'] for r in candidates[name].get('language', {}).get('rules', [])
                        if r['id'] in candidates[name].get('selected_rule_ids', []))
            return (not score['source_valid'], -score['native_correct'], name != 'Before', costs,
                    len(candidates[name].get('selected_rule_ids', [])), name)
        chosen = min(evaluated, key=rank); selected[arm] = chosen
        frozen = candidates[chosen]
        immutable_json(OUT / arm / 'selected_before_reuse.json', {'name': chosen, 'library': frozen,
            'acquisition_only': True, 'selection_scores': evaluated, 'no_reuse_guided_edit': True})
        result[arm] = {'acquisition': evaluated, 'selected': chosen, 'reuse': []}
        for sid in p['fixed_reuse_sources']:
            if chosen == 'Before':
                row = originals[arm][sid]
            else:
                raw = read(current.OUT / arm / 'raw_observations' / (digest(sid) + '.json'))
                row = current.assess(frozen, current.convert(frozen, raw), sid)
            immutable_json(OUT / arm / 'reuse' / (digest(sid) + '.json'), row)
            result[arm]['reuse'].append({'source': sid, 'native_correct': row['native_correct'],
                'native_total': 4, 'source_valid': row['hard_source_pass'], 'unresolved': row['unresolved']})
        print(json.dumps({'arm': arm, 'selected': chosen,
            'reuse_correct': sum(r['native_correct'] for r in result[arm]['reuse']),
            'reuse_source_failures': [r['source'] for r in result[arm]['reuse'] if not r['source_valid']]}), flush=True)
    assert ledger_counts() == before
    immutable_json(OUT / 'result.json', {'arms': result, 'selected': selected, 'new_executor_calls': 0,
        'all_paid_8B_reads_reused': True, 'incremental_original_TRAIN_reuse_not_blind_generalization': True,
        'DEV_TEST_accessed': False, 'goal_complete': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['prepare', 'acquire', 'evaluate'])
    args = parser.parse_args()
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        {'prepare': prepare, 'acquire': acquire, 'evaluate': evaluate}[args.phase]()
