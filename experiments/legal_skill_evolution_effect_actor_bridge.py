"""Install the narrowly scoped actor bridge; replay real observations offline.

The old acquired program and every scored run remain immutable. This produces a
new shared engineering version, not a learned update or a new semantic score.
"""
import ast
from pathlib import Path

from experiments.legal_skill_evolution_refutation_learning import OUT, ROOT, read, sha
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.effect_actor_binding import bind, finish
from legal_skill_guard.skill_evolution.native import source_spans
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.scoped_grammar import material_public
from legal_skill_guard.skill_evolution.source_python import validate, execute
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units


def revise(bundle):
    old = bundle['program']
    before = """        actor_choice=_sr_get(answers,base+'actor','disposal_retention_actor_role',unresolved,True)
        actor=None
        if actor_choice is not None:
            actor=_sr_actor(actor_choice,raw,unresolved,base+'actor')"""
    after = """        actors=inputs['effect_actor_bindings'].get(base,{})
        disposal_actor=actors.get('disposal_obligation')
        retention_effect='retention_prohibition' if role=='operative_retention_prohibition' else 'retention_permission'
        retention_actor=actors.get(retention_effect)
        if role in ('operative_disposal','operative_disposal_and_retention_permission') and disposal_actor is None:
            unresolved.append('The disposal actor remains unresolved for '+base+'role.')
        if role in ('operative_retention_permission','operative_retention_prohibition','operative_disposal_and_retention_permission') and retention_actor is None:
            unresolved.append('The retention actor remains unresolved for '+base+'role.')"""
    if old.count(before) != 1:
        raise ValueError('The actual acquired actor interface has changed')
    new = old.replace(before, after)
    edits = {
        'if needs_disposal and actor is not None and dinfo is not None:':
            'if needs_disposal and disposal_actor is not None and dinfo is not None:',
        '_sr_exceptions(qual,actor,rinfo)': '_sr_exceptions(qual,retention_actor,rinfo)',
        "['disposal_obligation',actor,action,trigger,ex]":
            "['disposal_obligation',disposal_actor,action,trigger,ex]",
        "and actor is not None and rinfo is not None:":
            "and retention_actor is not None and rinfo is not None:",
        "['retention_permission',actor,rinfo": "['retention_permission',retention_actor,rinfo",
        "['retention_prohibition',actor,rinfo": "['retention_prohibition',retention_actor,rinfo",
        'if cond is not None and rinfo is not None:':
            'if cond is not None and rinfo is not None and actor is not None:',
    }
    for before, after in edits.items():
        if before not in new:
            raise ValueError('Expected actual consumer binding absent: ' + before)
        new = new.replace(before, after)
    tree = ast.parse(new)
    for fn in tree.body:
        if fn.name == '_sr_queries':
            # The old shared actor operation is removed from this new version.
            returned = fn.body[-1]
            assert isinstance(returned, ast.Return)
            returned.value = ast.parse(
                "[q for q in out if q['operation']!='disposal_retention_actor_role']",
                mode='eval').body
    new = ast.unparse(ast.fix_missing_locations(tree))
    validate(new)
    return {**bundle, 'program': new,
            'operations': [o for o in bundle['operations']
                           if o['name'] != 'disposal_retention_actor_role']}


def run():
    old = read(ROOT/'artifacts/legal_skill_evolution_residual_reader_20261113/seed.json')
    bundle = revise(old)
    witness = read(OUT/'representation_audit/mixed_effect_actor.json')
    source = next(s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')
                  if s['key'] == witness['original_TRAIN_source'])
    pub = source['views'][0]['public']
    units, _ = execution_source_units(pub['source_text'], source_spans(material_public(pub)))
    queries = execute(bundle['program'], {'phase': 'plan', 'source_text': pub['source_text'],
                                         'source_spans': units, 'semantic_answers': []})['queries']
    qid = next(q['id'] for q in queries if q['id'].endswith('_role') and q['unit_ids'][-1] == 58)
    actual = read(OUT/'direct_actor_diagnostic/result.json')['value']
    observations = [
        {'query_id': qid, 'effect': 'disposal_obligation', 'unit_id': 58,
         'phrase': actual['return_actor_phrase']},
        {'query_id': qid, 'effect': 'retention_permission', 'unit_id': 58,
         'phrase': actual['maintain_copy_actor_phrase']},
    ]
    bindings = bind(bundle['spec'], queries, units, observations)
    # No unknown role/action/trigger is filled from the actor observations.
    output = finish(bundle, pub['source_text'], units, [], observations)
    assert output['complete'] is False
    assert not any(s['term'][0] in ('disposal_obligation', 'retention_permission',
                                   'retention_prohibition') for s in output['statements'])
    result = {'source': source['key'], 'real_actor_observations': observations,
              'typed_effect_actor_bindings': bindings,
              'missing_other_semantics_output': output,
              'new_model_calls': 0, 'no_missing_legal_semantics_filled': True,
              'old_bundle_sha256': digest(old), 'revised_bundle_sha256': digest(bundle),
              'shared_engineering_revision_not_learned_update': True,
              'full_source_semantic_execution_still_unvalidated': True,
              'no_native_rescoring_or_core_success_claim': True, 'goal_complete': False,
              'code_sha256': {str(p.relative_to(ROOT)): sha(p) for p in [
                  Path(__file__).resolve(), ROOT/'legal_skill_guard/skill_evolution/effect_actor_binding.py']}}
    immutable_json(OUT/'effect_actor_bridge/revised_bundle.json', bundle)
    immutable_json(OUT/'effect_actor_bridge/result.json', result)
    print({'source': source['key'], 'actor_bindings': bindings,
           'missing_semantics_preserved': True, 'new_model_calls': 0})


if __name__ == '__main__':
    run()
