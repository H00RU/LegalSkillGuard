#!/usr/bin/env python3
"""Select a Phase 4 candidate by pre-audit trigger coverage on generation trajectories."""

from __future__ import annotations

import argparse
import json

from legal_skill_guard.schemas.action import StructuredAction
from legal_skill_guard.schemas.state import ConsultationState
from legal_skill_guard.skills.engine import SkillEngine, condition_matches
from legal_skill_guard.skills.loader import load_skill, load_skill_directory

try:
    from scripts.run_phase1_baseline import ROOT, atomic_json
except ModuleNotFoundError:
    from run_phase1_baseline import ROOT, atomic_json  # type: ignore[no-redef]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase3-run", required=True)
    args = parser.parse_args()
    run_root = ROOT / "runs/phase3" / args.phase3_run
    candidates = [
        (path, load_skill(path))
        for path in sorted((run_root / "evolution/candidates").glob("*.yaml"))
    ]
    if not candidates:
        raise RuntimeError("No statically valid Phase 3 candidates are available")
    trajectories = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((run_root / "trajectories").glob("*/*.json"))
    ]
    seed_skills = load_skill_directory(ROOT / "skills/seed", active_only=True)
    scores: list[dict[str, object]] = []
    state_fields = set(ConsultationState.model_fields)
    for path, skill in candidates:
        triggers = 0
        triggered_sessions = 0
        activated = skill.model_copy(deep=True)
        activated.status = "active"
        library = {item.skill_id: item for item in seed_skills}
        library[activated.skill_id] = activated
        for trajectory in trajectories:
            engine = SkillEngine(list(library.values()))
            session_triggered = False
            for step in trajectory["steps"]:
                state = ConsultationState.model_validate(
                    {
                        key: value
                        for key, value in step["state_before"].items()
                        if key in state_fields
                    }
                )
                action = StructuredAction.model_validate(step["proposed_action"])
                state.candidate_action = action.model_dump(mode="python")
                if all(condition_matches(item, state, action) for item in skill.preconditions):
                    triggers += 1
                decision = engine.apply(state, action)
                session_triggered |= skill.skill_id in decision.activated_skill_ids
            triggered_sessions += int(session_triggered)
        scores.append(
            {
                "skill_id": skill.skill_id,
                "path": str(path.relative_to(ROOT)),
                "generation_step_triggers": triggers,
                "generation_sessions_activated": triggered_sessions,
            }
        )
    scores.sort(
        key=lambda item: (
            -int(item["generation_sessions_activated"]),
            -int(item["generation_step_triggers"]),
            str(item["skill_id"]),
        )
    )
    selected = scores[0]
    output = {
        "schema_version": 1,
        "phase3_run": args.phase3_run,
        "selection_policy": (
            "maximum actual session activation under the frozen seed library on "
            "training-generation visible states; then precondition coverage and skill_id; "
            "no acceptance-pool score consulted"
        ),
        "candidates": scores,
        "selected": selected,
    }
    atomic_json(run_root / "evolution/phase4_candidate_selection.json", output)
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
