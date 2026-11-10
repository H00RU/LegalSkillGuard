"""Verified native data access, source alignment and split-metadata audit.

TEST bodies are never returned by this module. Native branch/leaf IDs remain
only in the original gold/evaluator layer, not learned content inventories.
"""
from collections import Counter, defaultdict
from pathlib import Path
import hashlib
import json
import re
import unicodedata

SOURCE_SHA256 = '826bb2afb1b4ed5938043dc22802f22ac094df562e36acb9e348f52f928cfc19'
QUOTAS = {'train': 256, 'dev': 64, 'test': 128}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):h.update(chunk)
    return h.hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text())


def write_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.temporary')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(path)


def occurrences(source, text):
    if not text:return []
    out = [];start = 0
    while True:
        found = source.find(text, start)
        if found < 0:return out
        out.append([found, found + len(text)]);start = found + 1


def nonspace(text):
    return ''.join(c for c in text if not c.isspace())


def context_mask(context, target, visible_end):
    """Mask every target copy, including whitespace-only alternate renderings.

    Character maps change only the context view, never source/gold offsets.
    Fail closed when the target cannot be aligned to its context.
    """
    indices = [i for i,c in enumerate(context) if not c.isspace()]
    compact = ''.join(context[i] for i in indices)
    needle = nonspace(target)
    matches = occurrences(compact, needle)
    if not matches:raise ValueError('Target is not a whitespace-equivalent context substring')
    visible = len(nonspace(target[:visible_end]))
    hidden = set()
    for start,end in matches:
        hidden.update(indices[start+visible:end])
    return ''.join('□' if i in hidden else c for i,c in enumerate(context))


def leaves(tree):
    if tree is None:return
    if not isinstance(tree, dict):raise ValueError('Non-object native condition')
    if 'text' in tree and 'tag' in tree:
        yield tree;return
    if tree.get('op') not in {'AND', 'OR'} or not isinstance(tree.get('items'), list):
        raise ValueError('Unsupported native condition node; do not default to true')
    for child in tree['items']:yield from leaves(child)


class NativeDataset:
    def __init__(self, raw_path, manifest_path):
        self.raw_path = Path(raw_path);self.manifest_path = Path(manifest_path)
        if sha(self.raw_path) != SOURCE_SHA256:raise ValueError('Native source SHA mismatch')
        self.manifest = load_json(self.manifest_path)
        if self.manifest['source_sha256'] != SOURCE_SHA256:raise ValueError('Split/source mismatch')
        self.metadata = self.manifest['items']
        raw = load_json(self.raw_path)
        self.schema = raw['schema']
        # One monolithic author file supplies the fixed split. Only TRAIN/DEV
        # records are retained and exposed; no TEST gold is returned/logged.
        permitted = {m['item_id'] for m in self.metadata if m['split'] in {'train', 'dev'}}
        self._records = {r['item_id']: r for r in raw['items'] if r['item_id'] in permitted}
        self._metadata = {m['item_id']: m for m in self.metadata}
        if len(self._records) != len(permitted):raise ValueError('Missing selected native records')

    def split(self, name):
        if name not in {'train', 'dev'}:raise ValueError('TEST bodies/labels are sealed in this phase')
        return [{**self._records[m['item_id']], 'split': name, 'family_id': m['family_id']}
                for m in self.metadata if m['split'] == name]

    def record(self, item_id):
        if item_id not in self._records:raise ValueError('Item is outside open TRAIN/DEV')
        m = self._metadata[item_id]
        return {**self._records[item_id], 'split': m['split'], 'family_id': m['family_id']}


def metadata_audit(metadata):
    counts = Counter(m['split'] for m in metadata)
    if dict(counts) != QUOTAS:raise ValueError('Fixed 256/64/128 split not preserved')
    ids = [m['item_id'] for m in metadata]
    if len(set(ids)) != len(ids):raise ValueError('Duplicate split item')
    families = defaultdict(set);per_family = Counter();hashes = {'target_sha256': {}, 'full_article_sha256': {}}
    duplicates = []
    for m in metadata:
        families[m['family_id']].add(m['split']);per_family[m['family_id']] += 1
        for field in hashes:
            if m[field] in hashes[field]:duplicates.append({'field': field, 'items': [hashes[field][m[field]], m['item_id']]})
            hashes[field][m[field]] = m['item_id']
    cross = {k: sorted(v) for k, v in families.items() if len(v) > 1}
    return {'counts': dict(counts), 'source_families': {s: len({m['family_id'] for m in metadata if m['split'] == s}) for s in QUOTAS},
            'duplicate_item_ids': False, 'duplicate_target_or_full_article_hashes': duplicates,
            'family_ids_cross_splits': cross, 'max_records_per_family': max(per_family.values()),
            'TEST_metadata_only': True}


def normalize_title(title):
    value = unicodedata.normalize('NFKC', title).strip()
    if value.startswith('《') and value.endswith('》'):value = value[1:-1]
    value = re.sub(r'\s+', '', value)
    return value.removeprefix('最高人民法院')


def family_alias_audit(mapping):
    """Report definite textual aliases and explicit implementation-title links.

    These are metadata candidates for review, not automatic membership changes.
    No TEST body, condition or effect is read for this check.
    """
    title_to_family = defaultdict(set);raw_titles = {}
    for f in mapping:
        for title in f['titles']:
            key = normalize_title(title);title_to_family[key].add(f['family_id']);raw_titles[key] = title
    aliases = [{'normalized_title': k, 'families': sorted(v), 'reason': 'Same normalized document title'}
               for k, v in title_to_family.items() if len(v) > 1]
    links = []
    for title, owners in title_to_family.items():
        bases = []
        if title.endswith(('法实施条例', '法实施细则')):
            bases.append(re.sub(r'实施(?:条例|细则)$', '', title))
        match = re.search(r'关于适用[〈《](.+?)[〉》].*解释', title)
        if match:bases.append(normalize_title(match.group(1)))
        for base in bases:
            targets = title_to_family.get(base, set())
            if targets and owners != targets:
                links.append({'title': raw_titles[title], 'explicit_base_title': base,
                              'families': sorted(owners | targets),
                              'reason': 'Explicit implementation/application title; source-family review required'})
    return {'definite_textual_aliases': aliases, 'explicit_lineage_candidates': links,
            'family_mapping_modified': False, 'TEST_metadata_only': True}


def source_audit(records):
    stats = Counter();unaligned = [];invalid = [];tags = Counter();kinds = Counter();unit_counts = []
    for record in records:
        item = record['item_id'];text = record['input']['rule_text'];context = record['input']['full_article_text']
        if nonspace(text) not in nonspace(context):
            invalid.append({'item_id': item, 'reason': 'target_not_in_context_after_whitespace_normalization'})
        elif text not in context:stats['whitespace_only_context_differences'] += 1
        units = record['gold']['units'];unit_counts.append(len(units));stats['sources'] += 1
        stats['units'] += len(units)
        for ui, unit in enumerate(units):
            spans = occurrences(text, unit['unit_text']) or occurrences(text, unit['unit_text'].strip())
            stats['literal_unique_units'] += len(spans) == 1
            if not spans:unaligned.append({'item_id': item, 'unit_index': ui, 'kind': 'unit'})
            for branch in unit['branches']:
                stats['branches'] += 1;kinds[branch['norm_kind']] += 1
                try:ls = list(leaves(branch.get('conditions')))
                except ValueError as e:
                    invalid.append({'item_id': item, 'reason': str(e)});continue
                for leaf in ls:
                    tags[leaf['tag']] += 1;stats['leaves'] += 1
                    support = occurrences(text, leaf['text'])
                    stats['literal_unique_leaves'] += len(support) == 1
                    stats['literal_ambiguous_leaves'] += len(support) > 1
                    stats['nonliteral_leaves'] += not support
                    if not support:unaligned.append({'item_id': item, 'unit_index': ui,
                                                    'kind': 'leaf', 'tag': leaf['tag'], 'text': leaf['text']})
    return {'stats': dict(stats), 'tags': dict(tags), 'norm_kinds': dict(kinds),
            'unit_count_max': max(unit_counts), 'unaligned_native_content_retained': unaligned,
            'invalid': invalid, 'records_not_removed_based_on_model_scores': True}
