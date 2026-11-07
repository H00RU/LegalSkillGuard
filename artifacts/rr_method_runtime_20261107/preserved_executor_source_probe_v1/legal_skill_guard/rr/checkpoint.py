"""Content-addressed state saves with input/code/config binding and frozen reads."""
from __future__ import annotations

import json
import os
import tempfile
from hashlib import sha256
from pathlib import Path

from .coverage import digest


def immutable_json(path: Path, value: dict) -> str:
    raw = (json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise FileExistsError("Immutable artifact content differs")
        return sha256(raw).hexdigest()
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        try:
            os.link(temp, path)
        except FileExistsError:
            if path.read_bytes() != raw:
                raise FileExistsError("Concurrent immutable artifact conflict") from None
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        os.unlink(temp)
    return sha256(raw).hexdigest()


class Checkpoints:
    def __init__(self, root: Path, binding: dict):
        required = {"code_hash", "config_hash", "data_hash", "source_manifest_hash"}
        if set(binding) != required or any(not v for v in binding.values()):
            raise ValueError("Checkpoint requires exact code/config/data/source bindings")
        self.root, self.binding = Path(root), binding

    def save(self, state: dict, *, stage: str, ledger_export: dict) -> str:
        if stage != "preflight":
            raise ValueError("This entry saves only preflight state, not formal B1/B8 results")
        payload = {"schema": 1, "stage": stage, "binding": self.binding,
                   "state": state, "ledger": ledger_export}
        key = digest(payload)
        immutable_json(self.root / f"{key}.json", payload)
        return key

    def load(self, key: str) -> dict:
        if len(key) != 64 or any(c not in "0123456789abcdef" for c in key):
            raise ValueError("Invalid checkpoint identifier")
        payload = json.loads((self.root / f"{key}.json").read_text())
        if digest(payload) != key or payload["binding"] != self.binding:
            raise ValueError("Checkpoint corrupted or its state binding has changed")
        if payload["stage"] != "preflight":
            raise ValueError("Wrong checkpoint stage")
        return payload

    def freeze_preflight(self, key: str) -> dict:
        payload = self.load(key)
        manifest = {"schema": 1, "stage": "preflight", "checkpoint": key,
                    "binding": self.binding, "library_hash": digest(payload["state"]),
                    "frozen": True, "formal_B8": False}
        immutable_json(self.root / f"{key}.frozen.json", manifest)
        return manifest
