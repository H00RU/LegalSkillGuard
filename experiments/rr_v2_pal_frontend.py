"""Original TRAIN validation of the compact PAL-style source frontend."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3
from jsonschema import ValidationError

from experiments.rr_v2_source_probe import load
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor, MethodTeacher
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.method_run import load_executor_lock
from legal_skill_guard.rr.pal_frontend import pal_prompt,pal_schema,lower_pal,render_pal,decode_pal_text
from legal_skill_guard.rr.preflight import science_files, scientific_code_binding, score_source
from legal_skill_guard.rr.source_execution import assess_source, prepare_followup, accept_followup
from legal_skill_guard.rr.source_inference import _decode
from legal_skill_guard.rr.source_program import compile_source
from legal_skill_guard.rr.source_validation import validation_feedback
from legal_skill_guard.rr.wire_validation import validate_wire
from legal_skill_guard.rr.client import WireError
from legal_skill_guard.inference.codex_cli_client import CodexInvocationError
from legal_skill_guard.rr.compiler_templates import make_template
from legal_skill_guard.rr.rule_templates import matching_rule_template,instance_request,instantiate_rule_template

OFFLINE = 'reports/rr_method_runtime_20261107/offline_reference_frontend_v20_20261108.json'
QUESTION = 'Does compact source-annotated Python remove legal/numeric generation overhead while preserving existing source, scope, type and completion checks under locked OFF?'
TEACHER_QUESTION = 'Can a real original TRAIN teacher program provide complete source-faithful reusable compiler material in the compact Python interface, without a native answer, instead of incomplete or paragraph-enumerating executor output?'


def prepare(root, run_id, source_id, library_path, role='executor'):
    cfg, manifest, source, config, sources, stage = load(root, run_id, source_id, library_path, role)
    if source['dataset'] == 'ProofWriter_OWA_depth5':
        raise ValueError('Use the existing aligned-atom frontend for the original logic contract')
    load_executor_lock(root, config['executor'])
    from legal_skill_guard.rr.compiler_templates import validate_template
    prefix=set(sources['train'][:sources['train'].index(source['key'])])
    public={s['key']:s for s in json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources']}
    for item in (config['library'] or {}).get('compiler_templates',[]):
        validate_template(item)
        if item['source']['key'] not in prefix or item['source']!=public[item['source']['key']]:
            raise ValueError('Compiler templates must be exact strictly earlier original TRAIN sources')
    files = science_files(root)
    offline = json.loads((root/OFFLINE).read_text())
    if files != offline['files'] or offline['exit_code'] or not offline['network_blocked']:
        raise ValueError('Matching successful offline evidence is required')
    with sqlite3.connect('file:'+str(root/cfg['ledger_path'])+'?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Reconcile the actual pending physical request')
        baseline = [{'call_id': cid, **{k: json.loads(raw).get(k) for k in ('finish_reason','usage','elapsed_seconds')}}
                    for cid, raw in db.execute('select id,result from calls where source=? and id like ? order by reserved_at',
                        (source['key'], 'method_runtime_ast_v1_20261107:build:%')).fetchall()]
    match=matching_rule_template(source,config['library']) if role=='executor' else None
    config.update(frontend='learned_identical_rule_template_v1' if match else 'source_annotated_python_v1', question=TEACHER_QUESTION if role=='teacher' else QUESTION,
                  common_frontend_available_to_all_arms=True)
    messages,schema=instance_request(source,match) if match else (pal_prompt(source,config['library'],full_template=role=='teacher'),pal_schema() if role=='teacher' else None)
    tokens = MethodExecutor(None, stage, config['executor']).tokenize(messages, thinking=False)['count']
    if tokens+config['executor']['max_tokens'] > config['executor']['context_tokens']:
        raise ValueError('Original full public source does not fit; no truncation')
    auth = json.loads((root/'docs/rr_v2/method_runtime_authorization_20261107.json').read_text())
    seal = {'run_id':run_id, 'source':source, 'sources':sources, 'files':files, 'config':config,
        'binding':{'code_hash':scientific_code_binding(files), 'config_hash':digest(config)},
        'library_path':library_path, 'source_manifest_hash':digest(manifest), 'ledger_path':cfg['ledger_path'],
        'authorization_hash':digest(auth), 'offline_receipt_hash':digest(offline),
        'initial_messages':messages, 'schema':schema, 'input_tokens':tokens,
        'baseline_paid_responses':baseline, 'TEST_authorized':False, 'full_goal_complete':False}
    immutable_json(stage/'seal.json', seal)
    return {'prepared':True, 'source':source['key'], 'input_tokens':tokens, 'new_model_calls':0}


def run(root, run_id):
    stage = root/'artifacts/rr_method_runtime_20261107'/run_id
    seal = json.loads((stage/'seal.json').read_text())
    if science_files(root) != seal['files']:
        raise ValueError('Frozen scientific bytes changed')
    role=seal['config']['compiler_role']
    _, manifest, source, config, sources, _ = load(root, run_id, seal['source']['key'], seal['library_path'], role)
    if source != seal['source'] or digest(manifest) != seal['source_manifest_hash'] or any(
            config[k] != seal['config'][k] for k in ('executor','teacher','library')):
        raise ValueError('Bound source, model or previous TRAIN material changed')
    result_path = stage/'result.json'
    if result_path.exists():
        return json.loads(result_path.read_text())
    ledger = MethodLedger(root/seal['ledger_path'], run_id=run_id, binding=seal['binding'], sources=sources,
        authorization_hash=seal['authorization_hash'], question=seal['config']['question'])
    client = MethodExecutor(ledger, stage, config['executor'])
    teacher = MethodTeacher(ledger,stage,config['teacher']) if role=='teacher' else None
    match=matching_rule_template(source,config['library']) if seal['config']['frontend']=='learned_identical_rule_template_v1' else None
    if seal['config']['frontend']=='learned_identical_rule_template_v1' and not match:raise ValueError('Exact learned source template changed')
    attempts = []; actions = []; feedback = None; program = None; compiled = None; observed = {}; result = None
    for step in range(1 if role=='teacher' else 2):
        if science_files(root) != seal['files']:
            raise ValueError('Frozen scientific bytes changed')
        prepared = None
        if compiled is not None:
            candidate = prepare_followup(compiled, observed, compilation='answer_separating',
                tokenize=client.tokenize, request_config=config['executor'], thinking=False, library=config['library'],pal_fragments=True)
            actions.append({k:v for k,v in candidate.items() if k not in {'messages','schema'}})
            if candidate['kind'] == 'no_followup':
                break
            prepared = candidate
        if prepared:messages,schema=prepared['messages'],prepared['schema']
        elif match:messages,schema=instance_request(source,match,feedback=feedback)
        else:messages,schema=pal_prompt(source,config['library'],feedback=feedback,full_template=role=='teacher'),pal_schema() if role=='teacher' else None
        if client.tokenize(messages,thinking=False)['count']+config['executor']['max_tokens']>config['executor']['context_tokens']:
            raise ValueError('Full current request exceeds context; no truncation or dispatch')
        immutable_json(stage/('request'+str(step)+'.json'), {'messages':messages, 'schema':schema,
            'prepared':prepared, 'thinking':False})
        try:
            call_id=run_id+(':compile' if role=='teacher' else ':parse:'+str(step))
            if role=='teacher':
                paid=teacher.summarize(call_id,source_ids=[source['key']],system_prompt=messages[0]['content'],
                    user_prompt=messages[1]['content'],output_schema=schema)
                with sqlite3.connect('file:'+str(root/seal['ledger_path'])+'?mode=ro',uri=True) as db:
                    request_hash=db.execute('select request_hash from calls where id=?',(call_id,)).fetchone()[0]
                response={'content':json.dumps(paid['value'],ensure_ascii=False),'request_hash':request_hash,
                    'finish_reason':'teacher_structured_success_not_provider_finish_reason',
                    'usage':paid['invocation'].get('usage'),'elapsed_seconds':paid['elapsed_seconds'],
                    'cache_hit':paid.get('cache_hit',False)}
            else:
                response = client.generate(call_id, source=source['key'], purpose='method_train_synthesis',
                    messages=messages, thinking=False, schema=schema)
        except (WireError,CodexInvocationError) as exc:
            attempts.append({'step':step, 'error_type':type(exc).__name__, 'error':str(exc),
                'physical_failure_preserved_and_charged':True})
            break
        item = {k:response[k] for k in ('request_hash','finish_reason','usage','elapsed_seconds','cache_hit')}
        item.update(step=step, raw_content_sha256=hashlib.sha256(response['content'].encode()).hexdigest())
        try:
            if schema is None:
                value={'code':decode_pal_text(response['content'])}
            else:
                value = _decode(response['content']); validate_wire(value, schema)
            if prepared:
                compiled, observed = accept_followup(compiled, prepared, value, observed, library=config['library'])
                program = compiled['program']
                item['deterministic_adaptations']=compiled.get('deterministic_adaptations',[])
            else:
                if match:
                    program,compiled,instantiation=instantiate_rule_template(source,match,value,library=config['library'])
                    annotation_audit=[];item['template_instantiation']=instantiation
                else:
                    program,annotation_audit = lower_pal(source,value['code'])
                    compiled = compile_source(source, program, library=config['library'])
                item['source_provenance_adaptation']=annotation_audit
                item['residual_context_proofs']=compiled['residual_context_proofs']
                item['derived_context_scopes']=compiled['derived_context_scopes']
                item['scope_bindings']=compiled['scope_bindings']
            result = assess_source(compiled, observed, compilation='answer_separating')
            item['assessment'] = result
            item['program_hash'] = digest(program)
            if result['status'] == 'completion_stable':
                attempts.append(item)
                break
        except (ValueError, TypeError, KeyError, ValidationError) as exc:
            item.update(error_type=type(exc).__name__, error=exc.message if isinstance(exc,ValidationError) else str(exc),
                diagnostics=getattr(exc,'diagnostics',None))
            if isinstance(exc, ValidationError):item['field_path'] = list(exc.path)
            feedback = {'error':item['error'], 'diagnostics':item['diagnostics'],
                'source_validation':validation_feedback(source, program) if program else None}
            compiled = None; result = None
        attempts.append(item)
        if response['finish_reason']=='length':
            actions.append({'kind':'truncated_generation_requires_route_change','new_model_calls':0,
                'reason':'Preserve partial response; do not repeat the same full-generation path'})
            break
    stable = bool(result and result['status'] == 'completion_stable')
    output = {'run_id':run_id, 'source':source['key'], 'binding':seal['binding'], 'frontend':seal['config']['frontend'],
        'attempts':attempts, 'translation_actions':actions, 'program':program, 'observed':observed, 'result':result,
        'status':'component_executed_and_scored' if stable and role=='executor' else 'component_unresolved',
        'compiler_role':role,'independent_executor_compilation':role=='executor' and not match,
        'actual_executor_template_instantiation':role=='executor' and bool(match), 'executor_enable_thinking':False,
        'baseline_paid_responses':seal['baseline_paid_responses'], 'new_baseline_model_calls':0,
        'fallback_used':False, 'oracle_calls':0, 'TRAIN_labels_read':False,'TEST_labels_read':False, 'full_goal_complete':False,
        'bound_files_unchanged':science_files(root)==seal['files']}
    if role=='teacher' and compiled is not None:
        try:
            template=make_template(source,render_pal(program),{'role':'teacher','call_id':call_id,
                'request_hash':response['request_hash'],'model':paid['model'],
                'canonical_code_is_semantics_preserving_rendering_of_actual_program':True,
                'source_provenance_adaptation':annotation_audit,
                'result_file_sha256':hashlib.sha256((stage/'calls'/digest(call_id)/'result.json').read_bytes()).hexdigest()})
            immutable_json(stage/'compiler_template.json',template)
            from legal_skill_guard.rr.source_program import source_theory
            untranslated=[r.source for r in source_theory(compiled).residuals if r.unknown_scope]
            output.update(status='teacher_partial_training_template_validated' if untranslated else 'teacher_training_template_validated',
                untranslated_source_units=untranslated,compiler_template_hash=template['template_hash'],
                fresh_executor_core_success=False,TRAIN_labels_read=False)
        except (ValueError,TypeError,KeyError,ValidationError) as exc:
            output['template_validation_error']={'type':type(exc).__name__,
                'error':exc.message if isinstance(exc,ValidationError) else str(exc)}
    elif stable:
        grade_path = root/'data/packets/rr_v2/grading_only/train.json'
        if hashlib.sha256(grade_path.read_bytes()).hexdigest() != manifest['packet_sha256']['grading_train']:
            raise ValueError('Original TRAIN grading packet changed')
        grade = json.loads(grade_path.read_text())['sources'][source['key']]
        output['TRAIN_score'] = score_source(source, {'answer':result['answer']}, grade)
        output['TRAIN_labels_read']=True
    book = ledger.export()
    output['ledger_totals'] = {k:book[k] for k in ('executor_used','teacher_used')}
    immutable_json(result_path, output)
    immutable_json(root/'reports/rr_method_runtime_20261107'/('reference_frontend_'+run_id+'.json'), output)
    return {k:output[k] for k in ('run_id','source','status','ledger_totals','full_goal_complete')}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['prepare','run'])
    parser.add_argument('--run-id', required=True); parser.add_argument('--source-id'); parser.add_argument('--library-path')
    parser.add_argument('--role',choices=['executor','teacher'],default='executor')
    args = parser.parse_args(); root = Path(__file__).resolve().parents[1]
    if args.action == 'prepare':
        value = prepare(root, args.run_id, args.source_id, args.library_path,args.role)
    else:
        with (root/'artifacts/rr_method_runtime_20261107'/args.run_id/'component.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
            value = run(root, args.run_id)
    print(json.dumps(value, ensure_ascii=False))


if __name__ == '__main__':
    main()
