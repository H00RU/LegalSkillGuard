import pytest

from experiments.convergence_revision5_release_dev import CNI, ReleaseActor, digest


@pytest.fixture
def archive(monkeypatch):
    source = {'key': 'nda', 'dataset': CNI, 'project_split': 'dev'}
    baseline = {'answer': 'NotMentioned', 'evidence_sentence_ids': [], 'handled': True}
    parent = {'public_source_sha256': digest(source), 'library_sha256': 'baseline',
              'result': {'native': {'a': baseline, 'b': baseline}, 'revision5': {'mechanism_activated': False}}}
    change = {'answer': 'Entailment', 'evidence_sentence_ids': [7]}
    updates = {CNI: {'arm': {'nda': {'a': baseline, 'b': change}}}}
    actor = ReleaseActor(None, {'arm': (None, {'libraries': {CNI: 'baseline'}})}, updates)
    monkeypatch.setattr(actor, 'original', lambda *_: parent)
    return source, actor, parent


def test_amendment_preserves_unaffected_output_and_route(archive):
    source, actor, parent = archive
    prediction = actor(source, {'arm': 'arm', 'batch': 8}, 'skill_dev')
    assert prediction['native']['a'] == parent['result']['native']['a']
    assert prediction['native']['b'] == {'answer': 'Entailment', 'evidence_sentence_ids': [7], 'handled': True}
    assert prediction['revision5'] == parent['result']['revision5']
    assert parent['result']['native']['b']['answer'] == 'NotMentioned'


def test_rejects_unbound_use_and_dropped_tasks(archive):
    source, actor, _ = archive
    library = {'arm': 'arm', 'batch': 8}
    with pytest.raises(ValueError, match='exact original revised DEV'):
        actor(source, library, 'skill_test')
    with pytest.raises(ValueError, match='exact original revised DEV'):
        actor({**source, 'changed': True}, library, 'skill_dev')
    del actor.updates[CNI]['arm']['nda']['a']
    with pytest.raises(ValueError, match='drop native tasks'):
        actor(source, library, 'skill_dev')
