"""Two-gate M2 decision from fixed real records and computable F examples.

No new model calls, labels or benchmark cases. Constructed graph channels are
mathematical witnesses, not observations from the frozen executor. The method
is not revised here to make a gate pass.
"""
from collections import defaultdict
import json
from pathlib import Path

from experiments.two_method_graph_corpus import BASE,ROOT,read,sha
from legal_skill_guard.paired_interfaces.empirical_channel import indexed
from legal_skill_guard.paired_interfaces.formal_learning import pair_record
from legal_skill_guard.paired_interfaces.formal_observable import complete_replay
from legal_skill_guard.paired_interfaces.native_channel_selection import NativeLoss,choose_risks
from legal_skill_guard.paired_interfaces.observable_transfer import ASSUMPTIONS,fit_observable,choose_observable,images
from legal_skill_guard.paired_interfaces.partial_native_loss import loss_interval
from legal_skill_guard.paired_interfaces.rich_graph_pairs import SCHEMA,consumer_signature
from legal_skill_guard.paired_interfaces.structural_channel import Fact,Graph,Pair,generalized_edit
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest

TASK='Ordinary Course Covenant includes carve-out for Pandemic responses-Answer (Y/N)'
REAL=BASE/'revision_20261117/M2_observable_transfer/e56a2be8ff0d877968e2b19cc5837b2593ba9734146308eb9f49f02d9636acce'


class M2EvidenceGateError(ValueError):
    pass


def assert_dispatch_gates(path):
    gate=read(path)
    if not (gate.get('gate_1_passed') is True and gate.get('gate_2_passed') is True
            and gate.get('fixed_finite_real_validation_dispatch_allowed') is True):
        raise M2EvidenceGateError('M2 expansion stopped: both user evidence gates must pass before real validation or a formal matrix')
    return gate


def relation(predicate,args):
    return Fact('relation:'+json.dumps({'predicate':predicate,'value':None},sort_keys=True),tuple(args))


def world(exceptions):
    """An explicit input to the project's unchanged MAUD F, not a new case."""
    nodes=[('c','effect'),('a','person'),('b','person')]+[(f'e{i}','exception') for i in range(exceptions)]
    facts={Fact('scope_complete',('True',))}
    for identity,kind in nodes:
        concept='ordinary_course_covenant' if identity=='c' else 'covid_19' if kind=='exception' else 'unspecified'
        facts.update([Fact('present',(identity,)),Fact('concept:'+concept,(identity,)),
            Fact('literal_name:'+json.dumps(identity),(identity,))])
    facts.add(relation('actor',['c','a']))
    facts.update(relation('exception_for',[f'e{i}','c']) for i in range(exceptions))
    return Graph(tuple(sorted(nodes)),frozenset(facts),SCHEMA,'MAUD:'+digest([TASK]))


def drop_one_attachment(graph):
    return Graph(graph.nodes,graph.facts-{relation('exception_for',['e0','c'])},graph.schema,graph.context)


def wrong_actor(graph):
    return Graph(graph.nodes,(graph.facts-{relation('actor',['c','a'])})|{relation('actor',['c','b'])},graph.schema,graph.context)


def consume(graph):
    return consumer_signature(graph,'MAUD',{TASK:{}})


def full_trace_generalized_transfer(pairs,target,loss):
    """Strong diagnostic: transport each whole joint difference, no field noise.

    It adopts the SAME type-equivariant rewrite-transfer assumption as M2.
    It is stronger than replaying only historical native outcomes; agreement
    matters when assessing whether an example establishes a distinct method.
    """
    by_source=defaultdict(list)
    for pair in pairs:
        observed=pair.observed
        edit=indexed(generalized_edit(pair.reference,
            pair.reference.facts-observed.facts,observed.facts-pair.reference.facts))
        values=[loss_interval(loss,target,y) for y in images(edit,target)]
        if not values:values=[[0.,1.]]
        by_source[pair.source_id].append([min(v[0] for v in values),max(v[1] for v in values)])
    return [sum(sum(v[k] for v in rows)/len(rows) for rows in by_source.values())/len(by_source) for k in (0,1)]


def compute_example(n=64):
    source,target=world(2),world(1);loss=NativeLoss(consume)
    pairs={};models={};predictions={};empirical_replay={};accuracy={};generalized={}
    for plan,transform in [('columns',drop_one_attachment),('records',wrong_actor)]:
        dev=[Pair('constructed:dev',source,transform(source),'constructed:'+plan,'development','mathematical-only')]
        cal=[Pair('constructed:cal'+str(i),source,transform(source),'constructed:'+plan,'calibration','mathematical-only') for i in range(n)]
        pairs[plan]=dev+cal;models[plan]=fit_observable(dev,cal)
        predictions[plan]=models[plan].predict(loss,{target:1.},assumptions=ASSUMPTIONS,delta=.05/2)
        empirical_replay[plan]=complete_replay([pair_record(p) for p in dev+cal],'fixture',consume)
        accuracy[plan]=1.-empirical_replay[plan]['empirical_risk_interval'][1]
        generalized[plan]=full_trace_generalized_transfer(dev+cal,target,loss)
    m2=choose_observable(predictions,baseline='columns')
    replay=choose_risks(empirical_replay,baseline='columns',costs={p:0. for p in pairs},replay=True)
    ordinary=max(['columns','records'],key=lambda p:(accuracy[p],-['columns','records'].index(p)))
    # Two stationary-in-version, structure-dependent channels agree on EVERY
    # available paired source graph. They disagree only at the new structure.
    stable={'columns':drop_one_attachment,'records':wrong_actor}
    def changed_columns(graph):
        return drop_one_attachment(graph) if len([n for n,k in graph.nodes if k=='exception'])>=2 else graph
    def changed_records(graph):
        return wrong_actor(graph) if len([n for n,k in graph.nodes if k=='exception'])>=2 else drop_one_attachment(graph)
    switching={'columns':changed_columns,'records':changed_records}
    evidence_equal=all(stable[p](pair.reference)==switching[p](pair.reference)
        for p,rows in pairs.items() for pair in rows)
    target_losses={name:{p:loss_interval(loss,target,channel[p](target)) for p in pairs}
                   for name,channel in [('stable_rewrites',stable),('structure_dependent_rewrites',switching)]}
    unrestricted={p:[min(v[p][0] for v in target_losses.values()),max(v[p][1] for v in target_losses.values())] for p in pairs}
    return {'actual_frozen_MAUD_consumer_used':True,'source_exception_witnesses':2,'target_exception_witnesses':1,
        'constructed_calibration_sources':n,'new_real_sources_or_requests':0,
        'source_native_accuracy':accuracy,
        'full_paired_trace_historical_proxy':{p:v['empirical_risk_interval'] for p,v in empirical_replay.items()},
        'ordinary_accuracy_selected_plan':ordinary,'full_paired_trace_selected_plan':replay['plan'],
        'conditional_M2_empirical_risks':{p:v['empirical_interval'] for p,v in predictions.items()},
        'conditional_M2_confidence_intervals':{p:v['interval'] for p,v in predictions.items()},
        'conditional_M2_selected_plan':m2['plan'],'conditional_M2_separation':m2.get('certified_separation',False),
        'full_joint_trace_with_same_transfer_assumption':generalized,
        'current_example_M2_equals_generalized_whole_trace_transport':all(
            predictions[p]['empirical_interval']==generalized[p] for p in pairs),
        'counterexample_all_calibration_graph_pairs_observationally_identical':evidence_equal,
        'calibration_observable_residual_mass':{p:m.diagnostics()['observable_residual_mass'] for p,m in models.items()},
        'two_observationally_equivalent_channels_target_risks':target_losses,
        'target_risks_not_identified_without_additional_structure_transfer_restriction':unrestricted,
        'same_schema_and_reader_version_in_both_channels':True,
        'hypothetical_channels_not_claimed_to_be_the_frozen_Qwen_executor':True,
        'conditional_example_not_real_mechanism_or_distinct_contribution_evidence':True}


def evaluate(real,example):
    choices=real['pure_reference_choices']
    informative=sum(c.get('risk_informed_ranking',False) for c in choices)
    all_one=sum(bool(c.get('upper_risks')) and all(abs(v-1.)<1e-12 for v in c['upper_risks'].values()) for c in choices)
    unresolved_extrapolation=example['counterexample_all_calibration_graph_pairs_observationally_identical'] and all(
        v==[0.,1.] for v in example['target_risks_not_identified_without_additional_structure_transfer_restriction'].values())
    gate1=informative>0 and all_one<len(choices) and not unresolved_extrapolation
    # A changed selector or a constructed risk difference is insufficient.
    functional_difference=(example['conditional_M2_selected_plan']!=example['ordinary_accuracy_selected_plan']
        and example['conditional_M2_selected_plan']!=example['full_paired_trace_selected_plan'])
    # Do not require a real contribution BEFORE dispatching validation. This
    # gate asks for a defensible offline example/assumption contract; today's
    # example fails it on the strong replay comparison and identifiability.
    gate2=(functional_difference and not example['current_example_M2_equals_generalized_whole_trace_transport']
           and not unresolved_extrapolation)
    return {'gate_1_passed':gate1,'gate_2_passed':gate2,
        'real_candidate_families':len(choices),'real_families_all_upper_bounds_one':all_one,
        'real_risk_informed_selections':informative,
        'observable_calibration_counts_do_not_identify_unseen_structure_channel':unresolved_extrapolation,
        'conditional_constructive_example_computed':True,
        'conditional_example_differs_from_historical_proxy_and_accuracy':functional_difference,
        'strong_joint_trace_comparator_matches_current_example':example['current_example_M2_equals_generalized_whole_trace_transport'],
        'no_latent_unknown_probability_cap_or_cost_tie_used':True,
        'fixed_finite_real_validation_dispatch_allowed':gate1 and gate2,
        'M2_expansion_status':'gates_passed_only_not_a_contribution' if gate1 and gate2 else 'stopped_by_user_evidence_gate',
        'no_claim_all_structural_transfer_methods_are_impossible':True,
        'goal_complete':False}


def run():
    real=read(REAL/'summary.json');example=compute_example();decision=evaluate(real,example)
    assert real['actual_graph_pairs']==117 and real['actual_port_pairs']==18
    protocol={'name':'M2-two-user-gates-existing-evidence-v1',
        'existing_record_root':str(REAL.relative_to(ROOT)),'existing_summary_sha256':sha(REAL/'summary.json'),
        'existing_protocol_sha256':sha(REAL/'protocol.json'),
        'M2_algorithm_not_revised_to_pass_gates':True,'new_model_or_teacher_requests':0,
        'no_grading_or_DEV_TEST_or_structural_reference_access':True,
        'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__).resolve(),
            *sorted((ROOT/'legal_skill_guard/paired_interfaces').glob('*.py'))]}}
    out=BASE/'M2_two_gate_decision_20261117'/digest(protocol)
    immutable_json(out/'protocol.json',protocol);immutable_json(out/'computable_example.json',example)
    immutable_json(out/'decision.json',decision)
    for name,value in protocol['source_sha256'].items():
        target=out/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():target.write_bytes((ROOT/name).read_bytes())
        assert sha(target)==value
    print(json.dumps({'artifact_root':str(out.relative_to(ROOT)),**decision},ensure_ascii=False),flush=True)
    return out,decision


if __name__=='__main__':run()
