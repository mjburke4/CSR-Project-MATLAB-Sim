"""Independent inventory and per-case evidence checks; no MATLAB execution."""
import argparse
import csv
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import zipfile

def digest(data):
    return hashlib.sha256(data).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    candidate = args.source_root / 'evidence/tranche-14-candidate.json'
    assert digest(candidate.read_bytes()) == '4bb51710031ead9d8d7c6b718fb41fd9224156b46076111e4e9c161aebbcc69f'
    with zipfile.ZipFile(args.evidence) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names)) == 54
        assert archive.testzip() is None
        load = lambda name: json.loads(archive.read(name))
        rows = lambda name: list(csv.DictReader(io.StringIO(archive.read(name).decode('utf-8-sig'))))
        meta = load('metadata.json')
        artifacts = {row['path']: row for row in meta['Artifacts']}
        assert len(artifacts) == len(meta['Artifacts']) == 53
        assert set(artifacts) | {'metadata.json'} == set(names)
        for name, row in artifacts.items():
            data = archive.read(name)
            assert len(data) == row['bytes'] and digest(data) == row['sha256'], name
        source, refs = load('source.json'), load('references.json')
        assert source == meta['SourceFilesFinal'] and refs == meta['ReferenceFilesFinal']
        assert digest(archive.read('source.json')) == meta['SourceSnapshotSHA256']
        assert digest(archive.read('references.json')) == meta['ReferenceSnapshotSHA256']
        for row in source + refs:
            data = (args.source_root / row['path']).read_bytes()
            assert digest(data) == row['sha256'], row['path']
            if 'bytes' in row:
                assert len(data) == row['bytes']
        source_names = {row['path'] for row in source}
        assert len(source_names) == len(source) == 285
        assert sum(name.endswith('.m') for name in source_names) == 144
        assert len({row['path'] for row in refs}) == len(refs) == 317
        baseline = json.loads((args.source_root / 'evidence/t13/source.json').read_text())
        source_hashes = {row['path']: row['sha256'] for row in source}
        assert len(baseline) == 271 and sum(row['path'].endswith('.m') for row in baseline) == 138
        assert all(source_hashes[row['path']] == row['sha256'] for row in baseline)
        tests = rows('tests.csv')
        expected = json.loads(candidate.read_text())['ExpectedTestNames']
        assert len(tests) == len(expected) == 109
        assert [r['Name'] for r in tests] == expected
        assert all(r['Passed'] == '1' and r['Failed'] == r['Incomplete'] == '0' for r in tests)
        summary = load('edge/summary.json')
        cases = ['tie_early', 'tie_late', 'before', 'after', 'continuous', 'quantized']
        assert [r['Case'] for r in summary['CaseResults']] == cases
        assembled = {n: [] for n in ['events', 'boundary', 'check', 'draws', 'usage', 'scheduler']}
        per_case = []
        for index, (case, result) in enumerate(zip(cases, summary['CaseResults']), 1):
            prefix = f'edge/c{index}'
            assert load(prefix + '/result.json') == result
            assert result['Completed'] and result['Passed'] and result['CheckpointCount'] == 37
            counts = {}
            for name in assembled:
                values = rows(f'{prefix}/{name}.csv')
                assert values and all(row['case'] == case for row in values)
                assembled[name].extend(values)
                counts[name] = len(values)
            per_case.append({'case': case, 'folder': f'c{index}', 'rows': counts})
        for name, values in assembled.items():
            assert values == rows(f'edge/{name}.csv'), name
        assert len(assembled['check']) == 222
        assert all(row['pass'] == '1' for row in assembled['check'])
        elapsed = (datetime.fromisoformat(meta['CompletedUTC'].replace('Z', '+00:00')) -
                   datetime.fromisoformat(meta['StartedUTC'].replace('Z', '+00:00'))).total_seconds()
        output = {
            'schema': 'csr-tranche14-r2-owner-supplemental-audit-v1', 'status': 'passed',
            'matlab_executed_by_reviewer': False,
            'owner_archive_sha256': digest(args.evidence.read_bytes()),
            'candidate_sha256': digest(candidate.read_bytes()),
            'members': 54, 'artifact_hashes_and_sizes_verified': 53,
            'source_files_verified': 285, 'matlab_files_verified': 144,
            'reference_files_verified': 317, 'source_and_references_stable': True,
            't13_source_files_unchanged': 271, 't13_matlab_files_unchanged': 138,
            'tests_passed': 109, 'tests_failed': 0, 'tests_incomplete': 0,
            'checkpoints_passed': 222, 'per_case_files_verified': 42,
            'per_case_results_match_summary': True,
            'per_case_tables_reconstruct_all_six_aggregate_tables': True,
            'owner_elapsed_seconds': elapsed, 'case_artifacts': per_case,
            'audit_script_sha256': digest(Path(__file__).read_bytes()),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, indent=2) + '\n')
        print(json.dumps({k:v for k,v in output.items() if k != 'case_artifacts'}, indent=2))

if __name__ == '__main__':
    main()
