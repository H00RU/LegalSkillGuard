"""Group-isolated, deterministic selection; derived views never become sources."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .coverage import digest
from .ledger import DATASETS


@dataclass(frozen=True)
class Source:
    dataset: str
    group: str
    public: dict
    native_split: str = "unsplit"

    @property
    def key(self) -> str:
        return f"{self.dataset}:{digest(self.group)}"

    @property
    def content_key(self) -> str:
        # Deliberately excludes references, answers and annotations.
        return digest(self.public)


def normalized_text(text: str) -> str:
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold()))


def split_sources(records: list[Source], *, salt: str = "LSG-RR-v2:45") -> dict:
    """Respect native train/dev/test pools; split an unsplit pool by group hash.

    Cross-native-partition groups are removed from train/dev and retained only
    in test. No labels are inspected. Native train without a dev split may
    supply dev groups after training selection; native test is never borrowed.
    """
    by_dataset = {d: [] for d in DATASETS}
    seen, public_groups = {}, {}
    for source in records:
        if source.dataset not in by_dataset or source.native_split not in {"train", "dev", "test", "unsplit"}:
            raise ValueError("Unsupported dataset or native split")
        # Identical public inputs under different groups are a leakage cluster,
        # never independent source records. Adapters must resolve this first.
        if source.content_key in public_groups and public_groups[source.content_key] != source.key:
            raise ValueError("Duplicate public input across source groups")
        public_groups[source.content_key] = source.key
        key = (source.key, source.native_split)
        if key in seen:
            if seen[key].content_key != source.content_key:
                raise ValueError("More than one selected task per source group")
            continue
        seen[key] = source
        by_dataset[source.dataset].append(source)
    selected, excluded = {}, []
    for dataset, rows in by_dataset.items():
        groups = {}
        for row in rows:
            groups.setdefault(row.key, []).append(row)
        pools = {s: [] for s in ("train", "dev", "test", "unsplit")}
        for key, entries in groups.items():
            splits = {r.native_split for r in entries}
            if len(splits) > 1:
                excluded.append({"source": key, "reason": "cross_native_partition_cluster"})
                if "test" in splits:
                    pools["test"].append(next(r for r in entries if r.native_split == "test"))
                continue
            pools[entries[0].native_split].append(entries[0])
        for pool in pools.values():
            pool.sort(key=lambda s: digest({"salt": salt, "key": s.key}))
        train_n = 32 if dataset == "OpenExempt" else 24
        if pools["unsplit"]:
            if any(pools[s] for s in ("train", "dev", "test")):
                raise ValueError("Mixed native and unsplit pools require an explicit adapter policy")
            pool = pools["unsplit"]
            splits = {"train": pool[:train_n], "dev": pool[train_n:train_n + 8],
                      "test": pool[train_n + 8:train_n + 40]}
        else:
            train_pool = pools["train"]
            splits = {"train": train_pool[:train_n], "dev": pools["dev"][:8] if pools["dev"]
                      else train_pool[train_n:train_n + 8], "test": pools["test"][:32]}
        if {s: len(v) for s, v in splits.items()} != {"train": train_n, "dev": 8, "test": 32}:
            raise ValueError(f"Insufficient independent source groups for {dataset}: "
                             f"{ {s: len(v) for s, v in splits.items()} }")
        selected[dataset] = {split: [{"key": r.key, "group": r.group, "content_hash": r.content_key,
                                     "native_split": r.native_split} for r in pool]
                             for split, pool in splits.items()}
    manifest = {"protocol": "LSG-RR-v2", "salt": salt, "datasets": selected,
                "excluded": excluded, "test_labels_read": False}
    manifest["sha256"] = digest(manifest)
    return manifest


def preflight_sources(manifest: dict) -> dict[str, list[str]]:
    raw = {k: v for k, v in manifest.items() if k != "sha256"}
    if digest(raw) != manifest["sha256"]:
        raise ValueError("Split manifest hash mismatch")
    return {d: [r["key"] for r in manifest["datasets"][d]["train"][:4]] for d in DATASETS}
