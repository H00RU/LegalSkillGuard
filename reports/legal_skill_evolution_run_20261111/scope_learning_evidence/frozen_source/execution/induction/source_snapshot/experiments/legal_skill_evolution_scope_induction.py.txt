"""Fit and compare source influence policies using settled acquired TRAIN only."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.source_influence_learning import (
    RELATIONS,examples,fit,predict,baseline)

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'artifacts/legal_skill_evolution_scope_learning_20261113/execution'
read=lambda p:json.loads(p.read_text())


def evaluate(rows,predictions):
    tp=sum(r['positive'] and p is True for r,p in zip(rows,predictions))
    fp=sum(not r['positive'] and p is True for r,p in zip(rows,predictions))
    fn=sum(r['positive'] and p is not True for r,p in zip(rows,predictions))
    return {'pairs':len(rows),'positive_pairs':sum(r['positive'] for r in rows),'TP':tp,'FP':fp,'FN':fn,
        'unresolved_pairs':sum(p is None for p in predictions),
        'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,
        'F1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}


def control(rows,which):
    if which=='nearest':return [baseline(r['features'],which) for r in rows]
    groups=defaultdict(list)
    for i,r in enumerate(rows):groups[r['source'],r['focus']].append(i)
    result=[False]*len(rows)
    for indices in groups.values():
        explicit=any(rows[i]['features']['explicit_numbered_reference_matches'] for i in indices)
        for i in indices:
            f=rows[i]['features']
            result[i]=(f['explicit_numbered_reference_matches'] and f['target_eligible'] and f['before']) if explicit else f['nearest_eligible_before']
    return result


def run():
    data=read(FOLDER/'input.json');annotations=read(FOLDER/'validated.json')['value']['units']
    protocol=read(FOLDER/'protocol.json')
    paths=[Path(__file__).resolve(),ROOT/'legal_skill_guard/skill_evolution/source_influence_learning.py',
           ROOT/'tests/test_skill_evolution_source_influence.py']
    offline_protocol={'teacher_protocol_sha256':hashlib.sha256((FOLDER/'protocol.json').read_bytes()).hexdigest(),
        'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'same_acquired_labels_and_features_for_controls':True,'no_native_labels_or_reuse_material':True,
        'oracle_local_unit_kinds':'Acquired teacher labels; do not claim real neural inference or end-to-end acquisition.',
        'learner':'Existing exact DNF/set-cover. Adopted mature component, not a new algorithm claim.',
        'comparison':'Nearest eligible vs explicit referenced paragraph all eligible targets vs learned relation. An identical copy of adopted DNF is not an additional novelty gate or baseline.',
        'goal_complete':False}
    immutable_json(FOLDER/'induction/protocol.json',offline_protocol)
    for path in paths:
        dst=FOLDER/'induction/source_snapshot'/path.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():assert dst.read_bytes()==path.read_bytes()
        else:dst.write_bytes(path.read_bytes())
    full={};folds=[]
    for relation in RELATIONS:
        rows=examples(data,annotations,relation);policy=fit(rows)
        full[relation]={'policy':policy,'examples':rows,'training_metrics':evaluate(rows,[predict(policy,r['features']) for r in rows])}
        for held in protocol['sources']:
            train=[r for r in rows if r['source']!=held];test=[r for r in rows if r['source']==held]
            fold_policy=fit(train);outputs={'learned':[predict(fold_policy,r['features']) for r in test],
                'nearest':control(test,'nearest'),
                'explicit_paragraph_or_nearest':control(test,'explicit_paragraph_or_nearest')}
            folds.append({'relation':relation,'held_acquisition_parent':held,'policy':fold_policy,'rows':test,
                'predictions':outputs,'metrics':{k:evaluate(test,v) for k,v in outputs.items()}})
    totals={}
    for arm in ['learned','nearest','explicit_paragraph_or_nearest']:
        rows=[r for fold in folds for r in fold['rows']]
        predictions=[v for fold in folds for v in fold['predictions'][arm]]
        totals[arm]=evaluate(rows,predictions)
    result={'full_fit':full,'leave_one_acquisition_parent_out':folds,'totals':totals,
        'held_acquisition_parents_not_new_blind_TEST':True,'new_executor_calls':0,
        'native_task_benefit_not_measured':True,'contribution_established':False,'goal_complete':False}
    immutable_json(FOLDER/'induction/result.json',result)
    print(json.dumps({'totals':totals,'trained_policy_count':sum(v['policy']['status']=='learned' for v in full.values())}),flush=True)

if __name__=='__main__':run()
