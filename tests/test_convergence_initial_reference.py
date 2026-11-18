import pytest

from experiments import convergence_formal_test
from experiments.convergence_formal_test import INITIAL_ARM, _InitialReferenceEvaluation, _initial_reference_freeze
from legal_skill_guard.paired_interfaces.convergence_actors import initial_libraries
from legal_skill_guard.paired_interfaces.control_learning import direct_program
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def _cohort(partition, count):
    return [{'key': f'{partition}/{dataset}/{index}', 'project_split': partition, 'dataset': dataset,
             'views': [{'id': 'native', 'public': {}, 'answer_schema': {'type': 'boolean'}}]}
            for dataset in sorted(ConvergenceEvaluation.datasets) for index in range(count)]


def test_static_reference_uses_preselected_b0_on_the_full_frozen_cohort(tmp_path):
    dev, test = _cohort('dev', 16), _cohort('test', 32)
    identities = [{'source': row['key'], 'project_split': 'test', 'dataset': row['dataset'],
                   'public_content_sha256': digest(row), 'native_views': ['native']} for row in test]
    binding = {'enforce_physical_actor_audit': True, 'DEV_public_sha256': digest(dev),
               'TEST_identities_sha256': digest(identities)}
    initial = initial_libraries(direct_program(), binding)[INITIAL_ARM]
    learned = sealed({**{key: value for key, value in initial.items() if key != 'snapshot_sha256'},
                      'batch': 8}, 'snapshot_sha256')
    frozen = sealed({'batch': 8, 'study_binding': binding, 'TEST_identities_sha256': digest(identities),
                     'DEV_public_sha256': digest(dev), 'TEST_public_loaded_for_selection': False,
                     'TEST_grading_opened_for_selection': False}, 'freeze_sha256')
    reference = _initial_reference_freeze(initial, frozen)
    assert len(reference['choices']) == 1
    assert set(reference['choices'][INITIAL_ARM]) == ConvergenceEvaluation.datasets
    predictions, grades = set(), set()

    def grade(partition, source, seal):
        assert partition == 'test' and len(predictions) == 160
        assert set(seal['predictions_sha256']) == predictions
        grades.add(source)
        return {'native': {'answer': False}}

    evaluator = ConvergenceEvaluation(tmp_path, dev, identities, binding=binding, grade_provider=grade,
                                      load_test=lambda: pytest.fail('The reference should share the verified TEST sources'))
    evaluator.sources['test'] = test
    reference_evaluator = _InitialReferenceEvaluation(tmp_path, evaluator, frozen, reference)
    libraries = dict.fromkeys(evaluator.datasets, initial)

    def actor(source, snapshot, purpose):
        assert not grades and snapshot == initial and purpose == 'skill_test'
        predictions.add(source['key'])
        return {'native': {'native': {'handled': False}}}

    actor.verify_saved = lambda *_args: None
    with pytest.raises(ValueError, match='locally sealed fixed B8 study'):
        reference_evaluator.evaluate('test', INITIAL_ARM, 8, libraries, actor, freeze=reference)
    immutable_json(tmp_path / 'selection_freeze.json', frozen)
    with pytest.raises(ValueError, match='differs from the sealed'):
        reference_evaluator.evaluate('test', INITIAL_ARM, 8, dict.fromkeys(evaluator.datasets, learned), actor,
                                     freeze=reference)
    assert not predictions and not grades

    report = reference_evaluator.evaluate('test', INITIAL_ARM, 8, libraries, actor, freeze=reference)

    assert len(predictions) == len(grades) == len(report['source_scores']) == 160
    assert report['libraries'] == dict.fromkeys(evaluator.datasets, initial['snapshot_sha256'])
    assert not evaluator.cell_path('test', INITIAL_ARM, 8).exists()
    assert (reference_evaluator.cell_path('test', INITIAL_ARM, 8) / 'prediction_seal.json').is_file()


def test_frozen_sources_are_archived_at_prepare_and_preserved_on_conflict(tmp_path, monkeypatch):
    monkeypatch.setattr(convergence_formal_test, 'ROOT', tmp_path)
    source = tmp_path / 'reader.py'
    source.write_text('value = 1\n')
    stage = tmp_path / 'freeze'
    binding = {'source_sha256': {'reader.py': convergence_formal_test.sha(source)}}
    convergence_formal_test._archive_frozen_sources(stage, binding)
    convergence_formal_test._archive_frozen_sources(stage, binding)
    assert (stage / 'source_snapshot_receipt.json').exists()
    snapshot = stage / 'source_snapshot' / 'reader.py'
    assert snapshot.read_bytes() == source.read_bytes()

    source.write_text('value = 2\n')
    with pytest.raises(ValueError, match='changed before archiving'):
        convergence_formal_test._archive_frozen_sources(stage, binding)
    assert snapshot.read_text() == 'value = 1\n'
