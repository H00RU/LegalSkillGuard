"""Learn a finite source-check policy from actual frozen-reader outcomes.

The backend is ordinary finite subset selection. The learned objects are source
questions and evidence-window programs; no host legal correction table exists.
Rejected candidates supply negative constraints, never replacement meanings.
"""
from itertools import combinations
import json
import string

import jsonschema

from .native import record_schema
from .semantic_operations import ground_answers, NATIVE_LABELS
from .source_python import execute,validate
from .semantic_execution import strict_json

TEST=record_schema({'name':{'type':'string','minLength':1},
    'operation':{'type':'string'},'candidate_choices':{'type':'array','items':{'type':'string'},'minItems':1},
    'question_template':{'type':'string','minLength':1},'window_program':{'type':'string'},
    'exclusion_on':{'type':'string','enum':['supported','refuted']}})
BANK=record_schema({'rationale':{'type':'string'},'tests':{'type':'array','minItems':1,'maxItems':6,'items':TEST}})
DECISIONS=[{'name':'supported','meaning':'The current source supports the acquired probe proposition.'},
           {'name':'refuted','meaning':'The current source contradicts the acquired probe proposition. Missing context or a merely possible alternative is insufficient.'}]


def canonical_evidence(content):
    """Remove repeated identical witness IDs, preserving the assertion and set.

    The original raw response stays immutable. The strict decoder still checks
    every resulting choice, field, identity and current-source scope. Conflicting
    JSON keys, unknown units or missing meaning are never repaired here.
    """
    value=strict_json(content);changed=[]
    if isinstance(value,dict) and isinstance(value.get('answers'),dict):
        for key,answer in value['answers'].items():
            ids=answer.get('support_ids') if isinstance(answer,dict) else None
            if not isinstance(ids,list) or any(type(i) is not int for i in ids):continue
            unique=list(dict.fromkeys(ids))
            if ids!=unique:
                changed.append({'query':key,'before':ids,'after':unique,
                    'same_witness_identity_set':set(ids)==set(unique)})
                answer['support_ids']=unique
    return json.dumps(value,ensure_ascii=False),changed


def validate_bank(value,operations):
    jsonschema.validate(value,BANK)
    ops={o['name']:o for o in operations};names=[]
    for t in value['tests']:
        names.append(t['name'])
        if t['operation'] not in ops:raise ValueError('Unacquired target operation')
        choices={c['name'] for c in ops[t['operation']]['choices']}
        if not set(t['candidate_choices'])<=choices or len(set(t['candidate_choices']))!=len(t['candidate_choices']):
            raise ValueError('Invalid candidate applicability')
        fields=[name for _,name,_,_ in string.Formatter().parse(t['question_template']) if name is not None]
        if not set(fields)<={'candidate_meaning','candidate_name','operation_question'}:
            raise ValueError('Only explicit semantic template arguments allowed')
        validate(t['window_program'])
        if any(s in t['window_program'] for s in NATIVE_LABELS|{'ContractNLI:'}):
            raise ValueError('Source identity/native answer in a check program')
    if len(set(names))!=len(names):raise ValueError('Duplicate test identity')
    return value


def instantiate(test,case,operation,units):
    if case['operation']!=test['operation'] or case['candidate_choice'] not in test['candidate_choices']:
        return None
    window=execute(test['window_program'],{'source_spans':units,
        'query':{'id':case['id'],'operation':case['operation'],'unit_ids':case['unit_ids']},
        'candidate_choice':case['candidate_choice'],'focus_unit_id':case['focus_unit_id']})
    if set(window)!={'unit_ids'}:raise ValueError('Explicit window only')
    ids=window['unit_ids'];known={u['id'] for u in units}
    if not isinstance(ids,list) or any(type(i) is not int for i in ids) or len(set(ids))!=len(ids) or not set(ids)<=known:
        raise ValueError('Invalid current-source check window')
    if case['focus_unit_id'] not in ids:raise ValueError('Check must retain its actual focus')
    meaning=next(c['meaning'] for c in operation['choices'] if c['name']==case['candidate_choice'])
    question=test['question_template'].format(candidate_meaning=meaning,
        candidate_name=case['candidate_choice'],operation_question=operation['question'])
    identity=case['id']+':'+test['name']
    op={'name':identity,'question':question,'choices':DECISIONS,'examples':[]}
    q={'id':identity,'operation':identity,'unit_ids':ids}
    return op,q


def fit(tests,cases,observations):
    """Exact empirical risk/cost selection, without fitted hyperparameters.

    Compare subsets by: misrefuted known-positive cases; uncovered known-negative
    cases; number of requested checks; template bytes; stable names. Unknown is
    not a refutation, and unlabelled interpretations are not negative examples.
    This is training selection, not a guarantee about future source semantics.
    """
    names=[t['name'] for t in tests]
    by_case={c['id']:c for c in cases}
    if len(by_case)!=len(cases):raise ValueError('Repeated case')
    rows={}
    for r in observations:
        key=(r['case'],r['test'])
        if key in rows:raise ValueError('Repeated measured pair')
        if r['case'] not in by_case or r['test'] not in names:raise ValueError('Unbound measured pair')
        if r['verdict'] not in ('supported','refuted','unknown','inapplicable'):raise ValueError('Unknown outcome')
        if type(r['exclude_candidate']) is not bool:raise ValueError('Explicit learned outcome mapping required')
        if r['verdict'] in ('unknown','inapplicable') and r['exclude_candidate']:
            raise ValueError('Unknown/inapplicable cannot exclude')
        rows[key]=r
    expected={(c['id'],n) for c in cases for n in names}
    if set(rows)!=expected:raise ValueError('Need measured outcome or explicit inapplicability for every pair')
    if any(c['status'] not in ('supported','rejected') for c in cases):raise ValueError('Do not label unresolved equivalence')
    costs={t['name']:len(t['question_template'].encode()) for t in tests}
    scored=[]
    for k in range(len(names)+1):
        for selected in combinations(names,k):
            rejected={c['id'] for c in cases if any(rows[(c['id'],n)]['exclude_candidate'] for n in selected)}
            false=sum(c['status']=='supported' and c['id'] in rejected for c in cases)
            missed=sum(c['status']=='rejected' and c['id'] not in rejected for c in cases)
            queries=sum(rows[(c['id'],n)]['verdict']!='inapplicable' for c in cases for n in selected)
            objective=(false,missed,queries,sum(costs[n] for n in selected),tuple(sorted(selected)))
            scored.append((objective,selected,sorted(rejected)))
    objective,selected,rejected=min(scored)
    return {'selected_tests':list(selected),'rejected_training_cases':rejected,
        'objective':list(objective),'evaluated_subsets':len(scored),
        'objective_order':['false_refutation','uncovered_negative','requested_checks','template_bytes','stable_names'],
        'uncertain_aliases_not_negatives':True,'future_semantics_certified':False}


def messages(operations,queries,units,focus):
    """Literal source is shared once per batch, including explicit focus IDs."""
    used={i for q in queries for i in q['unit_ids']}
    by_id={u['id']:u for u in units}
    payload={'source_units':[{'id':u['id'],'text':u['text']} for u in units if u['id'] in used],
        'checks':[{'query':q,'focus_unit_id':focus[q['id']],
                   'focus_unit':{'id':focus[q['id']],'text':by_id[focus[q['id']]]['text']},
                   'definition':next(o for o in operations if o['name']==q['operation'])} for q in queries]}
    return [{'role':'system','content':
        'Execute the acquired source-interpretation checks. Focus identifies the assertion being interpreted; other units are context, not additional effects attributable to focus. '
        'Judge each acquired PROBE PROPOSITION, which may differ from the candidate interpretation. Return supported/refuted, or unknown. '
        'Unknown/missing context is not false. For every definite judgment select actual supporting current unit IDs within that query window. '
        'These are fallible source judgments, not formal certificates. Follow the response schema exactly.'},
        {'role':'user','content':json.dumps(payload,ensure_ascii=False)}]
