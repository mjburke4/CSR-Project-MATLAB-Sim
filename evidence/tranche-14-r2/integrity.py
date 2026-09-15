#!/usr/bin/env python3
"""Audit the failed second T14 owner return without granting acceptance.

Use the immutable first repair tree (csr14r), not the next repair tree.
The normal completion and test-success gates must still reject this archive.
No MATLAB execution or absent diagnostic results are reconstructed here.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import importlib
import json
from pathlib import Path
import sys
import tempfile
from zipfile import ZipFile

CANDIDATE_SHA = '94bde01e85eac80af05b0e9aa81132b4b7b0fee7907fc3420d28ae8b49eb9609'
EXPECTED_MEMBERS = {'references.json', 'run.log', 'source.json', 'tests.csv', 'metadata.json'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=Path('csr14r'))
    parser.add_argument('--evidence', type=Path, default=Path('upload/t14(1).zip'))
    parser.add_argument('--output', type=Path, default=Path('t14s/integrity.json'))
    args = parser.parse_args()
    source = args.source_root.resolve()
    sys.path.insert(0, str(source / 'scripts'))
    a = importlib.import_module('analyze_tranche14_return')
    require = a.require
    candidate = a.json_object(source / a.CANDIDATE)
    require(a.sha256(source / a.CANDIDATE) == CANDIDATE_SHA,
            'Audit requires immutable first-repair T14 candidate')
    with ZipFile(args.evidence) as archive:
        require(len(archive.infolist()) == 5 and set(archive.namelist()) == EXPECTED_MEMBERS,
                'Unexpected second-return ZIP membership')
    rejections = {}
    # This retained helper rejects traversal, symlinks, encryption, collisions,
    # nonregular members and oversized archives, and checks CRC while reading.
    with a.evidence_directory(args.evidence) as run:
        metadata = a.json_object(run / 'metadata.json')
        require(metadata['Status'] == 'failed' and metadata['CandidateSHA256'] == CANDIDATE_SHA,
                'Unexpected run/candidate identity')
        require(metadata['Schema'] == a.SCHEMA and metadata['Tranche'] == 14 and
                metadata['MATLABExecuted'] is True and metadata['NativeExecuted'] is False and
                metadata['SourceCommit'] == a.PIN, 'Owner runtime/source identity differs')
        require(metadata['Runtime']['Version'] == '25.1.0.2943329 (R2025a)' and
                metadata['Runtime']['DefaultBackend'] == 'portable', 'Unexpected owner runtime')
        require(metadata['InventoryExcludedPaths'] == ['metadata.json'] and
                metadata['EvidenceArchive'] == 't14.zip' and metadata['LocalArtifacts'] == [],
                'Unexpected archive closure declarations')
        require(metadata['DiagnosticOnly'] is True and all(metadata[field] is False for field in
                ('TestsPassed', 'BoundaryCompleted', 'BoundaryPassed', 'BoundaryMatchesNative',
                 'FocusedGateExecuted', 'FullAcceptanceGateExecuted', 'AcceptanceEstablished',
                 'NumericalParityEstablished')), 'Failed run contains contradictory success claim')
        artifacts = a.inventory(run, metadata['Artifacts'], excluded=('metadata.json',))
        require(len(artifacts) == 4 and a.all_files(run) == EXPECTED_MEMBERS,
                'Unexpected artifact inventory size or membership')
        sources = a.verify_sources(run, metadata, source)
        source_map = a.record_map(a.json_value(run / 'source.json'), 'source')
        matlab_count = sum(name.endswith('.m') for name in source_map)
        require(sources['count'] == 283 and matlab_count == 142, 'Unexpected source inventory')
        references = a.verify_references(run, metadata, source, candidate)
        require(references['count'] == 299, 'Unexpected reference inventory')
        baseline = a.verify_baseline(metadata, source, candidate)
        a.verify_plan(source, candidate)

        names = a.selected_test_names(source, candidate['TestFiles'])
        require(candidate['ExpectedTestNames'] == metadata['ExpectedTestNames'] == names and
                candidate['TestFiles'] == metadata['TestFiles'], 'Test selection identity differs')
        tests = a.csv_rows(run / 'tests.csv', ('Name','Passed','Failed','Incomplete','DurationSeconds'))
        require(len(tests) == len(names) == 106 and Counter(row['Name'] for row in tests) == Counter(names),
                'Missing, duplicate or unexpected MATLAB tests')
        totals = {field: sum(a.logical(row[field], field) for row in tests)
                  for field in ('Passed','Failed','Incomplete')}
        require(totals == {'Passed':88,'Failed':18,'Incomplete':18}, 'Unexpected test results')
        require(metadata['TestsExecuted'] is True and metadata['TestCount'] == 106 and
                metadata['PassedTests'] == 88 and metadata['FailedTests'] == 18 and
                metadata['IncompleteTests'] == 18 and metadata['TestClassesCompleted'] == 9,
                'Test counters contradict exact results')
        for row in tests:
            a.number(row['DurationSeconds'], 'test duration', minimum=0)
            require(not (a.logical(row['Passed'], 'Passed') and
                         (a.logical(row['Failed'], 'Failed') or a.logical(row['Incomplete'], 'Incomplete'))),
                    'Contradictory per-test state')
            require(not a.logical(row['Incomplete'], 'Incomplete') or a.logical(row['Failed'], 'Failed'),
                    'Incomplete test is not included in failed count')
        retained_candidate = a.json_object(source / 'evidence/t13/candidate.json')
        retained_names = a.selected_test_names(source, retained_candidate['TestFiles'])
        retained = [row for row in tests if row['Name'] in retained_names]
        new = [row for row in tests if row['Name'].startswith('TestAckEdgeContract/')]
        require(len(retained_names) == len(retained) == 88 and
                all(a.logical(row['Passed'],'Passed') and not a.logical(row['Failed'],'Failed') and
                    not a.logical(row['Incomplete'],'Incomplete') for row in retained),
                'Retained MATLAB baseline test regressed')
        require(len(new) == 18 and all(not a.logical(row['Passed'],'Passed') and
                a.logical(row['Failed'],'Failed') and a.logical(row['Incomplete'],'Incomplete')
                for row in new), 'New T14 class failure identity differs')
        require(len(retained) + len(new) == len(tests), 'Unaccounted test class')

        failure = metadata['BoundaryFailure']
        require(failure['Identifier'] == 'MATLAB:table:vertcat:VertcatMethodFailed' and
                failure['Message'] == "An error occurred when concatenating the table variable 'case' using vertcat.",
                'Unexpected boundary failure')
        require([(row['name'], row['line']) for row in failure['Stack']] ==
                [('vertcat',207),('ackEdgeContract',24),('run_tranche14_validation',75)],
                'Boundary failure does not identify table concatenation')
        require(metadata['Failure']['Identifier'] == 'MATLAB:unittest:TestResult:UnsuccessfulRun',
                'Unexpected final runner rejection')
        require(metadata['BoundaryDirectory'] == 'edge' and all(metadata[field] == 0 for field in
                ('BoundaryCaseCount','BoundaryEventCount','BoundaryCheckpointCount','BoundaryUnmatchedCount')),
                'Unexpected incomplete diagnostic counters')
        log = (run / 'run.log').read_text(encoding='utf-8')
        markers = ('ACK edge diagnostic 1/6: tie_early (4 simulated seconds).',
                   'ACK edge diagnostic 2/6: tie_late (4 simulated seconds).')
        require(all(log.count(marker) == 2 for marker in markers) and
                not any('ACK edge diagnostic '+str(i)+'/6:' in log for i in range(3,7)),
                'Console progress differs from two interrupted invocations')
        require('Error occurred while setting up or tearing down TestAckEdgeContract.' in log and
                'all TestAckEdgeContract tests failed and did not run to completion.' in log and
                "concatenating the table variable 'case' using vertcat." in log,
                'Console does not confirm class setup/teardown failure')

        for label, function in (
            ('run_identity',lambda:a.verify_run_identity(run,metadata,source,candidate)),
            ('test_success',lambda:a.verify_tests(run,metadata,source,candidate))):
            try:
                function()
            except ValueError as error:
                rejections[label] = str(error)
            else:
                raise ValueError('Failed owner archive unexpectedly passed ' + label)
        with tempfile.TemporaryDirectory(prefix='t14s-reject-') as temporary:
            try:
                a.review(args.evidence,source,Path(temporary))
            except ValueError as error:
                rejections['full_review'] = str(error)
            else:
                raise ValueError('Failed owner archive unexpectedly passed normal review')

        started, completed = (datetime.fromisoformat(metadata[field].replace('Z','+00:00'))
                              for field in ('StartedUTC','CompletedUTC'))
        require(started.tzinfo and completed.tzinfo and completed >= started, 'Invalid owner timestamps')
        report = {'schema':'csr-tranche14-second-failed-owner-integrity-v1',
                  'status':'failed_run_integrity_verified_not_accepted',
                  'evidence_integrity_verified':True,'focused_structural_gate_completed':False,
                  'acceptance_established':False,'numerical_parity_established':False,
                  'matlab_executed_by_reviewer':False,
                  'evidence':{'path':args.evidence.name,'sha256':a.sha256(args.evidence),
                              'bytes':args.evidence.stat().st_size,'regular_members':5,
                              'inventoried_artifacts':4,'metadata_sha256':a.sha256(run/'metadata.json'),
                              'members':sorted(EXPECTED_MEMBERS)},
                  'candidate_sha256':CANDIDATE_SHA,'runtime':metadata['Runtime'],
                  'owner_elapsed_seconds':(completed-started).total_seconds(),
                  'source':sources|{'matlab_files':matlab_count,'stable_before_after':True},
                  'references':references|{'stable_before_after':True},'baseline':baseline,
                  'tests':{'count':106,'passed':88,'failed':18,'incomplete':18,
                           'incomplete_is_subset_of_failed':True,'retained_passed':88,'retained_count':88,
                           'new_class_passed':0,'new_class_failed':18,'new_class_incomplete':18,
                           'new_class_setup_failed':True,
                           'failed_names':[row['Name'] for row in new],
                           'retained_duration_seconds':float(sum(a.number(row['DurationSeconds'],'duration') for row in retained))},
                  'diagnostic':{'complete_case_results_available':False,
                                'edge_artifacts_available':False,
                                'reported_cases':0,'reported_events':0,'reported_checkpoints':0,
                                'reported_unmatched_count':0,
                                'boundary_error_identifier':failure['Identifier'],
                                'boundary_error_message':failure['Message'],
                                'fixture_failure_line':24,
                                'console_case_labels_per_invocation':['tie_early','tie_late'],
                                'console_invocations':2,
                                'interpretation':'The diagnostic and class setup both abort while concatenating per-case tables. No edge evidence was exported. Reaching the second console label does not establish that the first case passed. Zero reported differences is an unpopulated counter, not a parity result.'},
                  'normal_gate_rejections':rejections,
                  'audit_source_sha256':a.sha256(Path(__file__))}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'source':sources['count'],'matlab':matlab_count,
                      'references':references['count'],'tests':totals,'retained_passed':88,
                      'edge_evidence_available':False,'acceptance_established':False,
                      'normal_gate_rejections':rejections},indent=2))


if __name__ == '__main__':
    main()
