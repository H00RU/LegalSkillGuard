import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

from experiments import legal_skill_evolution_observation_library_train as train
from legal_skill_guard.skill_evolution.statute_input_dependencies import dependency_graph


def fixture(directory, program):
    texts = {'events.pl':':- discontiguous pay_/1.\n:- discontiguous date_/2.\n',
        'utils.pl':'', 'section1.pl':program}
    for name,text in texts.items():
        (Path(directory)/name).write_text(text)
    return {'statute_directory':directory,
        'statute_sha256':{n:hashlib.sha256(t.encode()).hexdigest() for n,t in texts.items()},
        'native_query':[{'predicate':'s1','arguments':['payer']}]}


def test_reading_public_terms_does_not_execute_directives_and_handles_meta_scopes():
    with TemporaryDirectory() as folder:
        kernel=fixture(folder, ':- throw(must_not_execute).\ns1(X):- findall(hidden_data(X), (pay_(X), \\+ date_(X,_)), _).\n')
        graph=dependency_graph(kernel)
    assert graph['input_predicates']=={'date_':2,'pay_':1}
    assert graph['graph_complete_for_supported_control_forms']
    assert any(e['to']=='date_/2' and e['negated'] for e in graph['edges'])
    assert not any(e['to'].startswith('hidden_data') for e in graph['edges'])


def test_recursive_statutes_terminate_and_opaque_goals_remain_explicit():
    with TemporaryDirectory() as folder:
        kernel=fixture(folder,'s1(X):-s2(X).\ns2(X):-s1(X),pay_(X),call(_).\n')
        graph=dependency_graph(kernel)
    assert graph['input_predicates']=={'pay_':1}
    assert graph['opaque_calls'] and not graph['graph_complete_for_supported_control_forms']


def test_declared_case_inputs_can_also_have_statutory_definitions():
    with TemporaryDirectory() as folder:
        kernel=fixture(folder,'s1(X):-s151_b(X,4000,2017).\ns151_b(X,_,_):-pay_(X).\n')
        graph=dependency_graph(kernel)
    assert graph['input_predicates']=={'pay_':1,'s151_b':3}


def test_all_original_TRAIN_queries_have_label_free_dependency_graphs():
    bank=train.read(train.parent.OUT/'SARA_native_kernel_bank.json')
    for row in bank:
        graph=dependency_graph(row['kernel'])
        assert graph['graph_complete_for_supported_control_forms'], (row['source'],graph)
        assert graph['no_case_data_or_labels_read'] and graph['not_a_learned_mechanism']

