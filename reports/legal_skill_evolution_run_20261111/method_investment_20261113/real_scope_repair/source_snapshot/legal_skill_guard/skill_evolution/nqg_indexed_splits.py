"""Indexed equivalent of NQG NEW for the fixed no-repeated-target setting.

The upstream algorithm enumerates every source interval crossed with every
target interval, materializes them, then tests whether either resulting rule is
already derivable. We index those existing rules by their canonical source,
and only construct interval pairs that can pass that same membership test.
The original normalization and candidate validation remain authoritative.
"""
from collections import defaultdict

from legal_skill_guard._vendor.nqg.model.induction import split_utils
from legal_skill_guard._vendor.nqg.model.qcfg import qcfg_rule

NT1, NT2, TMP = qcfg_rule.NT_1, qcfg_rule.NT_2, split_utils.NT_TMP
UPSTREAM_FIND = split_utils.find_possible_splits


def canonical_source(tokens):
    mapping = {}; inverse = {}
    for token in tokens:
        if token in {NT1, NT2, TMP} and token not in mapping:
            if len(mapping) == 2:return None, None
            symbol = (NT1, NT2)[len(mapping)]
            mapping[token] = symbol;inverse[symbol] = token
    return tuple(mapping.get(t, t) for t in tokens), inverse


def positions(sequence, fragment):
    n = len(fragment)
    return [i for i in range(len(sequence) - n + 1) if sequence[i:i+n] == fragment]


def find_possible_splits(rule, derivable_rules, allow_repeated_target_nts=True):
    if allow_repeated_target_nts:
        # The unchanged upstream implementation remains available for settings
        # outside this study, rather than silently changing its semantics.
        return UPSTREAM_FIND(rule, derivable_rules, True)
    by_source = defaultdict(list)
    for known in derivable_rules:
        by_source[known.source].append(known)
    source, target = rule.source, rule.target
    source_counts = {}; target_positions = {}; candidates = set()
    def accept(sh, th, sg, tg):
        pair = split_utils._maybe_get_candidate_pair(sg, sh, tg, th)
        if pair is None:return
        g, h = pair
        if g in derivable_rules and h not in derivable_rules:candidates.add(h)
        elif h in derivable_rules and g not in derivable_rules:candidates.add(g)
    for a in range(len(source)):
        for b in range(a + 1, len(source) + 1):
            sh = source[a:b]
            if sh in {(NT1,), (NT2,)}:continue
            if sh not in source_counts:source_counts[sh] = len(positions(source, sh))
            if source_counts[sh] != 1:continue
            sg = source[:a] + (TMP,) + source[b:]
            if sg == (TMP,):continue
            gcanon, ginverse = canonical_source(sg)
            if gcanon is None:continue
            hcanon, hinverse = canonical_source(sh)
            # Existing inner rule h: its target is fixed after NT renaming.
            for known in by_source.get(hcanon, ()):
                th = tuple(hinverse.get(t, t) for t in known.target)
                if th not in target_positions:target_positions[th] = positions(target, th)
                hits = target_positions[th]
                if len(hits) != 1:continue
                c = hits[0];d = c + len(th)
                accept(sh, th, sg, target[:c] + (TMP,) + target[d:])
            # Existing outer rule g: its unique fresh target hole fixes the
            # target interval, so no target-interval Cartesian product exists.
            for known in by_source.get(gcanon, ()):
                tg = tuple(ginverse.get(t, t) for t in known.target)
                if tg.count(TMP) != 1:continue
                c = tg.index(TMP);prefix, suffix = tg[:c], tg[c+1:]
                d = len(target) - len(suffix)
                if d <= c or target[:c] != prefix or target[d:] != suffix:continue
                th = target[c:d]
                if th not in target_positions:target_positions[th] = positions(target, th)
                if len(target_positions[th]) != 1:continue
                accept(sh, th, sg, tg)
    return candidates
