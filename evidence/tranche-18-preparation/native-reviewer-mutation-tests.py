#!/usr/bin/env python3
"""Bounded independent T18 reviewer mutations; no MATLAB/native suite execution.

Usage: python -B reviewer-tests.py [--target path/to/run_tranche18_ns3_reference.py]
Comparison/projection tests use real temporary bytes. Stage tests execute the
real suite-review entrypoint with unrelated integrity/data gates isolated by
mocks. DACK classification compiles the exact helper expression with a tiny
header stub, exercising native ACK+DACK flag combinations.
"""
from __future__ import annotations

import argparse
import copy
import csv
from contextlib import ExitStack
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
DEFAULT_TARGET = Path(__file__).resolve().parents[2] / 'scripts/run_tranche18_ns3_reference.py'
parser = argparse.ArgumentParser()
parser.add_argument('--target', type=Path, default=DEFAULT_TARGET)
arguments, remaining = parser.parse_known_args()
target = arguments.target.resolve()
spec = importlib.util.spec_from_file_location('t18_independent_review_target', target)
review = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = review
spec.loader.exec_module(review)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_csv_gz(path, rows, fields):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)
    path.write_bytes(gzip.compress(stream.getvalue().encode(), mtime=0))


class TemporaryCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='t18-reviewer-')
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)


class Comparisons(TemporaryCase):
    def setUp(self):
        super().setUp()
        self.originals = {}
        for name in ('ns3-trace.csv', 'app-admission-diagnostics.csv', 'ns3-aggregates.csv'):
            data = ('fixture:' + name + '\n').encode()
            for prefix in ('', 'off-', 'pristine-'):
                path = self.home / (prefix + name)
                path.write_bytes(data)
                if name == 'ns3-trace.csv':
                    self.originals[path.name] = digest(data)
        self.record = {
            'nonperturbation': review.compare_files(self.home, '', 'off-', ['ns3-trace.csv', 'app-admission-diagnostics.csv']),
            'aggregate_nonperturbation': review.compare_files(self.home, '', 'off-', ['ns3-aggregates.csv']),
        }

    def check(self, key='r128'):
        return review.verify_comparisons(self.home, self.record, self.originals, key)

    def test_valid_exact_pairs_pass(self):
        self.check()

    def test_empty_comparison_lists_fail(self):
        for label in tuple(self.record):
            original = copy.deepcopy(self.record[label])
            self.record[label]['compared_files'] = []
            with self.subTest(label=label), self.assertRaises(ValueError):
                self.check()
            self.record[label] = original

    def test_wrong_or_duplicated_members_fail(self):
        original = copy.deepcopy(self.record['nonperturbation'])
        for mutation in ('wrong', 'duplicate', 'missing'):
            self.record['nonperturbation'] = copy.deepcopy(original)
            rows = self.record['nonperturbation']['compared_files']
            if mutation == 'wrong':
                rows[0]['name'] = 'other.csv'
            elif mutation == 'duplicate':
                rows[1] = copy.deepcopy(rows[0])
            else:
                rows.pop()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.check()

    def test_self_comparison_cannot_replace_on_off(self):
        row = self.record['nonperturbation']['compared_files'][0]
        row['second_path'] = row['first_path']
        with self.assertRaises(ValueError):
            self.check()

    def test_rebound_control_hash_does_not_hide_wrong_bytes(self):
        row = self.record['nonperturbation']['compared_files'][1]
        (self.home / row['second_path']).write_text('different\n')
        with self.assertRaises(ValueError):
            self.check()

    def test_missing_pristine_control_fails_for_mixed_seed128(self):
        with self.assertRaises((ValueError, KeyError)):
            self.check('m128')

    def test_pristine_membership_is_exact(self):
        self.record['pristine_nonperturbation'] = review.compare_files(
            self.home, 'off-', 'pristine-', ['ns3-trace.csv', 'app-admission-diagnostics.csv'])
        self.check('m128')
        with self.assertRaises(ValueError):
            self.check('r128')


RAW_FIELDS = ('schema,event_index,time_s,event,node,peer,packet_type,src,dst,'
              'sequence,rate_kbps,size_bytes,success,reason,pathloss_db,rx_power_dbm,'
              'noise_dbm,snr_db,jsr_db,header_errors,payload_errors,total_errors,'
              'route_cost,next_hop,security_count,reservation_slot,reservation_counter,'
              'detail,statistic,value').split(',')


class Projection(TemporaryCase):
    def setUp(self):
        super().setUp()
        self.case = {'duration_s': 600}
        self.raw = []
        for index, (event, node, peer, next_hop, reason) in enumerate([
                ('app_send', '4', '1', '', ''),
                ('nwk_enqueue', '5', '4', '', 'relay'),
                ('nwk_forward', '5', '4', '1', 'relay')]):
            row = dict.fromkeys(RAW_FIELDS, '')
            row.update(schema='csr-differential-trace-v1', event_index=str(index),
                       time_s=str(300 + index), event=event, node=node, peer=peer,
                       packet_type='data', src='4', dst='1', sequence='42',
                       next_hop=next_hop, route_cost='7450' if next_hop else '',
                       reason=reason, success='1')
            self.raw.append(row)
        self.observed = []
        for row in self.raw:
            observation = dict.fromkeys(review.SERVICE_FIELDS, '')
            observation.update({key: value for key, value in row.items() if key in observation})
            observation.update(schema=review.SERVICE_SCHEMA, event_index=str(len(self.observed) + 1))
            self.observed.append(observation)
        extra = dict.fromkeys(review.SERVICE_FIELDS, '')
        extra.update(schema=review.SERVICE_SCHEMA, event_index='4', time_s='302', event='mac_slot_tick', node='5')
        self.observed.append(extra)

    def check(self, raw_fields=RAW_FIELDS):
        write_csv_gz(self.home / 'ns3-trace.csv.gz', self.raw, raw_fields)
        write_csv_gz(self.home / 'ns3-service.csv.gz', self.observed, review.SERVICE_FIELDS)
        return review.verify_service_projection(self.home, self.case)

    def test_complete_projection_with_side_events_passes(self):
        self.assertEqual(self.check()['canonical_rows'], 3)

    def test_invented_egress_or_ingress_fails(self):
        for field in ('next_hop', 'peer', 'route_cost', 'sequence', 'src', 'dst'):
            old = self.observed[2][field]
            self.observed[2][field] = '999'
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check()
            self.observed[2][field] = old

    def test_missing_canonical_observation_fails(self):
        self.observed.pop(1)
        with self.assertRaises(ValueError):
            self.check()

    def test_missing_last_canonical_observation_fails(self):
        self.observed.pop(2)
        with self.assertRaises(ValueError):
            self.check()

    def test_excess_canonical_observation_fails(self):
        self.observed.append(copy.deepcopy(self.observed[2]))
        with self.assertRaises(ValueError):
            self.check()

    def test_raw_index_gap_fails(self):
        self.raw[1]['event_index'] = '99'
        with self.assertRaises(ValueError):
            self.check()

    def test_missing_egress_column_must_not_make_projection_vacuous(self):
        # The imported reviewer advertises next_hop preservation. Dropping that
        # column from canonical evidence must not permit an invented egress.
        self.observed[2]['next_hop'] = '999'
        with self.assertRaises(ValueError):
            self.check([field for field in RAW_FIELDS if field != 'next_hop'])


class StageGate(TemporaryCase):
    """Exercise actual suite-stage gate; isolate unrelated heavyweight gates."""
    def setUp(self):
        super().setUp()
        self.key = 'r128'
        self.hash = 'a' * 64
        self.case = {'storage_key': self.key, 'duration_s': 600,
                     'condition': 'relay_only', 'expected_admission_attempts': 1}
        self.suite = dict(schema=review.SUITE_SCHEMA, status='completed',
            ns3_source_commit=review.BASE.PIN, engine_commit=review.ENGINE_PIN,
            plan_sha256=self.hash, all_observer_on_off_checks_passed=True,
            source_files_stable=True, input_files_stable=True,
            binary_and_overlay_files_stable=True, matlab_executed=False,
            opnet_executed=False, files=[], build_manifest_sha256=self.hash,
            cases=[{'storage_key': self.key, 'manifest_sha256': self.hash}])
        self.build = dict(schema='csr-tranche18-native-build-v1',
            ns3_source_commit=review.BASE.PIN, engine_commit=review.ENGINE_PIN,
            full_ns3_rebuild_performed=True, source_headers_match_build=True,
            standalone_runner_compiled=True, compiles={name: {'exit_code': 0} for name in ('observer', 'pristine')},
            environment_receipt_sha256=self.hash, helper_sha256=self.hash, runner_sha256=self.hash)
        self.environment = dict(status='completed', source_commit=review.BASE.PIN,
            engine_commit=review.ENGINE_PIN, source_tracked_clean=True,
            engine_tracked_clean=True, build_exit_code=0, full_engine_and_csr_rebuild_performed=True,
            libraries={f'libns3-dev-{name}-debug.so': self.hash for name in review.BASE.MODULES})
        self.record = dict(schema=review.CASE_SCHEMA, status='completed', case=self.case,
            ns3_source_commit=review.BASE.PIN, engine_commit=review.ENGINE_PIN,
            runner_sha256=self.hash, matlab_executed=False, opnet_executed=False,
            files=[], compressed_artifacts=[], control_compressed_artifacts=[],
            stages={name: {'exit_code': 0} for name in ('run_ns3', 'off-run_ns3', 'aggregate_ns3', 'off-aggregate_ns3')},
            service_projection={}, feedback_diagnostics={}, service_diagnostics={}, application_metrics={'attempts': 1})

    def check(self):
        def loaded(path):
            path = Path(path)
            if path.name == 'manifest.json':
                return self.record if path.parent.name == self.key else self.suite
            if path.name == 'build.json':
                return self.build
            if path.name == 'environment-build.json':
                return self.environment
            return {}
        with ExitStack() as stack:
            for name, replacement in {
                    'CASE_ORDER': [self.key], 'load_json': loaded, 'verify_plan': lambda *args: None,
                    'verify_inventory': lambda *args: None, 'verify_comparisons': lambda *args: None,
                    'verify_service_projection': lambda *args: {}, 'feedback_summary': lambda *args: {},
                    'service_summary': lambda *args: {}}.items():
                stack.enter_context(patch.object(review, name, replacement))
            stack.enter_context(patch.object(review.BASE, 'digest', lambda *args: self.hash))
            stack.enter_context(patch.object(review.METRICS, 'ns3_applications', lambda *args: {'attempts': 1}))
            return review.verify_reference_suite(self.home, {'cases': [self.case]})

    def test_complete_stage_membership_passes(self):
        self.assertEqual(self.check()['status'], 'passed')

    def test_empty_stages_fail(self):
        self.record['stages'] = {}
        with self.assertRaisesRegex(ValueError, 'stage missing or failed'):
            self.check()

    def test_each_missing_stage_fails(self):
        original = copy.deepcopy(self.record['stages'])
        for name in original:
            self.record['stages'] = {key: value for key, value in original.items() if key != name}
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'stage missing or failed'):
                self.check()

    def test_failed_stage_fails(self):
        self.record['stages']['off-run_ns3']['exit_code'] = 1
        with self.assertRaisesRegex(ValueError, 'stage missing or failed'):
            self.check()

    def test_wrong_case_runner_hash_fails(self):
        self.record['runner_sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'case identity or completion differs'):
            self.check()

    def test_missing_binary_stability_claim_fails(self):
        self.suite['binary_and_overlay_files_stable'] = False
        with self.assertRaisesRegex(ValueError, 'suite did not complete'):
            self.check()


class DackClassification(TemporaryCase):
    def test_native_ack_and_dack_flags_classify_dack_first(self):
        code = review.HELPER.read_text()
        expression = re.search(r'event\.packetType\s*=\s*([^;]+);', code)
        self.assertIsNotNone(expression, 'Cannot identify actual observer classification expression')
        compiler = shutil.which('g++')
        self.assertIsNotNone(compiler, 'g++ is required for bounded classification check')
        source = self.home / 'classify.cc'
        source.write_text('#include <string>\n'
            'struct H { bool ack, dack; bool IsAck() const { return ack; } bool IsDack() const { return dack; } };\n'
            'int main() { const H inputs[] = {{false,false},{true,false},{true,true},{false,true}};\n'
            'const char* expected[] = {"other","ack","dack","dack"};\n'
            'for (int i=0; i<4; ++i) { H header=inputs[i]; std::string actual = ' + expression.group(1) + ';\n'
            'if (actual != expected[i]) return 10+i; } return 0; }\n')
        executable = self.home / 'classify'
        compiled = subprocess.run([compiler, '-std=c++17', str(source), '-o', str(executable)], capture_output=True, text=True)
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        run = subprocess.run([str(executable)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, f'Actual helper expression misclassified native flag combination: exit {run.returncode}')


if __name__ == '__main__':
    print(json.dumps({'scope': __doc__.splitlines()[0], 'target': str(target),
                      'target_sha256': digest(target.read_bytes()),
                      'helper_sha256': digest(review.HELPER.read_bytes())}), flush=True)
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
