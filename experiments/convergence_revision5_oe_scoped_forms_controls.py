"""Score the retrospective literal noun/ownership control on the locked PA TRAIN comparison."""

import json
from pathlib import Path
import re
from statistics import mean

from experiments.convergence_pilot_b0 import HANDOFF, ROOT, read, sha
from experiments.convergence_revision5_oe_scoped_forms import PORTS, FIXED, FORMS, RELATION, answers
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


# Corpus-scope literal comparator defined after seeing the TRAIN asset descriptions.
# Unmatched descriptions retain all possible forms.
OBJECT = re.compile(r'\b(?:bowl|dishwasher|router|blender|booster seat|ice maker|range|rifle)\b', re.I)
APPAREL = re.compile(r'\b(?:dress shirt|windbreaker|vest)\b', re.I)
OUTSIDE = re.compile(r'\b(?:primary home)\b', re.I)


def literal_ports(description, title):
    candidates = tuple(form for form, pattern in (
        ('movable_nonapparel', OBJECT), ('wearing_apparel', APPAREL), ('out_of_scope', OUTSIDE),
    ) if pattern.search(description))
    if len(candidates) != 1:
        return dict.fromkeys(PORTS)
    movable, apparel = FORMS[candidates[0]]
    return dict(zip(PORTS, (title if movable else False, movable, apparel), strict=True))


def run():
    current = read(HANDOFF / 'revision5_OE_scoped_forms_current.json')
    stage = ROOT / current['artifact_root']
    binding = read(stage / 'binding.json')
    terminal = read(stage / 'terminal.json')
    assert stage.name == digest(binding) and binding['partition'] == 'TRAIN'
    assert current['status'] == terminal['status'] == 'settled_OE_scoped_form_relation_TRAIN'
    assert sha(stage / 'predictions.json') == terminal['predictions_sha256']
    assert sha(stage / 'scores.json') == terminal['scores_sha256']
    cases = read(stage / 'cases.json')
    assert binding['cases_sha256'] == digest(cases)
    output = stage / 'literal_noun_control'
    immutable_json(output / 'binding.json', {'comparison_binding': stage.name, 'partition': 'TRAIN',
        'reader': 'retrospective explicit noun phrases plus the same literal title evidence and unchanged F',
        'runner_sha256': sha(Path(__file__)), 'observed_native_scores_used_to_choose_nouns': False})
    predicted, count, matched = [], 0, 0
    for case in cases:
        payload = {}
        for slot, asset in case['public']['inventory'].items():
            payload[slot] = literal_ports(asset['description'], asset['filing_interest_established'])
            count += 1
            matched += list(payload[slot].values()) == case['truth'][slot]
        result = answers(case, FIXED, {'finish_reason': 'stop', 'content': json.dumps(payload)},
                         binding['proof']['residuals'][case['family']])
        predicted.append({'source': case['source'], 'family': case['family'],
                          'prediction': result['raw'], 'full_source_port_agreement': payload})
    immutable_json(output / 'predictions.json', predicted)
    grade = ROOT / binding['grade']
    assert sha(grade) == binding['grade_sha256']
    grades = read(grade)
    results = []
    for row, case, paid in zip(predicted, cases, read(stage / 'scores.json'), strict=True):
        family, source = row['family'], row['source']
        assert (source, family) == (case['source'], case['family']) == (paid['source'], paid['family'])
        score = grade_view('OpenExempt', case['native'], grades[source][family], row['prediction'])['grade']
        assert score is not None
        results.append({**paid, 'literal_native_f1': score})
    immutable_json(output / 'scores.json', results)
    effects, direct = {}, {}
    for family in ('EC', 'EV'):
        subset = [r for r in results if r['family'] == family]
        direct[family] = mean(r['literal_native_f1'] for r in subset)
        def units(key):
            return [{'source': r['source'], 'view': r['family'], 'grade': r[key]} for r in subset]
        effects[family] = paired_source_effect(units(FIXED+'_audited'), units(RELATION+'_audited'))
    receipt = {'legacy_training_views': len(cases), 'assets': count, 'literal_port_tuple_matches': matched,
               'literal_official_mean_f1': direct, 'relation_vs_fixed_audited_paired_effect': effects,
               'new_requests': 0, 'labels_used_only_after_prediction_seal': True,
               'runner_sha256': sha(Path(__file__)),
               'predictions_sha256': sha(output / 'predictions.json'), 'scores_sha256': sha(output / 'scores.json')}
    immutable_json(output / 'terminal.json', receipt)
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    run()
