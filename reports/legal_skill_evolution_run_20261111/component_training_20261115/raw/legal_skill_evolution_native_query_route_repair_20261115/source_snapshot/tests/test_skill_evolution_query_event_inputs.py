import hashlib

import pytest

from legal_skill_guard.skill_evolution import statute_input_dependencies as dependencies


def interface(tmp_path, monkeypatch):
    monkeypatch.setattr(dependencies, 'ROOT', tmp_path)
    folder = tmp_path / 'statutes'
    folder.mkdir()
    body = b's3306_c_10_A(Service,Employer,Employee,Workday) :-\n patient_(Service,Employer), agent_(Service,Employee).\n'
    (folder / 'section3306.pl').write_bytes(body)
    return {'statute_directory': 'statutes',
        'statute_sha256': {'section3306.pl': hashlib.sha256(body).hexdigest()},
        'native_query': [{'predicate': 's3306_c_10_A',
            'arguments': ['source_event', 'Current employer', 'Current worker', '2017-01-01']}]}


def test_native_relational_event_input_is_not_lost_with_missing_unary_call(tmp_path, monkeypatch):
    kernel = interface(tmp_path, monkeypatch)
    rows = [{'predicate': 's3306_c_10_A', 'arity': 4, 'file': 'section3306.pl', 'line': 1,
        'calls': [{'predicate': 'patient_', 'arity': 2, 'negated': False},
                  {'predicate': 'agent_', 'arity': 2, 'negated': False}]}]
    monkeypatch.setattr(dependencies, '_read', lambda *args: (rows, {'service_': 1, 'patient_': 2, 'agent_': 2}))
    graph = dependencies.dependency_graph(kernel)
    assert graph['input_predicates']['service_'] == 1
    assert 'service_/1' not in graph['reachable_predicates']
    assert graph['declared_query_event_inputs'][0]['routing_input_not_a_source_fact']
    assert graph['no_case_data_or_labels_read']


def test_query_typing_uses_only_its_explicit_bound_native_contract(tmp_path, monkeypatch):
    kernel = interface(tmp_path, monkeypatch)
    kernel['native_query'] = [{'predicate': 's3306_c_21', 'arguments': ['services']}]
    assert dependencies.query_event_inputs(kernel) == []
    kernel['native_query'] = [{'predicate': 's3306_c_10_A', 'arguments': []}]
    with pytest.raises(ValueError, match='ABI'):
        dependencies.query_event_inputs(kernel)


def test_query_contract_does_not_silently_survive_changed_author_code(tmp_path, monkeypatch):
    kernel = interface(tmp_path, monkeypatch)
    (tmp_path / 'statutes' / 'section3306.pl').write_text('different source')
    with pytest.raises(ValueError, match='changed'):
        dependencies.query_event_inputs(kernel)
