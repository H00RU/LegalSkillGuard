"""Compile native OpenExempt candidates with a separate title-projection policy."""

import jsonschema

from experiments.convergence_pilot_b0 import HANDOFF, read, sha
from legal_skill_guard.paired_interfaces.convergence_compact_proposal import (
    SCHEMA, compact_native_passthrough, compile_proposal,
)
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest


DATASET = 'OpenExempt'
PROJECTION_FIELD = 'title_projection_policy'
OWNERSHIP_FIELD = 'shared_ownership_policy'
SCOPED_SCHEMA = record_schema({**SCHEMA['properties'], OWNERSHIP_FIELD: {'type': 'string'},
                               PROJECTION_FIELD: {'type': 'string'}})
SCOPED_TEACHER_SUFFIX = (
    ' Use native schema mode for the EC/EV program. The predicate_prompt and compose_source run only on '
    'full EC/EV inputs. Keep all actual assets in the native answer, including an empty claims array where '
    'applicable. Put source-level rules for reading ownership and retaining uncertainty in shared_ownership_policy. '
    'The same ownership rules are used in the native and projection readers. Put only the local computation for '
    'the requested title component in title_projection_policy. That computation runs only when the projection '
    'supplies a requested component and independently audited facts. Do not encode examples, case identities, or '
    'native answer labels in either policy.'
)


def scoped_program(reply, visible_train):
    """Bind both policies to the proposal while compiling only native fields for execution."""
    jsonschema.validate(reply, SCOPED_SCHEMA)
    ownership, projection = (reply[field].strip() for field in (OWNERSHIP_FIELD, PROJECTION_FIELD))
    if reply['schema_mode'] != 'native' or not ownership or not projection:
        raise ValueError('A scoped proposal needs a complete native program and both source and projection policies')
    if any(key in projection for key in visible_train):
        raise ValueError('The projection policy must be reusable across source identities')
    native = {key: reply[key] for key in SCHEMA['required']}
    native['predicate_prompt'] += '\nSource-level ownership rules:\n' + ownership
    program = compact_native_passthrough(compile_proposal(native, visible_train))
    return {**program, PROJECTION_FIELD: ownership + '\nRequested-component computation:\n' + projection}


def projection_policy(program, query):
    """Select the derived-field policy when the local projection contract is present."""
    if PROJECTION_FIELD not in program:
        return '\n'.join(predicate['prompt'] for predicate in program['predicates'])
    if (query.get('requested_component') not in ('forwarded', 'withheld')
            or not isinstance(query.get('independently_verified_source_facts'), dict)):
        raise ValueError('The title-projection policy requires its local source-conditioned input')
    return program[PROJECTION_FIELD]


def scope_feedback(b5_stage, conditioned_feedback):
    """Bind the observed B5 coverage error before revising matched teacher inputs."""
    path = HANDOFF / 'B5_OE_native_positive_gate_audit_20261118.json'
    audit = read(path)
    fit = read(b5_stage / 'binding.json')
    terminal = read(b5_stage / 'terminal.json')
    archive = read(b5_stage / 'source_snapshot_receipt.json')
    decisions = read(b5_stage / 'matched_decisions.json')
    proposal_dir = b5_stage / 'candidates' / 'common_teacher_skill_learning' / DATASET
    decision = read(proposal_dir / 'decision.json')
    measured = read(proposal_dir / 'measurements.json')
    if (b5_stage.name != digest(fit) or terminal['status'] != 'completed_all_five_TRAIN_updates'
            or terminal['batch'] != 5 or terminal['TEST_opened']
            or digest(decisions) != terminal['matched_decisions_sha256']
            or archive['archived_terminal_binding'] != b5_stage.name or audit['binding'] != b5_stage.name
            or archive['files'] != fit['source_sha256']
            or decision != decisions['teacher']['common_teacher_skill_learning'][DATASET]
            or sha(proposal_dir / 'decision.json') != audit['decision_sha256']
            or digest(measured['predictions']) != decision['predictions_sha256']
            or digest(measured['candidate']) != audit['candidate_sha256']
            or decisions['relation'][DATASET]['matched_proposal_sha256'] != audit['candidate_sha256']
            or decisions['relation'][DATASET]['status'] != 'retain_incumbent_on_native_train'
            or audit['TEST_opened'] or audit['candidate_entered_shared_projection']
            or not audit['proposal_includes_title_filter_component_in_native_reader']):
        raise ValueError('Use the sealed B5 native failure as the scope-revision evidence')
    rows = audit['paired_four_mothers']
    ev = [row['views']['EV'] for row in rows]
    undercovered = sum(row['candidate']['raw_asset_keys'] == 1 < row['target_asset_keys'] for row in ev)
    truncated = sum(row['candidate']['finish_reason'] == 'length' for row in ev)
    if len(rows) != 4 or not all(row['native_utility_delta'] < 0 for row in rows) or (undercovered, truncated) != (3, 1):
        raise ValueError('Report only the verified B5 coverage and native-supervision outcomes')
    return {
        'binding': {'terminal_sha256': sha(b5_stage / 'terminal.json'), 'native_coverage_audit_sha256': sha(path),
                    'teacher_schema_sha256': digest(SCOPED_SCHEMA)},
        'teacher_feedback': {
            'native_EC_EV': {
                'observed_issue': 'The previous native proposal applied the asset-specific projection guidance to full native inputs. All three completed EV responses returned only one asset. A fourth response reached the output limit.',
                'contract': 'Read the full asset list and emit one native record per actual asset, retaining each view’s supplied premises and exact citation vocabulary. Include empty claims arrays as applicable. Apply reversible field guidance only to the complete native output.',
            },
            'local_title_projection': {
                'applies_only_with': ['requested_component', 'independently_verified_source_facts'],
                **conditioned_feedback,
            },
            'case_text_and_label_examples_included': False,
        },
    }


def native_asset_counts(sources, predictions, annotations):
    rows = []
    for source in sources:
        key = source['key']
        for view in source['views']:
            family = view['id']
            native = predictions[key]['native'][family]
            rows.append({'source': key, 'view': family, 'reference_asset_count': len(annotations[key][family]['answer']),
                         'returned_asset_count': len(native['answer']) if native['handled'] else None})
    return rows
