from copy import deepcopy
import json
import re

import pytest

from legal_skill_guard.paired_interfaces import indexed_relational_read as indexed
from legal_skill_guard.paired_interfaces import cni_disclosure_relational as disclosure
from legal_skill_guard.paired_interfaces import maud_knowledge_relational as knowledge
from legal_skill_guard.paired_interfaces import relational_program
from legal_skill_guard.paired_interfaces.pilot_metrics import rank_external_pilot
from legal_skill_guard.paired_interfaces.production_decode import decode_response
from legal_skill_guard.paired_interfaces.residual import encode


def test_indexed_wire_preserves_consumer_and_rejects_span_exchange():
    public = {'source_text': 'Other defined words.\n Knowledge means information after reasonable inquiry.'}
    source = {'key': 'maud_fixture', 'views': [{'id': knowledge.TASK, 'public': public}]}
    selected, view = knowledge.build(source)
    view = indexed.reformat(view)
    fields = {'qualification_target': 'target_definition', 'inquiry_effect': 'required',
              'explicit_actual_restriction': None}
    for plan in view['plans']:
        program = plan['relational_program']
        name, unit = indexed.indexed_unit(program)
        binding = indexed.bind(program, public)
        asset = unit['asset']
        order, _ = indexed.encoded_relations(asset)
        relations = encode(asset['features'], fields)
        raw = '|'.join(['s2', *(indexed.symbol(relations[name]) for name in order)])
        scalar = indexed.reader_schema(program, binding)['enum']
        factored = indexed.reader_schema(program, binding, factorized=True)['pattern']
        assert raw in scalar
        assert all(re.fullmatch(factored, value) for value in scalar)
        assert not re.fullmatch(factored, raw.replace('s2|', 's99|'))
        original = {name: {'status': 'complete', 'evidence': [{
            'field': 'source_text', 'quote': ' Knowledge means information after reasonable inquiry.'}],
            'observation': {'source_anchor': name, 'relations': relations}}}
        for evidence in original[name]['evidence']:
            start, end = binding['spans']['s2']
            assert evidence['quote'] == public['source_text'][start:end]
        assert indexed.decode(program, binding, raw, public) == relational_program.decode(program, original, public)
        assert indexed.decode(program, binding, indexed.UNREAD, public)['outputs'][knowledge.TASK] is None
        result = decode_response(selected, view, plan, {'content': json.dumps(raw), 'finish_reason': 'stop'})
        assert result['production_errors'] == []
        assert result['native'][knowledge.TASK]['answer'] == 'Constructive knowledge'
        refused = decode_response(selected, view, plan, {'content': json.dumps(raw), 'finish_reason': 'length'})
        assert refused['production_errors']
        assert refused['native'][knowledge.TASK]['answer'] is None
        with pytest.raises(ValueError, match='Unknown evidence'):
            indexed.decode(program, binding, raw.replace('s2|', 's99|'), public)
        exchanged = deepcopy(binding)
        exchanged['spans']['s2'] = exchanged['spans']['s1']
        with pytest.raises(ValueError, match='lost its source'):
            indexed.decode(program, exchanged, raw, public)
        if plan['choices']['knowledge_scope'] == 1:
            for code in indexed.reader_schema(program, binding)['enum']:
                if code == indexed.UNREAD:
                    continue
                restored = indexed.expand(program, binding, code, public)[name]['observation']['relations']
                assert json.dumps(restored, sort_keys=True, separators=(',', ':')) in asset['decoder']


def test_clause_pair_retains_both_native_evidence_ids():
    first = 'The Receiving Party may disclose Confidential Information:'
    second = 'only to its employees with a need to know.'
    text = first + '\n' + second
    source = {'key': 'cni_fixture', 'dataset': 'ContractNLI', 'views': [{
        'id': disclosure.TASK, 'public': {'source_text': text, 'question': 'Employee sharing',
            'sentence_spans': [[0, len(first)], [len(first) + 1, len(text)]]}}]}
    selected, view = disclosure.build(source)
    for plan in view['plans']:
        program = plan['relational_program']
        _, unit = indexed.indexed_unit(program)
        asset = unit['asset']
        fields, _ = indexed.encoded_relations(asset)
        state = {'disclosure_actor': 'receiver', 'recipient_group': 'own_employees', 'permission_force': 'allow'}
        relation = encode(asset['features'], state)
        code = '|'.join(['n0_1', *(indexed.symbol(relation[name]) for name in fields)])
        result = decode_response(selected, view, plan, {'content': json.dumps(code), 'finish_reason': 'stop'})
        assert result['production_errors'] == []
        assert result['native'][disclosure.TASK]['answer'] == 'Entailment'
        assert result['native'][disclosure.TASK]['evidence_sentence_ids'] == [0, 1]
        ungrounded = decode_response(selected, view, plan, {'content': '"unread"', 'finish_reason': 'stop'})
        assert ungrounded['native'][disclosure.TASK]['answer'] is None
        assert ungrounded['native'][disclosure.TASK]['evidence_sentence_ids'] == []


def test_external_comparison_keeps_all_units_and_breaks_native_ties_by_logical_cost():
    fixed = [{'source': f'{dataset}_{index}', 'dataset': dataset}
             for dataset in 'abcde' for index in range(4)]
    rows = [{**source, 'view': 'native', 'grade': 0.5, 'handled': True} for source in fixed]
    task_ids = {source['source']: ['native'] for source in fixed}
    candidates = [
        {'family': name, 'matched_public_conditions_sha256': '0' * 64,
         'comparison_logical_tokens': tokens, 'rows': rows}
        for name, tokens in [('family_one', 30), ('family_two', 29)]
    ]
    families = ('family_one', 'family_two')
    result = rank_external_pilot(candidates, fixed, task_ids, families)
    assert result['selected_family'] == 'family_two'
    candidates[1]['rows'] = rows[:-1]
    with pytest.raises(ValueError, match='Every fixed native task'):
        rank_external_pilot(candidates, fixed, task_ids, families)
