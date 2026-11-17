"""Index existing source reviews for the original formal TRAIN roles.

No transport or grader object exists here. The explicit manifest preserves
review revisions and records missing reviews separately from known law-domain
refusals. Partial legal/source annotation is never promoted to complete gold.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
from types import SimpleNamespace

from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import BASE, ROOT, read, sha
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor
from legal_skill_guard.paired_interfaces.formal_design import source_roles
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.paired_interfaces.formal_training import ReferenceRegistry
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


PREFLIGHT = BASE / 'formal_read_preflight_v1/6e22e5920c3df1aac061f9bd159788e44b30c9bd570fc9f740c4c0894a56058f'
GENERIC = BASE / 'observed_abstention_channel_v3/8ab84a2860a622bcecbd94b2b340fbc3d38b5e22c420f0c8dfa8eb9b104cd44d/snapshots/ca524c1fe10e6024e17a5a693eebcf43e64eede1a5dd5eb863417eb5224d5385/corpus.json'
ASSET = BASE / 'asset_port_source_reviews_v1/b34952ae92340022b6ab0b26babba0ff77d5dc9038a6029afe1321042e0814b0/manifest.json'


def prepare(extra_reviews=None):
    source_lock, pilot = read(BASE / 'prepared/source_lock.json'), read(BASE / 'pilot_lock.json')
    public_path = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    if sha(public_path) != source_lock['prepared_sha256']['train']['public']:
        raise ValueError('The original TRAIN public bytes changed')
    sources = read(public_path); public = {s['key']: s for s in sources}
    roles = source_roles(source_lock, pilot)
    preflight = read(PREFLIGHT / 'protocol.json')
    if preflight['executor'] != pilot['executor']:
        raise ValueError('The frozen executor profile changed')
    review_index = {}
    for row in read(GENERIC)['inventory']:
        if row['dataset'] == 'OpenExempt':
            continue  # New OE F-port scope requires its own reviewed cards.
        item = {'source': row['source'], 'view': row['view'], 'kind': 'literal_semantic_graph',
                'path': row['audit_path'], 'sha256': row['audit_sha256']}
        identity = row['source'], row['view']
        if identity in review_index and review_index[identity] != item:
            raise ValueError('An old generic view has competing source review revisions')
        review_index[identity] = item
    for row in read(ASSET)['reviews']:
        review_index[row['source'], row['view']] = {'source': row['source'], 'view': row['view'],
            'kind': 'asset_program_ports', 'path': row['card_path'], 'sha256': row['card_sha256']}
    extra_binding = None
    if extra_reviews is not None:
        extra_reviews = extra_reviews.resolve()
        if not extra_reviews.is_relative_to(ROOT):
            raise ValueError('Additional source-only reviews must use an explicit project manifest')
        extra_binding = {'path': str(extra_reviews.relative_to(ROOT)), 'sha256': sha(extra_reviews)}
        seen = set()
        for row in read(extra_reviews)['reviews']:
            identity = row['source'], row['view']
            if identity in seen:
                raise ValueError('A reviewed view revision must be selected explicitly exactly once')
            seen.add(identity)
            review_index[identity] = row
    paths = [str(Path(__file__).relative_to(ROOT)), 'experiments/two_method_annotate.py',
             *[str(path.relative_to(ROOT)) for path in sorted((ROOT / 'legal_skill_guard/paired_interfaces').glob('*.py'))],
             *['legal_skill_guard/skill_evolution/' + name + '.py' for name in (
                 'clients', 'ledger', 'native', 'objects', 'grade_worker', 'sara_statute_kernel',
                 'partial_native_proof', 'literal_statutory_givens', 'statute_input_dependencies')],
             'legal_skill_guard/rr/checkpoint.py', 'legal_skill_guard/rr/client.py',
             'legal_skill_guard/rr/ledger.py', 'legal_skill_guard/rr/scoring.py']
    binding = {name: sha(ROOT / name) for name in paths}
    manifest = sealed({'protocol': 'formal-source-local-review-registry-v1',
        'source_public_sha256': {s['key']: digest(s) for s in sources},
        'source_lock_sha256': sha(BASE / 'prepared/source_lock.json'),
        'formal_roles_sha256': digest(roles), 'production_alignment_source_sha256': binding,
        'plan_assets_sha256': sha(PREFLIGHT / 'plan_assets.json'), 'executor': pilot['executor'],
        'explicit_extra_review_manifest': extra_binding,
        'reviews': [review_index[k] for k in sorted(review_index)],
        'source_local_reviews_not_independent_human_or_complete_legal_gold': True,
        'no_native_grading_or_external_annotation_or_weak_generation': True}, 'registry_sha256')
    # A metadata-only actor has no generate method;preparation cannot dispatch.
    actor = InterfaceActor(SimpleNamespace(config=pilot['executor']), BASE / 'unused_metadata_actor',
        plan_assets=read(PREFLIGHT / 'plan_assets.json'), source_inputs=inputs, pipeline_binding=binding)
    registry = ReferenceRegistry(ROOT, manifest, roles, public, actor)
    out = BASE / 'formal_reference_registry_v1' / manifest['registry_sha256']
    immutable_json(out / 'manifest.json', manifest)
    immutable_json(out / 'roles.json', roles)
    for name, expected in binding.items():
        destination = out / 'source_snapshot' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        raw = (ROOT / name).read_bytes()
        if destination.exists() and sha(destination) != expected:
            raise ValueError('An immutable formal source snapshot changed')
        if not destination.exists():
            destination.write_bytes(raw)
    readiness = [registry.readiness(batch) for batch in range(9)]
    immutable_json(out / 'prefix_readiness.json', readiness)
    summary = {'artifact_root': str(out.relative_to(ROOT)), 'source_mothers': len(public), 'batches': 8,
        'role_counts': dict(Counter(r['role'] for r in roles)), 'full_prefix_ready': readiness[-1]['ready'],
        'ready_source_views': len(readiness[-1]['ready_source_views']),
        'missing_source_views': len(readiness[-1]['missing_source_views']),
        'missing_source_mothers': len({s for s, _ in readiness[-1]['missing_source_views']}),
        'pre_generation_domain_refusal_views': len(readiness[-1]['pre_generation_domain_refusals']),
        'reviewed_native_undefined_worlds_not_filtered': True,
        'teacher_requests': 0, 'weak_model_requests': 0, 'native_grading_opened': False,
        'full_formal_training_DEV_TEST_or_goal_complete': False}
    immutable_json(out / 'summary.json', summary)
    return out, manifest, summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--extra-reviews', type=Path)
    args = parser.parse_args()
    out, manifest, summary = prepare(args.extra_reviews)
    print(json.dumps(summary, ensure_ascii=False))
