"""Replay the published OpenExempt EV task rule with a fresh federal allowance per claim."""

import argparse
import json
import re
import sqlite3
from collections import Counter
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

from experiments.convergence_formal_b1_observe import POINTER as B1_OBSERVATION
from experiments.convergence_formal_curves import pointer as dev_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_cni_nonsolicitation import bound_stage
from experiments.convergence_revision5_oe_native_amount_bound import (
    ARMS,
    BOOTSTRAP,
    OE,
    ev_view,
    load_roster,
)
from experiments.convergence_revision5_oe_task_route import (
    FAMILIES,
    OPTIONS,
    aligned_titles,
    conflicts,
    original_bank,
    score,
    select,
    source_checked_outputs,
)
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import (
    supplied_jurisdiction_scope,
)
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory
from legal_skill_guard.paired_interfaces.shared_semantics import (
    SourceCase,
    Theory,
    allowed_relation,
)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE / "revision5_OE_wildcard_replay_20261119"
POINTER = HANDOFF / "revision5_OE_wildcard_TRAIN_current.json"
CITATION = "11 U.S.C. § 522(d)(5)"
HOMESTEAD = "11 U.S.C. § 522(d)(1)"
JOINT_APPLY = "11 U.S.C. § 522(m)"
JOINT_CLAUSE = (
    "Subject to the limitation in subsection (b), this section shall apply separately "
    "with respect to each debtor in a joint case."
)
JOINT_FACTS = (
    "If the task involves a married couple, assume all assets mentioned are jointly owned, "
    "with each spouse holding an equal undivided interest, unless explicitly stated otherwise."
)
EV_SCOPE = "Consider each asset-exemption pair independently, without factoring in aggregate values across multiple assets."
DOLLARS = r"\$([0-9][0-9,]*)"
WILDCARD = re.compile(
    rf"The debtor's aggregate interest in any property, not to exceed in value {DOLLARS} "
    rf"plus up to {DOLLARS} of any unused amount of the exemption provided "
    r"under paragraph \(1\) of this subsection\."
)
RESIDENCE = re.compile(rf"The debtor's aggregate interest, not to exceed {DOLLARS} in value, in ")


def cents(token):
    return int(Decimal(token.replace("$", "").replace(",", "")) * 100)


def claimed_at_fresh_state(value, limits):
    """Draw base and unused residence allowance from a fresh state."""
    amount = min(value, limits["base"])
    return amount + min(value - amount, limits["fallback"], limits["residence"])


def direct_claim(value, limits):
    return min(value, limits["base"] + min(limits["fallback"], limits["residence"]))


def native_bounds(view):
    text = view["public"]["original_input"]
    scope = supplied_jurisdiction_scope(text)
    if scope is None or CITATION not in scope["citations"]:
        return None
    instruction, _, statutes = text.partition("\nStatutes:\n")
    if view["id"] == "EV" and EV_SCOPE not in instruction:
        return None
    statutes = statutes.partition("\nSolved Reasoning Steps:\n")[0]
    blocks = [block.partition("\n")[::2] for block in statutes.strip().split("\n\n")]
    wanted = {CITATION, HOMESTEAD, JOINT_APPLY}
    parts = {name: body for name, body in blocks if name in wanted}
    if set(parts) != wanted or sum(name in wanted for name, _ in blocks) != len(parts):
        return None
    rule = WILDCARD.fullmatch(parts[CITATION])
    residence = RESIDENCE.match(parts[HOMESTEAD])
    if rule is None or residence is None:
        return None
    try:
        filers, inventory, _ = title_inventory(text)
    except ValueError:
        return None
    if filers == 2 and (parts[JOINT_APPLY] != JOINT_CLAUSE or JOINT_FACTS not in instruction):
        return None
    limits = {
        name: filers * cents(value)
        for name, value in zip(
            ("base", "fallback", "residence"), (*rule.groups(), residence[1]), strict=True
        )
    }
    assets = {
        row["description"]: cents(row["amount_quote"])
        for row in inventory.values()
        if (filers == 2 or row["filing_interest_established"] is True)
        and cents(row["amount_quote"]) > 0
    }
    return {
        "assets": assets,
        "limits": limits,
        "filers": filers,
        "inventory_count": len(inventory),
        "law_sha256": digest(parts),
        "jurisdiction_scope_sha256": digest(scope),
    }


def reference(values, law):
    return claimed_at_fresh_state(values["asset_value"], law)


def certificate(key, view, bounds):
    """Prove the source-derived claim vector and compare it with local arithmetic."""
    assets = bounds["assets"]
    if not assets:
        return {}
    scope = digest([bounds["law_sha256"], bounds["jurisdiction_scope_sha256"], bounds["limits"]])
    solver_sha = sha(Path(__file__))
    provenance = ({"kind": "explicit_source", "evidence_sha256": digest(view["public"])},)
    theory = Theory(
        {scope: [bounds["limits"]]}, {key: [{}]}, reference, solver_sha, provenance=provenance
    )
    queries = [
        SourceCase(
            key + ":" + str(i),
            key,
            scope,
            {"public_sha256": digest(view["public"])},
            {"asset_value": value},
        )
        for i, value in enumerate(assets.values())
    ]
    (vector,) = allowed_relation(theory, queries)["signatures"].values()
    assert list(vector) == [direct_claim(value, bounds["limits"]) for value in assets.values()]
    return dict(zip(assets, vector, strict=True))


def complete_wildcard(answer, family, known):
    if not isinstance(answer, dict) or not known:
        return answer
    result = deepcopy(answer)
    for asset, amount in known.items():
        original = result.get(asset, [])
        if family == "EC":
            if CITATION not in original:
                result[asset] = [*original, CITATION]
        else:
            current = [claim for claim in original if claim["citation"] == CITATION]
            correction = {"citation": CITATION, "claim_value": amount / 100}
            if current != [correction]:
                result[asset] = [c for c in original if c["citation"] != CITATION] + [correction]
    return result


def record_coverage(bounds):
    supported = [row for row in bounds.values() if row is not None]
    return {
        "supported_mothers": len(supported),
        "claims_with_title_and_rule": sum(len(row["assets"]) for row in supported),
        "supported_filer_counts": dict(Counter(str(row["filers"]) for row in supported)),
        "fresh_claims_exceeding_a_single_joint_budget": sum(
            sum(direct_claim(value, row["limits"]) for value in row["assets"].values())
            > direct_claim(sum(row["assets"].values()), row["limits"])
            for row in supported
        ),
    }


def old_amount_bank(partition):
    receipt = read(HANDOFF / "revision5_OE_scoped_policy_replay_terminal_20261119.json")
    prior = receipt["comparison_artifacts"][partition.upper() + "_amount_bound"]
    artifact = ROOT / prior["path"]
    assert sha(artifact / "terminal.json") == prior["terminal_sha256"]
    terms, lock = read(artifact / "terminal.json"), read(artifact / "binding.json")
    runner = ROOT / "experiments/convergence_revision5_oe_native_amount_bound.py"
    assert lock["runner_sha256"] == sha(runner) and digest(lock) == artifact.name
    assert terms["predictions_sha256"] == sha(artifact / "predictions.json")
    checkpoint = ROOT / read(BOOTSTRAP)["artifact_root"]
    study = read(checkpoint / "binding.json")
    assert digest(study) == checkpoint.name
    if partition == "train":
        sources = [s for batch in load_roster(study) for s in batch]
        _, stage, _ = bound_stage(B1_OBSERVATION)
        grade = ROOT / stage["native_grade_paths"][OE]
    else:
        _, stage, _ = bound_stage(dev_pointer(8))
        assert stage["checkpoint_binding_sha256"] == checkpoint.name
        b0 = ROOT / stage["b0_dev_data_root"]
        sources = read(b0 / "public_DEV_sources.json")
        assert digest(sources) == read(b0 / "binding.json")["DEV_public_sha256"]
        grade = ROOT / study["grading_paths"][OE]
    cases = {row["key"]: row for row in sources if row["dataset"] == OE}
    assert len(cases) == (32 if partition == "train" else 16)
    assert all(row["project_split"] == partition for row in cases.values())
    assert lock["source_cluster_sha256"] == digest(cases)
    assert partition in grade.parts and lock["grader_sha256"] == sha(grade)
    bank = read(artifact / "predictions.json")
    assert bank.keys() == set(ARMS)
    assert all(rows.keys() == cases.keys() for rows in bank.values())
    return cases, bank, grade, prior["terminal_sha256"], terms["physical_responses_verified"]


def native_scores(views, predictions, labels):
    scored = {}
    for arm, rows in predictions.items():
        measurements = {mode: [] for mode in ("original", "asset_bound", "wildcard")}
        for key, row in rows.items():
            if not row["handled"]:
                continue
            grades = {
                mode: grade_view(OE, views[key], labels[key]["EV"], row[mode])["grade"]
                for mode in measurements
            }
            if any(value is None for value in grades.values()):
                continue
            for mode, result in grades.items():
                measurements[mode].append({"source": key, "view": "EV", "grade": result})
        count = len(measurements["original"])
        scored[arm] = {
            "common_scorable": count,
            "changed_mothers_vs_asset_bound": sum(
                r["asset_bound"] != r["wildcard"] for r in rows.values()
            ),
            "F1": {
                mode: sum(r["grade"] for r in records) / count
                for mode, records in measurements.items()
            },
            "paired_wildcard_vs_asset_bound": paired_source_effect(
                measurements["asset_bound"], measurements["wildcard"]
            ),
        }
    return scored


def prepare_routes(book):
    for record in book.values():
        scoped = record["common_controls"]
        views = record["views"]
        known = {
            key: {
                family: certificate(key, view, bounds) if (bounds := native_bounds(view)) else {}
                for family, view in pair.items()
            }
            for key, pair in views.items()
        }
        titles = {key: aligned_titles(view) for key, view in views.items()}
        rules = {
            mode: {
                key: {
                    family: complete_wildcard(pair[family], family, known[key][family])
                    for family in FAMILIES
                }
                for key, pair in by_key.items()
            }
            for mode, by_key in scoped.items()
        }
        witnesses = {
            mode: {
                (pos, *violation)
                for pos, (key, pair) in enumerate(by_key.items())
                for violation in conflicts(pair, titles[key])
            }
            for mode, by_key in rules.items()
        }
        record["wildcard"] = rules
        record["wildcard_conflicts"] = witnesses
        record["wildcard_facts"] = sum(
            len(assets) for pair in known.values() for assets in pair.values()
        )


def route_scores(out, book, labels):
    first, forward = (book[b] for b in (6, 7))
    calibration = score(first["views"], first["wildcard"], labels)
    choice = select(calibration, first["wildcard_conflicts"])
    immutable_json(out / "locked_B6_choice.json", {"choice": choice})
    next_scores = score(forward["views"], forward["wildcard"], labels)
    routed, kept = source_checked_outputs(
        forward["wildcard"], forward["wildcard_conflicts"], list(forward["views"]), choice
    )
    checked = score(
        forward["views"], {"incumbent": forward["wildcard"]["incumbent"], "routed": routed}, labels
    )["routed"]
    return {
        "B6_calibration": calibration,
        "B6_choice": choice,
        "B7_forward": next_scores,
        "B7_source_checked_route": checked,
        "B7_source_checked_proposal_positions": kept,
        "B7_new_conflicts_on_B6_route": len(
            forward["wildcard_conflicts"][choice] - forward["wildcard_conflicts"]["incumbent"]
        ),
        "source_bound_wildcard_claims": {str(b): row["wildcard_facts"] for b, row in book.items()},
    }


def run(partition):
    cases, baseline, grade, prior, reused = old_amount_bank(partition)
    views = {key: ev_view(source) for key, source in cases.items()}
    bounds = {key: native_bounds(view) for key, view in views.items()}
    known = {
        key: certificate(key, views[key], value) if value else {} for key, value in bounds.items()
    }
    predictions = {}
    for arm, rows in baseline.items():
        predictions[arm] = {
            key: {**row, "wildcard": complete_wildcard(row["asset_bound"], "EV", known[key])}
            for key, row in rows.items()
        }
    book = route_meta = train_terminal = None
    if partition == "train":
        book, route_grade, stage_refs, route_meta, programs = original_bank()
        assert grade == route_grade and set(OPTIONS) == book[6]["common_controls"].keys()
        prepare_routes(book)
    else:
        stage_refs, programs = {}, ()
        pointer = read(POINTER)
        train = ROOT / pointer["artifact_root"]
        train_terminal = sha(train / "terminal.json")
        assert pointer["terminal_sha256"] == train_terminal
        assert read(train / "binding.json")["runner_sha256"] == sha(Path(__file__))
    with sqlite3.connect(LEDGER.as_uri() + "?mode=ro", uri=True) as db:
        ledger = dict(db.execute("select status, count(*) from calls group by status"))
        assert not ledger.get("reserved")
    binding = {
        "partition": partition,
        "runner_sha256": sha(Path(__file__)),
        "source_sha256": digest(cases),
        "prior_archive_terminal_sha256": prior,
        "TRAIN_terminal_sha256": train_terminal,
        "B6_B7_stage_terminals": stage_refs,
        "B6_B7_program_hashes": list(programs),
        "grade_sha256": sha(grade),
    }
    out = HOME / partition / digest(binding)
    immutable_json(out / "binding.json", binding)
    immutable_json(out / "predictions.json", predictions)
    immutable_json(out / "certified_claims.json", known)
    if book:
        for batch, row in book.items():
            immutable_json(out / f"B{batch}_predictions.json", row["wildcard"])
    results = {
        "partition": partition,
        "mothers": len(cases),
        "new_requests": 0,
        "ledger": ledger,
        "bound_archived_response_count": reused,
        "predictions_sha256": sha(out / "predictions.json"),
        "coverage": record_coverage(bounds),
        "matched_direct_claims_equal": True,
    }
    labels = read(grade)
    results["native_EV"] = native_scores(views, predictions, labels)
    if book:
        results["B6_B7_route"] = route_scores(out, book, labels)
        results["B6_B7_route"]["matched_physical_count"] = route_meta["physical_responses"]
    immutable_json(out / "terminal.json", results)
    if partition == "train":
        write_status(
            out, {"status": "TRAIN_settled", "terminal_sha256": sha(out / "terminal.json")}, POINTER
        )
    print(
        json.dumps({"artifact_root": str(out.relative_to(ROOT)), **results}, sort_keys=True),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("partition", choices=("train", "dev"))
    run(parser.parse_args().partition)
