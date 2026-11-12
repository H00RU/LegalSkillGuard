def _uniq(items):
    out = []
    for item in items:
        if item not in out:
            out.append(item)
    return out

def _field(value, ids):
    return {"value": value, "support_ids": list(ids) if value is not None else []}

def _instance(values, ids):
    fields = {}
    for name, value in values.items():
        fields[name] = _field(value, ids)
    return {"support_ids": _uniq(ids), "fields": fields}

def _roles(text):
    t = text.casefold()
    pairs = [
        ("legal_advisor", ["legal advisor", "legal adviser", "attorney", "outside counsel", "legal counsel"]),
        ("financial_advisor", ["financial advisor", "financial adviser"]),
        ("professional_advisor", ["professional advisor", "professional adviser"]),
        ("accountant", ["accountant"]),
        ("contractor", ["independent contractor", "contractor"]),
        ("consultant", ["consultant"]),
        ("director", ["director"]),
        ("officer", ["officer"]),
        ("employee", ["employee", "staff"]),
        ("agent", ["agent"]),
        ("affiliate", ["affiliate"]),
        ("broad_third_party", ["third party", "third parties"]),
        ("broad_external_person", ["any other person", "other person or organization", "any person or organization"])
    ]
    out = []
    for symbol, forms in pairs:
        for form in forms:
            if form in t:
                out.append(symbol)
                break
    return _uniq(out)

def _has_any(text, parts):
    for part in parts:
        if part in text:
            return True
    return False

def _after_exception(text):
    t = text.casefold()
    marks = ["provided however that", "provided, however, that", "except in confidence to", "except to", "other than"]
    best = -1
    size = 0
    for mark in marks:
        pos = t.find(mark)
        if pos >= 0 and (best < 0 or pos < best):
            best = pos
            size = len(mark)
    if best < 0:
        return ""
    return text[best + size:]

def _before_exception(text):
    t = text.casefold()
    positions = []
    for mark in ["provided however that", "provided, however, that", "except in confidence to", "except to", "other than"]:
        pos = t.find(mark)
        if pos >= 0:
            positions.append(pos)
    if not positions:
        return text
    return text[:min(positions)]

def _relation(text, roles, internal):
    t = text.casefold()
    role_set = set(roles)
    if internal:
        return "actor_internal"
    if "affiliate" in t and any(x in role_set for x in ["employee", "director", "officer"]):
        return "actor_affiliate_personnel"
    if "broad_third_party" in role_set or "broad_external_person" in role_set:
        return "external_unspecified"
    professional = set(["contractor", "consultant", "agent", "legal_advisor", "financial_advisor", "professional_advisor", "accountant"])
    personnel = set(["employee", "director", "officer"])
    if any(x in role_set for x in professional) and not any(x in role_set for x in personnel):
        return "external_professional"
    if roles:
        return "actor_associated_personnel"
    return "unspecified"

def _actor_role(text):
    t = text.casefold()
    if "each party" in t or "either party" in t or "each participating entity" in t:
        return "reciprocal_party_as_recipient"
    if "receiving party" in t or "recipient" in t or "participating entity" in t or "volunteer" in t:
        return "receiving_party"
    return "other_actor"

def _definition_roles(spans):
    roles = []
    ids = []
    for span in spans:
        text = str(span.get("text", ""))
        t = text.casefold()
        if "representative" in t and (" means " in t or " shall mean " in t or "include" in t):
            found = _roles(text)
            concrete = [x for x in found if x not in ["broad_third_party", "broad_external_person", "affiliate"]]
            if concrete:
                roles.extend(concrete)
                ids.append(span.get("id"))
    return _uniq(roles), [x for x in ids if isinstance(x, int)]

def _context(spans, index):
    span = spans[index]
    text = str(span.get("text", ""))
    ids = [span.get("id")]
    tail = text.rstrip().casefold()
    if index + 1 < len(spans):
        next_text = str(spans[index + 1].get("text", ""))
        lead = next_text.lstrip().casefold()
        continuation = tail.endswith((" or", " and", " to", " including", " provided that", "the l.e.k.", "or to the l.e.k."))
        continuation = continuation or lead.startswith(("representatives identified", "who ", "provided ", "except ", "or "))
        if continuation:
            text = text + " " + next_text
            ids.append(spans[index + 1].get("id"))
    return text, [x for x in ids if isinstance(x, int)]

def _authorization(text, ids, roles, rep_roles, rep_ids, action, exception_text):
    t = text.casefold()
    recipient_text = exception_text if exception_text else text
    chosen = list(roles)
    used_ids = list(ids)
    if "representative" in recipient_text.casefold() and not chosen and rep_roles:
        chosen = list(rep_roles)
        used_ids.extend(rep_ids)
    internal = action == "internal_share"
    if internal and not chosen:
        chosen = ["internal_personnel"]
    affiliate_direct = _has_any(recipient_text.casefold(), ["to its affiliates", "to recipient's affiliates", "to recipient’s affiliates", "to the recipient's affiliates"])
    qualified = []
    qualified_relation = None
    if affiliate_direct and "affiliate" in _roles(recipient_text):
        direct = ["affiliate"]
        qualified = [x for x in chosen if x in ["employee", "director", "officer", "contractor", "consultant", "agent", "legal_advisor", "financial_advisor", "professional_advisor", "accountant", "internal_personnel"]]
        direct_relation = "actor_affiliate_entity"
        if qualified:
            qualified_relation = "actor_affiliate_personnel"
    else:
        direct = chosen
        direct_relation = _relation(recipient_text, direct, internal)
    values = {
        "actor_role": _actor_role(text),
        "action": action,
        "direct_recipient_classes": direct,
        "direct_recipient_relation": direct_relation,
        "qualified_access_classes": qualified,
        "qualified_access_relation": qualified_relation
    }
    return _instance(values, _uniq(used_ids))

def apply(inputs, premises):
    spans = inputs.get("source_spans", []) if isinstance(inputs, dict) else []
    if not isinstance(spans, list):
        raise TypeError("source_spans must be a list")
    authorizations = []
    restrictions = []
    links = []
    rep_roles, rep_ids = _definition_roles(spans)
    for index, span in enumerate(spans):
        if not isinstance(span, dict):
            continue
        current = str(span.get("text", ""))
        current_low = current.casefold()
        if not _has_any(current_low, ["disclos", "divulg", "reveal", "communicat", "transfer", "access", "internally share", "internal share"]):
            continue
        text, ids = _context(spans, index)
        t = text.casefold()
        has_object = "confidential" in t or "such information" in t or "the same" in t
        if not has_object:
            continue
        if _has_any(t, ["shall mean", " means ", "information includes"]) and not _has_any(t, ["shall not", "not to", "may disclose", "restrict access", "internally share"]):
            continue
        negative = _has_any(t, ["shall not disclose", "not to disclose", "will not disclose", "may not disclose", "prohibited from disclosing", "agrees not to", "neither it nor", "without prior written consent", "without the prior written consent", "without the express permission"])
        legal = _has_any(t, ["required by law", "required to disclose", "compelled to disclose", "court order", "subpoena", "statutory duty", "governmental authority", "legal process"])
        exception_text = _after_exception(text)
        exception_roles = _roles(exception_text)
        bounded = bool(exception_roles) and _has_any(t, ["except in confidence to", "except to", "provided however that", "provided, however, that", "other than"])
        permission = _has_any(t, ["may disclose", "may share", "may provide", "permitted to disclose", "entitled to disclose", "restrict access to", "allow access to", "internally share", "internal share", "except in confidence to"])
        if permission and not legal:
            if "internally share" in t or "internal share" in t:
                action = "internal_share"
            elif "access" in t and not "may disclose" in t:
                action = "grant_access"
            else:
                action = "disclose"
            recipient_text = exception_text if negative and bounded else text
            roles = _roles(recipient_text)
            authorizations.append(_authorization(text, ids, roles, rep_roles, rep_ids, action, recipient_text if negative and bounded else ""))
        if negative:
            restricted_text = _before_exception(text)
            restricted_roles = _roles(restricted_text)
            if "broad_third_party" in restricted_roles:
                restricted_scope = "broad_third_party"
            elif "broad_external_person" in restricted_roles:
                restricted_scope = "broad_external_person"
            else:
                restricted_scope = "specified_roles"
            if bounded:
                exception_scope = "bounded_recipient_exception"
                exception_classes = [x for x in exception_roles if x not in ["broad_third_party", "broad_external_person"]]
                exception_relation = _relation(exception_text, exception_classes, False)
            elif legal:
                exception_scope = "legal_compulsion_only"
                exception_classes = []
                exception_relation = None
            elif _has_any(t, ["prior written consent", "prior, written consent", "express permission", "written approval"]):
                exception_scope = "consent_required"
                exception_classes = []
                exception_relation = None
            elif _has_any(t, ["as required to analyze", "as required to fulfil", "as required to fulfill", "for the purpose", "for the purpose(s)"]) and _has_any(t, ["except", "other than"]):
                exception_scope = "operational_purpose_unspecified"
                exception_classes = []
                exception_relation = None
            elif _has_any(t, ["except as expressly permitted under", "except as permitted under", "subject to section", "subject to paragraph"]):
                exception_scope = "linked_specific_provision"
                exception_classes = []
                exception_relation = None
            else:
                exception_scope = "no_stated_exception"
                exception_classes = []
                exception_relation = None
            if "access" in restricted_text.casefold() and "disclos" not in restricted_text.casefold():
                restricted_action = "grant_access"
            elif "communicat" in restricted_text.casefold() and "disclos" not in restricted_text.casefold():
                restricted_action = "communicate"
            else:
                restricted_action = "disclose"
            values = {
                "actor_role": _actor_role(text),
                "action": restricted_action,
                "restricted_recipient_scope": restricted_scope,
                "restricted_recipient_classes": restricted_roles,
                "exception_scope": exception_scope,
                "exception_recipient_classes": exception_classes,
                "exception_recipient_relation": exception_relation
            }
            restrictions.append(_instance(values, ids))
    for index, span in enumerate(spans):
        if not isinstance(span, dict) or index == 0:
            continue
        text = str(span.get("text", ""))
        t = text.casefold()
        if "all such" not in t:
            continue
        roles = _roles(text)
        if not roles:
            continue
        start = max(0, index - 2)
        prior = " ".join(str(spans[j].get("text", "")) for j in range(start, index) if isinstance(spans[j], dict))
        p = prior.casefold()
        if not _has_any(p, ["restrict access", "may disclose", "may share", "grant access"]):
            continue
        target = "grant_access" if "access" in p else "disclose"
        ids = [spans[j].get("id") for j in range(start, index + 1) if isinstance(spans[j], dict) and isinstance(spans[j].get("id"), int)]
        values = {
            "actor_role": _actor_role(prior + " " + text),
            "target_action": target,
            "linked_recipient_classes": [x for x in roles if x in ["employee", "director", "officer", "contractor", "consultant", "agent", "legal_advisor", "financial_advisor", "professional_advisor", "accountant"]],
            "linked_recipient_relation": _relation(text, roles, False)
        }
        links.append(_instance(values, ids))
    return {
        "confidential_information_authorization": authorizations,
        "confidential_information_restriction": restrictions,
        "recipient_scope_link": links
    }