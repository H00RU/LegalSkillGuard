"""Finite original-TRAIN acquisition/update with a real independent control."""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

import jsonschema

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view, record_schema, source_spans
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema
from legal_skill_guard.skill_evolution.scoped_grammar import GRAMMAR, induce, material_public
from legal_skill_guard.skill_evolution.scoped_reader import apply_current
from legal_skill_guard.skill_evolution.scoped_source_program import run_source
from legal_skill_guard.skill_evolution.source_schema import TASKS, LABELS
from legal_skill_guard.skill_evolution.span_compiler import execute_json, validate_procedure, METHODS, execution_source_spans
from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION, pack
from experiments.legal_skill_evolution_role_TRAIN import physical_snapshot
from experiments.legal_skill_evolution_span_compiler import warm_base


RUN = 'legal_skill_evolution_scoped_acquisition_v5_20261113'
INHERITED_PHASE1 = 'legal_skill_evolution_scoped_acquisition_v2_20261113'
ARMS = ('ScopedGrammar', 'IndependentFree')
PROPOSAL = record_schema({'architecture': {'type': 'string', 'enum': ['grammar', 'program']},
    'rationale': {'type': 'string'}, 'grammar': {'anyOf': [GRAMMAR, {'type': 'null'}]},
    'program': {'type': ['string', 'null']}, 'source_program': {'type':['string','null']}})
TEACHER_SCHEMA, TEACHER_HOST_CHECKS = decoder_schema(PROPOSAL)
PROGRAM_RESULT = record_schema({'handled': {'type': 'boolean'},
    'answer': {'type': ['string', 'null'], 'enum': [None, *LABELS]},
    'used_span_ids': {'type': 'array', 'uniqueItems': True,
                      'items': {'type': 'integer', 'minimum': 0}}})
read = lambda p: json.loads(Path(p).read_text())
COMMON = '''Learn a reusable external legal skill from original TRAIN text and supervision. Both models stay frozen. Do not use source IDs, company-specific answer branches, answer tables, native labels as source facts, or missing evidence as false. Both arms independently acquire the complete method. You receive no other arm's new ontology, grammar, consumer or program. You may add/change semantic distinctions when the current source requires them. Preserve source-supported conditions, actors, recipient ownership, and exception scope.
Both architectures use the same pure Python executor. Code defines apply(inputs,premises); ordinary pure top-level helpers are allowed. No imports, nested functions, decorators, recursion, filesystem, network, introspection or unlisted builtins. Prebound re, containers, loops, comprehensions, string methods are allowed. Builtins: min,max,sum,len,abs,round,sorted,all,any,int,float,bool,str,list,dict,set,tuple,range,enumerate,zip,isinstance,ValueError,KeyError,TypeError. Keep code compact. No model parameter updates.
architecture=grammar acquires its own constructors, grounded source-to-term examples, AND decision_program. This is an open typed term algebra, not the old flat role fields. Constructors have name,meaning,result sort,ordered argument sorts. A term is JSON [constructor_name,arg1,...], recursively; raw strings have primitive sort text. Names must be identifiers, not native labels; literal is reserved for the shared reader. Learn source operators for descriptions versus operative norms and nested actor/possessor scope instead of flattening every role mention into one list. You may encode relative references to be interpreted in their enclosing norm; their semantics must be explicit. Unknown must remain unknown. Do not invent a legal rule merely to fit native labels.
Each seed has source,source_span_ids,occurrence,quote,term_json. quote is exact source text (whitespace alone may differ); occurrence is its zero-based occurrence WITHIN the cited span range, not the whole contract. term_json is a string containing the acquired JSON term. All source examples must cite provided TRAIN spans. Include both small lexical/subtree examples and source-supported composed expressions: the host discovers a child source phrase/semantic subtree correspondence only if both are actually demonstrated. It factors unambiguously located proper subterms into typed variables, preserves bindings, and composes the resulting productions. Pure literal matching is NOT the actual new-source reader. The host derives inherited scope templates when identical source wording has different acquired bindings, factoring uniquely aligned subtrees and preserving shared variables. It parses current source for unambiguous grammar matches and open scope nodes. Acquire source_program (pure Python apply(inputs,premises)) to compute actual source interpretations, not to call a model. Its inputs={source_text:complete current text,source_spans:[{id,start,end,text,...}]}; premises={grammar_nodes:[{id,start,end,sort,term,derivations,...}],scope_nodes:[{id,start,end,sort,template,inherited_sorts,unresolved:true,...}],scope_patterns:[{id,source_tokens,template,inherited_sorts,observed_bindings,...}]}. Old ground alternatives at a context-dependent lexical span are not certified facts. The pure prebound bind_scope(template,bindings) substitutes only values that YOU infer from current source context, without adding any semantics. Use learned scope parameters when applicable; do not default to old owners or turn a descriptive role mention into an operative permission. Reuse current-source grounded grammar nodes where valid, and acquire missing source recognition code for residual wording. Return {statements:[{term:closed nested JSON term,support_ids:[current source IDs]}],complete:bool,unresolved:[reasons]}. complete means the required disclosure/owner/reference bindings are resolved. If unresolved, preserve it and return complete=false. No native labels in source_program. All returned terms undergo acquired arity/type and source-witness checks. The consumer receives inputs={task_id,question} and premises={nodes:[{id,sort,term,support_ids,child_ids,ambiguous:false}],roots:[node_ids]}. Use actual current nodes to derive native answers; do not inspect raw source (not present here). Return {handled:bool,answer:Entailment|Contradiction|NotMentioned|null,used_nodes:[actual root node IDs]}. Unsupported/unresolved means handled=false,answer=null. A handled answer needs a relevant root proof. You may inspect nested terms with ordinary Python, and resolve references or combine rules as warranted by your acquired semantics. Return program=null and provide source_program.
architecture=program independently learns a full direct pure Python decision program. Its inputs={task_id,question}; premises={source_text:complete current text,source_spans:[{id,field,start,end,text,...}]}. Return {handled:bool,answer:Entailment|Contradiction|NotMentioned|null,used_span_ids:[current IDs]}. A handled answer needs relevant source support. You may use any internal decomposition, helpers, role parsing, complete history and ordinary joint repairs. Return grammar=null,source_program=null. Do not intentionally weaken the control.
Both receive identical complete sources and native supervision; all acquisition, reading and repair costs count. Target only the fixed disclosure hypotheses nda-5 and nda-7. The other original native views stay in source-level denominators with the same preserved fallback. Fallback is not a newly learned core success. Acquisition examples are TRAIN development material, not new blind validation. Fixed later TRAIN reuse material is not supplied here. The direct program may be cheaper; account for all actual model calls, not just the last teacher response. Ordinary code expressibility alone neither proves nor refutes an acquisition contribution.'''


def prepare(root):
    folder = root / 'artifacts' / RUN
    if (folder / 'protocol.json').exists():
        return folder, read(folder / 'protocol.json')
    prior = read(root / 'artifacts/legal_skill_evolution_source_program_acquisition_20261113/protocol.json')
    public = read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')
    exposed = set(prior['teacher_sources'] + prior['fixed_TRAIN_reuse_sources'])
    held = [s['key'] for s in public if s['dataset'] == 'ContractNLI' and s['key'] not in exposed][:2]
    assert len(held) == 2
    paths = set(prior['source_snapshot'])
    paths.update(str(p.relative_to(root)) for p in (root / 'tests').glob('test_skill_evolution*.py'))
    paths.update(['legal_skill_guard/skill_evolution/scoped_grammar.py',
                  'legal_skill_guard/skill_evolution/scoped_reader.py',
                  'legal_skill_guard/skill_evolution/scoped_source_program.py',
                  Path(__file__).relative_to(root).as_posix()])
    before = physical_snapshot(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3')
    if any(x.get('reserved', 0) for x in before.values()):
        raise ValueError('Reconcile existing in-flight model requests')
    protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'question': 'Can source-grounded typed open-term induction and actual update improve independently acquired source semantics/reuse or total acquisition cost over a free complete program?',
        'initial_sources': prior['teacher_sources'][:4], 'update_sources': prior['teacher_sources'][4:],
        'reuse_sources': held, 'excluded_previous_reuse_sources': prior['fixed_TRAIN_reuse_sources'],
        'reuse_selection': 'First2 remaining original TRAIN parents in preserved order, excluding all10 current mechanism acquisition/reuse parents, fixed before grading access or new generation. Original full-study exposure is retained; not a fresh blind dataset.',
        'history': read(root / 'artifacts/legal_skill_evolution_span_compiler_20261112/protocol.json')['history'],
        'teacher_profile': prior['teacher_profile'], 'executor_profile': prior['executor_profile'],
        'planned_work': 'Keep the actual independent4-parent acquisitions. After4 systemic failed neural source reads across2 formats, leave the remaining pre-update reads undispatched. Use the already planned one update per arm on the same8 development parents, acquiring a pure current-source compiler and typed inherited scope patterns. Evaluate8 development parents, then the same2 fixed reuse parents and NoFactor ablation deterministically. No more neural IR prompt variants or new source pool.',
        'no_new_mechanical_call_cap': True, 'automatic_retries': 0,
        'independent_complete_acquisition': True, 'shared_new_method_assets': False,
        'same_raw_sources_supervision_common_tools_and_feedback': True,
        'literal_source_NQG_counterexample_not_retested': True,
        'root_pattern_match_not_causal_or_semantic_proof': True,
        'no_new_full_training_DEV_TEST_or_paper': True,
        'source_snapshot': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in sorted(paths)},
        'inherited_phase1_run': INHERITED_PHASE1,
        'inherited_phase1_new_teacher_calls': 0,
        'inherited_phase1_repair': 'The4 old executor failures and exact teacher assets remain. Compile a reusable pure source program in the planned update, with actual source-conditioned inherited attributes; no old generated facts are repaired into new legal facts.',
        'ledger_before': before, 'created_utc': datetime.now(timezone.utc).isoformat()}
    inherited = root / 'artifacts' / INHERITED_PHASE1
    old_protocol = read(inherited / 'protocol.json')
    assert all(protocol[k] == old_protocol[k] for k in ('initial_sources', 'update_sources', 'reuse_sources'))
    assert not read(inherited / 'phase1/teachers_settled.json')['errors']
    protocol['inherited_phase1_files'] = {}
    for arm in ARMS:
        for name in ('teacher.json', 'teacher_input.json'):
            path = f'phase1/{arm}/{name}'
            body = (inherited / path).read_bytes()
            protocol['inherited_phase1_files'][path] = hashlib.sha256(body).hexdigest()
            target = folder / path;target.parent.mkdir(parents=True, exist_ok=True);target.write_bytes(body)
    immutable_json(folder / 'protocol.json', protocol)
    for p in sorted(paths):
        target = folder / 'source_snapshot' / p
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / p).read_bytes())
    with sqlite3.connect(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
        immutable_json(folder / 'ledger_rows_before.json', {'rows': db.execute('select * from calls order by id').fetchall()})
    return folder, protocol


def setup(root):
    folder, protocol = prepare(root)
    for p, expected in protocol['source_snapshot'].items():
        if hashlib.sha256((root / p).read_bytes()).hexdigest() != expected:
            raise ValueError('Bound source changed; preserve and use a new explicit run revision: ' + p)
    keys = protocol['initial_sources'] + protocol['update_sources'] + protocol['reuse_sources']
    ledger = EvolutionLedger(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': keys, 'dev': [], 'test': []}, binding=digest(protocol), teacher_concurrency=2)
    public = {s['key']: s for s in read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    return folder, protocol, ledger, public


def acquire(root, phase):
    folder, protocol, ledger, public = setup(root)
    if phase == 1:
        raise ValueError('Initial independent acquisitions are already preserved; do not repeat them')
    keys = protocol['initial_sources'] if phase == 1 else protocol['initial_sources'] + protocol['update_sources']
    prior_reads=root/'artifacts/legal_skill_evolution_scoped_acquisition_v4_20261113'
    if not (prior_reads/'PRESERVED_AFTER_SMOKE.json').exists():
        raise ValueError('First preserve the terminal source-reading failures')
    grading = read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    training = [{'source': key, 'source_spans': source_spans(material_public(public[key]['views'][0]['public'])),
                 'tasks': {v['id']: {'question': v['public']['question'], 'native_annotation': grading[key][v['id']]}
                           for v in public[key]['views'] if v['id'] in TASKS}} for key in keys]
    def one(arm):
        path = folder / f'phase{phase}' / arm / 'teacher.json'
        if path.exists():
            return
        task = {'training': training, 'phase': phase,
                'common_source_semantic_feedback': 'Roles in protected-information descriptions are not necessarily recipients of an operative permission. A third-party prohibition is not itself a third-party permission merely because it contains a bounded employee exception.'}
        if phase == 2:
            task['own_previous_complete_method'] = read(folder / 'phase1' / arm / 'teacher.json')['value']
            task['own_actual_preupdate_results'] = {'results':[read(p) for p in sorted((prior_reads/'phase1'/arm/'results').glob('*.json'))],
                'remaining6_preupdate_reads_undispatched_after_systemic_failure':True,
                'not_a_completed_phase1_score':True}
            if arm=='ScopedGrammar':
                actual=[]
                for p in sorted((prior_reads/'calls').glob('*/request.json')):
                    x=read(p)
                    if p.with_name('result.json').exists():actual.append({'source':x['source'],'response':read(p.with_name('result.json'))['content']})
                task['own_actual_failed_neural_source_IR']=actual
            task['update_instruction'] = 'Revise the external skill, retaining valid semantics. The small source reader copied old examples/ARG placeholders, so do not ask it to generate more IR. For grammar architecture acquire a pure source_program that computes closed current-source terms. Keep conditions, owner scopes and unknowns; improve the consumer too where needed. Include true minimal subtree examples with the same wording but different contextual ownership when present in these actual8 sources; also include the containing source interpretation. Do not manufacture contrastive materials. The host derives typed inherited scope parameters from such contradictions and preserves repeated-variable identity. Only one explicit current binding closes a scope variable. Source_program may use current matched grammar/scope nodes and raw text, never old source facts. Free program control may choose the same architecture or the strongest complete direct program. No old interface compatibility is required. Explain actual learning versus ordinary repair.'
        instruction = ('Acquire grammar with its own complete semantics and consumer; program must be null.'
                       if arm == 'ScopedGrammar' else 'Independently choose the strongest grammar or full direct program. The same induction and reader tools are available. Do not inherit any new method-side artifact.')
        system = INSTRUCTION + '\n' + COMMON + '\n' + instruction + '\nOnly these attributes are available: '+','.join(sorted(METHODS))
        user = json.dumps(pack(task), ensure_ascii=False)
        immutable_json(folder / f'phase{phase}' / arm / 'teacher_input.json', {'system': system, 'user': user,
            'logical_schema': PROPOSAL, 'wire_schema': TEACHER_SCHEMA, 'host_validated_constraints': TEACHER_HOST_CHECKS})
        call = RUN + ':teacher:' + digest({'arm': arm, 'phase': phase, 'system': system, 'user': user, 'schema': TEACHER_SCHEMA})
        result = FrozenTeacher(ledger, folder, protocol['teacher_profile']).propose(call,
            source_ids=keys, system_prompt=system, user_prompt=user, output_schema=TEACHER_SCHEMA)
        immutable_json(path, result)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(one, arm) for arm in ARMS]
        errors = []
        for job in jobs:
            try:
                job.result()
            except Exception as exc:
                errors.append(type(exc).__name__ + ': ' + str(exc))
    immutable_json(folder / f'phase{phase}' / 'teachers_settled.json', {'errors': errors, 'ledger': physical_snapshot(ledger.path)})
    if errors:
        raise ValueError(str(errors))


def compiled_proposal(folder, phase, arm, public, protocol):
    proposal = read(folder / f'phase{phase}' / arm / 'teacher.json')['value']
    jsonschema.validate(proposal, PROPOSAL)
    grammar = None
    if proposal['architecture'] == 'grammar':
        assert proposal['program'] is None and proposal['grammar'] is not None
        keys = protocol['initial_sources'] + (protocol['update_sources'] if phase == 2 else [])
        grammar = induce(proposal['grammar'], {k: public[k]['views'][0]['public'] for k in keys})
        if proposal['source_program'] is None:raise ValueError('Acquire the actual current-source compiler')
        validate_procedure(proposal['source_program'],allow_helpers=True)
        if any(isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value in LABELS
               for n in ast.walk(ast.parse(proposal['source_program']))):
            raise ValueError('A source compiler cannot encode native answer labels')
        immutable_json(folder / f'phase{phase}' / arm / 'induced_grammar.json', grammar)
    else:
        assert proposal['grammar'] is None and proposal['program'] is not None and proposal['source_program'] is None
        validate_procedure(proposal['program'], allow_helpers=True)
    if arm == 'ScopedGrammar' and grammar is None:
        raise ValueError('Method must acquire its own scoped grammar and consumer')
    return proposal, grammar


def evaluate(root, phase, *, smoke=False, reuse=False, nofactor=False):
    if phase!=2:raise ValueError('Do not resume the failed neural IR phase; evaluate the compiled update')
    if nofactor and not reuse:
        raise ValueError('The fixed NoFactor ablation uses only the same two frozen reuse sources')
    folder, protocol, ledger, public = setup(root)
    if any(v.get('reserved', 0) for v in physical_snapshot(ledger.path).values()):
        raise ValueError('Wait for the same in-flight teachers to settle')
    if reuse:
        if phase != 2 or not (folder / 'phase2/completed.json').exists():
            raise ValueError('Freeze both updated methods before using reuse sources')
        freeze = {a: digest(read(folder / 'phase2' / a / 'teacher.json')['value']) for a in ARMS}
        immutable_json(folder / 'reuse_freeze.json', {'method_hashes': freeze, 'source_snapshot': protocol['source_snapshot'],
            'reuse_sources': protocol['reuse_sources'], 'no_adaptive_update_after_this_freeze': True})
    keys = protocol['reuse_sources'] if reuse else protocol['initial_sources'] + protocol['update_sources']
    if smoke:
        keys = keys[:2]
    grading = read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    base = warm_base(root, protocol)
    arms = ('ScopedGrammar',) if nofactor else ARMS
    stage = 'NoFactor' if nofactor else 'reuse' if reuse else f'phase{phase}'
    for arm in arms:
        proposal, grammar = compiled_proposal(folder, phase, arm, public, protocol)
        if nofactor:
            grammar = deepcopy(grammar)
            grammar['disabled_rules'] = [r['id'] for r in grammar['rules'] if r['induced']]
            grammar['scope_patterns'] = []
        rows = []
        for key in keys:
            path = folder / stage / arm / 'results' / (key.replace(':', '_') + '.json')
            if path.exists():
                rows.append(read(path));continue
            source = public[key];spans = source_spans(material_public(source['views'][0]['public']))
            interpretation, event, error = None, None, None
            if grammar is not None:
                try:
                    interpretation, event = run_source(proposal['source_program'],proposal['grammar'],grammar,source)
                    if not interpretation['complete'] or interpretation['unresolved']:
                        raise ValueError('Acquired source compiler preserves unresolved source bindings: '+str(interpretation['unresolved']))
                except Exception as exc:
                    error = {'type': type(exc).__name__, 'message': str(exc),
                             'field_path': list(exc.absolute_path) if isinstance(exc, jsonschema.ValidationError) else None,
                             'expected': exc.validator_value if isinstance(exc, jsonschema.ValidationError) else None,
                             'actual_type': type(exc.instance).__name__ if isinstance(exc, jsonschema.ValidationError) else None}
            inherited = {v['view']: v for v in base[key]['views']};views = []
            for view in source['views']:
                result, failure, proof = None, error, []
                if view['id'] in TASKS and error is None:
                    try:
                        if grammar is not None:
                            result = apply_current(proposal['grammar'], grammar, interpretation, view)
                            proof_ids = sorted({s for i in result['value']['used_nodes'] for s in interpretation['nodes'][i]['support_ids']})
                        else:
                            value = execute_json(proposal['program'], {'task_id': view['id'], 'question': view['public']['question']},
                                {'source_text': source['views'][0]['public']['source_text'], 'source_spans': execution_source_spans(spans)}, allow_helpers=True)
                            jsonschema.validate(value, PROGRAM_RESULT)
                            if any(i >= len(spans) for i in value['used_span_ids']):
                                raise ValueError('Program proof cites absent source span')
                            if value['handled'] and (value['answer'] is None or not value['used_span_ids']):
                                raise ValueError('Handled program result lacks source proof')
                            result = {'value': value};proof_ids = value['used_span_ids']
                        proof = sorted({spans[i]['public_sentence_id'] for i in proof_ids if 'public_sentence_id' in spans[i]})
                    except Exception as exc:
                        failure = {'type': type(exc).__name__, 'message': str(exc)}
                core = view['id'] in TASKS and result is not None and result['value']['handled'] and failure is None
                answer = result['value']['answer'] if core else inherited[view['id']]['execution']['answer']
                score = grade_view(source['dataset'], view, grading[key][view['id']], answer, proof) if core else inherited[view['id']]['score']
                views.append({'view': view['id'], 'core_executed': core, 'fallback': not core, 'answer': answer,
                              'score': score, 'execution': result, 'proof_sentence_ids': proof, 'error': failure})
            row = {'arm': arm, 'source': key, 'phase': phase, 'architecture': proposal['architecture'],
                   'interpretation': interpretation, 'source_event': event, 'views': views,
                   'source_semantic_review_pending': True, 'goal_complete': False}
            immutable_json(path, row);rows.append(row)
            print(json.dumps({'stage': stage, 'arm': arm, 'source': key, 'core': sum(v['core_executed'] for v in views),
                              'correct': sum(v['core_executed'] and v['score']['correct'] for v in views), 'source_error': error}), flush=True)
        if not smoke:
            immutable_json(folder / stage / arm / 'completed.json', {'results': rows, 'goal_complete': False})
    if not smoke:
        immutable_json(folder / stage / 'completed.json', {'arms': list(arms), 'phase': phase,
            'ledger_after': physical_snapshot(ledger.path), 'source_semantic_and_contribution_review_pending': True, 'goal_complete': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser();parser.add_argument('stage', choices=['prepare', 'acquire', 'evaluate'])
    parser.add_argument('--phase', type=int, choices=[1, 2], default=1)
    parser.add_argument('--smoke', action='store_true');parser.add_argument('--reuse', action='store_true')
    parser.add_argument('--nofactor', action='store_true');args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    lock_path = root / 'artifacts/rr_v2_preflight/current_scoped_acquisition_client.lock'
    with lock_path.open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.stage == 'prepare':
            print(prepare(root)[0])
        elif args.stage == 'acquire':
            acquire(root, args.phase)
        else:
            evaluate(root, args.phase, smoke=args.smoke, reuse=args.reuse, nofactor=args.nofactor)
