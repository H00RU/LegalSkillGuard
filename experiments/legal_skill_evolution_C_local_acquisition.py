"""Acquire local source refinements from actual bounded C diagnostics.

One finite incremental comparison; the old φ/G/programs stay immutable. No
executor request is needed because their current neural contracts are fixed.
"""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

from experiments import legal_skill_evolution_C_TRAIN_runtime as current
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.source_candidate_diagnosis import missing_slot_demands
from legal_skill_guard.skill_evolution.source_concept_execution import convert
from legal_skill_guard.skill_evolution.source_revision_execution import ordinary_output
from legal_skill_guard.skill_evolution.span_compiler import validate_procedure, CALLS, METHODS
from legal_skill_guard.skill_evolution.teacher_transport import pack_programs, unpack_programs, INSTRUCTION, PROGRAM_INSTRUCTION

ROOT = current.ROOT
RUN = 'legal_skill_evolution_C_local_acquisition_20261116'
OUT = ROOT / 'artifacts' / RUN
DIAGNOSIS = ROOT / 'artifacts/legal_skill_evolution_C_candidate_diagnosis_20261116'
C_PARENT = ROOT / 'artifacts/legal_skill_evolution_C_revision_integration_20261115'
FREE_PARENT = ROOT / 'artifacts/legal_skill_evolution_C_control_list_scope_20261116'
SCHEMA = record_schema({'rationale': {'type': 'string'}, 'program': {'type': 'string'}})
SYSTEM = '''Continue the current legal source-skill study. No tools, no new data.
Learn one reusable PURE source-local refinement program from the three original
TRAIN contracts. Both arms receive the same full original text, supervision,
shared type/consumer specification and source-local update machinery. Each arm
uses its OWN independently acquired current library and actual outputs. Earlier
TRAIN/B8 exposure is disclosed. This is incremental acquisition, not cold-start
or a blind set. Other21 parents are excluded from this update; freeze before replay.

The actual diagnosis distinguishes current G outputs from a typed, producing-query
bound relaxation. No new term, native label, query choice or absence was inserted.
No correct singleton frame was found for these acquisition losses in that finite
interface. This does NOT prove English information is missing, all G impossible,
or source correctness. Inspect original text to choose the actual missing source
distinction; do not encode the native answer as legal meaning.

The last unconstrained whole-program proposal repaired target errors but erased
valid skills. Return a local refinement instead. The old two source producers,
G, native consumer, schema, reader definitions and learned applicability policy
stay UNCHANGED. Your apply(inputs,premises) runs AFTER each actual source producer
on current input, BEFORE native scoring. Its inputs contain ONLY source_text,
source_spans, actual semantic_answers and previous_output. No question, gold,
source ID, model or desired value is supplied at inference. It must work on both
current producer outputs. Match structural language/actual record content, not
contract/company identifiers, source hashes, unit numbers or memorized snippets.
All units/identities come from the actual input. No imports/IO/reflection/recursion,
nested functions, globals/locals or third-party calls. re is prebound. Permitted
calls/methods are supplied; helper functions are allowed.

C API: apply returns exactly {
retire_group_query_ids:[actual previous program clause-group IDs],
retire_neural_query_ids:[actual previous unit-local neural query IDs],
queries:[{id,operation,unit_ids}],
answers:[{id,choice,evidence_unit_ids}],
fragments:[{term,support_ids,query_ids}],unresolved:[string]}.
Only actual previous program queries whose operation is source_clause_kind or
source_retention_scope can be retired as groups. New queries have FRESH IDs and
use existing declared program operations. Every new primitive fragment has actual
source support and new producing-group query evidence. Never output a Norm,
Definition, Description or native answer as a fragment. Use the unchanged typed
constructors, existing renderer meanings and actual current source.
Source replacements may supersede demonstrably wrong unit-local neural readings;
the original raw responses stay preserved. A superseded neural query cannot be
needed by an untouched source frame. Retire its owning obsolete program group(s)
and provide complete correct current-source replacements where necessary.
Whole-source scan/absence audits CANNOT be superseded or invented. No deletion-only
patch: retire a claim only with a new source-concept production in overlapping
source units. Keep unknown/unrepresented meaning explicit, never a false default.
If no learned source condition applies, return all six empty lists (a no-op).

FreeTeacher API: independently learn your strongest ordinary source-to-Norm
refinement. apply returns exactly {retire_statement_indices:[actual zero-based
indices in previous_output.statements],statements:[{term,support_ids}],unresolved:
[string]}. New statements are full well-typed source Norms under the SAME common
specification. Retired current statements need replacement statements citing an
overlapping actual current-source scope. No whole-source absence certificate may
be invented; unchanged old audits remain available. Untouched statements stay
identical. Use all original text, diagnostic procedure, prior code, trace and
supervision; you may use arbitrary helpers, guards and joint edits within this
full-program capability, including the same local logic as C. Do not be weak to
distinguish the arms. If no edit applies return all three empty lists.

Do not collapse semantic distinctions to force a score. Internal/external actors,
defined Representatives, governing permissions and exclusion lists need actual
source scope. A fact/definition/mention is not an operative permission. Conditions
and retention remain attached to the actual source clause. The compiler transports
meaning; it never supplies an unstated rule. Existing false neural choices do not
override explicit source meaning. The host will type/execute and use whole-case
native plus existing source checks, selecting only on the three acquisition
parents; ties retain the old library. New patches do not automatically get credit.
All other21 source labels/material are excluded from this task, no DEV/TEST.
Return JSON with rationale and the complete pure Python program string.
'''


def read(path): return json.loads(path.read_text())


def counts():
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as c:
        return c.execute('select role,status,count(*) from calls group by role,status').fetchall()


def initial(arm):
    return read((C_PARENT if arm == 'C' else FREE_PARENT) / 'selected_library.json')


def previous_rows(arm):
    folder = C_PARENT / 'rows' if arm == 'C' else FREE_PARENT / 'selected_rows'
    return {r['source']: r for f in folder.glob('*.json') for r in [read(f)]}


def prepare():
    before = counts(); assert not any(status == 'reserved' for _, status, _ in before)
    old = read(ROOT / 'artifacts/legal_skill_evolution_C_diagnostic_refinement_20261115/protocol.json')
    bank = read(current.generation.OUT / 'raw_source_bank.json'); grading = read(current.generation.OUT / 'TRAIN_grading.json')
    sources = old['sources']; acquisition = [next(s for s in sources if ':' + pre in s) for pre in ('c46f72f5', 'bbb39011', '467e2e05')]
    assert all(bank[s]['source']['split'] == 'train' for s in sources)
    p = {k: deepcopy(old[k]) for k in ('executor_profile', 'teacher_profile')}
    p.update(run_id=RUN, sources=sources, acquisition_sources=acquisition, fixed_reuse_sources=[s for s in sources if s not in acquisition],
        no_new_executor_requests=True, no_DEV_TEST=True, old_TRAIN_exposure_disclosed=True,
        same_public_local_patch_engine=True, source_producers_G_policy_unchanged=True, goal_complete=False)
    for arm in ('C', 'FreeTeacher'):
        library = initial(arm); rows = previous_rows(arm); cases = []
        for sid in acquisition:
            raw = read(current.OUT / arm / 'raw_observations' / (digest(sid) + '.json'))
            productions = {}
            for label, child in library['source_revision'].items():
                if label not in ('previous', 'proposed'): continue
                if arm == 'C':
                    observation = convert(child, raw); output = observation['source_concept_execution']['program_output']
                    productions[label] = {'actual_output': output, 'type_slot_demands': missing_slot_demands(child, output)}
                else:
                    output, receipt = ordinary_output(child, raw['visible_inputs'])
                    productions[label] = {'actual_output': output}
            cases.append({'source': sid, 'full_source_text': bank[sid]['source']['views'][0]['public']['source_text'],
                'source_units': bank[sid]['units'], 'original_TRAIN_supervision': grading[sid],
                'native_hypotheses': [{'id': v['id'], 'question': v['public']['question']} for v in bank[sid]['source']['views']],
                'actual_own_neural_inputs': raw['visible_inputs'], 'actual_own_feedback': rows[sid]['feedback'],
                'actual_own_productions': productions})
        task = {'original_TRAIN_acquisition': cases, 'own_current_library': library,
            'public_calls': sorted(CALLS), 'public_methods': sorted(METHODS),
            'public_code': {n: (ROOT / 'legal_skill_guard/skill_evolution' / n).read_text() for n in (
                'source_local_refinement.py', 'source_concept_execution.py', 'source_revision_execution.py')},
            'no_other21_material_or_labels': True, 'no_other_arm_program_supplied': True}
        immutable_json(OUT / arm / 'initial_library.json', library)
        immutable_json(OUT / arm / 'teacher_task.json', task)
        packed = pack_programs(task, extra_program_fields=('source_concept_program',))
        assert unpack_programs(packed) == task
        length = len(json.dumps(packed, ensure_ascii=False, separators=(',', ':'))); assert length < 1048576
        immutable_json(OUT / arm / 'transport_receipt.json', {'exact_roundtrip': True, 'chars': length, 'no_content_omitted': True})
    files = [Path(__file__), Path(current.__file__)] + sorted((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py'))
    files += sorted(OUT.glob('*/*.json')) + sorted((ROOT / 'tests').glob('test_skill_evolution_source_local_refinement.py'))
    p['source_sha256'] = {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    immutable_json(OUT / 'protocol.json', p)
    for f in files:
        target = OUT / 'source_snapshot' / f.relative_to(ROOT); target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(f.read_bytes())
    assert counts() == before
    print(json.dumps({'prepared': RUN, 'sources': acquisition, 'new_model_calls': 0}), flush=True)


def protocol():
    p = read(OUT / 'protocol.json')
    for rel, sha in p['source_sha256'].items(): assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == sha, rel
    return p


def acquire():
    p = protocol()
    ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': p['sources'], 'dev': [], 'test': []}, binding=digest(p), teacher_concurrency=2)
    client = FrozenTeacher(ledger, OUT, p['teacher_profile'])
    def one(arm):
        if (OUT / arm / 'teacher.json').exists(): return
        task = read(OUT / arm / 'teacher_task.json'); packed = pack_programs(task, extra_program_fields=('source_concept_program',))
        value = client.propose(RUN + ':' + arm + ':source_local_update', source_ids=p['acquisition_sources'],
            system_prompt=SYSTEM + '\nYour arm: ' + arm + '\n' + INSTRUCTION + '\n' + PROGRAM_INSTRUCTION,
            user_prompt=json.dumps(packed, ensure_ascii=False, separators=(',', ':')), output_schema=SCHEMA)
        immutable_json(OUT / arm / 'teacher.json', value); print(json.dumps({'saved': arm}), flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in [pool.submit(one, arm) for arm in ('C', 'FreeTeacher')]: future.result()


def materialize(arm):
    library = read(OUT / arm / 'initial_library.json'); program = read(OUT / arm / 'teacher.json')['value']['program']
    validate_procedure(program, allow_helpers=True)
    assert not any(isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in ('Entailment', 'Contradiction', 'NotMentioned')
                   for n in ast.walk(ast.parse(program))), 'A source refinement cannot contain native answer labels'
    for label in ('previous', 'proposed'): library['source_revision'][label]['source_refinement_program'] = program
    return library


def evaluate():
    p = protocol(); before = counts(); summaries = {}
    for arm in ('C', 'FreeTeacher'):
        old = read(OUT / arm / 'initial_library.json'); old_rows = previous_rows(arm)
        library = materialize(arm); results = []
        immutable_json(OUT / arm / 'candidate.json', library)
        for sid in p['acquisition_sources']:
            raw = read(current.OUT / arm / 'raw_observations' / (digest(sid) + '.json'))
            row = current.assess(library, current.convert(library, raw), sid)
            immutable_json(OUT / arm / 'acquisition' / (digest(sid) + '.json'), row); results.append(row)
        old_correct = sum(old_rows[s]['native_correct'] for s in p['acquisition_sources'])
        correct = sum(r['native_correct'] for r in results); valid = all(r['hard_source_pass'] for r in results)
        adopt = valid and correct > old_correct
        selected = library if adopt else old
        immutable_json(OUT / arm / 'selected_before_reuse.json', {'library': selected, 'adopted': adopt,
            'old_acquisition_correct': old_correct, 'new_acquisition_correct': correct, 'source_valid': valid,
            'only_acquisition_scores_used': True})
        replay = []
        for sid in p['fixed_reuse_sources']:
            if adopt:
                raw = read(current.OUT / arm / 'raw_observations' / (digest(sid) + '.json'))
                row = current.assess(selected, current.convert(selected, raw), sid)
            else: row = old_rows[sid]
            immutable_json(OUT / arm / 'reuse' / (digest(sid) + '.json'), row); replay.append(row)
        summaries[arm] = {'adopted': adopt, 'acquisition_before': old_correct, 'acquisition_after': correct,
            'acquisition_source_valid': valid, 'reuse_native_correct': sum(r['native_correct'] for r in replay),
            'reuse_native_total': 84, 'reuse_source_failures': [r['source'] for r in replay if not r['hard_source_pass']]}
        print(json.dumps({'arm': arm, **summaries[arm]}), flush=True)
    assert counts() == before
    immutable_json(OUT / 'result.json', {'arms': summaries, 'new_executor_calls': 0, 'fixed_old_producers_G_and_policy': True,
        'incremental_original_TRAIN_reuse_not_blind_generalization': True, 'goal_complete': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['prepare', 'acquire', 'evaluate']); args = parser.parse_args()
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        {'prepare': prepare, 'acquire': acquire, 'evaluate': evaluate}[args.phase]()
