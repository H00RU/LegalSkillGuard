# ACE code attribution and adaptation

Upstream: https://github.com/ace-agent/ace

Commit: `82709de050e1db6e6ef2f07bcb0393560b94992a`.

`legal_skill_guard/learning/ace_native.py` reproduces selected deterministic
helpers from the ACE authors' `playbook_utils.py` and `utils.py`, licensed under
the accompanying Apache-2.0 license. Formatting and import isolation are local
modifications; counter updates, global IDs and ADD-only delta application are
retained. The upstream distribution contains no NOTICE file.

The legal task adapter and Chinese role instructions are modified adaptations,
not a complete unmodified ACE reproduction. Task-specific citation handling,
G4 experience and batch curation must be disclosed with actual call costs.
No upstream JSON-repair, error-skipping or retry fallback is imported.

2026-10-20: `learning/openexempt_ace.py` and
`experiments/openexempt_ace_online.py` adapt the pinned native role prompts,
bullet provenance, last-tag batch counters and ADD merge to source-disjoint
EC/EV training. This profile uses one frozen local generator prediction and
one TRAIN reflection per task, followed by one batch curator. Shared public
empty controls, audited transports, full-stream stopping and explicit capacity
failure are local adaptations. No claim is made to reproduce all original
offline epochs, retries, checkpoint selection, or default hyperparameters.

2026-10-19: experiments/witnessed_experience.py additionally adapts the separation
of training reflection and subsequent curation. Its legal-source-bound findings
schema and public-evidence instructions are original local code, not the full
ACE algorithm or a verbatim upstream prompt. The author reflector prompt at the
pinned commit was re-read; no hidden-chain-of-thought request, repair/fallback,
helpfulness gate or second inference role is adopted.

Audited source file SHA-256:

```json
{
  "playbook_utils.py": "c67943f06cb0ee747be04d0599216e40d6c00e0cdf96ddc6af38fc26143e3a07",
  "utils.py": "7824aa262de2cd030b6914d1f7de698ec620dbec9c9e5f14ed1fe6322079570c",
  "ace/core/generator.py": "4b750a59752bd5bdb24b2f27b80938844d8a7b5d89e86d7d6bb726f3685c25f5",
  "ace/prompts/reflector.py": "72b343ce2781531dac2fd765543410b6abfc4817c39078dd4f83187c4d217e9c",
  "ace/prompts/curator.py": "eb03d59b3f3593832f730a798199b581ad797acd503c47d1737616c68cf26107"
}
```
