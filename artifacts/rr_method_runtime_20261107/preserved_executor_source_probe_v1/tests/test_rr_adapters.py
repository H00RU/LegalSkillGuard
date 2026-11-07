"""Adapter checks use artificial releases; no held-out real labels for debugging."""
import io
import json
import tarfile
import zipfile

from legal_skill_guard.rr.adapters import (
    contractnli,
    openexempt,
    proofwriter,
    rulearena_airline,
    sara_v2,
)


def test_sara_separates_question_label_and_groups_same_fact_stems(tmp_path):
    path = tmp_path / "sara.tar.gz"
    content = {
        "sara_v2/statutes/source/section151": "Rule text.",
        "sara_v2/splits/train": "s151_a_pos\ns151_a_neg\n",
        "sara_v2/splits/test": "s151_b_pos\n",
    }
    for case, split_label, facts in [("s151_a_pos", "Entailment", "Alice has a job."),
                                      ("s151_a_neg", "Contradiction", "Alice has a job."),
                                      ("s151_b_pos", "Entailment", "Bob has a job.")]:
        content[f"sara_v2/cases/{case}.pl"] = (
            f"% Text\n% {facts}\n\n% Question\n% Section 151 applies. {split_label}\n\n"
            "% Facts\nreference_program_must_not_be_in_input.\n% Test\n:- halt.\n")
    with tarfile.open(path, "w:gz") as t:
        for name, data in content.items():
            b = data.encode()
            entry = tarfile.TarInfo(name)
            entry.size = len(b)
            t.addfile(entry, io.BytesIO(b))
    result = sara_v2(path)
    assert len(result.sources) == 2
    for s in result.sources:
        assert s.public["query"] == "Section 151 applies."
        assert "reference_program" not in str(s.public)
        assert "Entailment" not in str(s.public) and "Contradiction" not in str(s.public)


def test_contract_fixed_hypothesis_excludes_annotations_and_spans(tmp_path):
    path = tmp_path / "cnli.zip"
    with zipfile.ZipFile(path, "w") as z:
        for split in ("train", "dev", "test"):
            doc = {"id": split, "text": f"Public {split} contract", "url": f"https://example/{split}",
                   "spans": ["hidden proof"], "annotation_sets": [{"annotations": {
                       "nda-11": {"choice": "NotMentioned", "spans": [0]}}}]}
            z.writestr(f"contract-nli/{split}.json", json.dumps({"documents": [doc],
                       "labels": {"nda-11": {"hypothesis": "Public hypothesis"}}}))
    result = contractnli(path)
    assert len(result.sources) == 3
    for s in result.sources:
        assert set(s.public) == {"document", "query", "answer_type"}
        assert "NotMentioned" not in str(s.public) and "hidden proof" not in str(s.public)
    assert result.audit["automatic_gold_variants"] is False


def test_airline_keeps_problem_group_across_complexity_files(tmp_path):
    (tmp_path / "reference_rules.txt").write_text("Airline public rules")
    directory = tmp_path / "synthesized_problems"
    directory.mkdir()
    for i in range(2):
        (directory / f"comp_{i}.jsonl").write_text(json.dumps({"prompt": f"public formulation {i}",
                "info": {"base_price": 100, "bag_list": []}}) + "\n")
    result = rulearena_airline(tmp_path)
    assert len(result.sources) == 1
    assert "reference_arguments" not in result.sources[0].public
    assert result.audit["shared_allowance_fabricated"] is False


def test_openexempt_bundles_two_views_without_construction_or_target_fields(tmp_path):
    from legal_skill_guard.openexempt import ACTIVE_CASE_FIELDS
    tasks = {family: {"family": family, "components": {k: k for k in ACTIVE_CASE_FIELDS}}
             for family in ("EC", "EV")}
    path = tmp_path / "oe.json"
    path.write_text(json.dumps({"upstream_commit": "pinned", "seed": 45, "sources": [
        {"group": "case", "tasks": tasks, "targets": {"EC": "gold", "EV": "gold"},
         "construction_only_case": {"reference": "hidden"}}]}))
    result = openexempt(path)
    assert len(result.sources) == 1 and set(result.sources[0].public["views"]) == {"EC", "EV"}
    assert "gold" not in str(result.sources[0].public) and "hidden" not in str(result.sources[0].public)


def test_proofwriter_one_query_per_theory_independent_of_label_and_no_reference_input(tmp_path):
    for split in ("train", "dev", "test"):
        theory = {"id": split, "triples": {"t1": {"text": f"{split} is blue.", "representation": "private_atom"}},
                  "rules": {}, "questions": {
                      "q1": {"question": f"{split} is blue.", "representation": "private_query", "answer": True},
                      "q2": {"question": f"{split} is cold.", "representation": "private_query2", "answer": "Unknown"}},
                  "allProofs": ["private_proof"]}
        (tmp_path / f"meta-{split}.jsonl").write_text(json.dumps(theory) + "\n")
    first = proofwriter(tmp_path)
    assert len(first.sources) == 3
    assert all("private_" not in str(s.public) for s in first.sources)
    path = tmp_path / "meta-train.jsonl"
    theory = json.loads(path.read_text())
    theory["questions"]["q1"]["answer"] = False
    theory["questions"]["q2"]["answer"] = True
    path.write_text(json.dumps(theory) + "\n")
    second = proofwriter(tmp_path)
    assert [s.content_key for s in first.sources] == [s.content_key for s in second.sources]
