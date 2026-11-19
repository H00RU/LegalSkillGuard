"""Replay object-specific ContractNLI disclosure evidence on the original TRAIN reads."""

from collections import Counter
from itertools import product
import json
from pathlib import Path
import re
import sqlite3
from statistics import mean

from experiments.convergence_formal_b1_observe import POINTER as FIRST, load_roster
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_formal_train_fit import EXTERNAL_ARM, ORDINARY, pointer as fit_pointer
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_cni_linked_evidence import DATASET, span_inventory
from experiments.convergence_revision5_m2_cni_disposition_retention import verify_prediction
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


HOME = BASE / 'revision5_CNI_disclosure_objects_20261119'
TASK = 'nda-10'
ENTAILMENT = 'Entailment'
OBJECT = re.compile(r'\b(?:fact|existence|discussions?|negotiations?)\b', re.I)
BAR = re.compile(r'\b(?:shall|will)\b[^.!?]{0,150}\bnot\b[^.!?]{0,100}'
                 r'\b(?:disclos\w*|advertis\w*|announc\w*|publish\w*)\b', re.I)

# Each record binds explicit source passages, not annotation coordinates.
# The linked B1 restriction is separate from the definition listing discussions.
# The three B8 actors have separate existence restrictions with distinct exhibits.
EXPLICIT = {(3, 0): (27,), (4, 0): (19,), (5, 1): (22,), (6, 1): (57,),
            (8, 1): (55, 58, 60), (8, 2): (37,)}
RESTRICTION_CUES = {
    (3, 0): 'neither party hereto shall in any way or in any form disclose',
    (4, 0): 'will not disclose to any person or entity',
    (5, 1): 'shall not be disclosed without written approval',
    (6, 1): 'agrees to keep the existence and nature of this agreement confidential',
    (8, 1): 'shall not disclose the existence of this agreement',
    (8, 2): 'it shall not, without the prior written consent',
}
DECOY = (3, 1)
LINKED = (1, 0)
MODES = ('original', 'explicit_object_check', 'source_scope_check')
SENSITIVITY = {
    (2, 2): (44, 'about the nature of arrangement entered', 'nature_of_arrangement'),
    (5, 0): (55, 'the content, nature or extent of the discussions', 'terms_and_content_of_discussions'),
    (5, 2): (9, 'prohibited from disclosing confidential and proprietary information', 'generic_confidentiality'),
}


def clean(span):
    return ' '.join(span.split())


def source_rule(position, spans):
    """Return reviewed proof spans for the exact scope, or leave it unresolved."""
    if position == LINKED:
        definition, negotiations, rule = (clean(spans[i]) for i in (13, 16, 48))
        assert 'Confidential Information' in definition and 'means' in definition
        assert 'existence and content of the discussions and negotiations' in negotiations
        assert BAR.search(rule) and 'Confidential Information' in rule and 'except' not in definition
        return {'family': 'linked_membership', 'evidence': [13, 16, 48]}
    if position == DECOY:
        sense, rule = (clean(spans[i]) for i in (7, 10))
        assert 'the fact that the practices are available for purchase' in sense
        assert 'restrict access' in rule
        return {'family': 'different_object', 'evidence': []}
    if position in SENSITIVITY:
        index, cue, reason = SENSITIVITY[position]
        assert cue in clean(spans[index])
        return {'family': reason, 'evidence': [], 'unresolved_anchor': index}
    if position not in EXPLICIT:
        return {'family': 'unreviewed', 'evidence': []}
    evidence = list(EXPLICIT[position])
    for i in evidence:
        text = clean(spans[i])
        assert OBJECT.search(text) and RESTRICTION_CUES[position] in text.lower()
    if position == (8, 1):
        assert 'shall include the existence of this Agreement' in spans[30]
        assert 'Subject to the restrictions set forth below' in spans[49]
        assert 'may disclose the other Party’s Confidential Information' in spans[49]
        assert all('shall not disclose the existence of this Agreement' in spans[i] for i in evidence)
        assert all('Representatives identified' in spans[i] for i in (56, 61))
        return {'family': 'specific_scoped_override', 'evidence': evidence,
                'secondary': [30, 49], 'continuations': [56, 61]}
    return {'family': 'explicit_prohibition', 'evidence': evidence}


def score_witness(result, rule):
    if not rule['evidence'] or result['answer'] is None:
        return 'unmeasured'
    if result['answer'] != ENTAILMENT:
        return 'label_conflict'
    if set(rule['evidence']) <= set(result['evidence_sentence_ids']):
        return 'complete'
    if rule['family'] == 'specific_scoped_override' and set(result['evidence_sentence_ids']) & set(rule['secondary']):
        return 'generic_scope_only'
    return 'specific_witness_missing'


def compare_policies(result, rule):
    values = dict.fromkeys(MODES, result)
    if rule['evidence']:
        amended = {**result, 'answer': ENTAILMENT, 'evidence_sentence_ids': rule['evidence']}
        values['source_scope_check'] = amended
        if rule['family'] != 'linked_membership':
            values['explicit_object_check'] = amended
    return values


def run():
    root = ROOT / read(BOOTSTRAP)['artifact_root']
    study = read(root / 'binding.json')
    assert root.name == digest(study)
    roster = load_roster(study)
    journal = TrainingJournal(root, study, roster)
    bank, grade_paths, scope, positive, paid, override = {}, {}, {}, [], set(), {}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        db.execute('begin')
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
        assert not ledger.get('reserved')
        for batch, sources in enumerate(roster, 1):
            stage = ROOT / read(FIRST if batch == 1 else observe_pointer(batch))['artifact_root']
            binding = read(stage / 'binding.json')
            terminal = read(stage / 'terminal.json')
            assert stage.name == digest(binding) and not terminal['TEST_opened']
            p = binding['native_grade_paths'][DATASET]
            grade_paths[p] = binding['native_grade_sha256'][p]
            observations = journal._observations(ORDINARY, batch)
            for i, source in enumerate(s for s in sources if s['dataset'] == DATASET):
                pos, key = (batch, i), source['key']
                assert source['project_split'] == 'train'
                view, = (v for v in source['views'] if v['id'] == TASK)
                spans = span_inventory(view)
                rule = source_rule(pos, spans)
                stored = read(journal.directory(ORDINARY, batch) / 'predictions' / (digest(key)+'.json'))
                assert digest(stored) == observations['predictions'][key]
                prediction = stored['result']
                identity = verify_prediction(db, key, prediction)
                physical_wire(db, {key}, identity, key)
                paid.add(identity)
                result = prediction['native'][TASK]
                bank[key] = {'batch': batch, 'native': view, 'outputs': compare_policies(result, rule)}
                scope[key] = rule
                if rule['family'] == 'specific_scoped_override':
                    actual = prediction['native']
                    assert actual['nda-5']['evidence_sentence_ids'] == actual['nda-7']['evidence_sentence_ids']
                    override['shared_grant_cited_for_both_recipient_hypotheses'] = (
                        actual['nda-5']['evidence_sentence_ids'] == [49])
                    override['original_existence_scope'] = score_witness(result, rule)
                    fit = ROOT / read(fit_pointer(batch))['artifact_root']
                    fit_lock, end = (read(fit / t) for t in ('binding.json', 'terminal.json'))
                    decisions = read(fit / 'matched_decisions.json')
                    assert fit.name == digest(fit_lock) and end['matched_decisions_sha256'] == digest(decisions)
                    assert not end['TEST_opened']
                    candidate = decisions['teacher'][ORDINARY][DATASET]
                    artifact = read(fit/'candidates'/ORDINARY/DATASET/'measurements.json')
                    assert digest(artifact['predictions']) == candidate['predictions_sha256']
                    native = artifact['predictions'][key]
                    physical = verify_prediction(db, key, native)
                    physical_wire(db, {key}, physical, key)
                    paid.add(physical)
                    override.update(candidate_existence_scope=score_witness(native['native'][TASK], rule),
                                    candidate_original_selection=candidate['selected'],
                                    native_training_delta=candidate['native_utility_delta'])

        # The five native-positive fit cells identified by the existing
        # retention audit. Reuse each cell's measured prior-TRAIN regression.
        for batch, arm in product((3, 4, 5), (ORDINARY, EXTERNAL_ARM)):
            stage = ROOT / read(fit_pointer(batch))['artifact_root']
            bind = read(stage / 'binding.json')
            done = read(stage / 'terminal.json')
            decisions = read(stage / 'matched_decisions.json')
            assert stage.name == digest(bind) and not done['TEST_opened']
            assert digest(decisions) == done['matched_decisions_sha256']
            assert all(sha(stage / 'source_snapshot' / n) == h for n, h in bind['source_sha256'].items())
            decision = decisions['teacher'][arm][DATASET]
            if decision['native_utility_delta'] <= 0:
                continue
            directory = stage / 'candidates' / arm / DATASET
            measured = read(directory / 'measurements.json')['predictions']
            earlier = read(directory / 'prior_TRAIN_regression.json')
            assert digest(measured) == decision['predictions_sha256']
            assert digest(earlier) == decision['earlier_TRAIN_regression']['evidence_sha256']
            counts = {'before': Counter(), 'candidate': Counter()}
            obs = journal._observations(arm, batch)
            for key, rule in scope.items():
                if not rule['evidence'] or bank[key]['batch'] > batch:
                    continue
                if bank[key]['batch'] == batch:
                    prior = read(journal.directory(arm, batch) / 'predictions' / (digest(key)+'.json'))
                    assert digest(prior) == obs['predictions'][key]
                    runs = (prior['result'], measured[key])
                else:
                    runs = (earlier['before'][key], earlier['candidate'][key])
                for tag, raw in zip(counts, runs, strict=True):
                    identity = verify_prediction(db, key, raw)
                    if identity not in paid:
                        physical_wire(db, {key}, identity, key)
                    paid.add(identity)
                    counts[tag][score_witness(raw['native'][TASK], rule)] += 1
            positive.append({'batch': batch, 'arm': 'common' if arm == ORDINARY else 'PARSE',
                             'accepted': decision['selected']=='candidate', 'source_witness': counts,
                             'fit_terminal_sha256': sha(stage / 'terminal.json')})
    assert len(positive) == 5 and len(bank) == 24
    grade_file, = grade_paths
    assert 'train' in Path(grade_file).parts
    expected = grade_paths[grade_file]
    config = {'study': 'CNI_disclosure_object_scope_TRAIN', 'runner_sha256': sha(Path(__file__)),
              'grader_sha256': expected, 'source_proofs_sha256': digest(scope),
              'original_predictions_sha256': digest(bank), 'full_source_bound_revision': True}
    out = HOME / digest(config)
    immutable_json(out / 'binding.json', config)
    immutable_json(out / 'predictions.json', {k: r['outputs'] for k, r in bank.items()})
    assert sha(ROOT / grade_file) == expected
    grade = read(ROOT / grade_file)
    exact, support, evidence = {m: [] for m in MODES}, {m: Counter() for m in MODES}, {m: [] for m in MODES}
    ambiguity = {}
    for key, r in bank.items():
        rule = scope[key]
        if 'unresolved_anchor' in rule:
            gold = grade[key][TASK]
            ambiguity[rule['family']] = {'raw_label': r['outputs']['original']['answer'], 'native_label': gold['answer'],
                                        'reviewed_anchor_in_official_evidence': rule['unresolved_anchor'] in gold['evidence']}
        for mode, row in r['outputs'].items():
            result = grade_view(DATASET, r['native'], grade[key][TASK], row['answer'], row['evidence_sentence_ids'])
            exact[mode].append({'source': key, 'view': TASK, 'grade': result['grade']})
            evidence[mode].append({'source': key, 'view': TASK, 'grade': result['evidence_f1']})
            support[mode][score_witness(row, scope[key])] += 1
    native = {m: {'exact_count': sum(v['grade'] for v in exact[m]),
                  'evidence_f1': mean(v['grade'] for v in evidence[m]),
                  'source_witness': dict(support[m])} for m in MODES}
    output = {'status': 'settled_CNI_disclosure_object_scope_TRAIN', 'partition': 'TRAIN',
              'original_mothers': len(bank), 'physical_responses_verified': len(paid),
              'source_scope_counts': dict(Counter(r['family'] for r in scope.values())),
              'prediction_results': native, 'matching_history_of_positive_fit_updates': positive,
              'specific_scope_override_case': override, 'ambiguous_scope_annotation_sensitivity': ambiguity,
              'scope_vs_direct_explicit': {'labels': paired_source_effect(exact[MODES[1]], exact[MODES[2]]),
                                           'evidence': paired_source_effect(evidence[MODES[1]], evidence[MODES[2]])},
              'direct_same_information_scope_link': 'Apply the independently reviewed source restriction per hypothesis.',
              'no_changed_original_stage_decision': True, 'DEV_or_TEST_opened': False, 'new_calls': 0,
              'runner_sha256': config['runner_sha256'], 'predictions_sha256': sha(out / 'predictions.json'), 'ledger': ledger}
    immutable_json(out / 'terminal.json', output)
    print(json.dumps({'artifact_root': str(out.relative_to(ROOT)), **output}, sort_keys=True), flush=True)


if __name__ == '__main__':
    run()
