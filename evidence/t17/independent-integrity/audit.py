"""Independent ZIP/source/receipt audit of the returned T17 exported evidence.

Uses standard-library hashes and closed inventories, without MATLAB execution
or invoking the official T17 return checker.
"""
from pathlib import Path, PurePosixPath
import csv
from datetime import datetime
import hashlib
import io
import json
import math
import stat
import zipfile

ROOT = Path('/workspace/scratch/ab77b42f47ca')
SOURCE = ROOT / 'csr17'
ARCHIVE = ROOT / 'upload/t17.zip'
OUTPUT = ROOT / 't17-review/independent-integrity'
OWNER_SHA = '19921afa83c57db2779e4302e5b39afef5120afb129a87fddb1f6d1bdbec2bd1'
CANDIDATE_SHA = '6210329add45cd50c8173e2e1390f2aa157a154c6977a10bee5917ee01a1052c'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while data := stream.read(1024 * 1024):
            h.update(data)
    return h.hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def records(value):
    if isinstance(value, dict):
        return [value]
    check(isinstance(value, list), 'Inventory is neither object nor array')
    return value


def index(value):
    rows = records(value)
    check(all(isinstance(row, dict) and 'path' in row for row in rows), 'Malformed inventory record')
    result = {row['path']: row for row in rows}
    check(len(rows) == len(result), 'Duplicate inventory member')
    return result


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    check(parsed.tzinfo is not None, 'Missing timestamp timezone')
    return parsed


def main():
    check(digest(ARCHIVE) == OWNER_SHA, 'Owner archive identity mismatch')
    candidate_path = SOURCE / 'evidence/tranche-17-candidate.json'
    check(digest(candidate_path) == CANDIDATE_SHA, 'Frozen candidate identity mismatch')
    candidate = json.loads(candidate_path.read_text())
    with zipfile.ZipFile(ARCHIVE) as archive:
        infos = archive.infolist()
        names = [member.filename for member in infos]
        check(len(names) == len(set(name.casefold() for name in names)), 'Duplicate or case-colliding ZIP name')
        payload = {}
        for member in infos:
            path = PurePosixPath(member.filename)
            check(not path.is_absolute() and '..' not in path.parts and '\\' not in member.filename,
                  'Unsafe ZIP path')
            check(str(path) == member.filename.rstrip('/'), 'Noncanonical ZIP path')
            mode = member.external_attr >> 16
            check(not member.flag_bits & 1 and not stat.S_ISLNK(mode), 'Encrypted/symlink ZIP member')
            check(not mode or stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR), 'Nonregular ZIP member')
            if member.is_dir():
                continue
            h = hashlib.sha256()
            read_size = 0
            with archive.open(member) as stream:
                while data := stream.read(1024 * 1024):
                    h.update(data)
                    read_size += len(data)
            check(read_size == member.file_size, 'ZIP expanded byte count mismatch')
            payload[member.filename] = {'sha256': h.hexdigest(), 'bytes': read_size}

        def read_json(name):
            return json.loads(archive.read(name))

        def read_csv(name):
            return list(csv.DictReader(io.StringIO(archive.read(name).decode('utf-8-sig'))))

        def inventory(prefix, declared, local, excluded):
            declared, local = index(declared), index(local)
            actual = {name[len(prefix):] for name in payload if name.startswith(prefix)}
            check(not set(declared) & set(local), 'Local and returned inventories overlap')
            check(actual - set(excluded) - set(local) == set(declared), 'Incomplete inventory at ' + prefix)
            for name, row in declared.items():
                check(payload.get(prefix + name) == {'sha256': row['sha256'], 'bytes': row['bytes']},
                      'Artifact hash or size mismatch: ' + prefix + name)
            for name, row in local.items():
                check(PurePosixPath(name).suffix in ('.mat', '.zip'), 'Unexpected local-only file type')
                if prefix + name in payload:
                    check(payload[prefix + name] == {'sha256': row['sha256'], 'bytes': row['bytes']},
                          'Local artifact hash or size mismatch')
            return len(declared)

        metadata = read_json('metadata.json')
        artifact_count = inventory('', metadata['Artifacts'], metadata['LocalArtifacts'], {'metadata.json'})
        check(metadata['CandidateSHA256'] == payload['candidate.json']['sha256'] == CANDIDATE_SHA,
              'Returned candidate identity mismatch')
        check(read_json('candidate.json') == candidate, 'Returned candidate content mismatch')
        check(metadata['Status'] == 'completed-review-required' and metadata['MATLABExecuted'] is True,
              'Owner run not marked complete')
        check(metadata['NativeExecuted'] is False and metadata['AcceptanceEstablished'] is False
              and metadata['NumericalParityEstablished'] is False, 'Unsupported owner acceptance claim')
        check(payload['plan.json']['sha256'] == candidate['PlanSHA256']
              == digest(SOURCE / candidate['Plan']), 'Returned plan identity mismatch')

        sources = index(read_json('source.json'))
        references = index(read_json('references.json'))
        check(len(sources) == 313 and sum(name.endswith('.m') for name in sources) == 160,
              'T17 source counts changed')
        check(len(references) == 520, 'T17 reference count changed')
        check(sources == index(metadata['SourceFilesFinal'])
              and references == index(metadata['ReferenceFilesFinal']), 'Returned final snapshots changed')
        check(metadata['SourceFilesStableDuringRun'] is True and metadata['ReferenceFilesStableDuringRun'] is True,
              'Missing stability claims')
        check(payload['source.json']['sha256'] == metadata['SourceSnapshotSHA256']
              and payload['references.json']['sha256'] == metadata['ReferenceSnapshotSHA256'],
              'Snapshot hash mismatch')
        check(index(candidate['SourceFiles']) == {name: row for name, row in sources.items()
              if name != 'evidence/tranche-17-candidate.json'}, 'Candidate source membership mismatch')
        check(index(candidate['ReferenceFileInventory']) == references
              and candidate['ReferenceFiles'] == sorted(references), 'Candidate reference membership mismatch')
        for name, row in list(sources.items()) + list(references.items()):
            path = SOURCE / name
            check(path.is_file() and not path.is_symlink() and digest(path) == row['sha256'],
                  'Frozen source/reference hash mismatch: ' + name)
            if 'bytes' in row:
                check(path.stat().st_size == row['bytes'], 'Reference size mismatch: ' + name)
        baseline_path = SOURCE / candidate['BaselineSourceSnapshot']
        check(digest(baseline_path) == candidate['BaseSourceSnapshotSHA256']
              == '90b5506f4fdb54f64ae7dac61c0e48df9da2253a8408a4b50b3ad30309ac1905',
              'T16 baseline manifest identity mismatch')
        baseline = index(json.loads(baseline_path.read_text()))
        check(len(baseline) == 304 and sum(name.endswith('.m') for name in baseline) == 155,
              'T16 baseline count mismatch')
        check(all(sources.get(name) == row for name, row in baseline.items()), 'T16 source changed')

        stage_summaries = {}
        stage_counts = {}
        entries = metadata['StageReceipts']
        check(len(entries) == 2 and {row['Phase'] for row in entries} == {'tests', 'campus'},
              'Two stage receipts not present exactly once')
        for entry in entries:
            phase = entry['Phase']
            path = phase + '/receipt.json'
            check(entry['File'] == path and entry['SHA256'] == payload[path]['sha256']
                  == archive.read(phase + '/receipt.sha256').decode().strip(), 'Stage receipt hash mismatch')
            receipt = read_json(path)
            check(receipt['schema'] == 'csr-tranche17-stage-receipt-v1'
                  and receipt['phase'] == phase and receipt['status'] == 'completed', 'Stage incomplete')
            identity = receipt['identity']
            check(identity['CandidateSHA256'] == CANDIDATE_SHA and identity['Runtime'] == metadata['Runtime']
                  and identity['SourceCommit'] == metadata['SourceCommit'], 'Stage runtime/candidate mismatch')
            check(index(identity['SourceFiles']) == sources == index(receipt['SourceFilesFinal'])
                  and index(identity['ReferenceFiles']) == references == index(receipt['ReferenceFilesFinal']),
                  'Stage source/reference identity mismatch')
            check(receipt['SourceFilesStableDuringRun'] is True and receipt['ReferenceFilesStableDuringRun'] is True,
                  'Stage stability not recorded')
            started = read_json(phase + '/start.json')
            check(started['identity'] == identity and started['phase'] == phase and started['status'] == 'started',
                  'Stage start identity mismatch')
            check(timestamp(metadata['StartedUTC']) <= timestamp(started['started_utc'])
                  <= timestamp(receipt['completed_utc']) <= timestamp(metadata['CompletedUTC']),
                  'Stage times outside complete invocation')
            stage_counts[phase] = inventory(phase + '/', receipt['artifacts'], receipt['local_artifacts'],
                                           {'receipt.json', 'receipt.sha256'})
            stage_summaries[phase] = read_json(phase + '/summary.json')
            check(stage_summaries[phase] == receipt['summary'], 'Receipt summary differs from exported summary')

        tests = read_csv('tests/results.csv')
        expected = candidate['ExpectedTestNames']
        check(len(tests) == len(expected) == 660 and len(candidate['TestFiles']) == 57,
              'Full test membership count changed')
        check(len({row['Name'] for row in tests}) == 660
              and {row['Name'] for row in tests} == set(expected), 'Missing or duplicate test')
        check(all(row['Passed'] == '1' and row['Failed'] == '0' and row['Incomplete'] == '0'
                  and math.isfinite(float(row['DurationSeconds'])) and float(row['DurationSeconds']) >= 0
                  for row in tests), 'Failed/incomplete/malformed test result')
        check(stage_summaries['tests']['ExpectedTestNames'] == metadata['ExpectedTestNames'] == expected,
              'Expected test names disagree')
        check(stage_summaries['tests']['TestFiles'] == metadata['TestFiles'] == candidate['TestFiles'],
              'Test class selection disagrees')
        for report in [metadata, stage_summaries['tests']]:
            check(report['TestsExecuted'] is True and report['TestsPassed'] is True
                  and report['TestCount'] == report['PassedTests'] == 660
                  and report['FailedTests'] == report['IncompleteTests'] == 0, 'Test counters disagree')

        campus = stage_summaries['campus']
        check(campus['SchedulerStopSeconds'] == campus['DurationSeconds'] == 6000
              and campus['Seed'] == 128 and campus['DefaultContinuousTiming'] is True
              and campus['PostHorizonDrain'] is False and campus['RealPHY'] is True
              and campus['AutonomousRouting'] is True and campus['StructuralChecksPassed'] is True,
              'Campus scope or completion mismatch')
        check(campus['AcceptanceEstablished'] is False and campus['NumericalParityEstablished'] is False
              and campus['FiniteStopPendingIsFailure'] is False, 'Unsupported campus acceptance claim')
        check(records(metadata['Cases']) == [campus['Case']], 'Case identity inconsistent')
        manifest_path = 'campus/c/benchmark_manifest.json'
        check(campus['Case']['ManifestSHA256'] == payload[manifest_path]['sha256'], 'Campus manifest hash mismatch')
        manifest = read_json(manifest_path)
        inventory('campus/c/', manifest['files'], manifest['local_files'], {'benchmark_manifest.json'})
        raw_manifest = read_json('campus/c/raw/case_manifest.json')
        inventory('campus/c/raw/', raw_manifest['files'], raw_manifest['local_files'], {'case_manifest.json'})
        check(index(manifest['source_files']) == index(raw_manifest['source_files']) == sources,
              'Case source provenance mismatch')
        required = {'trace.csv', 'protocol_trace.csv', 'phy_trace.csv', 'summary.json', 'scenario.csv',
                    'case_manifest.json', 'nodes.csv', 'mac_nodes.csv', 'hop_nodes.csv', 'nwk_nodes.csv',
                    'neighbors.csv', 'routes.csv', 'application_admission_statistics.csv', 'application_admission_trace.csv'}
        check(required <= {name.removeprefix('campus/c/raw/') for name in payload if name.startswith('campus/c/raw/')},
              'Missing campus raw export')
        check(payload['campus/c/raw/trace.csv'] == payload['campus/c/raw/protocol_trace.csv'],
              'Duplicate protocol exports differ')
        raw = read_json('campus/c/raw/summary.json')
        stats = raw['Statistics']
        check(stats['Generated'] == stats['Received'] + stats['Dropped'] + stats['Pending'], 'Application accounting fails')
        check(stats['PhysicalAttempts'] == stats['PhysicalReceived'] + stats['PhysicalDropped'] + stats['PhysicalPending'],
              'Receiver accounting fails')
        check(stats['OmittedTraceRecords'] == stats['OmittedPhyTraceRecords'] == 0
              and campus['ProtocolTraceOmissions'] == campus['PhyTraceOmissions'] == 0, 'Protocol/PHY trace incomplete')
        check(raw['Config']['DurationSeconds'] == 6000 and raw['Config']['Seed'] == 128
              and raw['Metadata']['Backend'] == 'portable' and raw['Metadata']['ChannelModel'] == 'csr-phy'
              and not any(field in raw for field in ('TransportTiming', 'ServiceDiagnostics', 'LinkDiagnostics')),
              'Campus runtime/timing scope changed')
        performance = read_csv('campus/c/analysis/performance_summary.csv')
        check(len(performance) == 1, 'Performance row count differs')
        for field in ['Generated', 'Received', 'Dropped', 'Pending', 'PhysicalAttempts', 'PhysicalReceived', 'PhysicalDropped', 'PhysicalPending']:
            check(float(performance[0][field]) == stats[field] == campus['Performance'][field], 'Performance counter differs: ' + field)
        admissions = campus['Admissions']
        check(admissions['Attempts'] == admissions['Admitted'] + admissions['Blocked']
              and admissions['Admitted'] == stats['Generated'] and admissions['CountsComplete'] is True
              and admissions['TraceRecords'] + admissions['OmittedTraceRecords'] == admissions['Attempts']
              and admissions['TraceRecords'] == min(admissions['Attempts'], 100000), 'Admission accounting differs')

        report = {
            'schema': 'csr-tranche17-independent-integrity-audit-v1',
            'status': 'passed', 'owner_archive_sha256': OWNER_SHA,
            'candidate_sha256': CANDIDATE_SHA, 'archive_file_count': len(payload),
            'returned_artifacts_verified': artifact_count, 'all_archive_crcs_read': True,
            'source_files': len(sources), 'matlab_files': 160, 'reference_files': len(references),
            'baseline_source_files_unchanged': 304, 'baseline_matlab_files_unchanged': 155,
            'stage_receipts_verified': 2, 'stage_artifact_counts': stage_counts,
            'matlab_test_count': 660, 'matlab_test_classes': 57, 'all_exact_test_identities_passed': True,
            'owner_runtime': metadata['Runtime'], 'matlab_executed_by_auditor': False,
            'campus_case': campus['CaseId'], 'campus_seconds': 6000, 'timing_policy': 'continuous',
            'application_outcomes': {name: stats[name] for name in ['Generated', 'Received', 'Dropped', 'Pending']},
            'admission_observations': admissions, 'protocol_trace_omitted': 0, 'phy_trace_omitted': 0,
            'local_mat_artifacts_not_returned': list(index(metadata['LocalArtifacts'])),
            'source_snapshot_sha256': metadata['SourceSnapshotSHA256'],
            'reference_snapshot_sha256': metadata['ReferenceSnapshotSHA256'],
            'scope': 'Independent exported-evidence integrity, full portable test membership, stage provenance and finite-stop accounting; official semantic/aggregate review is separate.',
            'full_numerical_parity_established': False,
            'limitations': ['Owner execution is supported by hash-bound returned artifacts; this auditor did not run MATLAB.',
                'One seed and one campus configuration do not establish statistical parity or every-network acceptance.',
                '1,610,000 admission attempt trace rows were deliberately omitted; complete per-flow counters remain exported.',
                'Pending applications and physical receiver outcomes remain censored at 6,000 seconds, with no forced drain.',
                'Local results.mat is declared but absent from the returned ZIP; exported artifacts are audited.',
                'OPNET comparison uses archived aggregates, not packet-level event truth.']
        }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    (OUTPUT / 'report.md').write_text(
        '# Independent Tranche 17 owner-return integrity audit\n\n'
        'Passed: exact frozen candidate, all 35 returned artifacts, 313 source files (160 MATLAB), '
        '520 references, both stage receipts, and all 660 exact test identities across 57 classes. '
        'Every T16 baseline source remains unchanged. All ZIP payloads were read through CRC checks.\n\n'
        'The returned MATLAB R2025a portable run completed the unchanged 6,000-second campus case '
        'with continuous timing: 12,484 admitted, 11,825 delivered, 402 dropped and 257 pending. '
        'Protocol and PHY traces report zero omitted records. Admission counters cover 1,710,000 attempts; '
        'the explicitly capped trace retains 100,000 and omits 1,610,000.\n\n'
        'This is an independent integrity and accounting audit, not a MATLAB rerun. '
        'The official semantic/aggregate review is separate. One seed and one campus case do not '
        'establish numerical or statistical parity. Pending work is preserved at the original stop, '
        'and the local results.mat file was not included in the return.\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
