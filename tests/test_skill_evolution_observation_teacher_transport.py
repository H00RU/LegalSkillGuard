import json
from pathlib import Path

from legal_skill_guard.skill_evolution.observation_teacher_transport import pack_task, unpack_task
from legal_skill_guard.skill_evolution.teacher_transport import pack_programs


def test_actual_third_batch_task_is_byte_value_equivalent_and_smaller():
    task = json.loads(Path('artifacts/legal_skill_evolution_mixed_component_training_history_20261115/B3/teacher_task.json').read_text())
    old = pack_programs(task)
    packed = pack_task(task)
    assert unpack_task(packed) == task
    old_bytes = len(json.dumps(old, ensure_ascii=False, separators=(',', ':')).encode())
    new_bytes = len(json.dumps(packed, ensure_ascii=False, separators=(',', ':')).encode())
    assert new_bytes < old_bytes


def test_schema_order_literal_failures_and_unicode_are_preserved():
    task = {'components': [
        {'schema_json': '{"type":"object","properties":{"β":{"type":"string"},"a":{"type":"number"}}}'},
        {'schema_json': '{ "type": "object" }'},
        {'schema_json': '{bad original schema'},
    ], 'conversion_program': 'def helper(x):\n    return x\n\ndef apply(inputs,premises):\n    return helper(inputs)\n'}
    assert unpack_task(pack_task(task)) == task


def test_actual_fifth_batch_full_history_fits_without_omission():
    from legal_skill_guard.inference.codex_cli_client import CODEX_TURN_INPUT_CHARACTER_LIMIT
    task = json.loads(Path('artifacts/legal_skill_evolution_mixed_component_training_status_schema_20261115/B5/teacher_task.json').read_text())
    for arm, library in task['current_libraries_both_available'].items():
        payload = {**task, 'seed_for_this_arm': library}
        packed = pack_task(payload)
        assert unpack_task(packed) == payload
        # Leave ample room for the unchanged system instruction and wrapper.
        assert len(json.dumps(packed, ensure_ascii=False, separators=(',', ':'))) < CODEX_TURN_INPUT_CHARACTER_LIMIT - 20000


def test_actual_eighth_batch_full_history_fits_with_exact_key_order_and_full_prompt():
    from experiments import legal_skill_evolution_observation_component_acquire as acquisition
    from legal_skill_guard.inference.codex_cli_client import render_structured_codex_prompt, CODEX_TURN_INPUT_CHARACTER_LIMIT
    from legal_skill_guard.skill_evolution.teacher_transport import INSTRUCTION, PROGRAM_INSTRUCTION
    from legal_skill_guard.skill_evolution.observation_teacher_transport import INSTRUCTION as SCHEMA_INSTRUCTION
    task = json.loads(Path('artifacts/legal_skill_evolution_mixed_component_training_validated_updates_20261115/B8/teacher_task.json').read_text())
    system = acquisition.SYSTEM + INSTRUCTION + PROGRAM_INSTRUCTION + SCHEMA_INSTRUCTION + (' ' * 2000)
    for arm, library in task['current_libraries_both_available'].items():
        payload = {**task, 'seed_for_this_arm': library}
        packed = pack_task(payload)
        dump = lambda value: json.dumps(value, ensure_ascii=False, separators=(',', ':'))
        assert dump(unpack_task(packed)) == dump(payload)
        assert len(render_structured_codex_prompt(system, dump(packed))) <= CODEX_TURN_INPUT_CHARACTER_LIMIT
