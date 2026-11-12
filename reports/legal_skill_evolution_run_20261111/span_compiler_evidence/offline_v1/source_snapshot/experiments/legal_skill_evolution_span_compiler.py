"""Finite aligned-source compiler learning, independent free acquisition and ablations."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import FrozenReads
from legal_skill_guard.skill_evolution.source_schema import TASKS, execute_text_policy
from legal_skill_guard.skill_evolution.span_compiler import (SCHEMA, compile_annotations,
    parse_source, execute, learn_grammar, grammar_cost)
from experiments.legal_skill_evolution_role_TRAIN import physical_snapshot, status

RUN = 'legal_skill_evolution_span_compiler_20261112'
ARMS = ('LearnedCompiler', 'FreeStrongControl')
COMMON = '''Acquire a reusable external skill from the same complete original TRAIN evidence.
The seven source contracts, their two public hypotheses and native supervision, and actual prior erroneous reads are identical for both acquisitions. Both neural models stay frozen. Do not use source IDs, company/party names, memorized training answers, or label-valued source atoms as a decision lookup. IDs are allowed only in seed provenance. Do not supply a human-authored gold parser or assume the verifier knows omitted rules.
You may acquire kind compiler, program, or text_policy as the arm instruction permits. All share the same native grades, inherited warm-library/NoSkill fallback, pure execution tools, and unknown handling. Fallback never counts as a newly compiled core success. Non-target original views remain in each parent denominator.
For compiler, provide at most twelve source annotations. Each seed.quote is an actual contiguous TRAIN clause (words, case and punctuation must match; only whitespace may differ), not a generated paraphrase or an entire agreement. Its slots annotate exact nonoverlapping subspans of that quote. Include literal right context after the last slot, such as the clause punctuation or a following qualification; do not end a quote with an unbounded open slot. The host turns these examples into literal source-context patterns with named holes. New source holes must be actual text captures. slot.lexicon is null for raw local strings, or the name of a learned lexicon. Lexicon symbols are semantic concepts and forms are actual TRAIN phrases. The host recognizes forms only INSIDE the captured slot; a phrase elsewhere in the document cannot populate that slot. Entries with no recognized form stay unresolved (None), not a known-empty role list. Other unrecognized words remain explicit in lexical.unresolved_surface and lexical.complete is false. glue_words are grammatical connector words ignored for lexical completeness.
Each seed emits one record with kind=seed.kind, values=constants plus captured slot bindings, surface=raw captures, lexical=per-slot recognition status, span=[start,end], production=id. Constants name source semantic relations/properties, never a native answer label. Preserve actor, action, recipient, conditions and the relation of an exception to its target. A definition, information-subject mention, no-contact clause or copy restriction is not automatically a disclosure permission. Several small records may be joined by the learned procedure. Local lexical recognition and legal consequence reasoning should be inspectable separately.
The host learns a finite grammar by anti-unifying compatible contexts: same record kind/constants and slot names/types. protected_tokens must preserve polarity and scope operators in these merges; numeric literals are always protected unless explicitly annotated as slots. Merges may introduce bounded context gaps. All proposed grammar merges are replayed on the fixed seven TRAIN parents. The method accepts a compression only if native source grades do not regress. NoMerge and unguided compression use the same acquired examples as ablations. This is inspired by grammar induction, not a claim that generic anti-unification or MDL is new.
For compiler or program, emit one complete Python def apply(inputs, premises). inputs has task_id and question only. Compiler premises has records only, NEVER complete source text. A free program has source_text only and may parse it directly. Return exactly {"handled": bool, "answer": LABEL, "used_records": [indices]}. LABEL is Entailment, Contradiction or NotMentioned. For a compiler handled=True requires at least one actual record index. If the recognized records do not justify an answer, return handled=False and used_records=[]; its answer field is ignored. In particular, zero matches or a missed/unresolved role is not proof of NotMentioned, Contradiction or a legal absence. A positive existential can use a genuinely recognized role; a negative claim cannot treat an incomplete role list as exhaustive. Keep native task projection separate from source facts. A source-grounded NotMentioned determination is allowed only when the recognized structure actually establishes its applicability/absence, not as a catch-all.
Pure Python supports basic expressions, loops, comprehensions, dictionaries/lists, string operations and prebound re. No imports, files, network, introspection, nested functions or recursion. Allowed builtins: min,max,sum,len,abs,round,sorted,all,any,int,float,bool,str,list,dict,set,tuple,range,enumerate,zip,isinstance,ValueError,KeyError,TypeError. Allowed methods include lower,upper,casefold,strip,split,splitlines,replace,find,startswith,endswith,join,count,get,keys,values,items,append,extend,add,update,pop and re.compile/search/match/fullmatch/findall/finditer/escape/sub; match.group/groups/groupdict/start/end/span and re.I/IGNORECASE/S/DOTALL/M/MULTILINE are available. Execution is isolated and bounded.
For text_policy, set procedure=null, seeds=[], lexicons=[] and emit a reusable policy_text; the frozen executor applies it jointly to the two current hypotheses on complete source. For compiler/program set policy_text=null. For program use seeds=[] and lexicons=[]. Do not pretend that a prompt is a new algorithm, or deliberately weaken the free control. The two original TRAIN probe parents are not supplied and no proposal is revised after their execution.'''


def read(path):return json.loads(path.read_text())


def prepare(root):
    old = read(root / 'artifacts/legal_skill_evolution_schema_induction_20261112/protocol.json')
    public = root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    records = read(public);seen = old['teacher_sources'] + old['frozen_TRAIN_probes']
    held = [s['key'] for s in records if s['dataset'] == 'ContractNLI' and s['key'] not in seen][:2]
    if len(held) != 2:raise ValueError('Need the two fixed remaining original TRAIN parents')
    folder = root / 'artifacts' / RUN;folder.mkdir(exist_ok=True)
    paths = list((root / 'legal_skill_guard/skill_evolution').glob('*.py'))
    paths += list((root / 'tests').glob('test_skill_evolution*.py')) + [Path(__file__).resolve()]
    protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'question': 'Can independently acquired aligned-source compiler skills improve grounded reuse or cost over free acquisition, and do native-guided grammar merges contribute beyond annotated seed templates?',
        'learning_object': 'Versioned source lexicons, aligned clause examples, induced source-to-record productions, and a learned legal consequence procedure.',
        'teacher_sources': old['teacher_sources'], 'history': old['history'], 'trigger': old['trigger'],
        'frozen_TRAIN_probes': held, 'prior_probe_parents_not_recycled': old['frozen_TRAIN_probes'],
        'workload': 'One independent proposal per arm. All compiler training, induction and two fixed TRAIN probes execute without source-reading model calls. A free learned text policy, if chosen, runs once per seven calibration and two probe sources. No teacher retry, seed sweep or full study.',
        'same_information': True, 'teacher_source_labels_and_previous_errors_identical': True,
        'free_control_can_choose_same_compiler_tools': True,
        'ablations': ['NoMerge', 'NoNativeFeedback'],
        'generic_selection_not_claimed_new': True,
        'warm_base': 'The same preserved admitted Full results on four history parents; unchanged original NoSkill on other parents. These are actual archived fallback outputs, not new core success; all inherited costs remain in the global ledger.',
        'admission': 'Mean native grade strictly improves over the warm base on the three trigger parents; no history parent regresses. Do not accept based on probe labels.',
        'mechanism_credit': 'Require actual new-source use of learned productions and corresponding source semantics. Label fit, fallback, mere schema success, a seed quote unchanged on its original parent, or generic compression alone is not a contribution. Report whether induced merges actually change coverage/decisions and whether an independently acquired control absorbs the result.',
        'source_selection': 'Two first remaining ContractNLI parents in preserved public TRAIN order after the prior nine; no new source outside original128. Original full-study exposure is retained; not a fresh blind split.',
        'public_TRAIN_sha256': hashlib.sha256(public.read_bytes()).hexdigest(),
        'executor_profile': old['executor_profile'], 'teacher_profile': old['teacher_profile'],
        'code_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)},
        'offline_regressions_passed': 132, 'automatic_retries': 0,
        'no_new_full_training_DEV_TEST_or_paper': True}
    immutable_json(folder / 'protocol.json', protocol)
    return folder, protocol, {s['key']: s for s in records}


def setup(root):
    folder, protocol, records = prepare(root)
    path = root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    if any(x.get('reserved', 0) for x in physical_snapshot(path).values()):raise ValueError('Reconcile pending physical requests')
    ledger = EvolutionLedger(path, run_id=RUN, sources={'train': protocol['teacher_sources'] + protocol['frozen_TRAIN_probes'], 'dev': [], 'test': []}, binding=digest(protocol), teacher_concurrency=2)
    if not (folder / 'ledger_before.json').exists():immutable_json(folder / 'ledger_before.json', physical_snapshot(path))
    reads = FrozenReads(FrozenExecutor(ledger, folder, protocol['executor_profile']))
    return folder, protocol, records, ledger, reads


def acquire(root):
    folder, protocol, records, ledger, _ = setup(root)
    grading = read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    training = [{'source': k, 'source_text': records[k]['views'][0]['public']['source_text'],
        'tasks': {v['id']: {'hypothesis': v['public']['question'], 'native_annotation': grading[k][v['id']]}
                  for v in records[k]['views'] if v['id'] in TASKS}} for k in protocol['teacher_sources']]
    prior = read(root / 'artifacts/legal_skill_evolution_schema_induction_20261112/source_semantic_review_material.json')
    errors = [{'source': x['source'], 'field_values': {n: v['value'] for n, v in x['source_fields'].items()},
        'prior_predictions': [v for v in x['views'] if v['view'] in TASKS]}
        for x in prior if x['arm'] == 'SchemaRefinement' and x['source'] in protocol['teacher_sources']]
    user = json.dumps({'training': training, 'actual_prior_flat_reader_outputs': errors,
        'prior_input_warning': 'These are actual imperfect reads, not semantic gold; their failures must not be recoded as true values.'}, ensure_ascii=False)
    if any(k in user for k in protocol['frozen_TRAIN_probes']):raise ValueError('Probe entered teacher input')
    def one(arm):
        p = folder / arm / 'teacher.json'
        if p.exists():return read(p)
        instruction = ('''Acquire kind compiler. Learn source-span annotations with aligned actor/recipient/condition bindings and reusable lexical types, plus the consequence procedure. Provide compatible annotations where one reusable legal relation has different source formulations, so host grammar induction has meaningful work. Do not move the final legal answer into a source constant or use source-specific branch tables. Keep the interpretation of operational permission, restriction, definition and purpose exception in explicit learned records/procedure. Aim for reliable cross-contract reuse; let unresolved structure fall back rather than invent semantics.'''
            if arm == 'LearnedCompiler' else '''Independently acquire the strongest economical reusable skill with the same information. Choose compiler, full-source program or learned joint text policy freely. You have the same source-alignment/lexicon tools, native-guided grammar learning, pure Python/re operations and archived fallback. You may choose the same architecture if it is best; an absorbed effect will be reported. Prefer a capable source parser or reasoning procedure over brittle keyword coincidence; a direct text policy is also allowed. No extra teacher or execution oracle.''')
        system = COMMON + '\n' + instruction
        call = RUN + ':teacher:' + digest({'arm': arm, 'system': system, 'user': user, 'schema': SCHEMA})
        value = FrozenTeacher(ledger, folder, protocol['teacher_profile']).propose(call,
            source_ids=protocol['teacher_sources'], system_prompt=system, user_prompt=user, output_schema=SCHEMA)
        immutable_json(p, value);return value
    status(folder, phase='two_independent_compiler_or_free_acquisitions')
    errors = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(one, a) for a in ARMS]
        for job in jobs:
            try:job.result()
            except Exception as e:errors.append(e)
    if errors:raise errors[0]
    status(folder, phase='teachers_settled_offline_source_compilation_pending', ledger=physical_snapshot(ledger.path))


def warm_base(root, protocol):
    original = root / 'artifacts/legal_skill_evolution_20261111/formal_v5/NoSkill';base = {}
    for batch in range(1, 9):
        for row in read(original / f'initial_B{batch}.json')['results']:base[row['source']] = row
    prior = read(root / 'artifacts/legal_skill_evolution_fragment_program_update_20261112/completed.json')
    for i, key in enumerate(protocol['history']):
        if i == 3:base[key] = prior['frozen_TRAIN_reuse']['Full']
        elif i == 2:base[key] = next(c['trace'] for c in prior['updates']['Full']['table']['mixed_version_table'] if c['mask'] == 3 and c['source'] == key)
        else:base[key] = prior['before'][key]
    return base


def evaluate_source(spec, rules, source, annotations, base, reads, cache):
    text = source['views'][0]['public']['source_text']
    parse_error = None
    try:records = parse_source(spec, rules, text) if spec['kind'] == 'compiler' else []
    except ValueError as error:
        records = [];parse_error = str(error)
    policy, event = None, None
    if spec['kind'] == 'text_policy':
        policy_spec = {'scope_tasks': list(TASKS), 'policy_text': spec['policy_text']}
        policy, event = execute_text_policy(reads, source, policy_spec)
    rows, inherited = [], {v['view']: v for v in base['views']}
    for view in source['views']:
        old = inherited[view['id']];value, error = None, parse_error
        if view['id'] in TASKS and parse_error is None:
            try:
                if policy is not None:
                    answer = policy[view['id']]['answer']
                    value = {'handled': answer is not None, 'answer': answer, 'used_records': []}
                else:
                    premises = {'records': records} if spec['kind'] == 'compiler' else {'source_text': text}
                    inputs = {'task_id': view['id'], 'question': view['public']['question']}
                    key = digest({'procedure': spec['procedure'], 'inputs': inputs, 'premises': premises})
                    if key not in cache:
                        cache[key] = execute(spec['procedure'], inputs, premises)
                    value = cache[key]
            except (ValueError, TypeError, KeyError, subprocess.TimeoutExpired) as e:
                error = type(e).__name__ + ': ' + str(e)
        core = value is not None and value['handled'] and error is None
        if core:
            score = grade_view(source['dataset'], view, annotations[view['id']], value['answer'])
            rows.append({'view': view['id'], 'answer': value['answer'], 'score': score,
                'core_executed': True, 'fallback': False, 'used_records': value['used_records'], 'model_event': event})
        else:
            rows.append({'view': view['id'], 'answer': old['execution']['answer'], 'score': old['score'],
                'core_executed': False, 'fallback': True, 'error': error,
                'fallback_basis': 'Preserved actual common warm-library or NoSkill result; not newly compiled success.'})
    return {'source': source['key'], 'views': rows, 'parsed_records': records,
        'native_grade': sum(v['score']['grade'] for v in rows) / len(rows),
        'native_core_correct': sum(v['core_executed'] and v['score']['correct'] for v in rows),
        'core_views': sum(v['core_executed'] for v in rows), 'fallback_views': sum(v['fallback'] for v in rows)}


def evaluate(root):
    folder = root / 'artifacts' / RUN
    if (folder / 'completed.json').exists():return read(folder / 'completed.json')
    folder, protocol, records, ledger, reads = setup(root)
    grading = read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    base = warm_base(root, protocol);cache = {};variants = {};invalid = {};learning_logs = {}
    materials = {k: records[k]['views'][0]['public']['source_text'] for k in protocol['teacher_sources']}
    for arm in ARMS:
        spec = read(folder / arm / 'teacher.json')['value']
        try:
            if arm == 'LearnedCompiler' and spec['kind'] != 'compiler':raise ValueError('The candidate must actually learn a source compiler')
            seeds = compile_annotations(spec, materials)
        except Exception as e:
            invalid[arm] = type(e).__name__ + ': ' + str(e);continue
        def score(rules):
            return {k: evaluate_source(spec, rules, records[k], grading[k], base[k], reads, cache)['native_grade'] for k in protocol['teacher_sources']}
        if spec['kind'] == 'compiler':
            learned, log = learn_grammar(spec, seeds, score, native_feedback=True)
            variants[arm] = (spec, learned);learning_logs[arm] = log
            if arm == 'LearnedCompiler':
                variants['NoMerge'] = (spec, seeds)
                blind, blind_log = learn_grammar(spec, seeds, score, native_feedback=False)
                variants['NoNativeFeedback'] = (spec, blind);learning_logs['NoNativeFeedback'] = blind_log
        else:variants[arm] = (spec, [])
    calibration, updates = {}, {}
    for name, (spec, rules) in variants.items():
        calibration[name] = {}
        for k in protocol['teacher_sources']:
            status(folder, phase='fixed_calibration', arm=name, source=k)
            calibration[name][k] = evaluate_source(spec, rules, records[k], grading[k], base[k], reads, cache)
        gain = sum(calibration[name][k]['native_grade'] - base[k]['native_grade'] for k in protocol['trigger']) / len(protocol['trigger'])
        retained = all(calibration[name][k]['native_grade'] >= base[k]['native_grade'] for k in protocol['history'])
        updates[name] = {'strict_trigger_gain': gain, 'history_nonregression': retained, 'accepted': gain > 0 and retained,
            'source_rules': len(rules), 'merged_rules': sum(bool(r['merged_from']) for r in rules),
            'grammar_cost': grammar_cost(rules), 'candidate_hash': digest({'spec': spec, 'rules': rules})}
        immutable_json(folder / name / 'frozen_skill.json', {'spec': spec, 'rules': rules, 'update': updates[name],
            'before_probe_executions': True, 'before_probe_labels_used_for_updates': True})
    probes = {}
    for name, (spec, rules) in variants.items():
        probes[name] = []
        for k in protocol['frozen_TRAIN_probes']:
            status(folder, phase='fixed_remaining_original_TRAIN_probes', arm=name, source=k)
            probes[name].append(evaluate_source(spec, rules, records[k], grading[k], base[k], reads, cache))
    result = {'completed_utc': datetime.now(timezone.utc).isoformat(), 'protocol_hash': digest(protocol),
        'invalid_proposals': invalid, 'learning_logs': learning_logs, 'calibration': calibration,
        'updates': updates, 'frozen_TRAIN_probes': probes, 'deterministic_execution_cache_entries': len(cache),
        'warm_base_native_grades': {k: base[k]['native_grade'] for k in protocol['teacher_sources'] + protocol['frozen_TRAIN_probes']},
        'ledger_before': read(folder / 'ledger_before.json'), 'ledger_after': physical_snapshot(ledger.path),
        'semantic_and_contribution_review_pending': True, 'goal_complete': False}
    immutable_json(folder / 'completed.json', result)
    status(folder, phase='terminal_semantic_and_mechanism_review_pending', ledger=result['ledger_after'])
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser();parser.add_argument('action', choices=['prepare', 'acquire', 'evaluate']);args = parser.parse_args()
    root = Path(__file__).resolve().parents[1];folder = root / 'artifacts' / RUN;folder.mkdir(exist_ok=True)
    with (folder / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == 'prepare':
            _, p, _ = prepare(root);print(json.dumps({'protocol_hash': digest(p), 'teacher_tasks': 2, 'parents': len(p['teacher_sources']) + len(p['frozen_TRAIN_probes'])}))
        elif args.action == 'acquire':acquire(root);print(json.dumps({'teachers_settled': True}))
        else:
            x = evaluate(root);print(json.dumps({'updates': x['updates'], 'ledger': x['ledger_after'], 'invalid': x['invalid_proposals']}))
