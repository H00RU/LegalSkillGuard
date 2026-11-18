"""Run and audit the locked external family's learned reversible schema."""

import json

import jsonschema

from legal_skill_guard.paired_interfaces.control_answers import decode_native, source_bundle, wire_schema
from legal_skill_guard.paired_interfaces.convergence_actors import common_cells
from legal_skill_guard.paired_interfaces.convergence_schema_control import ReversibleWire, measure_schema
from legal_skill_guard.paired_interfaces.formal_actors import verify_physical_response
from legal_skill_guard.paired_interfaces.formal_evaluation import verify
from legal_skill_guard.paired_interfaces.scope_learning import strict_json
from legal_skill_guard.skill_evolution.native import record_schema, restore_enum_transport
from legal_skill_guard.skill_evolution.objects import digest


EXTERNAL_ARM = 'strongest_matched_external_baseline'


class ParseControlActor:
    def __init__(self, common, executor, root):
        self.common, self.executor, self.root = common, executor, root

    @staticmethod
    def _proposal(source, library):
        verify(library, 'snapshot_sha256')
        proposals = library.get('schema_proposals', {})
        if proposals and (library['arm'] != EXTERNAL_ARM or library['batch'] < 1):
            raise ValueError('The locked external arm alone may carry learned schema proposals')
        return proposals.get(source['dataset'])

    def __call__(self, source, library, purpose):
        proposal = self._proposal(source, library)
        if proposal is None:
            return self.common(source, library, purpose)
        reads = [measure_schema(self.executor, self.root, cell, proposal, purpose) for cell in common_cells(source)]
        return {'native': {key: value for read in reads for key, value in read['native'].items()},
                'schema_reads': reads, 'schema_library_sha256': library['snapshot_sha256'], 'fallback_executed': False}

    def verify_saved(self, source, library, purpose, result):
        proposal = self._proposal(source, library)
        if proposal is None:
            self.common.verify_saved(source, library, purpose, result)
            return
        if result['schema_library_sha256'] != library['snapshot_sha256'] or result['fallback_executed']:
            raise ValueError('An external prediction must bind its frozen library and actual schema route')
        native = {}
        for cell, row in zip(common_cells(source), result['schema_reads'], strict=True):
            if row['source_sha256'] != digest(cell) or row['proposal_sha256'] != digest(proposal):
                raise ValueError('A schema measurement must preserve the exact source and proposal')
            identity = row['physical_call_id']
            verify_physical_response(self.executor, identity=identity, source=cell['key'], purpose=purpose,
                                     content_sha256=row['response_sha256'], usage=row['usage'], finish_reason=row['finish_reason'])
            with self.executor.ledger.transaction() as db:
                physical = json.loads(db.execute('select result from calls where id=?', (identity,)).fetchone()[0])
            bundle = source_bundle(cell)
            codec = ReversibleWire(wire_schema(cell['dataset'], bundle), proposal)
            restored, answers, evidence = None, {}, {}
            try:
                if physical['finish_reason'] != 'stop':
                    raise ValueError('The physical model response did not complete')
                decoded, _ = restore_enum_transport(strict_json(physical['content']), record_schema({'value': codec.schema}))
                restored = codec.restore(decoded['value'])
                answers, evidence = decode_native(cell['dataset'], bundle, restored)
            except (ValueError, jsonschema.ValidationError):
                if row['production_error'] is None:
                    raise ValueError('The recorded prediction obscures a production decoding failure')
            else:
                if row['production_error'] is not None:
                    raise ValueError('A valid physical response may not be reported as a production failure')
            replay = {v['id']: {'handled': v['id'] in answers, 'answer': answers.get(v['id']),
                                'evidence_sentence_ids': evidence.get(v['id'], [])} for v in cell['views']}
            if replay != row['native'] or restored != row['restored_native_wire']:
                raise ValueError('The saved schema results must reproduce the original native output from the ledger')
            native.update(replay)
        if native != result['native'] or set(native) != {view['id'] for view in source['views']}:
            raise ValueError('The external route lost a native task')
