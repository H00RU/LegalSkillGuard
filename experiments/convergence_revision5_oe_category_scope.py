"""Check Oregon and federal exemption scopes on the original OpenExempt ports."""

import argparse
import json
import re
import sqlite3
from collections import Counter
from copy import deepcopy
from pathlib import Path
from statistics import mean

from experiments.convergence_formal_b1_observe import POINTER as FIRST
from experiments.convergence_formal_curves import pointer as dev_pointer
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_cni_nonsolicitation import bound_stage
from experiments.convergence_revision5_cni_oral_dev import verify_wire
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from experiments.convergence_revision5_oe_native_amount_bound import (
    ARMS,
    BOOTSTRAP,
    OE,
    TrainingJournal,
    load_roster,
)
from experiments.convergence_revision5_oe_task_route import (
    FAMILIES,
    aligned_titles,
    conflicts,
    original_bank,
    public_controls,
    score,
    select,
)
from experiments.convergence_revision5_oe_wildcard_replay import (
    EV_SCOPE,
    JOINT_APPLY,
    JOINT_CLAUSE,
    JOINT_FACTS,
    cents,
    certificate,
    complete_wildcard,
    native_bounds,
    old_amount_bank,
    prepare_routes,
)
from legal_skill_guard.paired_interfaces.convergence_effects import paired_source_effect
from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import (
    supplied_jurisdiction_scope,
)
from legal_skill_guard.paired_interfaces.convergence_oe_title_scope import title_inventory
from legal_skill_guard.paired_interfaces.formal_evaluation import verify
from legal_skill_guard.paired_interfaces.shared_semantics import (
    SourceCase,
    Theory,
    allowed_relation,
    matches_assertions,
)
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest

HOME = BASE / "revision5_OE_category_scope_20261119"
POINTER = HANDOFF / "revision5_OE_category_scope_TRAIN_current.json"
OREGON = "Or. Rev. Stat. § 18.345(1)(b)"
FEDERAL = "11 U.S.C. § 522(d)(3)"
OREGON_TEXT = "Wearing apparel and jewelry to the value of $1,800."
FEDERAL_TEXT = (
    "The debtor's interest, not to exceed $700 in value in any particular item or $14,875 in aggregate value, "
    "in household furnishings, household goods, wearing apparel, appliances, books, animals, crops, or musical "
    "instruments, that are held primarily for the personal, family, or household use of the debtor or a dependent of the debtor."
)
PERSONAL_USE = "Assume all assets are held for the personal use of the Debtor(s), unless explicitly stated otherwise."
CLAUSES = {OREGON: OREGON_TEXT, FEDERAL: FEDERAL_TEXT}
LIMITS = {OREGON: 180000, FEDERAL: 70000}
CATEGORY_RULES = {
    OREGON: {"apparel": True, "jewelry": True, "instrument": False, "art": False},
    FEDERAL: {"apparel": True, "instrument": True},
}
NOUNS = {
    "apparel": r"\b(?:shawl|scarf|business suit|dress shirt|blouse|pants|coat|jacket|skirt|sweater|vest)\b",
    "jewelry": r"\b(?:bracelet|necklace|earrings?)\b",
    "instrument": r"\b(?:flute|guitar|violin|piano|clarinet|trumpet|saxophone|drum)\b",
    "art": r"\bframed canvas print\b",
}


def category(description):
    # A compound with two category heads has no unambiguous local type here.
    words = description.partition(" with ")[0].partition(" in ")[0]
    matches = [kind for kind, pattern in NOUNS.items() if re.search(pattern, words, re.I)]
    return matches[0] if len(matches) == 1 else None


def eligibility(values, law):
    return law["category_claims"][values["citation"]] and values["title"]


def direct_supported(allowed, title, observations):
    permitted_title = {title} if title is not None else {False, True}
    for citation, eligible in observations.items():
        if eligible is None:
            continue
        if not allowed[citation]:
            if eligible:
                return False
        else:
            permitted_title.intersection_update({eligible})
    return bool(permitted_title)


def view_facts(view):
    text = view["public"]["original_input"]
    premise = supplied_jurisdiction_scope(text)
    if premise is None or not set(CLAUSES) & set(premise["citations"]):
        return {}
    instruction, _, blocks = text.partition("\nStatutes:\n")
    if view["id"] == "EV" and EV_SCOPE not in instruction:
        return {}
    statutes = [
        b.partition("\n")[::2]
        for b in blocks.partition("\nSolved Reasoning Steps:\n")[0].strip().split("\n\n")
    ]
    active = {
        c
        for c, law in CLAUSES.items()
        if c in premise["citations"] and [body for name, body in statutes if name == c] == [law]
    }
    if PERSONAL_USE not in instruction:
        active.discard(FEDERAL)
    if not active:
        return {}
    try:
        filers, assets, _ = title_inventory(text)
    except ValueError:
        return {}
    joint = filers == 2 and JOINT_FACTS in instruction and (JOINT_APPLY, JOINT_CLAUSE) in statutes
    output = {}
    for row in assets.values():
        name = row["description"]
        kind = category(name)
        allowed = {c: CATEGORY_RULES[c][kind] for c in active if kind in CATEGORY_RULES[c]}
        if allowed:
            output[name] = {
                "allowed": allowed,
                "value": cents(row["amount_quote"]),
                "title": True if joint else row["filing_interest_established"],
                "filers": filers,
            }
    return output


def signatures(view, root, asset, facts):
    laws = sorted(facts["allowed"])
    legal_scope = digest([laws, view["public"]])
    alternatives = (False, True) if facts["title"] is None else (facts["title"],)
    theory = Theory(
        {legal_scope: [{"category_claims": facts["allowed"]}]},
        {root: [{"title": p} for p in alternatives]},
        eligibility,
        sha(Path(__file__)),
        provenance=(
            {"kind": "explicit_source", "evidence_sha256": digest([view["public"], asset])},
        ),
    )
    queries = [
        SourceCase(
            f"{root}:{i}",
            root,
            legal_scope,
            {"source_rule_sha256": digest(CLAUSES[c])},
            {"citation": c},
        )
        for i, c in enumerate(laws)
    ]
    relations = {
        mode: list(allowed_relation(theory, queries, mode=mode)["signatures"].values())
        for mode in ("shared", "independent_completions")
    }
    return laws, relations


def verification(view, root, observations, facts):
    counts = Counter()
    for asset, fact in facts.items():
        if not isinstance(observations, dict) or asset not in observations:
            continue
        laws, relations = signatures(view, root, asset, fact)
        claims = (
            set(observations[asset])
            if view["id"] == "EC"
            else {row["citation"] for row in observations[asset] if row["claim_value"] > 0}
        )
        values = [law in claims for law in laws]
        feasible = {
            mode: any(matches_assertions(values, sig) for sig in allowed)
            for mode, allowed in relations.items()
        }
        assert feasible["shared"] == direct_supported(
            fact["allowed"], fact["title"], dict(zip(laws, values, strict=True))
        )
        counts["evaluated_asset_vectors"] += 1
        counts["shared_only_rejections"] += (
            feasible["independent_completions"] and not feasible["shared"]
        )
    return counts


def repair(answer, family, facts):
    if not isinstance(answer, dict) or not facts:
        return answer
    result = deepcopy(answer)
    for asset, fact in facts.items():
        for citation, category_allows in fact["allowed"].items():
            if not category_allows and asset in result:
                if family == "EC":
                    result[asset] = [old for old in result[asset] if old != citation]
                else:
                    result[asset] = [old for old in result[asset] if old["citation"] != citation]
            elif category_allows and fact["title"] is True and fact["value"] > 0:
                if family == "EC":
                    rows = result.setdefault(asset, [])
                    if citation not in rows:
                        rows.append(citation)
                elif fact["filers"] == 1 or fact["value"] <= LIMITS[citation]:
                    rows = result.setdefault(asset, [])
                    expected = {
                        "citation": citation,
                        "claim_value": min(fact["value"], LIMITS[citation]) / 100,
                    }
                    if [row for row in rows if row["citation"] == citation] != [expected]:
                        result[asset] = [row for row in rows if row["citation"] != citation] + [
                            expected
                        ]
    return result


def ec_read(db, source, saved, paid, partition):
    key = source["key"]
    result = saved["result"]
    field = "schema_reads" if "schema_reads" in result else "reads"
    (row,) = (item for item in result[field] if set(item["native"]) == {"EC"})
    assert row["native"]["EC"] == result["native"]["EC"]
    if field == "schema_reads":
        trace = row
    else:
        (trace,) = (t for t in row["execution"]["traces"] if "physical_call_id" in t)
    identity = trace["physical_call_id"]
    if partition == "dev":
        assert verify_wire(db, key, {field: [row], "native": row["native"]}, paid) == row["native"]
    else:
        physical_wire(db, {key}, identity, key)
        paid.add(identity)
    archived = json.loads(
        db.execute("select result from calls where id=?", (identity,)).fetchone()[0]
    )
    if field == "schema_reads":
        assert digest(archived["content"]) == trace["response_sha256"]
    else:
        assert archived["content"] == trace["raw_content"]
    payload = read(Path(archived["artifact_directory"]) / "request.json")["payload"]
    (user,) = (m["content"] for m in payload["messages"] if m["role"] == "user")
    literal = next(v["public"]["original_input"] for v in source["views"] if v["id"] == "EC")
    assert any(json.dumps(literal, ensure_ascii=f) in user for f in (False, True))
    return row["native"]["EC"]["answer"]


def full_archive(partition):
    cases, _, grade, _, _ = old_amount_bank(partition)
    prior = read(HANDOFF / "revision5_OE_wildcard_replay_terminal_20261119.json")[
        "partition_artifacts"
    ][partition]
    stage = ROOT / prior["artifact_root"]
    end = read(stage / "terminal.json")
    assert sha(stage / "terminal.json") == prior["terminal_sha256"]
    assert sha(stage / "predictions.json") == end["predictions_sha256"]
    ev = read(stage / "predictions.json")
    checkpoint = ROOT / read(BOOTSTRAP)["artifact_root"]
    study = read(checkpoint / "binding.json")
    roster = load_roster(study)
    journal = TrainingJournal(checkpoint, study, roster)
    ec = {arm: {} for arm in ARMS}
    paid = set()
    with sqlite3.connect(LEDGER.as_uri() + "?mode=ro", uri=True) as db:
        ledger = dict(db.execute("select status,count(*) from calls group by status"))
        assert not ledger.get("reserved")
        if partition == "train":
            for b, cohort in enumerate(roster, 1):
                _, _, terminal = bound_stage(FIRST if b == 1 else observe_pointer(b))
                for arm in ARMS:
                    registered = journal._observations(arm, b)
                    assert (
                        registered["train_observation_sha256"]
                        == terminal["observation_receipts"][arm]
                    )
                    for source in (s for s in cohort if s["key"] in cases):
                        key = source["key"]
                        saved = read(
                            journal.directory(arm, b) / "predictions" / (digest(key) + ".json")
                        )
                        assert digest(saved) == registered["predictions"][key]
                        ec[arm][key] = ec_read(db, source, saved, paid, partition)
        else:
            _, _, terminal = bound_stage(dev_pointer(8))
            for arm in ARMS:
                directory = checkpoint / "dev" / "B8" / arm
                seal = verify(read(directory / "prediction_seal.json"), "prediction_seal_sha256")
                cell = verify(read(directory / "scores.json"), "cell_sha256")
                assert seal["task_sha256"] == digest(read(directory / "task.json"))
                assert (
                    cell["partition"] == "dev"
                    and cell["cell_sha256"] == terminal["cell_sha256"][arm]
                )
                assert cell["prediction_seal_sha256"] == seal["prediction_seal_sha256"]
                for key, source in cases.items():
                    saved = read(directory / "predictions" / (digest(key) + ".json"))
                    assert (
                        digest(saved) == seal["predictions_sha256"][key]
                        and saved["library_sha256"] == cell["libraries"][OE]
                    )
                    ec[arm][key] = ec_read(db, source, saved, paid, partition)
    assert all(r.keys() == cases.keys() for r in (*ec.values(), *ev.values()))
    views = {key: {v["id"]: v for v in s["views"]} for key, s in cases.items()}
    bank = {}
    for arm in ARMS:
        bank[arm] = {}
        for key, row in views.items():
            answer = ec[arm][key]
            ec_view = row["EC"]
            if isinstance(answer, dict):
                answer = public_controls(ec_view, answer)
                if bounds := native_bounds(ec_view):
                    answer = complete_wildcard(answer, "EC", certificate(key, ec_view, bounds))
            bank[arm][key] = {
                "EC": answer,
                "EV": ev[arm][key]["wildcard"] if ev[arm][key]["handled"] else None,
            }
    return (
        views,
        bank,
        grade,
        {
            "EV_archive_terminal_sha256": prior["terminal_sha256"],
            "ev_physical": end["bound_archived_response_count"],
            "ec_physical": len(paid),
            "ledger": ledger,
        },
    )


def prepare_category(views, banks):
    bounds = {key: {f: view_facts(row[f]) for f in FAMILIES} for key, row in views.items()}
    repairs = {}
    observed = {}
    for arm, bank in banks.items():
        stats = Counter()
        repairs[arm] = {}
        for key, answer in bank.items():
            repairs[arm][key] = {}
            for f in FAMILIES:
                facts = bounds[key][f]
                stats.update(verification(views[key][f], key, answer[f], facts))
                repairs[arm][key][f] = repair(answer[f], f, facts)
        observed[arm] = dict(stats)
    return repairs, observed


def full_scores(views, bank, repaired, labels):
    out = {}
    for arm, rows in bank.items():
        out[arm] = {}
        for f in FAMILIES:
            raw, after = [], []
            for key, native in rows.items():
                before, changed = native[f], repaired[arm][key][f]
                if before is None:
                    continue
                y0 = grade_view(OE, views[key][f], labels[key][f], before)["grade"]
                y1 = grade_view(OE, views[key][f], labels[key][f], changed)["grade"]
                if y0 is not None and y1 is not None:
                    raw.append({"source": key, "view": f, "grade": y0})
                    after.append({"source": key, "view": f, "grade": y1})
            out[arm][f] = {
                "scorable": len(raw),
                "common": mean(r["grade"] for r in raw),
                "category": mean(r["grade"] for r in after),
                "paired": paired_source_effect(raw, after),
            }
    return out


def route_evidence(book, labels, out):
    before, later = (book[b] for b in (6, 7))
    scores = score(before["views"], before["category"], labels)
    choice = select(scores, before["category_conflicts"])
    immutable_json(out / "B6_calibration.json", {"choice": choice, "scores": scores})
    forward = score(later["views"], later["category"], labels)
    prior = later["wildcard_conflicts"]["EC_only"] - later["wildcard_conflicts"]["incumbent"]
    post = later["category_conflicts"]["EC_only"] - later["category_conflicts"]["incumbent"]
    return {
        "B6_route": choice,
        "B6_calibration": scores,
        "B7_after_category": forward,
        "B7_original_four_conflicts_repaired": len(prior - post),
        "B7_new_conflicts_after_category": len(post),
        "scope": "B7 was already inspected to construct the category rule",
    }


def run(partition):
    views, bank, grade, meta = full_archive(partition)
    repaired, observed = prepare_category(views, bank)
    book = None
    if partition == "train":
        book, route_grade, refs, _, programs = original_bank()
        assert grade == route_grade
        prepare_routes(book)
        for cohort in book.values():
            cohort["category"], cohort["category_support"] = prepare_category(
                cohort["views"], cohort["wildcard"]
            )
            titles = {key: aligned_titles(row) for key, row in cohort["views"].items()}
            cohort["category_conflicts"] = {
                arm: {
                    (i, *c)
                    for i, (key, row) in enumerate(rows.items())
                    for c in conflicts(row, titles[key])
                }
                for arm, rows in cohort["category"].items()
            }
        train_hash = None
    else:
        refs, programs = {}, ()
        p = read(POINTER)
        train = ROOT / p["artifact_root"]
        train_hash = sha(train / "terminal.json")
        assert p["terminal_sha256"] == train_hash
        assert read(train / "binding.json")["runner_sha256"] == sha(Path(__file__))
    binding = {
        "partition": partition,
        "runner_sha256": sha(Path(__file__)),
        "native_grade_sha256": sha(grade),
        "ordered_source_sha256": digest(views),
        "archive": meta,
        "TRAIN_terminal_sha256": train_hash,
        "B6_B7_original_terminals": refs,
        "B6_B7_programs": list(programs),
    }
    out = HOME / partition / digest(binding)
    immutable_json(out / "binding.json", binding)
    immutable_json(out / "predictions.json", {"common": bank, "category": repaired})
    if book:
        for b, cohort in book.items():
            immutable_json(out / f"B{b}_category_predictions.json", cohort["category"])
    labels = read(grade)
    terminal = {
        "partition": partition,
        "mothers": len(views),
        "archive": meta,
        "physical_requests_new": 0,
        "predictions_sha256": sha(out / "predictions.json"),
        "source_verified_shared_vs_direct": observed,
        "native_pairs": full_scores(views, bank, repaired, labels),
    }
    if book:
        terminal["route_replay"] = route_evidence(book, labels, out)
        terminal["B6_B7_signature_counts"] = {
            str(b): cohort["category_support"] for b, cohort in book.items()
        }
    immutable_json(out / "terminal.json", terminal)
    if partition == "train":
        write_status(
            out, {"status": "TRAIN_settled", "terminal_sha256": sha(out / "terminal.json")}, POINTER
        )
    print(
        json.dumps({"artifact_root": str(out.relative_to(ROOT)), **terminal}, sort_keys=True),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("partition", choices=("train", "dev"))
    run(parser.parse_args().partition)
