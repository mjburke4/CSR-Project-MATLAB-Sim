#!/usr/bin/env python3
"""Bind the bounded T27 diagnostic to its unchanged accepted T25 baseline."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import analyze_tranche11_return as base

PIN = '486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b'
ENGINE = '6b5cd24ea80713ce16d88575869aedd6f432bdae'
CANDIDATE = 'evidence/tranche-27-candidate.json'
BASELINE = 'evidence/tranche-27-baseline.json'
PARENT = 'evidence/tranche-27-parent-candidate.json'
ACCEPTANCE = 'evidence/t27/baseline/t25-acceptance.json'
PLAN = 'evidence/tranche-27-plan.json'
NATIVE = 'evidence/tranche-27-native-reference'
TEST_FILES = ['tests/TestTranche27DiscoveryController.m', 'tests/TestNwkLayer.m',
              'tests/TestNeighbors.m', 'tests/TestRoutes.m']


def freeze(root):
    root = Path(root).resolve()
    baseline = base.json_value(root / BASELINE)
    base.require(base.sha256(root / BASELINE) ==
                 'a18437d84b4557a9b52c96ef6fb065b7904ec7a011c55debf2cc637541aa7376',
                 'Accepted T25 source snapshot identity changed')
    base.require(base.sha256(root / PARENT) ==
                 '3859ff6eaecd504b9c84f0030a97069a364a054063022c903cfdeabd47b02741',
                 'Accepted T25 candidate identity changed')
    base.require(base.sha256(root / ACCEPTANCE) ==
                 '4c0937d5a6387e5bed3e23920ca9889e32c6eca04f44c61a6cd96e59b068c80d',
                 'Accepted T25 review identity changed')
    base.require(len(baseline) == 420 and
                 sum(row['path'].endswith('.m') for row in baseline) == 186,
                 'Expected all 420 accepted source bindings, including 186 MATLAB files')
    for row in baseline:
        base.require(base.sha256(base.safe_path(root, row['path'])) == row['sha256'],
                     'Accepted source changed: ' + row['path'])
    parent = base.json_object(root / PARENT)
    references = set(parent['ReferenceFiles'])
    for row in parent['ReferenceFileInventory']:
        name = ('evidence/t27/baseline/parity-ledger.csv'
                if row['path'] == 'docs/parity-ledger.csv' else row['path'])
        path = base.safe_path(root, name)
        base.require(base.sha256(path) == row['sha256'] and path.stat().st_size == row['bytes'],
                     'Accepted reference changed: ' + row['path'])
    plan = base.json_object(root / PLAN)
    ids = ['C0', 'C1', 'C2', 'C3_match', 'C3_timeout']
    base.require([case['id'] for case in plan['cases']] == ids,
                 'Unexpected fixture membership')
    base.require(plan['fixture_count'] == 4 and plan['execution_count'] == 5,
                 'Unexpected fixture counts')
    base.require(sum(len(case['checkpoints_s']) for case in plan['cases']) == 44,
                 'Unexpected checkpoint membership')
    main = base.json_object(root / 'evidence/tranche-27-main-check.json')
    base.require(main['commit'] == PIN and main['source_main_unchanged'] is True,
                 'Native source pin changed')
    native_files = [p for p in (root / NATIVE).rglob('*') if p.is_file()]
    base.require(native_files, 'Native references must be prepared before freezing')
    native_summary = base.json_object(root / NATIVE / 'summary.json')
    base.require(native_summary.get('status') == 'passed'
                 and native_summary.get('source_pin') == PIN
                 and native_summary.get('engine_pin') == ENGINE
                 and native_summary.get('native_executed') is True
                 and native_summary.get('matlab_executed') is False
                 and native_summary.get('observer_on_off_identical') is True
                 and native_summary.get('production_source_unchanged') is True
                 and native_summary.get('engine_source_unchanged') is True
                 and native_summary.get('case_ids') == ids
                 and native_summary.get('plan_sha256') == base.sha256(root / PLAN),
                 'Native fixture preparation is incomplete or has a different identity')
    native_manifest = base.json_object(root / NATIVE / 'manifest.json')
    native_names = {p.relative_to(root / NATIVE).as_posix() for p in native_files}
    base.require(set(native_manifest['files']) == native_names - {'manifest.json'},
                 'Native reference manifest is not closed')
    for name, digest in native_manifest['files'].items():
        base.require(base.sha256(base.safe_path(root / NATIVE, name)) == digest,
                     'Native reference changed: ' + name)
    references.update([BASELINE, PARENT, PLAN, 'evidence/tranche-27-main-check.json',
                       'T27.md', 'docs/T27-Holistic-Review.md', 'AGENTS.md'])
    for folder in ('evidence/t27', NATIVE):
        references.update(p.relative_to(root).as_posix() for p in (root / folder).rglob('*')
                          if p.is_file() and not any(part.startswith('.') or part == '__pycache__'
                                                    for part in p.relative_to(root / folder).parts))
    inventory = [{'path': name, 'sha256': base.sha256(root / name),
                  'bytes': (root / name).stat().st_size} for name in sorted(references)]
    sources = base.candidate_snapshot(root)
    sources.pop(CANDIDATE, None)
    names = base.selected_test_names(root, TEST_FILES)
    candidate = {
        'Schema': 'csr-tranche-27-candidate-v1', 'Tranche': 27,
        'Status': 'native_references_verified_matlab_execution_pending',
        'CreatedUTC': datetime.now(timezone.utc).isoformat(),
        'Objective': 'Resolve four bounded discovery-controller questions, then fix a concrete defect or freeze the scoped portable baseline.',
        'SourceCommit': PIN, 'EngineCommit': ENGINE,
        'SourceMainInspection': 'evidence/tranche-27-main-check.json',
        'BaseInstallation': 'Copy the accepted T25 installation and overlay t27up.zip. T26 is an offline review.',
        'BaselineSourceSnapshot': BASELINE, 'BaseSourceSnapshotSHA256': base.sha256(root / BASELINE),
        'BaselineSourceFiles': 420, 'BaselineMatlabFiles': 186,
        'BaselineCandidate': PARENT, 'BaselineCandidateSHA256': base.sha256(root / PARENT),
        'BaselineAcceptance': ACCEPTANCE, 'BaselineAcceptanceSHA256': base.sha256(root / ACCEPTANCE),
        'AllowedModifiedSourceFiles': [], 'AllBaselineSourcesUnchanged': True,
        'AllowedModifiedReferenceFiles': ['docs/parity-ledger.csv'],
        'PreservedBaselineLedger': 'evidence/t27/baseline/parity-ledger.csv',
        'SourceFilesExcludedPaths': [CANDIDATE],
        'SourceFiles': [{'path': name, 'sha256': digest} for name, digest in sorted(sources.items())],
        'ReferenceRoots': [], 'ReferenceFiles': sorted(references), 'ReferenceFileInventory': inventory,
        'Plan': PLAN, 'PlanSHA256': base.sha256(root / PLAN), 'NativeReferenceRoot': NATIVE,
        'TestFiles': TEST_FILES, 'ExpectedTestNames': names, 'ExpectedTestCount': len(names),
        'ExactExecutableCaseIDs': ids, 'ExpectedCaseCount': 5, 'ConceptualCaseCount': 4,
        'ExpectedCheckpointCount': 44, 'WorkingCampusBandPercent': 10,
        'FullPortableRegression': False, 'FullCampusRun': False,
        'PlannedSimulatedSeconds': sum(case['stop_s'] for case in plan['cases']),
        'DataQueuedRetryPolicy': 'actual-tx', 'TimingPolicy': 'continuous',
        'ProductionSourceChanged': False, 'PHYExecuted': False,
        'PHY_ECC_Changed': False, 'PHY_ECCChanged': False,
        'MATLABExecuted': False, 'MATLABExecutionPending': True, 'NativeExecuted': True,
        'NativeReferencePreparationCompleted': True, 'AcceptanceEstablished': False,
        'NumericalParityEstablished': False, 'DiagnosticOnly': True,
        'StopRule': 'Review the four fixtures; fix a concrete defect or freeze a scoped baseline. No automatic campus rerun or additional seed.'}
    (root / CANDIDATE).write_text(json.dumps(candidate, indent=2) + '\n')
    return {'candidate_sha256': base.sha256(root / CANDIDATE),
            'source_bindings': len(sources) + 1,
            'matlab_files': sum(name.endswith('.m') for name in sources),
            'reference_bindings': len(inventory), 'focused_test_count': len(names),
            'fixture_count': 4, 'execution_count': 5, 'checkpoint_count': 44,
            'matlab_execution_pending': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(freeze(args.source_root)))
