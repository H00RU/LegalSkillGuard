"""Training/scoring-only reference adapters; never prediction tools."""
from __future__ import annotations

import importlib.util
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path

from .horn import Atom, Rule, closure

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def _reference_environment(directory: Path):
    original = Path.cwd()
    old_path = list(sys.path)
    try:
        sys.path.insert(0, str(ROOT / ".local-tools/rr-v2-deps"))
        os.chdir(directory)
        yield
    finally:
        os.chdir(original)
        sys.path[:] = old_path


def airline(arguments: dict, *, root: Path | None = None) -> int:
    location = root or ROOT / "data/cache/rr_v2/RuleArena/airline"
    with _reference_environment(location):
        spec = importlib.util.spec_from_file_location("rr_airline_reference", location / "compute_answer.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result, _ = module.compute_answer(**arguments, check_base_tables=module.check_base_tables)
    return int(result)


def reference_atom(representation: str) -> Atom:
    parts = re.findall(r'"([^"\n]*)"', representation)
    if len(parts) != 4 or parts[3] not in {"+", "-", "~"}:
        raise ValueError("Unsupported ProofWriter reference atom")
    subject, relation, obj, polarity = parts
    def term(value):
        return "?" + value if value in {"someone", "something"} else value
    if relation == "is":
        return Atom(obj, (term(subject),), polarity == "+")
    return Atom(relation, (term(subject), term(obj)), polarity == "+")


def proofwriter(reference: dict, *, facts_override: list[str] | None = None) -> dict:
    facts = {reference_atom(t) for t in (reference["facts"] if facts_override is None else facts_override)}
    rules = []
    for i, text in enumerate(reference["rules"]):
        atoms = re.findall(r'\((?:"[^"\n]*"\s*){4}\)', text)
        if not atoms or "->" not in text:
            raise ValueError("Unsupported ProofWriter reference rule")
        rules.append(Rule(tuple(reference_atom(t) for t in atoms[:-1]),
                          reference_atom(atoms[-1]), f"reference_rule_{i}"))
    return closure(facts, rules, reference_atom(reference["query"]))
