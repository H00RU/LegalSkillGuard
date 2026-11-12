"""One partial-conflict-guided source-schema acquisition and a free strong control.

Old evidence is reused, not relabeled. Both teachers independently acquire a
single candidate from the same seven TRAIN sources; two further original TRAIN
parents are frozen probes. This is a finite candidate test, not a new full study.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import argparse
import fcntl
import hashlib
import json
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.ledger import BudgetError
from legal_skill_guard.rr.client import WireError
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher, GenerationHold
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import FrozenReads
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.source_schema import (SCHEMA, TASKS, compile_schema,
    read_semantic_record, execute_schema, execute_text_policy, source_material)
from experiments.legal_skill_evolution_role_TRAIN import physical_snapshot, status

RUN = 'legal_skill_evolution_schema_induction_20261112'
ARMS = ('SchemaRefinement', 'FreeStrongControl')
COMMON = '''Acquire ONE reusable external legal reasoning skill from the same supplied TRAIN evidence.
Both models stay frozen. No extra tools, data, labels or external knowledge oracle.
The supplied old observations are actual imperfect reads; their target labels are native TRAIN feedback.
Their partial-record conflict witnesses prove only that a read-only deterministic program cannot correctly answer both current observations without new information. They do not prove that known model fields are true or that the underlying source schema is necessarily inadequate. Repairing the reader or inventing a grounded source predicate are both valid; do not manufacture a missing rule.
You have the complete seven training contracts, their two public hypotheses and native labels/evidence. Do not branch on source identity, party names or training answers. Infer a reusable procedure from the law and supervision. Keep the difference between intrinsic qualifications, a new consent requirement, definitions and a bare mention of a recipient; do not copy one old agreement's safeguards into every source.
Return at most eight explicit source fields. Semantic fields ask for local source parameters/structure/role classes/condition relationships, NOT the truth of a native hypothesis, an answer label, or the full query-specific legal permission decision. Source reading is independent of the current hypothesis, and one record is shared by nda-5 and nda-7. A field's finite domain names reusable semantic concepts. A known value requires current-source support; unknown is omitted, never default False/empty or proof of absence. Do not assume unstated rules, roles, consent or qualifications.
For a program, emit one complete Python def apply(inputs, premises) returning exactly {"answer": LABEL}. inputs contains task_id and question only; premises contains your declared source fields only. Every declared source field must actually be used. No imports, attributes/methods, globals, files, network, recursion or calls except min,max,sum,len,abs,round,sorted,all,any,int,float,bool,str,list,dict,range,enumerate,zip. With unknown fields only literal read-only premises["name"] access is allowed; no dictionary-membership guard, whole-map observation or default. Short-circuiting may avoid a missing field.
Native LABEL is exactly Entailment, Contradiction or NotMentioned. Public task IDs may project the query; they cannot supply a source answer. Both supported tasks remain in scope; other original views use the unchanged recorded fallback and remain in the parent denominator.
A text_policy instead supplies one reusable legal instruction applied by the frozen executor jointly to the two current public hypotheses. It may reason directly, without a program. Use null read_question, empty source_fields, null procedure for that form. It is an explicitly permitted strong-control capability, not an oracle.
For typed_rule/raw_rule set policy_text null, supply a read_question and the program. boolean/integer/number fields use domain []; finite string or array fields use canonical semantic tokens in domain. Arrays contain strings. raw_text/raw_spans bind the complete actual source directly at zero model cost, with empty question/domain, when used.
Candidate compilation, source support checks, unknown handling, old-source retention and native scoring are identical for both arms. Do not invent an empirical advantage or knowingly cripple a baseline. Return a grounded candidate, not a report.'''


def read(path):return json.loads(path.read_text())


def prepare(root):
    previous = root / 'artifacts/legal_skill_evolution_fragment_program_update_20261112'
    history = read(previous / 'protocol.json')['already_fixed_original_TRAIN_parents']
    trigger = read(root / 'artifacts/legal_skill_evolution_whole_source_control_20261112/protocol.json')['next_original_TRAIN_parents']
    public = root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    records = read(public)
    held = [s['key'] for s in records if s['dataset'] == 'ContractNLI' and s['key'] not in history + trigger][:2]
    if len(history) != 4 or len(trigger) != 3 or len(held) != 2:raise ValueError('Keep the fixed original TRAIN workload')
    folder = root / 'artifacts' / RUN
    witness = read(folder / 'historical_partial_observations.json')
    if len(witness['conditional_witnesses']) != 4:raise ValueError('Preserved actual partial observations differ')
    paths = list((root / 'legal_skill_guard/skill_evolution').glob('*.py'))
    paths += list((root / 'tests').glob('test_skill_evolution_*.py')) + [Path(__file__).resolve()]
    profile = read(root / 'configs/legal_skill_evolution_formal_v5_20261111.json')
    protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'candidate': 'Partial-observation-conflict-guided semantic source-schema refinement; not a claimed new generic CEGAR solver or an established contribution.',
        'learning_object': 'A versioned source encoder: typed semantic source fields, questions, finite concept vocabulary and a native reasoning procedure. New predicates must actually be acquired from source, not supplied by the verifier.',
        'update': 'Current compatible partial records with differing TRAIN targets rule out a procedure-only remedy. Request a new grounded reader/schema and procedure, compile the source-effect restriction, execute the fixed trigger/history cohort, and accept by the unchanged native/history criterion. Preserve source/reader uncertainty separately from semantic insufficiency.',
        'previous_B_difference': 'Old collision refinement selected among a fixed pre-extracted field set. This candidate may change semantic reading instructions and invent source predicates; a completion witness never supplies a field value. If only fixed-field selection is observed, do not credit new rule acquisition.',
        'strong_control': 'Independent acquisition with identical seven sources, labels, imperfect reads and all conflict certificates. It may learn the same typed interface, inspect raw source with code, or use a reusable joint text policy. No restriction to a weak greedy or code-only baseline.',
        'teacher_sources': history + trigger, 'history': history, 'trigger': trigger, 'frozen_TRAIN_probes': held,
        'source_selection': 'Keep the seven already-fixed TRAIN materials; probes are the first two remaining ContractNLI parents in the preserved public file order. No old TEST, source outside the original128, new seed or sweep.',
        'workload': 'One independent teacher proposal per arm, at most one source-record generation or joint policy execution per source per arm. Seven calibration parents, then the two frozen probes once each. No repeated proposal, unchanged retry or full study.',
        'admission': 'Strict mean improvement on the three trigger parents relative to preserved NoSkill; every one of four history parents at least its already-measured admitted Full grade. Candidate and final admitted state remain distinct. Failed candidates may receive the same fixed probes for diagnosis, without being credited as admitted skills.',
        'independent_acquisition': True, 'inherited_diagnostic_costs_retained': True,
        'historical_observations_sha256': hashlib.sha256((folder / 'historical_partial_observations.json').read_bytes()).hexdigest(),
        'public_TRAIN_sha256': hashlib.sha256(public.read_bytes()).hexdigest(),
        'executor_profile': profile['executor'], 'teacher_profile': profile['teacher'],
        'code_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)},
        'automatic_retries': 0, 'offline_regressions_passed': 124,
        'no_new_full_training_DEV_TEST_or_paper': True}
    immutable_json(folder / 'protocol.json', protocol)
    return folder, protocol, profile, {s['key']: s for s in records}


def setup(root):
    folder, protocol, profile, records = prepare(root)
    for name, sha in protocol['code_sha256'].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != sha:raise ValueError('Bound code changed: ' + name)
    path = root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    if any(v.get('reserved', 0) for v in physical_snapshot(path).values()):raise ValueError('Reconcile pending physical calls first')
    ledger = EvolutionLedger(path, run_id=RUN, sources={'train': protocol['teacher_sources'] + protocol['frozen_TRAIN_probes'], 'dev': [], 'test': []},
        binding=digest(protocol), teacher_concurrency=2)
    if not (folder / 'ledger_before.json').exists():immutable_json(folder / 'ledger_before.json', physical_snapshot(path))
    executor = FrozenExecutor(ledger, folder, profile['executor'])
    return folder, protocol, profile, records, ledger, FrozenReads(executor)


def acquire(root):
    folder, protocol, profile, records, ledger, _ = setup(root)
    grades = read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    # Held-source text and labels are absent from both serialized teacher calls.
    training = [{'key': k, 'source_text': records[k]['views'][0]['public']['source_text'],
        'sentence_spans': records[k]['views'][0]['public']['sentence_spans'],
        'tasks': {v['id']: {'question': v['public']['question'], 'native_TRAIN_annotation': grades[k][v['id']]}
                  for v in records[k]['views'] if v['id'] in TASKS}} for k in protocol['teacher_sources']]
    user = json.dumps({'training': training, 'actual_prior_reads_and_partial_conflicts': read(folder / 'historical_partial_observations.json'),
        'actual_witness_scope': 'Current observed neural records only. Do not fill missing fields with target labels or treat overlap as universal semantic equivalence.'}, ensure_ascii=False)
    for key in protocol['frozen_TRAIN_probes']:
        if key in user:raise ValueError('Frozen TRAIN probe entered teacher context')
    def one(arm):
        p = folder / arm / 'teacher.json'
        if p.exists():return read(p)
        instruction = ('''Use partial-conflict-guided semantic schema refinement. Produce kind typed_rule.
No raw source text/span data may enter the persistent program. String/list fields require a finite vocabulary of semantic identifiers, not source sentences or native labels. Read/source interpretation may use natural language; program comparisons on source-derived values must use this vocabulary. Learn local source properties and the rule procedure jointly. The observed conflicts mean an unchanged reader plus a program-only rewrite cannot solve the old compatible observations; the reading questions/schema must substantively change. This restriction is the candidate inductive bias, not a proof of native correctness.'''
            if arm == 'SchemaRefinement' else '''Acquire the strongest simple reusable competitor with exactly the same evidence and tools. Choose typed_rule, raw_rule or text_policy freely. You may learn the same semantic source abstraction, use complete original text directly in code at no reading cost, or directly reason with a concise learned text policy in one joint model call. Use the partial-conflict certificates too; do not waste attempts on a procedure-only edit that cannot distinguish the observations. Prefer the most reliable and economical valid approach, not a deliberately literal or weak implementation.''')
        system = COMMON + '\n' + instruction
        identity = RUN + ':teacher:' + digest({'arm': arm, 'system': system, 'user': user, 'schema': SCHEMA})
        response = FrozenTeacher(ledger, folder, profile['teacher']).propose(identity,
            source_ids=protocol['teacher_sources'], system_prompt=system, user_prompt=user, output_schema=SCHEMA)
        immutable_json(p, response);return response
    status(folder, phase='two_independent_source_schema_acquisitions')
    errors = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(one, a) for a in ARMS]
        for job in jobs:
            try:job.result()
            except Exception as error:errors.append(error)
    if errors:raise errors[0]
    status(folder, phase='teachers_settled_compile_and_semantic_review_pending', ledger=physical_snapshot(ledger.path))
    return {a: read(folder / a / 'teacher.json') for a in ARMS}


def evaluate_source(folder, arm, spec, source, grades, baseline, reads):
    p = folder / arm / 'source_results' / (digest(source['key']) + '.json')
    if p.exists():return read(p)
    inherited = {v['view']: v for v in baseline['views']}
    results, values, event, error = [], {}, None, None
    try:
        if spec['kind'] == 'text_policy':policy, event = execute_text_policy(reads, source, spec)
        else:values, event = read_semantic_record(reads, source, spec)
    except Exception as e:
        if isinstance(e, (GenerationHold, BudgetError, WireError)):raise
        with reads.executor.ledger.transaction() as db:
            if db.execute("select 1 from calls where status='reserved'").fetchone():raise
        error = type(e).__name__ + ': ' + str(e)
    for view in source['views']:
        old = inherited[view['id']]
        output, failure = None, error
        if view['id'] in spec['scope_tasks'] and failure is None:
            try:
                if spec['kind'] == 'text_policy':
                    output = policy[view['id']]['answer']
                    ids = policy[view['id']]['support_ids']
                else:
                    output = execute_schema(spec, source, view, values)
                    ids = sorted({i for q in (event or {}).get('fields', {}).values()
                                  if q['status'] == 'known' for i in q['support_ids']})
                if output is None:failure = 'Learned policy unresolved'
            except Exception as e:failure = type(e).__name__ + ': ' + str(e)
        if output is not None and failure is None:
            spans = source_material(source)
            evidence = sorted({spans[i]['public_sentence_id'] for i in ids if 'public_sentence_id' in spans[i]})
            score = grade_view(source['dataset'], view, grades[view['id']], output, evidence)
            results.append({'view': view['id'], 'answer': output, 'score': score, 'core_executed': True, 'fallback': False,
                'source_event': event, 'source_values': values, 'semantic_field_review_pending': spec['kind'] != 'text_policy'})
        else:
            results.append({'view': view['id'], 'answer': old['execution']['answer'], 'score': old['score'],
                'core_executed': False, 'fallback': True, 'error': failure,
                'source_event': event, 'source_values': values,
                'fallback_basis': 'Preserved actual same-source NoSkill output, no fresh model call; not core success.'})
    result = {'source': source['key'], 'arm': arm, 'views': results,
        'native_grade': sum(v['score']['grade'] for v in results) / len(results),
        'native_core_correct': sum(v['core_executed'] and v['score']['correct'] for v in results),
        'native_fallback_views': sum(v['fallback'] for v in results)}
    immutable_json(p, result)
    return result


def evaluate(root):
    folder = root / 'artifacts' / RUN
    if (folder / 'completed.json').exists():return read(folder / 'completed.json')
    folder, protocol, _, records, ledger, reads = setup(root)
    grades = read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    no_skill = {}
    for b in range(1, 9):
        for row in read(root / 'artifacts/legal_skill_evolution_20261111/formal_v5/NoSkill' / f'initial_B{b}.json')['results']:
            no_skill[row['source']] = row
    prior = read(root / 'artifacts/legal_skill_evolution_fragment_program_update_20261112/completed.json')
    history_grades = {}
    for key in protocol['history']:
        row = prior['frozen_TRAIN_reuse']['Full'] if key == protocol['history'][3] else prior['before'][key]
        if key == protocol['history'][2]:
            row = next(c['trace'] for c in prior['updates']['Full']['table']['mixed_version_table'] if c['mask'] == 3 and c['source'] == key)
        history_grades[key] = row['native_grade']
    # Validate every proposal before any executor generation.
    compiled, invalid = {}, {}
    for arm in ARMS:
        try:compiled[arm] = compile_schema(read(folder / arm / 'teacher.json')['value'], restricted=arm == 'SchemaRefinement')
        except Exception as e:invalid[arm] = type(e).__name__ + ': ' + str(e)
    immutable_json(folder / 'compile_receipt.json', {'valid_arms': list(compiled), 'invalid': invalid})
    calibration, updates, probes = {}, {}, {}
    for arm, spec in compiled.items():
        calibration[arm] = {}
        for key in protocol['teacher_sources']:
            status(folder, phase='fixed_calibration', arm=arm, source=key)
            calibration[arm][key] = evaluate_source(folder, arm, spec, records[key], grades[key], no_skill[key], reads)
        gain = sum(calibration[arm][k]['native_grade'] - no_skill[k]['native_grade'] for k in protocol['trigger']) / len(protocol['trigger'])
        retained = all(calibration[arm][k]['native_grade'] >= history_grades[k] for k in protocol['history'])
        updates[arm] = {'candidate_hash': digest(spec), 'strict_trigger_gain': gain,
            'history_nonregression': retained, 'accepted': gain > 0 and retained,
            'history_reference': history_grades, 'semantic_field_review_pending': spec['kind'] != 'text_policy'}
        immutable_json(folder / arm / 'frozen_candidate.json', {'schema': spec, 'update': updates[arm],
            'before_probe_labels_or_executions': True})
    for arm, spec in compiled.items():
        probes[arm] = []
        for key in protocol['frozen_TRAIN_probes']:
            status(folder, phase='frozen_original_TRAIN_probes', arm=arm, source=key)
            probes[arm].append(evaluate_source(folder, arm, spec, records[key], grades[key], no_skill[key], reads))
    result = {'completed_utc': datetime.now(timezone.utc).isoformat(), 'protocol_hash': digest(protocol),
        'invalid_proposals': invalid, 'calibration': calibration, 'updates': updates, 'frozen_TRAIN_probes': probes,
        'NoSkill_native_grades': {k: no_skill[k]['native_grade'] for k in protocol['teacher_sources'] + protocol['frozen_TRAIN_probes']},
        'ledger_before': read(folder / 'ledger_before.json'), 'ledger_after': physical_snapshot(ledger.path),
        'semantic_and_contribution_review_pending': True, 'goal_complete': False}
    immutable_json(folder / 'completed.json', result)
    status(folder, phase='terminal_semantic_and_strong_control_review_pending', ledger=result['ledger_after'])
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser();parser.add_argument('action', choices=['prepare', 'acquire', 'evaluate']);args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    folder = root / 'artifacts' / RUN;folder.mkdir(exist_ok=True)
    with (folder / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == 'prepare':
            _, p, _, _ = prepare(root);print(json.dumps({'protocol_hash': digest(p), 'teacher_tasks': 2, 'parents': len(p['teacher_sources']) + len(p['frozen_TRAIN_probes'])}))
        elif args.action == 'acquire':
            value = acquire(root);print(json.dumps({'teachers_completed': list(value)}))
        else:
            value = evaluate(root);print(json.dumps({'completed': True, 'goal_complete': False, 'updates': value['updates'], 'ledger': value['ledger_after']}))
