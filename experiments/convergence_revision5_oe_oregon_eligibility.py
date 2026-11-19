"""Trace the two B7 eligibility conflicts through explicit Oregon asset scopes."""

import argparse
from collections import Counter
from itertools import product
from pathlib import Path
import sqlite3

from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from experiments.convergence_revision5_oe_assertion_coverage import (
    CHOICES, archived_pairs, conflict_summary, normalized_scope, replay,
)
from experiments.convergence_revision5_oe_category_scope import (
    PERSONAL_USE, category, full_archive, prepare_category,
)
from experiments.convergence_revision5_oe_task_route import aligned_titles, score
from experiments.convergence_revision5_oe_wildcard_replay import EV_SCOPE, cents, prepare_routes
from legal_skill_guard.paired_interfaces.convergence_ev_inventory import public_inventory
from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory
from legal_skill_guard.paired_interfaces.shared_semantics import (
    SourceCase, Theory, allowed_relation, matches_assertions, source_variant,
)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


OE = "OpenExempt"
PICTURES = "Or. Rev. Stat. § 18.345(1)(a)"
VEHICLE = "Or. Rev. Stat. § 18.345(1)(d)"
HOUSEHOLD = "Or. Rev. Stat. § 18.345(1)(f)"
CLAUSES = {
    PICTURES: "Books, pictures and musical instruments to the value of $600.",
    VEHICLE: (
        "A vehicle to the value of $3,000. As used in this paragraph “vehicle” "
        "includes an automobile, truck, trailer, truck and trailer or other motor vehicle."
    ),
    HOUSEHOLD: (
        "Household goods, furniture, radios, a television set and utensils all to the total value of $3,000, "
        "if the judgment debtor holds the property primarily for the personal, family or household use of the "
        "judgment debtor; provisions actually provided for family use and necessary for the support of a "
        "householder and family for 60 days and also 60 days' supply of fuel."
    ),
}
HOME = BASE / "revision5_OE_oregon_eligibility_20261119"
TABLE = ROOT / "reports/legal_skill_convergence_20261117/paper/tables/REVISION5_OE_OREGON_ELIGIBILITY_20261119.json"
PRIOR = TABLE.with_name("REVISION5_OE_ASSERTION_COVERAGE_20261119.json")


def bound_clauses(view):
    text = view["public"]["original_input"]
    scope = supplied_jurisdiction_scope(text)
    if not scope:
        return set()
    statutes = text.partition("\nStatutes:\n")[2].partition("\nSolved Reasoning Steps:\n")[0]
    provided = [block.partition("\n")[::2] for block in statutes.strip().split("\n\n")]
    return {code for code, clause in CLAUSES.items()
            if code in scope["citations"] and [text for key, text in provided if key == code] == [clause]}


def local_terms(view):
    clauses = bound_clauses(view)
    if not clauses & {VEHICLE, PICTURES}:
        return set(), {}
    scoped, _ = normalized_scope(view)
    text = scoped["public"]["original_input"]
    try:
        filers, inventory, _ = title_inventory(text)
    except ValueError:
        return set(), {}
    independent = view["id"] == "EC" or EV_SCOPE in text.partition("\nStatutes:\n")[0]
    excludes, instruments = set(), {}
    for row in inventory.values():
        name = row["description"]
        kind = category(name)
        if VEHICLE in clauses and kind in ("instrument", "art"):
            excludes.add(name)
        if (PICTURES in clauses and kind == "instrument" and filers == 1 and independent
                and row["filing_interest_established"] is True):
            value = cents(row["amount_quote"])
            if value > 0:
                instruments[name] = min(value, 60000) / 100
    return excludes, instruments


def repair(view, answer):
    if not isinstance(answer, dict):
        return answer
    excludes, instruments = local_terms(view)
    family = view["id"]
    output = {}
    for name, claims in answer.items():
        output[name] = [
            row for row in claims if name not in excludes or
            (row if family == "EC" else row["citation"]) != VEHICLE
        ]
    for name, value in instruments.items():
        rows = output.setdefault(name, [])
        if family == "EC":
            if PICTURES not in rows:
                rows.append(PICTURES)
        else:
            output[name] = [row for row in rows if row["citation"] != PICTURES] + [
                {"citation": PICTURES, "claim_value": value}
            ]
    return output


def outputs(views, bank):
    return {arm: {key: {family: repair(views[key][family], answer) for family, answer in pair.items()}
                  for key, pair in rows.items()} for arm, rows in bank.items()}


def project_usage(values, law):
    eligibility = values["household_category"] and values["personal_use"]
    if values["query"] == "EC":
        return eligibility
    return min(values["dollars"], law["cap_dollars"]) if eligibility else 0


def usage_edit(root, views, asset):
    """Change only the named asset's use while holding category and value fixed."""
    assert aligned_titles(views)[asset][0] is True
    scope = digest({HOUSEHOLD: CLAUSES[HOUSEHOLD]})
    proof = digest({"statute": CLAUSES[HOUSEHOLD], "instruction": PERSONAL_USE,
                    "views": {fam: digest(v["public"]) for fam, v in views.items()}})
    theory = Theory(
        {scope: [{"cap_dollars": 3000}]},
        {root: [{"household_category": False}, {"household_category": True}]},
        project_usage, sha(Path(__file__)),
        provenance=({"kind": "explicit_source", "evidence_sha256": proof},),
        allowed_edits=frozenset({"personal_use"}),
    )
    facts = {}
    cases = []
    for family, view in views.items():
        original = view["public"]["original_input"]
        instruction = original.partition("\nStatutes:\n")[0]
        assert PERSONAL_USE in instruction and HOUSEHOLD in bound_clauses(view)
        assert family == "EC" or EV_SCOPE in instruction
        inventory = public_inventory(original)
        slot, = (k for k, r in inventory.items() if r["description"] == asset)
        row = inventory[slot]
        assert original.count(row["source_quote"]) == row["source_quote"].count(asset) == 1
        first = original.index(row["source_quote"]) + row["source_quote"].index(asset)
        amount = cents(row["amount_quote"]) / 100
        case = SourceCase(
            root + ":" + family, root, scope, {"text": original},
            {"personal_use": True, "query": family, "dollars": amount},
            spans={"personal_use": ("text", first, first + len(asset))},
        )
        resale = asset + " held exclusively for resale in the judgment debtor's business"
        patch = source_variant(
            case, theory, {"personal_use": False}, {"personal_use": {True: asset, False: resale}.__getitem__}
        )
        assert patch["status"] == "REALIZABLE"
        changed = patch["case"].public["text"]
        revised = public_inventory(changed)
        assert revised.keys() == inventory.keys() and supplied_jurisdiction_scope(changed) == supplied_jurisdiction_scope(original)
        assert all(r == revised[k] for k, r in inventory.items() if r["source_quote"] != row["source_quote"])
        for k, r in inventory.items():
            assert revised[k]["amount_quote"] == r["amount_quote"]
            assert revised[k]["description"] == (resale if k == slot else r["description"])
        facts[family] = digest(patch["receipt"])
        cases.append((case, patch["case"]))
    ec, ev = cases
    group = (ec[0], ev[0], ec[1], ev[1])
    allowed = {mode: list(allowed_relation(theory, group, mode=mode)["signatures"].values())
               for mode in ("shared", "independent_completions")}
    claim = min(ec[0].primitives["dollars"], 3000)
    states = tuple(product((None, False, True), (None, 0, claim), (None, False, True), (None, 0, claim)))
    for observed in states:
        e, v, resale_e, resale_v = observed
        direct = resale_e in (None, False) and resale_v in (None, 0) and (
            e is None or v is None or e == (v == claim)
        )
        assert any(matches_assertions(list(observed), signature) for signature in allowed["shared"]) == direct
    return {"source_edit_receipt_sha256": facts, "counts": {m: len(v) for m, v in allowed.items()},
            "shared_signatures": allowed["shared"], "direct_matches_shared_on_all_states": len(states),
            "household_category_unresolved_in_source": True, "edited_model_reads": 0}


def focus_scores(views, before, after, labels):
    report = {}
    for arm, rows in before.items():
        scores = {f: [] for f in ("EC", "EV")}
        for key, pair in rows.items():
            for family, answer in pair.items():
                revised = after[arm][key][family]
                if revised != answer:
                    vals = [grade_view(OE, views[key][family], labels[key][family], plan)["official_metrics"]["metrics"]
                            for plan in (answer, revised)]
                    scores[family].append({
                        "native_before_after": [v["f1"] for v in vals],
                        "secondary_full_output_before_after": [v["full_output_f1"] for v in vals],
                        "secondary_false_positive_counts_before_after": [v["full_output_claim_fp"] for v in vals],
                    })
        report[arm] = {f: {"changed_sources": len(a), "receipts": a,
                           "paired_native_delta_over_all_mothers": sum(
                               r["native_before_after"][1] - r["native_before_after"][0] for r in a
                           ) / len(rows)} for f, a in scores.items()}
    return report


def coverage(views):
    counts = Counter(mothers=len(views))
    for row in views.values():
        for view in row.values():
            excludes, instruments = local_terms(view)
            counts["views_in_scope"] += bool(excludes or instruments)
            counts["mandatory_vehicle_exclusions"] += len(excludes)
            counts["title_supported_instrument_claims"] += len(instruments)
    return dict(counts)


def training():
    with sqlite3.connect(LEDGER.as_uri() + "?mode=ro", uri=True) as db:
        assert not db.execute("select 1 from calls where status='reserved'").fetchone()
        bank, seals, versions, physical, grade = archived_pairs(db)
    for row in bank.values():
        replay(row)
    prepare_routes(bank)
    prior = read(PRIOR)
    assert (seals == prior["archive_terminals_sha256"] and versions == prior["program_sha256"]
            and physical == prior["observed_physical_responses_verified"])
    earlier = bank[7]
    conflict_key, art, _ = next(row for row in earlier["original_candidate_conflicts"] if row[2] == HOUSEHOLD)
    (_, instrument, _) = next(row for row in earlier["original_candidate_conflicts"] if row[2] == VEHICLE)
    assert category(art) == "art" and category(instrument) == "instrument"
    edit = usage_edit(conflict_key, earlier["original_views"][conflict_key], art)
    receipts = {}
    labels = read(grade)
    for batch, row in bank.items():
        common, _ = prepare_category(row["views"], row["wildcard"])
        assert score(row["original_views"], common, labels) == prior["batch"][str(batch)]["metrics"]["category"]
        corrected = outputs(row["views"], common)
        before = conflict_summary({**row, "category": common}, "category")["bound_assertion"]
        after = conflict_summary({**row, "category": corrected}, "category")["bound_assertion"]
        receipts[batch] = {
            "scope_conflicts_before_after": [before, after],
            "after_direct_controls": score(row["original_views"], corrected, labels),
            "changed_views": focus_scores(row["original_views"], common, corrected, labels),
        }
    target = labels[conflict_key]
    household_reference = [HOUSEHOLD in target["EC"]["answer"][art], any(
        row["citation"] == HOUSEHOLD for row in target["EV"]["answer"][art]
    )]
    assert household_reference == [True, True] and file_access_is_train(grade)
    return {"B7_B8_archived_comparisons": receipts, "usage_edit_witness": edit,
            "remaining_B7_reference_assertions_for_household": household_reference,
            "archived_physical_responses_verified": physical, "bound_TRAIN_terminals": seals,
            "TRAIN_grade_sha256": sha(grade)}


def file_access_is_train(grade):
    return "train" in grade.parts and "test" not in grade.parts


def run(partition):
    binding = {"rule_sha256": sha(Path(__file__)), "prior_comparison_sha256": sha(PRIOR),
               "policy": "apply vehicle exclusion and literal musical-instrument category to both programs"}
    folder = HOME / digest(binding)
    if partition == "train":
        result = training()
        views, native, grade, meta = full_archive("train")
        assert file_access_is_train(grade)
        result["full_TRAIN_coverage"] = coverage(views)
        common, _ = prepare_category(views, native)
        result["full_TRAIN_scores"] = focus_scores(views, common, outputs(views, common), read(grade))
        result["full_TRAIN_archive_receipt"] = {k: meta[k] for k in ("EV_archive_terminal_sha256", "ev_physical", "ec_physical")}
        immutable_json(folder / "binding.json", binding)
        immutable_json(folder / "TRAIN.json", result)
        print(result["full_TRAIN_coverage"], flush=True)
    else:
        assert read(folder / "binding.json") == binding
        path = folder / "TRAIN.json"
        views, native, grade, meta = full_archive("dev")
        assert "dev" in grade.parts
        common, _ = prepare_category(views, native)
        changed = outputs(views, common)
        result = {
            "status": "settled_Oregon_category_and_usage_replay",
            "binding": binding, "TRAIN": read(path), "TRAIN_receipt_sha256": sha(path),
            "DEV": {"coverage": coverage(views), "scores": focus_scores(views, common, changed, read(grade)),
                    "native_predictions_identical": common == changed,
                    "DEV_archive_receipt": {k: meta[k] for k in ("EV_archive_terminal_sha256", "ev_physical", "ec_physical")}},
            "new_requests": 0, "TEST_opened": False, "continuous_ledger": meta["ledger"],
        }
        immutable_json(TABLE, result)
        print(result["DEV"], flush=True)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("partition", choices=("train", "dev"))
    run(cli.parse_args().partition)
