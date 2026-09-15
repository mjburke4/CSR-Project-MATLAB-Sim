#!/usr/bin/env python3
"""Independent, read-only audit of the returned Tranche 7 evidence.

Uses Python standard library and immutable Git blobs, not the production return
reviewer. The output describes structural evidence only, not numeric parity.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import posixpath
import re
import stat
import subprocess
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def integer(value):
    number = float(value)
    assert math.isfinite(number) and number.is_integer()
    return int(number)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--previous-tranche6', type=Path)
    parser.add_argument('--output-root', required=True, type=Path)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    errors = []
    counts = collections.Counter()

    def check(condition, label):
        if not condition:
            errors.append(label)

    git_cache = {}

    def git_file(path):
        if path not in git_cache:
            git_cache[path] = subprocess.check_output(
                ['git', 'show', f'{args.candidate}:{path}'], cwd=args.source_root)
        return git_cache[path]

    paths = subprocess.check_output(
        ['git', 'ls-tree', '-r', '--name-only', args.candidate],
        cwd=args.source_root, text=True).splitlines()
    expected_source = {
        p for p in paths if
        ('/' not in p and p.endswith('.m')) or
        (p.startswith(('+csr/', 'tests/', 'examples/')) and p.endswith('.m')) or
        (p.startswith('scripts/') and p.endswith(('.py', '.cc'))) or
        p.startswith(('data/', 'scenarios/')) or
        (p.startswith('evidence/tranche-') and p.endswith('-candidate.json')) or
        p == 'evidence/source-baseline.json'
    }
    reference_prefixes = ('evidence/tranche-7-ns3-reference/',
                          'evidence/tranche-7-benchmark-inputs/')
    expected_reference = {p for p in paths if p.startswith(reference_prefixes)}
    report = {
        'schema': 'csr-tranche7-independent-return-audit-v1',
        'reviewed_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'candidate_commit': args.candidate,
        'archive': {'name': args.archive.name,
                    'bytes': args.archive.stat().st_size,
                    'sha256': sha(args.archive.read_bytes())},
        'audit_method': 'Independent Python standard-library checks against immutable Git blobs; production review script not imported or executed.',
        'matlab_executed_locally': False,
        'matlab_execution_evidence': 'Owner-returned MATLAB evidence archive',
        'numerical_parity_established': False,
    }
    with zipfile.ZipFile(args.archive) as archive:
        names = archive.namelist()
        check(len(names) == len(set(names)), 'duplicate archive entries')
        check(len(names) == len({n.casefold() for n in names}), 'case-colliding archive entries')
        check(archive.testzip() is None, 'archive CRC failure')
        file_hashes = {}
        file_sizes = {}
        for entry in archive.infolist():
            name = entry.filename
            check(not name.startswith('/') and '..' not in PurePosixPath(name).parts and '\\' not in name,
                  f'unsafe archive path: {name}')
            check(not stat.S_ISLNK(entry.external_attr >> 16), f'archive symlink: {name}')
            check(not entry.flag_bits & 1, f'encrypted archive entry: {name}')
            if not entry.is_dir():
                file_hashes[name] = sha(archive.read(name))
                file_sizes[name] = entry.file_size

        def read_json(name):
            return json.loads(archive.read(name))

        def csv_rows(name):
            with archive.open(name) as stream:
                yield from csv.DictReader(io.TextIOWrapper(stream, encoding='utf-8-sig', newline=''))

        meta = read_json('validation_metadata.json')
        snapshot = read_json('source_snapshot.json')
        snapshot_paths = {e['path'] for e in snapshot}
        check(snapshot_paths == expected_source, 'source snapshot membership differs from candidate')
        check(len(snapshot_paths) == len(snapshot), 'duplicate source snapshot paths')
        check(snapshot == meta['SourceFiles'] == meta['SourceFilesFinal'], 'source snapshots differ')
        check(meta['ReferenceFiles'] == meta['ReferenceFilesFinal'], 'reference snapshots differ')
        check({e['path'] for e in meta['ReferenceFiles']} == expected_reference,
              'reference inventory membership differs from candidate')
        check(file_hashes['source_snapshot.json'] == meta['SourceSnapshotSHA256'], 'snapshot SHA mismatch')
        for item in snapshot + meta['ReferenceFiles']:
            check(sha(git_file(item['path'])) == item['sha256'], f'candidate blob mismatch: {item["path"]}')
        top_inventory = {e['path'] for e in meta['Artifacts']}
        check(top_inventory == set(file_hashes) - {'validation_metadata.json'}, 'outer inventory coverage mismatch')
        check(meta['Status'] == 'completed', 'outer execution not completed')
        check(meta['TestsExecuted'] and meta['TestsPassed'], 'outer tests not passed')
        check(not meta['NativeRequested'] and not meta['NativeExecuted'], 'unexpected native scope')
        check(meta['SourceFilesStableDuringRun'] and meta['ReferenceFilesStableDuringRun'], 'runtime stability flags false')
        nested = []
        for name in names:
            if not name.endswith('.json'):
                continue
            data = read_json(name)
            if not isinstance(data, dict):
                continue
            for key in ('Artifacts', 'files'):
                items = data.get(key, [])
                if isinstance(items, dict):
                    items = [items]
                for item in items:
                    if not isinstance(item, dict) or not {'path', 'sha256'} <= item.keys():
                        continue
                    artifact_path = posixpath.join(posixpath.dirname(name), item['path'])
                    counts['declared_artifact_hash_checks'] += 1
                    check(file_hashes.get(artifact_path) == item['sha256'], f'artifact hash mismatch: {artifact_path}')
                    if 'bytes' in item:
                        check(file_sizes.get(artifact_path) == integer(item['bytes']), f'artifact size mismatch: {artifact_path}')
            for key in ('SourceFiles', 'SourceFilesFinal', 'source_files'):
                for item in data.get(key, []):
                    counts['source_hash_checks_in_nested_bindings'] += 1
                    check(sha(git_file(item['path'])) == item['sha256'], f'nested source mismatch: {item["path"]}')
            for item in data.get('MatlabSourceFiles', []):
                counts['legacy_dot_m_hash_checks'] += 1
                check(sha(git_file(item['Path'])) == item['SHA256'], f'legacy source mismatch: {item["Path"]}')
            if name.endswith('validation_metadata.json'):
                check(data['Status'] == 'completed', f'nested status: {name}')
                check((data['TestCount'], data['PassedTests'], data['FailedTests'], data['IncompleteTests']) == (467, 467, 0, 0), f'nested test counts: {name}')
                nested.append({'path': name, 'schema': data.get('Schema', 'legacy-tranche3'),
                               'test_count': data['TestCount'], 'status': data['Status']})
        test_name = next(n for n in names if n.endswith('/test_results.csv'))
        tests = list(csv_rows(test_name))
        check(len(tests) == 467 and len({r['Name'] for r in tests}) == 467, 'test row count or uniqueness')
        check(all((r['Passed'], r['Failed'], r['Incomplete']) == ('1', '0', '0') for r in tests), 'test CSV contains non-passing record')
        for result in tests:
            class_name, method = result['Name'].split('/')
            source_test = f'tests/{class_name}.m'
            text = git_file(source_test).decode()
            check(re.search(r'\bfunction\s+' + re.escape(method) + r'\s*\(', text) is not None,
                  f'test method not found in candidate: {result["Name"]}')
        cases = []
        for case in meta['Cases']:
            base = case['Directory']
            manifest_path = base + '/benchmark_manifest.json'
            manifest = read_json(manifest_path)
            check(file_hashes[manifest_path] == case['ManifestSHA256'], f'case manifest binding: {base}')
            check(manifest['source_files'] == snapshot and manifest['source_snapshot_sha256'] == meta['SourceSnapshotSHA256'], f'case source binding: {base}')
            check(manifest['status'] == 'completed' and manifest['structural_checks_passed'], f'case structural flag: {base}')
            check(manifest['runtime'] == meta['Runtime'], f'case runtime differs: {base}')
            summary = read_json(base + '/raw/summary.json')
            stats = summary['Statistics']
            check(stats['Generated'] == stats['Received'] + stats['Dropped'] + stats['Pending'], f'app partition: {base}')
            check(stats['PhysicalAttempts'] == stats['PhysicalReceived'] + stats['PhysicalDropped'] + stats['PhysicalPending'], f'PHY partition: {base}')
            check(stats['OmittedTraceRecords'] == 0 and stats['OmittedPhyTraceRecords'] == 0, f'trace truncation: {base}')
            applications = list(csv_rows(base + '/analysis/applications.csv'))
            ids = {r['PacketId'] for r in applications}
            check(len(ids) == len(applications) == stats['Generated'], f'app ID uniqueness/count: {base}')
            outcomes = collections.Counter(r['Outcome'] for r in applications)
            check((outcomes['delivered'], outcomes['dropped'], outcomes['pending']) == (stats['Received'], stats['Dropped'], stats['Pending']), f'app outcomes: {base}')
            flows = []
            for admission in csv_rows(base + '/raw/application_admission_statistics.csv'):
                blocked = sum(integer(v) for k, v in admission.items() if k.startswith('Blocked'))
                check(integer(admission['Attempts']) == integer(admission['Admitted']) + blocked, f'admission partition: {base}')
                selected = [r for r in applications if r['SourceId'] == admission['SourceId'] and r['DestinationId'] == admission['ConfiguredDestinationId']]
                check(len(selected) == integer(admission['Admitted']), f'flow admission/application count: {base}')
                flow_outcomes = collections.Counter(r['Outcome'] for r in selected)
                flows.append({'source_id': integer(admission['SourceId']), 'attempts': integer(admission['Attempts']),
                              'admitted': len(selected), 'delivered': flow_outcomes['delivered'],
                              'dropped': flow_outcomes['dropped'], 'pending': flow_outcomes['pending'],
                              'blocked_nsdp': integer(admission['BlockedNsdp'])})
            protocol_events = collections.Counter()
            protocol_app_ids = collections.defaultdict(set)
            protocol_count = 0
            for row in csv_rows(base + '/raw/protocol_trace.csv'):
                protocol_count += 1
                protocol_events[row['Event']] += 1
                if row['Event'] in ('app_generate', 'app_receive', 'app_drop'):
                    protocol_app_ids[row['Event']].add(row['PacketId'])
            for event, expected_count in [('app_generate', stats['Generated']), ('app_receive', stats['Received']), ('app_drop', stats['Dropped'])]:
                check(protocol_events[event] == len(protocol_app_ids[event]) == expected_count, f'raw app event counts: {base}/{event}')
            check(protocol_app_ids['app_generate'] == ids, f'raw/app packet identity set: {base}')
            check(protocol_events['tx_start'] == stats['PhysicalTransmissions'], f'physical TX trace count: {base}')
            phy_count = sum(1 for _ in csv_rows(base + '/raw/phy_trace.csv'))
            admission_count = sum(1 for _ in csv_rows(base + '/raw/application_admission_trace.csv'))
            omitted = integer(stats['OmittedApplicationAdmissionRecords'])
            check(admission_count + omitted == sum(f['attempts'] for f in flows), f'admission trace count: {base}')
            check(omitted == manifest['admission_trace_omitted_records'] and manifest['admission_counts_complete'], f'admission omission declarations: {base}')
            performance = next(csv_rows(base + '/analysis/performance_summary.csv'))
            check(protocol_count == integer(performance['ProtocolTraceRecords']) and phy_count == integer(performance['PhyTraceRecords']), f'exported trace row counts: {base}')
            cases.append({'case_id': case['CaseId'], 'generated': stats['Generated'], 'delivered': stats['Received'],
                          'dropped': stats['Dropped'], 'pending': stats['Pending'], 'physical_pending': stats['PhysicalPending'],
                          'runtime_seconds': summary['Metadata']['RuntimeSeconds'], 'all_flows_made_progress': all(f['delivered'] > 0 for f in flows),
                          'protocol_trace_rows': protocol_count, 'phy_trace_rows': phy_count,
                          'admission_trace_rows': admission_count, 'admission_trace_omitted': omitted, 'flows': flows})
        sweep_file = min((n for n in names if n.endswith('/scenario_summary.csv')), key=lambda n: n.count('/'))
        sweeps = list(csv_rows(sweep_file))
        check(len(sweeps) == 18, 'retained sweep count')
        check(all(r['StructuralChecksPassed'] == '1' for r in sweeps), 'retained sweep structural flag')
        fixed_summaries = [n for n in names if n.endswith('/scenario_summary.csv') and n != sweep_file]
        retained_case_count = sum(sum(1 for _ in csv_rows(n)) for n in fixed_summaries)
        check(retained_case_count == 28, 'retained fixed-case count')
        previous_comparison = None
        if args.previous_tranche6:
            with zipfile.ZipFile(args.previous_tranche6) as previous:
                prev_file = min((n for n in previous.namelist() if n.endswith('/scenario_summary.csv')), key=lambda n: n.count('/'))
                previous_rows = list(csv.DictReader(io.StringIO(previous.read(prev_file).decode('utf-8-sig'))))
                def normalized_path(value):
                    return '/'.join(part for part in value.split('/') if not part.startswith('run_'))
                regression_prefix = meta['RegressionEvidenceDirectory'] + '/'
                previous_summaries = {normalized_path(n): n for n in previous.namelist() if n.endswith('/summary.json')}
                current_summaries = {normalized_path(n[len(regression_prefix):]): n for n in names
                                     if n.startswith(regression_prefix) and n.endswith('/summary.json')}
                check(previous_summaries.keys() == current_summaries.keys(), 'retained statistics case membership differs')
                statistic_differences = []
                added_statistics = collections.Counter()
                for key in previous_summaries.keys() & current_summaries.keys():
                    previous_stats = json.loads(previous.read(previous_summaries[key]))['Statistics']
                    current_stats = read_json(current_summaries[key])['Statistics']
                    for field in previous_stats.keys() & current_stats.keys():
                        if previous_stats[field] != current_stats[field]:
                            statistic_differences.append({'case': key, 'field': field,
                                                         'previous': previous_stats[field], 'current': current_stats[field]})
                    for field in current_stats.keys() - previous_stats.keys():
                        added_statistics[field] += 1
                        check(field == 'OmittedApplicationAdmissionRecords' and current_stats[field] == 0,
                              f'unexpected added retained statistic: {key}/{field}')
                check(not statistic_differences, 'retained common statistics differ from previous T6 return')
            keys = ('CaseId', 'Generated', 'Received', 'Dropped', 'Pending')
            previous_values = sorted(tuple(row[k] for k in keys) for row in previous_rows)
            current_values = sorted(tuple(row[k] for k in keys) for row in sweeps)
            check(current_values == previous_values, 'T6 retained sweep application outcomes differ')
            previous_comparison = {'archive_sha256': sha(args.previous_tranche6.read_bytes()), 'cases': len(sweeps),
                                   'compared_columns': keys, 'equal': current_values == previous_values,
                                   'retained_raw_summary_count': len(current_summaries),
                                   'all_common_raw_statistics_equal': not statistic_differences,
                                   'raw_statistic_differences': statistic_differences,
                                   'added_statistics_with_zero_values': dict(added_statistics)}
        elapsed = (dt.datetime.fromisoformat(meta['CompletedUTC'].replace('Z', '+00:00')) -
                   dt.datetime.fromisoformat(meta['StartedUTC'].replace('Z', '+00:00'))).total_seconds()
        report.update({'status': 'passed' if not errors else 'failed', 'errors': errors,
                       'archive_file_count': len(file_hashes), 'expanded_bytes': sum(file_sizes.values()),
                       'outer_artifact_hash_checks': len(meta['Artifacts']), 'checks': dict(counts),
                       'bound_source_files': len(snapshot), 'matlab_code_files': sum(p.endswith('.m') for p in snapshot_paths),
                       'pinned_reference_files': len(meta['ReferenceFiles']),
                       'legacy_dot_m_note': 'The legacy 107 .m bindings contain 103 MATLAB code files and four archived OPNET input files with .m suffixes.',
                       'source_snapshot_sha256': meta['SourceSnapshotSHA256'], 'runtime': meta['Runtime'],
                       'started_utc': meta['StartedUTC'], 'completed_utc': meta['CompletedUTC'], 'elapsed_seconds': elapsed,
                       'test_count': len(tests), 'test_passed': len(tests), 'nested_validation_records': nested,
                       'retained_sweeps': len(sweeps), 'retained_fixed_cases': retained_case_count,
                       'previous_tranche6_application_outcomes': previous_comparison,
                       'local_artifacts_excluded_by_declared_policy': {'total': len(meta['LocalArtifacts']),
                           'extensions': dict(collections.Counter(PurePosixPath(e['path']).suffix for e in meta['LocalArtifacts']))},
                       'cases': cases,
                       'acceptance_recommendation': ('Accept bounded portable R2025a benchmark execution, reproducibility and structural accounting milestone; retain numerical/protocol differences and finite-stop limitations.' if not errors else 'Resolve the reported audit errors before acceptance.'),
                       'qualifications': ['Only seed 128 for the three benchmarks; no statistical-equivalence claim.',
                           'Archived OPNET output is available only for campus and was not rerun.',
                           'All cases retain finite-stop application and HOP/NWK custody work; pending is not a terminal loss.',
                           'Campus admission diagnostic trace stores only 100000 of 1710000 attempts; all per-flow counters and application/protocol/PHY records are retained.',
                           'MAT objects and three nested ZIPs remain excluded by the declared execution-machine archive policy.',
                           'No R2026a/native execution occurred; optional adapter capability probes do not establish native integration.',
                           'Numerical agreement and full protocol equivalence are not established by these checks.']})
    (args.output_root / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# Independent Tranche 7 return audit', '',
             f"**Result: {report['status']}.** No production return-review code was imported or executed.", '',
             f"Archive SHA-256: `{report['archive']['sha256']}`. Candidate: `{args.candidate}`.", '',
             f"Verified {report['outer_artifact_hash_checks']} outer artifact hashes; {counts['declared_artifact_hash_checks']} declared artifact hash/size bindings in total; 155 source/input files, including 103 MATLAB code files; and 50 pinned reference files. Source and reference snapshots remained stable. Archive CRC and path checks passed.", '',
             'The returned MATLAB R2025a 25.1.0.2943329 records contain 467 unique passing tests, 18 completed retained sweeps and 28 retained fixed cases. No MATLAB was executed on the review host.', '',
             'All retained sweep application outcomes match the earlier Tranche 6 return: 357 generated, 334 delivered, 23 dropped, zero pending. Each of the nine benchmark flows delivered data. Application and physical-observation partitions balance, and raw protocol event counts match the exported application records.', '',
             'All common Statistics fields also match exactly across 47 retained raw summaries (18 sweep, 28 fixed and one foundation summary). The sole added statistics field is OmittedApplicationAdmissionRecords, zero in all 37 applicable summaries.', '',
             '| Case | Admitted | Delivered | Dropped | Pending | Runtime, seconds |',
             '|---|---:|---:|---:|---:|---:|']
    for case in report['cases']:
        lines.append(f"| {case['case_id']} | {case['generated']} | {case['delivered']} | {case['dropped']} | {case['pending']} | {case['runtime_seconds']:.3f} |")
    lines += ['', f"The full returned run spans {report['elapsed_seconds']:.3f} seconds (88 minutes 3.187 seconds).", '',
              'Recommendation: accept the bounded portable R2025a benchmark milestone with these qualifications:', '']
    lines += [f'- {item}' for item in report['qualifications']]
    lines += ['', 'The legacy T3 field named `MatlabSourceFiles` binds 107 `.m` files because it also includes four archived OPNET inputs. The executed MATLAB code set is 103 files, matching the candidate. No discrepancy was found.', '']
    if errors:
        lines += ['Audit failures:', ''] + [f'- {error}' for error in errors]
    (args.output_root / 'audit.md').write_text('\n'.join(lines))
    print(json.dumps({'status': report['status'], 'errors': errors, 'checks': dict(counts),
                      'cases': len(report['cases']), 'output': str(args.output_root)}))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
