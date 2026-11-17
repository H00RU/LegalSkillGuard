"""Source-realizable quantity/entity groups for the new shared-semantics M2.

The official Diversity rules make this K a singleton law interpretation with
explicit case facts. Its relations test nonlinear aggregation and entity
binding but cannot establish an advantage of shared over single interpretation.
The module says this explicitly; it never manufactures legal uncertainty.
"""
import hashlib
import inspect
import re
from textwrap import dedent

from legal_skill_guard.paired_interfaces.diversity import audit_source,reference_outputs,TASK_RULES
from legal_skill_guard.paired_interfaces.shared_semantics import SourceCase,Theory,DerivedField,source_variant,allowed_relation
from legal_skill_guard.skill_evolution.objects import digest

LAW_SCOPE='LegalBench_Diversity:official_rules:'+hashlib.sha256(TASK_RULES.encode()).hexdigest()


def reference(values,law):
    record={'citizenship':values['citizenship'],'claims':values['claims']}
    return reference_outputs(record)


def derive_citizenship(values,law):
    return {party:values[field] for party,field in values['citizen_bindings'].items()}


def derive_claims(values,law):
    return [{'plaintiff':row['plaintiff'],'defendant':row['defendant'],
        'amount':values[row['amount_field']]} for row in values['claim_bindings']]


def build(source):
    """Independent source/parser audit; never an inference shortcut."""
    if source['dataset']!='LegalBench_Diversity' or source.get('project_split',source.get('split'))!='train':
        raise ValueError('Derivative supervision is restricted to the locked TRAIN family')
    public=source['views'][0]['public'];text=public['source_text'];record=audit_source(text)
    # Explicit source literals are primitive edits. Derived claim totals and
    # cross-role equality are recomputed from the edited text at reference time.
    primitives={};spans={};renderers={};amount_names={};citizen_bindings={}
    for i,match in enumerate(re.finditer(r'\$([\d,]+)',text)):
        name='amount_'+str(i);primitives[name]=int(match[1].replace(',',''))
        spans[name]=('source_text',match.start(),match.end())
        amount_names[match.start()]=name
        original=match.group()
        renderers[name]=(lambda value,comma=',' in original:'$'+(format(value,',d') if comma else str(value)))
    for i,match in enumerate(re.finditer(r'\b(\w+) is from ([^.]+)\.',text)):
        name='citizenship_'+str(i);primitives[name]=match[2];citizen_bindings[match[1]]=name
        spans[name]=('source_text',match.start(2),match.end(2));renderers[name]=str
    claim_bindings=[]
    for sentence in re.finditer(r'[^.]+(?:\.|$)',text):
        raw=sentence.group()
        if ' sue' not in raw:continue
        match=re.match(r'\s*(.+?) (?:both sue|sues|sue) (.+?)(?: each)? for ',raw)
        if not match:raise ValueError('Unsupported independently audited claim syntax')
        for amount in re.finditer(r'\$[\d,]+',raw):
            for plaintiff in match[1].split(' and '):
                for defendant in match[2].split(' and '):
                    claim_bindings.append({'plaintiff':plaintiff,'defendant':defendant,
                        'amount_field':amount_names[sentence.start()+amount.start()]})
    primitives.update({'citizen_bindings':citizen_bindings,'claim_bindings':claim_bindings})
    code='\n'.join(dedent(inspect.getsource(fn)) for fn in (reference,derive_citizenship,derive_claims))
    theory=Theory({LAW_SCOPE:[{'task_rules_sha256':hashlib.sha256(TASK_RULES.encode()).hexdigest()}]},
        {source['key']:[{}]},reference,hashlib.sha256(code.encode()).hexdigest(),
        provenance=({'kind':'official_task_assumption','evidence_sha256':hashlib.sha256(TASK_RULES.encode()).hexdigest()},
                    {'kind':'explicit_source','evidence_sha256':hashlib.sha256(text.encode()).hexdigest()}),
        derived=(DerivedField('citizenship',tuple(['citizen_bindings',*citizen_bindings.values()]),derive_citizenship),
                 DerivedField('claims',tuple(['claim_bindings',*amount_names.values()]),derive_claims)),
        allowed_edits=frozenset(spans))
    case=SourceCase(source['key'],source['key'],LAW_SCOPE,{'source_text':text},primitives,spans)
    return case,theory,renderers


def group_relation(source,changes):
    case,theory,renderers=build(source)
    variants=[case];receipts=[]
    for change in changes:
        if any(name.startswith('amount_') and (type(v) is not int or v<0) for name,v in change.items()):
            raise ValueError('A monetary intervention must be a nonnegative integer literal')
        result=source_variant(case,theory,change,renderers)
        if result['status']!='REALIZABLE':return result
        variants.append(result['case']);receipts.append(result['receipt'])
    # Independent source reparse checks the declared dependency closure. The
    # allowed relation itself still executes Theory.complete and its DAG.
    for variant in variants:
        parsed=audit_source(variant.public['source_text'])
        complete=theory.complete(variant,theory.law_alternatives[LAW_SCOPE][0],{})
        normalized=lambda rows:sorted((r['plaintiff'],r['defendant'],r['amount']) for r in rows)
        if complete['citizenship']!=parsed['citizenship'] or normalized(complete['claims'])!=normalized(parsed['claims']):
            raise ValueError('A source edit disagrees with recomputed semantic dependencies')
    relation=allowed_relation(theory,variants)
    control=allowed_relation(theory,variants,mode='single_interpretation')
    return {'status':'REALIZABLE','cases':variants,'theory':theory,'edit_receipts':receipts,'relation':relation,
        'singleton_semantics':True,'shared_vs_single_signatures_identical':relation['signatures']==control['signatures'],
        'establishes_M2_shared_interpretation_advantage':False,
        'independent_native_positive_supervision_still_required':True}
