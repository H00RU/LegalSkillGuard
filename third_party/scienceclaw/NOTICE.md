# ScienceClaw lexical primitive

Upstream: https://github.com/beita6969/ScienceClaw

Pinned commit: `e925f732c7ca435f557e88075bc47a58f1e984f1`.

`legal_skill_guard/learning/clauses.py` adapts the word/number tokenizer and
light suffix stemmer from `packages/scienceclaw/scilib/contracts.py`, under MIT.
The retained historical MIT notice is in `LICENSE` beside this file.

The adaptation preserves negation/modality (no stopword removal), returns only
literal original ContractNLI spans and neighbours, and never returns a legal
relation or evidence-relevance verdict.

The evidence-operator experiment additionally imports the attributed evidence
scorer in `legal_skill_guard/_vendor/scienceclaw_contracts.py` from that same
commit. Its local NotMentioned-negative adaptation and preserved MIT license are
documented in the adjacent `SCIENCECLAW_NOTICE.md` and `SCIENCECLAW_LICENSE.txt`.
This is a supervised external tool, not an additional language model or an
unmodified canonical reproduction of ScienceClaw.
