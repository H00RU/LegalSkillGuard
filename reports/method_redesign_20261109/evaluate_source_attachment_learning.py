"""Freeze cheap strong controls and replay fixed source-only reuse.

No new native questions or labels are graded. Human source-meaning review is
separate from compatibility with the visible partial TRAIN constraints.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from experiments.rr_v2_source_attachment_learning import ROOT,STAGE,read,sha,snapshot
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.source_attachment_learning import features,meaning,problem,choose,project,native_answers

SCRIPT=Path(__file__).resolve()


def signature(material,forest):
    counts={}
    for record in forest['rules']:
        text=record['readings'][0]['head_quote'].casefold()
        for word in re.findall(r'\w+',text):
            for i in range(max(1,len(word)-3)):
                gram=word[i:i+4];counts[gram]=counts.get(gram,0)+1
    return counts


def cosine(x,y):
    den=math.sqrt(sum(v*v for v in x.values())*sum(v*v for v in y.values()))
    return sum(v*y.get(k,0) for k,v in x.items())/den if den else 0.


def retrieval_memory(rows,problems):
    memory=[]
    for key,row in rows.items():
        p=problems[key];good=[i for i,x in enumerate(p['compatible']) if x]
        chosen=max(good,key=lambda i:p['prior'][i]);prior=choose(None,p)['choice'];prior_index=p['choices'].index(tuple(prior))
        a=p['feature_dicts'][chosen];b=p['feature_dicts'][prior_index]
        delta={k:a.get(k,0)-b.get(k,0) for k in a.keys()|b.keys()}
        memory.append({'training_key':key,'signature':signature(row['material'],row['forest']),
                       'correction':{k:v for k,v in delta.items() if v},'source_feedback_only':True})
    return memory


def retrieve(memory,row,p):
    query=signature(row['material'],row['forest']);nearest=max(memory,key=lambda m:cosine(query,m['signature']))
    delta=nearest['correction'];norm=math.sqrt(sum(v*v for v in delta.values())) or 1.
    scores=[float(base)+sum(delta.get(k,0)*v for k,v in f.items())/norm for base,f in zip(p['prior'],p['feature_dicts'])]
    indices=[i for i,x in enumerate(p['valid']) if x];idx=max(indices,key=lambda i:scores[i])
    return {'choice':list(p['choices'][idx]),'score':scores[idx],'retrieved_training_key':nearest['training_key'],
            'training_compatible':bool(p['compatible'][idx])}


def preferred_programs(material,rid,reading):
    """A source-licensed ordinary lexical/tree control, not a verifier."""
    rule=next(r for r in material['graph']['rules'] if r['id']==rid)
    head=reading['head_quote'].casefold();negative=reading['negation_quote'].casefold()
    if re.search(r'\bbreach\w*\b',head):
        return {'NOT(BREACH(A))'} if re.search(r'\bnot\b',negative) else {'BREACH(A)'}
    if re.search(r'\b(?:prohibit\w*|preclud\w*|forbid\w*|disallow\w*|barred)\b',head):
        if re.search(r'\bnot\b',negative) and re.search(r'\bnot\b.{0,35}\b(?:preclud|prohibit|forbid|disallow)',head):return {'NOT(F(A))'}
        # Do not manufacture an advantage from an undeclared P duality.
        return {'F(A)','O(NOT(A))','NOT(P(A))'}
    word=re.escape(reading['action_quote'])
    support=' '.join(rule['source_quotes'])
    if re.search(r'\bmay\b[^.;]{0,100}\b'+word+r'\b',support,re.I):return {'P(A)'}
    if re.search(r'\b(?:shall|must|agrees)\b[^.;]{0,100}\bnot\b[^.;]{0,80}\b'+word+r'\b',support,re.I):return {'F(A)','O(NOT(A))','NOT(P(A))'}
    if re.search(r'\b(?:shall|must|agrees)\b[^.;]{0,120}\b'+word+r'\b',support,re.I):return {'O(A)'}
    return set()


def qualifier_role(quote):
    words=re.findall(r'\w+',quote.casefold())
    if not words:return None
    if words[:2] in [['provided','that'],['subject','to']]:return 'condition'
    if words[0] in ['except','notwithstanding']:return 'reference'
    if words[0] in ['if','upon','when','within','solely','whichever','immediately','unless','or']:return 'condition'
    if words[0].isdigit() or ('provisions' in words and 'survive' in words):return 'context'
    return None


def ordinary_tree(row,p):
    material=row['material'];forest=row['forest'];rules={r['id']:r for r in material['graph']['rules']}
    def score(index):
        choice=p['choices'][index];selected={r['rule_id']:r['readings'][j] for r,j in zip(forest['rules'],choice)}
        heads=roles=bindings=0
        for rid,r in selected.items():
            wanted=preferred_programs(material,rid,r)
            heads+=int(bool(wanted) and r['program'] in wanted)
            for role,key in [('condition','conditions'),('reference','references'),('context','context_quotes')]:
                roles+=sum(qualifier_role(q)==role for q in r[key])
            target=r['exception_target']
            potential=[k for k,v in rules.items() if k!=rid and v['action']=='return_or_destroy'
                       and rules[rid]['action']=='retain' and set(v['source_quotes'])&set(rules[rid]['source_quotes'])
                       and any(re.search(r'\bexcept\b',q,re.I) for q in set(v['source_quotes'])&set(rules[rid]['source_quotes']))]
            if potential and meaning(r)['effect']=='permission':
                if target in potential:
                    other=selected[target]
                    bindings+=int(bool(r['information_anchor']) and r['information_anchor']==other['information_anchor']
                                  and r['actor_quote'].casefold()==other['actor_quote'].casefold()
                                  and meaning(other)['effect']=='obligation')
            elif target is None:bindings+=1
        return heads,roles,bindings,float(p['prior'][index])
    indices=[i for i,x in enumerate(p['valid']) if x];idx=max(indices,key=score)
    return {'choice':list(p['choices'][idx]),'lexicographic_score':list(score(idx)),
            'training_compatible':bool(p['compatible'][idx])}


def controls(row,p,models,memory):
    return {'marginal':choose(models['marginal'],p),'hard_em':choose(models['hard_em'],p),
            'frozen_proposal_prior':choose(None,p),'same_material_correction_retrieval':retrieve(memory,row,p),
            'ordinary_lexical_tree':ordinary_tree(row,p)}


def freeze():
    before=snapshot();seal=read(STAGE/'seal.json');learned=read(STAGE/'learned_attachment_parameters.json')
    rows={key:read(STAGE/(key+'_forest.json')) for key in ['p15','p20','p111']}
    problems={key:problem(row['material'],row['forest'],seal['partial_source_feedback'][key]) for key,row in rows.items()}
    memory=retrieval_memory(rows,problems)
    replay={key:controls(row,problems[key],learned['models'],memory) for key,row in rows.items()}
    paths=[SCRIPT.relative_to(ROOT).as_posix(),'legal_skill_guard/rr/source_attachment_learning.py',
           'legal_skill_guard/rr/source_attachment_forests.py','experiments/rr_v2_source_attachment_learning.py',
           'reports/method_redesign_20261109/source_attachment_learning_protocol.md']
    data={'controls':list(next(iter(replay.values()))),'training_replay':replay,'retrieval_memory':memory,
          'same_feature_log_linear_parameterization_is_identical_not_independent_evidence':True,
          'free_program_control_required_before_any_positive_contribution_claim_if_cheap_controls_do_not_absorb_effect':True,
          'old_paid_seed_heads_and_unique_information_resolver_shared_by_every_arm':True,
          'no_new_model_calls':True,'no_new_native_labels':True,'goal_complete':False}
    immutable_json(STAGE/'controls_and_training_replay.json',data)
    immutable_json(STAGE/'reuse_freeze.json',{'files':{p:sha(ROOT/p) for p in paths},
        'models_sha256':sha(STAGE/'learned_attachment_parameters.json'),'controls_sha256':sha(STAGE/'controls_and_training_replay.json'),
        'source_plan_sha256':sha(STAGE/'source_only_reuse_plan.json'),
        'scoring':'Review selected source programs, conditional/reference roles and actual exception/information binding on the fixed source slices; not new native NLI grades',
        'no_weight_or_selector_tuning_from_reserved_source_results':True,'DEV_sealed':True})
    assert before==snapshot()
    print(json.dumps({'frozen':True,'training_partial_constraint_fit':{key:{k:v['training_compatible'] for k,v in value.items()} for key,value in replay.items()},'new_model_calls':0}))


def evaluate():
    freeze=read(STAGE/'reuse_freeze.json')
    for p,h in freeze['files'].items():assert sha(ROOT/p)==h,p
    assert sha(STAGE/'learned_attachment_parameters.json')==freeze['models_sha256']
    assert sha(STAGE/'controls_and_training_replay.json')==freeze['controls_sha256']
    before=snapshot();models=read(STAGE/'learned_attachment_parameters.json')['models']
    memory=read(STAGE/'controls_and_training_replay.json')['retrieval_memory'];rows=[]
    for key in ['p114','p116','p117','p118']:
        raw=read(STAGE/(key+'_forest.json'))
        record={'key':key,'material':raw['material'],'forest_accepted':raw['accepted'],'controls':{}}
        if raw['accepted']:
            p=problem(raw['material'],raw['forest'],[])
            for name,selection in controls(raw,p,models,memory).items():
                record['controls'][name]={'selection':selection,**project(raw['material'],raw['forest'],selection['choice'])}
        else:record['error']=raw['error']
        rows.append(record)
    assert before==snapshot()
    immutable_json(STAGE/'fixed_source_reuse_predictions.json',{'results':rows,'new_model_calls_for_decoding':0,
        'new_native_predictions_or_labels':0,'source_semantic_review_pending':True,'goal_complete':False})
    print(json.dumps({'fixed_original_mothers':4,'accepted_forests':sum(r['forest_accepted'] for r in rows),'native_labels':0,'goal_complete':False}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['freeze','evaluate']);a=p.parse_args()
    freeze() if a.action=='freeze' else evaluate()
