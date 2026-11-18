import pytest

from legal_skill_guard.paired_interfaces.convergence_actors import initial_libraries
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.control_learning import direct_program
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, sealed
from legal_skill_guard.skill_evolution.objects import digest


def test_journal_resumes_verified_rows_and_requires_committed_batches(tmp_path):
    batches = [[{'key': f'train-{batch}-{index}', 'project_split': 'train', 'views': [{'id': 'native'}]}
                for index in range(16)] for batch in range(8)]
    binding = {'TRAIN_ordered_batches_sha256': digest(batches)}
    journal = TrainingJournal(tmp_path, binding, batches)
    initial = initial_libraries(direct_program(), binding)
    journal.initialize(initial)
    arm = ConvergenceEvaluation.arms[0]
    reads = []

    class AuditActor:
        def __call__(self, source, library, purpose):
            reads.append(source['key'])
            return {'native': {'native': {'answer': 1, 'handled': True}},
                    'fallback_executed': False, 'source': source['key']}

        def verify_saved(self, source, library, purpose, result):
            assert result['source'] == source['key']
            assert purpose == 'skill_actor' and library['batch'] == 0

    actor = AuditActor()
    first = journal.observe(arm, 1, actor)
    assert journal.observe(arm, 1, actor) == first
    assert len(reads) == 16
    with pytest.raises(FileNotFoundError):
        journal.seal_B8()

    state = {key: value for key, value in initial[arm].items() if key != 'snapshot_sha256'}
    checkpoint = sealed({**state, 'batch': 1}, 'snapshot_sha256')
    evidence = {'visible_prefix_sha256': digest(first['ordered_sources']), 'choice': 'retain'}

    def verify_retain(before, after, decision, prefix):
        return (before['programs'] == after['programs'] and decision['choice'] == 'retain'
                and list(prefix) == first['ordered_sources'])

    with pytest.raises(ValueError, match='visible prefix'):
        journal.commit_update(arm, 1, checkpoint, {**evidence, 'visible_prefix_sha256': 'changed'},
                              verify_update=verify_retain)
    result = journal.commit_update(arm, 1, checkpoint, evidence, verify_update=verify_retain)
    assert result['library_sha256'] == journal.library(arm, 1)['snapshot_sha256']
    with pytest.raises(FileNotFoundError):
        journal.seal_B8()

    row = tmp_path / 'train' / arm / 'B1' / 'predictions' / (digest(first['ordered_sources'][0]) + '.json')
    row.write_text('{}')
    with pytest.raises(ValueError, match='differs from its verified prediction'):
        journal.seal_B8()
