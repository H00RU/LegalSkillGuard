"""Fixed MAUD reference/paid-read audit of shared completion-invariant F.

66 existing source views x3 and54 original paid outputs. No new trial, model
client, source annotation, heldout case or query-driven data expansion.
Predictions are sealed before mechanically reading TRAIN D/C native grades.
"""
from collections import Counter,defaultdict
import json
from pathlib import Path
from types import SimpleNamespace

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import BASE,ROOT,read,sha
from experiments.two_method_normalize_graph_reads import physical_response
from experiments.two_method_reference_chain_audit import CORPUS,PREFLIGHT
from legal_skill_guard.paired_interfaces.control_answers import source_bundle
from legal_skill_guard.paired_interfaces.control_tools import legal_tools,module_assets
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor
from legal_skill_guard.paired_interfaces.partial_legal_consumer import BASE_SHA256,PROTOCOL
from legal_skill_guard.paired_interfaces.production_decode import decode_response
from legal_skill_guard.paired_interfaces.reference_wire import reference_wire
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


def run():
    if (BASE/'formal_study_v1/active_study.json').exists():raise ValueError('A frozen formal study is active')
    before=read(BASE/'revision_20261117/delivery.json');prior=ROOT/before['M1_artifact_root']
    study=read(ROOT/before['preflight']['artifact_root']/'protocol.json')
    registry_path=ROOT/study['registry_path'];registry=read(registry_path)
    roles={r['source']:r['role'] for r in read(registry_path.parent/'roles.json')}
    public_path=ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    sources={s['key']:s for s in read(public_path)}
    assert {k:digest(s) for k,s in sources.items()}==registry['source_public_sha256']
    reviews=[r for r in registry['reviews'] if sources[r['source']]['dataset']=='MAUD'];assert len(reviews)==66
    paid=[r for r in read(CORPUS)['inventory'] if r['dataset']=='MAUD' and r['read_settled']];assert len(paid)==54
    bindings={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__).resolve(),
        ROOT/'experiments/two_method_annotate.py',ROOT/'experiments/two_method_normalize_graph_reads.py',
        *sorted((ROOT/'legal_skill_guard/paired_interfaces').glob('*.py')),
        ROOT/'legal_skill_guard/skill_evolution/native.py',ROOT/'legal_skill_guard/skill_evolution/objects.py']}
    protocol={'name':'fixed-MAUD-shared-partial-F-existing-evidence-v1','source_sha256':bindings,
        'partial_execution_protocol':PROTOCOL,'unchanged_frozen_MAUD_sha256':BASE_SHA256,
        'prior_prediction_root':str(prior.relative_to(ROOT)),'prior_summary_sha256':sha(prior/'summary.json'),
        'source_registry_path':str(registry_path.relative_to(ROOT)),'source_registry_sha256':sha(registry_path),
        'source_cards_sha256':{r['path']:r['sha256'] for r in reviews},
        'TRAIN_public_sha256':sha(public_path),'original_paid_graphs_source_units_and_schemas_unchanged':True,
        'source_context_restoration_proposal_not_activated':True,
        'new_model_or_teacher_calls':0,'new_independent_trials':0,
        'no_DEV_TEST_or_structure_evaluation_reference_access':True,
        'only_original_TRAIN_D_C_native_grading_after_prediction_seal':True}
    out=BASE/'partial_F_revision_20261117'/digest(protocol)
    immutable_json(out/'protocol.json',protocol)
    for name,value in bindings.items():
        target=out/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():target.write_bytes((ROOT/name).read_bytes())
        assert sha(target)==value
    actor=InterfaceActor(SimpleNamespace(config=registry['executor']),out/'unused_metadata_actor',
        plan_assets=read(PREFLIGHT/'plan_assets.json'),source_inputs=inputs,pipeline_binding=bindings)
    views={(s['key'],v['view']):v for s in sources.values() if s['dataset']=='MAUD' for v in actor.views(s)}
    jobs=[]
    for entry in reviews:
        assert sha(ROOT/entry['path'])==entry['sha256']
        card=read(ROOT/entry['path']);view=views[entry['source'],entry['view']]
        assert card['source_units_sha256']==digest(view['source_units'])
        assert card['source_semantic_truth_verified'] is True
        for plan in view['plans']:
            jobs.append({'kind':'reference_wire_probe','source':entry['source'],'view':entry['view'],
                'plan':plan,'wire':reference_wire('MAUD',plan,card,view['source_units'])})
    for item in paid:
        view=views[item['source'],item['view']];plan=next(p for p in view['plans'] if p['name']==item['plan'])
        request=read((ROOT/item['read_path']).with_name('task.json'))
        assert digest(request['output_schema'])==digest(plan['schema'])
        actual=read(ROOT/item['read_path']);response,physical=physical_response(actual,item['source'])
        jobs.append({'kind':'original_paid_response_replay','source':item['source'],'view':item['view'],
            'plan':plan,'response':response,'physical':physical})
    assert len(jobs)==252
    predictions=[];comparisons=[];tools_by_source={}
    for i,job in enumerate(jobs):
        source=sources[job['source']];view=views[job['source'],job['view']];plan=job['plan']
        response=job.get('response',{'content':json.dumps(job.get('wire')),'finish_reason':'stop'})
        result=decode_response(source,view,plan,response)
        oldpath=prior/'predictions'/(digest([job['kind'],job['source'],job['view'],plan['name']])+'.json')
        old=read(oldpath)
        assert digest(old['graph'])==digest(result['graph'])
        for task,value in result['native'].items():
            previous=old['native'][task]
            if previous['handled']:
                assert value['handled'] and value['answer']==previous['answer']
            elif value['handled']:
                assert value['answer']=='Yes'
                assert value['partial_F_execution']['path']=='completion_invariant_positive_witness'
        control_equal=True
        if result['graph'] is not None:
            if job['source'] not in tools_by_source:
                tools,assets=legal_tools(source,source_bundle(source))
                assert assets['completion_invariant_execution']['frozen_base_sha256']==BASE_SHA256
                tools_by_source[job['source']]=tools
            for task,value in result['native'].items():
                control=tools_by_source[job['source']]['frozen_legal_module']['invoke']({'graph':result['graph'],'task':task})
                control_equal &= (control['handled'],control['answer'])==(value['handled'],value['answer'])
            assert control_equal
        row={'source':job['source'],'dataset':'MAUD','view':job['view'],'role':roles[job['source']],
            'plan':plan['name'],'kind':job['kind'],**result,
            'original_prediction_sha256':sha(oldpath),'old_native':old['native'],
            'physical':job.get('physical'),'new_model_requests':0,'new_independent_trial':False,
            'control_tool_answers_match':control_equal,'graph_unknowns_scope_and_source_assertions_unchanged':True}
        immutable_json(out/'predictions'/(digest([job['kind'],job['source'],job['view'],plan['name']])+'.json'),row)
        predictions.append(row)
        if (i+1)%60==0:print(json.dumps({'predictions_finished':i+1}),flush=True)
    immutable_json(out/'prediction_seal.json',{'predictions':len(predictions),
        'source_kind_identities_sha256':digest([(r['kind'],r['source'],r['view'],r['plan']) for r in predictions]),
        'no_native_grading_opened_before_this_seal':True,'pure_R_and_internal_grading_prohibited':True})
    eligible={r['source'] for r in predictions if r['role'] in ('development','calibration')}
    raw_grading=read(public_path.with_name('grading.json'));grading={s:raw_grading[s] for s in eligible};del raw_grading
    old_scores=read(prior/'D_C_native_scores.json')
    old_score={(r['kind'],r['source'],r['view'],r['plan'],r['native_task']):r['native_metrics']['grade'] for r in old_scores if r['dataset']=='MAUD'}
    scores=[];counts=defaultdict(Counter)
    for row in predictions:
        stat=counts[row['kind']];stat['views_x_plans']+=1
        stat['production_decoder_refusals']+=bool(row['production_errors'])
        for task,value in row['native'].items():
            old=row['old_native'][task];stat['old_handled']+=old['handled'];stat['new_handled']+=value['handled']
            stat['newly_handled']+=value['handled'] and not old['handled']
            if row['source'] not in eligible:continue
            native=next(v for v in sources[row['source']]['views'] if v['id']==task)
            grade=(grade_view('MAUD',native,grading[row['source']][task],value['answer'],[]) if value['handled'] else {'grade':0.})
            previous=old_score[row['kind'],row['source'],row['view'],row['plan'],task]
            stat['D_C_scored_tasks']+=1;stat['D_C_old_positive']+=previous>0;stat['D_C_new_positive']+=grade['grade']>0
            scores.append({k:row[k] for k in ('kind','source','view','role','plan')} |
                {'native_task':task,'handled':value['handled'],'old_grade':previous,'new_native_metrics':grade,
                 'partial_F_execution':value.get('partial_F_execution')})
    immutable_json(out/'D_C_native_scores.json',scores)
    summary={'artifact_root':str(out.relative_to(ROOT)),'source_reference_views':66,'original_paid_outputs':54,
        'predictions':252,'all_prior_defined_answers_preserved':True,'graph_and_scope_changes':0,
        'main_and_control_F_mismatches':0,'frozen_F_sha256':BASE_SHA256,'new_model_or_teacher_requests':0,
        'source_reference_mothers':len({r['source'] for r in predictions if r['kind']=='reference_wire_probe'}),
        'D_C_scored_mothers':len(eligible),'pure_R_grading_opened':False,'all_predictions_sealed_before_grading':True,
        'counts':[{ 'kind':kind,**dict(v)} for kind,v in sorted(counts.items())],
        'shared_execution_change_is_not_M1_learning_or_independent_method_evidence':True,
        'extra_source_context_was_not_added':True,'source_context_gap_and_fresh_TEST_still_unresolved':True,
        'formal_training_not_started':True,'goal_complete':False}
    for name,value in bindings.items():assert sha(ROOT/name)==value,name
    assert all(sha(ROOT/e['path'])==e['sha256'] for e in registry['reviews'])
    assert sha(ROOT/'legal_skill_guard/paired_interfaces/legal_consumers.py')==BASE_SHA256
    immutable_json(out/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    return out,summary


if __name__=='__main__':run()
