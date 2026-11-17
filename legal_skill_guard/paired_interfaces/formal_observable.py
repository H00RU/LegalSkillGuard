"""Revised M2 primary selector; historical unrestricted channels are not used.

Only prespecified source-only TRAIN reference worlds enter deployment risk.
No current target true graph/read/label is an input. Frozen legacy snapshots
are explicitly unsupported and require an authorized refit, not silent reuse.
"""
from legal_skill_guard.paired_interfaces.native_channel_selection import NativeLoss
from legal_skill_guard.paired_interfaces.observable_transfer import ASSUMPTIONS, choose_observable, restore_model


def row_loss(dataset, public, fallback):
    if dataset=='OpenExempt' and public is not None:
        from legal_skill_guard.paired_interfaces.asset_graph_pairs import consumer_signature
        return NativeLoss(lambda graph: consumer_signature(graph,tuple(public)))
    if public is not None:
        from legal_skill_guard.paired_interfaces.rich_graph_pairs import consumer_signature
        return NativeLoss(lambda graph: consumer_signature(graph,dataset,public))
    if dataset=='SARA_v2_Binary':
        raise ValueError('SARA reference worlds require their own public query, not the current target name/year')
    return NativeLoss(fallback)


def complete_replay(records, dataset, fallback):
    from collections import defaultdict
    from legal_skill_guard.paired_interfaces.formal_learning import restore_pair
    from legal_skill_guard.paired_interfaces.structural_channel import observations
    from legal_skill_guard.paired_interfaces.partial_native_loss import loss_interval
    by_source = defaultdict(list)
    for row in records:
        pair=restore_pair(row.get('pair',row)); loss=row_loss(dataset,row.get('native_public'),fallback)
        values=[loss_interval(loss,pair.reference,y) for y in observations(pair)]
        by_source[pair.source_id].append([min(v[0] for v in values),max(v[1] for v in values)])
    if not by_source:return {'supported':False,'reason':'no complete traces'}
    interval=[sum(sum(v[k] for v in rows)/len(rows) for rows in by_source.values())/len(by_source) for k in (0,1)]
    return {'supported':True,'empirical_risk_interval':interval,'mother_weighted':True,
            'paired_mothers':len(by_source),'uses_own_TRAIN_public_task_context':True,
            'transfer_proxy_population':'all cached paired TRAIN worlds','channel_model_executed':False}


def select_observable(snapshot, *, dataset, schema, context, arm, consume):
    from legal_skill_guard.paired_interfaces.formal_learning import world_weights
    plans = snapshot['raw_candidate_orders'][dataset]
    if arm=='M2_fixed_interfaces':plans=[p for p in plans if p in ('columns','records')]
    baseline = plans[0]
    refs = [r for r in snapshot['reference_world_groups'] if (r['dataset'],r['schema'],r['context'])==(dataset,schema,context)]
    rows = [r for r in snapshot['fitted_groups'] if (r['dataset'],r['schema'],r['context'])==(dataset,schema,context)]
    if len({r['plan'] for r in rows})!=len(rows) or len(refs)>1:
        raise ValueError('Competing model versions or reference populations')
    by_plan, predictions = {r['plan']:r for r in rows},{}
    loss = NativeLoss(consume)
    for plan in plans:
        model = by_plan.get(plan,{}).get('observable_model')
        if not refs or not model:
            predictions[plan]={'supported':False,'reason':'requires revised frozen observable model and source-only reference population'}
        else:
            from legal_skill_guard.paired_interfaces.empirical_channel import restore_graph
            from legal_skill_guard.skill_evolution.objects import digest
            public_by_graph={}
            by_graph={}
            for r in refs[0]['records']:
                graph=restore_graph(r['graph']);public_digest=digest(r.get('native_public'))
                if graph in public_by_graph and public_by_graph[graph]!=public_digest:
                    raise ValueError('Conflicting public queries for an identical reference graph require distinct task worlds')
                public_by_graph[graph]=public_digest
                by_graph[graph]=row_loss(dataset,r.get('native_public'),consume)
            predictions[plan]=restore_model(model).predict(loss,world_weights(refs[0]['records']),
                assumptions=ASSUMPTIONS,delta=.05/len(plans),loss_for_reference=by_graph.__getitem__)
    result = choose_observable(predictions,baseline=baseline)
    return {**result,'risks':predictions,'primary_method':'observable-rewrite-set-transfer-v1',
        'assumptions':list(ASSUMPTIONS),'costs_used':False,
        'unidentified_unrestricted_selector_executed':False,
        'target_reference_graph_label_or_actual_weak_output_used':False,
        'complete_trace_replay_executed_by_this_arm':False,
        'natural_structure_novelty_or_native_accuracy_not_established_by_selection':True}
