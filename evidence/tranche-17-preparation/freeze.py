#!/usr/bin/env python3
"""Freeze the prepared T17 candidate; does not execute MATLAB or accept results."""
from pathlib import Path
import hashlib
import json
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from analyze_tranche11_return import candidate_snapshot, selected_test_names

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')

def main():
    rel = 'evidence/tranche-17-candidate.json'
    base = json.loads((ROOT / 'evidence/tranche-17-baseline.json').read_text())
    assert len(base) == 304 and sum(row['path'].endswith('.m') for row in base) == 155
    assert all(sha(ROOT / row['path']) == row['sha256'] for row in base)
    previous = json.loads((ROOT / 'evidence/tranche-16-candidate.json').read_text())
    references = set(previous['ReferenceFiles'])
    for directory in ('evidence/tranche-7-ns3-reference', 'evidence/tranche-7-benchmark-inputs', 'evidence/t16'):
        references.update(path.relative_to(ROOT).as_posix() for path in (ROOT/directory).rglob('*') if path.is_file())
    references.update(('evidence/tranche-17-baseline.json', 'evidence/tranche-17-main-check.json',
        'evidence/tranche-1-ns3-reference.json', 'scenarios/t17/plan.json',
        'evidence/tranche-7-r2025a-accepted/benchmarks/campus_multihop_6000/raw/summary.json'))
    references = sorted(references)
    assert rel not in references
    inventory = [{'path': name, 'sha256': sha(ROOT/name), 'bytes': (ROOT/name).stat().st_size} for name in references]
    sources = candidate_snapshot(ROOT)
    sources.pop(rel, None)
    tests = sorted(path.relative_to(ROOT).as_posix() for path in (ROOT/'tests').glob('Test*.m'))
    methods = selected_test_names(ROOT, tests)
    candidate = {
        'Schema': 'csr-tranche-17-candidate-v1', 'Tranche': 17,
        'Status': 'full_portable_regression_and_campus_matlab_execution_pending',
        'CreatedUTC': datetime.now(timezone.utc).isoformat(),
        'Objective': 'Full portable regression and one unchanged 6000-second campus release gate on reviewed T16 source.',
        'SourceCommit': '486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b',
        'EngineCommit': '6b5cd24ea80713ce16d88575869aedd6f432bdae',
        'SourceMainInspection': 'evidence/tranche-17-main-check.json',
        'BaseInstallation': 'Copy the exact reviewed Tranche 16 installation and overlay every t17up.zip file at its root.',
        'BaseCandidateSHA256': sha(ROOT/'evidence/tranche-16-candidate.json'),
        'BaselineSourceSnapshot': 'evidence/tranche-17-baseline.json',
        'BaseSourceSnapshotSHA256': sha(ROOT/'evidence/tranche-17-baseline.json'),
        'BaselineOwnerEvidence': 'evidence/t16/owner.zip',
        'BaselineOwnerEvidenceSHA256': sha(ROOT/'evidence/t16/owner.zip'),
        'BaselineCandidate': 'evidence/t16/candidate.json',
        'BaselineCandidateSHA256': sha(ROOT/'evidence/t16/candidate.json'),
        'AllowedModifiedSourceFiles': [], 'BaselineSourceFiles': 304, 'BaselineMatlabFiles': 155,
        'BaselineSourceFilesUnchanged': 304, 'BaselineMatlabFilesUnchanged': 155,
        'SourceFilesExcludedPaths': [rel],
        'SourceFiles': [{'path': name, 'sha256': digest} for name, digest in sorted(sources.items())],
        'TestFiles': tests, 'ExpectedTestNames': methods, 'PreparedMatlabTestCount': len(methods),
        'Plan': 'scenarios/t17/plan.json', 'PlanSHA256': sha(ROOT/'scenarios/t17/plan.json'),
        'ReferenceRoots': [], 'ReferenceFiles': references, 'ReferenceFileInventory': inventory,
        'MATLABExecutedHere': False, 'NativeExecutedHere': False,
        'FullAcceptanceEstablished': False, 'NumericalParityEstablished': False,
        'NativeReferenceReused': True, 'DefaultTimingPolicy': 'continuous',
        'ProductionBehaviorChanged': False, 'SourcePolicy': 'Every T16 source binding is preserved byte for byte.',
        'Scope': 'All top-level portable tests plus original campus_multihop_6000, seed128, realPHY, 6000s; no native MATLAB tests or forced drain.'
    }
    write(ROOT/rel, candidate)
    print(json.dumps({'candidate_sha256': sha(ROOT/rel), 'source_files_including_candidate': len(sources)+1,
        'matlab_files': sum(name.endswith('.m') for name in sources), 'test_classes': len(tests),
        'prepared_matlab_tests': len(methods), 'reference_files': len(references),
        'baseline_source_files_unchanged': 304, 'matlab_executed': False}, indent=2))

if __name__ == '__main__':
    main()
