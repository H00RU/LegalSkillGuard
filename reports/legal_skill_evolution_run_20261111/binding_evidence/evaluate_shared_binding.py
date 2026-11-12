"""Execute actual learned binding and strong controls after the causal audit.

The fitted Joint/Unary policies are identical and contain no cross-slot literal.
No extra free-program model request or held-reuse exposure is justified to test
that absent mechanism. This saves the planned request, not the active Goal.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.binding_learning import resolve
from legal_skill_guard.skill_evolution.native import source_spans,grade_view
from legal_skill_guard.skill_evolution.scoped_grammar import constructors,material_public,term_sort
from legal_skill_guard.skill_evolution.scoped_reader import apply_current

ROOT=Path(__file__).resolve().parents[3]
path=Path(__file__).with_name('ground_actual_demonstrations.py')
loader=importlib.util.spec_from_file_location('grounded_binding',path)
ground=importlib.util.module_from_spec(loader);loader.loader.exec_module(ground)
s=ground.study


if __name__=='__main__':
    folder,p,ledger,public=s.setup(ROOT);b,cases,models=ground.grounded_fit(ROOT)
    audit=s.read(folder/'binding_opportunity_audit.json')
    assert audit['joint_and_unary_policies_identical']
    assert not any(a['cross_slot_literals_used'] for a in audit['actual_open_claims'])
    assert not (folder/'free_teacher.json').exists() and not (folder/'reuse_freeze.json').exists()
    with sqlite3.connect(ledger.path) as c:before=list(c.execute('select * from calls order by id'))
    immutable_json(folder/'mechanism_audit_decision.json',{
        'joint_unary_identical_on_every_possible_assignment_for_these_fitted_policies':True,
        'reason':'Both policy dictionaries are identical and every literal is unary; deleting cross-slot features cannot change any predicate read by these policies.',
        'cross_slot_literals_used':0,'additional_free_model_request_not_dispatched':True,
        'held_TRAIN_reuse_not_opened':True,'no_code_or_data_changed_to_force_activation':True,
        'not_a_general_impossibility_claim':True,'goal_complete':False})
    grading=s.read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    base=s.warm_base(ROOT,p);schema=constructors(b['spec']);results={a:[] for a in ('Joint','UnaryRelations','NearestContext')}
    for key in p['development_sources']:
        source=public[key];case=s.decode(b,source)
        immutable_json(folder/'development_controls/fragments'/(key.replace(':','_')+'.json'),case)
        spans=source_spans(material_public(source['views'][0]['public']))
        inherited={v['view']:v for v in base[key]['views']}
        for arm in results:
            binding=resolve(models.get(arm,models['Joint']),case['fragments'],schema,nearest=arm=='NearestContext')
            nodes=[]
            for item in binding['statements']:
                sort=term_sort(item['term'],schema)
                if sort not in ('Norm','Definition','Description'):continue
                nodes.append({'id':len(nodes),'sort':sort,'term':item['term'],
                    'support_ids':item['support_ids'],'child_ids':[],'ambiguous':False})
            interp={'nodes':nodes,'roots':[n['id'] for n in nodes]};views=[]
            for view in source['views']:
                execution=apply_current(b['spec'],{'rules':[],'disabled_rules':[],'acquired_pairs':[]},interp,view)
                value=execution['value'];blocked=bool(binding['unresolved'] or case['decoder_unresolved'])
                core=value['handled'] and not blocked
                ids=sorted({i for n in value['used_nodes'] for i in nodes[n]['support_ids']})
                proof=sorted({spans[i]['public_sentence_id'] for i in ids if 'public_sentence_id' in spans[i]})
                answer=value['answer'] if core else inherited[view['id']]['execution']['answer']
                score=grade_view('ContractNLI',view,grading[key][view['id']],answer,proof) if core else inherited[view['id']]['score']
                views.append({'view':view['id'],'core_executed':core,'fallback':not core,
                    'answer':answer,'score':score,'primary_proof_sentence_ids':proof,'execution':execution,
                    'source_unresolved_gate':blocked,'source_semantic_review_pending':True})
            row={'source':key,'arm':arm,'interpretation':interp,'binding':binding,
                'decoder_unresolved':case['decoder_unresolved'],'views':views,'goal_complete':False}
            immutable_json(folder/'development_controls'/arm/(key.replace(':','_')+'.json'),row)
            results[arm].append(row)
    summary={}
    for arm,rows in results.items():
        views=[v for r in rows for v in r['views']]
        primary=[v for v in views if v['core_executed']]
        evidence=[v['score']['evidence_f1'] for v in primary if 'evidence_f1' in v['score']]
        summary[arm]={'source_count':len(rows),'views':len(views),'core':len(primary),
            'core_native_correct':sum(v['score']['correct'] for v in primary),
            'fallback':sum(v['fallback'] for v in views),
            'primary_evidence_f1_mean':sum(evidence)/len(evidence) if evidence else None,
            'primary_evidence_scored_views':len(evidence)}
    for left,right in zip(results['Joint'],results['UnaryRelations']):
        assert left['interpretation']==right['interpretation'] and left['views']==right['views']
    with sqlite3.connect(ledger.path) as c:after=list(c.execute('select * from calls order by id'))
    assert before==after
    immutable_json(folder/'development_controls/completed.json',{'results':results,'summary':summary,
        'joint_unary_source_and_all_native_outputs_exactly_identical':True,
        'new_model_requests':0,'no_held_TRAIN_reuse_opened':True,'no_new_DEV_TEST_or_full_study':True,
        'ledger_rows_unchanged':len(after),'goal_complete':False})
    print(json.dumps(summary),flush=True)
