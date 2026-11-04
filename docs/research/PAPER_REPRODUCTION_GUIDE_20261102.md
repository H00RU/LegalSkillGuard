# Reproducing the OpenExempt skill-evolution study

Updated 4 November 2026. Run commands from the repository root. The English paper
and separate Chinese explanation are indexed in [paper/README](../../paper/README.md).
This guide separates recomputing scores from generating new predictions and
independently learning a new library. It does not launch another experiment.

## 1. Identify the experiment and its artifacts

| Item | Authoritative entry |
|---|---|
| Main method, eighth complete build | `configs/openexempt_complete_output_utility_public_assets128_20261030_run01.json` and its `.frozen.json` manifest, with 379 bound files |
| Main training protocol | `docs/research/OPENEXEMPT_COMPLETE_OUTPUT_UTILITY_COMPLETE8_20261030.md` |
| Original ten-condition frozen evaluation | `artifacts/launches/openexempt_v6_final_after_withheld_20261031_run01/actual_final_matrix_config.json` |
| Evaluation protocol | `docs/research/OPENEXEMPT_V6_FINAL_SOURCE_ISOLATED_FROZEN_EVALUATION_20261030.md` |
| Original predictions and per-record scores | `runs/legal_openexempt_v6_frozen_source_isolated_IID128_20261031_run01/scored_records.json` |
| Reported aggregates and paired intervals | `paper/tables/utility_frozen_results_20261101.json` |
| Main training/library/cost evidence | `paper/tables/utility_training_evolution_cost_20261030.json` |
| Supplementary SkillCommit adaptation | `configs/openexempt_skillcommit_paper_public_assets128_seed45_20261102_run05.json` and its `.frozen.json` manifest, with 648 bound files |
| SkillCommit adaptation protocol | `docs/research/OPENEXEMPT_SKILLCOMMIT_VERIFIED_REFERENCE_ENGLISH_PROTOCOL_20261102.md` |
| Completed SkillCommit final library and learning cost | `runs/legal_openexempt_skillcommit_paper_public_assets128_seed45_20261102_run05/publications/final.json` |
| SkillCommit complete-build evidence | `artifacts/research/openexempt_skillcommit_20261102/run05_eighth_complete_batch_and_build_evidence_20261104.json` |
| Eleven-condition presentation and separate SkillCommit paired supplement | `paper/tables/utility_frozen_results_with_skillcommit_20261104.json` |
| Complete SkillCommit TEST score, HTTP delivery and bootstrap audit | `artifacts/research/openexempt_skillcommit_20261102/run05_complete_frozen_TEST_scores_delivery_cost_and_pairing_20261104.json` |

The supplementary eight-batch build completed on 4 November at 01:18 CST and
its actual-final-bank evaluation completed at 03:31 CST. The original
ten-condition table remains unchanged. The eleven-condition presentation adds
the complete SkillCommit result and its separate two-endpoint paired supplement,
not a new blinded confirmation or a replacement eighteen-endpoint family.
Retired runs and the v0.23 study remain historical artifacts, not replacements
for these entries.

The current English and separate Chinese Word/PDF exports are v15, indexed in
[paper/README](../../paper/README.md): 22 and 20 pages respectively, each with
13 tables, 23 native mathematical objects, two original figures and eleven
author-year references. Export source/file hashes, full-text checks and the
bounded 13-key-page visual review are recorded in
[`run05_bilingual_v15_complete_output_validation_20261104.json`](../../artifacts/research/openexempt_skillcommit_20261102/run05_bilingual_v15_complete_output_validation_20261104.json).
Earlier v12-v14 exports remain intact. Rendering changed no scientific scores,
executor/teacher settings or frozen source files, and is not a new experiment.

The final SkillCommit bank contains 21 higher-level patterns and 23 residual
patches. The final-publication file has SHA256
`090af0de02fd5ba84bd053683411ea930b7fa8c9906613ccb8f5aac518b9cc89`;
the canonical library payload has SHA256
`93fd552b3fb54e25c37235903bcef82903ec7874b3e2098bcd3af1ba2a4a1023`.
These identify the actual eighth-batch terminal bank, not a selected earlier bank.
Its completed learning cost is 2,015 physical executor generations, 345
exact-request reuses and 930 successful teacher responses from 931 recorded
attempts. The publication's cost fields end before frozen-test inference;
unreported failed-request usage is unknown, not zero. The four earlier retired
implementation attempts and their costs remain separately recorded in the
frozen run05 configuration and were not imported into this bank.

The completed TEST has 256 physical generations and zero teacher calls. Its
prediction-before-grading file has SHA256
`6c15d6f6ab2fe019fbf79804306141b8b44c63713fa6113353cf3a54a1a7d39a`;
its scored-record file has SHA256
`04f765cdb95b1c67200864c4b053830535cb642566d9ae448f5f8365d19e24df`.
All 256 original score dictionaries and the fixed 20,000-draw, seed-2026110101
paired intervals were independently recomputed in the existing driver
environment. The full read-only command is in the completed-TEST audit linked
above. This extends, rather than repeats or relabels, the earlier isolated
dependency-environment check of the original 2,560 scores in Section 2. Seven
length-limited invalid outputs remain zero. All 256 actual HTTP inputs match
their public task plus four complete retrieved patterns; memory delivery and
inference costs are reported separately from library construction.

The pinned generator is `servantez/OpenExempt` revision
`ec6fa2547431096588ce2d3ef107b8adc33cd4fe`. Its archive and extracted source are
under `data/cache/openexempt/`. Retain its CC BY 4.0 attribution. The study uses
128 TRAIN sources, eight batches of 16, and 128 source-disjoint TEST sources;
each source yields EC and EV tasks. Exact packets and grading directories are
specified by the corresponding configurations. Reuse these packets when
reproducing the reported scores rather than generating a different sample.
This conditioned 2–4-asset setting is not the official Advanced suite.

## 2. Recompute the original scores without models

This is the level already verified: all 2,560 original per-record score
dictionaries matched, as did 140 aggregate fields, retaining all 30 original
parse-invalid outputs. The complete command, dependency metadata, source/data
hashes and result are in
[`paper_isolated_environment_all2560_score_reproduction_20261102.json`](../../artifacts/research/openexempt_skillcommit_20261102/paper_isolated_environment_all2560_score_reproduction_20261102.json).
That check used a new dependency environment and the existing source tree;
it was not a clean-machine training or inference reproduction.

For a scoring-only environment, use Python 3.11 and these tested direct
dependencies. Choose a new environment path; do not overwrite the active `.venv`.

```bash
python3.11 -m venv .venv-score-reproduction
.venv-score-reproduction/bin/python -m pip install numpy==2.4.6 inflect==7.5.0 rapidfuzz==3.14.1 pydantic==2.12.0 langchain-core==0.3.79 langsmith==0.4.34
```

The following source-tree check emits a count and writes no experiment files.
It does not parse or regenerate model output: original parse failures remain
failures. The preserved evidence above additionally records the complete
hash and environment checks performed in the original reproduction.

```bash
.venv-score-reproduction/bin/python -B - <<'PY'
import copy, json, math, socket
from pathlib import Path
def offline_only(*args, **kwargs):
    raise RuntimeError("Score reproduction must not make network calls")
socket.socket.connect = offline_only
from legal_skill_guard.openexempt import evaluate
records = json.loads(Path("runs/legal_openexempt_v6_frozen_source_isolated_IID128_20261031_run01/scored_records.json").read_text())
cfg = json.loads(Path("artifacts/launches/openexempt_v6_final_after_withheld_20261031_run01/actual_final_matrix_config.json").read_text())
rows = json.loads(Path(cfg["input_packet"]).read_text())["rows"]
lookup = {(r["case_id"], r["family"]): r for r in rows}
table = {r["condition"]: r for r in json.loads(Path("paper/tables/utility_frozen_results_20261101.json").read_text())["conditions"]}
assert len(records) == 10 and len(lookup) == 256
checked = invalid = 0
for condition, items in records.items():
    assert len(items) == 256 and {(r["case_id"], r["family"]) for r in items} == set(lookup)
    fresh = {"EC": [], "EV": []}
    for r in items:
        row = lookup[r["case_id"], r["family"]]
        gold = json.loads((Path(cfg["grading_directory"]) / f'{r["case_id"]}.json').read_text())
        assert r["source_key"] == row["source_key"] == gold["source_key"]
        answer = r["parsed"]["answer"] if r["parse_error"] is None else None
        score = evaluate(row, answer, copy.deepcopy(gold["targets"][r["family"]]))
        assert score == r["score"], (condition, r["case_id"], r["family"])
        fresh[r["family"]].append(score)
        checked += 1
        invalid += int(r["parse_error"] is not None)
    for family, scores in fresh.items():
        actual = {"tasks": len(scores), "invalid_format": sum(s["invalid_format"] for s in scores)}
        actual.update({k: sum(s[k] for s in scores) / len(scores) for k in ("precision", "recall", "f1", "full_output_f1", "exact_target")})
        for key, value in actual.items():
            assert math.isclose(value, table[condition]["metrics"][family][key], rel_tol=0, abs_tol=1e-12)
assert checked == 2560 and invalid == 30
print({"matched_records": checked, "retained_parse_invalid": invalid, "matched_aggregate_fields": 140})
PY
```

This verifies the saved score table, not the bootstrap intervals or a new
SkillCommit outcome. F1 is not case-level accuracy. The evaluator preserves both
native F1 and complete-output F1; neither should be substituted for the other.

## 3. Runtime needed for new predictions

The driver and model service use separate environments. The measured package
versions are recorded in
[`paper_actual_runtime_environment_metadata_20261102.json`](../../artifacts/research/openexempt_skillcommit_20261102/paper_actual_runtime_environment_metadata_20261102.json).
`pyproject.toml` and the Python-3.11 branch of `uv.lock` cover the driver, not the
entire inference service. Actual driver versions include Python 3.11.15,
NumPy 2.4.6, jsonschema 4.26.0 and tiktoken 0.14.0; the OpenExempt extra pins
the scoring dependencies listed above.

The executor is one Qwen3-8B/BF16 service at model revision
`b968826d9c46dd6066d109eabc6255188de91218`. Its recorded runtime uses Python
3.11.15, vLLM 0.10.2, Torch distribution 2.8.0 (module build `2.8.0+cu128`),
Transformers 4.56.2 and tokenizers 0.22.2. The historical launch is in
[`ops/legal-qwen3-8b-phase-dispatch.service`](../../ops/legal-qwen3-8b-phase-dispatch.service);
additional inference pins are in `ops/inference-requirements.txt`. Retain the
recorded EOS alignment patch
`patches/vllm-0.10.2-hf-generation-eos-alignment.patch`: an unpatched wheel is not
the declared runtime.

Shared requests use context 32,768, output limit 8,192, temperature 0.6, top-p
0.95, top-k 20, request seed 45 and thinking enabled. The server's startup seed
42 is a separate setting. Four native workers share the one service. Full public
messages, JSON schema, parsed answer and raw response are saved per call;
length limits and invalid outputs are retained, not silently retried for quality.

The SkillCommit adaptation additionally uses CPU BGE-base-en-v1.5, revision
`a5beb1e3e68b9ab74eb54cfd186867f64f240e1a`, two CPU threads. Its configuration
binds six model/tokenizer files by SHA256 and records the runtime site-packages
path. It is not a second lawyer service. It is a declared local-encoder
adaptation, not the original paper's paid embedding API.

Learning uses the existing CLI teacher adapter in
`legal_skill_guard/inference/codex_cli_client.py`, requested model
`gpt-5.6-sol` with high reasoning effort and one teacher worker. A legitimate
configured teacher environment is necessary for fresh learning, not for auditing
saved scores or evaluating a frozen library. Do not publish account credentials.
Actual requests, responses and usage records, rather than a claim of indefinite
teacher availability, document the historical calls.

## 4. Existing execution entry points and a new reproduction

The existing command syntax is:

```text
.venv/bin/python -m experiments.openexempt_online prepare CONFIG
.venv/bin/python -m experiments.openexempt_online freeze CONFIG
.venv/bin/python -m experiments.openexempt_online run CONFIG
.venv/bin/python -m experiments.openexempt_frozen_eval freeze CONFIG
.venv/bin/python -m experiments.openexempt_frozen_eval run CONFIG
.venv/bin/python -m experiments.openexempt_skillcommit freeze CONFIG
.venv/bin/python -m experiments.openexempt_skillcommit run CONFIG
```

`CONFIG` denotes a separately prepared new configuration, not an instruction to
rerun a completed ID. `prepare` creates a new packet and freezes it, refusing to
overwrite an existing packet; use `freeze` when retaining the fixed study packet.
Frozen evaluation references the actual completed libraries and binds their
hashes before predictions. It does not continue teacher learning on TEST.
The current SkillCommit `run` completes all TRAIN sources and then automatically
freezes its actual final bank and evaluates the fixed TEST packet.

For an independent reproduction, restore the corresponding source snapshot in a
separate checkout; assign a new Run ID and output paths; retain the declared
data, public interface, generation settings and method-specific budgets. Resolve
machine-dependent paths, source-profile contracts and backup destinations in
that separate copy, capture the real service argv/PID/process-birth and inference
dependency hashes, then create new bindings before any result is observed.
The current driver checks `/proc` identity as well as file hashes: copying an old
machine's PID receipt is not a valid setup. No portable `capture-env` command is
advertised because these entry points do not provide one.

Archive completed raw calls, teacher usage, first-encounter records, library
publications, final-bank hash, frozen predictions and scores. Count physical
calls separately from exact-response aliases. Reusing the same learned bank for
another evaluation is not an independent learning repetition. Preserve
unsuccessful candidates and runs alongside accepted libraries.

The scoring-only check in Section 2 is verified. A complete fresh-machine
learning/inference rerun and a stable public release are not yet verified;
independent learning repetitions remain deferred by the user. This guide
documents the existing interfaces and required state rather than claiming that
changing one path makes the historical execution automatically portable.
