"""Assign a cross-task conflict to a reader only when the source fixes its direction."""

from legal_skill_guard.paired_interfaces import convergence_oe_joint_acquisition as joint


def attribute(answers, titles, exact_ec, excluded_ev):
    """Preserve each task's title and leave symmetric disagreements unresolved."""
    ec, ev = (answers[task] or {} for task in joint.TASKS)
    supported = {'EC': set(), 'EV': set(), 'unresolved': set()}
    for asset, citation in joint.conflicts(answers, titles, exact_ec):
        pair = asset, citation
        title_ec, title_ev = titles[asset]
        in_ec = citation in ec.get(asset, ())
        in_ev = any(row['citation'] == citation and row['claim_value'] > 0 for row in ev.get(asset, ()))
        expected = exact_ec.get(pair)
        identify_ec = (in_ec and (expected is False or title_ec is False)
                       or not in_ec and expected is True and title_ec is True and answers['EC'] is not None)
        identify_ev = in_ev and (pair in excluded_ev or title_ev is False)
        if identify_ec:
            supported['EC'].add(pair)
        if identify_ev:
            supported['EV'].add(pair)
        if not identify_ec and not identify_ev:
            supported['unresolved'].add(pair)
    return supported


def screen(original, proposal, titles, exact_ec, values, item_cap, excluded_ev):
    """Count new source-certified errors separately from unresolved contradictions."""
    archived = joint.evidence(original, proposal, titles, exact_ec, values, item_cap,
                              require_category=True, ev_excluded=excluded_ev)
    before = attribute(original, titles, exact_ec, excluded_ev)
    after = attribute(proposal, titles, exact_ec, excluded_ev)
    def assertions(port, native):
        entries = joint.port_claims(native[port], port)
        return entries if port == 'EC' else {row[:2] for row in entries if row[2] > 0}

    changed = {port: assertions(port, original) ^ assertions(port, proposal) for port in joint.TASKS}
    introduced = {task: (after[task] - before[task]) & changed[task] for task in joint.TASKS}
    introduced['unresolved'] = after['unresolved'] - before['unresolved']
    return {**archived, 'introduced_undirected_conflicts': archived['introduced_cross_conflicts'],
            'introduced_cross_conflicts': sum(len(introduced[task]) for task in joint.TASKS),
            'new_cross_task_witnesses': {task: sorted(pairs) for task, pairs in introduced.items()},
            'exposed_existing_errors': {task: len(after[task] - before[task] - changed[task]) for task in joint.TASKS}}
