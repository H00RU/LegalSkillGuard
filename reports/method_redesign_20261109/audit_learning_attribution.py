"""Post-hoc, zero-call attribution: separate fitting from hand-written grammar.

Not a second blind experiment. No tuning, resampling, source additions or model
refits in the frozen arms. These extra controls use the original four TRAIN
induction cases only, then score the already closed excluded observations.
"""
import json
import math
import numpy as np
from legal_skill_guard.rr.semantic_learning import OPS, PRIMITIVES, H, Y, transform, forecasts
from experiments.rr_v2_semantic_learning import read, STAGE, REPORT, check_frozen
from legal_skill_guard.rr.checkpoint import immutable_json


def prior():
    p = np.array([math.exp(-.5*sum(v!='self' for v in op)) for op in OPS]); return p/p.sum()


def factor_fit(rows):
    result=[]
    p=np.array([math.exp(-.5*(v!='self')) for v in PRIMITIVES]);p/=p.sum()
    for i in range(4):
        likelihood=np.array([[.95*int(transform(r['h'], tuple(v if k==i else 'self' for k in range(4)))[i]==r['y'][i])+.05/3 for v in PRIMITIVES] for r in rows])
        w=p.copy();rw=np.array([r['weight'] for r in rows])
        for _ in range(100):
            z=likelihood*w;z/=z.sum(axis=1,keepdims=True);w=(z*rw[:,None]).sum(axis=0)+p;w/=w.sum()
        result.append(w.tolist())
    return result


def factored_forecast(h, weights):
    marginal=[]
    for i in range(4):
        p=np.full(3,.05/3)
        for v,w in zip(PRIMITIVES,weights[i]):
            pred=transform(h,tuple(v if k==i else 'self' for k in range(4)))[i];p[pred]+=.95*w
        marginal.append(p)
    return [math.prod(marginal[i][y[i]] for i in range(4)) for y in Y]


def main():
    f=check_frozen();rows=f['training_rows']; frozen=f['models']; result=read(REPORT/'M1M2_real_TRAIN_results.json')
    zero=json.loads(json.dumps(frozen));zero['structured']['global']=prior().tolist();zero['structured']['contexts']={}
    global_factor=factor_fit(rows)
    local_factors={''.join(map(str,r['context'])):factor_fit([s for s in rows if s['context']==r['context']]) for r in rows}
    scores=[]
    for r in result['rows']:
        c=read(STAGE/'blind_predictions.json')['cases'][r['case_id']]['context']
        weights=local_factors.get(''.join(map(str,c)),global_factor)
        controls={'untrained_same_structured_grammar':forecasts(zero,r['h'],c)['structured'],
                  'fitted_factorized_same_operator_grammar':factored_forecast(r['h'],weights)}
        entry={'case_id':r['case_id'],'variant':r['variant'],'scores':{}}
        for name,p in controls.items():
            yi=Y.index(tuple(r['y']));entry['scores'][name]={'NLL':-math.log(p[yi]),'top1_exact':int(max(range(81),key=lambda i:p[i])==yi)}
        scores.append(entry)
    means={name:{k:sum(e['scores'][name][k] for e in scores)/len(scores) for k in ('NLL','top1_exact')} for name in scores[0]['scores']}
    hypotheses=[]
    for group in ('global','00','10'):
        mix=frozen['structured']['global'] if group=='global' else frozen['structured']['contexts'][group]
        order=np.argsort(mix)[::-1][:3]
        for i in order:
            op=OPS[i]; matching=[r for r in rows if transform(r['h'],op)==r['y']]
            diagnostic=[r for r in matching if r['y']!=list(r['h'])*2]
            hypotheses.append({'context':group,'operator':list(op),'mass':mix[i],
                'error_demonstrating_induction_mothers':sorted({r['mother'] for r in diagnostic}),
                'identity_equivalent_matches_do_not_validate_copy_direction':True})
    out={'analysis_type':'Post-hoc frozen-data attribution, not additional confirmatory experiment',
         'new_model_calls':0,'no_new_data_or_parameters_scanned':True,'per_case':scores,'mean':means,
         'frozen_structured_NLL':result['forecast_scores']['structured']['mean']['negative_log_likelihood'],
         'top_operators_induction_support':hypotheses,
         'M1_same_information_tree_exactly_identical':result['M1_absorbed_by_same_information_tree'],
         'conclusion':'Forecast learning can be measured against the untrained grammar; joint-specific advantage requires beating fitted factorized operators. Neither proves source-role coverage or additional correct semantic answers.',
         'goal_complete':False}
    immutable_json(REPORT/'M1M2_learning_attribution.json',out)
    print(json.dumps({'posthoc_means':means,'frozen_structured_NLL':out['frozen_structured_NLL'],'new_calls':0}))


if __name__=='__main__':main()
