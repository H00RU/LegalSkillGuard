"""Native-feedback selection and learned external co-revision evidence."""
from __future__ import annotations

from dataclasses import dataclass, field
import math

from .objects import digest


@dataclass
class ReplayBudget:
    blocks: int = 0
    logical_executions: int = 0

    def admit_block(self, revisions, parents):
        if not 1 <= revisions <= 3 or not 1 <= parents <= 8 or self.blocks >= 3:
            raise ValueError('The shared three-block, three-revision, eight-parent budget is fixed')
        required = (1 << revisions) * parents
        if self.logical_executions + required > 192:
            raise ValueError('Candidate-parent execution allowance exceeded')
        self.blocks += 1
        self.logical_executions += required


@dataclass
class VersionTable:
    revision_hashes: tuple
    trigger: tuple
    history: tuple
    cells: dict = field(default_factory=dict)
    traces: dict = field(default_factory=dict)

    def __post_init__(self):
        if not 1 <= len(self.revision_hashes) <= 3 or not self.trigger:
            raise ValueError('One to three exact revisions and a fixed trigger cohort required')
        if len(set(self.revision_hashes)) != len(self.revision_hashes):
            raise ValueError('Duplicate revision')
        sources = self.trigger + self.history
        if len(set(sources)) != len(sources) or len(sources) > 8:
            raise ValueError('Trigger plus disjoint fixed history has at most eight parent sources')

    def observe(self, mask, source, grade, trace):
        if type(mask) is not int or not 0 <= mask < (1 << len(self.revision_hashes)):
            raise ValueError('Unknown mixed-version assignment')
        if source not in self.trigger + self.history:
            raise ValueError('Source outside this exact replay cohort')
        if grade is not None and (not math.isfinite(grade) or not 0 <= grade <= 1):
            raise ValueError('Native parent-source grade must be in [0,1] or unmeasured')
        key = (mask, source)
        if key in self.cells and (self.cells[key] != grade or self.traces[key] != trace):
            raise ValueError('Keep the original outcome; stochastic repeats need explicit identities')
        self.cells[key] = grade
        self.traces[key] = trace

    def acceptable(self, mask):
        if not mask:
            return False
        sources = self.trigger + self.history
        if any(self.cells.get((m, source)) is None for m in (0, mask) for source in sources):
            return None
        gain = sum(self.cells[mask, s] - self.cells[0, s] for s in self.trigger) / len(self.trigger)
        retained = all(self.cells[mask, s] >= self.cells[0, s] for s in self.history)
        return gain > 0 and retained

    @property
    def complete(self):
        return all(self.cells.get((mask, source)) is not None
            for mask in range(1 << len(self.revision_hashes)) for source in self.trigger + self.history)

    def minimal_blocks(self):
        if not self.complete:
            return []  # Unknown is not a rejected true subset.
        accepted = [m for m in range(1, 1 << len(self.revision_hashes)) if self.acceptable(m)]
        return [mask for mask in accepted if not any(subset != mask and subset & mask == subset
                                                    for subset in accepted)]

    def classify(self):
        if not self.complete:
            return 'harmful_or_unresolved'
        blocks = self.minimal_blocks()
        if any(mask.bit_count() == 1 for mask in blocks):
            return 'single_sufficient'
        if blocks:
            return 'joint_needed'
        return 'harmful_or_unresolved'

    def choose(self, added_read_tokens):
        if not self.complete:
            return None
        # Joint necessity and update selection are separate questions. The
        # common protocol ranks gain before edit count, so a larger improving
        # package must remain eligible even if a singleton also improves.
        choices = [mask for mask in range(1, 1 << len(self.revision_hashes)) if self.acceptable(mask)]
        if not choices:
            return None
        def key(mask):
            gain = sum(self.cells[mask, source] - self.cells[0, source] for source in self.trigger) / len(self.trigger)
            return gain, -mask.bit_count(), -added_read_tokens[mask], -mask
        return max(choices, key=key)

    def export(self):
        value = {'revision_hashes': self.revision_hashes, 'trigger': self.trigger, 'history': self.history,
            'mixed_version_table': [{'mask': mask, 'source': source, 'native_parent_grade': self.cells.get((mask, source)),
                'trace': self.traces.get((mask, source)),
                'measured': self.cells.get((mask, source)) is not None,
                'attempt_recorded': (mask, source) in self.cells}
                for mask in range(1 << len(self.revision_hashes)) for source in self.trigger + self.history],
            'complete': self.complete, 'minimal_blocks': self.minimal_blocks(),
            'classification': self.classify(), 'unmeasured_assignments': 'unknown'}
        return {**value, 'hash': digest(value)}


def rank_patterns(patterns, verified_context):
    """Exact observed legal relation fields first; unknown is not matching data."""
    ranked = []
    for pattern in patterns:
        required = pattern['verified_relation_fields']
        if not required or any(verified_context.get(k) in (None, 'unknown') or verified_context[k] != v
                               for k, v in required.items()):
            continue
        counts = pattern['counts_by_context'].get(digest(verified_context), {'joint_needed': 0,
            'single_sufficient': 0, 'harmful_or_unresolved': 0})
        rate = (counts['joint_needed'] + 1) / (sum(counts.values()) + 3)
        ranked.append((len(required), rate, -pattern['observed_read_tokens'], pattern['id']))
    return [identity for _, _, _, identity in sorted(ranked, reverse=True)]


def observe_transfer(pattern, verified_context, table):
    """Retain adverse/singleton evidence in its exact observed context cell."""
    key = digest(verified_context)
    counts = pattern['counts_by_context'].setdefault(key,
        {'joint_needed': 0, 'single_sufficient': 0, 'harmful_or_unresolved': 0})
    outcome = table.classify()
    counts[outcome] += 1
    pattern.setdefault('evidence', []).append({'context_hash': key, 'outcome': outcome,
        'exact_version_table': table.export()})
    return outcome
