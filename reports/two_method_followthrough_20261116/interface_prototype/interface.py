"""Finite residual partition synthesis. No LLM calls or legal-language claims."""
from dataclasses import dataclass
from typing import Callable, Hashable, Mapping


@dataclass(frozen=True)
class Outcome:
    valid: bool
    value: Hashable = None


INVALID = Outcome(False)


@dataclass
class FiniteSpec:
    states: tuple
    contexts: tuple
    table: dict

    @classmethod
    def build(cls, states, contexts, function: Callable, valid_domain: Callable):
        states, contexts = tuple(states), tuple(contexts)
        if not states or not contexts:
            raise ValueError("Both finite domains must be nonempty")
        if len(set(states)) != len(states) or len(set(contexts)) != len(contexts):
            raise ValueError("Domain values must be unique and hashable")
        table = {}
        for u in states:
            for c in contexts:
                if valid_domain(u, c):
                    value = function(u, c)
                    hash(value)  # tuples permit native multi-query outputs
                    table[u, c] = Outcome(True, value)
                else:
                    table[u, c] = INVALID
        return cls(states, contexts, table)

    def residual(self, u):
        return tuple(self.table[u, c] for c in self.contexts)


@dataclass(frozen=True)
class Collision:
    left: Hashable
    right: Hashable
    context: Hashable
    left_output: Outcome
    right_output: Outcome


@dataclass
class Interface:
    # This is strictly H(u), never H(u,c). Decoder alone receives context.
    encoding: dict
    decoding: dict

    def encode(self, local_state):
        return self.encoding[local_state]

    def decode(self, code, context):
        return self.decoding[code, context]


def collision(spec: FiniteSpec, encoding: Mapping):
    """Return an exact witness that a proposed local grouping is insufficient."""
    if set(encoding) != set(spec.states):
        raise ValueError("Encoding must cover exactly local states, not whole worlds")
    for code in encoding.values():
        hash(code)
    for i, u in enumerate(spec.states):
        for v in spec.states[i + 1:]:
            if encoding[u] == encoding[v]:
                for c in spec.contexts:
                    a, b = spec.table[u, c], spec.table[v, c]
                    if a != b:
                        return Collision(u, v, c, a, b)
    return None


def compile_grouping(spec: FiniteSpec, encoding: Mapping):
    witness = collision(spec, encoding)
    if witness is not None:
        raise ValueError(f"Insufficient grouping: {witness!r}")
    decoder = {}
    for u in spec.states:
        for c in spec.contexts:
            decoder[encoding[u], c] = spec.table[u, c]
    return Interface(dict(encoding), decoder)


def synthesize(spec: FiniteSpec):
    """Coarsest local partition preserving output AND declared validity domain.

    Equality of complete residual vectors gives equivalence classes; it does
    not take transitive closure of pairwise common-context compatibility.
    """
    classes, encoding = {}, {}
    for u in spec.states:
        residual = spec.residual(u)
        if residual not in classes:
            classes[residual] = len(classes)
        encoding[u] = classes[residual]
    return compile_grouping(spec, encoding)


def verify(spec: FiniteSpec, interface: Interface):
    for u in spec.states:
        for c in spec.contexts:
            actual = interface.decode(interface.encode(u), c)
            if actual != spec.table[u, c]:
                return False
    return True
