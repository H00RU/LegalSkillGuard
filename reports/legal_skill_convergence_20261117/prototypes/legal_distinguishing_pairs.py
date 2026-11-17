"""Finite exact prototype. No LLM calls; symbolic hypotheses, not model results."""
from pathlib import Path
from itertools import product, combinations
import hashlib, json, re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def signature(hypothesis, pair, interpretations, independent=False):
    if independent:
        return {tuple(hypothesis(x, theta) for x, theta in zip(pair, ts))
                for ts in product(interpretations, repeat=len(pair))}
    return {tuple(hypothesis(x, theta) for x in pair) for theta in interpretations}

def disjoint(a, b):
    return not (a & b)

def encode(s):
    return [list(v) for v in sorted(s)]

def scoped_ownership_signature(cases):
    """Law is fixed here; independently quantify latent ownership for each root.

    A derived case inherits its root's unedited unknowns. An explicitly permitted
    primitive intervention overrides ownership only for that derived case, then
    permission is recomputed. This is a fixture, not a claim about real property law.
    """
    root_ids=sorted({c['root_id'] for c in cases})
    signatures=set()
    for values in product([False,True], repeat=len(root_ids)):
        root_latent=dict(zip(root_ids,values))
        outcomes=[]
        for case in cases:
            assert case['law_scope']=='fixture:owner_required:v1'
            owns=case.get('intervention',{}).get('owns',root_latent[case['root_id']])
            permission=owns  # dependency closure is recomputed after intervention
            outcomes.append(bool(owns and permission))
        signatures.add(tuple(outcomes))
    return signatures

def main():
    # Legal toy: a benefit applies only at age >=65 (or >65), net <=100.
    # Net is a derived fact; changing wage must also update net.
    # H_reader uses total net; H_consumer only uses wage. Both are fixed bug models.
    interpretations = [False, True]  # inclusive/strict age boundary
    records = [dict(age=a, wage=w, bonus=b, net=w+b)
               for a,w,b in product([65,66], [80,110], [0,30])]
    def scope(x, strict):
        return x['age'] > 65 if strict else x['age'] >= 65
    def reader_fix(x, strict):
        return scope(x, strict) and x['net'] <= 100
    def consumer_fix(x, strict):
        return scope(x, strict) and x['wage'] <= 100
    allowed = [(x,y) for x,y in combinations(records,2)
               if x['age']==y['age'] and x['wage']==y['wage']
               and x['bonus'] != y['bonus']]
    witnesses=[]
    for q in allowed:
        a=signature(reader_fix,q,interpretations)
        b=signature(consumer_fix,q,interpretations)
        if disjoint(a,b):
            witnesses.append({'pair':q, 'reader_fix':encode(a), 'consumer_fix':encode(b)})
    assert witnesses
    assert all(w['pair'][0]['age']==66 for w in witnesses)
    # At ambiguous scope age65 the off-scope interpretation makes both identical.
    ambiguous=[q for q in allowed if q[0]['age']==65]
    assert not any(disjoint(signature(reader_fix,q,interpretations),
                            signature(consumer_fix,q,interpretations)) for q in ambiguous)
    # Different component edits can induce precisely the same source->answer function.
    # R=not x, P=not z versus R=x, P=z cannot be separated by terminal-only inputs.
    terminal_identical=all((not(not x))==x for x in [False,True])
    assert terminal_identical

    # Real TRAIN text; exact-span amount patch. No native label or payment date oracle.
    source_path=HERE/'sara_source_fixture.json'
    p=json.loads(source_path.read_text(encoding='utf-8'))['pairs'][0]
    assert p['split']=='TRAIN'
    original=p['reference_source_text']; old='$3200'; new='$3500'
    assert original.count(old)==1
    start=original.index(old); modified=original[:start]+new+original[start+len(old):]
    assert modified[:start]==original[:start] and modified[start+len(new):]==original[start+len(old):]
    amounts=tuple(int(re.search(r'\$(\d+)',s).group(1)) for s in (original,modified))
    assert amounts==(3200,3500)
    # Symbolic uncertainty test, deliberately NOT a claim about SARA's true tax rule:
    # threshold is one shared interpretation across source pair.
    thresholds=[3000,3600]
    valid=lambda amount,threshold: amount>=threshold
    bad=lambda amount,threshold: amount<3300
    shared=signature(valid,amounts,thresholds)
    wrongly_independent=signature(valid,amounts,thresholds,independent=True)
    badsig=signature(bad,amounts,thresholds)
    assert disjoint(shared,badsig)
    assert not disjoint(wrongly_independent,badsig)
    # Automatically compile legal pairs and their set-valued reference relation.
    # Both theta3000 and theta3600 remain legitimate; no single one is gold.
    candidates={
        'threshold3000':lambda a:a>=3000,
        'threshold3600':lambda a:a>=3600,
        'unsupported_middle_threshold':lambda a:a>=3300,
        'decreasing_program':lambda a:a<3300,
    }
    compiled=[]
    for new_amount in [2800,3500,3700]:
        q=(3200,new_amount)
        relation=signature(valid,q,thresholds)
        traces={name:tuple(fn(a) for a in q) for name,fn in candidates.items()}
        violations={name:list(v) for name,v in traces.items() if v not in relation}
        rendered=original[:start]+f'${new_amount}'+original[start+len(old):]
        assert int(re.search(r'\$(\d+)',rendered).group(1))==new_amount
        compiled.append({'amount_pair':q,'allowed_signature_relation':encode(relation),
            'candidate_violations':violations,'edit_distance':abs(new_amount-3200),
            'source_pair':[original,rendered],
            'explicit_amount_faithfulness_checked':True})
    selected=min(compiled,key=lambda r:(-len(r['candidate_violations']),r['edit_distance']))
    assert selected['amount_pair']==(3200,3500)
    assert set(selected['candidate_violations'])=={'unsupported_middle_threshold','decreasing_program'}
    # A relation induced by only theta3000 falsely excludes legitimate theta3600.
    selected_pair=selected['amount_pair']
    one_theta_relation=signature(valid,selected_pair,[3000])
    legitimate_theta3600=tuple(a>=3600 for a in selected_pair)
    assert legitimate_theta3600 not in one_theta_relation
    assert legitimate_theta3600 in signature(valid,selected_pair,thresholds)
    law_scope='fixture:owner_required:v1'
    independent_cases=[{'root_id':'case_A','law_scope':law_scope},
                       {'root_id':'case_B','law_scope':law_scope}]
    within_root=[{'root_id':'case_A','law_scope':law_scope,'variant':'base'},
                 {'root_id':'case_A','law_scope':law_scope,'variant':'unrelated_amount_edit'}]
    root_edited=[within_root[0],dict(within_root[1],intervention={'owns':True})]
    independent_latents=scoped_ownership_signature(independent_cases)
    shared_within_root=scoped_ownership_signature(within_root)
    edited_latent=scoped_ownership_signature(root_edited)
    assert (True,False) in independent_latents
    assert (True,False) not in shared_within_root
    assert edited_latent=={(False,True),(True,True)}
    result={
        'new_model_calls':0,
        'kind':'exact finite symbolic mechanism; not actual model accuracy',
        'dependency_and_scope':{'witness_count':len(witnesses),'witness':witnesses[0],
            'candidate_disagreement_not_truth_oracle':True,
            'dependent_fields_updated':['net'],'primitive_edit':['bonus'],
            'age65_robustly_identifiable':False,
            'age65_reason':'shared strict interpretation excludes scope for both hypotheses'},
        'terminal_equivalent_component_repairs':{'identifiable':False,'exhaustive_boolean_check':terminal_identical,
            'required_extra_observation':'reader field/source provenance, not more terminal examples'},
        'real_train_source_patch':{'source_key':p['source_key'],'split':'TRAIN',
            'source_artifact_sha256':hashlib.sha256(source_path.read_bytes()).hexdigest(),
            'original':original,'modified':modified,'edit_span':[start,start+len(old)],
            'changed_explicit_field':'payment.amount','amounts':amounts,
            'frame_byte_preservation':True,
            'payment_date_and_year':'not added; source does not state them',
            'native_label_used':False,'consumer_rule_used':'synthetic shared threshold for mechanism check only'},
        'shared_interpretation_check':{'shared_valid_signatures':encode(shared),
            'independent_per_case_signatures':encode(wrongly_independent),
            'bad_candidate_signature':encode(badsig),
            'shared_interpretation_rejects_bad_candidate':True,
            'independent_completion_falsely_keeps_candidate':True},
        'automatic_relation_synthesis':{'generated_pairs':compiled,'selected_pair':selected,
            'selection':'maximize number of candidate violations, then minimize amount change',
            'surviving_updates':['threshold3000','threshold3600'],
            'survivors_are_not_certified_true':'They are not yet contradicted by the finite reference theory family.'},
        'single_interpretation_unsoundness':{'theta_used':3000,'induced_relation':encode(one_theta_relation),
            'legitimate_theta3600_signature':list(legitimate_theta3600),
            'falsely_rejected_if_only_one_theta':True,
            'accepted_by_shared_family_relation':True},
        'interpretation_scope_checks':{
            'semantic_uncertainty_may_be_incomplete_audit_not_genuine_legal_ambiguity':True,
            'law_scope':'Law interpretation shared only by regulation version/definition/applicability scope.',
            'root_latent':'Unedited unknown case facts shared only across variants of the same mother/root; independent cases receive independent latent variables.',
            'independent_cases_allowed_signatures':encode(independent_latents),
            'within_root_unedited_allowed_signatures':encode(shared_within_root),
            'cross_case_shared_ownership_would_spuriously_reject_TF':True,
            'within_root_independent_ownership_would_spuriously_accept_TF':True,
            'allowed_ownership_edit_recomputes_permission':encode(edited_latent),
            'source_fixture_status':'Synthetic ownership dependency, not a real law or native dataset annotation.'},
        'strong_baseline_boundary':'A general constraint-based distinguishing-input solver supplied the same semantics can recover these pairs. The proposed contribution is specialized constraint construction/learning object, not a new SAT/active-learning primitive.'}
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
