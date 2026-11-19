"""Reconcile B7 eligibility checks with explicitly answered OpenExempt categories."""

import itertools
import json
from pathlib import Path
import sqlite3

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_train_fit import M2, OE, ORDINARY, pointer as fit_pointer
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_cni_nonsolicitation import bound_stage
from experiments.convergence_revision5_oe_category_scope import prepare_category, view_facts
from experiments.convergence_revision5_oe_joint_native_gate import compare_slots, slot_records
from experiments.convergence_revision5_oe_m2_source_placement import direct_title_scope, title_conditional_support
from experiments.convergence_revision5_oe_scoped_policy_replay import verify_native
from experiments.convergence_revision5_oe_task_route import aligned_titles, public_controls, score
from experiments.convergence_revision5_oe_wildcard_replay import prepare_routes
from legal_skill_guard.openexempt import UPSTREAM
from legal_skill_guard.paired_interfaces.convergence_ev_inventory import public_inventory
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import FILER, filers, rules, title_inventory
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


CHOICES = ("incumbent", "proposal")
REGIMES = ("common_controls", "wildcard", "category")
HOME = BASE / "revision5_OE_assertion_coverage_20261119"
TABLE = ROOT / "reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_ASSERTION_COVERAGE_20261119.json"
PUBLIC_B7 = TABLE.with_name("REVISION5_M2_OE_JOINT_NATIVE_GATE_20261119.json")
RENDERER = {
    "party.py": "be76cb0dd2d855a768c92819567b831e200414b552865db76d3428043464ba2e",
    "task_generator.py": "78f50e89108a938ffd383350bd83d2922b516890faa8181453b3cfe3a0df6af3",
}


def normalized_scope(view):
    """Recognize the exact renderer family name in a matched asset quote."""
    public = view["public"]
    text = public["original_input"]
    facts = text.partition("\nFacts:\n")[2].partition("\nOutput contract:")[0]
    count, aliases = filers(facts)
    if count != 2:
        return view, 0
    names = [n.split() for n in FILER.match(facts.strip())["names"].casefold().split(" and ")]
    surname = names[-1][-1]
    if len(names[-1]) < 2 or any(len(n) > 1 and n[-1] != surname for n in names):
        return view, 0
    suffix = "es" if surname.endswith(("s", "x", "z", "ch", "sh")) else "s"
    alias = "the " + surname + suffix
    if alias in aliases:
        return view, 0

    inventory = public_inventory(text)
    assert inventory is not None
    quotes = {row["source_quote"] for row in inventory.values()}
    edits = []
    for quote in quotes:
        ranges = {m.span("holder") for _, template, _, _ in rules()
                  if (m := template.fullmatch(quote)) and m["holder"].casefold() == alias}
        if not ranges:
            continue
        assert facts.count(quote) == text.count(quote) == len(ranges) == 1
        offset = text.index(quote)
        (start, end), = ranges
        edits.append((offset + start, offset + end))
    if not edits:
        return view, 0
    revised = text
    for first, end in sorted(edits, reverse=True):
        revised = revised[:first] + ("The Debtors" if text[first].isupper() else "the Debtors") + revised[end:]
    _, scoped, _ = title_inventory(revised)
    assert [(a["description"], a["amount_quote"]) for a in inventory.values()] == [
        (a["description"], a["amount_quote"]) for a in scoped.values()
    ]
    assert supplied_jurisdiction_scope(revised) == supplied_jurisdiction_scope(text)
    return {**view, "public": {**public, "original_input": revised}}, len(edits)


def assertion(ec, *, explicitly_answered, exact_exclusion):
    if ec:
        return True
    if explicitly_answered or exact_exclusion:
        return False
    return None


def compare_conflicts(original, controlled, titles, exact_ec_scope):
    """Keep other eligibility values unresolved on rows added by a repair."""
    coarse, bound, relaxed = set(), set(), set()
    ec, ev = controlled["EC"], controlled["EV"]
    for asset in ec.keys() & ev.keys() & titles.keys():
        title_ec, title_ev = titles[asset]
        for claim in ev[asset]:
            if claim["claim_value"] <= 0:
                continue
            citation = claim["citation"]
            present = citation in ec[asset]
            fact = exact_ec_scope.get(asset, {}).get("allowed", {}).get(citation)
            observed = assertion(present, explicitly_answered=asset in original["EC"], exact_exclusion=fact is False)
            triple = (asset, citation)
            if not title_conditional_support(present, True, title_ec, title_ev):
                coarse.add(triple)
            supported = title_conditional_support(observed, True, title_ec, title_ev)
            assert supported == direct_title_scope(observed, True, title_ec, title_ev)
            if not supported:
                bound.add(triple)
            if observed is None:
                relaxed.add(triple)
    return coarse, bound, relaxed


def archived_pairs(db):
    fit, frozen, terminal = bound_stage(fit_pointer(7))
    recorded = read(fit / "matched_decisions.json")
    assert digest(recorded) == terminal["matched_decisions_sha256"]
    path = fit / "candidates" / ORDINARY / OE
    proposal = read(path / "measurements.json")
    decision = recorded["teacher"][ORDINARY][OE]
    assert decision == read(path / "decision.json") and decision["selected"] == "candidate"
    assert digest(proposal["predictions"]) == decision["predictions_sha256"]
    review = read(HANDOFF / "B7_OE_shared_selection_audit_20261119.json")
    checkpoint = ROOT / frozen["checkpoint_root"]
    study = read(checkpoint / "binding.json")
    assert digest(study) == frozen["study_binding_sha256"] == checkpoint.name
    batches = load_roster(study)
    journal = TrainingJournal(checkpoint, study, batches)
    programs = {
        "incumbent": digest(journal.library(M2, 6)["programs"][OE]),
        "proposal": digest(proposal["candidate"]),
    }
    assert programs["incumbent"] == review["incumbent_sha256"]
    assert programs["proposal"] == review["candidate_sha256"] == recorded["relation"][OE]["matched_proposal_sha256"]
    for role, arm in zip(CHOICES, (M2, ORDINARY), strict=True):
        assert digest(journal.library(arm, 7)["programs"][OE]) == programs[role]

    known, bank, grade = set(), {}, {}
    terminals = {"B7_fit": sha(fit / "terminal.json")}
    for batch in (7, 8):
        stage, binding, end = bound_stage(observe_pointer(batch))
        terminals[f"B{batch}_observations"] = sha(stage / "terminal.json")
        grade_path = binding["native_grade_paths"][OE]
        grade[grade_path] = binding["native_grade_sha256"][grade_path]
        views, slots, raw = {}, [], {role: {} for role in CHOICES}
        sources = [s for s in batches[batch - 1] if s["dataset"] == OE]
        assert len(sources) == 4 and all(s["project_split"] == "train" for s in sources)
        for source in sources:
            key = source["key"]
            views[key] = {v["id"]: v for v in source["views"]}
            measured = []
            for role, arm in zip(CHOICES, (M2, ORDINARY), strict=True):
                if batch == 7 and role == "proposal":
                    result = proposal["predictions"][key]
                else:
                    receipt = journal._observations(arm, batch)
                    assert receipt["train_observation_sha256"] == end["observation_receipts"][arm]
                    saved = read(journal.directory(arm, batch) / "predictions" / (digest(key) + ".json"))
                    assert digest(saved) == receipt["predictions"][key] and saved["source"] == key
                    result = saved["result"]
                verify_native(db, source, result, programs[role], known)
                measured.append(result)
                raw[role][key] = {task: row["answer"] for task, row in result["native"].items()}
            slots.extend({"source": key, **row} for row in slot_records(source, *measured))
        bank[batch] = {
            "original_views": views, "raw": raw, "raw_slots": compare_slots(slots),
            "original_candidate_conflicts": {
                (row["source"], row["asset"], row["citation"]) for row in slots
                if row["ports"]["candidate"] == [False, True]
            },
        }
    (grade_path, grade_hash), = grade.items()
    assert "train" in Path(grade_path).parts and sha(ROOT / grade_path) == grade_hash
    return bank, terminals, programs, len(known), ROOT / grade_path


def replay(board):
    original = board["original_views"]
    scoped, edits = {}, 0
    for key, pair in original.items():
        scoped[key] = {}
        for family, view in pair.items():
            scoped[key][family], count = normalized_scope(view)
            edits += count
    public = {
        role: {key: {family: public_controls(scoped[key][family], answer)
                     for family, answer in pair.items()} for key, pair in rows.items()}
        for role, rows in board["raw"].items()
    }
    board.update(views=scoped, common_controls=public, normalized_alias_occurrences=edits)


def conflict_summary(board, mode):
    titles = {key: aligned_titles(views) for key, views in board["views"].items()}
    facts = {key: view_facts(views["EC"]) if mode == "category" else {} for key, views in board["views"].items()}
    rows = {role: [set(), set(), set()] for role in CHOICES}
    for role in CHOICES:
        for key, predictions in board[mode][role].items():
            receipt = compare_conflicts(board["raw"][role][key], predictions, titles[key], facts[key])
            for acc, slots in zip(rows[role], receipt, strict=True):
                acc.update((key, *slot) for slot in slots)
    results = {}
    for index, name in enumerate(("row_presence", "bound_assertion", "unresolved_categories")):
        a, b = (rows[role][index] for role in CHOICES)
        results[name] = {"incumbent": len(a), "proposal": len(b), "new_in_proposal": len(b - a)}
    if mode == "category":
        results["new_bound_conflicts_match_original_candidate_conflicts"] = (
            rows["proposal"][1] - rows["incumbent"][1] == board["original_candidate_conflicts"]
        )
    return results


def report():
    assert all(sha(UPSTREAM / "source" / name) == old for name, old in RENDERER.items())
    for values in itertools.product((None, False, True), repeat=4):
        assert title_conditional_support(*values) == direct_title_scope(*values)
    with sqlite3.connect(LEDGER.as_uri() + "?mode=ro", uri=True) as db:
        counts = dict(db.execute("select status,count(*) from calls group by status"))
        assert not counts.get("reserved")
        bank, terminals, programs, responses, grade = archived_pairs(db)
    prior = read(PUBLIC_B7)
    assert bank[7]["raw_slots"] == prior["B7_joint_native_port_stats"]
    assert prior["B7_rechecked_literal_gate"] == "eligible_train_update"
    for item in bank.values():
        replay(item)
    prepare_routes(bank)
    for item in bank.values():
        item["category"], item["within_category"] = prepare_category(item["views"], item["wildcard"])
        item["conflict_summary"] = {mode: conflict_summary(item, mode) for mode in REGIMES}

    # Determine compatibility on B7 before loading the archived native grades.
    block = bank[7]["conflict_summary"]
    observed = block["category"]["bound_assertion"]
    assert block["category"]["new_bound_conflicts_match_original_candidate_conflicts"]
    reference = observed["incumbent"] == 0 and observed["proposal"] > 0
    labels = read(grade)
    boards = {}
    for batch, item in bank.items():
        boards[str(batch)] = {
            "metrics": {mode: score(item["original_views"], item[mode], labels) for mode in ("raw", *REGIMES)},
            "conflicts": item["conflict_summary"],
            "within_category": item["within_category"],
            "normalized_filing_alias_occurrences": item["normalized_alias_occurrences"],
        }
    raw_b8 = boards["8"]["metrics"]["raw"]
    for role in CHOICES:
        frame = "candidate" if role == "proposal" else role
        assert raw_b8[role]["F1"] == prior["B8_sealed_forward"]["native_EC_EV"][frame]
    assert all(boards["7"]["metrics"][mode]["proposal"]["paired_vs_incumbent"]["mean_change"] > 0
               for mode in ("raw", *REGIMES))
    outcome = {
        "shared": "incumbent" if reference else "proposal",
        "direct": "incumbent" if reference else "proposal",
        "independent": "proposal",
    }
    return {
        "status": "settled_OE_B7_B8_shared_assertion_coverage",
        "archive_terminals_sha256": terminals,
        "program_sha256": programs,
        "native_grade_sha256": sha(grade),
        "observed_physical_responses_verified": responses,
        "prior_b7_report_sha256": sha(PUBLIC_B7),
        "renderer_source_sha256": RENDERER,
        "runner_sha256": sha(Path(__file__)),
        "reused_control_source_sha256": {
            str(p.relative_to(ROOT)): sha(p) for p in (
                ROOT / "experiments/convergence_revision5_oe_category_scope.py",
                ROOT / "experiments/convergence_revision5_oe_wildcard_replay.py",
                ROOT / "experiments/convergence_revision5_oe_task_route.py",
                ROOT / "legal_skill_guard/paired_interfaces/convergence_oe_title_scope.py",
            )
        },
        "B7_replayed_choices_after_common_checks": outcome,
        "same_information_formula_matches_all_81_finite_states": True,
        "batch": boards,
        "continuation_ledger": counts,
        "new_requests": 0,
        "DEV_or_TEST_content_or_labels_used": False,
        "scope": "retrospective on unchanged B7 and B8 TRAIN executor reads",
    }


if __name__ == "__main__":
    outcome = report()
    immutable_json(TABLE, outcome)
    print(json.dumps({k: v for k, v in outcome.items() if k != "batch"}, sort_keys=True), flush=True)
