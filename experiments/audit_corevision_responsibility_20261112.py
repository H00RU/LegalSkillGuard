"""Zero-model replay of code contexts from the actual rejected TRAIN package."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from legal_skill_guard.skill_evolution.objects import Library, Skill
from legal_skill_guard.skill_evolution.patterns import learn, relation_context
from legal_skill_guard.skill_evolution.responsibilities import context, invocations, read_cost, source_relation
from legal_skill_guard.skill_evolution.revisions import VersionTable


def main():
    root = Path(__file__).resolve().parents[1]
    report = root / 'reports/legal_skill_evolution_run_20261111'
    folder = report / 'source_rule_evidence/legal_skill_evolution_source_rule_check_20261112'
    old = Library.load(folder / 'FreeEvolution/B2.json')
    candidate = json.loads((folder / 'FreeEvolution/B3_candidates/0.json').read_text())
    new = {r['skill_id']: Skill.from_dict(r['new']) for r in candidate['revisions']}
    sources = {s['key']: s for s in json.loads((report / 'contract_original_TRAIN_public.json').read_text())}
    producer, consumer, field = 'nda_representative_exception_applicability', 'nda_disclosure_permission_consequence', 'exception_applies'
    p, c = old.skills[producer], old.skills[consumer]
    export = candidate['table']
    table = VersionTable(tuple(export['revision_hashes']), tuple(export['trigger']), tuple(export['history']))
    observations = []
    for cell in export['mixed_version_table']:
        table.observe(cell['mask'], cell['source'], cell['native_parent_grade'], cell['trace'])
        if cell['mask'] == 3:
            for unit in invocations(cell['trace'], producer, field, consumer):
                observations.append(context(p, c, new[producer], new[consumer], field, unit, sources[unit['source']]))
    assert candidate['selected_mask'] is None
    accepted = {}
    for generic in (False, True):
        library = Library(skills=deepcopy(new))
        accepted[str(generic)] = learn(library, old, candidate['revisions'], table, candidate['selected_mask'],
                                      generic=generic, source_records=sources)
        assert library.revision_patterns == []
    seed = Library.load(report / 'contract_TRAIN_evidence/legal_skill_evolution_contract_acquisition_20261112/Full/B1.json')
    bindings = {key: source_relation(seed.skills[producer], seed.skills[consumer], field, source)
                for key, source in sources.items()}
    known = sum(x['status'] == 'known' for x in bindings.values())
    assert known == 1
    current = {x['evidence']['view']: x for x in observations if x['evidence']['source'].startswith('ContractNLI:354')}
    assert current['nda-5']['fields']['consumer_after_false_output'] == {'answer': 'NotMentioned'}
    assert current['nda-7']['fields']['consumer_after_false_output'] == {'answer': 'Contradiction'}
    assert current['nda-5']['fields'] != current['nda-7']['fields']
    code = ['legal_skill_guard/skill_evolution/' + name + '.py' for name in
            ('responsibilities', 'patterns', 'revisions', 'proposal_batch', 'study')]
    result = {
        'captured_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Actual rejected TRAIN response and cached executions only; no new model response or legal gold.',
        'code_sha256': {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in code},
        'coarse_role_context_unchanged_despite_code_effect_change': relation_context(p, c, field) == relation_context(new[producer], new[consumer], field),
        'actual_code_observations': observations,
        'seed_provenance_literal_source_bindings': bindings,
        'literal_relation_coverage': {'known_parent_materials': known, 'checked_parent_materials': len(bindings),
            'interpretation': 'Coverage of these literal seed-quote bindings, not overall legal or method coverage.'},
        'read_consumption_footprints_by_mask': {str(mask): read_cost(table, mask) for mask in range(4)},
        'original_selected_mask': candidate['selected_mask'],
        'real_patterns_created_by_Full_or_Generic': accepted,
        'synthetic_fixture_grades_are_not_native_results': True,
        'new_physical_requests': {'executor': 0, 'teacher': 0},
        'cumulative_physical_requests': {'executor': 9218, 'teacher': 162}, 'pending': 0,
        'independent_Lift_evidence': False, 'independent_CoRev_evidence': False,
        'goal_complete': False,
        'limitations': ['Finite code effects under fixed observed bindings are not legal correctness labels.',
            'Only uniquely bound literal express-exception references are recognized; unsupported syntax stays unknown.',
            'No new accepted co-revision or real cross-parent pattern use has been demonstrated.']}
    destination = report / 'source_rule_responsibility_regression.json'
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'actual_code_contexts': len(observations), 'known_literal_bindings': known,
                      'real_patterns_created': 0, 'new_calls': 0, 'path': str(destination)}))


if __name__ == '__main__':
    main()
