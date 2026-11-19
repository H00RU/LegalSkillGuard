"""Test finite pairwise closure of saved M2 relations and a two-asset TRAIN edit."""

from collections import Counter
from dataclasses import replace
from itertools import combinations, product
from pathlib import Path
import sqlite3

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_train_fit import OE, pointer
from experiments.convergence_m2_signature_audit import _batches, _pilots
from experiments.convergence_oe_natural_relation import OLD_TRAIN, REGISTRY
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from legal_skill_guard.paired_interfaces.convergence_ev_inventory import public_inventory
from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.paired_interfaces.shared_semantics import (
    SourceCase, Theory, allowed_relation, canonical, matches_assertions, source_variant,
)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE/'revision5_M2_pairwise_scope_20261119'


def closure(signatures):
    """Join all width-two projections, keeping singleton domains fixed."""
    exact = {tuple(map(canonical,row)) for row in signatures}
    width = len(next(iter(exact)))
    domains = [sorted({s[i] for s in exact}) for i in range(width)]
    pairs = {(i,j):{(row[i],row[j]) for row in exact} for i,j in combinations(range(width),2)}
    reconstructed = {row for row in product(*domains) if all((row[i],row[j]) in values
                                                              for (i,j),values in pairs.items())}
    if not exact<=reconstructed:
        raise ValueError('A pairwise projection cannot discard a valid joint witness')
    return exact,reconstructed


def projection_compatibility(allowed,actual):
    width=len(actual)
    pairs=list(combinations(range(width),2)) if width>1 else [(0,)]
    return all(any(matches_assertions([actual[i] for i in subset],[r[i] for i in subset])
                   for r in allowed) for subset in pairs)


def previous_validations():
    for name,stage,row in (*_pilots(),*_batches(8)):
        yield name,stage,row
        if 'conditioned_projection' in row:
            for role,item in row['conditioned_projection']['evidence'].items():
                yield name+':conditioned:'+role,stage,item['validation']
    k='B8_OE_typed_component_current.json'
    stage=ROOT/read(HANDOFF/k)['artifact_root']
    t=read(stage/'terminal.json')
    assert t['status']=='completed_B8_OE_typed_component_diagnostic' and not t['TEST_opened']
    for role,item in t['details'].items():
        yield 'B8_typed:'+role,stage,item['validation']
    k='revision5_OE_disclosure_current.json'
    stage=ROOT/read(HANDOFF/k)['artifact_root']
    t=read(stage/'terminal.json')
    assert t['status']=='completed_revision5_OE_disclosure_TRAIN' and not t['TEST_opened']
    yield 'B8_disclosure:literal',stage,t['literal']
    for role,item in t['results'].items():
        yield 'B8_disclosure:'+role,stage,item['validation']
    k='revision5_OE_joint_native_gate_current.json'
    stage=ROOT/read(HANDOFF/k)['artifact_root']
    t=read(stage/'terminal.json')
    assert t['status']=='completed_revision5_OE_joint_native_gate_TRAIN' and t['TRAIN_only']
    yield 'B7_joint_native:literal',stage,t['literal_recheck']


def archived_evidence(db,train):
    rows=[]
    ids=set()
    groups_per_validation=Counter()
    for name,stage,data in previous_validations():
        state=data['explanation_state']
        obs=state['observations']
        groups_per_validation[len(obs)]+=1
        for observation in obs:
            actual=observation['actual_signature']
            allowed=observation['allowed_signatures']
            calls=observation['physical_call_ids']
            if (observation['evidence_kind']!='actual_model' or not observation['physical_model_evidence_verified']
                    or len(calls)!=len(actual) or len(actual)!=len(observation['root_ids'])):
                raise ValueError('Use settled, source-bound model observations')
            for identity,root in zip(calls,observation['root_ids'],strict=True):
                expected=('completed','executor',root,'skill_actor')
                real=db.execute('select status,role,source,purpose from calls where id=?',(identity,)).fetchone()
                if root not in train or real!=expected:
                    raise ValueError('The relation must stay bound to a physical TRAIN request')
                ids.add(identity)
            exact,joined=closure(allowed)
            pair_accept=projection_compatibility(allowed,actual)
            full_accept=any(matches_assertions(actual,r) for r in allowed)
            if full_accept!=observation['locally_allowed']:
                raise ValueError('The archived local decision must reproduce')
            rows.append({'condition':name,'queries':len(actual),'distinct_shared_signatures':len(exact),
                         'extra_pairwise_signatures':len(joined-exact),'pairwise_accepts':pair_accept,
                         'shared_accepts':full_accept,
                         'positive_native_gain':data['native_utility_sum_delta']>0,
                         'stage_terminal_sha256':sha(stage/'terminal.json')})
    return rows,len(ids),dict(groups_per_validation)


def two_asset_material():
    fit=ROOT/read(pointer(7))['artifact_root']
    form=read(fit/'binding.json')
    study=read(ROOT/form['checkpoint_root']/'binding.json')
    batches=load_roster(study)
    train={s['key'] for b in batches for s in b}
    candidates={s['key']:s for s in batches[6] if s['dataset']==OE}
    registry=read(REGISTRY)
    old={r['key']:r for r in read(OLD_TRAIN) if r['key'] in candidates}
    found=[]
    for row in registry['reviews']:
        key=row['source']
        if key not in candidates or row['view']!='v0' or row['kind']!='asset_program_ports':
            continue
        path=ROOT/row['path']
        card=read(path)
        if (sha(path)!=row['sha256'] or card['source_semantic_truth_verified'] is not True
                or card['native_answers_used'] or card.get('native_answers_used_to_create_or_repair_graph') is not False):
            continue
        source=candidates[key]
        if source['views']!=old[key]['views'] or digest(old[key])!=registry['source_public_sha256'][key]:
            raise ValueError('The two untreated title coordinates require exactly audited facts')
        text, = (v['public']['original_input'] for v in source['views'] if v['id']=='EC')
        by_name={r['description']:r for r in public_inventory(text).values()}
        assets=[]
        for asset in card['port_record']['assets']:
            ownership=asset.get('ownership_evidence',{})
            label=asset['fields']['asset_descriptions']['value']
            value=asset['fields']['asset_values']
            if ownership.get('status')!='unknown' or label not in by_name or value['status']!='stated':
                continue
            anchored=by_name[label]
            quote=anchored['source_quote']
            token=anchored['amount_quote']
            if (quote!=ownership['quote'] or text.count(quote)!=1 or quote.count(token)!=1
                    or text.count(label)!=1 or int(token.removeprefix('$').replace(',','').removesuffix('.00'))!=value['value']):
                raise ValueError('The source-only card must bind a unique asset and editable amount occurrence')
            start=text.index(quote)+quote.index(token)
            assets.append((label, value['value'], (start,start+len(token)),token))
        if len(assets)==2:
            found.append((source,text,row['sha256'],assets))
    (source,text,card_sha,assets),=found
    t=read(fit/'terminal.json')
    recorded=read(fit/'matched_decisions.json')
    assert digest(recorded)==t['matched_decisions_sha256'] and not t['TEST_opened'] and fit.name==digest(form)
    value_pair,=(r for r in recorded['relation'][OE]['native_comparisons'] if r['source']==source['key'])
    assert value_pair['patch_utility']>value_pair['baseline_utility']
    return train,source,text,card_sha,assets,value_pair


def forwarded(values, law):
    return sum(values['amount'+str(i)] for i in values['selected_assets'] if values['title'+str(i)])


def two_asset_witness(source,text,card_sha,assets):
    key=source['key']
    large,small=sorted(assets,key=lambda row:-row[1])
    names=[large[0],small[0]]
    a,b=large[1],small[1]
    assert type(a) is int and type(b) is int and a>b>0
    venue=supplied_jurisdiction_scope(text)
    scope=venue['premise']
    theory=Theory({scope:[{'projection':'title-conditioned valuation'}]},
                  {key:[{'title0':v,'title1':w} for v,w in product((False,True),repeat=2)]},
                  forwarded,sha(Path(__file__)),
                  provenance=({'kind':'independent_source_audit','evidence_sha256':card_sha,
                               'interpretation':'Each quoted asset has an explicit valuation and unresolved title. '
                                                'Separate per-asset title completions are a controlled local proxy.'},),
                  allowed_edits=frozenset({'amount1'}))
    root=SourceCase(key,key,scope,{'text':text,'assets':names},{'amount0':a,'amount1':b},
                    spans={'amount1':('text',*small[2])})
    money = (lambda value:f'${value:,}.00') if ',' in small[3] else (lambda value:f'${value}.00')
    patch=source_variant(root,theory,{'amount1':a},{'amount1':money})
    assert patch['status']=='REALIZABLE'
    start,end=small[2]
    assert patch['case'].public['text']==text[:start]+money(a)+text[end:]
    cases=[
        replace(root,source_id=key+':first',primitives={**root.primitives,'selected_assets':(0,)}),
        replace(root,source_id=key+':second',primitives={**root.primitives,'selected_assets':(1,)}),
        replace(patch['case'],primitives={**root.primitives,'selected_assets':(0,1)}),
    ]
    shared=list(allowed_relation(theory,cases)['signatures'].values())
    independent=list(allowed_relation(theory,cases,mode='independent_completions')['signatures'].values())
    exact,paired=closure(shared)
    support_test=[0,0,a]
    assert projection_compatibility(shared,support_test)
    assert not any(matches_assertions(support_test,values) for values in shared)
    # A control can derive the exact relation if it explicitly normalizes the edited amount.
    direct=[row for row in independent if row[2]==row[0]+(a if row[1]==b else 0)]
    assert {tuple(v) for v in direct}=={tuple(v) for v in shared}
    return {'source_only_title_card_sha256':card_sha,
            'literal_edit_sha256':digest(patch['receipt']), 'edited_source_bytes_outside_valuation_unchanged':True,
            'shared_signatures':len(exact),'independent_signatures':len(independent),
            'pairwise_closure_signatures':len(paired),'pairwise_only_signatures':len(paired-exact),
            'state_opportunity_verified_beyond_pairwise':True,
            'exact_direct_normalized_sum_matches_exhaustive_relation':True,
            'controlled_latent_title_projection':True,'native_EV_forwarded_amount_claimed':False,
            'actual_model_responses_for_the_new_three_query_group':0}


def main():
    train,source,text,card,assets,native=two_asset_material()
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        db.execute('begin')
        status=dict(db.execute('select status,count(*) from calls group by status'))
        assert not status.get('reserved')
        rows,calls,validation=archived_evidence(db,train)
    diag=two_asset_witness(source,text,card,assets)
    diag['original_B7_native_pair_delta_for_the_same_mother']=native['patch_utility']-native['baseline_utility']
    t={'archived_actual_projection_groups':len(rows),'distinct_physical_responses_verified':calls,
       'observed_groups_per_validation_count':validation,'archived_conditions':rows,
       'actual_groups_distinguished_from_pairwise_closure':sum(r['pairwise_accepts']!=r['shared_accepts'] for r in rows),
       'archived_relations_beyond_pairwise':sum(r['extra_pairwise_signatures']>0 for r in rows),
       'groups_with_native_positive_companion':sum(r['positive_native_gain'] for r in rows),
       'new_two_asset_source_witness':diag,'new_model_requests':0,'ledger_rows':sum(status.values()),
       'DEV_or_TEST_content_or_labels_used':False,'audit_source_sha256':sha(Path(__file__))}
    immutable_json(HOME/'terminal.json',t)
    print({k:v for k,v in t.items() if k!='archived_conditions'},flush=True)


if __name__=='__main__':
    main()
