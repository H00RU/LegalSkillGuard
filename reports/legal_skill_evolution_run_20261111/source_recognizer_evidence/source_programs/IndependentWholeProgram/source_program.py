def _norm(value):
    return str(value).casefold().replace("’", "'").replace("–", "-").replace("—", "-")

def _unique(values):
    out = []
    for value in values:
        if value not in out:
            out.append(value)
    return out

def _roles(text):
    t = _norm(text)
    out = []
    tests = [
        ("employee", ["employee", "employees", "staff"]),
        ("director", ["director", "directors"]),
        ("officer", ["officer", "officers"]),
        ("contractor", ["contractor", "contractors"]),
        ("consultant", ["consultant", "consultants"]),
        ("agent", ["agent", "agents"]),
        ("legal_advisor", ["legal advisor", "legal adviser", "legal counsel", "attorney", "attorneys"]),
        ("financial_advisor", ["financial advisor", "financial adviser"]),
        ("professional_advisor", ["professional advisor", "professional adviser"]),
        ("accountant", ["accountant", "accountants", "auditor", "auditors"]),
        ("affiliate", ["affiliate", "affiliates"]),
        ("broad_third_party", ["third party", "third parties", "third-party", "third-parties"]),
        ("broad_external_person", ["any other person", "other person or organization", "any person or organization", "general public"])
    ]
    for symbol, forms in tests:
        for form in forms:
            if form in t:
                out.append(symbol)
                break
    return _unique(out)

def _after(text):
    t = _norm(text)
    cut = -1
    for marker in ["provided however", "provided, however", "except", "other than", "unless"]:
        pos = t.find(marker)
        if pos >= 0 and (cut < 0 or pos < cut):
            cut = pos
    if cut < 0:
        return ""
    return t[cut:]

def _relation(text, classes):
    t = _norm(text)
    personnel = set(["employee", "director", "officer", "contractor", "consultant", "agent", "legal_advisor", "financial_advisor", "professional_advisor", "accountant", "internal_personnel"])
    external = set(["contractor", "consultant", "agent", "legal_advisor", "financial_advisor", "professional_advisor", "accountant"])
    c = set(classes) if isinstance(classes, list) else set()
    if ("affiliates'" in t or "affiliate's" in t or "affiliate personnel" in t) and any(x in personnel for x in c):
        return "actor_affiliate_personnel"
    if c == set(["affiliate"]):
        return "actor_affiliate_entity"
    if "representative" in t or (any(x in external for x in c) and any(x in set(["employee", "director", "officer"]) for x in c)):
        return "actor_associated_personnel"
    if any(x in external for x in c):
        return "external_professional"
    if any(x in set(["employee", "director", "officer", "internal_personnel"]) for x in c):
        return "actor_internal"
    if "broad_third_party" in c or "broad_external_person" in c:
        return "external_unspecified"
    return "unspecified"

def _field(value, ids):
    return {"value": value, "support_ids": list(ids) if value is not None else []}

def _authorization(ids, action, direct, direct_relation, qualified, qualified_relation):
    fields = {
        "actor_role": _field("receiving_party", ids),
        "action": _field(action, ids),
        "direct_recipient_classes": _field(direct, ids),
        "direct_recipient_relation": _field(direct_relation, ids),
        "qualified_access_classes": _field(qualified, ids),
        "qualified_access_relation": _field(qualified_relation, ids)
    }
    return {"support_ids": list(ids), "fields": fields}

def _restriction(ids, scope, classes, exception_scope, exception_classes, exception_relation):
    fields = {
        "actor_role": _field("receiving_party", ids),
        "action": _field("disclose", ids),
        "restricted_recipient_scope": _field(scope, ids),
        "restricted_recipient_classes": _field(classes, ids),
        "exception_scope": _field(exception_scope, ids),
        "exception_recipient_classes": _field(exception_classes, ids),
        "exception_recipient_relation": _field(exception_relation, ids)
    }
    return {"support_ids": list(ids), "fields": fields}

def _link(ids, action, classes, relation):
    fields = {
        "actor_role": _field("receiving_party", ids),
        "target_action": _field(action, ids),
        "linked_recipient_classes": _field(classes, ids),
        "linked_recipient_relation": _field(relation, ids)
    }
    return {"support_ids": list(ids), "fields": fields}

def apply(inputs, premises):
    result = {
        "confidential_information_authorization": [],
        "confidential_information_restriction": [],
        "recipient_scope_link": []
    }
    if not isinstance(inputs, dict):
        return result
    raw = inputs.get("source_spans", [])
    if not isinstance(raw, list):
        return result
    spans = []
    for span in raw:
        if isinstance(span, dict) and isinstance(span.get("id"), int):
            spans.append(span)
    seen_authorizations = set()
    seen_restrictions = set()
    seen_links = set()
    for i, span in enumerate(spans):
        sid = span.get("id")
        base = _norm(span.get("text", ""))
        text = base
        ids = [sid]
        action_words = any(x in base for x in ["disclos", "divulg", "reveal", "communicat", "share", "access", "transmit", "transfer"])
        if action_words and len(_roles(base)) == 0 and i + 1 < len(spans):
            nxt = _norm(spans[i + 1].get("text", ""))
            if len(_roles(nxt)) > 0 and not any(x in nxt for x in [" remedies", " governing law", " severability", " term.", " return of"]):
                text = base + " " + nxt
                ids.append(spans[i + 1].get("id"))
        mentions_information = any(x in text for x in ["confidential information", "such information", "the same", "confidential material"])
        operative = any(x in text for x in [" shall ", " may ", " agrees ", " agree ", " will ", " must ", "undertakes", "prohibited", "entitled"])
        definition_only = (" means " in text or " shall mean " in text) and not any(x in text for x in ["may disclose", "shall not disclose", "not to disclose", "restrict access", "internally share"])
        if mentions_information and operative and not definition_only:
            prohibited = any(x in text for x in ["shall not disclose", "not to disclose", "will not disclose", "may not disclose", "must not disclose", "prohibited from disclosing", "prohibited from disclosure", "neither it nor its representatives will", "not to, directly or indirectly"])
            permitted = any(x in text for x in ["may disclose", "may share", "may internally share", "may use and internally share", "is permitted to disclose", "shall be entitled to disclose", "restrict access to", "shall restrict access", "except in confidence to"])
            legally_conditioned = any(x in text for x in ["required by law", "required to disclose", "compelled to disclose", "court order", "subpoena", "legal process", "statutory duty"])
            consent_conditioned = permitted and any(x in text for x in ["with prior written consent", "with the prior written consent", "with prior written approval", "expressly authorized in writing"]) and "provided however" not in text
            nonconfidential_exception = any(x in text for x in ["public domain", "independently developed", "rightfully furnished", "rightfully received", "non-confidential basis"])
            if permitted and not legally_conditioned and not consent_conditioned and not nonconfidential_exception:
                classes = _roles(text)
                action = "disclose"
                if "internally share" in text:
                    action = "internal_share"
                    if len(classes) == 0:
                        classes = ["internal_personnel"]
                elif "access" in text and "may disclose" not in text:
                    action = "grant_access"
                direct = list(classes)
                direct_relation = _relation(text, direct)
                qualified = None
                qualified_relation = None
                if "affiliate" in classes and "restrict access" in text:
                    direct = ["affiliate"]
                    direct_relation = "actor_affiliate_entity"
                    qualified = []
                    for role in classes:
                        if role != "affiliate":
                            qualified.append(role)
                    if len(qualified) > 0:
                        qualified_relation = "actor_affiliate_personnel"
                    else:
                        qualified = None
                if len(direct) > 0:
                    key = (tuple(ids), action, tuple(direct), direct_relation, tuple(qualified) if isinstance(qualified, list) else ())
                    if key not in seen_authorizations:
                        result["confidential_information_authorization"].append(_authorization(ids, action, direct, direct_relation, qualified, qualified_relation))
                        seen_authorizations.add(key)
            if prohibited:
                all_classes = _roles(text)
                broad = "broad_third_party" in all_classes or "broad_external_person" in all_classes
                scope = "broad_third_party" if "broad_third_party" in all_classes else ("broad_external_person" if "broad_external_person" in all_classes else "specified_roles")
                tail = _after(text)
                exception_classes = _roles(tail) if tail else []
                exception_scope = "no_stated_exception"
                exception_relation = None
                if tail and len(exception_classes) > 0:
                    exception_classes = [x for x in exception_classes if x not in ["broad_third_party", "broad_external_person", "affiliate"]]
                    if len(exception_classes) > 0:
                        exception_scope = "bounded_recipient_exception"
                        exception_relation = _relation(tail, exception_classes)
                if exception_scope == "no_stated_exception" and any(x in text for x in ["without prior written consent", "without the prior written consent", "without prior written approval", "without the express permission"]):
                    exception_scope = "consent_required"
                if exception_scope == "no_stated_exception" and legally_conditioned:
                    exception_scope = "legal_compulsion_only"
                if tail and exception_scope == "no_stated_exception" and any(x in tail for x in ["required to analyze", "required to fulfil", "required to fulfill", "for the purpose", "for the purpose of", "in the course of service"]):
                    exception_scope = "operational_purpose_unspecified"
                if tail and exception_scope == "no_stated_exception" and any(x in tail for x in ["section ", "paragraph ", "clause ", "as expressly permitted"]):
                    exception_scope = "linked_specific_provision"
                if broad or scope == "specified_roles":
                    restricted = all_classes if len(all_classes) > 0 else None
                    exc = exception_classes if exception_scope == "bounded_recipient_exception" else []
                    key = (tuple(ids), scope, tuple(all_classes), exception_scope, tuple(exc))
                    if key not in seen_restrictions:
                        result["confidential_information_restriction"].append(_restriction(ids, scope, restricted, exception_scope, exc, exception_relation))
                        seen_restrictions.add(key)
        current_roles = _roles(base)
        if "all such" in base and len(current_roles) > 0 and any(x in base for x in ["inform", "instruct", "ensure", "responsible for ensuring"]):
            for back in range(max(0, i - 2), i):
                previous = _norm(spans[back].get("text", ""))
                if "confidential information" in previous and any(x in previous for x in ["restrict access", "may disclose", "grant access"]):
                    target = "grant_access" if "access" in previous else "disclose"
                    link_ids = [spans[back].get("id"), sid]
                    relation = _relation(base, current_roles)
                    key = (tuple(link_ids), target, tuple(current_roles), relation)
                    if key not in seen_links:
                        result["recipient_scope_link"].append(_link(link_ids, target, current_roles, relation))
                        seen_links.add(key)
                    break
    return result