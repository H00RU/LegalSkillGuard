"""Reconcile literal OpenExempt EC asset keys with the public inventory."""

import re

from legal_skill_guard.paired_interfaces.convergence_ev_inventory import MONEY, public_inventory

VALUATION = re.compile(
    rf",? (?:is |stands )?(?:worth|at|priced at|appraised at|valued at|"
    rf"with (?:a|an) (?:market |appraisal |estimated )?value of) ({MONEY})"
)


def asset_key(key, inventory):
    """Bind a valuation-suffixed alias only to its own exact source quotation."""
    matching = []
    for row in inventory.values():
        name, quote, amount = (row[field] for field in ("description", "source_quote", "amount_quote"))
        article, matched, suffix = key.partition(name)
        if not matched or not suffix or key not in quote or quote.count(name) != 1:
            continue
        # Leading articles are part of the source quote, rather than the asset description.
        if article.casefold() not in ("", "a ", "an ", "the "):
            continue
        value = VALUATION.fullmatch(suffix)
        if value and value[1] == amount:
            matching.append(name)
    return matching[0] if len(matching) == 1 else key


def bind_classification(view, answer):
    """Consolidate duplicate citation assertions on one uniquely quoted asset."""
    if view["id"] != "EC" or not isinstance(answer, dict):
        return answer
    inventory = public_inventory(view["public"]["original_input"])
    if not inventory:
        return answer
    names = {row["description"] for row in inventory.values()}
    output = {}
    for key, claims in answer.items():
        bound = key if key in names else asset_key(key, inventory)
        if bound in output:
            output[bound] = list(dict.fromkeys([*output[bound], *claims]))
        else:
            output[bound] = claims
    return output
