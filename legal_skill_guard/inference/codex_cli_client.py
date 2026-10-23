"""Auditable structured-output adapter for a ChatGPT-authenticated Codex CLI.

Codex runs in an empty temporary working directory. Tool-use events make the call
invalid. Persistent caches contain response payloads and hashes, never hidden prompts.
"""

from __future__ import annotations

import ctypes
import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from contextlib import suppress
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal_skill_guard.utils.hashing import canonical_json_sha256


class CodexInvocationError(RuntimeError):
    """A structured Codex call failed without producing a trustworthy payload."""


@dataclass(frozen=True)
class StructuredCodexResponse:
    value: dict[str, Any]
    model: str
    request_sha256: str
    response_sha256: str
    cache_hit: bool
    invocation: dict[str, Any]


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]

# The turn/start transport cap is separate from model-context/token capacity.
# Verified from input_too_large on 2026-10-14; never truncate to satisfy it.
CODEX_TURN_INPUT_CHARACTER_LIMIT = 1_048_576


def render_structured_codex_prompt(system_prompt: str, user_prompt: str) -> str:
    return (
        "你是一个无工具的结构化推理组件。不得调用shell、文件、网络、MCP或任何其他工具；"
        "只能根据下方显式输入完成任务，并输出符合给定JSON Schema的单个JSON对象。\n\n"
        f"系统任务：\n{system_prompt.strip()}\n\n具体输入：\n{user_prompt.strip()}"
    )


ANY_CONDITION_VALUE_SCHEMA: dict[str, Any] = {
    "anyOf": [
        {"type": "string"},
        {"type": "number"},
        {"type": "boolean"},
        {
            "type": "array",
            "items": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "number"},
                    {"type": "boolean"},
                ]
            },
        },
        {"type": "null"},
    ]
}


def strict_output_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Convert a Pydantic schema to OpenAI's strict Structured Outputs subset."""

    normalized = deepcopy(schema)

    def visit(node: dict[str, Any]) -> None:
        node.pop("default", None)
        node.pop("title", None)
        if not node:
            node.update(deepcopy(ANY_CONDITION_VALUE_SCHEMA))
            return
        properties = node.get("properties")
        if isinstance(properties, dict):
            node["additionalProperties"] = False
            node["required"] = list(properties)
            for child in properties.values():
                if isinstance(child, dict):
                    visit(child)
        definitions = node.get("$defs")
        if isinstance(definitions, dict):
            for child in definitions.values():
                if isinstance(child, dict):
                    visit(child)
        items = node.get("items")
        if isinstance(items, dict):
            visit(items)
        alternatives = node.get("anyOf")
        if isinstance(alternatives, list):
            for child in alternatives:
                if isinstance(child, dict):
                    visit(child)

    visit(normalized)
    issues = strict_output_schema_issues(normalized)
    if issues:
        raise ValueError(f"strict output schema normalization failed: {issues[:5]}")
    return normalized


def strict_output_schema_issues(schema: dict[str, Any]) -> list[str]:
    """Return deterministic violations of OpenAI strict-schema object rules."""

    issues: list[str] = []

    def visit(node: dict[str, Any], path: str) -> None:
        if "default" in node:
            issues.append(f"{path}:default_not_supported")
        # A valid general JSON Schema need not be a valid transport schema.
        # Reject before reserving a teacher request; do not silently drop a
        # constraint or repair the returned value. Callers enforce cross-item
        # identity/uniqueness separately after generation.
        for keyword in (
            "uniqueItems",
            "allOf",
            "not",
            "dependentRequired",
            "dependentSchemas",
            "if",
            "then",
            "else",
        ):
            if keyword in node:
                issues.append(f"{path}:{keyword}_not_supported")
        properties = node.get("properties")
        if isinstance(properties, dict):
            if node.get("additionalProperties") is not False:
                issues.append(f"{path}:additional_properties_not_false")
            required = node.get("required")
            # `required` names a set of fields. Output ordering belongs to
            # `properties`; changing that order does not make fields optional.
            if (
                not isinstance(required, list)
                or any(not isinstance(name, str) for name in required)
                or len(required) != len(set(required))
                or set(required) != set(properties)
            ):
                issues.append(f"{path}:not_all_properties_required")
            for name, child in properties.items():
                if isinstance(child, dict):
                    visit(child, f"{path}.properties.{name}")
        definitions = node.get("$defs")
        if isinstance(definitions, dict):
            for name, child in definitions.items():
                if isinstance(child, dict):
                    visit(child, f"{path}.$defs.{name}")
        items = node.get("items")
        if isinstance(items, dict):
            visit(items, f"{path}.items")
        alternatives = node.get("anyOf")
        if isinstance(alternatives, list):
            for index, child in enumerate(alternatives):
                if isinstance(child, dict):
                    visit(child, f"{path}.anyOf[{index}]")
        if not any(key in node for key in ("type", "$ref", "anyOf", "properties")):
            issues.append(f"{path}:untyped_schema")

    visit(schema, "$")
    return issues


def run_process_tree(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """Run a command in its own process group and reap the whole tree on timeout."""

    input_value = kwargs.pop("input", None)
    if input_value is not None and "stdin" not in kwargs:
        kwargs["stdin"] = subprocess.PIPE
    timeout = kwargs.pop("timeout", None)
    check = bool(kwargs.pop("check", False))
    _enable_child_subreaper()
    process = subprocess.Popen(command, start_new_session=True, **kwargs)
    try:
        stdout, stderr = process.communicate(input=input_value, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
        _reap_process_group(process.pid)
        # communicate() after termination contains the complete drained stream,
        # including events received before the deadline. Preserve it without
        # treating a timed-out command as a successful teacher response.
        if stdout is not None:
            exc.output = stdout
        if stderr is not None:
            exc.stderr = stderr
        raise
    completed = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    if check:
        completed.check_returncode()
    return completed


def _enable_child_subreaper() -> None:
    """Adopt orphaned grandchildren so timed-out command trees can be reaped."""

    if sys.platform != "linux":
        return
    with suppress(OSError, AttributeError):
        libc = ctypes.CDLL(None, use_errno=True)
        pr_set_child_subreaper = 36
        libc.prctl(pr_set_child_subreaper, 1, 0, 0, 0)


def _reap_process_group(process_group_id: int, timeout_seconds: float = 2.0) -> None:
    """Reap adopted descendants from exactly one terminated process group."""

    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            child_pid, _ = os.waitpid(-process_group_id, os.WNOHANG)
        except ChildProcessError:
            return
        if child_pid > 0:
            continue
        if time.monotonic() >= deadline:
            return
        time.sleep(0.01)


class CodexCLIClient:
    """Call one fixed Codex model with a JSON Schema and output-only contract."""

    TOOL_EVENT_MARKERS = (
        '"type":"command_execution"',
        '"type":"mcp_tool_call"',
        '"type":"web_search"',
        '"type":"file_change"',
    )

    def __init__(
        self,
        *,
        model: str,
        cache_root: Path,
        reasoning_effort: str = "low",
        timeout_seconds: int = 180,
        retries: int = 1,
        executable: str = "codex",
        command_runner: CommandRunner | None = None,
        invocation_budget_path: Path | None = None,
        max_invocations: int | None = None,
        context_window_tokens: int | None = None,
        auto_compact_token_limit: int | None = None,
        max_input_tokens: int | None = None,
    ) -> None:
        self.model = model
        self.cache_root = cache_root
        self.reasoning_effort = reasoning_effort
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.executable = executable
        self.command_runner = command_runner or run_process_tree
        self.invocation_budget_path = invocation_budget_path
        self.max_invocations = max_invocations
        self.context_window_tokens = context_window_tokens
        self.auto_compact_token_limit = auto_compact_token_limit
        self.max_input_tokens = max_input_tokens
        context_settings = (context_window_tokens, auto_compact_token_limit, max_input_tokens)
        if any(value is not None for value in context_settings) and (
            any(value is None for value in context_settings)
            or not 0 < max_input_tokens < auto_compact_token_limit < context_window_tokens
        ):
            raise ValueError("context profile requires input < compact threshold < context window")
        if (invocation_budget_path is None) != (max_invocations is None):
            raise ValueError(
                "invocation_budget_path and max_invocations must be configured together"
            )
        if max_invocations is not None and max_invocations < 1:
            raise ValueError("max_invocations must be positive")

    def preflight(self) -> dict[str, Any]:
        executable = shutil.which(self.executable)
        if executable is None:
            return {"ready": False, "reason": "codex_executable_not_found"}
        completed = self.command_runner(
            [executable, "login", "status"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
            check=False,
        )
        output = completed.stdout or ""
        return {
            "ready": completed.returncode == 0 and "Logged in" in output,
            "reason": "authenticated" if completed.returncode == 0 else "login_status_failed",
            # Report canonical identity rather than the symlink spelling used to
            # invoke it, matching invocation artifacts and the frozen role check.
            "executable": str(Path(executable).resolve()),
            "login_status_sha256": canonical_json_sha256({"output": output.strip()}),
        }

    def request_payload(
        self,
        *,
        purpose: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
    ) -> dict[str, Any]:
        value = {
            "adapter_schema_version": 1,
            "purpose": purpose,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "output_schema": output_schema,
        }
        if self.context_window_tokens is not None:
            value.update(
                {
                    "adapter_schema_version": 2,
                    "context_window_tokens": self.context_window_tokens,
                    "auto_compact_token_limit": self.auto_compact_token_limit,
                    "max_input_tokens": self.max_input_tokens,
                    "input_budget_estimator": "o200k_base_plus_20000_cli_reserve",
                }
            )
        return value

    def generate_json(
        self,
        *,
        purpose: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
    ) -> StructuredCodexResponse:
        schema_issues = strict_output_schema_issues(output_schema)
        if schema_issues:
            raise CodexInvocationError(
                f"Codex output schema violates strict Structured Outputs rules: {schema_issues[:5]}"
            )
        request_value = self.request_payload(
            purpose=purpose,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_schema=output_schema,
        )
        prompt = render_structured_codex_prompt(system_prompt, user_prompt)
        if len(prompt) > CODEX_TURN_INPUT_CHARACTER_LIMIT:
            raise CodexInvocationError(
                f"complete teacher input exceeds turn/start character limit: "
                f"{len(prompt)}/{CODEX_TURN_INPUT_CHARACTER_LIMIT}; no evidence was truncated"
            )
        if self.max_input_tokens is not None:
            # Explicit conservative local estimate, not a server token count.
            # Check before reserving a call; never truncate or choose evidence.
            import tiktoken

            estimated = (
                len(
                    tiktoken.get_encoding("o200k_base").encode(
                        system_prompt + user_prompt + json.dumps(output_schema, ensure_ascii=False),
                        disallowed_special=(),
                    )
                )
                + 20_000
            )  # Leave room for the CLI's own fixed instructions/envelope.
            if estimated > self.max_input_tokens:
                raise CodexInvocationError(
                    f"complete teacher input exceeds local token budget: "
                    f"{estimated}/{self.max_input_tokens}; no evidence was truncated"
                )
        request_sha256 = canonical_json_sha256(request_value)
        cache_path = self.cache_root / purpose / f"{request_sha256}.json"
        if cache_path.is_file():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise CodexInvocationError(f"Codex cache is unreadable: {cache_path}") from exc
            value = cached.get("value") if isinstance(cached, dict) else None
            cache_contract_valid = (
                isinstance(cached, dict)
                and cached.get("schema_version") == 1
                and cached.get("request_sha256") == request_sha256
                and cached.get("model") == self.model
                and cached.get("purpose") == purpose
                and isinstance(value, dict)
                and isinstance(cached.get("invocation"), dict)
                and canonical_json_sha256(value) == cached.get("response_sha256")
            )
            if not cache_contract_valid:
                raise CodexInvocationError(f"Codex cache contract mismatch: {cache_path}")
            return StructuredCodexResponse(
                value=value,
                model=self.model,
                request_sha256=request_sha256,
                response_sha256=cached["response_sha256"],
                cache_hit=True,
                invocation=cached["invocation"],
            )

        executable = shutil.which(self.executable)
        if executable is None:
            raise CodexInvocationError(f"Codex executable not found: {self.executable}")
        last_error = "unknown_failure"
        for attempt in range(self.retries + 1):
            try:
                value, invocation = self._invoke(
                    executable,
                    prompt,
                    output_schema,
                    attempt,
                    purpose=purpose,
                    request_sha256=request_sha256,
                )
            except (
                OSError,
                subprocess.SubprocessError,
                json.JSONDecodeError,
                CodexInvocationError,
            ) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                response_sha256 = canonical_json_sha256(value)
                payload = {
                    "schema_version": 1,
                    "request_sha256": request_sha256,
                    "response_sha256": response_sha256,
                    "model": self.model,
                    "purpose": purpose,
                    "value": value,
                    "invocation": invocation,
                }
                self._atomic_json(cache_path, payload)
                return StructuredCodexResponse(
                    value=value,
                    model=self.model,
                    request_sha256=request_sha256,
                    response_sha256=response_sha256,
                    cache_hit=False,
                    invocation=invocation,
                )
            if attempt < self.retries:
                time.sleep(1.0 * (2**attempt))
        raise CodexInvocationError(
            f"Structured Codex call failed for {purpose} after {self.retries + 1} attempts: "
            f"{last_error}"
        )

    def _invoke(
        self,
        executable: str,
        prompt: str,
        output_schema: dict[str, Any],
        attempt: int,
        *,
        purpose: str,
        request_sha256: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        started = datetime.now(UTC)
        with tempfile.TemporaryDirectory(prefix="lsg-codex-") as directory:
            workdir = Path(directory)
            schema_path = workdir / "output.schema.json"
            output_path = workdir / "response.json"
            schema_path.write_text(
                json.dumps(output_schema, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            command = [
                executable,
                "exec",
                "--model",
                self.model,
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--ignore-rules",
                "--ignore-user-config",
                "--disable",
                "apps",
                "--disable",
                "plugins",
                "--disable",
                "tool_suggest",
                "--json",
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
                "--cd",
                str(workdir),
                "-c",
                f'model_reasoning_effort="{self.reasoning_effort}"',
                "-",
            ]
            if self.context_window_tokens is not None:
                command[-1:-1] = [
                    "-c",
                    f"model_context_window={self.context_window_tokens}",
                    "-c",
                    f"model_auto_compact_token_limit={self.auto_compact_token_limit}",
                ]
            environment = dict(os.environ)
            environment.pop("OPENAI_API_KEY", None)
            budget_reservation = self._reserve_invocation(
                purpose=purpose,
                request_sha256=request_sha256,
                attempt=attempt + 1,
            )
            try:
                completed = self.command_runner(
                    command,
                    input=prompt,
                    text=True,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=self.timeout_seconds,
                    check=False,
                    cwd=workdir,
                    env=environment,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                partial = getattr(exc, "stdout", None) or getattr(exc, "output", None) or ""
                event_log = (partial.decode("utf-8", errors="replace")
                             if isinstance(partial, bytes) else partial)
                self._write_failure_artifact(
                    purpose=purpose,
                    request_sha256=request_sha256,
                    attempt=attempt + 1,
                    executable=executable,
                    started=started,
                    budget_reservation=budget_reservation,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    returncode=None,
                    event_log=event_log,
                    failure_events=self._failure_events(event_log),
                )
                raise
            event_log = completed.stdout or ""
            usage = self._turn_usage(event_log)
            compact_events = event_log.replace(" ", "").replace("\n", "")
            if any(marker in compact_events for marker in self.TOOL_EVENT_MARKERS):
                self._write_failure_artifact(
                    purpose=purpose,
                    request_sha256=request_sha256,
                    attempt=attempt + 1,
                    executable=executable,
                    started=started,
                    budget_reservation=budget_reservation,
                    error_type="CodexInvocationError",
                    error_message="Codex attempted a forbidden tool call",
                    returncode=completed.returncode,
                    event_log=event_log,
                    failure_events=[],
                )
                raise CodexInvocationError("Codex attempted a forbidden tool call")
            if completed.returncode != 0:
                failure_events = self._failure_events(event_log)
                digest = canonical_json_sha256({"event_log": event_log[-4000:]})
                self._write_failure_artifact(
                    purpose=purpose,
                    request_sha256=request_sha256,
                    attempt=attempt + 1,
                    executable=executable,
                    started=started,
                    budget_reservation=budget_reservation,
                    error_type="CodexNonzeroExit",
                    error_message=f"Codex exited {completed.returncode}",
                    returncode=completed.returncode,
                    event_log=event_log,
                    failure_events=failure_events,
                )
                raise CodexInvocationError(
                    f"Codex exited {completed.returncode}; event_log_sha256={digest}; "
                    f"failure_events={failure_events[:3]}"
                )
            if not output_path.is_file():
                self._write_failure_artifact(
                    purpose=purpose,
                    request_sha256=request_sha256,
                    attempt=attempt + 1,
                    executable=executable,
                    started=started,
                    budget_reservation=budget_reservation,
                    error_type="CodexInvocationError",
                    error_message="Codex produced no output-last-message file",
                    returncode=completed.returncode,
                    event_log=event_log,
                    failure_events=self._failure_events(event_log),
                )
                raise CodexInvocationError("Codex produced no output-last-message file")
            try:
                value = json.loads(output_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                self._write_failure_artifact(
                    purpose=purpose,
                    request_sha256=request_sha256,
                    attempt=attempt + 1,
                    executable=executable,
                    started=started,
                    budget_reservation=budget_reservation,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    returncode=completed.returncode,
                    event_log=event_log,
                    failure_events=self._failure_events(event_log),
                )
                raise
            if not isinstance(value, dict):
                self._write_failure_artifact(
                    purpose=purpose,
                    request_sha256=request_sha256,
                    attempt=attempt + 1,
                    executable=executable,
                    started=started,
                    budget_reservation=budget_reservation,
                    error_type="CodexInvocationError",
                    error_message="Codex structured output is not a JSON object",
                    returncode=completed.returncode,
                    event_log=event_log,
                    failure_events=self._failure_events(event_log),
                )
                raise CodexInvocationError("Codex structured output is not a JSON object")
            finished = datetime.now(UTC)
            invocation = {
                "attempt": attempt + 1,
                "started_at": started.isoformat(),
                "finished_at": finished.isoformat(),
                "elapsed_seconds": round((finished - started).total_seconds(), 3),
                "returncode": completed.returncode,
                "event_log_sha256": canonical_json_sha256({"event_log": event_log}),
                "tool_events_detected": False,
                "budget_reservation": budget_reservation,
                "usage": usage,
                "estimated_credits": self._estimated_credits(usage),
            }
            return value, invocation

    @staticmethod
    def _failure_events(event_log: str) -> list[dict[str, str]]:
        events: list[dict[str, str]] = []
        for line in event_log.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") not in {"error", "turn.failed"}:
                continue
            events.append(
                {
                    "type": str(event.get("type")),
                    "message": str(event.get("message") or event.get("error") or "")[:500],
                }
            )
        return events

    def _write_failure_artifact(
        self,
        *,
        purpose: str,
        request_sha256: str,
        attempt: int,
        executable: str,
        started: datetime,
        budget_reservation: dict[str, Any] | None,
        error_type: str,
        error_message: str,
        returncode: int | None,
        event_log: str,
        failure_events: list[dict[str, str]],
    ) -> None:
        """Persist actual transport output, never recover an answer from a failure."""

        finished = datetime.now(UTC)
        artifact = {
            "schema_version": 1,
            "model": self.model,
            "purpose": purpose,
            "request_sha256": request_sha256,
            "attempt": attempt,
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "elapsed_seconds": round((finished - started).total_seconds(), 3),
            "executable": str(Path(executable).resolve()),
            "returncode": returncode,
            "error_type": error_type,
            "error_message": error_message[:1000],
            "event_log_sha256": canonical_json_sha256({"event_log": event_log}),
            "event_log": event_log,
            "event_log_tail": event_log[-4000:],
            "failure_events": failure_events[:10],
            "budget_reservation": budget_reservation,
            "usage": self._turn_usage(event_log),
        }
        safe_purpose = "".join(
            character if character.isalnum() or character in {"-", "_"} else "_"
            for character in purpose
        )
        destination = (
            self.cache_root
            / "_failures"
            / safe_purpose
            / f"{request_sha256}.attempt-{attempt}.json"
        )
        self._atomic_json(destination, artifact)

    def _reserve_invocation(
        self, *, purpose: str, request_sha256: str, attempt: int
    ) -> dict[str, Any] | None:
        if self.invocation_budget_path is None or self.max_invocations is None:
            return None
        path = self.invocation_budget_path
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_suffix(path.suffix + ".lock")
        with lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if path.is_file():
                ledger = json.loads(path.read_text(encoding="utf-8"))
            else:
                ledger = {
                    "schema_version": 1,
                    "model": self.model,
                    "max_invocations": self.max_invocations,
                    "reservations": [],
                }
            if ledger.get("model") != self.model:
                raise CodexInvocationError("Codex invocation budget model mismatch")
            if ledger.get("max_invocations") != self.max_invocations:
                raise CodexInvocationError("Codex invocation budget limit mismatch")
            reservations = ledger.get("reservations")
            if not isinstance(reservations, list):
                raise CodexInvocationError("Codex invocation budget ledger is invalid")
            historical = ledger.get("historical_count_lower_bound", 0)
            if type(historical) is not int or historical < 0:
                raise CodexInvocationError("Invalid historical lower bound")
            reserved = historical + len(reservations)
            if reserved >= self.max_invocations:
                raise CodexInvocationError(
                    f"Codex hard invocation budget exhausted: at least {reserved}/"
                    f"{self.max_invocations}"
                )
            reservation = {
                "sequence": reserved + 1,
                "new_epoch_sequence": len(reservations) + 1,
                "reserved_at": datetime.now(UTC).isoformat(),
                "model": self.model,
                "purpose": purpose,
                "request_sha256": request_sha256,
                "attempt": attempt,
            }
            reservations.append(reservation)
            self._atomic_json(path, ledger)
            return reservation

    def invocation_budget_status(self) -> dict[str, int] | None:
        """Read capacity under the same lock used by invocation reservation.

        The experiment executor checks this before a teacher round so a shortage
        stops the round before its first new proposal instead of producing a
        partially teacher-processed batch.
        """

        if self.invocation_budget_path is None or self.max_invocations is None:
            return None
        path = self.invocation_budget_path
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_suffix(path.suffix + ".lock")
        with lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if path.is_file():
                ledger = json.loads(path.read_text(encoding="utf-8"))
                if ledger.get("model") != self.model:
                    raise CodexInvocationError("Codex invocation budget model mismatch")
                if ledger.get("max_invocations") != self.max_invocations:
                    raise CodexInvocationError("Codex invocation budget limit mismatch")
                reservations = ledger.get("reservations")
                if not isinstance(reservations, list):
                    raise CodexInvocationError("Codex invocation budget ledger is invalid")
                historical = ledger.get("historical_count_lower_bound", 0)
                if type(historical) is not int or historical < 0:
                    raise CodexInvocationError("Invalid historical lower bound")
                new_reserved = len(reservations)
                reserved = historical + new_reserved
            else:
                reserved = 0
                historical = new_reserved = 0
            return {
                "hard_limit": self.max_invocations,
                "reserved": reserved,
                "available": max(self.max_invocations - reserved, 0),
                "historical_count_lower_bound": historical,
                "new_epoch_reserved": new_reserved,
                "historical_records_missing": bool(historical),
            }

    @staticmethod
    def _turn_usage(event_log: str) -> dict[str, int] | None:
        usage = None
        for line in event_log.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "turn.completed" or not isinstance(event.get("usage"), dict):
                continue
            candidate = event["usage"]
            keys = (
                "input_tokens",
                "cached_input_tokens",
                "output_tokens",
                "reasoning_output_tokens",
            )
            usage = {key: int(candidate.get(key) or 0) for key in keys}
        return usage

    def _estimated_credits(self, usage: dict[str, int] | None) -> float | None:
        if usage is None or self.model != "gpt-5.6-luna":
            return None
        cached = min(usage["cached_input_tokens"], usage["input_tokens"])
        uncached = usage["input_tokens"] - cached
        credits = (uncached * 5 + cached * 0.5 + usage["output_tokens"] * 30) / 1_000_000
        return round(credits, 6)

    @staticmethod
    def _atomic_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(path)
