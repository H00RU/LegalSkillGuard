"""One recorded teacher-only control build; no model generations or scores."""
import json
import signal
import sys
import traceback
from pathlib import Path

from experiments.openexempt_online import DIRECT_GUIDANCE, Online, preserve
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.legal_namespace import validate_scopes
from legal_skill_guard.learning.publication import skill_record_schema
from legal_skill_guard.learning.task_scoped_skills import validate_scoped_bank
from legal_skill_guard.openexempt import FAMILIES, ROOT
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

SYSTEM = (
    "Compile one compact reusable STATIC law-only skill library for frozen Qwen3-8B "
    "to perform the two supplied legal tasks. Use only the provided public statutes "
    "and generic interfaces. No case, answer, trajectory, score or previous skill "
    "library is supplied; do not invent any. Write useful operational procedures "
    "rather than copying the statute corpus. The host projects the known public "
    "task and allowable legal namespace; legal judgments and numeric answers remain "
    "the executor's responsibility. Declare each skill's EC/EV and jurisdiction scope "
    "explicitly, with when/procedure/avoid_when guidance. Each task declared in "
    "hypothesis_ids must occur exactly once "
    "across guidance.by_task blocks, with no extra or repeated tasks. Use either "
    "one shared [EC,EV] block or two disjoint [EC] and [EV] blocks for a two-task "
    "skill, never a shared block plus a second EV block. Do not force a skill count "
    "or taxonomy. Every operators array must be empty; there is no interpreter or "
    "hidden calculator. No case tables, example assets, debtor names, particular "
    "answers or fabricated empirical claims. Public statutory citations and values "
    "may be used when supported by the supplied text. The complete serialized bank "
    "must fit4096 Qwen3-8B tokens; aim2500. This is one blind compilation without "
    "outcome-guided revision. No tools, shell, files, network or external information. "
    "Return only the requested bank JSON."
)


def main(config_path):
    cfg = json.loads(config_path.read_text())
    manifest = json.loads(config_path.with_suffix(".frozen.json").read_text())
    study = Online.__new__(Online)
    study.cfg, study.bindings, study.run_id = cfg, manifest["files"], cfg["run_id"]
    study.out = ROOT / "runs" / study.run_id
    study.out.mkdir()  # A recorded invocation is never overwritten or resumed.
    study.bank, study.native, study.teachers, study.reuse_events = [], [], [], []
    study.current_batch, study.teacher_attempts, study.stop = 0, 0, False
    study.meter = WireClient(cfg["generation"])
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: setattr(study, "stop", True))
    status = "failed"
    try:
        study.check()
        public = json.loads((ROOT / cfg["input_packet"]).read_text())
        schema = {"type": "object", "additionalProperties": False, "required": ["bank"],
                  "properties": {"bank": {"type": "array", "items": skill_record_schema(
                      FAMILIES, guidance_schema=DIRECT_GUIDANCE)}}}
        study.bank = study.teacher_call("law_only_compilation", SYSTEM, public, schema)["bank"]
        validate_scoped_bank(study.bank)
        validate_scopes(study.bank, "\n\n".join(public["complete_public_statutes"].values()))
        tokens = study.meter.token_count(text=json.dumps(
            study.bank, ensure_ascii=False, separators=(",", ":")))
        if tokens > cfg["library_token_hard_cap"]:
            raise ValueError(f"Static bank exceeds cap: {tokens}; no trimming or reroll")
        RunStore.immutable_json(study.out / "publication.json", {
            "bank": study.bank, "bank_sha256": csha(study.bank), "Qwen_tokens": tokens,
            "training_sources_seen": 0, "actual_native_generations": 0,
            "actual_teacher_responses": len(study.teachers),
            "actual_teacher_attempts": study.teacher_attempts,
            "compiled_not_evaluated": True})
        status = "compiled_law_only_static_bank_not_evaluated"
        RunStore.immutable_json(study.out / "completion.json", {"status": status})
    except Exception as exc:
        RunStore.immutable_json(study.out / "failure.json", {
            "error": repr(exc), "traceback": traceback.format_exc(),
            "actual_native_generations": len(study.native),
            "actual_teacher_responses": len(study.teachers),
            "actual_teacher_attempts": study.teacher_attempts})
        raise
    finally:
        study.progress("terminal", state=status)
        names = [str(p.relative_to(ROOT)) for p in study.out.rglob("*")
                 if p.is_file() and "/cache/" not in str(p)]
        receipt = preserve(study.run_id, "actual-terminal", names)
        RunStore.immutable_json(study.out / "terminal_preservation.json", receipt)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
