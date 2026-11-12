"""Acquire reusable source recognizers versus independent whole-source code.

The acquisition cohort and native TRAIN reuse checks are unchanged. This
finite comparison tests the reading component rather than new label prompts.
"""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

import jsonschema

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema, grade_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.relational_compiler import spans_for, read_schema, bind_records, apply
from legal_skill_guard.skill_evolution.source_schema import TASKS, LABELS
from legal_skill_guard.skill_evolution.span_compiler import execute_json, validate_procedure
from legal_skill_guard.skill_evolution.teacher_transport import pack, unpack, INSTRUCTION
from experiments.legal_skill_evolution_role_TRAIN import physical_snapshot
from experiments.legal_skill_evolution_span_compiler import warm_base

RUN = 'legal_skill_evolution_source_program_acquisition_20261113'
PRIOR = 'legal_skill_evolution_relational_acquisition_v2_20261113'
ARMS = ('LearnedSourceCompiler', 'IndependentWholeProgram')
SCHEMA = record_schema({'architecture': {'type': 'string', 'enum': ['source_compiler', 'direct_program']},
    'rationale': {'type': 'string'}, 'compiler_choice': {'type': 'string',
        'enum': ['ScopedAcquisition', 'FreeAcquisition', 'none']},
    'source_program': {'type': ['string', 'null']}, 'decision_program': {'type': ['string', 'null']}})
read = lambda p: json.loads(p.read_text())
COMMON = '''Acquire a reusable pure Python skill from the fixed original TRAIN evidence. Both models stay frozen; this updates external code. No source IDs, company-specific branches, per-contract answer tables or old-example factual copying. Learn legal action/participant structure from current source text and native TRAIN supervision, not native labels as extracted source facts. Source spans are complete public sentence/paragraph segmentation with integer IDs. Input code has def apply(inputs, premises), and may define ordinary pure top-level helper functions; no imports, nested functions, decorators, recursion, module-level statements besides functions, filesystem, network, introspection or exception types besides ValueError/KeyError/TypeError. Basic Python containers, loops, comprehensions, string methods and prebound re are allowed, under the same shared pure executor. Allowed builtin names: min,max,sum,len,abs,round,sorted,all,any,int,float,bool,str,list,dict,set,tuple,range,enumerate,zip,isinstance,ValueError,KeyError,TypeError.
The NEW source-program path receives inputs={source_text:complete_current_text,source_spans:[{id,field,start,end,text,public_sentence_id?}]} and premises={}. No native question or label is supplied to a source compiler. Code must inspect actual current text; regex/span analysis is allowed. Regex groups are not new legal semantics: resolve direction, deontic force, protected-information subjects versus governed recipients, actor/affiliate ownership, conditions and cross-clause references. Do not convert missing evidence into a negative rule or empty set; unknown source fields remain null.
Architecture source_compiler: choose one supplied frozen relation specification. Return from source_program exactly its read_schema JSON: every relation frame maps to a list of instances {support_ids:[current_span_ids],fields:{FIELD:{value:canonical_concept_or_list_or_null,support_ids:[current_span_ids]}}}. Each known field needs actual supporting IDs within that instance. All listed fields are required, unresolved values null. [] on a frame means no acquired instance, not proof of legal absence. Do not invent role words or use contract-specific labels to force a task answer. The corresponding supplied frozen decision procedure is unchanged and executed separately. Use decision_program=null.
Architecture direct_program: compiler_choice=none,source_program=null; independently learn a complete direct decision_program. It receives the same complete current source_text/source_spans plus tasks={nda-5:actual_public_question,nda-7:actual_public_question}. Return {TASK:{handled:bool,answer:Entailment|Contradiction|NotMentioned,evidence_span_ids:[current_span_ids]}} for both tasks. Missing or unresolved support means handled=false. A handled native answer requires actual relevant current span IDs; no answer may be chosen from source identity. You may internally use the same relation decomposition if useful; do not intentionally weaken this strong simple control.
Both arms have identical original full material, native supervision, both previous acquired specifications and actual failed records. All acquisition/repair costs are counted. The fixed two other TRAIN reuse sources are withheld here; do not infer their contents. Keep the code compact. Source compilers cannot contain native answer label literals; direct programs may return them. No parameter updates or new datasets.'''


def prepare(root):
    folder = root / 'artifacts' / RUN
    if (folder / 'protocol.json').exists(): return folder, read(folder / 'protocol.json')
    prior = root / 'artifacts' / PRIOR
    old = read(prior / 'protocol.json')
    before = physical_snapshot(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3')
    if any(x.get('reserved', 0) for x in before.values()): raise ValueError('Reconcile pending requests')
    public = {s['key']: s for s in read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    evidence = unpack(read(prior / 'teacher_evidence.json'))
    specs = {a: read(prior / a / 'frozen_candidate.json')['spec'] for a in ('ScopedAcquisition', 'FreeAcquisition')}
    training = old['teacher_sources']
    extra = {'same_original_TRAIN_evidence': evidence,
        'both_actual_frozen_relation_specs': specs,
        'public_segmentation_by_TRAIN_source': {k: public[k]['views'][0]['public']['sentence_spans'] for k in training},
        'actual_prior_TRAIN_records': {a: [r for r in read(prior / 'completed.json')['results'][a]
            if r['source'] in training] for a in specs},
        'diagnosis': 'Current abstract-schema reads copy whole role domains; a current lexical occurrence codec still merges employees in information descriptions with governed recipients. Learn an operational source recognizer, not more field descriptions. Existing correct labels may have incorrect proof. No gold field values are supplied by the host.'}
    packed = pack(extra); assert unpack(packed) == extra
    hashes = {}
    paths = list((root / 'legal_skill_guard/skill_evolution').glob('*.py'))
    paths += list((root / 'tests').glob('test_skill_evolution*.py')) + [Path(__file__).resolve()]
    for p in sorted(paths):
        rel = p.relative_to(root);target = folder / 'source_snapshot' / rel
        target.parent.mkdir(parents=True, exist_ok=True);target.write_bytes(p.read_bytes())
        hashes[str(rel)] = hashlib.sha256(p.read_bytes()).hexdigest()
    profile = read(root / 'configs/legal_skill_evolution_formal_v5_20261111.json')
    protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
        'created_utc': datetime.now(timezone.utc).isoformat(), 'parent_run': PRIOR,
        'teacher_sources': training, 'fixed_TRAIN_reuse_sources': old['frozen_TRAIN_probes'],
        'arms': list(ARMS), 'teacher_profile': profile['teacher'], 'executor_profile': profile['executor'],
        'question': 'Can executable source recognition learned from the same TRAIN repair actual semantic reading failures, and does a same-information independent whole program absorb the result?',
        'workload': 'One independent teacher per arm, then deterministic code/proof checks on the same eight acquisition and two previously fixed original TRAIN reuse sources. No executor generation, new source pool, seed, full study or unchanged retry.',
        'learning_object': 'A persistent current-source recognition program, versus an independent whole-source answer program. The existing method consumer stays fixed to isolate source acquisition.',
        'no_independent_contribution_assumed_from_common_code_execution': True,
        'automatic_retries': 0, 'source_snapshot': hashes, 'ledger_before': before,
        'no_new_full_training_DEV_TEST_or_paper': True}
    immutable_json(folder / 'teacher_evidence.json', packed)
    immutable_json(folder / 'frozen_specs.json', specs)
    immutable_json(folder / 'protocol.json', protocol)
    with sqlite3.connect(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
        immutable_json(folder / 'ledger_rows_before.json', db.execute('select * from calls order by id').fetchall())
    return folder, protocol


def acquire(root):
    folder, protocol = prepare(root)
    ledger = EvolutionLedger(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        sources={'train': protocol['teacher_sources'] + protocol['fixed_TRAIN_reuse_sources'], 'dev': [], 'test': []},
        binding=digest(protocol), teacher_concurrency=2)
    user = json.dumps(read(folder / 'teacher_evidence.json'), ensure_ascii=False)
    def one(arm):
        if (folder / arm / 'teacher.json').exists(): return
        instruction = ('Acquire source_compiler using compiler_choice=ScopedAcquisition. Learn actual source code to emit faithful instances of those existing semantic frames; keep its consumer fixed.'
            if arm == 'LearnedSourceCompiler' else 'Independently select the strongest source_compiler (either frozen spec) or a direct_program with your own complete reasoning. Full source code is permitted; do not default to the previous failed neural field reader.')
        system = INSTRUCTION + '\n' + COMMON + '\n' + instruction
        call = RUN + ':teacher:' + digest({'arm': arm, 'system': system, 'user': user, 'schema': SCHEMA})
        result = FrozenTeacher(ledger, folder, protocol['teacher_profile']).propose(call,
            source_ids=protocol['teacher_sources'], system_prompt=system, user_prompt=user, output_schema=SCHEMA)
        immutable_json(folder / arm / 'teacher.json', result)
    errors = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(one, a) for a in ARMS]
        for job in jobs:
            try: job.result()
            except Exception as exc: errors.append(type(exc).__name__ + ': ' + str(exc))
    immutable_json(folder / 'teacher_settlement.json', {'ledger': physical_snapshot(ledger.path), 'errors': errors})
    if errors: raise ValueError(str(errors))


def evaluate(root):
    folder, protocol = prepare(root)
    for name, expected in protocol['source_snapshot'].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected: raise ValueError(name)
    if any(x.get('reserved', 0) for x in physical_snapshot(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3').values()):
        raise ValueError('Wait for the same teacher requests')
    public = {s['key']: s for s in read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    grading = read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    specs = read(folder / 'frozen_specs.json')
    base = warm_base(root, read(root / 'artifacts/legal_skill_evolution_span_compiler_20261112/protocol.json'))
    results = {}
    for arm in ARMS:
        proposal = read(folder / arm / 'teacher.json')['value'];jsonschema.validate(proposal, SCHEMA)
        compiler = proposal['architecture'] == 'source_compiler'
        if arm == 'LearnedSourceCompiler' and (not compiler or proposal['compiler_choice'] != 'ScopedAcquisition'):
            raise ValueError('Candidate source recognition must preserve its fixed consumer')
        code = proposal['source_program'] if compiler else proposal['decision_program'];validate_procedure(code, allow_helpers=True)
        if compiler:
            assert proposal['decision_program'] is None
            if any(isinstance(n, ast.Constant) and n.value in LABELS for n in ast.walk(ast.parse(code)) if isinstance(getattr(n,'value',None), str)):
                raise ValueError('A source compiler may not emit native labels')
        else: assert proposal['source_program'] is None and proposal['compiler_choice'] == 'none'
        rows = []
        for key in protocol['teacher_sources'] + protocol['fixed_TRAIN_reuse_sources']:
            path = folder / arm / (key.replace(':', '_') + '.json')
            if path.exists(): rows.append(read(path));continue
            source = public[key];spans = spans_for(source);records=[];raw=None;outputs={};failure=None
            inputs={'source_text':source['views'][0]['public']['source_text'],'source_spans':spans}
            if not compiler: inputs['tasks']={v['id']:v['public']['question'] for v in source['views'] if v['id'] in TASKS}
            try:
                raw = execute_json(code, inputs, {}, allow_helpers=True)
                if compiler: records = bind_records(specs[proposal['compiler_choice']],spans,raw)
                else:
                    schema=record_schema({task:record_schema({'handled':{'type':'boolean'},
                        'answer':{'type':'string','enum':list(LABELS)},'evidence_span_ids':{'type':'array','uniqueItems':True,
                            'items':{'type':'integer','minimum':0,'maximum':len(spans)-1}}}) for task in TASKS})
                    jsonschema.validate(raw,schema);outputs=raw
            except (ValueError,TypeError,KeyError,jsonschema.ValidationError) as exc: failure=type(exc).__name__+': '+str(exc)
            inherited={v['view']:v for v in base[key]['views']};views=[]
            for view in source['views']:
                value=None;error=failure;proof=[]
                if view['id'] in TASKS and error is None:
                    try:
                        if compiler:
                            value=apply(specs[proposal['compiler_choice']],source,view,records)
                            proof=sorted({s['public_sentence_id'] for i in value['used_records'] for s in records[i]['source_evidence'] if 'public_sentence_id' in s})
                        else:
                            value=outputs[view['id']]
                            if value['handled'] and not value['evidence_span_ids']: raise ValueError('Handled direct answer lacks current proof')
                            proof=sorted({spans[i]['public_sentence_id'] for i in value['evidence_span_ids'] if 'public_sentence_id' in spans[i]})
                    except (ValueError,TypeError,KeyError) as exc: error=type(exc).__name__+': '+str(exc)
                core=value is not None and value['handled'] and error is None
                answer=value['answer'] if core else inherited[view['id']]['execution']['answer']
                score=grade_view(source['dataset'],view,grading[key][view['id']],answer,proof) if core else inherited[view['id']]['score']
                views.append({'view':view['id'],'answer':answer,'core_executed':core,'fallback':not core,'score':score,'execution':value,'proof_sentence_ids':proof,'error':error})
            row={'arm':arm,'source':key,'architecture':proposal['architecture'],'records':records,'raw_program_output':raw,'views':views,
                'core_views':sum(v['core_executed'] for v in views),'core_correct':sum(v['core_executed'] and v['score']['correct'] for v in views),
                'source_semantic_review_pending':True,'goal_complete':False}
            immutable_json(path,row);rows.append(row)
            print(json.dumps({'arm':arm,'source':key,'core':row['core_views'],'correct':row['core_correct'],'error':failure}),flush=True)
        results[arm]=rows
    immutable_json(folder/'completed.json',{'results':results,'goal_complete':False,'semantic_and_contribution_review_pending':True,
        'ledger_after':physical_snapshot(root/'artifacts/rr_v2_preflight/research_ledger.sqlite3')})


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','acquire','evaluate']);args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    if args.stage=='prepare': print(prepare(root)[0])
    elif args.stage=='acquire': acquire(root)
    else: evaluate(root)
