"""Replay the actual acquired G with joint source evidence, no model requests."""
from copy import deepcopy

from experiments import legal_skill_evolution_source_gap_acquisition as e
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.source_provenance_projection import preserve_joint_support


def run():
    protocol, _, public = e.setup()
    grading = e.read(e.previous.prior.prior.GRADING)
    arm = 'ConstraintAcquire'
    before = e.read(e.OUT / 'certified_revision/library.json')
    after = deepcopy(before)
    after['language'], after['renderers'], changes = preserve_joint_support(before['language'], before['renderers'])
    assert after['source_program'] == before['source_program']
    assert after['spec'] == before['spec']
    assert after['selected_rule_ids'] == before['selected_rule_ids']
    for old, new in zip(before['language']['rules'], after['language']['rules']):
        assert old['body'] == new['body'] and old['cost'] == new['cost'] and old['id'] == new['id']
    dest = e.OUT / 'unbound_provenance_replay'
    immutable_json(dest / 'library.json', after)
    rows = []
    for key in protocol['acquisition_sources']:
        old = e.read(e.OUT / 'unbound_pure_preview' / arm / e.name_for(key))
        saved = dest / 'execution' / e.name_for(key)
        if saved.exists():
            new = e.read(saved)
            assert new['execution']['library_sha256'] == digest(after)
            assert new['execution']['observation_sha256'] == old['observation']['visible_inputs_sha256']
        else:
            new = e.previous.prior.prior.evaluate_source(after, old['observation'], public[key], grading[key])
        original = old['actual']
        original_terms = {digest(s['term']) for s in original['execution']['source_output']['statements']}
        new_terms = {digest(s['term']) for s in new['execution']['source_output']['statements']}
        assert original_terms == new_terms
        old_views = original['feedback']['views']; new_views = new['feedback']['views']
        for a, b in zip(old_views, new_views):
            assert a['score'] == b['score'] and a['core_executed'] == b['core_executed']
            assert a['execution']['value']['answer'] == b['execution']['value']['answer']
        immutable_json(dest / 'execution' / e.name_for(key), new)
        rows.append({'source': key, 'identical_legal_term_set': True,
            'native_correct_and_core_coverage_unchanged': True,
            'native_correct': sum(bool(v['score'] and v['score']['correct']) for v in new_views),
            'before_statement_count': len(original['execution']['source_output']['statements']),
            'after_statement_count': len(new['execution']['source_output']['statements'])})
    proof = {'new_model_requests': 0, 'original_outputs_preserved': True,
        'no_semantic_condition_acquired_or_changed': True, 'not_U_learning': True,
        'not_a_full_source_semantics_certificate': True, 'changes': changes, 'rows': rows,
        'native_correct': sum(r['native_correct'] for r in rows)}
    immutable_json(dest / 'proof.json', proof)
    print(e.json.dumps({'native_correct': proof['native_correct'], 'sources': len(rows),
        'provenance_coordinates_repaired': len(changes), 'new_model_requests': 0}), flush=True)


if __name__ == '__main__':
    run()
