# ScienceClaw lexical primitive

Upstream: https://github.com/beita6969/ScienceClaw

Pinned commit: `e925f732c7ca435f557e88075bc47a58f1e984f1`.

`legal_skill_guard/learning/clauses.py` adapts the word/number tokenizer and
light suffix stemmer from `packages/scienceclaw/scilib/contracts.py`, under MIT.
The retained historical MIT notice is in `LICENSE` beside this file.

The adaptation preserves negation/modality (no stopword removal), returns only
literal original ContractNLI spans and neighbours, and never returns a legal
relation or evidence-relevance verdict. No other ScienceClaw runtime is imported.
