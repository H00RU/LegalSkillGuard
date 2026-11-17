"""Fixed zero-request reanalysis of117 graph pairs and18 OE port pairs.

Reader versions/domains stay separate. No heldout/structural truth or grade
file is read. Pure-reference TRAIN worlds retain their own public task context.
"""
from collections import defaultdict, Counter
import json
from pathlib import Path

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import BASE, ROOT, read, sha
from experiments.two_method_reference_chain_audit import CORPUS, REGISTRY
from legal_skill_guard.paired_interfaces import asset_graph_pairs, rich_graph_pairs
from legal_skill_guard.paired_interfaces.empirical_channel import graph_record, restore_graph
from legal_skill_guard.paired_interfaces.formal_learning import restore_pair, world_weights
from legal_skill_guard.paired_interfaces.formal_observable import row_loss, complete_replay
from legal_skill_guard.paired_interfaces.native_channel_selection import NativeLoss
from legal_skill_guard.paired_interfaces.observable_transfer import ASSUMPTIONS, RESIDUAL, fit_observable, images, model_record, choose_observable
from legal_skill_guard.paired_interfaces.partial_native_loss import loss_interval, replay_bounds
from legal_skill_guard.paired_interfaces.structural_channel import observations
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

PORTS = BASE/'asset_port_redecode_v2/20afd6a84d91af3a71f16a0ab5d6d850c1f1cda6420edc7c31d14b8b5ca513c6/paired_reads.json'


def run():
    public={s['key']:s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    roles={r['source']:r['role'] for r in read(REGISTRY/'roles.json')}
    refs=read(REGISTRY/'manifest.json')['reviews']
    public_context={}; units={}
    for s in public.values():
        task,mapping=inputs(s);by_id={v['id']:v['public'] for v in s['views']}
        for v in task['views']:
            public_context[s['key'],v['view_id']]={k:by_id[k] for k,opaque in mapping.items() if opaque==v['view_id']}
            units[s['key'],v['view_id']]=v['source_units']
    rows=read(CORPUS)['pairs']+[{'dataset':'OpenExempt',**r} for r in read(PORTS)]
    bindings={str(Path(__file__).relative_to(ROOT)):sha(Path(__file__)),
        **{str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'legal_skill_guard/paired_interfaces').glob('*.py'))}}
    protocol={'name':'observable-rewrite-set-existing-evidence-audit-v1','source_sha256':bindings,
        'original_graph_corpus_sha256':sha(CORPUS),'port_pairs_sha256':sha(PORTS),
        'source_registry_sha256':sha(REGISTRY/'manifest.json'), 'assumptions':list(ASSUMPTIONS),
        'no_native_grading_no_DEV_TEST_no_structure_evaluation_reference':True,
        'different_reader_decoder_versions_never_pooled':True,'new_model_requests':0}
    out=BASE/'revision_20261117/M2_observable_transfer'/digest(protocol)
    immutable_json(out/'protocol.json',protocol)
    for name,expected in bindings.items():
        target=out/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():target.write_bytes((ROOT/name).read_bytes())
        assert sha(target)==expected
    groups=defaultdict(list)
    for r in rows:
        pair=restore_pair(r['pair'])
        assert pair.role in ('development','calibration')
        groups[r['dataset'],pair.reference.schema,pair.reference.context,r['plan'],pair.plan_version].append(r)
    results=[]; selections=defaultdict(dict); reconstruction_violations=0
    for (dataset,schema,context,plan,version),items in sorted(groups.items()):
        pairs=[restore_pair(r['pair']) for r in items]
        d=[p for p in pairs if p.role=='development'];c=[p for p in pairs if p.role=='calibration']
        result={'dataset':dataset,'schema':schema,'context':context,'plan':plan,'version':version,
            'development_mothers':len({p.source_id for p in d}),'calibration_mothers':len({p.source_id for p in c})}
        if not d or not c:
            results.append({**result,'supported':False,'reason':'no disjoint D/C in the same actual version/domain'});continue
        model=fit_observable(d,c)
        result.update(model.diagnostics());immutable_json(out/'models'/(digest([dataset,schema,context,plan,version])+'.json'),model_record(model))
        # Direct reconstruction on C checks intervals against complete traces.
        actual_lo=actual_hi=event_lo=event_hi=0.;by_source=defaultdict(list)
        for pair,event in zip(model.calibration,model.events):
            row=next(r for r in items if r['source']==pair.source_id and restore_pair(r['pair'])==pair)
            pub=public_context[row['source'],row['view']]
            consume=(lambda g:asset_graph_pairs.consumer_signature(g,tuple(pub))) if schema==asset_graph_pairs.scope('Illinois')['schema'] else (lambda g:rich_graph_pairs.consumer_signature(g,dataset,pub))
            loss=NativeLoss(consume)
            actual=[loss_interval(loss,pair.reference,y) for y in observations(pair)]
            actual_interval=[min(v[0] for v in actual),max(v[1] for v in actual)]
            predicted=([[0.,1.]] if event==RESIDUAL else [loss_interval(loss,pair.reference,y) for e in event for y in images(model.edits[e],pair.reference)])
            event_interval=[min(v[0] for v in predicted),max(v[1] for v in predicted)]
            reconstruction_violations += not(event_interval[0]<=actual_interval[0]+1e-12 and event_interval[1]>=actual_interval[1]-1e-12)
            by_source[pair.source_id].append((actual_interval,event_interval))
        for values in by_source.values():
            n=len(by_source)*len(values)
            actual_lo+=sum(v[0][0] for v in values)/n;actual_hi+=sum(v[0][1] for v in values)/n
            event_lo+=sum(v[1][0] for v in values)/n;event_hi+=sum(v[1][1] for v in values)/n
        result['calibration_complete_trace_native_loss']=[actual_lo,actual_hi]
        result['same_trace_reconstruction_native_loss']=[event_lo,event_hi]
        result['same_trace_is_diagnostic_not_independent_validation']=True
        # Primary risk population uses only original pure-R, no weak read/grade.
        reference_records=[];by_graph={}
        for entry in refs:
            if roles[entry['source']]!='reference_only' or public[entry['source']]['dataset']!=dataset:continue
            card=read(ROOT/entry['path']);assert sha(ROOT/entry['path'])==entry['sha256']
            supplied=units[entry['source'],entry['view']];pub=public_context[entry['source'],entry['view']]
            if schema==rich_graph_pairs.SCHEMA:
                if 'graph' not in card:continue  # Old generic OE and new port scopes are distinct.
                tasks=sorted(pub)
                local_context=dataset+':'+digest(tasks)
                (world,_,_),_=rich_graph_pairs.reference_graph(card['graph'],{u['id']:u for u in supplied},local_context)
                consume=lambda g,pub=pub:rich_graph_pairs.consumer_signature(g,dataset,pub)
            else:
                if 'port_record' not in card:continue
                world,_=asset_graph_pairs.reference_world(card,supplied,card['public_regime'])
                consume=lambda g,pub=pub:asset_graph_pairs.consumer_signature(g,tuple(pub))
            if (world.schema,world.context)!=(schema,context):continue
            if world in by_graph and by_graph[world][0]!=digest(pub):
                raise ValueError('Same graph with conflicting public query bundle must not be collapsed')
            by_graph[world]=(digest(pub),NativeLoss(consume))
            reference_records.append({'source':entry['source'],'graph':graph_record(world)})
        if reference_records:
            weights=world_weights(reference_records)
            prediction=model.predict(None,weights,assumptions=ASSUMPTIONS,delta=.05/3,
                loss_for_reference=lambda graph:by_graph[graph][1])
            result['pure_reference_prediction']=prediction
            result['pure_reference_mothers']=len({r['source'] for r in reference_records})
            result['exact_complete_replay_support_on_pure_R']=all(any(p.reference==g for p in pairs) for g in weights)
            selections[dataset,schema,context][plan]=prediction
        else:
            result['pure_reference_prediction']={'supported':False,'reason':'no compatible pure-R in this exact ABI/domain'}
        results.append(result)
        print(json.dumps({'groups_finished':len(results)}),flush=True)
    choices=[]
    for key,predictions in sorted(selections.items()):
        complete=set(predictions)=={'columns','records','local_records'}
        choice=choose_observable(predictions,baseline='columns') if complete else {'supported':False,'risk_informed_ranking':False,'reason':'incomplete candidate family'}
        choices.append({'dataset':key[0],'schema':key[1],'context':key[2],**choice,
            'empirical_upper_risks':{k:v['empirical_interval'][1] for k,v in predictions.items()}})
    summary={'artifact_root':str(out.relative_to(ROOT)),'actual_graph_pairs':117,'actual_port_pairs':18,
        'actual_physical_responses_not_new_trials':135,'groups':len(groups),
        'fitted_groups':sum('prediction_target' in r for r in results),
        'groups_with_multiple_observable_events':sum(r.get('distinct_observable_events',0)>1 for r in results),
        'reconstruction_interval_violations':reconstruction_violations,
        'pure_reference_choices':choices,
        'risk_informed_selections':sum(c['risk_informed_ranking'] for c in choices),
        'confidence_bearing_conditional_prediction_not_unrestricted_guarantee':True,
        'real_independent_structural_transfer_advantage_established':False,
        'new_model_or_teacher_requests':0,'native_grading_opened':False,'goal_complete':False}
    for name,value in bindings.items():assert sha(ROOT/name)==value,name
    immutable_json(out/'group_results.json',results);immutable_json(out/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    return out,summary


if __name__=='__main__':run()
