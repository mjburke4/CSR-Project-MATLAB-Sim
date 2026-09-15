"""Synthetic return tampering and accounting checks; no MATLAB run implied."""
from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze_tranche7_return as review


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value)+"\n", encoding="utf-8")


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def files(root, exclude=()):
    return [dict(path=p.relative_to(root).as_posix(), sha256=review.sweep.digest(p), bytes=p.stat().st_size)
            for p in sorted(root.rglob("*")) if p.is_file() and p.relative_to(root).as_posix() not in exclude]


class ReturnPrimitives(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_fractional_and_unsafe_rounded_counts_rejected(self):
        for value in (True, 1.25, "3.0", "1e2", float(2**53), -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                review.integer(value, "count")
        self.assertEqual(review.integer("9007199254740993", "count"), 9007199254740993)
        self.assertEqual(review.integer(380.0, "count"), 380)

    def test_stop_exclusive_counts_use_nanosecond_arithmetic(self):
        self.assertEqual(review.possible_attempts(.4, .1, .1, 99), 3)
        self.assertEqual(review.possible_attempts(6000, 300, .02, 999999), 285000)
        self.assertEqual(review.possible_attempts(3, 3, 1, 5), 0)
        self.assertEqual(review.possible_attempts(3, 0, 1, 2), 2)

    def test_duplicate_case_colliding_and_traversal_zip_paths_rejected(self):
        for index, paths in enumerate((['../outside'], ['a/../../outside'], ['C:/outside'],
                                       ['a\\outside'], ['item', 'item'], ['A', 'a'])):
            archive = self.root / f"bad{index}.zip"
            with zipfile.ZipFile(archive, 'w') as bundle:
                for path in paths:
                    bundle.writestr(path, 'x')
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                with review.evidence_directory(archive):
                    pass
        self.assertFalse((self.root.parent / 'outside').exists())

    def test_zip_symlink_rejected_and_valid_zip_unchanged(self):
        archive = self.root / 'link.zip'
        with zipfile.ZipFile(archive, 'w') as bundle:
            member = zipfile.ZipInfo('link')
            member.create_system = 3
            member.external_attr = (stat.S_IFLNK | 0o777) << 16
            bundle.writestr(member, '/tmp/elsewhere')
        with self.assertRaises(ValueError):
            with review.evidence_directory(archive):
                pass
        valid = self.root / 'valid.zip'
        with zipfile.ZipFile(valid, 'w') as bundle:
            bundle.writestr('validation_metadata.json', '{}')
        digest = review.sweep.digest(valid)
        with review.evidence_directory(valid) as directory:
            self.assertEqual((directory / 'validation_metadata.json').read_text(), '{}')
        self.assertEqual(review.sweep.digest(valid), digest)

    def test_inventory_tampering_missing_and_extra_rows_fail(self):
        raw = self.root / 'data'
        write_csv(raw / 'a.csv', [{'x': 1}])
        expected = files(raw)
        expected[0]['row_count'] = 1
        review.inventory(raw, expected, 'fixture')
        wrong = copy.deepcopy(expected)
        wrong[0]['row_count'] = 2
        with self.assertRaisesRegex(ValueError, 'Row count'):
            review.inventory(raw, wrong, 'fixture')
        (raw / 'extra.log').write_text('x')
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            review.inventory(raw, expected, 'fixture')
        (raw / 'extra.log').unlink()
        write_csv(raw / 'a.csv', [{'x': 2}])
        with self.assertRaisesRegex(ValueError, 'Hash mismatch'):
            review.inventory(raw, expected, 'fixture')

    def test_live_t4_log_excluded_only_when_outer_inventory_binds_it(self):
        raw = self.root / 't4'
        write_json(raw / 'case.json', {'a': 1})
        expected = files(raw)
        (raw / 'validation.log').write_text('closed by outer wrapper')
        review.inventory(raw, expected, 'T4', excluded=('validation.log',))
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            review.inventory(raw, expected, 'outer')
        review.inventory(raw, files(raw), 'outer')

    def test_source_snapshot_detects_added_and_modified_source_files(self):
        (self.root / 'run.m').write_text('function run; end')
        first = review.candidate_snapshot(self.root)
        (self.root / 'extra.m').write_text('function extra; end')
        second = review.candidate_snapshot(self.root)
        self.assertNotEqual(first, second)
        (self.root / 'run.m').write_text('function changed; end')
        self.assertNotEqual(second, review.candidate_snapshot(self.root))

    def test_test_membership_excludes_setup_private_and_native_methods(self):
        path = self.root / 'tests/TestTiny.m'
        path.parent.mkdir()
        path.write_text('classdef TestTiny\n    methods (TestClassSetup)\n        function setup(test)\n        end\n    end\n'
                        '    methods (Test)\n        function works(test)\n        end\n    end\n'
                        '    methods (Static, Access=private)\n        function helper()\n        end\n    end\nend\n')
        native = path.parent / 'native/TestNative.m'
        native.parent.mkdir()
        native.write_text(path.read_text().replace('TestTiny', 'TestNative'))
        self.assertEqual(review.portable_test_names(self.root), {'TestTiny/works'})
        self.assertEqual(review.portable_test_names(self.root, native=True), {'TestNative/works'})


class AdmissionChecks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = {'DurationSeconds': 3, 'ApplicationFlowLimit': 0,
                       'Benchmark': {'BucketWidthSeconds': 1},
                       'Traffic': {'SourceId': 1, 'DestinationId': 2, 'StartSeconds': 0,
                                   'IntervalSeconds': 1, 'PacketCount': 3, 'ApplicationPayloadBytes': 185,
                                   'Dscp': 0, 'DestinationMode': 'fixed'}}
        self.stats = {'Generated': 2, 'Received': 1, 'Dropped': 1, 'Pending': 0,
                      'ApplicationBytesReceived': 185, 'OmittedApplicationAdmissionRecords': 0}
        self.counters = {'FlowIndex': 1, 'SourceId': 1, 'ConfiguredDestinationId': 2,
                         'Attempts': 3, 'Admitted': 2, **dict.fromkeys(review.GATES.values(), 0)}
        self.counters['BlockedNsdp'] = 1
        self.protocol = [self.event(0, 'app_generate', 1), self.event(.5, 'app_receive', 1, 2, 1),
                         self.event(2, 'app_generate', 2), self.event(2.2, 'app_drop', 2, reason='retry_exhausted')]
        self.trace = [{'TimeSeconds': n, 'FlowIndex': 1, 'AttemptIndex': n+1, 'SourceId': 1,
                       'DestinationId': 2, 'PacketId': packet, 'Accepted': int(packet > 0),
                       'Reason': 'admitted' if packet else 'nsdp_full'} for n, packet in enumerate([1, 0, 2])]
        self.apps = [{'PacketId': 1, 'SourceId': 1, 'DestinationId': 2, 'ApplicationBytes': 185, 'Dscp': 0,
                      'GeneratedSeconds': 0, 'LastEventSeconds': .5, 'ReceivedSeconds': .5,
                      'LatencySeconds': .5, 'Outcome': 'delivered', 'DropReason': ''},
                     {'PacketId': 2, 'SourceId': 1, 'DestinationId': 2, 'ApplicationBytes': 185, 'Dscp': 0,
                      'GeneratedSeconds': 2, 'LastEventSeconds': 2.2, 'ReceivedSeconds': 'NaN',
                      'LatencySeconds': 'NaN', 'Outcome': 'dropped', 'DropReason': 'retry_exhausted'}]
        values = [[1, 0, 1], [1536, 0, 1536], [1536, None, 1536], [1, 0, 0], [1, 0, 0],
                  [1536, 0, 0], [1536, 0, 0], [.5, None, None]]
        self.aggregates = [{'statistic': name, 'time_s': index+1, 'value': '' if value is None else value,
                            'value_status': 'missing' if value is None else 'observed'}
                           for name, values in zip(review.compare.CORE_SERIES, values) for index, value in enumerate(values)]
        self.save()

    @staticmethod
    def event(time, event, packet, node=1, peer=2, reason=''):
        return {'TimeSeconds': time, 'Event': event, 'PacketId': packet, 'NodeId': node,
                'PeerId': peer, 'ApplicationBytes': 185, 'Dscp': 0, 'Reason': reason}

    def save(self):
        write_csv(self.root / 'raw/application_admission_statistics.csv', [self.counters])
        write_csv(self.root / 'raw/application_admission_trace.csv', self.trace)
        write_csv(self.root / 'raw/protocol_trace.csv', self.protocol)
        write_csv(self.root / 'analysis/applications.csv', self.apps)
        write_csv(self.root / 'analysis/aggregates.csv', self.aggregates)

    def check(self):
        return review.verify_admission(self.root, self.config, self.stats)

    def test_complete_accounting_and_flow_progress(self):
        result = self.check()
        self.assertEqual((result['attempts'], result['admitted'], result['blocked']), (3, 2, 1))
        self.assertEqual(result['flows'][0]['delivered'], 1)
        self.assertTrue(result['all_flows_made_progress'])

    def test_bounded_prefix_retains_full_admitted_identity_check(self):
        self.trace.pop()
        self.stats['OmittedApplicationAdmissionRecords'] = 1
        self.save()
        self.assertEqual(self.check()['omitted_trace_records'], 1)
        self.protocol[2]['TimeSeconds'] = 2.1
        self.apps[1]['GeneratedSeconds'] = 2.1
        self.save()
        with self.assertRaisesRegex(ValueError, 'scheduled flow attempt'):
            self.check()

    def test_admission_prefix_time_must_match_schedule(self):
        self.trace[1]['TimeSeconds'] = 1.1
        self.save()
        with self.assertRaisesRegex(ValueError, 'canonical schedule'):
            self.check()

    def test_counter_fraction_partition_and_omission_tampering_fail(self):
        original = copy.deepcopy(self.counters)
        for field, value in [('Attempts', '3.5'), ('Admitted', 3), ('BlockedNsdp', 2)]:
            self.counters = dict(original, **{field: value})
            self.save()
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check()
        self.counters = original
        self.stats['OmittedApplicationAdmissionRecords'] = 1
        self.save()
        with self.assertRaisesRegex(ValueError, 'coverage'):
            self.check()

    def test_blocked_attempt_cannot_own_a_packet(self):
        self.trace[1]['PacketId'] = 9
        self.save()
        with self.assertRaisesRegex(ValueError, 'Blocked attempt'):
            self.check()

    def test_rehashed_aggregate_values_and_missing_buckets_fail(self):
        self.aggregates[0]['value'] = 2
        self.save()
        with self.assertRaisesRegex(ValueError, 'aggregate bucket disagrees'):
            self.check()
        self.aggregates[0]['value'] = 1
        self.aggregates.pop()
        self.save()
        with self.assertRaisesRegex(ValueError, 'grid is incomplete'):
            self.check()

    def test_missing_sample_mean_cannot_be_silently_zero(self):
        self.aggregates[7]['value'] = 0
        self.aggregates[7]['value_status'] = 'observed'
        self.save()
        with self.assertRaisesRegex(ValueError, 'remain missing'):
            self.check()

    def test_outcome_and_latency_diagnostics_must_match_trace(self):
        self.apps[0]['LatencySeconds'] = .4
        self.save()
        with self.assertRaisesRegex(ValueError, 'latency mismatch'):
            self.check()

    def test_payload_change_beyond_prefix_is_rejected(self):
        self.trace.pop()
        self.stats['OmittedApplicationAdmissionRecords'] = 1
        for row in self.protocol[2:]:
            row['ApplicationBytes'] = 186
        self.apps[1]['ApplicationBytes'] = 186
        self.save()
        with self.assertRaisesRegex(ValueError, 'payload/DSCP'):
            self.check()


class OuterMembershipChecks(unittest.TestCase):
    """Isolate outer membership from independently tested raw/reference validators."""
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'source'
        self.evidence = self.root / 'evidence'
        self.source.mkdir()
        self.evidence.mkdir()
        (self.source / 'run.m').write_text('function run; end')
        cases = [dict(case_id=f'case{index}', scenario=f'fixture{index}', scenario_file=f'scenarios/benchmarks/case{index}.csv',
                      scenario_sha256='a'*64, profile_id='hist-adb97c54-bare', duration_s=3, seed=128, bucket_width_s=1,
                      default=True, flow_limit=0, reference_directory=f'evidence/tranche-7-ns3-reference/case{index}',
                      source_kind='synthetic_diagnostic', opnet_available=False) for index in range(3)]
        catalog_path = self.source / 'scenarios/benchmarks/catalog.json'
        write_json(catalog_path, dict(schema='csr-benchmark-catalog-v1', ns3_source_commit=review.PIN, cases=cases))
        for tree in ('tranche-7-ns3-reference', 'tranche-7-benchmark-inputs'):
            write_json(self.source / 'evidence' / tree / 'manifest.json', {})
        (self.evidence / 'benchmark_catalog.json').write_bytes(catalog_path.read_bytes())
        snapshot = [dict(path=name, sha256=digest) for name, digest in review.candidate_snapshot(self.source).items()]
        write_json(self.evidence / 'source_snapshot.json', snapshot)
        catalog_hash = review.sweep.digest(catalog_path)
        fields = {'Scenario': 'scenario', 'ScenarioFile': 'scenario_file', 'ScenarioSHA256': 'scenario_sha256',
                  'ProfileId': 'profile_id', 'DurationSeconds': 'duration_s', 'Seed': 'seed',
                  'BucketWidthSeconds': 'bucket_width_s', 'ReferenceDirectory': 'reference_directory'}
        write_json(self.evidence / 'benchmark_plan.json', {'Schema': 'csr-matlab-benchmark-plan-v1',
                   'SourceCommit': review.PIN, 'CatalogSHA256': catalog_hash, 'CaseCount': 3,
                   'Cases': [dict(CaseId=item['case_id'], **{k: item[v] for k, v in fields.items()}) for item in cases]})
        self.metadata = {'Schema': review.SCHEMA, 'Tranche': 7, 'Status': 'completed', 'MATLABExecuted': True,
                         'SourceCommit': review.PIN, 'MatlabBaseCommit': review.BASE, 'ValidatedTranche6CodeCommit': review.T6_CODE,
                         'Runtime': {'Runtime': 'MATLAB', 'Version': 'fixture-R2025a', 'Release': '2025a'},
                         'SourceFiles': snapshot, 'SourceFilesFinal': snapshot, 'SourceFilesStableDuringRun': True,
                         'SourceSnapshotSHA256': review.sweep.digest(self.evidence / 'source_snapshot.json'),
                         'CatalogSHA256': catalog_hash, 'Options': {'RunTests': False, 'IncludeNative': False, 'Cases': []},
                         'TestsRequested': False, 'NativeRequested': False, 'TestsExecuted': False, 'TestsPassed': False,
                         'NativeExecuted': False, **dict.fromkeys(review.TEST_COUNTS, 0), 'RegressionStatus': 'not_run',
                         'RegressionEvidenceDirectory': '', 'RegressionMetadataSHA256': '', 'BenchmarkPlan': 'benchmark_plan.json',
                         'CompletedCaseCount': 3, 'PlannedCaseCount': 3, 'Cases': [], 'ReferenceFilesStableDuringRun': True}
        reference = [dict(row, path='evidence/'+row['path']) for row in files(self.source / 'evidence')]
        self.metadata['ReferenceFiles'] = reference
        self.metadata['ReferenceFilesFinal'] = copy.deepcopy(reference)
        for item in cases:
            path = self.evidence / 'benchmarks' / item['case_id'] / 'benchmark_manifest.json'
            write_json(path, {'fixture': True})
            self.metadata['Cases'].append(dict(CaseId=item['case_id'], Directory=f"benchmarks/{item['case_id']}",
                                              ManifestSHA256=review.sweep.digest(path)))
        write_csv(self.evidence / 'benchmark_summary.csv', [dict(CaseId=x['case_id'], Generated=0, Received=0,
                  Dropped=0, Pending=0, Attempts=3, AdmissionBlocked=3) for x in cases])
        self.save()
        self.patches = [patch.object(review, 'verify_reference_suite'), patch.object(review, 'reference_flow_progress', return_value=[]),
                        patch.object(review, 'verify_case', side_effect=self.observation)]
        for context in self.patches:
            context.start()
            self.addCleanup(context.stop)

    @staticmethod
    def observation(root, item, *_):
        return {'case_id': item['CaseId'], 'counts': dict.fromkeys(review.COUNTS, 0),
                'admission': {'attempts': 3, 'admitted': 0, 'blocked': 3, 'flows': [], 'all_flows_made_progress': False}}

    def save(self):
        self.metadata['Artifacts'] = files(self.evidence, ('validation_metadata.json',))
        write_json(self.evidence / 'validation_metadata.json', self.metadata)

    def check(self):
        return review.verify_return(self.evidence, self.source)[0]

    def test_run_tests_false_is_diagnostic_even_with_all_cases(self):
        report = self.check()
        self.assertTrue(report['diagnostic_only'])
        self.assertFalse(report['default_structural_gate_completed'])
        self.assertFalse(report['all_flows_made_progress'])
        self.assertFalse(report['acceptance_established'])

    def test_missing_default_case_cannot_pass_as_complete(self):
        self.metadata['Cases'].pop()
        self.save()
        with self.assertRaisesRegex(ValueError, 'Missing/duplicated'):
            self.check()

    def test_duplicate_case_and_fractional_count_rejected(self):
        self.metadata['Cases'][1] = self.metadata['Cases'][0]
        self.save()
        with self.assertRaisesRegex(ValueError, 'Missing/duplicated'):
            self.check()

    def test_source_change_and_false_requested_test_claim_rejected(self):
        self.metadata['Options']['RunTests'] = True
        self.metadata['TestsRequested'] = True
        self.save()
        with self.assertRaisesRegex(ValueError, 'regression incomplete'):
            self.check()
        (self.source / 'run.m').write_text('function changed; end')
        with self.assertRaisesRegex(ValueError, 'Source snapshot mismatch'):
            self.check()

    def test_reference_start_final_disagreement_rejected(self):
        self.metadata['ReferenceFilesFinal'][0]['sha256'] = 'f'*64
        self.save()
        with self.assertRaisesRegex(ValueError, 'Reference snapshots changed'):
            self.check()


if __name__ == '__main__':
    unittest.main()
