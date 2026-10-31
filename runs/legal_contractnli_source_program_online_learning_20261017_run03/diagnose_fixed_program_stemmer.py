"""CPU-only fixed-program morphology diagnostic; never changes a running worker."""

# ruff: noqa: E402 -- Isolated run-local analysis, no production dependency.
from __future__ import annotations

import json
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.clauses import _WORD, _contains, _tokens, find_original_clauses, original_clause_records
from legal_skill_guard.learning.conditioned import list_preamble_links
from legal_skill_guard.learning.experiment import now, read, sha


def diagnose():
    wheel = ROOT / "artifacts/research_code/snowballstemmer-3.1.1-py3-none-any.whl"
    assert sha(wheel) == "7e207fa178741da09cdee59d3ecec3827ad5f92b1fc5c9ff3755b639f71f5752"
    sys.path.insert(0, str(wheel))  # Analysis process only; no installation/import in the worker.
    from snowballstemmer.english_stemmer import EnglishStemmer

    stemmer = EnglishStemmer()
    stem = lru_cache(None)(stemmer.stemWord)

    @lru_cache(None)
    def snowball_tokens(text):
        return tuple(stem(w) for w in _WORD.findall(text.lower()))

    def search(records, query, tokens):
        all_terms, any_terms, none_terms = ([tokens(p) for p in query[k]] for k in ("all_phrases", "any_phrases", "none_phrases"))
        return [r["original_span_index"] for r in records
            if all(_contains(tokens(r["literal_original_text"]), p) for p in all_terms)
            and (not any_terms or any(_contains(tokens(r["literal_original_text"]), p) for p in any_terms))
            and not any(_contains(tokens(r["literal_original_text"]), p) for p in none_terms)]

    cfg = read(ROOT / "configs/contractnli_source_programs_completion.json")
    packet, tx = read(ROOT / cfg["input_packet"]), read(OUT / "update_transactions/b2.json")
    rows = [r for r in packet["training"] if r["id"] in tx["source_case_ids"]]
    results, details = {}, []
    for version, bank in (("M1", tx["actual_parent"]), ("M2", tx["publication"])):
        counts = {"original_light": Counter(), "snowball_3_1_1": Counter()}
        changes = Counter()
        for row in rows:
            records = original_clause_records(row)
            pools = {}
            for mode, tokenizer in (("original_light", _tokens), ("snowball_3_1_1", snowball_tokens)):
                executed = {}
                for skill in bank:
                    members = set()
                    for query in skill["guidance"]["source_queries"]:
                        hits = search(records, query, tokenizer)
                        if mode == "original_light":
                            assert hits == find_original_clauses(records, query["all_phrases"], query["any_phrases"], query["none_phrases"])
                        links = list_preamble_links(row, hits) if query["include_list_preamble"] else []
                        members.update(hits)
                        members.update(v["possible_preamble_span_index"] for v in links)
                    executed[skill["id"]] = members
                pools[mode] = {h: set().union(*(executed[s["id"]] for s in bank if h in s["hypothesis_ids"])) for h in packet["public_hypotheses"]}
                for h, target in row["annotation_sets"][0]["annotations"].items():
                    G, P = set(target["spans"]), pools[mode][h]
                    if target["choice"] == "NotMentioned":
                        counts[mode]["NM_query_returned_members"] += len(P)
                    else:
                        counts[mode].update(Gold_members=len(G), query_true=len(G & P), query_false=len(P - G), query_missing=len(G - P))
            for h, target in row["annotation_sets"][0]["annotations"].items():
                G, old, new = set(target["spans"]), pools["original_light"][h], pools["snowball_3_1_1"][h]
                gained, lost = (G & new) - old, (G & old) - new
                changes.update(true_members_gained=len(gained), true_members_lost=len(lost))
                if gained or lost:
                    details.append({"bank": version, "document_id": row["id"], "hypothesis_id": h,
                        "new_true_members": sorted(gained), "lost_true_members": sorted(lost)})
        results[version] = {"coverage": {k: dict(v) for k, v in counts.items()}, "changes": dict(changes)}
    result = {"at": now(), "run_id": OUT.name, "fixed_programs_all12_seen_TRAIN_sources": True,
        "not_deployed_not_a_native_answer_effect_or_admission_test": True,
        "same_word_regex_no_stopword_or_modality_removal_no_term_tuning": True,
        "new_native_teacher_fit_counts": [0, 0, 0], "results": results, "changed_original_members": details,
        "bindings": {str(p): sha(p) for p in (wheel, Path(__file__), OUT / "update_transactions/b2.json", ROOT / cfg["input_packet"])}}
    RunStore.immutable_json(OUT / "monitoring/fixed_program_Snowball_vs_light_morphology_all12_seen_only.json", result)
    print(json.dumps({"results": results, "new_native_teacher_fit_counts": [0, 0, 0]}, ensure_ascii=False))


if __name__ == "__main__":
    diagnose()
