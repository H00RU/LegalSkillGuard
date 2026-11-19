from experiments.convergence_revision5_cni_reverse_engineering import apply, source_proof


def view(*spans):
    text = " ".join(spans)
    offsets = []
    start = 0
    for span in spans:
        offsets.append([start, start + len(span)])
        start += len(span) + 1
    return {"public": {"source_text": text, "sentence_spans": offsets}}


def test_engineering_prohibition_keeps_operational_evidence_and_written_consent():
    task = view("The Receiving Party shall not reverse engineer the prototype except with written consent.")
    result = apply({}, source_proof(task))
    assert result == {"answer": "Entailment", "evidence_sentence_ids": [0]}


def test_copying_and_litigation_discovery_have_separate_action_scope():
    task = view(
        "The Receiving Party shall not publish, copy, or use the Confidential Information for their sole benefit.",
        "A discovery request or any other lawful process may result in disclosure.",
    )
    assert apply({}, source_proof(task)) == {"answer": "NotMentioned", "evidence_sentence_ids": []}


def test_list_introducer_supplies_recipient_scope():
    task = view(
        "The Receiving Parties undertake and agree:",
        "(a) Not to disclose confidential information;",
        "(b) Not to disassemble or reverse engineer any Confidential Information;",
    )
    proof = source_proof(task)
    assert apply({}, proof) == {}
    assert apply({}, proof, linked=True) == {"answer": "Entailment", "evidence_sentence_ids": [0, 2]}


def test_scope_checks_leave_unresolved_permissions_and_unrelated_list_actors_unchanged():
    for task in (
        view("The Recipient shall not publish the findings but may reverse engineer prototypes."),
        view("The Seller undertakes and agrees:", "(a) Not to reverse engineer samples."),
        view("The Recipient undertakes and agrees:", "(c) Not to reverse engineer samples."),
        view("The Recipient undertakes and agrees:",
             "(a) Not to publish designs and may reverse engineer samples."),
    ):
        proof = source_proof(task)
        assert not proof["same"] and not proof["linked"]
        assert not proof["no_engineering_cue"]
