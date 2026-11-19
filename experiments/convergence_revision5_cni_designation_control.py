"""Test shared source scope and adjudicate the paired designation result."""

from collections import Counter
from pathlib import Path
import base64
import hashlib
import json
import re
import sqlite3
from statistics import mean

from experiments.convergence_revision5_cni_designation import (
    C, DATASET, DONE, E, LEDGER, MANDATORY, N, OPTION, POINTER, ROLES, ROOT, TARGET, TASK,
    bind_request, decode, layouts, materials, read, sha, spans_for,
)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


DEFINITION = re.compile(r'Confidential Information["”]?\s+(?:(?:shall|will)\s+)?mean\b', re.I)
INDEPENDENT_MARK = (
    ('explicit_regardless', re.compile(r'shall apply to all Confidential Information.*whether or not it is designated as', re.I)),
    ('by_nature', re.compile(r'Confidential Information also includes.*marked .{0,50} or should be deemed by its nature to be confidential', re.I)),
)
DESIGNATION_ALTERNATIVES = (
    ('disclosing_party_or_reasonable_circumstances', re.compile(
        r'designated as Confidential Information by Disclosing Party, or .*circumstances should reasonably be assumed by Receiving Party', re.I)),
    ('mark_or_otherwise_disclosed', re.compile(
        r'appropriately marked as .* or otherwise disclosed in a manner consistent with its proprietary and confidential nature', re.I)),
)
WRITTEN = re.compile(r'^\(a\) if in writing, is marked .* at the time of disclosure, or$', re.I)
ORAL = re.compile(r'^\(b\) if provided orally or visually, is identified as confidential at the time of disclosure and confirmed in writing', re.I)


def direct(view):
    """Use explicit qualification language and its nearest operative definition."""
    clauses = [' '.join(s.split()) for s in spans_for(view)]
    witnesses = []
    for i, text in enumerate(clauses):
        for form, pattern in INDEPENDENT_MARK:
            if pattern.search(text):
                witnesses.append((C,(i,),form))
        for form, pattern in DESIGNATION_ALTERNATIVES:
            if pattern.search(text):
                for j in range(i-1,max(-1,i-5),-1):
                    if DEFINITION.search(clauses[j]):
                        witnesses.append((C,(j,i),form))
                        break
        if (0<i<len(clauses)-1 and WRITTEN.search(text) and ORAL.search(clauses[i+1])
                and re.search(r'Confidential Information.*includes.*which$',clauses[i-1],re.I)):
            witnesses.append((E,(i-1,i,i+1),'written_mark_or_oral_identification'))
    labels = {label for label,_,_ in witnesses}
    if len(labels)!=1:
        return {'answer':None,'evidence':[],'witnesses':[]}
    answer, = labels
    ids = sorted({i for _,group,_ in witnesses for i in group})
    return {'answer':answer,'evidence':ids,'witnesses':[form for _,_,form in witnesses]}


def verified_read(db, identity, asset, case, recorded, parameters):
    status,role,source,purpose,fingerprint,result = db.execute(
        'select status,role,source,purpose,request_hash,result from calls where id=?',(identity,)).fetchone()
    assert (status,role,source,purpose)==('completed','executor',case['source'],'skill_actor')
    raw = json.loads(result)
    path = Path(raw['artifact_directory'])
    request,wire = (read(path/name) for name in ('request.json','wire_request.json'))
    data = base64.b64decode(wire['body_b64'],validate=True)
    payload = request['payload']
    assert read(path/'result.json')==raw
    assert hashlib.sha256(data).hexdigest()==wire['body_sha256'] and json.loads(data)==payload
    assert raw['request_hash']==request['request_hash']==fingerprint and request['id']==identity
    assert payload['model']=='Qwen/Qwen3-8B' and raw['thinking_requested'] is False
    assert payload['chat_template_kwargs']['enable_thinking'] is False
    settings = {k:v for k,v in payload.items() if k not in ('messages','response_format')}
    assert not parameters or settings==parameters
    parameters.update(settings)
    messages,schema = bind_request(asset,case)
    assert payload['messages']==messages and json.loads(messages[-1]['content'])==case['payload']
    assert payload['response_format']['json_schema']['schema']==schema
    assert {**decode(asset,case,schema,raw),'physical_call_id':identity}==recorded
    return raw['usage']['total_tokens']


def score_rows(cases, records, grades, wires):
    results=[]
    for case,pair,native in zip(cases,records,wires,strict=True):
        key = case['source']
        truth = grades[key][TASK]
        outcome={}
        for role,p in {'early_program':case['prior'],'retrospective_direct':native,**pair}.items():
            grade = grade_view(DATASET,case['view'],truth,p['answer'],p['evidence'])
            outcome[role] = {'exact': grade['grade'],'evidence_f1':grade['evidence_f1'],
                             'exact_times_evidence_f1':grade['grade']*grade['evidence_f1'],
                             'source_polarity': p['answer']==case['expected_source_label'],
                             'asserted':p['answer'] in (C,E,N)}
        results.append({'stratum':case['review_stratum'],'ambiguous_benchmark_scope':case['source_benchmark_scope_ambiguous'],
                        'results':outcome})
    return results


def aggregate(rows):
    return {role:{field:mean(r['results'][role][field] for r in rows) for field in fields}
            for role,fields in rows[0]['results'].items()}


def audit():
    stage = ROOT/read(POINTER)['artifact_root']
    terminal = read(stage/'terminal.json')
    assert terminal['status']==DONE and terminal['TRAIN_only']
    protocol,cases,prior = materials()
    assert stage.name==digest(protocol) and read(stage/'binding.json')==protocol
    assert read(stage/'cases.json')==cases
    assert all(sha(stage/'source_snapshot'/p)==h for p,h in protocol['source_sha256'].items())
    records = read(stage/'paired_reads.json')
    baseline = [direct(case['view']) for case in cases]
    coverage = [direct(row['view']) for row in prior]
    control = {'direct_outputs':baseline,'direct_all_train':coverage,
               'candidate_protocol_sha256':stage.name,
               'methods_source_sha256':sha(Path(__file__))}
    evidence = stage/'designation_attribution'/digest(control)
    immutable_json(evidence/'control_predictions.json',control)
    tokens = Counter()
    params = {}
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        counts = dict(db.execute('select status,count(*) from calls group by status'))
        assert not counts.get('reserved')
        for case,pair in zip(cases,records,strict=True):
            for role,asset in zip(ROLES,layouts()[1],strict=True):
                identity = pair[role]['physical_call_id']
                tokens[role] += verified_read(db,identity,asset,case,pair[role],params)
    assert sum(tokens.values())==terminal['executor_tokens']
    path = ROOT/protocol['grade_path']
    assert sha(path)==protocol['grade_sha256']
    grades=read(path)
    rows=score_rows(cases,records,grades,baseline)
    attrs = [r for r in rows if not r['ambiguous_benchmark_scope']]
    fixed_unknown_pair = [case for case,pair in zip(cases,records,strict=True)
                          if all(pair['fixed']['relations'].get(k) is None for k in (TARGET,OPTION))
                          and pair['fixed']['relations'].get(MANDATORY) is True]
    summary = {
        'TRAIN_only':True, 'paired_train_contracts':len(cases),
        'verified_original_common_responses':len(prior),
        'verified_new_responses':terminal['executor_calls'],
        'executor_tokens_by_role':dict(tokens),'new_teacher_requests':0,'ledger':counts,
        'proof_states':protocol['consumer_states'],
        'original_common_all_train_native_exact':terminal['prior_native_correct'],
        'original_common_all_train_answer_counts':terminal['prior_labels'],
        'all_train_native_label_counts':terminal['prior_native_gold'],
        'all_train_direct_explicit_rule_matches':sum(r['answer'] is not None for r in coverage),
        'all_train_direct_explicit_rule_correct_matches':sum(
            r['answer'] is not None and r['answer']==grades[row['source']][TASK]['answer']
            for r,row in zip(coverage,prior,strict=True)),
        'fixed_unknown_pair_with_asserted_universal_requirement':len(fixed_unknown_pair),
        'native_correct_if_accepting_only_those_fixed_universal_assertions':sum(
            grades[c['source']][TASK]['answer']==E for c in fixed_unknown_pair),
        'matched_pair_aggregate':aggregate(rows),'source_explicit_aligned_aggregate':aggregate(attrs),
        'per_structure':rows,'frozen_original_model_and_libraries_changed':False,
        'bound_runner_sha256':sha(Path(__file__).with_name('convergence_revision5_cni_designation.py')),
        'direct_control_runner_sha256':sha(Path(__file__)),
    }
    immutable_json(evidence/'summary.json',summary)
    print(json.dumps({'artifact_root':str(evidence.relative_to(ROOT)),**summary},sort_keys=True))


if __name__=='__main__':
    audit()
