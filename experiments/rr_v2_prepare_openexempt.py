"""Generate exactly 72 OE source cases once; no outcome filtering or rerolls."""
from __future__ import annotations

import contextlib
import io
import json
import random
from pathlib import Path

from legal_skill_guard.openexempt import (
    COMMIT,
    FAMILIES,
    UPSTREAM,
    public_case_key,
    public_task,
    upstream,
)
from legal_skill_guard.rr.checkpoint import immutable_json

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    destination = ROOT / "data/cache/rr_v2/openexempt_generated.json"
    if destination.exists():
        raise FileExistsError("Fixed generation exists: reuse it, never reroll")
    settings = json.loads((UPSTREAM / "config.json").read_text())
    # One study seed, fixed before generation; no model outcomes used.
    overrides = {"asset_count_min": 2, "asset_count_max": 4, "asset_selection": "random",
                 "married_ratio": 0.5, "domicile_count_min": 2, "domicile_count_max": 4,
                 "irrelevant_asset_facts": False, "irrelevant_domicile_facts": False,
                 "asset_opinions": False, "domicile_opinions": False,
                 "state_jurisdictions": ["ARIZONA", "ILLINOIS", "OREGON", "PENNSYLVANIA", "WISCONSIN"]}
    settings.update(overrides)
    for key in ("data_directory", "asset_directory", "statute_directory", "template_directory"):
        settings[key] = str(UPSTREAM / settings[key])
    settings.update({"dataset_size": 72, "start_task_id": 2,
                     "output_directory": str(destination.parent / "unused_official_output")})
    Config = upstream("source.config").Config
    CaseGenerator = upstream("source.case_generator").CaseGenerator
    TaskGenerator = upstream("source.task_generator").TaskGenerator
    random.seed(45)
    configs = {f: Config({**settings, "terminal_task_id": i}, "rr_v2_" + f, False)
               for f, i in FAMILIES.items()}
    cases = CaseGenerator(configs["EC"])
    generators = {f: TaskGenerator(c) for f, c in configs.items()}
    sources = []
    seen = set()
    # Official generators compute labels for preparation only. Their reference
    # solver is not registered as a prediction tool.
    with contextlib.redirect_stdout(io.StringIO()):
        for i in range(72):
            case = cases.generate_case()
            key = public_case_key(case)
            if key in seen:
                raise ValueError("Duplicate case; retain the fixed seed and investigate, no reroll")
            seen.add(key)
            tasks, targets = {}, {}
            for family, generator in generators.items():
                task = generator.generate_task(case)
                tasks[family] = public_task(task, i + 1, key, family)
                targets[family] = task.solution
            sources.append({"group": key, "tasks": tasks, "targets": targets,
                            "construction_only_case": case.serialize()})
    # This is a data-construction artifact. Public packets will exclude targets
    # and serialized reference-only fields before the model allowlist is sealed.
    receipt = {"upstream_commit": COMMIT, "seed": 45, "source_cases": 72,
               "generation_overrides": overrides, "sources": sources,
               "model_calls": 0, "resampled_by_outcome": False}
    checksum = immutable_json(destination, receipt)
    print(json.dumps({"path": str(destination), "sha256": checksum,
                      "source_cases": len(sources), "model_calls": 0}))


if __name__ == "__main__":
    main()
