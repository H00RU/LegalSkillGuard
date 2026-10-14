"""Reconstruct the exact latest TRAIN-only source-component selection.

Never opens official dev.json/test.json. No generated facts or relabelling.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import zipfile
from pathlib import Path

from legal_skill_guard.experiment.storage import RunStore

TRAIN_IDS = [
    490,
    334,
    538,
    177,
    88,
    331,
    136,
    187,
    238,
    245,
    273,
    416,
    262,
    588,
    261,
    487,
    325,
    206,
    377,
    159,
    204,
    375,
    430,
    290,
    388,
    322,
    622,
    613,
    163,
    104,
    383,
    92,
]
FUTURE_IDS = [
    242,
    182,
    199,
    229,
    359,
    221,
    495,
    100,
    541,
    489,
    424,
    617,
    557,
    184,
    149,
    597,
    344,
    120,
    269,
    196,
    284,
    113,
    176,
    256,
]


def source_components(documents):
    parent = {r["id"]: r["id"] for r in documents}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[max(a, b)] = min(a, b)

    urls, texts = {}, {}
    for row in documents:
        if row["url"]:
            if row["url"] in urls:
                union(row["id"], urls[row["url"]])
            else:
                urls[row["url"]] = row["id"]
        key = " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", row["text"]).casefold()))
        if key in texts:
            union(row["id"], texts[key])
        else:
            texts[key] = row["id"]
    groups = {}
    for i in parent:
        groups.setdefault(find(i), []).append(i)
    return [sorted(g) for g in groups.values()]


def prepare_packets(root: Path, cfg: dict):
    archive = root / cfg["source_archive"]
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    if checksum != cfg["source_archive_sha256"]:
        raise ValueError("Pinned dataset archive bytes differ")
    with zipfile.ZipFile(archive) as z:
        original = json.loads(z.read("contract-nli/train.json"))
    docs = {r["id"]: r for r in original["documents"]}
    groups = source_components(original["documents"])
    ranked = sorted(
        (g for g in groups if 382 not in g),
        key=lambda g: hashlib.sha256(
            ("contractnli_bounded_learning_v1:" + ",".join(map(str, g))).encode()
        ).hexdigest(),
    )
    a, b = cfg["train_component_ranks"]
    c, d = cfg["future_component_ranks"]
    train_groups, future_groups = ranked[a:b], ranked[c:d]
    training = [{**docs[i], "batch": j // 4 + 1} for j, g in enumerate(train_groups) for i in g]
    future_ids = [i for g in future_groups for i in g]
    if [r["id"] for r in training] != TRAIN_IDS or future_ids != FUTURE_IDS:
        raise ValueError("Exact historical metadata selection did not reconstruct")
    if len(original["labels"]) != 17 or len(future_groups) != 24:
        raise ValueError("Original task/source group cardinality differs")
    packet = {
        "public_hypotheses": original["labels"],
        "training": training,
        "development_inputs_no_annotation_sets": [
            {k: v for k, v in docs[i].items() if k != "annotation_sets"} for i in future_ids
        ],
        "development_component_groups": future_groups,
    }
    RunStore.immutable_json(root / cfg["input_packet"], packet)
    RunStore.immutable_json(
        root / cfg["grading_only"],
        {
            "annotations": {
                str(i): docs[i]["annotation_sets"][0]["annotations"] for i in future_ids
            },
            "never_to_solver_or_teacher": True,
            "read_only_after_all_six_future_conditions_finish": True,
        },
    )
    preselection = {
        "source_archive_sha256": checksum,
        "source_archive_url": cfg["source_archive_url"],
        "read_members": ["contract-nli/train.json"],
        "train_component_ranks_half_open": [a, b],
        "future_component_ranks_half_open": [c, d],
        "training_ids": TRAIN_IDS,
        "future_ids": FUTURE_IDS,
        "train_component_groups": train_groups,
        "future_component_groups": future_groups,
        "rank_rule": "SHA256(contractnli_bounded_learning_v1:ordered IDs), excluding component382",
        "component_rule": "same nonempty URL or normalized complete text, transitive union",
        "official_dev_test_opened": False,
        "old_raw_runs_and_historical_libraries_recovered": False,
        "reconstruction_from_original_data_not_new_generation": True,
    }
    RunStore.immutable_json(root / cfg["preselection"], preselection)
    return preselection
