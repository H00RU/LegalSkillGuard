"""TRAIN-only empirical B learning inside the current complete source program.

References construct authorized source-local fact edits and score candidates.
They never construct candidate graphs, fill missing rules or reach prediction.
"""
from copy import deepcopy
from dataclasses import asdict
from fractions import Fraction
from itertools import combinations
import re
import sqlite3
from jsonschema import ValidationError

from .coverage import Unsupported,digest
from .interfaces import Observation,refine
from .learning import parameterize_graph
from .source_bindings import decode_source_bindings
from .source_execution import exact_native
from .source_interfaces import connector_cases,replace_connector
from .source_program import accept_observations,compile_source,source_theory
from .source_structure import inspect_source
from .typed_learning import primitive_io,public_variant,typed_metadata
from .source_learning import (OracleUnavailable,candidate_views,learn_source,original_view)


NUMERAL=re.compile(r'(?<![\w.])-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?!\w|\.\d)')


def rebind_source_program(source,variant,program,observation_rows,*,library=None):
    """Apply only the already-authorized public fact edit, with unique evidence.

    An ambiguous literal mapping or changed factual evidence is unavailable.
    There is no inferred truth, reconstructed legal rule or default native value.
    """
    before=inspect_source(source);after=inspect_source(variant)
    old={c.id:before.ledger.text[c.start:c.end] for c in before.ledger.clauses}
    new={c.id:after.ledger.text[c.start:c.end] for c in after.ledger.clauses}
    if set(old)!=set(new) or before.roles!=after.roles:
        raise Unsupported('Fact edit changed source unit structure or roles')
    result=deepcopy(program)
    for binding in result['bindings']:
        a='\n'.join(old[key] for key in binding['sources'])
        b='\n'.join(new[key] for key in binding['sources'])
        if a==b:continue
        left=[Fraction(m[0].replace(',','')) for m in NUMERAL.finditer(a)]
        right=[Fraction(m[0].replace(',','')) for m in NUMERAL.finditer(b)]
        def number(value,integer):
            if len(left)!=len(right):raise Unsupported('Numeric edit has no positional literal correspondence')
            original=Fraction(str(value));mapped={y for x,y in zip(left,right) if x==original}
            if len(mapped)!=1:raise Unsupported('Primitive value has no unambiguous public rebind')
            target=next(iter(mapped))
            if integer and target.denominator!=1:raise Unsupported('Integer primitive cannot be rounded')
            return target.numerator if integer else str(target)
        kind=binding['type'];value=binding['value'];edit=variant.get('_entity_reassignment')
        if kind in {'integer','rational'}:binding['value']=number(value,kind=='integer')
        elif kind=='scalar' and type(value) is int:binding['value']=number(value,True)
        elif kind=='amount':value['value']=number(value['value'],True)
        elif kind=='amounts':
            for amount in value:amount['value']=number(amount['value'],True)
        elif kind=='allowance_bank':
            for state in value:state['balance']=number(state['balance'],True)
        elif kind=='relation' and edit:
            value['rows']=[[edit['new'] if cell==edit['old'] else cell for cell in row] for row in value['rows']]
        elif kind=='scalar' and edit and value==edit['old']:binding['value']=edit['new']
        # Remaining unchanged metadata still has to pass the actual public
        # decoder. No guessed key/ownership/witness extractor is supplied.
    decode_source_bindings(result['bindings'],new)
    variant=deepcopy(variant);variant['content_hash']=digest(variant['public'])
    compiled=compile_source(variant,result,library=library)
    names=[row['name'] for row in observation_rows]
    observed=accept_observations(compiled,names,{'observations':observation_rows}) if names else {}
    return compiled,observed


def _execute_case(compiled,observed,case,library):
    try:
        program=replace_connector(compiled['program'],case)
        candidate=compile_source(compiled['source'],program,library=library)
        execution=candidate['query'].execute(source_theory(candidate,observed).facts)
        return {'status':'executed','prediction':exact_native(execution['answer']),
            'target_node_executed':case['node'] in execution['executed_nodes'],
            'execution':exact_native(execution),'A_certificate_issued':False}
    except (ValueError,TypeError,KeyError,ValidationError) as exc:
        return {'status':'unavailable','prediction':None,'target_node_executed':False,
            'error_type':type(exc).__name__,'error':str(exc),'A_certificate_issued':False}


def learn_source_interfaces(source,grade,oracle,*,program=None,observation_rows=(),library=None):
    compiled=None;diagnostic=None
    if program is not None:
        try:compiled=compile_source(source,program,library=library)
        except (ValueError,TypeError,KeyError,ValidationError) as exc:diagnostic=str(exc)
    cases=connector_cases(compiled) if compiled else []
    if not cases and source['dataset']=='ProofWriter_OWA_depth5':
        trace={};result=learn_source(source,grade,oracle,trace=trace)
        if result.get('learned_pattern') and not result['learned_pattern']['graphs']:
            result['learned_pattern']=None
        return {**result,'candidate_checks':[],'source_program_candidate_count':0,
            'source_program_diagnostic':diagnostic,'candidate_trace':trace,
            'primitive_source':'predefined_public_Horn_grammar_not_new_rule_learning'}
    no_oracle=source['dataset']=='ContractNLI'
    base=original_view(source,grade);target=grade['targets'] if source['dataset']=='OpenExempt' else grade['answer']
    bound={};checks={case['case_hash']:[] for case in cases}
    def prepare(view):
        key=digest(view)
        if key not in bound:
            try:
                variant=public_variant(source,grade,view)
                translated,observed=rebind_source_program(source,variant,program,observation_rows,library=library)
                bound[key]={'compiled':translated,'observed':observed,
                    'coarse':primitive_io(translated['slots']),'metadata':typed_metadata(translated['slots'])}
            except (ValueError,TypeError,KeyError,ValidationError) as exc:bound[key]={'error':str(exc)}
        return bound[key]
    def predict(case,view,answer=None):
        item=prepare(view);key=digest(view)
        result=_execute_case(item['compiled'],item['observed'],case,library) if 'compiled' in item else {
            'status':'unavailable','prediction':None,'target_node_executed':False,'error':item['error'],'A_certificate_issued':False}
        if answer is not None:
            checks[case['case_hash']].append({**result,'view_hash':key,
                'matches_reference':result['status']=='executed' and digest(result['prediction'])==digest(answer)})
        return result
    item=prepare(base) if cases else {'error':diagnostic or 'No query-relevant connector in the proposed source program'}
    observations=[Observation(item['coarse'],item['metadata'],target,digest(base))] if 'compiled' in item else []
    initial=[predict(case,base,target) for case in cases]
    retained=[case for case,value in zip(cases,initial) if value['status']=='executed' and digest(value['prediction'])==digest(target)]
    cached=[] if no_oracle else oracle.cached_views()
    if no_oracle:charged=set()
    else:
        with sqlite3.connect('file:'+str(oracle.ledger.path)+'?mode=ro',uri=True) as db:
            charged={row[0] for row in db.execute('select view_hash from oracle_views where source=?',(source['key'],))}
    cached_keys={digest(v) for v in cached};missing_charged=charged-cached_keys
    new_left=max(0,4-len(charged))
    remaining=[] if no_oracle or not cases else [v for v in candidate_views(source,grade) if digest(v) not in charged]
    queried=[]
    for _ in range(4):
        if cached:view=cached.pop(0);fresh=False
        else:
            if new_left==0:break
            ranked=[]
            for view in remaining:
                candidate=prepare(view)
                if 'compiled' not in candidate or 'compiled' not in item:continue
                if digest(candidate['coarse'])!=digest(item['coarse']) or digest(candidate['metadata'])==digest(item['metadata']):continue
                predictions=[predict(case,view)['prediction'] for case in retained]
                disagreements=sum(digest(a)!=digest(b) for a,b in combinations(predictions,2))
                ranked.append((-disagreements,digest(view),view))
            if not ranked:break
            view=min(ranked,key=lambda row:row[:2])[2];fresh=True;new_left-=1
        key=digest(view);remaining=[v for v in remaining if digest(v)!=key]
        try:answer=oracle.query(view)
        except OracleUnavailable as exc:
            queried.append({'view':view,'view_hash':key,'answer':None,'status':'reference_failed',
                'error':str(exc),'view_slot_charged':True});continue
        queried.append({'view':view,'view_hash':key,'answer':answer,'reused_charged_view':not fresh})
        current=prepare(view)
        if 'compiled' in current:observations.append(Observation(current['coarse'],current['metadata'],answer,key))
        values={case['case_hash']:predict(case,view,answer) for case in cases}
        retained=[case for case in retained if values[case['case_hash']]['status']!='executed' or
                  digest(values[case['case_hash']]['prediction'])==digest(answer)]
    refinement=refine(observations) if observations else None
    complete=[case for case in retained if all(c['status']=='executed' and c['matches_reference'] for c in checks[case['case_hash']])
              and any(c['target_node_executed'] for c in checks[case['case_hash']])]
    pattern=None
    if refinement and refinement.status=='identified_on_observed_collisions' and complete and not missing_charged:
        graphs={digest(parameterize_graph(c['graph'])):parameterize_graph(c['graph']) for c in complete}
        pattern={'fields':list(refinement.minimal_field_sets[0]),'graphs':list(graphs.values()),
                 'basis':'observed_source_collisions','universal_semantic_equivalence_claim':False}
    status='no_counterfactual_oracle' if no_oracle else 'charged_view_record_missing' if missing_charged else \
        'typed_inputs_unavailable' if not cases else 'NO_VALID_CONNECTOR' if not retained else \
        'view_rebinding_unavailable' if not complete else refinement.status
    candidate_checks=[{**case,'checks':checks[case['case_hash']]} for case in cases]
    return {'status':status,'oracle_views':queried,'learned_pattern':pattern,
        'refinement':asdict(refinement) if refinement else None,'source_program_diagnostic':diagnostic,
        'candidate_checks':candidate_checks,'connector_candidates_generated':len(cases),
        'connector_candidates_retained':len(retained),'connector_candidates_fully_checked':len(complete),
        'missing_charged_view_records':sorted(missing_charged),
        'available_library_pattern_hashes':[p['pattern_hash'] for p in (library or {}).get('patterns',[])],
        'candidate_generator':'single_connector_interventions_in_full_source_program',
        'primitive_source':'model_source_linked_inputs','A_certificate_issued_by_B':False,
        'finite_candidate_pool_is_Omega':False}
