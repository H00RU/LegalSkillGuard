import json

import pytest

from legal_skill_guard.paired_interfaces.control_programs import ControlProgramRuntime
from legal_skill_guard.skill_evolution.clients import GenerationHold
from tests.test_paired_control_programs import FakeExecutor, program


def test_hold_is_preserved_without_creating_a_reusable_program_result(tmp_path):
    source = {'key': 'constructed_train_mother', 'dataset': 'fixture'}
    view = {'id': 'native', 'public': {'facts': '5 and 7'}, 'answer_schema': {'type': 'integer'}}
    candidate = program()

    class HoldThenServe(FakeExecutor):
        def __init__(self):
            super().__init__()
            self.held_id = None

        def generate(self, call_id, **kwargs):
            if self.held_id is None:
                self.held_id = call_id
                raise GenerationHold('before reservation')
            assert call_id == self.held_id
            return super().generate(call_id, **kwargs)

    executor = HoldThenServe()
    runtime = ControlProgramRuntime(executor, tmp_path, max_calls=1)
    result_path = runtime.execution_path(candidate, source, view)
    with pytest.raises(GenerationHold):
        runtime.run(candidate, source, view)
    assert executor.calls == [] and not result_path.exists()
    interrupted, = result_path.parent.glob('generation_interruptions/*.json')
    audit = json.loads(interrupted.read_text())
    assert audit['traces'][0]['logical_call_id'] == executor.held_id and not audit['core_executed']

    result = runtime.run(candidate, source, view)
    assert result['answer'] == 12 and result['core_executed']
    assert len(executor.calls) == 1
    assert runtime.run(candidate, source, view) == result and len(executor.calls) == 1
