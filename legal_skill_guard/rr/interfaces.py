"""Method B: collision witnesses, finite interface refinement and connectors.

Only source-derived semantic metadata enters refinement. Learned artifacts store
field families and role-parameterized graphs, never example values or labels.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from itertools import combinations
from typing import Any, Callable

from .coverage import digest

FIELDS = (
    "entity_equality", "membership", "owner_period_keys", "contribution_lineage",
    "aggregation_stage", "balance", "allocation_policy", "order_observable",
)
CONNECTORS = frozenset({"bind_rename", "join_on", "project_exists", "group_by",
                        "map", "fold_reduce", "thread_allowance"})


class InterfaceError(ValueError):
    pass


@dataclass(frozen=True)
class Relation:
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    closed: bool = True  # closure of the supplied input, not the real world

    def __post_init__(self):
        if len(set(self.columns)) != len(self.columns):
            raise InterfaceError("Duplicate columns")
        if any(len(r) != len(self.columns) for r in self.rows):
            raise InterfaceError("Row arity mismatch")

    def rename(self, mapping: dict[str, str]) -> Relation:
        if not mapping.keys() <= set(self.columns):
            raise InterfaceError("Missing source column")
        return Relation(tuple(mapping.get(c, c) for c in self.columns), self.rows, self.closed)

    def join(self, other: Relation, on: tuple[str, ...]) -> Relation:
        if not set(on) <= set(self.columns).intersection(other.columns):
            raise InterfaceError("Join requires available entity witness columns")
        overlap = set(self.columns).intersection(other.columns)
        if overlap != set(on):
            raise InterfaceError("Rename nonjoin overlapping columns explicitly")
        extra = tuple(c for c in other.columns if c not in on)
        li = [self.columns.index(c) for c in on]
        ri = [other.columns.index(c) for c in on]
        result = []
        for left in self.rows:
            for right in other.rows:
                if all(digest(left[i]) == digest(right[j]) for i, j in zip(li, ri)):
                    result.append(left + tuple(right[other.columns.index(c)] for c in extra))
        return Relation(self.columns + extra, tuple(result), self.closed and other.closed)

    def exists(self) -> bool:
        return bool(self.rows)

    def group(self, keys: tuple[str, ...]) -> dict[tuple, Relation]:
        if not set(keys) <= set(self.columns) or not self.closed:
            raise InterfaceError("Group reduction requires keys and closed input")
        groups = {}
        for row in self.rows:
            key = tuple(row[self.columns.index(c)] for c in keys)
            groups.setdefault(key, []).append(row)
        return {k: Relation(self.columns, tuple(v), True) for k, v in groups.items()}


@dataclass(frozen=True)
class Amount:
    value: int
    unit: str
    owner: str
    period: str
    lineage: frozenset[str]
    stage: str = "element"

    def __post_init__(self):
        if type(self.value) is not int or self.value < 0 or not self.lineage:
            raise InterfaceError("Exact nonnegative amount and contribution lineage required")
        if self.stage not in {"element", "closed_group"}:
            raise InterfaceError("Unclosed aggregate")


def sum_amounts(items: list[Amount], *, allow_multiplicity: bool = False) -> Amount:
    if not items:
        raise InterfaceError("Empty sum needs an explicit typed zero")
    first, seen = items[0], set()
    for a in items:
        if (a.unit, a.owner, a.period) != (first.unit, first.owner, first.period):
            raise InterfaceError("Reduce must retain unit, owner and period")
        if seen.intersection(a.lineage) and not allow_multiplicity:
            raise InterfaceError("Repeated contribution without source permission")
        seen.update(a.lineage)
    return Amount(sum(a.value for a in items), first.unit, first.owner, first.period,
                  frozenset(seen), "closed_group")


def cap(amount: Amount, limit: int, *, scope: str) -> Amount:
    if type(limit) is not int or limit < 0 or scope != amount.stage:
        raise InterfaceError("Cap requires its declared complete scope")
    # Cap is a transform: no consumable balance and no state version.
    return Amount(min(amount.value, limit), amount.unit, amount.owner, amount.period,
                  amount.lineage, amount.stage)


@dataclass
class AllowanceState:
    initial: int
    balance: int
    allocation_policy: str
    order_observable: bool
    version: int = 0


class AllowanceBank:
    """One authoritative state per (rule, owner, period); no branch cloning."""

    def __init__(self):
        self.states: dict[tuple[str, str, str], AllowanceState] = {}
        self.events: list[dict] = []

    def __rr_state__(self) -> dict:
        return {"states": [{"key": key, **asdict(state)}
                            for key, state in sorted(self.states.items())], "events": self.events}

    def create(self, key: tuple[str, str, str], balance: int, *, policy: str,
               order_observable: bool) -> None:
        if key in self.states:
            raise InterfaceError("Allowance already exists; copying it would duplicate entitlement")
        if type(balance) is not int or balance < 0 or policy not in {"input_order", "reverse_order"}:
            raise InterfaceError("Unresolved allocation policy or invalid balance")
        if len(key) != 3 or type(order_observable) is not bool:
            raise InterfaceError("Allowance key/policy contract")
        self.states[key] = AllowanceState(balance, balance, policy, order_observable)

    def consume(self, key: tuple[str, str, str], value: int, *, expected_version: int) -> int:
        state = self.states[key]
        if state.version != expected_version:
            raise InterfaceError("Stale or forked allowance state")
        if type(value) is not int or value < 0:
            raise InterfaceError("Negative/noninteger consumption")
        used = min(value, state.balance)
        state.balance -= used
        state.version += 1
        self.events.append({"key": key, "used": used, "balance": state.balance,
                            "version": state.version})
        return used

    def thread(self, key: tuple[str, str, str], amounts: list[Amount]) -> list[Amount]:
        state = self.states[key]
        order = list(range(len(amounts)))
        if state.allocation_policy == "reverse_order":
            order.reverse()
        output = list(amounts)
        for i in order:
            a = amounts[i]
            if (a.owner, a.period) != key[1:]:
                raise InterfaceError("Consumption bound to a different owner or period")
            used = self.consume(key, a.value, expected_version=state.version)
            output[i] = Amount(a.value - used, a.unit, a.owner, a.period, a.lineage, a.stage)
        return output


def alpha_structure(value: Any) -> Any:
    """Rename tagged entities/lineage jointly, preserving equality and ownership.

    IDs must be explicitly tagged {entity: name} / {lineage: name}. Arbitrary
    strings cannot become learning metadata. Field names are fixed role names.
    """
    names: dict[str, dict[str, str]] = {"entity": {}, "lineage": {}}

    def visit(node):
        if isinstance(node, dict):
            if len(node) == 1 and next(iter(node)) in names:
                kind, original = next(iter(node.items()))
                if not isinstance(original, str):
                    raise InterfaceError("Tagged identifier must be a string")
                table = names[kind]
                if original not in table:
                    table[original] = f"{kind[0]}{len(table)}"
                return {kind: table[original]}
            return {k: visit(v) for k, v in sorted(node.items())}
        if isinstance(node, (tuple, list)):
            return [visit(v) for v in node]
        if type(node) in {bool, int} or node is None:
            return node
        # Categorical metadata is a finite schema, not an arbitrary string slot.
        if node in {"element", "closed_group", "input_order", "reverse_order", "unknown"}:
            return node
        raise InterfaceError("Unscoped identifier or string fingerprint in metadata")

    return visit(value)


@dataclass(frozen=True)
class Observation:
    coarse: Any
    metadata: dict[str, Any]
    answer: Any
    view_hash: str

    def normalized(self) -> dict:
        if not self.metadata.keys() <= set(FIELDS):
            raise InterfaceError("Forbidden metadata field")
        # Joint normalization, not separate per-field maps which lose identity.
        return alpha_structure(self.metadata)


@dataclass(frozen=True)
class Collision:
    left: str
    right: str
    distinguishing_fields: tuple[str, ...]


@dataclass
class Refinement:
    status: str
    minimal_field_sets: list[tuple[str, ...]]
    collisions: list[Collision]

    def pattern(self) -> dict:
        return {"status": self.status, "field_sets": self.minimal_field_sets,
                "evidence_count": len(self.collisions), "schema_version": 1}


def refine(observations: list[Observation], weights: dict[str, int] | None = None) -> Refinement:
    normalized = [o.normalized() for o in observations]
    collisions = []
    for i, j in combinations(range(len(observations)), 2):
        a, b = observations[i], observations[j]
        if digest(a.coarse) != digest(b.coarse) or digest(a.answer) == digest(b.answer):
            continue
        fields = tuple(f for f in FIELDS if digest(normalized[i].get(f)) != digest(normalized[j].get(f)))
        collisions.append(Collision(a.view_hash, b.view_hash, fields))
    if any(not c.distinguishing_fields for c in collisions):
        return Refinement("unrecoverable_interface_information", [], collisions)
    if not collisions:
        return Refinement("no_observed_collision", [()], [])
    w = {f: 1 for f in FIELDS} if weights is None else weights
    if set(w) != set(FIELDS) or any(type(v) is not int or v <= 0 for v in w.values()):
        raise InterfaceError("Positive fixed field complexity weights required")
    solutions = []
    for n in range(len(FIELDS) + 1):
        for chosen in combinations(FIELDS, n):
            if all(set(chosen).intersection(c.distinguishing_fields) for c in collisions):
                solutions.append((sum(w[f] for f in chosen), chosen))
    best = min(c for c, _ in solutions)
    minima = [s for c, s in solutions if c == best]
    return Refinement("identified_on_observed_collisions" if len(minima) == 1 else
                      "ambiguous_interface", minima, collisions)


class OracleViews:
    """Charge before querying, including discarded views and oracle failures.

    Caller must supply a durable reserve callback; this class cannot silently
    create an unaccounted oracle for an unsupported dataset or TEST source.
    """

    def __init__(self, source: str, dataset: str, split: str,
                 reserve: Callable[[str, str], None], oracle: Callable):
        if split != "train" or dataset == "ContractNLI":
            raise InterfaceError("No training variant oracle for this partition/dataset")
        self.source, self.reserve, self.oracle = source, reserve, oracle
        self.queried: list[str] = []

    def query(self, public_view: dict) -> Any:
        key = digest(public_view)
        if len(self.queried) >= 4:
            raise InterfaceError("Source oracle view budget exhausted")
        self.reserve(self.source, key)
        self.queried.append(key)
        return self.oracle(public_view)


@dataclass(frozen=True)
class Connector:
    """A graph using source role slots. All constants arrive via public slots."""
    graph: dict

    def validate(self) -> None:
        def check(node):
            if not isinstance(node, dict):
                raise InterfaceError("Graph must be a data-only connector")
            if set(node) == {"slot"} and isinstance(node["slot"], str):
                return
            if node.get("op") not in CONNECTORS or not set(node) <= {"op", "inputs", "params"}:
                raise InterfaceError("Unknown connector or extra executable data")
            if not isinstance(node.get("inputs"), list) or not isinstance(node.get("params", {}), dict):
                raise InterfaceError("Malformed connector")
            for child in node["inputs"]:
                check(child)
            # Parameter values are role names, enum operators or public slot
            # references. No literal numeric thresholds/amounts in learned graphs.
            for v in node.get("params", {}).values():
                if not (isinstance(v, str) or
                        isinstance(v, list) and all(isinstance(x, str) for x in v)):
                    raise InterfaceError("Graph constants must be parameterized")
        check(self.graph)

    def execute(self, slots: dict[str, Any]) -> Any:
        self.validate()

        def run(node):
            if "slot" in node:
                return slots[node["slot"]]
            op, p = node["op"], node.get("params", {})
            args = [run(n) for n in node["inputs"]]
            if op == "bind_rename" and len(args) == 1:
                return args[0].rename(dict(zip(p["from"], p["to"], strict=True)))
            if op == "join_on" and len(args) == 2:
                return args[0].join(args[1], tuple(p["keys"]))
            if op == "project_exists" and len(args) == 1:
                if not isinstance(args[0], Relation):
                    raise InterfaceError("Cannot recover witnesses from Boolean output")
                return args[0].exists()
            if op == "group_by" and len(args) == 1:
                return args[0].group(tuple(p["keys"]))
            if op == "map" and len(args) == 1 and p["primitive"] == "cap":
                if isinstance(args[0], Amount):
                    return cap(args[0], slots[p["limit_slot"]], scope=p["scope"])
                return [cap(a, slots[p["limit_slot"]], scope=p["scope"]) for a in args[0]]
            if op == "map" and len(args) == 1 and p["primitive"] == "exists":
                if not all(isinstance(r, Relation) for r in args[0]):
                    raise InterfaceError("Exists map requires available relations")
                return [r.exists() for r in args[0]]
            if op == "fold_reduce" and len(args) == 1 and p["primitive"] == "sum_amounts":
                return sum_amounts(args[0])
            if op == "fold_reduce" and len(args) == 1 and p["primitive"] in {"all", "any"}:
                if not all(type(x) is bool for x in args[0]):
                    raise InterfaceError("Boolean reduction requires Boolean inputs")
                return (all if p["primitive"] == "all" else any)(args[0])
            if op == "thread_allowance" and len(args) == 1:
                bank = slots[p["bank_slot"]]
                return bank.thread(slots[p["key_slot"]], args[0])
            raise InterfaceError("Unsupported connector arity/primitive")

        return run(self.graph)


@dataclass
class ConnectorPool:
    """Finite H: evidence-filtered synthesis, never a representation of Ω."""
    candidates: list[Connector]
    queried_views: list[str] = field(default_factory=list)

    def __post_init__(self):
        if len(self.candidates) > 32:
            raise InterfaceError("At most 32 connector candidates per source")
        for c in self.candidates:
            c.validate()

    def observe(self, view: dict, answer: Any, *, project: Callable = lambda x: x) -> None:
        self.queried_views.append(digest(view))
        retained = []
        for c in self.candidates:
            try:
                # State-bearing inputs need an independent copy per hypothesis.
                from copy import deepcopy
                if digest(project(c.execute(deepcopy(view)))) == digest(answer):
                    retained.append(c)
            except (InterfaceError, KeyError, TypeError, ValueError):
                continue
        self.candidates = retained

    def predict(self, view: dict, *, project: Callable = lambda x: x) -> dict:
        if not self.candidates:
            return {"status": "NO_VALID_CONNECTOR", "answer": None}
        from copy import deepcopy
        values, states = [], []
        for c in self.candidates:
            local = deepcopy(view)
            values.append(project(c.execute(local)))
            states.append({name: value.__rr_state__() for name, value in local.items()
                           if hasattr(value, "__rr_state__")})
        if len({digest(v) for v in values}) != 1:
            return {"status": "ambiguous_connector", "answer": None, "execution_states": states}
        return {"status": "candidate_pool_agreement_only", "answer": values[0],
                "certificate_status": "translation_unresolved", "is_Omega": False,
                "execution_states": states}


def choose_view(pool: ConnectorPool, public_candidates: list[dict],
                *, project: Callable = lambda x: x) -> dict | None:
    """Maximum pairwise disagreement; no oracle/gold access during selection."""
    from copy import deepcopy
    ranked = []
    for i, view in enumerate(public_candidates):
        predictions = []
        try:
            predictions = [digest(project(c.execute(deepcopy(view)))) for c in pool.candidates]
        except (InterfaceError, KeyError, TypeError, ValueError):
            continue
        disagreement = sum(a != b for a, b in combinations(predictions, 2))
        if disagreement:
            ranked.append((-disagreement, i, view))
    return min(ranked, key=lambda x: x[:2])[2] if ranked else None
