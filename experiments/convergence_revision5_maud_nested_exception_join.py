"""Reconcile saved MAUD reads under two explicit scopes for the same question."""

import base64
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import sqlite3
from zipfile import ZipFile

from experiments.convergence_formal_train_fit import EXTERNAL_ARM, ORDINARY as COMMON, pointer
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_maud_parent_definition_coverage import (
    ARCHIVE, ARM, BOOTSTRAP, NEGATIVE, PANDEMIC, TrainingJournal, load_roster, unpage,
)
from legal_skill_guard.paired_interfaces.shared_semantics import (
    ExplanationState, SourceCase, Theory, allowed_relation, matches_assertions,
)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE/'revision5_MAUD_nested_exception_join_20261119'
MAUD_PAPER = 'https://aclanthology.org/2023.emnlp-main.1019.pdf'
MAUD_RELEASE = 'https://zenodo.org/records/7500064'
LAW = 'MAUD:negative-interim-pandemic:two-scope-hypotheses'
CASES = {
    6: ('loan_modification', 'modifications of such loans consistent with regulatory COVID-relief guidelines',
        'shall not be a violation of this Section 5.2(b)', 1),
    8: ('temporary_facility_closure', 'except for such temporary closures',
        'ongoing efforts to contain the outbreak', 2),
}


def source_view(source):
    view,=(v for v in source['views'] if v['id']==NEGATIVE)
    return view['public']


def audited_case(source, batch, parent_bytes):
    """Confirm the relevant settings in the excerpt and the exact parent."""
    kind,lead,tail,count=CASES[batch]
    assert source['project_split']=='train'
    assert sha256(parent_bytes).hexdigest()==source['fulltext_raw_sha256']
    full=unpage(parent_bytes.decode('utf-8-sig'))
    public=source_view(source)
    excerpt=unpage(public['source_text'])
    for text in (full,excerpt):
        assert text.count(lead)==1
        start=text.index(lead)
        following=text.find(tail,start)
        assert start<following<start+900
    assert len(list(PANDEMIC.finditer(excerpt)))==count
    if batch==8:
        assert 'in-person access in light of COVID-19 concerns' in excerpt
        assert excerpt.index('in-person access in light of COVID-19 concerns')>excerpt.index(tail)
    case=SourceCase(source['key']+':'+kind,source['key'],LAW,public,
                    {'item_relief':True,'rule_introduced_at_covenant_level':False,
                     'express_exception_wording':batch==8})
    receipt={'kind':kind,'source_public_sha256':digest(public),
             'parent_content_sha256':source['fulltext_raw_sha256'],
             'pandemic_cues_in_excerpt':count,'access_cue_is_separate':batch==8,
             'scope':'enumerated_item_only',
             'relief_form':'express_exception' if batch==8 else 'clarifies_non_violation'}
    return case,receipt


def answer(values, law):
    mode=law['item_relief_policy']
    count_item=mode=='all' or mode=='express_only' and values['express_exception_wording']
    applies=values['rule_introduced_at_covenant_level'] or count_item and values['item_relief']
    return 'Yes' if applies else 'No'


def physical(db,source,result):
    key=source['key']
    if 'schema_reads' in result:
        trace,=result['schema_reads']
        version=trace['proposal_sha256']
        native=trace['native']
        matches=lambda raw: digest(raw['content'])==trace['response_sha256']
    else:
        readout,=result['reads']
        trace,=readout['execution']['traces']
        version=readout['execution']['program_sha256']
        native=readout['native']
        matches=lambda raw: raw['content']==trace['raw_content']
    assert native==result['native']
    identity=trace['physical_call_id']
    row=db.execute('select status,role,source,purpose,request_hash,result from calls where id=?',
                   (identity,)).fetchone()
    assert row[:4]==('completed','executor',key,'skill_actor')
    actual=json.loads(row[5])
    assert matches(actual) and actual['request_hash']==row[4] and not actual['thinking_requested']
    folder=Path(actual['artifact_directory'])
    assert folder.is_relative_to(ROOT/'artifacts')
    request=read(folder/'request.json')
    wire=read(folder/'wire_request.json')
    raw=base64.b64decode(wire['body_b64'])
    payload=request['payload']
    assert sha256(raw).hexdigest()==wire['body_sha256'] and json.loads(raw)==payload
    assert request['source']==key and request['id']==identity and request['request_hash']==row[4]
    assert read(folder/'result.json')==actual
    assert payload['chat_template_kwargs']['enable_thinking'] is False and payload['model']=='Qwen/Qwen3-8B'
    contract=digest({**{k:v for k,v in payload.items() if k!='messages'},
                         'system':[m['content'] for m in payload['messages'] if m['role']=='system']})
    observed=result['native'][NEGATIVE]['answer']
    assert observed in ('Yes','No')
    return identity,version,contract,observed


def show_join(theory, cases, verified):
    values=[r[3] for r in verified]
    identities=[r[0] for r in verified]
    assert len(set(identities))==2
    versions={r[1] for r in verified}
    contracts={r[2] for r in verified}
    assert len(versions)==len(contracts)==1
    measured=dict(zip(identities,zip(cases,values,strict=True),strict=True))
    state=ExplanationState(theory,versions.pop())
    for c,identity,value in zip(cases,identities,values,strict=True):
        state.observe([c],[value],physical_call_ids=[identity],evidence_kind='actual_model',
                      physical_verifier=lambda key,case,value: measured.get(key)==(case,value))
    rows=state.snapshot()['observations']
    assert all(r['locally_allowed'] and r['physical_model_evidence_verified'] for r in rows)
    assert rows[0]['cumulative_shared_explanation_exists'] and not rows[1]['cumulative_shared_explanation_exists']
    return {'archived_responses':values,'binding_of_the_same_program_verified':True,
            'same_reader_contract_verified':True,'matched_physical_responses':2,
            'locally_admissible':True,'cumulative_assignment_exists':False,
            'direct_equality_accepts':values[0]==values[1]}


def run():
    boot=ROOT/read(BOOTSTRAP)['artifact_root']
    study=read(boot/'binding.json')
    roster=load_roster(study)
    journal=TrainingJournal(boot,study,roster)
    sources=[tuple(s for s in roster[b-1] if s['dataset']=='MAUD')[1] for b in CASES]
    valid_archive=read(BASE/'postfreeze_M2_MAUD_source_scope_20261119'/'terminal.json')['parent_reference_audit']
    assert sha(ARCHIVE)==valid_archive['official_archive_sha256']
    cases,receipts=[],[]
    with ZipFile(ARCHIVE) as z:
        for batch,source in zip(CASES,sources,strict=True):
            c,r=audited_case(source,batch,z.read('data/contracts/'+source['parent_id']+'.txt'))
            cases.append(c)
            receipts.append(r)
    assert len({c.root_id for c in cases})==2
    assert source_view(sources[0])['question']==source_view(sources[1])['question']
    provenance=tuple({'kind':'independent_source_audit','evidence_sha256':digest(r)} for r in receipts)
    roots={case.root_id:[{}] for case in cases}
    policy_options=[{'item_relief_policy':'none'},{'item_relief_policy':'all'}]
    theory=Theory({LAW:policy_options},roots,answer,sha(Path(__file__)),provenance=provenance)
    shared=allowed_relation(theory,cases)
    independent=allowed_relation(theory,cases,mode='independent_completions')
    assert len(shared['signatures'])==2 and len(independent['signatures'])==4
    for x,y in product(('No','Yes',None),repeat=2):
        passes=any(matches_assertions([x,y], sig) for sig in shared['signatures'].values())
        assert passes==(x is None or y is None or x==y)
    extended=Theory({LAW:[*policy_options,{'item_relief_policy':'express_only'}]},roots,answer,
                    sha(Path(__file__)),provenance=provenance)
    widened=allowed_relation(extended,cases)
    assert len(widened['signatures'])==3

    six,eight=sources
    stage=ROOT/read(pointer(6))['artifact_root']
    bound=read(stage/'binding.json')
    terminal=read(stage/'terminal.json')
    d=read(stage/'matched_decisions.json')
    assert digest(bound)==stage.name and digest(d)==terminal['matched_decisions_sha256'] and not terminal['TEST_opened']
    assert all(sha(stage/'source_snapshot'/f)==value for f,value in bound['source_sha256'].items())
    forward_stage=ROOT/read(observe_pointer(8))['artifact_root']
    forward_binding=read(forward_stage/'binding.json')
    forward_terminal=read(forward_stage/'terminal.json')
    assert digest(forward_binding)==forward_stage.name and not forward_terminal['TEST_opened']
    assert all(sha(forward_stage/'source_snapshot'/f)==value for f,value in forward_binding['source_sha256'].items())
    rows={}
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        db.execute('begin')
        ledger=dict(db.execute('select status,count(*) from calls group by status'))
        assert not ledger.get('reserved')
        for arm in (COMMON,EXTERNAL_ARM):
            decision=d['teacher'][arm]['MAUD']
            assert decision['selected']=='candidate' and decision['native_utility_delta']>0
            archived=read(stage/'candidates'/arm/'MAUD'/'measurements.json')
            assert digest(archived['predictions'])==decision['predictions_sha256']
            forward=journal._observations(arm,8)
            record=read(journal.directory(arm,8)/'predictions'/(digest(eight['key'])+'.json'))
            assert digest(record)==forward['predictions'][eight['key']]
            verified=[physical(db,six,archived['predictions'][six['key']]),
                      physical(db,eight,record['result'])]
            key='ordinary_teacher' if arm==ARM else 'PARSE_style'
            rows[key]={**show_join(theory,cases,verified),
                       'chronology':'B6 candidate read followed by B8 entering-library read',
                       'B6_original_native_batch_gain':decision['native_utility_delta']}
            rows[key]['wording_sensitive_shared_assignment_exists']=any(
                matches_assertions(rows[key]['archived_responses'],sig) for sig in widened['signatures'].values())
            assert rows[key]['wording_sensitive_shared_assignment_exists']
    observed=read(ROOT/bound['observations_root']/'binding.json')
    grade_path=ROOT/observed['native_grade_paths']['MAUD']
    assert sha(grade_path)==observed['native_grade_sha256'][str(grade_path.relative_to(ROOT))]
    grades=read(grade_path)
    actual_labels=[grades[s['key']][NEGATIVE]['answer'] for s in sources]
    assert actual_labels==['No','No']
    t={'scope_hypotheses':['any item-specific relief counts','relief must be introduced at covenant level'],
       'official_annotation_policy_established':False,
       'official_materials_consulted':{'publication':MAUD_PAPER, 'versioned_release':MAUD_RELEASE},
       'source_reviewed_TRAIN_cases':receipts,'source_native_labels_for_audit_only':actual_labels,
       'shared_legal_facts_across_different_contracts':False,
       'shared_variable':'candidate definition of the same benchmark question',
       'reader_results':rows,'distinct_physical_responses_verified':4,
       'supports_shared':list(shared['signatures'].values()),'supports_independent':list(independent['signatures'].values()),
       'same_information_equality_equivalent_on_9_output_states':True,
       'wording_sensitive_extension':{'policy':'count express item exceptions, omit item-level non-violation clarifications',
                                     'source_forms_verified':True,'policy_officially_supported':False,
                                     'extended_shared_support':list(widened['signatures'].values()),
                                     'both_archived_pairs_restored':True},
       'B6_archived_execution_sources_verified':len(bound['source_sha256']),
       'B8_archived_observation_sources_verified':len(forward_binding['source_sha256']),
       'new_native_selection_or_result_claimed':False,
       'new_model_requests':0,'TRAIN_only':True,'ledger_count':sum(ledger.values()),
       'bound_runner_sha256':sha(Path(__file__))}
    immutable_json(HOME/'audited_terminal.json',t)
    print(json.dumps({k:v for k,v in t.items() if k!='source_reviewed_TRAIN_cases'},sort_keys=True),flush=True)


if __name__=='__main__':
    run()
