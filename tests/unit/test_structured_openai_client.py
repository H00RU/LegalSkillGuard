import json

import pytest

from legal_skill_guard.inference.structured_openai_client import (
    StructuredModelInvocationError,
    StructuredOpenAIClient,
)

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["ready"],
    "properties": {"ready": {"type": "boolean"}},
}


def test_structured_client_validates_and_replays_cache(tmp_path) -> None:
    calls = []

    def runner(method, path, payload, timeout):
        calls.append((method, path, payload, timeout))
        return {
            "id": "response-1",
            "choices": [{"finish_reason": "stop", "message": {"content": '{"ready": true}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 4},
        }

    client = StructuredOpenAIClient(
        base_url="http://127.0.0.1:8002/v1",
        model="judge",
        cache_root=tmp_path,
        retries=0,
        request_runner=runner,
    )
    first = client.generate_json(
        purpose="probe", system_prompt="system", user_prompt="user", output_schema=SCHEMA
    )
    second = client.generate_json(
        purpose="probe", system_prompt="system", user_prompt="user", output_schema=SCHEMA
    )
    assert first.value == {"ready": True}
    assert not first.cache_hit
    assert second.cache_hit
    assert len(calls) == 1
    assert calls[0][2]["response_format"]["json_schema"]["strict"] is True


def test_structured_client_rejects_schema_invalid_output(tmp_path) -> None:
    def runner(method, path, payload, timeout):
        return {
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"ready": 1})}}]
        }

    client = StructuredOpenAIClient(
        base_url="http://127.0.0.1:8002/v1",
        model="judge",
        cache_root=tmp_path,
        retries=0,
        request_runner=runner,
    )
    with pytest.raises(StructuredModelInvocationError, match="ValidationError"):
        client.generate_json(
            purpose="probe",
            system_prompt="private system prompt",
            user_prompt="private user prompt",
            output_schema=SCHEMA,
        )
    artifacts = list((tmp_path / "_failures" / "probe").glob("*.json"))
    assert len(artifacts) == 1
    artifact_text = artifacts[0].read_text(encoding="utf-8")
    artifact = json.loads(artifact_text)
    assert artifact["error_type"] == "ValidationError"
    assert artifact["finish_reason"] == "stop"
    assert artifact["content_tail"] == '{"ready": 1}'
    assert "private system prompt" not in artifact_text
    assert "private user prompt" not in artifact_text


def test_structured_client_preflight_checks_exact_model(tmp_path) -> None:
    def runner(method, path, payload, timeout):
        assert (method, path, payload) == ("GET", "/models", None)
        return {"data": [{"id": "judge"}]}

    client = StructuredOpenAIClient(
        base_url="http://127.0.0.1:8002/v1",
        model="judge",
        cache_root=tmp_path,
        request_runner=runner,
    )
    assert client.preflight()["ready"] is True


def test_structured_client_preflight_rejects_same_name_wrong_runtime_contract(
    tmp_path,
) -> None:
    expected_root = tmp_path / "expected"

    def runner(method, path, payload, timeout):
        return {
            "data": [
                {
                    "id": "judge",
                    "root": str(tmp_path / "old"),
                    "max_model_len": 8192,
                }
            ]
        }

    client = StructuredOpenAIClient(
        base_url="http://127.0.0.1:8002/v1",
        model="judge",
        cache_root=tmp_path,
        request_runner=runner,
        expected_model_root=expected_root,
        expected_max_model_len=16384,
    )

    preflight = client.preflight()

    assert preflight["ready"] is False
    assert preflight["failed_checks"] == [
        "model_root_matches",
        "max_model_len_matches",
    ]


def test_structured_client_cache_identity_binds_model_revision(tmp_path) -> None:
    calls = []

    def runner(method, path, payload, timeout):
        calls.append(payload)
        return {
            "id": f"response-{len(calls)}",
            "choices": [
                {"finish_reason": "stop", "message": {"content": '{"ready": true}'}}
            ],
        }

    for revision in ("revision-a", "revision-b", "revision-a"):
        client = StructuredOpenAIClient(
            base_url="http://127.0.0.1:8002/v1",
            model="judge",
            model_revision=revision,
            cache_root=tmp_path,
            retries=0,
            request_runner=runner,
        )
        client.generate_json(
            purpose="probe",
            system_prompt="system",
            user_prompt="user",
            output_schema=SCHEMA,
        )

    assert len(calls) == 2
