"""Hash-verified, allowlisted training data access for bounded live preflight."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .coverage import digest
from .ledger import DATASETS, BudgetError
from .partitions import preflight_sources


class PreflightData:
    def __init__(self, root: Path, manifest_path: Path):
        self.root = Path(root)
        self.manifest = json.loads(Path(manifest_path).read_text())
        if digest(self.manifest["packet_sha256"]) != self.manifest["data_hash"]:
            raise BudgetError("Dataset hash differs from packet bindings")
        allowlist = self.manifest["allowlist"]
        if allowlist != preflight_sources(self.manifest["split"]):
            raise BudgetError("Preflight sources differ from the first four fixed training sources")
        if set(allowlist) != set(DATASETS) or any(len(v) != 4 for v in allowlist.values()):
            raise BudgetError("Malformed fixed 20-source manifest")
        self.allowed = {s for values in allowlist.values() for s in values}
        self.order = self.manifest["pilot_order"]
        if len(self.allowed) != 20 or len(self.order) != 20 or set(self.order) != self.allowed:
            raise BudgetError("Pilot order differs from the source allowlist")
        directory = self.root / "data/packets/rr_v2"
        public_path = directory / "public_train.json"
        if hashlib.sha256(public_path.read_bytes()).hexdigest() != self.manifest["packet_sha256"]["public_train"]:
            raise BudgetError("Public training packet hash differs")
        public = json.loads(public_path.read_text())
        if public["split"] != "train" or public["contains_gold_or_reference_program"]:
            raise BudgetError("Preflight only accepts isolated public training inputs")
        self._public = {s["key"]: s for s in public["sources"] if s["key"] in self.allowed}
        if set(self._public) != self.allowed:
            raise BudgetError("Whitelisted training sources are missing")
        for source in self._public.values():
            if digest(source["public"]) != source["content_hash"]:
                raise BudgetError("Training source content binding differs")
        self.grade_path = directory / "grading_only/train.json"

    def public(self, source: str) -> dict:
        if source not in self.allowed:
            raise BudgetError("Source is not one of the fixed preflight training sources")
        # Return a detached value so that schema repair cannot alter the packet.
        return json.loads(json.dumps(self._public[source]))

    def grade(self, source: str) -> dict:
        if source not in self.allowed:
            raise BudgetError("Preflight cannot access non-allowlisted labels or test references")
        if hashlib.sha256(self.grade_path.read_bytes()).hexdigest() != self.manifest["packet_sha256"]["grading_train"]:
            raise BudgetError("Training grading packet hash differs")
        data = json.loads(self.grade_path.read_text())
        if data["split"] != "train" or not data["never_to_actor_or_teacher"]:
            raise BudgetError("Wrong grading partition")
        return data["sources"][source]

    def public_prediction_partition(self, partition: str) -> dict:
        if partition != "train":
            raise BudgetError("Formal dev/test prediction entry remains disabled")
        return {s: self.public(s) for s in self.order}
