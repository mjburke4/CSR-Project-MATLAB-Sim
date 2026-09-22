"""Receipt, source, metadata and plan mutation tests. No MATLAB execution."""
import copy
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze_tranche25_return as r
from test_tranche25_metrics import run


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n')


def inventory(directory, excluded=()):
    return [{'path': path.relative_to(directory).as_posix(), 'sha256': r.sha256(path), 'bytes': path.stat().st_size}
            for path in sorted(directory.rglob('*')) if path.is_file() and path.relative_to(directory).as_posix() not in excluded]


class ReturnContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.source = self.root/'source'; self.source.mkdir()
        path = self.source/'scenarios/campus.csv'; path.parent.mkdir(); path.write_text('original\n')
        self.case = {'seed': 131, 'policy': 'actual-tx', 'scenario_file': 'scenarios/campus.csv', 'scenario_sha256': r.sha256(path)}
        self.base = {'Seed': 128, 'Hop': {'DataQueuedRetryPolicy': 'actual-tx', 'Capacity': 10},
                     'SharedScenario': {'SourcePath': str(path), 'SourceSHA256': r.sha256(path)}}
        self.actual = copy.deepcopy(self.base); self.actual['Seed'] = 131
    def tearDown(self): self.temp.cleanup()

    def test_seed_only_configuration_accepted(self):
        self.assertEqual(r.verify_configuration(self.actual, self.base, self.case, self.source)['seed_override'], {'before': 128, 'after': 131})
    def test_retry_policy_change_rejected(self):
        self.actual['Hop']['DataQueuedRetryPolicy'] = 'native-provisional'
        with self.assertRaisesRegex(ValueError, 'policy'): r.verify_configuration(self.actual, self.base, self.case, self.source)
    def test_capacity_change_rejected(self):
        self.actual['Hop']['Capacity'] += 1
        with self.assertRaises(ValueError): r.verify_configuration(self.actual, self.base, self.case, self.source)
    def test_wrong_seed_rejected(self):
        self.actual['Seed'] = 132
        with self.assertRaisesRegex(ValueError, 'seed'): r.verify_configuration(self.actual, self.base, self.case, self.source)
    def test_modified_scenario_rejected(self):
        (self.source/'scenarios/campus.csv').write_text('modified\n')
        with self.assertRaises(ValueError): r.verify_configuration(self.actual, self.base, self.case, self.source)
    def test_failed_or_partial_run_rejected_before_data_reads(self):
        for status in ('failed', 'phase-completed-review-pending'):
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, 'not finalized'):
                r.verify_identity(self.root, {'Schema': r.SCHEMA, 'Tranche': 25, 'Status': status}, self.source, {})
    def test_artifact_byte_mutation_rejected(self):
        path = self.root/'one.txt'; path.write_text('before'); rows = inventory(self.root)
        path.write_text('after!')
        with self.assertRaisesRegex(ValueError, 'hash/size'): r.inventory(self.root, rows, 'test')
    def test_unlisted_artifact_rejected(self):
        path = self.root/'one.txt'; path.write_text('one'); rows = inventory(self.root)
        (self.root/'two.txt').write_text('two')
        with self.assertRaisesRegex(ValueError, 'Incomplete'): r.inventory(self.root, rows, 'test')
    def test_omitted_nonlocal_artifact_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Invalid omitted'):
            r.inventory(self.root, [], 'test', local=[{'path': 'trace.csv', 'bytes': 1, 'sha256': '0'*64}])
    def test_rowcount_mutation_rejected(self):
        directory = self.root/'data'; directory.mkdir(); path = directory/'x.csv'; path.write_text('a\n1\n')
        rows = inventory(directory); rows[0]['row_count'] = 2
        with self.assertRaisesRegex(ValueError, 'row count'): r.inventory(directory, rows, 'test')
    def test_bound_delay_mismatch_rejected(self):
        expected = run(); actual = run(delay=11)
        with self.assertRaisesRegex(ValueError, 'conditional delay'): r._equal_normalized(actual, expected, 'reused')
    def test_bound_count_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, 'count differs'): r._equal_normalized(run(admitted=101), run(), 'reused')
    def test_roundoff_from_different_summation_order_allowed(self):
        actual = run(); expected = run(); actual['totals']['delivered_delay_sum_s'] += 1e-10
        r._equal_normalized(actual, expected, 'reused')

    def stage(self):
        phase = 's131'; directory = self.root/phase; directory.mkdir()
        identity = {'CandidateSHA256': 'a'*64, 'SourceCommit': r.multi.PIN,
                    'Runtime': {'Runtime': 'MATLAB', 'Release': '2025a'},
                    'SourceFiles': [{'path': 'model.m', 'sha256': 'b'*64}],
                    'ReferenceFiles': [{'path': 'reference.json', 'sha256': 'c'*64, 'bytes': 10}]}
        summary = {'Schema': 'synthetic-contract-only'}; write(directory/'summary.json', summary)
        start = {'schema': 'csr-tranche25-stage-start-v1', 'phase': phase, 'status': 'started',
                 'identity': identity, 'started_utc': '2026-09-19T00:00:00Z'}
        write(directory/'start.json', start)
        receipt = {'schema': 'csr-tranche25-stage-receipt-v1', 'phase': phase, 'status': 'completed',
            'identity': identity, 'completed_utc': '2026-09-19T00:01:00Z',
            'SourceFilesStableDuringRun': True, 'ReferenceFilesStableDuringRun': True,
            'SourceFilesFinal': identity['SourceFiles'], 'ReferenceFilesFinal': identity['ReferenceFiles'],
            'summary': summary, 'artifacts': inventory(directory), 'local_artifacts': []}
        def seal(value):
            write(directory/'receipt.json', value); digest = r.sha256(directory/'receipt.json')
            (directory/'receipt.sha256').write_text(digest+'\n')
            return {'Phase': phase, 'File': phase+'/receipt.json', 'SHA256': digest}
        entry = seal(receipt)
        meta = {'CandidateSHA256': identity['CandidateSHA256'], 'CompletedUTC': '2026-09-19T00:02:00Z'}
        args = (self.root, phase, entry, meta, {'model.m': 'b'*64},
                {'reference.json': {'path': 'reference.json', 'sha256': 'c'*64, 'bytes': 10}}, identity['Runtime'])
        # record_map preserves just sha256/bytes and path? Derive through canonical helper.
        args = (*args[:5], r.record_map(identity['ReferenceFiles'], 'reference', sizes=True), args[-1])
        return directory, receipt, seal, args
    def test_valid_completed_stage_receipt(self):
        directory, receipt, seal, args = self.stage(); self.assertEqual(r.verify_stage(*args), receipt['summary'])
    def test_same_candidate_different_runtime_cannot_reuse_stage(self):
        directory, receipt, seal, args = self.stage(); args = (*args[:-1], {'Runtime': 'MATLAB', 'Release': '2026a'})
        with self.assertRaisesRegex(ValueError, 'runtime'): r.verify_stage(*args)
    def test_changed_final_source_rejected_even_resealed(self):
        directory, receipt, seal, args = self.stage(); receipt['SourceFilesFinal'] = [{'path': 'model.m', 'sha256': 'd'*64}]
        args = (*args[:2], seal(receipt), *args[3:])
        with self.assertRaisesRegex(ValueError, 'stability'): r.verify_stage(*args)
    def test_completion_before_start_rejected_even_resealed(self):
        directory, receipt, seal, args = self.stage(); receipt['completed_utc'] = '2026-09-18T23:00:00Z'
        args = (*args[:2], seal(receipt), *args[3:])
        with self.assertRaisesRegex(ValueError, 'timing'): r.verify_stage(*args)
    def test_start_candidate_mutation_rejected_even_reinventoried(self):
        directory, receipt, seal, args = self.stage(); start = r.json_object(directory/'start.json')
        start['identity']['CandidateSHA256'] = 'd'*64; write(directory/'start.json', start)
        receipt['artifacts'] = inventory(directory, ('receipt.json', 'receipt.sha256'))
        args = (*args[:2], seal(receipt), *args[3:])
        with self.assertRaisesRegex(ValueError, 'start identity'): r.verify_stage(*args)
    def test_stage_summary_rewrite_rejected(self):
        directory, receipt, seal, args = self.stage(); write(directory/'summary.json', {'Schema': 'changed'})
        receipt['artifacts'] = inventory(directory, ('receipt.json', 'receipt.sha256'))
        args = (*args[:2], seal(receipt), *args[3:])
        with self.assertRaisesRegex(ValueError, 'summary'): r.verify_stage(*args)

    def test_portable_test_discovery_excludes_setup_private_and_postclass_helpers(self):
        path = self.source/'tests/TestSample.m'; path.parent.mkdir()
        path.write_text('''classdef TestSample < matlab.unittest.TestCase
    methods (TestClassSetup)
        function setUp(test)
        end
    end
    methods (Test)
        function actual(test)
        end
    end
end
function helper()
        function nestedHelper()
        end
end
''')
        self.assertEqual(r.selected_test_names(self.source, ['tests/TestSample.m']), ['TestSample/actual'])


if __name__ == '__main__': unittest.main()
