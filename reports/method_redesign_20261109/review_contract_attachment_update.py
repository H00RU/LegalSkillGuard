"""Source-only interpretation and no-selection ablation; no further learning."""
import hashlib
import json
from pathlib import Path

from experiments.rr_v2_contract_attachment_update import ROOT, STAGE, read, snapshot
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.contract_attachment_update import assess, apply, production_code


def main():
    before = snapshot()
    seal = read(STAGE/'training_seal.json')
    state = read(STAGE/'current_update_state.json')
    raw = read(STAGE/'minimum_attachment_learned.json')
    reuse = read(STAGE/'frozen_source_only_reuse.json')
    # Post-hoc mechanism isolation using actual acquired productions. This is
    # not independent acquisition or a retroactive reduction in paid cost.
    full_bank_code = production_code(raw['value']['productions'])
    selected = state['arms']['minimum_attachment']['update']
    full_training = assess(full_bank_code, seal['documents'], seal['feedback'])
    assert full_training == selected['training']
    replay = []
    for row in reuse['results']:
        all_productions = apply(full_bank_code, row['document'], row['initial_graph_entry']['value'])
        actual = row['arms']['minimum_attachment']
        assert all(all_productions[k] == actual[k] for k in all_productions)
        assert all(x['graph'] == row['initial_graph_entry']['value'] for x in row['arms'].values())
        replay.append({'ordinal':row['ordinal'], 'attachments_each_arm':0,'source_graph_changed':False,
                       'full_bank_equals_selected':True,'new_native_predictions_or_labels':0})
    rows = {r['ordinal']:r for r in reuse['results']}
    def rule(ordinal, rid):
        return next(r for r in rows[ordinal]['initial_graph_entry']['value']['rules'] if r['id']==rid)
    checks = [
        {'ordinal':109,'status':'no_update_activation; supported_permission_heads_with_coarse_conditions',
         'actual_claims':[rule(109,'rule-1'),rule(109,'rule-2')],
         'interpretation':'The quoted source permits disclosure only to need-to-know employees/contractors under written confidentiality agreements. Permission heads have source support. Detailed qualifications survive in quotes, not as executed event predicates; no complete compiler correctness claim.'},
        {'ordinal':110,'status':'unresolved_false_permission_from_remedies',
         'actual_claims':[rule(110,'rule-1')],
         'interpretation':'The actual support states disclosure/use would be a breach and describes compensation/specific-performance remedies. It does not grant disclosure permission. Both updates leave the unsupported permission unchanged; no new native hypothesis label is assigned.'},
        {'ordinal':112,'status':'unresolved_negated_preclusion_scope',
         'actual_claims':[rule(112,'rule-1')],
         'interpretation':'The source says the Recipient shall not be precluded from disclosing information in the listed categories. The initial prohibition head reverses the scope of not over precluded. Neither learned update activates on this construction. Do not infer a whole-contract label or silently repair the output.'},
        {'ordinal':113,'status':'unresolved_source_object_and_support_ownership',
         'actual_claims':[rule(113,'rule-4'),rule(113,'rule-5'),rule(113,'rule-6')],
         'interpretation':'Clauses4(b-d) concern the existence of the Agreement/related discussions, whereas4(a) concerns Confidential Information. The initial compiler appends4(a) as context and emits additional share permissions without a represented information-object distinction. The existing4(a) permission can support some queries; this finding is not a claim that all native answers are wrong. No update activates.'}]
    out = {'comparison_frozen_before_source_reuse':True,'source_only_original_TRAIN_mothers':[109,110,112,113],
           'not_new_sources_native_pairs_questions_or_labels':True,'source_reuse':replay,'source_semantic_findings':checks,
           'post_hoc_no_selection_ablation':{'all_actual_productions_kept':len(raw['value']['productions'])==len(selected['productions']),
               'full_bank_code_equals_selected_code':full_bank_code==selected['code'],
               'TRAIN_and_fixed_source_reuse_outputs_equal':True,'new_model_calls':0,
               'scope':'Isolates selector only; does not refute acquisition from ordinary expressibility or erase measured acquisition cost.'},
           'first_contribution_established':False,'second_contribution_started':False,'goal_complete':False,
           'decision':'Stop expanding minimum-subset selection/local regex attachment as a contribution. The selector has no observed independent role, free repair fixes the same visible errors, and neither update transfers to the pre-fixed source constructions. Preserve the single-pair latency/token signal without claiming general cost advantage. No DEV/main training/extra calls are justified to rescue this candidate.',
           'research_adjustment':'Retain actual learned programs and common execution components; withdraw the assumption that adding constrained patch selection establishes a new legal learning contribution. Before another model experiment, a method must learn/combine semantic operators rather than memorize two clause constructions, and its same-information control must share the compact interface. This is a concrete design gap, not a requirement for universally correct parsing or a new dataset.',
           'primary_sources':[
             {'work':'RuleChef','url':'https://github.com/KRLabsOrg/rulechef/blob/80ff36bd508f9371b3d21dce48d4f1afbe52e3a3/rulechef/learner.py#L569',
              'verified_relevance':'Already learns regex/Python rules and applies failure-driven updates with admission checks; generic patching is not a difference.'},
             {'work':'SG-DT/NormBench','url':'https://github.com/AlexJJJChen/NormBench/blob/bd56aff7eb9518db02b10e189576331f271564cc/benchmark/article2unit2structure/prompts/stage1_major_premise_extraction.md#L656',
              'verified_relevance':'Existing core-predicate/condition/effect decomposition and empty effects for references were common hints to both arms, not our contribution.'},
             {'work':'REFAZER','url':'https://arxiv.org/abs/1608.09000',
              'verified_relevance':'Learns reusable syntactic transformations from examples using a DSL and ranking. Our finite selector is not a new general program-repair principle.'},
             {'work':'CounterExample Guided Neural Synthesis','url':'https://arxiv.org/abs/2001.09245',
              'verified_relevance':'Formal constraints can guide neural synthesis. Our two natural-language source corrections are not a formal universal semantic oracle.'},
             {'work':'Wang/Titov/Lapata2019','url':'https://aclanthology.org/D19-1391/',
              'verified_relevance':'Structured latent alignments/abstract programs are a relevant tool, not evidence that our current regex patch learner acquires compositional semantic operators.'}],
           'no_native_DEV_or_TEST_scoring':True,'ledger_unchanged':True}
    assert before == snapshot()
    immutable_json(STAGE/'source_semantic_review_and_selector_ablation.json',out)
    immutable_json(ROOT/'reports/method_redesign_20261109/contract_attachment_update_review.json',out)
    print(json.dumps({'reviewed_original_mothers':4,'both_updates_activated_mothers':0,'no_selection_ablation_equal':True,'goal_complete':False}))


if __name__ == '__main__':
    main()
