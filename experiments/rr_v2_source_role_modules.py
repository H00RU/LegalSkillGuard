"""Source-generated role interfaces and obligation pilot on fixed TRAIN."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor, MethodTeacher
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.preflight import science_files
from legal_skill_guard.rr.source_obligations import compile_module, verify

ROOT = Path(__file__).resolve().parents[1]
RUN = 'redesign_source_roles_v1_20261109'
STAGE = ROOT / 'artifacts/rr_method_redesign_20261109' / RUN
OLD = ROOT / 'artifacts/rr_method_runtime_20261107/method_runtime_reference_v10_20261109'


def obj(properties):
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)


STRING = dict(type='string')
SCHEMA = obj(dict(
    inputs=dict(type='array', items=obj(dict(name=STRING, type=dict(type='string', enum=['integer','boolean']),
        meaning=STRING, origin=dict(type='string',enum=['case','external_rule']), quote=STRING))),
    output_type=dict(type='string',enum=['integer','boolean']), domain=STRING, domain_quote=STRING,
    expression=STRING, rule_quote=STRING,
    obligations=dict(type='array',items=obj(dict(name=STRING,condition=STRING,assertion=STRING,quote=STRING))),
    unresolved=dict(type='array',items=STRING)))


def prepare():
    old = json.loads((OLD / 'seal.json').read_text())
    public = {s['key']:s for s in json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources']}
    targets = [dict(id='sara151_percentage',ordinal=18,target='Applicable percentage under section151(d)(3)(B), in integer percentage points, for the cases where section151(d)(3)(A) applies. Do not compute the exemption amount or tax.'),
        dict(id='sara63_basic_deduction',ordinal=8,target='The basic standard deduction, in dollars, under section63(c)(2), modified where required by(c)(5),(c)(6),(c)(7). Exclude the additional standard deduction under(c)(3)/(f). All external legal classifications must be explicit input roles, not guessed.'),
        dict(id='sara68_f_activation',ordinal=76,target='Whether the taxable-year-beginning condition of section68(f) holds. Result true means that the exception provision68(f) applies. Do not output whether the overall section68 applies or a deduction amount.')]
    system = ('Learn a generic source-bound executable module from the supplied policy. No case facts or answers are supplied. '
        'Derive the primitive input roles yourself, with names, integer/boolean types, meanings and exact policy quotes. '
        'case means an externally observed fact; external_rule means a referenced legal amount or classification that must be provided, never guessed. '
        'Do not move the target legal conclusion or a numeric comparison to an input Boolean. '
        'Use a nonempty, source-justified domain. List unsupported rules/dependencies in unresolved instead of completing them. '
        'expression computes the requested generic function. Allowed syntax: integer/Boolean literals, declared names, + - * //, '
        'single comparisons, and/or/not, a if condition else b, min/max and ceildiv(n,d). Division requires a positive denominator. '
        'No imports, assignment, functions, attributes, floats, arrays or other calls. '
        'Also give independently meaningful postconditions from the policy: each has a condition over inputs and an assertion using result. '
        'All quotes must be exact nonempty substrings of the policy, not citation labels or paraphrases. '
        'Neither current-case success nor program/postcondition agreement proves policy fidelity. Return only the schema object.')
    for target in targets:
        target['source'] = old['sources']['train'][target['ordinal']-1]
        target['rules'] = public[target['source']]['public']['rules']
        target['messages'] = [dict(role='system',content=system),dict(role='user',content=json.dumps(dict(policy=target['rules'],requested_function=target['target']),ensure_ascii=False))]
    files = science_files(ROOT)
    protocol = ROOT/'reports/method_redesign_20261109/source_role_pilot_protocol.md'
    seal = dict(run_id=RUN,files=files,binding=dict(code_hash=digest(files),config_hash=digest(old['config'])),
        config=old['config'],sources=old['sources'],schema=SCHEMA,targets=targets,
        protocol_sha256=hashlib.sha256(protocol.read_bytes()).hexdigest(),
        initial_roles_or_case_facts_provided=False, original_labels_opened=False, TEST_authorized=False,
        preregistered_original_case_TRAIN_ordinals=[18,8,85,76],goal_complete=False)
    immutable_json(STAGE/'seal.json',seal)
    return seal


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','executor','teacher'])
    parser.add_argument('--target',choices=['sara151_percentage','sara63_basic_deduction','sara68_f_activation']);args=parser.parse_args()
    seal=prepare()
    if args.action=='prepare':
        print(json.dumps(dict(run_id=RUN,targets=[t['id'] for t in seal['targets']],new_calls=0)));return
    if args.target is None:
        parser.error('Select a fixed target explicitly so each result is inspected before the next dispatch')
    ledger=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        binding=seal['binding'],sources=seal['sources'],authorization_hash=seal['protocol_sha256'],
        question='Can source-only model-generated roles, scopes and obligations form faithful executable modules and support fixed original tasks? Compare independent same-contract Qwen/teacher controls, not method efficacy by format alone.')
    executor=MethodExecutor(ledger,STAGE,seal['config']['executor'])
    teacher=MethodTeacher(ledger,STAGE,seal['config']['teacher'])
    for target in seal['targets']:
        if target['id'] != args.target:continue
        path=STAGE/(args.action+'_'+target['id']+'.json')
        if path.exists():
            print(json.dumps(dict(role=args.action,target=target['id'],existing_result=True)));continue
        cid=RUN+':'+args.action+':'+target['id']+':0'
        if args.action=='executor':
            executor.readiness()
            wire=executor.generate(cid,source=target['source'],purpose='method_train_synthesis',
                messages=target['messages'],schema=SCHEMA,thinking=False)
            raw=wire['content']
        else:
            wire=teacher.summarize(cid,source_ids=[target['source']],system_prompt=target['messages'][0]['content'],
                user_prompt=target['messages'][1]['content'],output_schema=SCHEMA)
            raw=wire['value']
        try:
            value=json.loads(raw) if isinstance(raw,str) else raw
            module=compile_module(value,target['rules'])
            checked=verify(module)
            validation=dict(status='compiled_source_roles',signature=module.signature,checks=checked,quote_positions=module.quote_positions)
        except Exception as exc:
            validation=dict(status='rejected',error_type=type(exc).__name__,error=str(exc));value=raw
        immutable_json(path,dict(captured_utc=datetime.now(timezone.utc).isoformat(),role=args.action,target=target['id'],
            source=target['source'],module=value,physical_response=wire,validation=validation,
            independent_source_review='pending',core_method_success=False,live_library_updated=False))
        print(json.dumps(dict(role=args.action,target=target['id'],validation=validation),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
