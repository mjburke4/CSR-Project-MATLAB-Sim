"""Corruption and finite-stop accounting regressions; no MATLAB run implied."""
from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_tranche17_return as review
import test_tranche7_return as t7fixtures


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value)+'\n', encoding='utf-8')


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def files(root, exclude=()):
    return [dict(path=path.relative_to(root).as_posix(), sha256=review.sha256(path), bytes=path.stat().st_size)
            for path in sorted(root.rglob('*')) if path.is_file() and path.relative_to(root).as_posix() not in exclude]


class TemporaryCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)


class CandidateAndTests(TemporaryCase):
    def setUp(self):
        super().setUp()
        for name in ('Alpha', 'Beta'):
            path = self.root/f'tests/Test{name}.m'
            path.parent.mkdir(exist_ok=True)
            path.write_text(f'classdef Test{name}\n    methods (Test)\n        function works(test)\n        end\n    end\nend\n')
        self.candidate = {'Schema': 'csr-tranche-17-candidate-v1', 'Tranche': 17, 'SourceCommit': review.t7.PIN,
            'SourceFilesExcludedPaths': [review.CANDIDATE],
            'TestFiles': ['tests/TestAlpha.m', 'tests/TestBeta.m'],
            'ExpectedTestNames': ['TestAlpha/works', 'TestBeta/works']}
        self.candidate['SourceFiles'] = [dict(path=name, sha256=digest) for name, digest in review.candidate_snapshot(self.root).items()]
        write_json(self.root/review.CANDIDATE, self.candidate)
        self.summary = {'Schema': 'csr-tranche17-portable-tests-summary-v1', 'TestResultsFile': 'results.csv',
            'TestFiles': self.candidate['TestFiles'], 'ExpectedTestNames': self.candidate['ExpectedTestNames'],
            'TestsExecuted': True, 'TestsPassed': True, 'TestCount': 2, 'PassedTests': 2, 'FailedTests': 0, 'IncompleteTests': 0}
        self.rows = [dict(Name=name, Passed=1, Failed=0, Incomplete=0, DurationSeconds=.5)
                     for name in self.candidate['ExpectedTestNames']]

    def check_tests(self):
        write_csv(self.root/'tests/results.csv', self.rows)
        return review.verify_tests(self.root, self.summary, self.root, self.candidate, self.summary)

    def test_full_candidate_and_test_membership(self):
        self.assertEqual(len(review.verify_frozen_candidate(self.root, self.candidate)), 3)
        self.assertEqual(self.check_tests()['count'], 2)

    def test_added_or_changed_source_is_not_the_frozen_candidate(self):
        (self.root/'rogue.m').write_text('function rogue; end')
        with self.assertRaisesRegex(ValueError, 'Candidate source membership'):
            review.verify_frozen_candidate(self.root, self.candidate)
        (self.root/'rogue.m').unlink()
        (self.root/'tests/TestAlpha.m').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'Candidate source membership'):
            review.verify_frozen_candidate(self.root, self.candidate)

    def test_candidate_cannot_omit_a_portable_class_even_with_rebound_sources(self):
        self.candidate['TestFiles'] = self.candidate['TestFiles'][:1]
        self.candidate['ExpectedTestNames'] = self.candidate['ExpectedTestNames'][:1]
        with self.assertRaisesRegex(ValueError, 'every portable'):
            review.verify_frozen_candidate(self.root, self.candidate)

    def test_missing_duplicate_or_native_runtime_test_rejected(self):
        original = copy.deepcopy(self.rows)
        for bad in (original[:1], [original[0], original[0]], [original[0], dict(original[1], Name='TestNative/works')]):
            self.rows = bad
            with self.subTest(rows=bad), self.assertRaisesRegex(ValueError, 'test identity'):
                self.check_tests()

    def test_failed_incomplete_or_falsified_count_rejected(self):
        self.rows[0]['Incomplete'] = 1
        with self.assertRaisesRegex(ValueError, 'failed or incomplete'):
            self.check_tests()
        self.rows[0]['Incomplete'] = 0
        self.summary['PassedTests'] = 1
        with self.assertRaisesRegex(ValueError, 'counters disagree'):
            self.check_tests()


class ReferencesAndReceipts(TemporaryCase):
    def setUp(self):
        super().setUp()
        self.source = {'run.m': 'a'*64}
        self.references = {'ref.json': {'path': 'ref.json', 'sha256': 'b'*64, 'bytes': 8}}
        self.runtime = {'Runtime': 'MATLAB', 'DefaultBackend': 'portable', 'Release': '2025a', 'Version': '25.1'}
        self.metadata = {'CandidateSHA256': 'c'*64, 'CompletedUTC': '2026-09-15T12:00:00Z'}
        self.summary = {'Schema': 'fixture', 'TestsPassed': True}
        self.receipt = {'schema': 'csr-tranche17-stage-receipt-v1', 'phase': 'tests', 'status': 'completed',
            'completed_utc': '2026-09-15T11:00:00Z',
            'identity': {'CandidateSHA256': 'c'*64, 'SourceCommit': review.t7.PIN, 'Runtime': self.runtime,
                'SourceFiles': [{'path': 'run.m', 'sha256': 'a'*64}], 'ReferenceFiles': list(self.references.values())},
            'SourceFilesFinal': [{'path': 'run.m', 'sha256': 'a'*64}], 'ReferenceFilesFinal': list(self.references.values()),
            'SourceFilesStableDuringRun': True, 'ReferenceFilesStableDuringRun': True,
            'summary': self.summary, 'local_artifacts': []}
        write_json(self.root/'tests/summary.json', self.summary)
        write_json(self.root/'tests/start.json', {'schema': 'csr-tranche17-stage-start-v1', 'phase': 'tests',
            'status': 'started', 'started_utc': '2026-09-15T10:00:00Z', 'identity': self.receipt['identity']})
        write_csv(self.root/'tests/results.csv', [{'Name': 'TestA/works', 'Passed': 1}])
        self.freeze()

    def freeze(self):
        self.receipt['artifacts'] = files(self.root/'tests', ('receipt.json', 'receipt.sha256'))
        write_json(self.root/'tests/receipt.json', self.receipt)
        digest = review.sha256(self.root/'tests/receipt.json')
        (self.root/'tests/receipt.sha256').write_text(digest+'\n')
        self.entry = {'Phase': 'tests', 'File': 'tests/receipt.json', 'SHA256': digest}

    def check(self):
        return review.verify_stage(self.root, 'tests', self.entry, self.metadata, self.source, self.references, self.runtime)

    def test_stage_complete_receipt_binds_all_files(self):
        self.assertEqual(self.check(), self.summary)

    def test_stage_file_tampering_missing_and_extra_files_rejected(self):
        path = self.root/'tests/results.csv'
        original = path.read_bytes()
        path.write_bytes(original.replace(b'1', b'0'))
        with self.assertRaisesRegex(ValueError, 'Hash mismatch'):
            self.check()
        path.write_bytes(original)
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing'):
            self.check()
        path.write_bytes(original)
        (self.root/'tests/unlisted.log').write_text('extra')
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            self.check()

    def test_receipt_rewrite_requires_both_hash_bindings(self):
        self.receipt['status'] = 'failed'
        write_json(self.root/'tests/receipt.json', self.receipt)
        with self.assertRaisesRegex(ValueError, 'receipt hash mismatch'):
            self.check()
        self.freeze()
        with self.assertRaisesRegex(ValueError, 'incomplete or wrong phase'):
            self.check()

    def test_null_or_list_stage_identity_fails_explicitly(self):
        for value in (None, []):
            self.receipt['identity'] = value
            self.freeze()
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'identity must be a JSON object'):
                self.check()

    def test_rebound_receipt_cannot_change_candidate_or_stage_source(self):
        self.receipt['identity']['CandidateSHA256'] = 'd'*64
        self.freeze()
        with self.assertRaisesRegex(ValueError, 'candidate/source/runtime'):
            self.check()
        self.receipt['identity']['CandidateSHA256'] = 'c'*64
        self.receipt['SourceFilesFinal'][0]['sha256'] = 'd'*64
        self.freeze()
        with self.assertRaisesRegex(ValueError, 'stability unproven'):
            self.check()

    def test_reference_snapshot_omission_duplicate_and_digest_rejected(self):
        write_json(self.root/'references.json', list(self.references.values()))
        meta = {'ReferenceFilesFinal': list(self.references.values()), 'ReferenceFilesStableDuringRun': True,
                'ReferenceSnapshotSHA256': review.sha256(self.root/'references.json')}
        self.assertEqual(review.verify_references(self.root, meta, self.references)['count'], 1)
        for bad in ([], list(self.references.values())*2, [{'path': 'ref.json', 'sha256': 'f'*64, 'bytes': 8}]):
            write_json(self.root/'references.json', bad)
            meta['ReferenceSnapshotSHA256'] = review.sha256(self.root/'references.json')
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                review.verify_references(self.root, meta, self.references)

    def test_rebound_stage_start_identity_or_timestamps_rejected(self):
        started = review.json_object(self.root/'tests/start.json')
        started['started_utc'] = '2026-09-15T11:00:01Z'
        write_json(self.root/'tests/start.json', started)
        self.freeze()
        with self.assertRaisesRegex(ValueError, 'precedes its start'):
            self.check()
        started['started_utc'] = '2026-09-15T10:00:00Z'
        started['phase'] = 'campus'
        write_json(self.root/'tests/start.json', started)
        self.freeze()
        with self.assertRaisesRegex(ValueError, 'start identity'):
            self.check()


class Accounting(TemporaryCase):
    def setUp(self):
        super().setUp()
        self.config = {'DurationSeconds': 6000, 'Nodes': [{'Id': 1}, {'Id': 2}],
                       'Nwk': {'QueueLimit': 512}, 'Mac': {'DataQueueLimit': 512}}
        self.stats = {'PhysicalTransmissions': 1, 'PhysicalAttempts': 1,
                      'PhysicalReceived': 1, 'PhysicalDropped': 0, 'PhysicalPending': 0}
        self.performance = {'ProtocolTraceRecords': 1, 'PhyTraceRecords': 2}
        self.tx = [{'TimeSeconds': 5999, 'Event': 'tx_start', 'NodeId': 1, 'PacketId': 42}]
        self.phy = [dict(TimeSeconds=5999.01, Event='phy_signal_start', PacketId=42, NodeId=2, SourceId=1, Success=0, Reason=''),
                    dict(TimeSeconds=5999.99, Event='phy_signal_end', PacketId=42, NodeId=2, SourceId=1, Success=1, Reason='decoded')]

    def check_phy(self):
        write_csv(self.root/'raw/protocol_trace.csv', self.tx)
        write_csv(self.root/'raw/phy_trace.csv', self.phy)
        return review.verify_phy(self.root, self.config, self.stats, self.performance)

    def test_real_phy_receiver_accounting_allows_pending_at_original_stop(self):
        self.assertEqual(self.check_phy()['receiver_completions'], 1)
        self.phy.pop()
        self.stats.update(PhysicalReceived=0, PhysicalPending=1)
        self.performance['PhyTraceRecords'] = 1
        self.assertEqual(self.check_phy()['pending_receivers'], 1)

    def test_horizon_duplicate_and_unknown_receiver_fail(self):
        original = copy.deepcopy(self.phy)
        for altered in (dict(original[1], TimeSeconds=6000.01), dict(original[1], NodeId=9), dict(original[1], PacketId=43)):
            self.phy = [original[0], altered]
            with self.subTest(altered=altered), self.assertRaises(ValueError):
                self.check_phy()
        self.phy = original+[original[1]]
        with self.assertRaisesRegex(ValueError, 'Duplicate PHY completion'):
            self.check_phy()

    def test_phy_omission_cannot_be_disguised_by_declared_rowcount(self):
        self.phy.pop()
        self.performance['PhyTraceRecords'] = 1
        with self.assertRaisesRegex(ValueError, 'outcomes disagree'):
            self.check_phy()

    def test_queue_ownership_can_be_pending_but_counts_and_ids_must_match(self):
        mappings = {
            'nodes.csv': {'Id': 1, 'Generated': 2, 'Received': 1, 'Dropped': 0},
            'hop_nodes.csv': {'NodeId': 1, 'PendingData': 1, 'ResendQueueDepth': 1, 'DackHoldCount': 0,
                'ControlPending': 1, 'ControlPendingTargets': 1, 'Retransmissions': 1, 'ControlRetransmissions': 0},
            'nwk_nodes.csv': {'NodeId': 1, 'PendingCustody': 1, 'PendingControlMessages': 1},
            'mac_nodes.csv': {'NodeId': 1, 'Transmissions': 1, 'SegmentsTransmitted': 2, 'AckTransmissions': 1, 'MaxDataQueueDepth': 5}}
        performance = {'Generated': 2, 'Received': 1, 'Dropped': 0, 'HopPendingData': 1, 'ResendQueueDepth': 1,
            'DackHoldCount': 0, 'ControlPending': 1, 'ControlPendingTargets': 1, 'HopDataRetransmissions': 1,
            'HopControlRetransmissions': 0, 'NwkPendingCustody': 1, 'NwkPendingControlMessages': 1,
            'PhysicalTransmissions': 1, 'MacMemberTransmissions': 2, 'AckFeedbackMemberTransmissions': 1}
        for filename, row in mappings.items():
            key = 'Id' if filename == 'nodes.csv' else 'NodeId'
            write_csv(self.root/'raw'/filename, [row, {field: 2 if field == key else 0 for field in row}])
        self.assertEqual(review.verify_node_metrics(self.root, self.config, performance)['nwk_nodes.csv']['PendingCustody'], 1)
        performance['NwkPendingCustody'] = 0
        with self.assertRaisesRegex(ValueError, 'ownership/counter mismatch'):
            review.verify_node_metrics(self.root, self.config, performance)
        performance['NwkPendingCustody'] = 1
        row = mappings['nwk_nodes.csv']
        write_csv(self.root/'raw/nwk_nodes.csv', [row, {field: 1 if field == 'NodeId' else 0 for field in row}])
        with self.assertRaisesRegex(ValueError, 'ownership identity'):
            review.verify_node_metrics(self.root, self.config, performance)

    def test_complete_admission_counters_survive_bounded_prefix(self):
        fixture = t7fixtures.AdmissionChecks(methodName='test_complete_accounting_and_flow_progress')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.trace.pop()
        fixture.stats['OmittedApplicationAdmissionRecords'] = 1
        fixture.save()
        self.assertEqual(fixture.check()['attempts'], 3)
        fixture.counters['Attempts'] = 2
        fixture.save()
        with self.assertRaisesRegex(ValueError, 'partition'):
            fixture.check()

    def test_campus_duplicate_summary_cannot_hide_pending_or_blocked_counts(self):
        performance = {'Pending': '1', 'DataDrained': '0', 'MeanLatencySeconds': 'NaN'}
        admission = dict(attempts=3, admitted=2, blocked=1, trace_records=2, omitted_trace_records=1)
        summary = {'Performance': {'Pending': 1, 'DataDrained': False, 'MeanLatencySeconds': None},
            'Admissions': {'Attempts': 3, 'Admitted': 2, 'Blocked': 1, 'TraceRecords': 2,
                'OmittedTraceRecords': 1, 'CountsComplete': True}}
        review.verify_campus_summary(summary, performance, admission)
        summary['Performance']['Pending'] = 0
        with self.assertRaisesRegex(ValueError, 'numeric disagreement'):
            review.verify_campus_summary(summary, performance, admission)
        summary['Performance']['Pending'] = 1
        summary['Admissions']['Blocked'] = 0
        with self.assertRaisesRegex(ValueError, 'admission counters disagree'):
            review.verify_campus_summary(summary, performance, admission)


class ArchiveAndFailure(TemporaryCase):
    def test_duplicate_and_unsafe_zip_rejected(self):
        for index, names in enumerate((['../escape'], ['item', 'item'], ['A', 'a'])):
            archive = self.root/f'bad{index}.zip'
            with zipfile.ZipFile(archive, 'w') as bundle:
                for name in names:
                    bundle.writestr(name, 'x')
            with self.subTest(names=names), self.assertRaises(ValueError):
                with review.evidence_directory(archive):
                    pass

    def test_partial_return_writes_failed_structured_review(self):
        evidence = self.root/'partial'
        write_json(evidence/'metadata.json', {'Schema': review.SCHEMA, 'Status': 'failed'})
        output = self.root/'output'
        with patch.object(review, 'verify_preparation', side_effect=ValueError('interrupted or incomplete stage')):
            code = review.main(['--evidence', str(evidence), '--source-root', str(self.root/'source'), '--output', str(output)])
        self.assertEqual(code, 1)
        result = json.loads((output/'review.json').read_text())
        self.assertEqual(result['status'], 'review_failed')
        for name in ('evidence_integrity_verified', 'full_structural_gate_completed', 'acceptance_established', 'numerical_parity_established'):
            self.assertIs(result[name], False)

    def test_unsafe_output_failure_does_not_write_into_evidence_or_source(self):
        evidence, source = self.root/'evidence', self.root/'source'
        write_json(evidence/'metadata.json', {'Status': 'failed'})
        write_json(source/'scripts/frozen.json', {'preserved': True})
        before = {str(path): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        for output in (evidence/'review', source/'scripts', source):
            with self.subTest(output=output):
                self.assertEqual(review.main(['--evidence', str(evidence), '--source-root', str(source), '--output', str(output)]), 1)
        after = {str(path): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        self.assertEqual(before, after)

    def test_descendant_output_symlink_cannot_modify_input(self):
        evidence, source, output = self.root/'evidence', self.root/'source', self.root/'output'
        write_json(evidence/'metadata.json', {'Status': 'failed'})
        output.mkdir()
        (output/'review.json').symlink_to(evidence/'metadata.json')
        original = (evidence/'metadata.json').read_bytes()
        self.assertEqual(review.main(['--evidence', str(evidence), '--source-root', str(source), '--output', str(output)]), 1)
        self.assertEqual((evidence/'metadata.json').read_bytes(), original)


class OriginalAggregateInputs(TemporaryCase):
    """Retained real buckets validate descriptive residuals without simulation."""
    def setUp(self):
        super().setUp()
        repository = Path(__file__).resolve().parents[2]
        native = repository/'evidence/tranche-7-ns3-reference/campus_multihop_6000'
        matlab = repository/'evidence/tranche-7-r2025a-accepted/benchmarks/campus_multihop_6000/analysis'
        if not (native/'ns3-aggregates.csv').is_file() or not (matlab/'aggregates.csv').is_file():
            self.skipTest('Preserved campus aggregate fixture not available')
        case = next(row for row in review.json_object(repository/review.CATALOG)['cases'] if row['case_id'] == review.CASE_ID)
        self.manifest = {'schema': review.aggregate.INPUT_SCHEMA,
            **{name: case[name] for name in ('scenario', 'scenario_sha256', 'profile_id', 'duration_s', 'bucket_width_s')},
            'inputs': []}
        for simulator in ('matlab', 'ns3', 'opnet'):
            data = matlab/'aggregates.csv' if simulator == 'matlab' else native/f'{simulator}-aggregates.csv'
            provenance = matlab/'aggregate_provenance.json' if simulator == 'matlab' else native/f'{simulator}-benchmark.provenance.json'
            shutil.copyfile(data, self.root/f'{simulator}.csv')
            shutil.copyfile(provenance, self.root/f'{simulator}.json')
            sidecar = review.json_object(self.root/f'{simulator}.json')
            self.manifest['inputs'].append({'source': simulator, 'aggregate_file': f'{simulator}.csv',
                'aggregate_sha256': review.sha256(self.root/f'{simulator}.csv'), 'provenance_file': f'{simulator}.json',
                'provenance_sha256': review.sha256(self.root/f'{simulator}.json'),
                'excluded_statistics': sidecar.get('excluded_extra_statistics', [])})

    def compare(self):
        write_json(self.root/'input.json', self.manifest)
        return review.aggregate.compare_manifest(self.root/'input.json')

    def test_real_original_campus_residuals_are_descriptive(self):
        result = self.compare()
        self.assertEqual(set(result['inputs']), {'matlab', 'ns3', 'opnet'})
        self.assertEqual((result['bucket_count'], result['bucket_width_s'], result['duration_s']), (100, 60, 6000))
        self.assertTrue(result['structural_gate_passed'])
        self.assertFalse(result['numeric_tolerance_gate_applied'])
        self.assertFalse(result['full_protocol_parity_established'])

    def test_wrong_horizon_and_duplicate_rehashed_bucket_fail(self):
        self.manifest['duration_s'] = 3000
        with self.assertRaises(ValueError):
            self.compare()
        self.manifest['duration_s'] = 6000
        path = self.root/'matlab.csv'
        with path.open() as stream:
            lines = stream.readlines()
        with path.open('a') as stream:
            stream.write(lines[1])
        provenance = review.json_object(self.root/'matlab.json')
        provenance['output']['sha256'] = review.sha256(path)
        write_json(self.root/'matlab.json', provenance)
        self.manifest['inputs'][0].update(aggregate_sha256=review.sha256(path), provenance_sha256=review.sha256(self.root/'matlab.json'))
        with self.assertRaisesRegex(ValueError, 'duplicate series/bucket'):
            self.compare()


if __name__ == '__main__':
    unittest.main()
