#!/usr/bin/env python3
"""Audit the rejected first T14 owner return, without granting acceptance.

Usage: python t14r/integrity.py --source-root csr14 --evidence upload/t14.zip
Requires the immutable original T14 package, not the repaired candidate.
The normal gate and test-success helpers must reject this run. Independent
inventory/provenance checks remain useful for diagnosing a genuine failed run.
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

CANDIDATE_SHA = '38d3e5cbbf30528a5a5a99a39b04d45490f22663486e3ebdafbfaeb95f4003d1'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=Path('csr14'))
    parser.add_argument('--evidence', type=Path, default=Path('upload/t14.zip'))
    parser.add_argument('--output', type=Path, default=Path('t14r/integrity.json'))
    args = parser.parse_args()
    source = args.source_root.resolve()
    sys.path.insert(0, str(source / 'scripts'))
    a = importlib.import_module('analyze_tranche14_return')
    require = a.require
    candidate = a.json_object(source / a.CANDIDATE)
    require(a.sha256(source / a.CANDIDATE) == CANDIDATE_SHA,
            'Audit requires immutable original T14 candidate')
    rejections = {}
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
        require(all(metadata[field] is False for field in
                ('TestsPassed', 'BoundaryCompleted', 'BoundaryPassed', 'BoundaryMatchesNative',
                 'FocusedGateExecuted', 'FullAcceptanceGateExecuted', 'AcceptanceEstablished',
                 'NumericalParityEstablished')), 'Failed run contains contradictory success claim')
        artifacts = a.inventory(run, metadata['Artifacts'], excluded=('metadata.json',))
        require(len(artifacts) == 11 and len(a.all_files(run)) == 12,
                'Unexpected artifact inventory size')
        sources = a.verify_sources(run, metadata, source)
        source_map = a.record_map(a.json_value(run / 'source.json'), 'source')
        matlab_count = sum(name.endswith('.m') for name in source_map)
        require(sources['count'] == 283 and matlab_count == 142, 'Unexpected source inventory')
        references = a.verify_references(run, metadata, source, candidate)
        require(references['count'] == 283, 'Unexpected reference inventory')
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
        require(totals == {'Passed':97,'Failed':9,'Incomplete':2}, 'Unexpected test results')
        require(metadata['TestsExecuted'] is True and metadata['TestCount'] == 106 and
                metadata['PassedTests'] == 97 and metadata['FailedTests'] == 9 and
                metadata['IncompleteTests'] == 2 and metadata['TestClassesCompleted'] == 9,
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
        require(len(retained_names) == len(retained) == 88 and
                all(a.logical(row['Passed'],'Passed') and not a.logical(row['Failed'],'Failed') and
                    not a.logical(row['Incomplete'],'Incomplete') for row in retained),
                'Retained MATLAB baseline test regressed')
        require(all(row['Name'].startswith('TestAckEdgeContract/') for row in tests
                    if a.logical(row['Failed'], 'Failed')), 'Failure extends outside new T14 class')

        summary = a.json_object(run / 'edge/summary.json')
        events = a.csv_rows(run / 'edge/events.csv', a.EVENT_FIELDS)
        boundaries = a.csv_rows(run / 'edge/boundary.csv', a.BOUNDARY_FIELDS)
        scheduler = a.csv_rows(run / 'edge/scheduler.csv', a.SCHEDULER_FIELDS)
        checks = a.csv_rows(run / 'edge/check.csv', a.CHECK_FIELDS)
        draws = a.csv_rows(run / 'edge/draws.csv', a.DRAW_FIELDS)
        usage = a.csv_rows(run / 'edge/usage.csv', a.USAGE_FIELDS)
        require((len(events),len(boundaries),len(scheduler),len(checks),len(draws),len(usage)) ==
                (36,0,660,222,18,18), 'Unexpected partial diagnostic sizes')
        failed_checks = sum(not a.logical(row['pass'], 'check pass') for row in checks)
        require(failed_checks == summary['FailedCount'] == 135, 'Structural failure counts disagree')
        require(summary['DiagnosticCompleted'] is False and summary['Passed'] is False and
                summary['MatchesNative'] is False and summary['EventCount'] == metadata['BoundaryEventCount'] == 36 and
                summary['CheckpointCount'] == metadata['BoundaryCheckpointCount'] == 222,
                'Boundary metadata contradicts incomplete evidence')
        require([row['Case'] for row in summary['CaseResults']] == list(a.CASES), 'Case identity differs')
        case_results = []
        for result in summary['CaseResults']:
            case = result['Case']
            require(result['Completed'] is False and result['Passed'] is False and
                    result['ErrorIdentifier'] == 'MATLAB:nonExistentField' and
                    result['ErrorMessage'] == 'Unrecognized field name "SourceId".',
                    'Unexpected per-case failure')
            stack = result['ErrorStack']
            require([(row['name'],row['line']) for row in stack[:2]] ==
                    [('ackEdgeContract/runCase/observe',333),('ackEdgeContract/runCase/transmit',254)],
                    'Failure stack does not identify the original observer')
            observed = [row for row in events if row['case'] == case]
            require([row['phase'] for row in observed] ==
                    ['prime_before','deliver','prime_after','prime_before','deliver','prime_after'] and
                    all(row['time_ns'] == '2832961000' for row in observed), 'Unexpected completed event prefix')
            trace = [row for row in scheduler if row['case'] == case]
            executes = [row for row in trace if row['operation'] == 'execute']
            require(len(trace) == 110 and executes[-1]['event_id'] == '56' and
                    executes[-1]['callback'] == '@()obj.slotTick()' and
                    executes[-1]['observed_hex'] == '4008f5c28f5c28f6', 'Unexpected execution stop')
            # Check exact timestamp serialization on the observed prefix. The
            # completed scheduler validator correctly rejects remaining due work.
            for row in trace:
                a.full_time(row['observed_seconds'],row['observed_hex'],'observed prefix')
                a.full_time(row['scheduled_seconds'],row['scheduled_hex'],'scheduled prefix')
            require(result['Delivered'] == 2 and result['GatewayAckTransmissions'] == 0 and
                    result['SourceDataTransmissions'] == 0 and result['IngressEventId'] == 0 and
                    result['FirstAckEventId'] == 0, 'Unexpected post-error result state')
            case_results.append({'case':case,'completed':False,'error_identifier':result['ErrorIdentifier'],
                                 'error_message':result['ErrorMessage'],
                                 'observer_line':333,'transmit_caller_line':254,
                                 'last_execute_id':56,'last_execute_seconds':executes[-1]['observed_seconds'],
                                 'last_execute_hex':executes[-1]['observed_hex'],
                                 'event_rows':6,'priming_deliveries':2,'boundary_rows':0,
                                 'gateway_ack_observations':0})

        comparisons = []
        for key, family, actual in (
            ('EventComparison','events',events),('FullPrecisionComparison','events',events),
            ('BoundaryComparison','boundary',boundaries),('DrawComparison','draws',draws),
            ('UsageComparison','usage',usage)):
            claim = summary[key]
            native = a.csv_rows(source / a.REFERENCE / (family + '.csv'))
            recomputed = a.compare_cases(actual,native,claim['ComparedFields'],key)
            require(recomputed['unmatched_rows'] == claim['UnmatchedCount'] and
                    recomputed['actual_rows'] == claim['ActualRows'] and
                    recomputed['reference_rows'] == claim['ReferenceRows'], 'Partial comparison count differs')
            fields = Counter(field for row in recomputed['differences'] for field in row['fields'])
            if key != 'UsageComparison':
                require(dict(fields) == {'missing_row':recomputed['unmatched_rows']},
                        'Observed prefix differs from native beyond missing tail')
            comparisons.append({'family':key,'actual_rows':len(actual),'reference_rows':len(native),
                                'unmatched_rows':recomputed['unmatched_rows'],'difference_fields':dict(fields)})
        require(sum(row['unmatched_rows'] for row in comparisons) ==
                summary['UnmatchedCount'] == metadata['BoundaryUnmatchedCount'] == 406,
                'Mismatch total differs')

        # Explicitly retain and demonstrate rejection by the unmodified gate.
        for label, function in (
            ('run_identity',lambda:a.verify_run_identity(run,metadata,source,candidate)),
            ('test_success',lambda:a.verify_tests(run,metadata,source,candidate)),
            ('completed_scheduler',lambda:a.validate_scheduler(scheduler,events,boundaries,label='failed owner'))):
            try:
                function()
            except ValueError as error:
                rejections[label] = str(error)
            else:
                raise ValueError('Failed owner archive unexpectedly passed ' + label)
        with tempfile.TemporaryDirectory(prefix='t14-reject-') as temporary:
            try:
                a.review(args.evidence,source,Path(temporary))
            except ValueError as error:
                rejections['full_review'] = str(error)
            else:
                raise ValueError('Failed owner archive unexpectedly passed normal review')

        started, completed = (datetime.fromisoformat(metadata[field].replace('Z','+00:00'))
                              for field in ('StartedUTC','CompletedUTC'))
        require(started.tzinfo and completed.tzinfo and completed >= started, 'Invalid owner timestamps')
        report = {'schema':'csr-tranche14-failed-owner-integrity-v1',
                  'status':'failed_run_integrity_verified_not_accepted',
                  'evidence_integrity_verified':True,'focused_structural_gate_completed':False,
                  'acceptance_established':False,'numerical_parity_established':False,
                  'matlab_executed_by_reviewer':False,
                  'evidence':{'path':args.evidence.name,'sha256':a.sha256(args.evidence),
                              'bytes':args.evidence.stat().st_size,'regular_members':12,
                              'inventoried_artifacts':11,'metadata_sha256':a.sha256(run/'metadata.json')},
                  'candidate_sha256':CANDIDATE_SHA,'runtime':metadata['Runtime'],
                  'owner_elapsed_seconds':(completed-started).total_seconds(),
                  'source':sources|{'matlab_files':matlab_count,'stable_before_after':True},
                  'references':references|{'stable_before_after':True},'baseline':baseline,
                  'tests':{'count':106,'passed':97,'failed':9,'incomplete':2,
                           'incomplete_is_subset_of_failed':True,'retained_passed':88,'retained_count':88,
                           'new_class_passed':9,'new_class_failed':9,
                           'failed_names':[row['Name'] for row in tests if a.logical(row['Failed'],'Failed')],
                           'incomplete_names':[row['Name'] for row in tests if a.logical(row['Incomplete'],'Incomplete')],
                           'retained_duration_seconds':float(sum(a.number(row['DurationSeconds'],'duration') for row in retained))},
                  'diagnostic':{'completed_cases':0,'attempted_cases':6,'checkpoints':222,
                                'passed_checks':87,'failed_checks':135,'events':36,'boundaries':0,
                                'cases':case_results,'comparisons':comparisons,'reported_unmatched_count':406,
                                'interpretation':'Comparison is invalid as a parity measurement: every case aborts in the observer on the source aggregate ACK member at 3.12 s, before the DATA transport and gateway ACK opportunity. Missing trace tails and truncated usage account for all 406 differences.'},
                  'normal_gate_rejections':rejections,
                  'audit_source_sha256':a.sha256(Path(__file__))}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'source':sources['count'],'matlab':matlab_count,
                      'references':references['count'],'tests':totals,'retained_passed':88,
                      'cases_completed':0,'mismatches_not_parity':406},indent=2))


if __name__ == '__main__':
    main()
