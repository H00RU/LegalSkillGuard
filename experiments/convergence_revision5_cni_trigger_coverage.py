"""Reconcile disposition triggers with the original source-only TRAIN graph cards."""

from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sqlite3

from experiments.convergence_oe_natural_relation import OLD_TRAIN, REGISTRY
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_cni_disposition_literal import positive_citations
from experiments.convergence_revision5_cni_disposition_scope import (
    ARM, BOOTSTRAP, DATASET, TASK, TrainingJournal, load_roster, materials, spans_for,
)
from legal_skill_guard.paired_interfaces.legal_consumers import index
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE/'revision5_CNI_trigger_coverage_20261119'
AGREEMENT_CLOSE = 'explicit_agreement_end'
RELATIONSHIP_CLOSE = 'explicit_covered_relationship_end'
DISTINCT_EVENT = 'other_project_or_purpose_event'
REQUEST_ONLY = 'request_only'
NO_DISPOSITION = 'no_relevant_disposition_identified'
# Evidence locations were checked against the same complete public contracts.
# A missing closing condition is a source reading. The native labels are
# loaded only after the inventory, card hashes, and original reads are bound.
REVIEW = {
    (1,0):(REQUEST_ONLY,(77,78,79)),
    (1,1):(RELATIONSHIP_CLOSE,(29,45,47)),
    (1,2):(REQUEST_ONLY,(43,44,45)),
    (2,0):(NO_DISPOSITION,()),
    (2,1):(AGREEMENT_CLOSE,(48,)),
    (2,2):(AGREEMENT_CLOSE,(31,37,38,39)),
    (3,0):(DISTINCT_EVENT,(21,22,23,61)),
    (3,1):(NO_DISPOSITION,()),
    (3,2):(NO_DISPOSITION,()),
    (4,0):(REQUEST_ONLY,(21,22,36)),
    (4,1):(NO_DISPOSITION,()),
    (4,2):(REQUEST_ONLY,(13,)),
    (5,0):(REQUEST_ONLY,(32,52)),
    (5,1):(AGREEMENT_CLOSE,(35,)),
    (5,2):(REQUEST_ONLY,(28,31)),
    (6,0):(DISTINCT_EVENT,(39,40,41,44,45)),
    (6,1):(DISTINCT_EVENT,(49,50,51,61,62,63)),
    (6,2):(AGREEMENT_CLOSE,(15,20,22)),
    (7,0):(REQUEST_ONLY,(20,)),
    (7,1):(AGREEMENT_CLOSE,(26,)),
    (7,2):(RELATIONSHIP_CLOSE,(29,31,34,35)),
    (8,0):(REQUEST_ONLY,(20,21)),
    (8,1):(REQUEST_ONLY,(87,90)),
    (8,2):(REQUEST_ONLY,(21,22,35,36)),
}
NEW_ENDPOINT_CUE = re.compile(r'\bupon\s+termination\s+of\s+service\b', re.I)
RETURN_TOKENS = re.compile(
    r'\b(?:return(?:s|ed)?|destro(?:y|ys|yed)|eras(?:e|ed)|deliver(?:s|ed)?)\b', re.I)
SPECIFIC_DISTINCT_CUES = {
    (3,0): ('not to proceed with', 'agreement and all obligations'),
    (6,0): ('relationship is not entered into', 'terminate the working relationship'),
    (6,1): ('completion of the purpose', 'continue in force for a period'),
}
REQUEST_CUE = re.compile(r'\b(?:request(?:s|ed)?|demand(?:s|ed)?)\b', re.I)
TERMINATION_TAGS = {'termination','termination_or_request'}


def graph_triggers(card):
    """Read only scoped obligation-to-trigger edges. Do not promote graph completeness."""
    graph=card['graph']
    nodes,_,tags=index(graph)
    return sorted({trigger for key,n in nodes.items()
                   if n['concept']=='obligation'
                   and tags(key,'actor')&{'receiving_party','either_party'}
                   and tags(key,'action')&{'return','destruction'}
                   for trigger in tags(key,'trigger')})


def review_contract(pos, view):
    category,spans=REVIEW[pos]
    quoted=spans_for(view)
    if any(not quoted[k].strip() for k in spans):
        raise ValueError('Every reviewed evidence coordinate must denote original text')
    coalesced=' '.join(' '.join(quoted[k].lower().split()) for k in spans)
    exact_rule=positive_citations(quoted)
    service_rule=[k for k,s in enumerate(quoted) if NEW_ENDPOINT_CUE.search(s) and RETURN_TOKENS.search(s)]
    if len(service_rule)>1 or (category==AGREEMENT_CLOSE and not exact_rule):
        raise ValueError('The explicit closing review lost its original words')
    if category==RELATIONSHIP_CLOSE and not (exact_rule or service_rule):
        raise ValueError('The role or relationship close needs its own disposition trigger')
    if category in (DISTINCT_EVENT,REQUEST_ONLY,NO_DISPOSITION) and (exact_rule or service_rule):
        raise ValueError('Reconcile another closing candidate before measuring the scope')
    if category==REQUEST_ONLY and not REQUEST_CUE.search(coalesced):
        raise ValueError('The request-only review must cite the source requirement')
    if category==DISTINCT_EVENT and not all(c in coalesced for c in SPECIFIC_DISTINCT_CUES[pos]):
        raise ValueError('The different operative event and agreement end must be independently worded')
    literal_indices=sorted(set.union(*exact_rule)) if exact_rule else service_rule
    if not set(literal_indices)<=set(spans):
        raise ValueError('The original reviewed spans must cover the literal proof')
    return category,list(spans),literal_indices,bool(exact_rule)


def run():
    boot=ROOT/read(BOOTSTRAP)['artifact_root']
    spec=read(boot/'binding.json')
    roster=load_roster(spec)
    journal=TrainingJournal(boot,spec,roster)
    registry=read(REGISTRY)
    snapshots={r['source']:r for r in registry['reviews'] if r['kind']=='literal_semantic_graph'
               and r['view']=='v0'}
    old={m['key']:m for m in read(OLD_TRAIN) if m['dataset']==DATASET}
    bound,_=materials()
    audits=[]
    with sqlite3.connect(LEDGER.as_uri()+'?mode=ro',uri=True) as db:
        db.execute('begin')
        settled=dict(db.execute('select status,count(*) from calls group by status'))
        assert not settled.get('reserved')
        for b,sources in enumerate(roster,1):
            receipt=journal._observations(ARM,b)
            for j,source in enumerate(x for x in sources if x['dataset']==DATASET):
                view,=(v for v in source['views'] if v['id']==TASK)
                key=source['key']
                category,span_ids,explicit,old_match=review_contract((b,j),view)
                case={'source':key,'source_sha256':digest(view['public']),'category':category,
                      'reviewed_native_span_ids':span_ids,'evidence_support_spans':explicit,
                      'old_literal_match':old_match,'graph_card':None}
                if key in snapshots:
                    prior=old[key]
                    assert digest(prior)==registry['source_public_sha256'][key]
                    old_view,=(v['public'] for v in prior['views'] if v['id']==TASK)
                    entry=snapshots[key]
                    path=ROOT/entry['path']
                    card=read(path)
                    assert view['public']==old_view and sha(path)==entry['sha256']
                    assert card['source_semantic_truth_verified'] is True and card['reference_ready'] is True
                    assert card['native_answers_used_to_create_or_repair_graph'] is False
                    case['graph_card']={'sha256':entry['sha256'],'triggers':graph_triggers(card),
                                        'scope_complete':card['graph']['scope_complete']}
                obs=read(journal.directory(ARM,b)/'predictions'/(digest(key)+'.json'))
                assert digest(obs)==receipt['predictions'][key] and source['project_split']=='train'
                trace,=obs['result']['reads'][0]['execution']['traces']
                physical=db.execute('select status,source,role,purpose,result from calls where id=?',
                                    (trace['physical_call_id'],)).fetchone()
                assert physical[:4]==('completed',key,'executor','skill_actor')
                record=json.loads(physical[4])
                assert record['content']==trace['raw_content']
                case['historical_answer']=obs['result']['native'][TASK]['answer']
                audits.append(case)
    assert len(audits)==len(REVIEW)==24
    immutable_json(HOME/'source_inventory.json',audits)
    grading_path=ROOT/bound['grade_path']
    assert sha(grading_path)==bound['grade_sha256']
    grade=read(grading_path)
    counts=defaultdict(Counter)
    figures=[]
    card_count=0
    for row in audits:
        category=row['category']
        observed=grade[row['source']][TASK]
        stats=counts[category]
        stats['mothers']+=1
        stats[observed['answer']]+=1
        stats['past_predictions_exact']+=row['historical_answer']==observed['answer']
        stats['covered_by_old_pattern']+=row['old_literal_match']
        if not row['old_literal_match'] and observed['answer']=='Entailment':
            cites=set(observed['evidence'])
            assert cites<=set(row['reviewed_native_span_ids'])
            figures.append({'source_trigger_type':category,
                            'cited_native_spans':len(cites),'positive_citation_witness':bool(row['evidence_support_spans']),
                            'graph_trigger_tags':(row['graph_card'] or {}).get('triggers',[])})
        stats['source_linked_positive_witnesses']+=bool(row['evidence_support_spans'])
        if row['graph_card']:
            card_count+=1
            stats['prior_verified_cards']+=1
            tags=set(row['graph_card']['triggers'])
            stats['prior_closure_tags']+=bool(tags&TERMINATION_TAGS)
            if row['evidence_support_spans'] and not tags&TERMINATION_TAGS:
                stats['explicit_witness_with_no_coarse_closure_tag']+=1
            if category==REQUEST_ONLY and observed['answer']=='Entailment':
                assert tags=={'request'}
    assert card_count==21 and len(figures)==5
    family_label_ceiling=sum(max(c['Entailment'],c['NotMentioned']) for c in counts.values())
    summary={'scope':'All 24 original ContractNLI TRAIN mothers on the disposition-at-termination hypothesis',
             'verified_prior_source_cards':card_count,
             'archived_native_program_calls_verified':len(audits),
             'source_trigger_families':{k:dict(v) for k,v in counts.items()},
             'five_reference_entailments_outside_previous_explicit_pattern':figures,
             'family_only_in_sample_upper_bound_correct':family_label_ceiling,
             'family_upper_bound_is_retrospective_and_not_a_policy_score':True,
             'literal_service_extension_is_shared_with_direct_control':True,
             'original_cards_with_incomplete_scope':sum(row['graph_card'] is not None and
                                                         not row['graph_card']['scope_complete'] for row in audits),
             'native_confirmatory_effect_established':False,
             'model_calls_added':0,'ledger_rows':sum(settled.values()),'DEV_or_TEST_used':False,
             'registry_manifest_sha256':sha(REGISTRY),
             'source_inventory_sha256':sha(HOME/'source_inventory.json'),
             'bound_experiment_source_sha256':sha(Path(__file__))}
    immutable_json(HOME/'terminal.json',summary)
    print(json.dumps(summary,sort_keys=True),flush=True)


if __name__=='__main__':
    run()
