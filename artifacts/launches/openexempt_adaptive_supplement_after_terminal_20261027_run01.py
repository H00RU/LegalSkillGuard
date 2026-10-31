"""One approved TRAIN-terminal -> fixed-benchmark supplement handoff.

No learner/model signal, teacher call, repeat learning, repair, or score-selected
checkpoint. This operational launcher is outside the live scientific manifest.
"""
from __future__ import annotations
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT = Path("/media/sangfor/vdb/legal-skill-evolve")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import now, read, sha
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha
from experiments.openexempt_online import preserve

OUT = ROOT / "artifacts/launches/openexempt_adaptive_supplement_after_terminal_20261027_run01"
QUEUE = "legal_openexempt_adaptive_supplement_after_terminal_20261027_run01"
TRAIN = ROOT / "runs/legal_openexempt_adaptive_legal_public_assets128_20261026_run01"
TRAIN_CONFIG = ROOT / "configs/openexempt_adaptive_legal_public_assets128_20261026_run01.json"
TEMPLATE = OUT / "evaluation_template_pending_terminal.json"
CONFIG = ROOT / "configs/openexempt_adaptive_supplement_TEST128_20261027_run01.json"
IMPLEMENTATION = "5087f19d4db9908ba197ca6c83a3bdf445078998"
BASE_HEAD = "9ad5b558d9a60200cec103349c69f79c4ab2e006"
GIT = "/media/sangfor/vdb/legal-skill-forensics-20261015.pr9fln/git-runtime/usr/bin/git"
GIT_ENV = {**os.environ, "GIT_EXEC_PATH": "/media/sangfor/vdb/legal-skill-forensics-20261015.pr9fln/git-runtime/usr/lib/git-core"}
PATCHER = Path("/home/yndx/.codex/packages/app-server-daemon/releases/0.164.0-x86_64-unknown-linux-musl/bin/codex")
PATCHER_SHA = "b93f6811d3f653f0fb83be4050d857fb9abbb111dfa2ce160563327daff7f306"
EXPECTED_AFTER = {
  "experiments/openexempt_frozen_eval.py": "b1430ca922add90a361cf04c0943597ef3374d25264bcabd096b2106d264915a",
  "legal_skill_guard/learning/runtime_sources.py": "824737c6c622d8cd849a4f599f8a0a08c5ec6c4752f734210bc2d8cf1399a403",
  "tests/test_openexempt_frozen_eval.py": "6ecd550e6f3d66ed086975cc0b7b1d945b6c73c2a4b2174f240ba09332f1a8c8",
  "artifacts/research/openexempt_legal_scope_20261020/source_snapshots/runtime_versions_20261023/openexempt_trace2skill__b7277fb9d6e94abac4ffd92e1c74e66f477ccbcab7523f886b993346ab5dc5b7.py": "b7277fb9d6e94abac4ffd92e1c74e66f477ccbcab7523f886b993346ab5dc5b7",
  "artifacts/research/openexempt_legal_scope_20261020/source_snapshots/runtime_versions_20261023/openexempt_online__732f1a924d0e49333de0384b5d6a63a25d990eb9d187874a9b1e54d114032c1c.py": "732f1a924d0e49333de0384b5d6a63a25d990eb9d187874a9b1e54d114032c1c",
  "artifacts/research/openexempt_legal_scope_20261020/source_snapshots/runtime_versions_20261023/openexempt_online_phase_dispatch_20261023__e8a2d2e4eff63d2d1cda876e3de545db60459bbf69a7573e2fc098ff94773705.py": "e8a2d2e4eff63d2d1cda876e3de545db60459bbf69a7573e2fc098ff94773705",
  "artifacts/research/openexempt_legal_scope_20261020/source_snapshots/runtime_versions_20261023/experiment__07a4f9599d72da83be97eac54c04e4601ebae8645506b06615f0830a14bfca88.py": "07a4f9599d72da83be97eac54c04e4601ebae8645506b06615f0830a14bfca88",
  "artifacts/research/openexempt_legal_scope_20261020/source_snapshots/runtime_versions_20261023/openexempt_ace_online__9321cb95d4374467484e34d46170a59e1911ba299f3a922ebd566fb7169c3fc0.py": "9321cb95d4374467484e34d46170a59e1911ba299f3a922ebd566fb7169c3fc0",
  "artifacts/research/openexempt_legal_scope_20261020/source_snapshots/runtime_versions_20261023/experiment_before_teacher_timeout_logs_20261023__7f598092149e21d0bfec923e682d19a046ae61a88c112a4768669e9d81369e17.py": "7f598092149e21d0bfec923e682d19a046ae61a88c112a4768669e9d81369e17",
  "artifacts/research/openexempt_legal_scope_20261020/source_snapshots/initial_eval_20261025/experiments__openexempt_frozen_eval__26501c279eba6446f08e797898e7800b65c9c7043dee61ae3bba9594e18d24b0.py": "26501c279eba6446f08e797898e7800b65c9c7043dee61ae3bba9594e18d24b0",
  "artifacts/research/openexempt_legal_scope_20261020/source_snapshots/initial_eval_20261025/tests__test_openexempt_contract__03591a0bc9a4b82b40694e3ba6f3b3a0c3c1b91c6051a5e68e0deabfa6d56e7f.py": "03591a0bc9a4b82b40694e3ba6f3b3a0c3c1b91c6051a5e68e0deabfa6d56e7f",
  "artifacts/research/openexempt_legal_scope_20261020/source_snapshots/initial_eval_20261025/legal_skill_guard__learning__runtime_sources__130cf7a88b993190b790453db867184ca0adeb6aa531346a3f842d0c8eb4b712.py": "130cf7a88b993190b790453db867184ca0adeb6aa531346a3f842d0c8eb4b712",
  "artifacts/research/openexempt_legal_scope_20261020/source_snapshots/initial_eval_20261025/tests__test_openexempt_frozen_eval__2103e3b3e77f8950b0d672a0afc7f9abf2d337a685e59a0960aeb6a4e0bed066.py": "2103e3b3e77f8950b0d672a0afc7f9abf2d337a685e59a0960aeb6a4e0bed066",
  "artifacts/research/openexempt_legal_scope_20261020/source_snapshots/initial_eval_20261025/README__45d45f304e90aa27adb30374efdb4285fcc20717fd00eceb8c1d894dc14acba6.md": "45d45f304e90aa27adb30374efdb4285fcc20717fd00eceb8c1d894dc14acba6"
}
EXPECTED_BEFORE = {
    "experiments/openexempt_frozen_eval.py": "26501c279eba6446f08e797898e7800b65c9c7043dee61ae3bba9594e18d24b0",
    "legal_skill_guard/learning/runtime_sources.py": "130cf7a88b993190b790453db867184ca0adeb6aa531346a3f842d0c8eb4b712",
    "tests/test_openexempt_frozen_eval.py": "2103e3b3e77f8950b0d672a0afc7f9abf2d337a685e59a0960aeb6a4e0bed066",
}
def save(name, value):
    return RunStore.immutable_json(OUT / (name + ".json"), {"at": now(), **value})

def live(pid, expected):
    p = Path("/proc") / str(pid) / "stat"
    try:
        return p.read_text().rsplit(") ", 1)[1].split()[19] == expected
    except FileNotFoundError:
        return False

def command(argv):
    shown = argv[:2] + ["<generated local configuration patch>"] if argv[0] == str(PATCHER) else argv
    print(json.dumps({"at": now(), "command": shown}), flush=True)
    subprocess.run(argv, check=True, cwd=ROOT, env=GIT_ENV)

def archive(stage):
    names = {str(Path(__file__).relative_to(ROOT))}
    names.update(str(p.relative_to(ROOT)) for p in OUT.rglob("*")
                 if p.is_file() and p.name not in ("progress.json", ".controller.lock"))
    return preserve(QUEUE, stage, sorted(names))

def check_stop():
    if (OUT / "STOP").exists():
        raise RuntimeError("Explicit handoff STOP marker; no further phase is authorized")

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / ".controller.lock").open("a") as own:
        fcntl.flock(own, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if CONFIG.exists() or (ROOT / "runs" / read(TEMPLATE)["run_id"]).exists():
            raise FileExistsError("Never overwrite, retry or resume selected TEST answers")
        if sha(TRAIN_CONFIG) != "85a961c171c715d07b2615812e0c817359da75a6455ba2656661f3f6c05d9d29":
            raise ValueError("Keep the one original adaptive training config")
        if not live(379868, "501319825") or not live(958223, "486445918"):
            raise RuntimeError("Queue only the positively identified live learner and single 8B server")
        pins = {"controller_sha256": sha(Path(__file__)), "template_sha256": sha(TEMPLATE)}
        save("queued", {**pins, "learner": [379868, "501319825"], "model": [958223, "486445918"],
            "implementation": IMPLEMENTATION, "expected_pre_handoff_HEAD": BASE_HEAD,
            "six_retained_conditions": read(TEMPLATE)["retained_initial_arms"],
            "no_teacher_or_additional_learning": True, "independent_repeats": "USER_DEFERRED"})
        save("queued_preservation", archive("queued-before-training-terminal"))
        while live(379868, "501319825"):
            check_stop()
            if not live(958223, "486445918"):
                raise RuntimeError("Original inference service changed; never deploy or substitute a model")
            progress = read(TRAIN / "progress.json")
            event = {"at": now(), "state": "waiting_original_TRAIN_terminal",
                     "original_learner_live": True, "original_model_live": True,
                     "stage": progress.get("stage"), "native": progress.get("completed_native_calls")}
            RunStore.atomic_json(OUT / "progress.json", event)
            print(json.dumps(event), flush=True)
            time.sleep(30)
        check_stop()
        if sha(Path(__file__)) != pins["controller_sha256"] or sha(TEMPLATE) != pins["template_sha256"]:
            raise RuntimeError("Queued controller/template changed")
        if (TRAIN / "failure.json").exists():
            raise RuntimeError("Failed TRAIN is not a complete method; keep all outcomes and do not launch TEST")
        complete, terminal = read(TRAIN / "completion.json"), read(TRAIN / "terminal_preservation.json")
        publication, b1 = read(TRAIN / "publications/b8.json"), read(TRAIN / "frozen_after_B1.json")
        if (complete.get("status") != "completed_bounded_mechanism_study"
                or len(complete.get("batch_summary", [])) != 8
                or any(complete["prequential_skills"][f]["tasks"] != 128 for f in ("EC", "EV"))
                or publication["bank"] != complete["bank"]
                or b1["bank_sha256"] != "509fcf9408a5c92719df6a799693487db3bd8ff00fb3178e79a88b9665b87860"):
            raise ValueError("Require the complete original eight-batch stream and its unique final/ownB1 banks")
        if len(terminal.get("paths", [])) != 2:
            raise ValueError("Require completed original dual terminal preservation")
        for item in terminal["paths"]:
            if sha(Path(item["path"])) != item["sha256"]:
                raise ValueError("Original terminal backup bytes changed")
        if len({Path(p["path"]).stat().st_dev for p in terminal["paths"]}) != 2:
            raise ValueError("Original terminal backups must be on distinct devices")
        with (ROOT / "artifacts/openexempt_training.lock").open("a") as gate:
            fcntl.flock(gate, fcntl.LOCK_EX | fcntl.LOCK_NB)
            manifest = read(TRAIN_CONFIG.with_suffix(".frozen.json"))
            if len(manifest["files"]) != 380 or any(sha(ROOT / n) != d for n, d in manifest["files"].items()):
                raise ValueError("Do not promote over a changed live-bound training source")
            for name, digest in EXPECTED_BEFORE.items():
                if sha(ROOT / name) != digest:
                    raise ValueError("An evaluator source changed before promotion: " + name)
            for name, digest in EXPECTED_AFTER.items():
                if name not in EXPECTED_BEFORE and (ROOT / name).exists() and sha(ROOT / name) != digest:
                    raise ValueError("Never overwrite a different existing preserved source: " + name)
            if subprocess.check_output([GIT, "rev-parse", "HEAD"], cwd=ROOT, env=GIT_ENV, text=True).strip() != BASE_HEAD:
                raise RuntimeError("Canonical HEAD changed; request a manual provenance review, not a forced merge")
            save("training_complete_preserved", {
                "completion_sha256": sha(TRAIN / "completion.json"),
                "publication_B8_sha256": sha(TRAIN / "publications/b8.json"),
                "terminal_preservation_sha256": sha(TRAIN / "terminal_preservation.json"),
                "final_bank_sha256": csha(publication["bank"]),
                "own_B1_bank_sha256": b1["bank_sha256"], "canonical380_unchanged_before_promotion": True,
                "dual_terminal_archives_verified": terminal["paths"]})
            command([GIT, "-c", "user.name=Codex", "-c", "user.email=codex@localhost", "cherry-pick", IMPLEMENTATION])
            if any(sha(ROOT / n) != d for n, d in EXPECTED_AFTER.items()):
                raise ValueError("Promoted sources differ from the exact isolated tested implementation")
            save("source_promoted", {"implementation": IMPLEMENTATION, "source_sha256": EXPECTED_AFTER})
            cfg = read(TEMPLATE)
            main_arm = next(a for a in cfg["arms"] if a["role"] == "evolved")
            if main_arm["bank_sha256"] is not None:
                raise ValueError("The prospective template cannot preselect a terminal bank")
            main_arm["bank_sha256"] = csha(publication["bank"])
            cfg["inference_dependency_artifacts"] = list(dict.fromkeys(
                cfg.get("inference_dependency_artifacts", []) + [
                    str(Path(__file__).relative_to(ROOT)), str(TEMPLATE.relative_to(ROOT)),
                    str((OUT / "queued.json").relative_to(ROOT)),
                    str((OUT / "training_complete_preserved.json").relative_to(ROOT)),
                    str((OUT / "source_promoted.json").relative_to(ROOT))]))
            if CONFIG.exists() or sha(PATCHER) != PATCHER_SHA:
                raise RuntimeError("Exact local patch executable/config creation boundary changed")
            content = json.dumps(cfg, ensure_ascii=False, indent=2) + "\n"
            patch = "*** Begin Patch\n*** Add File: " + str(CONFIG) + "\n"
            patch += "".join("+" + line + "\n" for line in content.splitlines()) + "*** End Patch\n"
            command([str(PATCHER), "--codex-run-as-apply-patch", patch])
        check_stop()
        command([sys.executable, "-m", "experiments.openexempt_frozen_eval", "freeze", str(CONFIG)])
        save("evaluation_frozen", {"config_sha256": sha(CONFIG),
             "frozen_sha256": sha(CONFIG.with_suffix(".frozen.json")),
             "unique_final_bank": csha(publication["bank"]), "new_native_requests_at_most": 512,
             "retained_logical_predictions": 1536, "teacher_calls": 0})
        check_stop()
        if not live(958223, "486445918"):
            raise RuntimeError("Original single model exited before evaluation; no restart/substitution")
        command([sys.executable, "-u", "-m", "experiments.openexempt_frozen_eval", "run", str(CONFIG)])
        result = read(ROOT / "runs" / cfg["run_id"] / "completion.json")
        save("completed", {"evaluation_run_id": cfg["run_id"], "status": result["status"],
             "actual_native_calls": result["actual_native_calls"], "teacher_calls": result["teacher_calls"],
             "no_score_selected_bank_or_retry": True, "manuscript_integration_and_matched_controls_still_due": True})

if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        if OUT.is_dir() and not (OUT / "failure.json").exists():
            save("failure", {"error": repr(exc), "traceback": traceback.format_exc(),
                             "no_retry_or_fallback": True})
        raise
    finally:
        if (OUT / "queued.json").exists():
            save("actual_terminal_preservation", archive("actual-controller-terminal"))
