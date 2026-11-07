"""One fixed paired selection; tests exercise policy, never prove backend effects."""
from __future__ import annotations


def select_thinking(records: list[dict], expected_sources: list[str]) -> dict:
    if len(expected_sources) != 20 or len(set(expected_sources)) != 20:
        raise ValueError("Thinking selection requires exactly 20 fixed training sources")
    indexed = {}
    for r in records:
        if r["source"] not in expected_sources or type(r["thinking"]) is not bool:
            raise ValueError("Thinking records contain an unauthorized source/profile")
        key = r["source"], r["thinking"]
        if key in indexed:
            raise ValueError("No repeated quality/profile sweep")
        indexed[key] = r
    if set(indexed) != {(s, thinking) for s in expected_sources for thinking in (True, False)}:
        raise ValueError("Paired thinking comparison is incomplete")
    stats = {}
    for thinking in (True, False):
        rows = [indexed[s, thinking] for s in expected_sources]
        usage_known = all(isinstance(r.get("usage"), dict) and
                          type(r["usage"].get("prompt_tokens")) is int and
                          type(r["usage"].get("completion_tokens")) is int for r in rows)
        stats[str(thinking).lower()] = {
            "structural_passes": sum(bool(r["structural_pass"]) for r in rows),
            "task_correct": sum(bool(r["task_correct"]) for r in rows),
            "tokens": sum(r["usage"]["prompt_tokens"] + r["usage"]["completion_tokens"] for r in rows)
            if usage_known else None,
            "elapsed_seconds": sum(r["elapsed_seconds"] for r in rows),
            "actual_backend_effect_verified": all(r["actual_backend_effect_verified"] for r in rows)}
    on, off = stats["true"], stats["false"]
    harm = [s for s in expected_sources if indexed[s, True]["task_correct"] and
            not indexed[s, False]["task_correct"]]
    # Fixed before calls: require no increase in either measured token cost or
    # wall time, and strict reduction in at least one. No fitted cost weights.
    lower_cost = on["tokens"] is not None and off["tokens"] is not None and \
        off["tokens"] <= on["tokens"] and off["elapsed_seconds"] <= on["elapsed_seconds"] and \
        (off["tokens"] < on["tokens"] or off["elapsed_seconds"] < on["elapsed_seconds"])
    if all("template_profile_observed" in r and "reasoning_present" in r for r in records):
        # Enabling thinking permits reasoning; it does not force every answer
        # to contain a nonempty reasoning channel. Verify the two profiles as a
        # pair using all template observations plus actual generation behavior.
        template_verified = all(r["template_profile_observed"] for r in records)
        on_reasoning = sum(bool(indexed[s, True]["reasoning_present"]) for s in expected_sources)
        off_reasoning = sum(bool(indexed[s, False]["reasoning_present"]) for s in expected_sources)
        switch_verified = template_verified and on_reasoning > 0 and off_reasoning == 0
        on["reasoning_present_outputs"], off["reasoning_present_outputs"] = on_reasoning, off_reasoning
    else:
        switch_verified = on["actual_backend_effect_verified"] and off["actual_backend_effect_verified"]
    both_invalid = on["structural_passes"] == off["structural_passes"] == 0
    choose_off = switch_verified and not both_invalid and \
        off["structural_passes"] >= on["structural_passes"] and \
        off["task_correct"] >= on["task_correct"] and not harm and lower_cost
    return {"selected_thinking": not choose_off, "stats": stats,
            "on_correct_off_incorrect_sources": harm,
            "lower_measured_resource_cost": lower_cost,
            "actual_backend_switch_verified": switch_verified,
            "engineering_block": both_invalid or not switch_verified,
            "selection_rule": "structure_and_task_nondecrease_zero_harm_tokens_and_time_pareto_reduction",
            "quality_equivalence_claim": False, "extra_sweep_authorized": False}
