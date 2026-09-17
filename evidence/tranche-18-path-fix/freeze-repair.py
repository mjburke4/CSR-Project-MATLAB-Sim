#!/usr/bin/env python3
"""Refreeze only the confirmed T18 recipe-path predicate repair."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'scripts'))
from analyze_tranche11_return import candidate_snapshot, selected_test_names

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    prior = json.loads((HERE / 'original-candidate.json').read_text())
    assert sha(HERE / 'original-candidate.json') == '582802501a94338cc3e70e1cb79d7f66f9b83aa6fcc5dc10508003a7d1f4d892'
    baseline = json.loads((ROOT / 'evidence/tranche-18-baseline.json').read_text())
    assert len(baseline) == 313 and all(sha(ROOT / row['path']) == row['sha256'] for row in baseline)
    candidate_path = 'evidence/tranche-18-candidate.json'
    source = candidate_snapshot(ROOT)
    source.pop(candidate_path)
    previous = {row['path']: row['sha256'] for row in prior['SourceFiles']}
    assert set(previous) == set(source)
    changed = sorted(name for name in source if source[name] != previous[name])
    assert changed == ['+csr/+scenario/tranche18Suite.m'], changed
    for row in prior['ReferenceFileInventory']:
        path = ROOT / row['path']
        assert path.stat().st_size == row['bytes'] and sha(path) == row['sha256'], row['path']
    assert selected_test_names(ROOT, prior['TestFiles']) == prior['ExpectedTestNames']
    additions = ['original-candidate.json', 'original-package.json', 'original-suite.m',
                 'owner-failed.zip', 'failure-review.json']
    names = sorted(set(prior['ReferenceFiles']) | {
        (HERE / name).relative_to(ROOT).as_posix() for name in additions})
    candidate = dict(prior)
    candidate.update(
        CreatedUTC=datetime.now(timezone.utc).isoformat(),
        Revision=2,
        Status='relay_service_diagnostic_path_repaired_matlab_execution_pending',
        SupersedesCandidateSHA256=sha(HERE / 'original-candidate.json'),
        RepairScope='Exact shipped recipe/scenario/reference path equality; no simulation behavior change.',
        RepairChangedSourceFiles=changed,
        NativeReferenceReexecutedForRepair=False,
        SourceFiles=[{'path': name, 'sha256': value} for name, value in sorted(source.items())],
        ReferenceFiles=names,
        ReferenceFileInventory=[{'path': name, 'sha256': sha(ROOT / name),
                                 'bytes': (ROOT / name).stat().st_size} for name in names])
    (ROOT / candidate_path).write_text(json.dumps(candidate, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'candidate_sha256': sha(ROOT / candidate_path),
        'changed_source_files': changed, 'source_files': len(source)+1,
        'reference_files': len(names), 'baseline_sources_unchanged': len(baseline),
        'prepared_matlab_tests': len(prior['ExpectedTestNames'])}, indent=2))

if __name__ == '__main__':
    main()
