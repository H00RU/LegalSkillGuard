"""Public-input-only adapters. Labels and reference code stay in grading artifacts.

Loading a release for preparation may read annotations mechanically; inference
receives only Source.public. No test annotations are exposed in manifests/logs.
"""
from __future__ import annotations

import json
import re
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .coverage import digest
from .partitions import Source, normalized_text


@dataclass
class Prepared:
    sources: list[Source]
    grading: dict[str, dict]
    audit: dict


def _clusters(items: list[dict], keys: list[list[str]]) -> list[str]:
    parent = list(range(len(items)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    seen = {}
    for i, group_keys in enumerate(keys):
        for k in group_keys:
            if not k:
                continue
            if k in seen:
                a, b = find(i), find(seen[k])
                parent[max(a, b)] = min(a, b)
            else:
                seen[k] = i
    groups = {}
    for i in range(len(items)):
        groups.setdefault(find(i), []).append(i)
    result = [""] * len(items)
    for indexes in groups.values():
        group = digest(sorted(k for i in indexes for k in keys[i] if k))
        for i in indexes:
            result[i] = group
    return result


def _one_per_group(rows: list[tuple[Source, dict]]) -> Prepared:
    selected = {}
    for source, grade in rows:
        key = (source.key, source.native_split)
        # Deterministic public-content ordering, never sort by label/difficulty.
        if key not in selected or source.content_key < selected[key][0].content_key:
            selected[key] = source, grade
    pairs = [selected[k] for k in sorted(selected)]
    grading = {}
    for source, grade in pairs:
        # Cross-partition clusters may have different selected queries; binding
        # includes partition and public input hash rather than overwriting gold.
        grading[digest({"key": source.key, "split": source.native_split,
                        "content": source.content_key})] = grade
    return Prepared([s for s, _ in pairs], grading,
                    {"raw_rows": len(rows), "selected_native_groups": len(pairs),
                     "public_inputs_exclude_gold": True})


def sara_v2(archive: Path) -> Prepared:
    rows = []
    with tarfile.open(archive) as t:
        sections = {Path(m.name).name: t.extractfile(m).read().decode()
                    for m in t.getmembers() if m.isfile() and
                    m.name.startswith("sara_v2/statutes/source/section")}
        for split in ("train", "test"):
            ids = t.extractfile(f"sara_v2/splits/{split}").read().decode().splitlines()
            for case_id in ids:
                if not case_id.startswith("s"):
                    continue  # numeric tax cases are outside the fixed Binary task
                text = t.extractfile(f"sara_v2/cases/{case_id}.pl").read().decode()
                fact_match = re.search(r"% Text\s*\n(.*?)\n\s*% Question", text, re.S)
                question_match = re.search(r"% Question\s*\n(.*?)\n\s*% Facts", text, re.S)
                if not fact_match or not question_match:
                    raise ValueError("Unsupported SARA public-text schema")
                facts = " ".join(line.removeprefix("% ") for line in fact_match[1].splitlines())
                question_and_label = " ".join(line.removeprefix("% ") for line in question_match[1].splitlines())
                match = re.fullmatch(r"(.*?)\s+(Entailment|Contradiction)\s*", question_and_label)
                if not match:
                    raise ValueError("Binary SARA question/label separation failed")
                section_id = re.match(r"s(\d+)", case_id)[1]
                public = {"rules": sections[f"section{section_id}"], "facts": facts,
                          "query": match[1], "answer_type": "binary_entailment"}
                rows.append({"id": case_id, "split": split, "facts": facts,
                             "public": public, "answer": match[2]})
    keys = [["stem:" + re.sub(r"_(pos|neg)$", "", r["id"]),
             "facts:" + normalized_text(r["facts"])] for r in rows]
    clusters = _clusters(rows, keys)
    result = _one_per_group([(Source("SARA_v2_Binary", group, r["public"], r["split"]),
                              {"answer": r["answer"], "original_id": r["id"]})
                             for r, group in zip(rows, clusters)])
    result.audit.update({"grouping": "transitive case stem and normalized fact text",
                         "reference_prolog_in_public_input": False})
    return result


def contractnli(archive: Path, *, hypothesis: str = "nda-11") -> Prepared:
    rows = []
    with zipfile.ZipFile(archive) as z:
        for split in ("train", "dev", "test"):
            data = json.loads(z.read(f"contract-nli/{split}.json"))
            hypothesis_text = data["labels"][hypothesis]["hypothesis"]
            for doc in data["documents"]:
                rows.append({"id": doc["id"], "split": split, "url": doc["url"],
                             "text": doc["text"], "hypothesis": hypothesis_text,
                             "answer": doc["annotation_sets"][0]["annotations"][hypothesis]["choice"]})
    keys = [["url:" + r["url"] if r["url"] else "",
             "text:" + normalized_text(r["text"])] for r in rows]
    clusters = _clusters(rows, keys)
    result = _one_per_group([(Source("ContractNLI", group,
                              {"document": r["text"], "query": r["hypothesis"],
                               "answer_type": "contract_nli"}, r["split"]),
                              {"answer": r["answer"], "original_id": r["id"],
                               "hypothesis_id": hypothesis}) for r, group in zip(rows, clusters)])
    result.audit.update({"hypothesis_fixed_before_model_calls": hypothesis,
                         "automatic_gold_variants": False, "formal_completeness_claim": False,
                         "grouping": "transitive nonempty URL and normalized complete contract"})
    return result


def rulearena_airline(root: Path) -> Prepared:
    rules = (root / "reference_rules.txt").read_text()
    rows = []
    for path in sorted((root / "synthesized_problems").glob("comp_*.jsonl")):
        for line in path.read_text().splitlines():
            row = json.loads(line)
            group = digest(row["info"])
            source = Source("RuleArena_Airline", group,
                            {"rules": rules, "prompt": row["prompt"], "answer_type": "integer_cost"})
            # Original raw arguments, not computed intermediary answers. Only
            # the training/scoring oracle sees this record; actor sees prompt.
            rows.append((source, {"reference_arguments": row["info"]}))
    if not rows:
        raise ValueError("No Airline source problems")
    result = _one_per_group(rows)
    result.audit.update({"grouping": "original public problem arguments across complexity files",
                         "shared_allowance_fabricated": False})
    return result


def openexempt(packet: Path) -> Prepared:
    from legal_skill_guard.openexempt import active_case_input
    data = json.loads(packet.read_text())
    rows = []
    for item in data["sources"]:
        if set(item["tasks"]) != {"EC", "EV"}:
            raise ValueError("Each OE source must bundle EC and EV")
        source = Source("OpenExempt", item["group"],
                        {"views": {f: active_case_input(task) for f, task in item["tasks"].items()},
                         "answer_type": "bundled_EC_EV"})
        rows.append((source, {"targets": item["targets"],
                              "construction_only_case": item["construction_only_case"]}))
    result = _one_per_group(rows)
    result.audit.update({"upstream_commit": data["upstream_commit"], "seed": data["seed"],
                         "EC_EV_bundled": True, "resampled_by_outcome": False})
    return result


def proofwriter(root: Path) -> Prepared:
    """Official OWA depth-5 theory groups, one query fixed without its label."""
    rows = []
    for split in ("train", "dev", "test"):
        path = root / f"meta-{split}.jsonl"
        with path.open() as stream:
            for line in stream:
                theory = json.loads(line)
                facts = sorted(item["text"] for item in theory["triples"].values())
                rules = sorted(item["text"] for item in theory["rules"].values())
                group = digest({"facts": [normalized_text(t) for t in facts],
                                "rules": [normalized_text(t) for t in rules]})
                question_id, question = min(theory["questions"].items(),
                                           key=lambda item: digest(item[1]["question"]))
                answer = question["answer"]
                label = "True" if answer is True else "False" if answer is False else answer
                if label not in {"True", "False", "Unknown"}:
                    raise ValueError("Unexpected official ProofWriter label")
                public = {"facts": facts, "rules": rules, "query": question["question"],
                          "answer_type": "three_valued_owa"}
                source = Source("ProofWriter_OWA_depth5", group, public, split)
                grade = {"answer": label, "original_theory_id": theory["id"],
                         "original_question_id": question_id,
                         "reference_representation": {
                             "facts": [t["representation"] for t in theory["triples"].values()],
                             "rules": [r["representation"] for r in theory["rules"].values()],
                             "query": question["representation"]}}
                rows.append((source, grade))
    result = _one_per_group(rows)
    result.audit.update({"release": "V2020.12.3", "assumption": "OWA", "folder": "depth-5",
                         "one_query_per_theory": True, "query_selection_uses_label": False,
                         "reference_proofs_or_programs_in_public_input": False,
                         "grouping": "normalized complete facts and rules, independent of query"})
    return result
