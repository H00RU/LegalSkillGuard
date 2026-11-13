"""Finite TRAIN-only acquisition of callable semantic reading operations.

This compares independently acquired source-reader updates from one common
actual library. It does not certify novelty or authorize a full study.
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
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema, source_spans, grade_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema
from legal_skill_guard.skill_evolution.scoped_grammar import constructors, term_sort, material_public
from legal_skill_guard.skill_evolution.scoped_reader import apply_current
from legal_skill_guard.skill_evolution.scoped_source_program import OUTPUT
from legal_skill_guard.skill_evolution.semantic_operations import (
    OPERATION, validate_operations, prepare_queries, read_semantics, finish, PLAN)
from legal_skill_guard.skill_evolution.source_effect_update import function_update
from legal_skill_guard.skill_evolution.span_compiler import (
    execution_source_units, expand_unit_support, METHODS)
from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION, pack
from experiments.legal_skill_evolution_role_TRAIN import physical_snapshot

ROOT = Path(__file__).resolve().parents[1]
RUN = 'legal_skill_evolution_semantic_operations_v2_20261113'
ARMS = ('LearnedOperations', 'IndependentReader')
read = lambda p: json.loads(Path(p).read_text())
PROPOSAL = record_schema({'rationale': {'type': 'string'},
    'operations': {'type': 'array', 'items': OPERATION},
    'source_functions': {'type': 'array', 'items': {'type': 'string'}}})

COMMON = '''Acquire a reusable external source-reading update from the supplied
original TRAIN only. All model weights and the common ontology/consumer stay
frozen. Both arms get exactly the same complete source, native annotations,
prior compiler and existing TRAIN-only source review. No reuse material is
supplied. Do not use source IDs/company names/answer tables as applicability
keys. Do not encode Entailment/Contradiction/NotMentioned in source operations
or source terms. Preserve actual actor/action/trigger/qualification/exception
scope. Native labels and their evidence do not certify complete source terms.

The prior finite proposal and its exact source snapshots are preserved in
legal_skill_evolution_semantic_operations_20261113. Offline inspection found its
new operation only gated the old parse_disposal, leaving all missing semantics
to the same lexical parser. Zero executor requests were spent on that absent
constructive mechanism. Both arms now receive that exact acquired role operation
and its six grounded examples as a COMMON asset; its teacher cost is shared and
charged to both, not claimed as an independent candidate success. Do not merely
reproduce a semantic gate around old parse_disposal. The candidate must actually
derive missing actor/action/trigger/scope/retention fields through acquired small
semantic operations and construct the typed source terms from those judgments.
The free arm is allowed the same operations, alternatives, source and tools.

The available NEW common tool is a frozen Qwen3-8B semantic classification
service. Its thinking remains OFF. You may acquire operations: each has a name,
question, explicit choices with meanings, and original TRAIN verbatim-quote
examples (source,quote,choice). unknown is reserved and automatically available.
These are learned source-reading operations, not legal facts imported into a
new source. A question can distinguish a mention/heading from an operative
action or resolve a semantic role. Examples must be actual source judgments;
never invent contracts, conditions or negative labels from missing annotations.
The service returns only {id,choice,evidence:[{unit_id,quote}]} for each planned
query; it is fallible and quotes do not certify semantics. The host checks the
declared choice, exact current words and window, and never invents legal rules.

Return the complete operations list, including any common operation still used.
Put verbatim TRAIN examples only in the examples array, never inside question
or choice meaning; question is the reusable interpretation request. Do not pack
a whole native answer or complete IR into one alternative. Typed actor/action/
trigger/condition distinctions may be composed by the learned finisher; lexical
filters can choose candidate windows but must not replace semantic interpretation
with an old wording match. Complex unsupported scope stays unknown, not erased.
Return source_functions, each string containing only complete pure functions.
The host splits function modules without changing their AST. Functions not
replaced are inherited from common_actual_library.source_program. Override
apply(inputs,premises). inputs={phase:plan|finish,source_text,source_spans,
semantic_answers:[]}; source_spans are punctuation-grouped, whitespace-folded
current units with original anchor IDs (not dense). At phase=plan return ONLY
{queries:[{id:unique string,operation:acquired name,unit_ids:[current anchors]}]}.
Choose necessary windows, including governing nonlocal context and definitions
when needed; do not create a task-answer question. The model gets exact current
units and the acquired operation, never hidden gold. Queries are batched by12,
all physical batches/costs counted, no hidden retry. Empty query list is allowed.
At phase=finish semantic_answers contains {id,operation,choice,evidence,
source_semantics_verified:false}; preserve unknown rather than treating it as
false. Return the existing source output {statements:[{term:closed constructor
list,support_ids:[current unit IDs]}],complete:bool,unresolved:[string]}.
Use only the common59 acquired constructors and their unchanged meanings;
the common decision program is unchanged. It handles the four supplied native
tasks from actual Norm/Definition roots, with original correctness checks.
Do not import/network/reflect inside the pure program. Helpers are allowed;
prebound re and ordinary supported Python methods are available. Source output
and all actual arguments still need source-semantic review. Genuine unknown
is allowed; no default norm, inherited answer or fallback counts as core success.
The independent arm can use the same semantic tool, old source functions,
arbitrary pure decomposition or ordinary program repair, and may use no model
operations at all. It must not be weakened merely to look different. Same-info
comparison isolates updating a common library, not independent initial learning.
Keep changes compact and preserve actual valid behavior. This is one finite
learning prototype, not proof of either contribution or a full training run.'''


def prepare():
    folder = ROOT/'artifacts'/RUN
    if (folder/'protocol.json').exists(): return folder, read(folder/'protocol.json')
    previous = read(ROOT/'artifacts/legal_skill_evolution_binding_TRAIN_v2_20261113/protocol.json')
    counts = physical_snapshot(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3')
    if any(c.get('reserved', 0) for c in counts.values()): raise ValueError('Reconcile current requests first')
    files = [*sorted((ROOT/'legal_skill_guard/skill_evolution').glob('*.py')),
             *sorted((ROOT/'tests').glob('test_skill_evolution*.py')), Path(__file__).resolve(),
             ROOT/'experiments/legal_skill_evolution_role_TRAIN.py']
    base = ROOT/'artifacts/legal_skill_evolution_semantic_operations_20261113/common_gate_asset.json'
    data = [base, ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json',
            ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json',
            ROOT/'reports/legal_skill_evolution_run_20261111/open_effect_evidence/source_semantic_review.json']
    protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'teacher_sources': previous['teacher_sources'], 'reuse_sources': previous['reuse_sources'],
        'reuse_selection': 'Unopened2 parents fixed by the earlier binding protocol; same original TRAIN, historical full-study exposure retained; no new blind TEST claim.',
        'teacher_profile': previous['teacher_profile'], 'executor_profile': previous['executor_profile'],
        'ledger_before': counts, 'arms': list(ARMS), 'automatic_retries': 0,
        'no_new_mechanical_call_cap': True, 'shared_common_initial_library': True,
        'workload': 'One independent teacher update per arm; offline plan/grounding checks; first training parent semantic smoke per arm. Only after semantic usability freeze both updates and run the previously fixed2 TRAIN reuse; NoExamples shares the exact learned program/operation meanings and removes only examples. No full training, new data, DEV/TEST or parameter update.',
        'decision': 'If atomic judgments are also systematically wrong, diagnose the real inputs and stop that read route rather than batch identically. No adaptive repair from reuse answers. Reuse/core source support, acquired-operation use and total acquisition/runtime cost decide, not JSON pass or isolated native success.',
        'research_hypothesis': 'Can acquired, callable small semantic reading operations construct source-supported norms on new wording more reliably/economically than independently acquired unrestricted source code using the same tool?',
        'not_novel_by_interface_or_neural_calls': True,
        'shared_acquisition_seed': 'legal_skill_evolution_semantic_operations_20261113/common_gate_asset.json',
        'shared_seed_teacher_physical_requests': 1,
        'first_proposal_preserved_executor_requests_saved': True,
        'source_snapshot': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        'data_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in data}}
    immutable_json(folder/'base.json', read(base)); immutable_json(folder/'protocol.json', protocol)
    for f in files:
        dst = folder/'source_snapshot'/f.relative_to(ROOT); dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(f.read_bytes())
    with sqlite3.connect(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
        immutable_json(folder/'ledger_before.json', {'rows': db.execute('select * from calls order by id').fetchall()})
    return folder, protocol


def setup():
    folder, p = prepare()
    for name, h in {**p['source_snapshot'], **p['data_sha256']}.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != h: raise ValueError('Frozen input changed: '+name)
    ledger = EvolutionLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': p['teacher_sources']+p['reuse_sources'], 'dev': [], 'test': []}, binding=digest(p))
    public = {s['key']: s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    return folder, p, ledger, public


def acquire(arm):
    folder, p, ledger, public = setup()
    if (folder/arm/'teacher.json').exists(): return
    grading = read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    review = read(ROOT/'reports/legal_skill_evolution_run_20261111/open_effect_evidence/source_semantic_review.json')
    prefixes = {k.split(':')[1][:6] for k in p['teacher_sources']}
    training = []
    for k in p['teacher_sources']:
        s = public[k]; pub = s['views'][0]['public']; units, _ = execution_source_units(pub['source_text'], source_spans(material_public(pub)))
        training.append({'source': k, 'current_source_units': units,
            'tasks': {v['id']: {'question': v['public']['question'], 'native_annotation': grading[k][v['id']]} for v in s['views']}})
    content = {'common_actual_library': read(folder/'base.json'), 'training': training,
        'existing_TRAIN_source_review': [r for r in review['source_findings'] if r['source_prefix'] in prefixes]}
    instruction = ('Learn compact reusable semantic operations and a source planner/finisher which actually uses them for new wording. The learned operation should encode a meaningful recurring source distinction, not a native task or merely a wrapper for whole IR generation.' if arm == ARMS[0] else
        'Independently choose the strongest economical reader update. The exact same semantic tool is available and may be used, combined or ignored. Pure code, own callable operations, the same planner/finisher and any local editing strategy are permitted. Do not choose a weak baseline.')
    system = INSTRUCTION+COMMON+'\n'+instruction+'\nAllowed attributes: '+','.join(sorted(METHODS))
    user = json.dumps(pack(content), ensure_ascii=False); wire, host = decoder_schema(PROPOSAL)
    immutable_json(folder/arm/'teacher_input.json', {'system': system, 'user': user,
        'logical_schema': PROPOSAL, 'wire_schema': wire, 'host_constraints': host})
    value = FrozenTeacher(ledger, folder, p['teacher_profile']).propose(RUN+':teacher:'+arm+':'+digest([system,user,wire]),
        source_ids=p['teacher_sources'], system_prompt=system, user_prompt=user, output_schema=wire)
    immutable_json(folder/arm/'teacher.json', value)


def compile_arm(folder, p, public, arm):
    proposal = read(folder/arm/'teacher.json')['value']; jsonschema.validate(proposal, PROPOSAL)
    texts = {k: public[k]['views'][0]['public']['source_text'] for k in p['teacher_sources']}
    validate_operations(proposal['operations'], texts)
    parts = []
    for module in proposal['source_functions']:
        tree = ast.parse(module)
        if any(not isinstance(n,ast.FunctionDef) for n in tree.body):
            raise ValueError('Only complete pure function modules')
        pieces = [ast.get_source_segment(module,n) for n in tree.body]
        if ast.dump(ast.parse('\n\n'.join(pieces)),include_attributes=False) != ast.dump(tree,include_attributes=False):
            raise ValueError('Function extraction changed AST')
        parts.extend(pieces)
    code = function_update(read(folder/'base.json')['source_program'], parts)
    if any(isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value in ('Entailment','Contradiction','NotMentioned') for n in ast.walk(ast.parse(code))):
        raise ValueError('Native labels in source program')
    bundle = {'operations': proposal['operations'], 'program': code, 'spec': read(folder/'base.json')['grammar']}
    plans = []
    for k in p['teacher_sources']:
        pub = public[k]['views'][0]['public']; units, _ = execution_source_units(pub['source_text'], source_spans(material_public(pub)))
        q = prepare_queries(code, bundle['operations'], pub['source_text'], units)
        plans.append({'source': k, 'queries': q})
    immutable_json(folder/arm/'compiled.json', bundle)
    immutable_json(folder/arm/'offline_plans.json', {'plans': plans, 'new_model_requests': 0,
        'not_semantic_correctness_or_utility_evidence': True})
    return bundle


def evaluate(arm, *, reuse=False, no_examples=False):
    folder, p, ledger, public = setup(); b = compile_arm(folder,p,public,arm)
    if reuse:
        gate = read(folder/'smoke_semantic_decision.json')
        if not gate['continue_to_fixed_reuse']: raise ValueError('Smoke did not establish semantic usability')
        frozen = {a: digest(read(folder/a/'compiled.json')) for a in ARMS}
        immutable_json(folder/'reuse_freeze.json', {'bundles': frozen, 'parents': p['reuse_sources'], 'no_reuse_adaptation': True})
    stage = ('reuse' if reuse else 'smoke')+('_NoExamples' if no_examples else '')
    keys = p['reuse_sources'] if reuse else p['teacher_sources'][:1]
    client = FrozenExecutor(ledger, folder, p['executor_profile'])
    for key in keys:
        dst = folder/stage/arm/(key.replace(':','_')+'.json')
        if dst.exists(): continue
        source = public[key]; pub = source['views'][0]['public']; spans = source_spans(material_public(pub))
        units, supports = execution_source_units(pub['source_text'], spans)
        queries = prepare_queries(b['program'], b['operations'], pub['source_text'], units)
        immutable_json(folder/stage/arm/(key.replace(':','_')+'_plan.json'), {'queries': queries})
        answers, events = read_semantics(client, RUN+':'+stage+':'+arm+':'+key, key,
            b['operations'], queries, units, examples=not no_examples)
        immutable_json(folder/stage/arm/(key.replace(':','_')+'_semantic.json'), {'answers':answers,'events':events})
        raw = finish(b['program'], pub['source_text'], units, answers); jsonschema.validate(raw, OUTPUT)
        schema = constructors(b['spec']); nodes = []
        for i,r in enumerate(raw['statements']):
            nodes.append({'id':i,'sort':term_sort(r['term'],schema),'term':r['term'],
                'support_ids':expand_unit_support(r['support_ids'],supports),'child_ids':[],
                'ambiguous':False,'source_semantics_verified':False})
        interpretation = {'nodes':nodes,'roots':list(range(len(nodes))),
            'source_program_output':raw,'complete':raw['complete'],'unresolved':raw['unresolved']}
        # Score only after the reader has completed. Native labels never enter
        # the acquired planner, operation execution or source finisher.
        grading = read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
        views = []
        for view in source['views']:
            result = apply_current(b['spec'], {'rules':[],'disabled_rules':[],'acquired_pairs':[]}, interpretation, view)
            core = result['value']['handled']
            proof = sorted({spans[s]['public_sentence_id'] for n in result['value']['used_nodes']
                for s in nodes[n]['support_ids'] if 'public_sentence_id' in spans[s]})
            score = grade_view(source['dataset'],view,grading[key][view['id']],result['value']['answer'],proof) if core else None
            views.append({'view':view['id'],'core_executed':core,'fallback':not core,
                'fallback_not_executed_in_this_component_test':not core,'execution':result,'score':score,'proof_sentence_ids':proof})
        row = {'source':key,'arm':arm,'stage':stage,'interpretation':interpretation,'views':views,
            'operation_queries':len(queries),'physical_batches':len(events),
            'semantic_review_pending':True,'goal_complete':False}
        immutable_json(dst,row)
        print(json.dumps({'stage':stage,'arm':arm,'source':key,'queries':len(queries),
            'batches':len(events),'core':sum(v['core_executed'] for v in views),
            'native_correct':sum(bool(v['score'] and v['score']['correct']) for v in views)}),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('stage',choices=['prepare','acquire','compile','evaluate'])
    parser.add_argument('--arm',choices=ARMS,default=ARMS[0]); parser.add_argument('--reuse',action='store_true'); parser.add_argument('--no-examples',action='store_true')
    args = parser.parse_args()
    with (ROOT/'artifacts/rr_v2_preflight/current_semantic_operations_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.stage=='prepare': print(prepare()[0])
        elif args.stage=='acquire': acquire(args.arm)
        elif args.stage=='compile':
            folder,p,ledger,public=setup(); b=compile_arm(folder,p,public,args.arm); print({'operations':len(b['operations'])})
        else: evaluate(args.arm,reuse=args.reuse,no_examples=args.no_examples)
