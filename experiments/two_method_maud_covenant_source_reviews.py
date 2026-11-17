"""Explicit source-only reviews of all remaining32 MAUD covenant excerpts.

Every supplied view was read separately. Recipes bind exact original units;
knowledge-view facts,other-view definitions,native labels and F results never
fill a missing covenant,exception,consent requirement or prohibited-act list.
"""
from collections import Counter
from pathlib import Path
import json

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import ROOT,BASE,read,sha
from experiments.two_method_cni_short_source_reviews import ClauseGraph
from experiments.two_method_cni_long_source_reviews import prepare as previous_reviews
from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


LOCK_PATH=ROOT/'experiments/source_review_locks/maud_covenants32_20261117.json'

# Units and lexical anchors were selected after reading each complete view.
# Sub modes distinguish causing a subsidiary act/omission from not permitting
# it. They never assert that an unnamed subsidiary is itself a contract party.
BASES={
 '7e2add3c':{'v1':(1,'ordinary','Company','conduct','cause'),'v2':(0,'negative','Company','will not','not_permit')},
 'cef0e433':{'v1':(1,'ordinary','Company','conduct','cause'),'v2':(0,'negative','Company','shall not','not_permit')},
 '294850b3':{'v1':(2,'ordinary','Company','conduct','cause'),'v2':(0,'negative','Company','shall not','not_permit')},
 'a3142f07':{'v1':(1,'ordinary','Company','carry on','cause'),'v2':(0,'negative','Company','shall not','not_permit')},
 '9f3b4889':{'v1':(1,'ordinary','Company','conduct','cause'),'v2':(0,'negative','Company','shall not','not_permit')},
 'aaf70b03':{'v1':(0,'ordinary','Company','conduct','cause'),'v2':(0,'negative','Company','will not','cause_not')},
 'e4081ab8':{'v1':(1,'ordinary','Company','conduct','cause'),'v2':(1,'negative','Company','shall not','not_permit')},
 '04bc1032':{'v1':(0,'ordinary','Company','conduct','cause'),'v2':(0,'negative','Company','shall not','not_permit')},
 'bed0af63':{'v1':(2,'ordinary','Company','conduct','cause'),'v2':(0,'negative','Company','shall not','not_permit')},
 '5a36bd3b':{'v1':(0,'ordinary','Acquired Companies','conduct',None),'v2':(2,'negative','Acquired Companies','shall not',None)},
 'b3fc96b4':{'v1':(0,'ordinary','SB','operate','cause'),'v2':(1,'negative','SB','will not','not_permit')},
 '195081ce':{'v1':(1,'ordinary','Company','conduct','cause'),'v2':(0,'negative','Company','shall not','cause_not')},
 'b1a2f5ad':{'v1':(3,'ordinary','BancShares','conduct','cause'),'v2':(1,'negative','BancShares','neither BancShares nor CIT shall','not_permit')},
 'b8241f8f':{'v1':(0,'ordinary','Company','conduct','cause'),'v2':(0,'negative','Company','shall not','cause_not')},
 '447ae333':{'v1':(0,'ordinary','Company','conduct','cause'),'v2':(0,'negative','Company','shall not','not_permit')},
 'ef95fbbc':{'v1':(2,'ordinary','Company','conduct','cause'),'v2':(1,'negative','Company','will not','cause_not')},
}

# General exceptions are explicit per-view recipes;no template supplies a
# missing Law exception,written/prior qualifier,Disclosure Schedule or approver.
# Each tuple is(identity,literal quote,unit,concept).
EXCEPTIONS={
 '7e2add3c':{
  'v1':[('agreement','except as contemplated or permitted by this Agreement',1,'unspecified'),('law','required by applicable Laws or any Governmental Authority',1,'unspecified'),('consent','with the prior written approval of Parent or Merger Sub',1,'written_consent')],
  'v2':[('agreement','as otherwise expressly contemplated or permitted by this Agreement',0,'unspecified'),('consent','with the prior written approval of Parent or Merger Sub',0,'written_consent'),('law','as required by applicable Law or any Governmental Authority',0,'unspecified'),('disclosure_schedule','as set forth in Section 5.1 of the Disclosure Schedule',0,'unspecified')]},
 'cef0e433':{
  'v1':[('disclosure_schedule','as expressly set forth in Section 5.01 of the Company Disclosure Letter',1,'unspecified'),('agreement','as expressly contemplated or required by any other provision of this Agreement',1,'unspecified'),('law','as required by applicable Law (including any COVID-19 Measures)',1,'unspecified'),('consent','unless Parent otherwise agrees in writing',1,'written_consent')],
  'v2':[('disclosure_schedule','as expressly set forth in Section 5.01 of the Company Disclosure Letter',0,'unspecified'),('agreement','as expressly contemplated or required by this Agreement',0,'unspecified'),('law','as required by applicable Law (including any COVID-19 Measures)',0,'unspecified'),('consent','without the prior written consent of Parent',0,'written_consent')]},
 '294850b3':{
  'v1':[],
  'v2':[('consent','with Parent’s prior written consent',0,'written_consent'),('disclosure_schedule','as set forth in Section 5.1 of the Company Disclosure Schedule',0,'unspecified'),('agreement','as expressly permitted or expressly required by this Agreement',0,'unspecified')]},
 'a3142f07':{v:[('consent','with the prior written consent of Parent',u,'written_consent'),('law','as required by applicable Law',u,'unspecified'),('agreement','as expressly contemplated by this Agreement',u,'unspecified'),('disclosure_schedule','as otherwise set forth in Section 5.1 of the Company Disclosure Schedule',u,'unspecified')] for v,u in [('v1',1),('v2',0)]},
 '9f3b4889':{
  'v1':[('agreement','except as expressly permitted or required by this Agreement',1,'unspecified'),('law','as required by applicable Law',1,'unspecified'),('consent','with the prior written consent of Parent',1,'written_consent')],
  'v2':[('agreement','except as otherwise expressly permitted or required by this Agreement',0,'unspecified'),('law','as required by applicable Law',0,'unspecified'),('disclosure_schedule','as set forth on Section 6.01 of the Company Disclosure Letter',0,'unspecified'),('consent','without the prior written consent of Parent',0,'written_consent')]},
 'aaf70b03':{v:[('previously_disclosed','Except as Previously Disclosed',0,'unspecified'),('agreement','as expressly contemplated by or permitted by this Agreement',0,'unspecified'),('law','as required by applicable Legal Requirement',0,'unspecified'),('consent','with the prior written consent of Nicolet',0,'written_consent')] for v in ['v1','v2']},
 'e4081ab8':{v:[('disclosure_schedule','except as set forth in Section 6.1 of the Company Disclosure Schedule',1,'unspecified'),('agreement','as any other provision of this Agreement expressly contemplates or expressly requires',1,'unspecified'),('law_SEC_NYSE','as required by applicable Law, or rules and regulations of the SEC or NYSE',1,'unspecified'),('Migration','for any action taken by the Company to the extent necessary, desirable or appropriate in order to effect the Migration',1,'unspecified'),('consent','to the extent Parent has consented in writing thereto',1,'written_consent')] for v in ['v1','v2']},
 '04bc1032':{
  'v1':[('agreement','as expressly contemplated by or required pursuant to this Agreement',0,'unspecified'),('law','as may be required by applicable Law',0,'unspecified'),('consent','as consented to in writing by Parent',0,'written_consent')],
  'v2':[('agreement','as expressly contemplated by or required pursuant to this Agreement',0,'unspecified'),('law','as required by applicable Law',0,'unspecified'),('consent','as consented to in writing by Parent',0,'written_consent')]},
 'bed0af63':{v:[('consent','with the prior written consent of Parent',u,'written_consent'),('agreement','as expressly contemplated by this Agreement',u,'unspecified'),('disclosure_schedule','as set forth in Section 6.01 of the Company Disclosure Schedule',u,'unspecified'),('law','as required by Applicable Law or any COVID-19 Measures',u,'unspecified')] for v,u in [('v1',2),('v2',0)]},
 '5a36bd3b':{
  'v1':[('agreement_law','as required or expressly contemplated under this Agreement or as required by applicable Laws',0,'unspecified'),('consent','with the written consent of Parent',0,'written_consent'),('disclosure_schedule','as set forth in Section 6.2 of the Company Disclosure Schedule',0,'unspecified')],
  'v2':[('agreement_law','as required or expressly contemplated under this Agreement or as required by applicable Laws',1,'unspecified'),('consent','with the written consent',1,'written_consent'),('disclosure_schedule','as set forth in Section 6.2 of the Company Disclosure Schedule',2,'unspecified')]},
 'b3fc96b4':{
  'v1':[('consent','unless the prior written Consent of Buyer shall have been obtained',0,'written_consent'),('agreement','except as otherwise expressly contemplated herein',0,'unspecified')],
  'v2':[('consent','unless the prior written Consent of Buyer shall have been obtained',1,'written_consent'),('agreement','except as otherwise contemplated herein',1,'unspecified')]},
 '195081ce':{
  'v1':[('consent','as Parent shall otherwise approve in writing',1,'written_consent'),('agreement','as otherwise expressly contemplated or required by this Agreement',1,'unspecified'),('law','as required by applicable Law',1,'unspecified'),('disclosure_schedule','as set forth in Section 7.1(a) of the Company Disclosure Letter',1,'unspecified')],
  'v2':[('agreement','as otherwise expressly contemplated or required by this Agreement',0,'unspecified'),('law','as required by applicable Law',0,'unspecified'),('consent','as approved in writing by Parent',0,'written_consent'),('disclosure_schedule','as set forth in Section 7.1(a) of the Company Disclosure Letter',0,'unspecified')]},
 'b1a2f5ad':{
  'v1':[('agreement_and_schedules','except as expressly contemplated or permitted by this Agreement (including as set forth in the CIT Disclosure Schedule or the BancShares Disclosure Schedule)',1,'unspecified'),('law','required by law (including the Pandemic Measures)',3,'unspecified'),('consent','as consented to in writing by the other party',3,'written_consent')],
  'v2':[('disclosure_schedules','except as set forth in the BancShares Disclosure Schedule or the CIT Disclosure Schedule',1,'unspecified'),('agreement','as expressly contemplated or permitted by this Agreement',1,'unspecified'),('law','as required by law (including the Pandemic Measures)',1,'unspecified'),('consent','without the prior written consent of the other party to this Agreement',1,'written_consent')]},
 'b8241f8f':{
  'v1':[('required_agreement_law','as required hereby or by applicable Law (including any COVID-19 Measure)',0,'unspecified'),('disclosure_schedule','as disclosed in Section 5.1(a) of the Company Disclosure Schedule',0,'unspecified'),('consent','as consented to in writing by Parent',0,'written_consent')],
  'v2':[('required_agreement_law','as required hereby or by applicable Law (including any COVID-19 Measure)',0,'unspecified'),('disclosure_schedule','as disclosed in Section 5.1(b) of the Company Disclosure Schedule',0,'unspecified'),('consent','as consented to in writing by Parent',0,'written_consent')]},
 '447ae333':{
  'v1':[('disclosure_schedule','as set forth on Schedule 6.1(a) of the Company Disclosure Letter',0,'unspecified'),('agreement_exchange','as expressly permitted or required by this Agreement or the Exchange Agreement',0,'unspecified'),('law','as may be required by applicable Law, (including any COVID-19 Measures)',0,'unspecified'),('consent','otherwise consented to by Parent in writing',0,'written_consent')],
  'v2':[('disclosure_schedule','as set forth on the corresponding subsection of Schedule 6.1(b) of the Company Disclosure Letter',0,'unspecified'),('agreement_exchange','as expressly permitted or required by this Agreement or the Exchange Agreement',0,'unspecified'),('law','as may be required by applicable Law',0,'unspecified'),('consent','otherwise consented to by Parent in writing',0,'written_consent')]},
 'ef95fbbc':{
  'v1':[('agreement','as expressly required by this Agreement',2,'unspecified'),('disclosure_schedule','as set forth in Section 5.1 of the Company Disclosure Letter',2,'unspecified'),('section52_prohibition','as expressly prohibited by Section 5.2',2,'unspecified'),('law','as required by applicable Law',2,'unspecified'),('consent','as approved in writing in advance by Parent',2,'written_consent')],
  'v2':[('disclosure_schedule','as set forth in the correspondingly numbered subsection of Section 5.2 of the Company Disclosure Letter',1,'unspecified'),('consent','as approved by Parent',1,'unspecified'),('law','as required by applicable Law',1,'unspecified'),('agreement','as expressly contemplated by the terms of this Agreement',1,'unspecified')]},
}


MAIN_EFFORTS={
 'cef0e433':('use commercially reasonable efforts',),
 '04bc1032':('use its commercially reasonable efforts',),
 '5a36bd3b':('use commercially reasonable efforts',),
 'b8241f8f':('use commercially reasonable efforts to conduct its business',),
 '447ae333':('use reasonable best efforts',),
}
AUXILIARY={
 'a3142f07':[('preserve_organization','preserve'),('maintain_relations','maintain')],
 '9f3b4889':[('preserve_organization','preserve'),('keep_services','keep available'),('preserve_relations','preserve')],
 'e4081ab8':[('preserve_organization','preserve'),('maintain_permits','maintain in effect'),('maintain_relationships','maintain satisfactory relationships')],
 '04bc1032':[('maintain_organization_relationships','maintain in all material respects'),('maintain_assets','maintain its material assets')],
 'bed0af63':[('preserve_organization','preserve'),('maintain_relations','maintain existing relationships'),('keep_services','keep available')],
 '5a36bd3b':[('preserve_organization','preserve')],
 'b8241f8f':[('additional_efforts_object_omitted','use commercially reasonable efforts')],
 '447ae333':[('preserve_organization_goodwill_assets','preserve'),('keep_services','keep available'),('preserve_relations','preserve')],
}


def build_base(g,key,view):
    unit,kind,actor_name,verb,submode=BASES[key][view]
    if key=='b1a2f5ad':
        group_name='each of BancShares and CIT' if view=='v1' else 'neither BancShares nor CIT'
        g.n('company','group','unspecified',unit,name=group_name)
        for identity,name in [('BancShares','BancShares'),('CIT','CIT')]:
            g.n(identity,'organization','unspecified',unit,name=name);g.r('member_of',identity,'company',unit)
    else:g.n('company','group' if actor_name=='Acquired Companies' else 'organization','unspecified',unit,name=actor_name)
    subtype='ordinary_course_covenant' if kind=='ordinary' else 'negative_interim_covenant'
    g.effect('main','obligation' if kind=='ordinary' else 'prohibition',unit,'company',subtype,verb)
    targets=['main'];aux=[]
    if submode:
        literal=next(t for t in ('Company Subsidiaries','Company Subsidiary','Subsidiaries') if t in g.text(unit))
        g.n('subsidiaries','group','unspecified',unit,name=literal)
        g.n('subsidiary_activity','event',subtype,unit)
        g.r('actor','subsidiary_activity','subsidiaries',unit)
        mode='prohibition' if submode=='not_permit' else 'obligation'
        g.effect('subsidiary_control',mode,unit,'company','unspecified','permit' if submode=='not_permit' else 'cause')
        g.r('object','subsidiary_control_action','subsidiary_activity',unit)
        if submode=='cause_not':g.qualify('caused_omission',unit,['subsidiary_control'])
        targets.append('subsidiary_control')
    if kind=='ordinary':
        for identity,name in AUXILIARY.get(key,[]):
            g.effect(identity,'obligation',unit,'company','unspecified',name);targets.append(identity);aux.append(identity)
        effort_targets=['main']+(['subsidiary_control'] if submode else [])
        for phrase in MAIN_EFFORTS.get(key,[]):g.qualify('main_effort_standard',unit,effort_targets,quote=phrase)
        if key=='04bc1032':
            g.effect('REIT_qualification','obligation',unit,'company','unspecified','maintain its qualification for taxation as a REIT')
            targets.append('REIT_qualification')
        if aux:g.qualify('auxiliary_standards_and_limits',unit,aux)
    temporal_unit=None if (key in ('294850b3','bed0af63') and view=='v2') else unit
    if (key,view)==('5a36bd3b','v2'):temporal_unit=1
    if (key,view)==('b1a2f5ad','v1'):temporal_unit=1
    if temporal_unit is not None:g.qualify('temporal_window',temporal_unit,targets)
    # Per-clause text retains materiality,past practice and conditional effort
    # standards. No obligation is rewritten into a guarantee of performance.
    g.qualify('source_operation_scope',unit,targets)
    for identity,quote,evidence_unit,concept in EXCEPTIONS[key][view]:
        g.n(identity,'exception',concept,evidence_unit,quote=quote)
        for effect in targets:g.r('exception_for',identity,effect,evidence_unit,quote=quote)
    if key=='04bc1032':
        # Zero-width typography in the source reference is preserved by using
        # its actual original unit;the referenced letter itself is not loaded.
        g.n('disclosure_letter','exception','unspecified',unit)
        for effect in targets:g.r('exception_for','disclosure_letter',effect,unit)
    if key=='5a36bd3b' and view=='v2':
        g.n('consenting_Parent','organization','unspecified',2,name='Parent')
        g.r('object','consent','consenting_Parent',2)
    if key=='b1a2f5ad':
        g.qualify('opposite_party_consent',unit,['consent'])
    elif key=='b3fc96b4':
        g.n('consenting_Buyer','organization','unspecified',unit,name='Buyer');g.r('object','consent','consenting_Buyer',unit)
    elif key=='aaf70b03':
        g.n('consenting_Nicolet','organization','unspecified',unit,name='Nicolet');g.r('object','consent','consenting_Nicolet',unit)
    elif key not in ('294850b3',) or view=='v2':
        if not (key=='5a36bd3b' and view=='v2'):
            g.n('consenting_Parent','organization','unspecified',unit,name='Parent');g.r('object','consent','consenting_Parent',unit)
    if key=='7e2add3c':
        g.n('consenting_MergerSub','organization','unspecified',unit,name='Merger Sub')
        g.qualify('Parent_or_MergerSub_alternative',unit,['consent']);g.r('object','consent','consenting_MergerSub',unit)
    # Qualification on reasonableness is not expanded to clauses outside its
    # source scope (e.g.294850 v2 and195081 v2 enumerate narrower carveouts).
    if any(identity=='consent' for identity,*_ in EXCEPTIONS[key][view]):g.qualify('consent_qualification_as_written',unit,['consent'])
    return unit,kind,targets,aux


def covid_exception(g,identity,unit,quote,targets,*,concept='covid_19',qualification=None):
    g.n(identity,'exception',concept,unit,quote=quote)
    for target in targets:g.r('exception_for',identity,target,unit,quote=quote)
    if qualification:g.qualify(identity+'_eligibility',unit,[identity],quote=qualification)


def source_specific(g,key,view,unit,kind,targets,aux):
    notes=[]
    if key=='cef0e433':
        covid_exception(g,'COVID_required_law',unit,'COVID-19 Measures',targets,
            qualification='as required by applicable Law (including any COVID-19 Measures)')
    elif key=='294850b3' and view=='v2':
        covid_exception(g,'COVID_government_compliance',0,'COVID-19 pandemic',targets)
        g.qualify('required_law_order_directive',0,['COVID_government_compliance'])
        g.effect('terminate_deviations','obligation',0,'company','unspecified','shall be terminated')
        g.effect('resume_ordinary_conduct','obligation',0,'company','unspecified','shall be resumed')
        g.qualify('compliance_no_longer_required',0,['terminate_deviations','resume_ordinary_conduct'],quote='as soon as reasonably practicable after compliance with such Law, Order or directive is no longer required')
        notes.append('COVID government-compliance relief has a cease-deviation/resume-conduct condition;the resumption duty is not a new general ordinary-course covenant in this view.')
    elif key=='9f3b4889' and view=='v1':
        covid_exception(g,'COVID_conduct_response',1,'COVID-19 or COVID-19 Measures',['main','subsidiary_control'],
            qualification='except for any actions taken reasonably and in good faith in response to COVID-19 or COVID-19 Measures')
        g.qualify('aux_consistent_with_conduct',1,aux,quote='to the extent consistent therewith')
        notes.append('The COVID parenthetical modifies conduct;it is not flattened into an unrestricted exception to every preservation/relationship effort.')
    elif key=='04bc1032':
        covid_exception(g,'section51_COVID_response',1,'COVID-19 or any COVID-19 Measures',targets)
        g.qualify('section51_notwithstanding_scope',1,['section51_COVID_response'])
        g.qualify('commercial_reasonableness_good_faith_actions_or_omissions',1,['section51_COVID_response'])
        notes.append('Each current view itself supplies Section6.8;its actions/omissions relief spans Section5.1,not an inferred exception copied from another view or an external tax-law waiver.')
    elif key=='bed0af63':
        covid_exception(g,'COVID_required_measures',unit,'COVID-19 Measures',targets,
            qualification='as required by Applicable Law or any COVID-19 Measures')
    elif key=='5a36bd3b':
        covid_unit=0 if view=='v1' else 1
        covid_exception(g,'COVID_compliance_actions_omissions',covid_unit,'COVID-19 Measures',targets)
        g.qualify('reasonable_taken_omitted_required_compliance',covid_unit,['COVID_compliance_actions_omissions'])
        if view=='v1':g.qualify('section62b_specific_provisions_govern',0,targets)
        else:notes.append('Written consent and Parent lie in separate source units;no cross-unit quote or missing Part(a) definition is reconstructed.')
    elif key=='195081ce':
        if view=='v1':
            covid_exception(g,'COVID_reasonably_required_measures',1,'for commercially reasonable actions as reasonably required to comply with or implement COVID-19 Measures',targets)
            g.qualify('commercially_reasonable_required_actions',1,['COVID_reasonably_required_measures'])
            g.qualify('ordinary_definition_including_deviations',1,['main'])
        else:
            g.n('specified_negative_clauses','group','unspecified',0,quote='clauses (xii) (Material Contracts) (other than with respect to the Contracts described in the proviso thereto) or (xvii) (Compensation)')
            g.r('object','main','specified_negative_clauses',0)
            covid_exception(g,'COVID_scoped_negative_relief',0,'COVID-19 Measures',['specified_negative_clauses'])
            g.qualify('scoped_commercially_reasonable_required_actions',0,['COVID_scoped_negative_relief'])
            g.qualify('consent_specific_iii_iv_sole_discretion',0,['consent'])
            notes.append('COVID relief targets specified(xii)/(xvii) prohibitions with an excluded Contracts proviso,not the entire negative covenant;Parent sole-discretion clauses(iii)/(iv) are a different scope.')
    elif key=='b1a2f5ad':
        covid_exception(g,'Pandemic_required_law',unit,'Pandemic Measures',targets,concept='pandemic')
        g.qualify('as_required_by_law',unit,['Pandemic_required_law'])
        notes.append('The source says Pandemic Measures;its unprovided definition is not silently changed to a COVID-only measure or an unconditional pandemic permission.')
    elif key=='b8241f8f':
        covid_exception(g,'COVID_required_hereby_or_law',0,'COVID-19 Measure',targets,
            qualification='as required hereby or by applicable Law (including any COVID-19 Measure)')
        if view=='v1':
            g.qualify('ordinary_definition_excludes_contract_law_tort',0,['main'])
            g.qualify('additional_efforts_consistency',0,aux,quote='to the extent consistent therewith')
            notes.append('The additional effort object is omitted,and the ordinary-course definition excludes contract breach,law violation and tort;neither is filled from a similar contract.')
    elif key=='447ae333' and view=='v1':
        covid_exception(g,'COVID_required_law',0,'as may be required by applicable Law, (including any COVID-19 Measures)',targets,
            qualification='as may be required by applicable Law, (including any COVID-19 Measures)')
        g.qualify('ordinary_definition_excluding_deviations_literal',0,['main'])
        notes.append('The definition literally says excluding COVID deviations;it is not rewritten as including or an extra affirmative permission. The independently stated Law exception is preserved.')
    if key=='a3142f07' and view=='v1':g.qualify('ordinary_definition_past_practice',1,['main'])
    if key=='aaf70b03' and view=='v1':g.qualify('ordinary_definition_own_practice_and_industry',1,['main'])
    if key=='bed0af63' and view=='v1':g.qualify('ordinary_past_practice_definition',0,['main'])
    if key=='ef95fbbc' and view=='v1':g.qualify('ordinary_past_practice_definition',0,['main'])
    if key=='e4081ab8' and view=='v2':g.qualify('section61b_not_automatic61a_breach',1,['main'])
    if key=='04bc1032' and view=='v1':g.qualify('section51b_subject_matter_breach_qualification',0,['main'])
    if key=='b3fc96b4' and view=='v2':g.qualify('do_agree_commit_and_subsidiaries',1,targets)
    if key in ('294850b3','bed0af63') and view=='v2':notes.append('This view supplies no interim date window;foregoing text is not imported from v1.')
    if key in ('9f3b4889','447ae333') and view=='v2':notes.append('This negative excerpt supplies no COVID wording;v1 COVID and ordinary definitions are not copied into it or negated into a whole-contract absence.')
    if key=='ef95fbbc' and view=='v2':notes.append('Parent approval is not expressly written or prior in this negative view;the v1 writing/in-advance requirement is not imported.')
    if key=='b1a2f5ad':notes.append('BancShares/CIT and their respective subsidiary sets remain reciprocal;opposite-party consent is not self-consent or an invented Parent approval.')
    return notes


def reviewed_graph(source,view,units):
    locks={(r['source'],r['view']):r for r in read(LOCK_PATH)}
    if (source,view) not in locks or digest(units)!=locks[source,view]['units_sha256']:
        raise ValueError('Only32 exact separately read source/view units are covered by these covenant reviews')
    key=source.split(':')[1][:8];g=ClauseGraph(units)
    unit,kind,targets,aux=build_base(g,key,view)
    notes=source_specific(g,key,view,unit,kind,targets,aux)
    unknown=[
        'Only this supplied excerpt is covered;full Agreement,Disclosure Letter/Schedule,defined-law/measure contents and actual party identities/dates/consents are not supplied.',
        'No current compliance,discretionary consent,government requirement or COVID response is asserted to have occurred;alternative exceptions,causation,effort/materiality and temporal conditions are not fully Boolean-formalized.',
        'Company obligation to cause subsidiary conduct/omission or not permit subsidiary acts is not an assertion that each unnamed subsidiary independently signed this Agreement.',
    ]
    if kind=='negative':unknown.append('The prohibited-activity list following the introductory colon is not supplied;no concrete restricted transaction or complete absence of other exceptions is invented.')
    if '<omitted>' in ' '.join(u['text'] for u in units):unknown.append('The source explicitly omits text;omitted acts,definitions,paragraphs and attachments remain unknown.')
    if key=='7e2add3c' and view=='v1':unknown.append('The excerpt ends in and;the unprovided additional affirmative undertaking is not filled.')
    if key=='aaf70b03' and view=='v1':unknown.append('Ordinary course requires both own past practice AND similar nature/magnitude to same-line peers;it is not simplified to past practice alone.')
    if key=='e4081ab8':unknown.append('Migration and SEC/NYSE exceptions are not pandemic exceptions;the source does not supply the Migration definition.')
    return g.finish(complete=False,unknown=unknown+notes)


def prepare():
    locks=read(LOCK_PATH)
    if (len(locks)!=32 or len({(r['source'],r['view']) for r in locks})!=32 or len({r['source'] for r in locks})!=16
            or Counter(r['role'] for r in locks)!=Counter(development=12,calibration=12,reference_only=8)):
        raise ValueError('Keep all32 exact views of the original16 mothers and their roles')
    _,previous=previous_reviews();checkpoint=read(BASE/'handoff/current_checkpoint.json')
    roles={r['source']:r for r in read(ROOT/checkpoint['formal_source_reference_registry']['artifact_root']/'roles.json')}
    public_path=ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json';public={s['key']:s for s in read(public_path)}
    builders=[Path(__file__),LOCK_PATH,ROOT/'experiments/two_method_annotate.py',ROOT/'experiments/two_method_cni_short_source_reviews.py',
        ROOT/'experiments/two_method_cni_long_source_reviews.py',ROOT/'legal_skill_guard/paired_interfaces/graph_interface.py',
        ROOT/'legal_skill_guard/skill_evolution/objects.py']
    protocol={'experiment':'remaining32_MAUD_covenant_whole_view_root_reviews_v1',
        'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in builders},'original_TRAIN_public_sha256':sha(public_path),
        'locked_original_roles_and_views':locks,'prior68_explicit_manifest_sha256':digest(previous),
        'all32_supplied_source_views_individually_read':True,'cross_view_completion_or_native_question_label_used':False,
        'source_mothers_not_view_count_is_independent_sample_unit':True,
        'native_target_questions_labels_weak_outputs_or_program_results_used':False,
        'explicit_root_review_not_automatic_semantic_certification':True,
        'interactive_root_annotation_cost_usd':None,'new_experimental_endpoint_requests':0}
    out=BASE/'MAUD_covenant_source_reviews_v1'/digest(protocol);immutable_json(out/'protocol.json',protocol)
    rows=list(previous['reviews'])
    for lock in locks:
        source,view=lock['source'],lock['view'];role=roles[source]
        if (role['role'],role['batch'])!=(lock['role'],lock['batch']) or role['role']=='structure_evaluation':raise ValueError('Original source role/batch changed')
        task,mapping=inputs(public[source]);units=next(v['source_units'] for v in task['views'] if v['view_id']==view)
        graph=reviewed_graph(source,view,units)
        card={'source':source,'view_id':view,'role':role['role'],'source_units_sha256':lock['units_sha256'],
            'native_views':sorted(k for k,v in mapping.items() if v==view),'graph':graph,
            'reference_ready':True,'source_semantic_truth_verified':True,
            'native_answers_used_to_create_or_repair_graph':False,'complete_native_case_gold_claimed':False,
            'reviewer':'root assistant explicit separately read source-view review;not independent human annotation',
            'verification_scope':'Every asserted local actor,covenant,exception target and condition against this entire supplied view only;unprovided acts,definitions and Boolean/legal scope stay unknown.',
            'source_span_checks':gi.validate(graph,units),'review':{'entire_supplied_view_read':True,'source_sha_locked':True,
                'no_knowledge_or_other_view_facts_imported':True,'blanket_pandemic_permission_or_missing_prohibited_act_not_invented':True,
                'consent_effort_actor_temporal_and_exception_subset_scope_preserved':True,
                'no_native_labels_reference_parameters_or_F_output_used_to_edit_graph':True},'new_model_requests':0}
        path=out/'cards'/digest([source,view])/'source_review.json';immutable_json(path,card)
        rows.append({'source':source,'view':view,'kind':'literal_semantic_graph','path':str(path.relative_to(ROOT)),'sha256':sha(path)})
    if len(rows)!=100 or len({(r['source'],r['view']) for r in rows})!=100:raise ValueError('Retain prior68 and all new32 views exactly once')
    manifest={'reviews':rows,'new_root_reviewed_views':32,'new_reviewed_mothers':16,'previous_extra_reviews_retained':68,
        'interactive_root_annotation_cost_usd':None,'unmetered_interactive_annotation_not_counted_as_free':True,
        'independent_human_or_complete_legal_gold_claimed':False,'new_model_requests':0}
    immutable_json(out/'manifest.json',manifest)
    for builder in builders:
        target=out/'source_snapshot'/builder.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and target.read_bytes()!=builder.read_bytes():raise ValueError('A frozen source builder changed')
        if not target.exists():target.write_bytes(builder.read_bytes())
    return out,manifest


if __name__=='__main__':
    out,manifest=prepare()
    print(json.dumps({'artifact_root':str(out.relative_to(ROOT)),'new_reviewed_views':32,'new_reviewed_mothers':16,
        'cumulative_explicit_review_views':len(manifest['reviews']),'new_model_requests':0,'complete_goal_claimed':False},ensure_ascii=False))
