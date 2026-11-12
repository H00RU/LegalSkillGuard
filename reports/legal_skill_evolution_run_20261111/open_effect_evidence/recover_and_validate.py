"""Explicit terminal-request recovery; original acquisition source is unchanged.

One control response omitted a container declaration already defined by its own
source function and examples. The other request timed out without any output.
No host-created legal norm or native-label repair is permitted here.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_open_effect_acquisition as study
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.scoped_grammar import constructors,term_sort
from legal_skill_guard.skill_evolution.span_compiler import occurrences


ORIGINAL=study.materialize


def metadata_only(base,proposal,materials):
    if proposal['architecture']!='compiler':return ORIGINAL(base,proposal,materials)
    schema=constructors({'constructors':base['grammar']['constructors']+proposal['new_constructors']})
    unknown=set()
    def heads(t):
        if isinstance(t,list):
            if t[0] not in schema:unknown.add(t[0])
            for a in t[1:]:heads(a)
    for s in proposal['source_examples']:heads(json.loads(s['term_json']))
    if not unknown:return ORIGINAL(base,proposal,materials)
    if unknown!={'information_union'}:raise ValueError('Unresolved declaration is not the observed container defect: '+str(unknown))
    definitions=[f for f in proposal['source_functions']
                 if f.startswith('def disposition_scope(') and "['information_union',base,['copies_of',base]]" in f]
    if len(definitions)!=1 or 'information-and-copy scope' not in proposal['rationale']:
        raise ValueError('Missing acquired definition; do not invent a container meaning')
    constraints=[]
    def infer(t,expected=None):
        if isinstance(t,str):return term_sort(t,schema)
        if t[0] in schema:
            c=schema[t[0]]
            if len(t)!=len(c['arguments'])+1:raise ValueError('Arity mismatch is not metadata-only recovery')
            for child,wanted in zip(t[1:],c['arguments']):
                if infer(child,wanted)!=wanted:raise ValueError('Conflicting inferred type')
            return c['sort']
        if expected is None:raise ValueError('Container result type is not determined')
        args=tuple(infer(child) for child in t[1:]);constraints.append((expected,args))
        return expected
    for s in proposal['source_examples']:infer(json.loads(s['term_json']))
    if not constraints or set(constraints)!={('Information',('Information','Information'))}:
        raise ValueError('The omitted signature is not unambiguous')
    value=deepcopy(proposal)
    decl={'name':'information_union','sort':'Information','arguments':['Information','Information'],
          'meaning':'The acquired information-and-copy scope is defined by this unchanged source function: '+definitions[0]}
    value['new_constructors'].append(decl)
    assert all(value[k]==proposal[k] for k in ('source_functions','decision_functions','source_examples','direct_program'))
    folder=ROOT/'artifacts'/study.RUN
    immutable_json(folder/'IndependentOpen/metadata_recovery.json',{
        'raw_proposal_digest':digest(proposal),'inferred_signature_constraints':constraints,
        'acquired_definition':definitions[0],'added_declaration':decl,
        'source_terms_and_G_P_unchanged':True,'native_labels_used':False,
        'new_legal_rules_created_by_host':False,'source_semantics_review_pending':True})
    immutable_json(folder/'IndependentOpen/adapted_proposal.json',value)
    return ORIGINAL(base,value,materials)


def retry(root):
    folder,p,ledger,public=study.setup(root)
    assert (folder/'teachers_settled.json').exists()
    assert not (folder/'SourceEffect/teacher.json').exists()
    old=study.read(folder/'SourceEffect/teacher_input.json')
    system=old['system']+'''\nRecovery request: the earlier request timed out before returning any proposal. Return a compact executable delta. Keep unchanged helper functions inherited rather than reproducing their bodies. Two representative new source examples suffice; the source program should still handle all supplied training material. Every constructor used by the new code or examples must have an explicit signature/meaning, including information containers. Preserve unknowns and legal scope. The source evidence, labels and model profile are unchanged.'''
    request={'system':system,'user':old['user'],'logical_schema':study.PROPOSAL,'wire_schema':study.WIRE,
             'change':'Compact delta and2 representative examples, explicit declaration consistency; no new domain facts, data or model configuration.'}
    immutable_json(folder/'SourceEffect/compact_retry_input.json',request)
    identity=study.RUN+':compact_source_effect_retry:'+digest(request)
    result=FrozenTeacher(ledger,folder,p['teacher_profile']).propose(identity,source_ids=p['teacher_sources'],
        system_prompt=system,user_prompt=old['user'],output_schema=study.WIRE)
    immutable_json(folder/'SourceEffect/teacher.json',result)


def policy_bank(root,folder,public):
    bank={}
    for path in sorted((folder/'development/SourceEffect').glob('ContractNLI_*.json')):
        row=study.read(path);source=public[row['source']]
        spans=study.source_spans(study.material_public(source['views'][0]['public']))
        if row['interpretation'] is None:continue
        for n in row['interpretation']['nodes']:
            a=min(spans[i]['start'] for i in n['support_ids']);b=max(spans[i]['end'] for i in n['support_ids'])
            quote=source['views'][0]['public']['source_text'][a:b]
            entry={'quote':quote,'term':n['term'],'sort':n['sort']}
            bank[digest(entry)]=entry
    immutable_json(folder/'shared_rule_bank.json',{'entries':list(bank.values()),
        'all_actual_acquired_development_roots_included':True,
        'not_an_independent_acquisition':True,'no_native_answers_cached':True,
        'source_truth_not_automatically_certified':True})
    def literal_parse(grammar,text):
        nodes=[]
        for e in bank.values():
            for a,b in occurrences(text,e['quote']):
                if not any(n['start']==a and n['end']==b and n['term']==e['term'] for n in nodes):
                    nodes.append({'id':len(nodes),'start':a,'end':b,'sort':e['sort'],
                                  'term':e['term'],'ambiguous':False})
        return nodes
    return literal_parse


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['preflight','retry','evaluate']);args=parser.parse_args()
    ROOT=Path(__file__).resolve().parents[3]
    folder,p,ledger,public=study.setup(ROOT)
    manifest={'base_protocol_sha256':hashlib.sha256((folder/'protocol.json').read_bytes()).hexdigest(),
        'base_bound_source_unchanged':p['source_snapshot'],
        'recovery_source':str(Path(__file__).relative_to(ROOT)),
        'recovery_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'old_failed_request_preserved':True,'no_model_or_sampling_change':True,
        'metadata_recovery_no_term_G_P_or_legal_rule_change':True,
        'cache_uses_all_actual_development_rule_roots_not_just_two_examples':True,
        'no_reuse_labels_in_repair':True,'goal_complete':False}
    immutable_json(folder/'recovery_execution_manifest.json',manifest)
    study.materialize=metadata_only
    if args.stage=='preflight':
        b,g=study.compiled(folder,p,public,'IndependentOpen')
        print('Independent control compiles after the recorded type-only declaration recovery; G/P/examples unchanged.')
    elif args.stage=='retry':retry(ROOT)
    else:
        study.evaluate(ROOT)
        study.evaluate(ROOT,reuse=True)
        study.parse=policy_bank(ROOT,folder,public)
        study.evaluate(ROOT,cache=True)
        study.evaluate(ROOT,reuse=True,cache=True)
