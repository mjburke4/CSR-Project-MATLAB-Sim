#!/usr/bin/env python3
"""Review complete T25 full-campus multi-seed evidence without executing MATLAB.

Structural completeness, preserved default behavior and evidence identities are
gates. Numerical 10% bands remain descriptive, including cases outside the band.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import gzip
import math
import re
from collections import defaultdict
import json
from pathlib import Path
import zipfile

from analyze_tranche11_return import (all_files, candidate_snapshot, csv_rows,
    json_object, json_value, logical, number, record_map, records, require,
    safe_path, sha256, verify_sources)
import analyze_tranche7_return as t7
import analyze_tranche17_return as t17
import analyze_research_sweep as sweep
import compare_benchmark_aggregates as aggregate
import tranche10_metrics as retained
import tranche19_metrics as metrics
import tranche25_metrics as multi

integer = metrics.integer
SCHEMA = 'csr-matlab-tranche-25-validation-v1'
REVIEW_SCHEMA = 'csr-matlab-tranche-25-return-review-v1'
CANDIDATE = 'evidence/tranche-25-candidate.json'
BASELINE = 'evidence/tranche-25-baseline.json'
BASELINE_SHA = 'ff654a8774b23965b2d8a45866a807cdc88a31594920542c60536a4fcf5b7364'
PARENT_OWNER_SHA = '569cf1bbd7ca31e90518128d32dfd7a51c2f94b15e1ec5c5131aa1d5a426804c'
PARENT_CANDIDATE_SHA = 'b40afd3755ceb47576ea2c9854b4af15a14cebcf87024331e67bf53e069f0818'
PARENT_ACCEPTANCE_SHA = '3ef62d8fbb8a59fd496b36d4b69978647324e643d99b361a1342340f1f9af43f'
PLAN = 'scenarios/t25/plan.json'
REUSED = 'evidence/t25/reused-campus.json'
PARENT_CANDIDATE = 'evidence/tranche-25-parent-candidate.json'
PARENT_ACCEPTANCE = 'evidence/t23/acceptance.json'
NATIVE = 'evidence/tranche-7-ns3-reference/campus_multihop_6000'
PHASES = ('tests','s131','s132')
CORE_CSV = ('trace.csv','protocol_trace.csv','phy_trace.csv','nodes.csv','mac_nodes.csv','hop_nodes.csv',
    'nwk_nodes.csv','neighbors.csv','routes.csv','application_admission_statistics.csv','application_admission_trace.csv','scenario.csv')
LIMITATIONS = [
    'Hashes bind owner evidence claims; they do not independently prove MATLAB execution.',
    'Five seeds are a small exploratory ensemble, not statistical equivalence or a numerical acceptance test.',
    'Accepted seeds128 through130 retain original source/runtime identity; only seeds131 and132 execute under T25.',
    'Engine random streams are not common random numbers; seed labels do not pair packets or bootstrap samples.',
    'Complete counters cover1710000 attempts per run; only the original100000 admission-attempt prefix is retained.',
    'Native unmatched sends do not separate dropped and pending applications.',
    'Delivered delay excludes packets not delivered by6000seconds. Pooled weighted delay is separate from run-mean delay.',
    'The10% band is descriptive, never a structural gate. OPNET has no matched additional seeds.'
]


def verify_reused(source_root):
    reused = json_object(source_root/REUSED)
    require(reused.get('schema') == 'csr-tranche25-reused-campus-v1' and reused.get('seeds') == list(multi.REUSED_SEEDS),
            'Reused campus identity/seeds differ')
    cases = records(reused.get('cases'), 'reused campus cases')
    require([row.get('seed') for row in cases] == list(multi.REUSED_SEEDS) and
            [row.get('case_id') for row in cases] == ['a128', 's129', 's130'], 'Reused case population/order differs')
    for row in cases:
        require(row.get('fresh_execution') is False and row.get('policy') == 'actual-tx'
                and row.get('duration_s') == 6000 and row.get('scenario_sha256') == sha256(source_root/'scenarios/benchmarks/campus_multihop_6000.csv'),
                'Reused case scope differs')
        for stem in ('owner', 'candidate', 'acceptance', 'source_snapshot'):
            require(sha256(safe_path(source_root, row[stem+'_file'])) == row[stem+'_sha256'], 'Reused '+stem+' identity differs')
        snapshot = record_map(json_value(source_root/row['source_snapshot_file']), 'reused source snapshot')
        for name, binding in snapshot.items():
            require(sha256(safe_path(source_root, name)) == binding['sha256'], 'Reused historical source changed: '+name)
        accepted = json_object(source_root/row['acceptance_file'])
        require(accepted.get('status') in ('accepted_for_portable_regression_and_policy_experiment',
                                         'accepted_for_portable_regression_and_multi_seed_campus_validation'),
                'Reused case is not an accepted original result')
        require(accepted.get('owner_evidence_sha256', accepted.get('owner_archive_sha256')) == row['owner_sha256'] and
                accepted.get('candidate_sha256') == row['candidate_sha256'] and
                accepted.get('source_snapshot_sha256') == row['source_snapshot_sha256'] and
                accepted.get('runtime') == row['runtime'] and accepted.get('numerical_parity_established', accepted.get('numerical_equivalence_established')) is False,
                'Reused acceptance bindings/flags differ')
        with zipfile.ZipFile(source_root/row['owner_file']) as archive:
            meta = json.loads(archive.read('metadata.json'))
            require(meta.get('Status') == 'completed-review-required' and meta.get('TestsPassed') is True
                    and meta.get('Runtime') == row['runtime'] and meta.get('CandidateSHA256') == row['candidate_sha256']
                    and hashlib.sha256(archive.read('source.json')).hexdigest() == row['source_snapshot_sha256'],
                    'Reused original owner metadata differs')
            config = json.loads(archive.read(row['case_id']+'/raw/summary.json'))['Config']
            require(config.get('Seed') == row['seed'] and config.get('Hop', {}).get('DataQueuedRetryPolicy') == 'actual-tx',
                    'Reused seed/default differs')
            _equal_normalized(reused_matlab_metrics(archive, row['case_id']), row['matlab'], 'Reused MATLAB')
        reference = NATIVE if row['seed'] == 128 else f"evidence/tranche-20-ns3-reference/s{row['seed']}"
        require(row.get('ns3_reference_directory', reference) == reference, 'Reused native reference changed')
        _equal_normalized(reused_native_metrics(source_root/reference), row['ns3'], 'Reused native')
    return reused


def reused_report_rows(reused, runtime):
    mapping = {'CaseId': 'case_id', 'Seed': 'seed', 'Policy': 'policy', 'DurationSeconds': 'duration_s',
        'ScenarioSHA256': 'scenario_sha256', 'OwnerFile': 'owner_file', 'OwnerSHA256': 'owner_sha256',
        'CandidateFile': 'candidate_file', 'CandidateSHA256': 'candidate_sha256',
        'AcceptanceFile': 'acceptance_file', 'AcceptanceSHA256': 'acceptance_sha256',
        'SourceSnapshotFile': 'source_snapshot_file', 'SourceSnapshotSHA256': 'source_snapshot_sha256', 'Runtime': 'runtime'}
    return [dict({key: row[value] for key, value in mapping.items()},
                 RuntimeMatchesCurrent=row['runtime'] == runtime, SourceBindingsUnchanged=True, FreshlyExecuted=False)
            for row in reused['cases']]


def reused_native_metrics(directory):
    """First unique delivery by native's own source/sequence identity, no joins to MATLAB."""
    sent, delivered = {}, set()
    delays = defaultdict(list)
    previous = -1.0
    with gzip.open(directory/'ns3-trace.csv.gz', 'rt', encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream, strict=True):
            when = metrics.finite(row['time_s'], 'native time')
            require(previous <= when <= 6000 and when >= 0, 'Reused native event order/window differs')
            previous = when
            if row['event'] not in ('app_send', 'nwk_delivery'): continue
            source = metrics.integer(row['src'], 'source')
            identity = source, metrics.integer(row['sequence'], 'sequence')
            require(source in multi.SOURCES, 'Unexpected native source')
            if row['event'] == 'app_send':
                require(identity not in sent and when < 6000, 'Repeated native generation or outside window')
                sent[identity] = when
            else:
                require(identity in sent and when >= sent[identity], 'Native delivery has no source generation')
                if identity not in delivered:
                    delivered.add(identity); delays[source].append(when-sent[identity])
    flows = []
    for row in metrics.rows(directory/'app-admission-diagnostics.csv', ('source', 'attempts', 'admitted')):
        source = metrics.integer(row['source'], 'source')
        admitted = sum(identity[0] == source for identity in sent)
        require(admitted == metrics.integer(row['admitted'], 'native admitted'), 'Native admitted diagnostics differ')
        ds = delays[source]
        flows.append({'source': source, 'admitted': admitted, 'delivered': len(ds),
                      'first_delivery_delay_s': {'count': len(ds), 'mean': math.fsum(ds)/len(ds) if ds else None,
                                                 'sum_s': math.fsum(ds)}})
    return multi.normalize_native({'flows': flows, 'totals': {'admitted': len(sent), 'delivered': len(delivered)}})


def reused_matlab_metrics(archive, key):
    """Reconstruct accepted archival application outcomes, preserving original bytes."""
    sent, delivered, delays = defaultdict(int), defaultdict(int), defaultdict(list)
    seen = set()
    with archive.open(f'{key}/analysis/applications.csv') as binary:
        rows = csv.DictReader(io.TextIOWrapper(binary, encoding='utf-8-sig', newline=''), strict=True)
        for row in rows:
            identity = metrics.integer(row['PacketId'], 'application id', 1)
            require(identity not in seen, 'Reused application identity repeated')
            seen.add(identity)
            source = metrics.integer(row['SourceId'], 'source')
            require(source in multi.SOURCES, 'Unknown reused application source')
            generated = metrics.finite(row['GeneratedSeconds'], 'generated time')
            last = metrics.finite(row['LastEventSeconds'], 'last application time')
            require(0 <= generated < 6000 and generated <= last <= 6000, 'Reused application outside horizon')
            sent[source] += 1
            require(row['Outcome'] in ('delivered', 'dropped', 'pending'), 'Unknown reused application outcome')
            if row['Outcome'] == 'delivered':
                received = metrics.finite(row['ReceivedSeconds'], 'received time')
                delay = metrics.finite(row['LatencySeconds'], 'conditional delay')
                require(generated <= received <= 6000 and math.isclose(delay, received-generated, rel_tol=2e-12, abs_tol=1e-9),
                        'Reused delay disagrees with delivery timestamps')
                delivered[source] += 1; delays[source].append(delay)
            else:
                require(row['ReceivedSeconds'].lower() in ('', 'nan') and row['LatencySeconds'].lower() in ('', 'nan'),
                        'Reused undelivered application has delivery delay')
    observations = {'totals': {'admitted': sum(sent.values()), 'delivered': sum(delivered.values())},
        'flows': [{'source': source, 'admitted': sent[source], 'delivered': delivered[source],
                   'delivered_latency': metrics.distribution(delays[source])} for source in multi.SOURCES]}
    raw = json.loads(archive.read(f'{key}/raw/summary.json'))
    require(raw['Statistics']['Generated'] == observations['totals']['admitted'] and
            raw['Statistics']['Received'] == observations['totals']['delivered'],
            'Reused outcomes disagree with accepted raw counters')
    return multi.normalize_matlab(observations)


def _equal_normalized(actual, expected, label):
    multi.validate_run(actual); multi.validate_run(expected)
    am = {row['source']: row for row in actual['flows']}; em = {row['source']: row for row in expected['flows']}
    for a, e in [(actual['totals'], expected['totals']), *[(am[source], em[source]) for source in multi.SOURCES]]:
        for key in ('admitted', 'unique_delivered', 'delivered_delay_count'):
            require(a[key] == e[key], label+' normalized count differs: '+key)
        for key in ('mean_delivered_delay_s', 'delivered_delay_sum_s'):
            require((a[key] is None and e[key] is None) or
                    (a[key] is not None and e[key] is not None and math.isclose(a[key], e[key], rel_tol=1e-12, abs_tol=1e-8)),
                    label+' normalized conditional delay differs: '+key)


def selected_test_names(source_root, files):
    """Parse class test-method blocks, stopping before same-indent end/local code."""
    require(isinstance(files, list) and files == sorted(set(files)) and files, 'Invalid portable test selection')
    source_root = Path(source_root).resolve()
    names = []
    for name in files:
        path = safe_path(source_root, name)
        require(path.parent == Path(source_root)/'tests' and path.suffix == '.m' and path.stem.startswith('Test'),
                'Unsupported portable test file')
        code = path.read_text(encoding='utf-8')
        found = []
        for block in re.finditer(r'^    methods\s*\(([^)]*)\)(.*?)(?=^    end\s*$)', code, re.M|re.S):
            if re.search(r'\bTest\b', block[1]):
                found.extend(f'{path.stem}/{method}' for method in re.findall(r'^        function\s+(\w+)\s*\(', block[2], re.M))
        require(found and len(found) == len(set(found)), 'Missing/duplicate MATLAB test method: '+name)
        names.extend(found)
    require(len(names) == len(set(names)), 'Duplicate portable test identity')
    return names


def inventory(root, raw, label, *, excluded=(), local=()):
    """Closed inventory with scalar-struct and scientific integer support."""
    root = Path(root)
    found = record_map(raw,label,sizes=True,empty=True)
    raw_rows = {row['path']:row for row in records(raw,label,empty=True)}
    for name,item in found.items():
        path = safe_path(root,name)
        require(path.is_file() and path.stat().st_size == item['bytes'] and sha256(path) == item['sha256'],
                'Artifact hash/size mismatch: '+name)
        count = raw_rows[name].get('row_count')
        if count not in (None,[]):
            require(path.suffix == '.csv' and sum(1 for _ in metrics.rows(path)) == integer(count,'CSV row count'),
                    'Artifact CSV row count mismatch: '+name)
    local_items = record_map(local or [],label+' local',sizes=True,empty=True)
    require(not (set(found) & set(local_items)), 'Artifact present in both carried and local inventories')
    for name,item in local_items.items():
        path = safe_path(root,name)
        require(path.suffix in ('.mat','.zip'), 'Invalid omitted local-only artifact')
        if path.exists():
            require(path.is_file() and path.stat().st_size == item['bytes'] and sha256(path) == item['sha256'],
                    'Local artifact hash/size mismatch: '+name)
    require(all_files(root)-set(excluded)-set(local_items) == set(found), 'Incomplete '+label+' inventory')
    return found


def verify_baseline(source_root, candidate, metadata=None):
    require(candidate.get('BaselineSourceSnapshot') == BASELINE and
            candidate.get('BaseSourceSnapshotSHA256') == sha256(source_root/BASELINE) == BASELINE_SHA,
            'Accepted T23 source snapshot mismatch')
    baseline = record_map(json_value(source_root/BASELINE), 'T23 baseline')
    require(len(baseline) == 404 and sum(name.endswith('.m') for name in baseline) == 181,
            'T23 baseline membership mismatch')
    require(candidate.get('AllowedModifiedSourceFiles') == [], 'T25 permits no baseline source changes')
    for name, row in baseline.items():
        require(sha256(safe_path(source_root, name)) == row['sha256'], 'Accepted T23 source changed: '+name)
    require(candidate.get('BaselineSourceFiles') == 404 and candidate.get('BaselineMatlabFiles') == 181,
            'T23 baseline counts disagree')
    for field, path, digest in [('BaselineCandidate', PARENT_CANDIDATE, PARENT_CANDIDATE_SHA),
                                ('BaselineAcceptance', PARENT_ACCEPTANCE, PARENT_ACCEPTANCE_SHA)]:
        require(candidate.get(field) == path and candidate.get(field+'SHA256') == sha256(source_root/path) == digest,
                'Accepted T23 provenance mismatch: '+field)
    accepted = json_object(source_root/PARENT_ACCEPTANCE)
    require(accepted.get('diagnostic_accepted') is True and accepted.get('production_change') is False
            and accepted.get('candidate_sha256') == PARENT_CANDIDATE_SHA
            and accepted.get('owner_archive_sha256') == PARENT_OWNER_SHA
            and accepted.get('source_snapshot_sha256') == BASELINE_SHA,
            'T23 diagnostic acceptance identity differs')
    # T23 proved a controlled contract difference; it did not accept numerical parity.
    require(accepted.get('numerical_parity_established') is False and accepted.get('cross_engine_contract_passed') is False,
            'T23 prior diagnostic flags were rewritten')
    require(sha256(source_root/'evidence/t23/owner.zip') == PARENT_OWNER_SHA, 'T23 accepted owner archive differs')
    if metadata is not None:
        require(metadata.get('AllBaselineSourcesUnchanged') is True
                and metadata.get('BaselineSourceFilesVerified') == 404
                and metadata.get('BaselineMatlabFilesVerified') == 181,
                'Returned T23 baseline preservation claims disagree')
    return {'source_files': 404, 'matlab_files': 181, 'source_snapshot_sha256': BASELINE_SHA,
            'all_baseline_sources_unchanged': True, 'prior_t23_cross_engine_contract_passed': False,
            'prior_numerical_parity_established': False}


def verify_plan(source_root, candidate):
    require(candidate.get('Plan') == PLAN and candidate.get('PlanSHA256') == sha256(source_root/PLAN), 'Plan binding mismatch')
    plan = json_object(source_root/PLAN)
    required = {'schema': 'csr-tranche25-ensemble-plan-v1', 'tranche': 25,
        'execution_order': ['s131', 's132'], 'comparison_seeds': list(multi.SEEDS),
        'fresh_seeds': list(multi.FRESH_SEEDS), 'planned_simulated_seconds': 12000,
        'comparison_band_percent': 10, 'timeline_bucket_width_s': 300, 'duration_s': 6000,
        'expected_admission_attempts': 1710000, 'timing_policy': 'continuous',
        'full_portable_regression': True, 'seed_override_after_import': True,
        'runtime_must_equal_parent': False, 'reused_seeds': list(multi.REUSED_SEEDS),
        'fresh_native_reference_seeds': list(multi.FRESH_SEEDS), 'reused_native_reference_seeds': list(multi.REUSED_SEEDS),
        'numerical_method_frozen_before_fresh_result_review': True}
    require(all(plan.get(key) == value for key, value in required.items()), 'T25 predefined plan scope mismatch')
    for flag in ('default_policy_changed', 'phy_ecc_changed', 'observer_enabled', 'post_horizon_drain',
                 'numerical_parity_required', 'common_random_numbers_claimed'):
        require(plan.get(flag) is False, 'Unsupported plan behavior: '+flag)
    require(plan.get('ns3_source_commit') == multi.PIN and plan.get('engine_commit') == multi.ENGINE,
            'Plan source/engine pin differs')
    require(plan.get('reused_campus_file') == REUSED and plan.get('reused_campus_sha256') == sha256(source_root/REUSED),
            'Reused campus plan binding differs')
    require(plan.get('numerical_method') == multi.METHOD, 'Prespecified ensemble method changed')
    catalog = json_object(source_root/'scenarios/benchmarks/catalog.json')
    campus = [case for case in records(catalog['cases'], 'catalog') if case['case_id'] == 'campus_multihop_6000']
    require(len(campus) == 1, 'Missing/duplicate original campus')
    campus = campus[0]
    require(plan.get('scenario_file') == campus['scenario_file'] and
            plan.get('scenario_sha256') == campus['scenario_sha256'] == sha256(source_root/campus['scenario_file']),
            'Original campus changed')
    cases = records(plan.get('cases'), 'cases')
    require([case.get('case_id') for case in cases] == ['s131', 's132'], 'Wrong fresh cases/order')
    for case, seed in zip(cases, multi.FRESH_SEEDS):
        require(case.get('seed') == seed and case.get('policy') == 'actual-tx'
                and case.get('reference_directory') == f'evidence/tranche-25-ns3-reference/s{seed}'
                and all(case.get(key) == campus[key] for key in ('scenario','scenario_file','scenario_sha256','duration_s','bucket_width_s')),
                'Fresh case changed beyond seed')
    return plan, campus


def verify_references(source_root, candidate):
    names = candidate.get('ReferenceFiles')
    require(candidate.get('ReferenceRoots') == [] and isinstance(names, list) and names == sorted(set(names)) and names,
            'Expected sorted explicit reference inventory')
    bindings = record_map(candidate.get('ReferenceFileInventory'), 'references', sizes=True)
    require(set(bindings) == set(names), 'Reference membership mismatch')
    required = {BASELINE, PARENT_CANDIDATE, PARENT_ACCEPTANCE, REUSED, 'evidence/t23/owner.zip'}
    reused = json_object(source_root/REUSED)
    for row in records(reused.get('cases'), 'reused cases'):
        required.update(row[key] for key in ('owner_file', 'candidate_file', 'acceptance_file', 'source_snapshot_file'))
    for tree in ('evidence/tranche-7-ns3-reference', 'evidence/tranche-7-benchmark-inputs',
                 'evidence/tranche-20-ns3-reference', 'evidence/tranche-25-ns3-reference'):
        required.update(f'{tree}/{name}' for name in all_files(source_root/tree))
    parent_references = record_map(json_object(source_root/PARENT_CANDIDATE).get('ReferenceFileInventory'), 'T23 references', sizes=True)
    require(candidate.get('AllowedModifiedReferenceFiles') == ['docs/parity-ledger.csv']
            and candidate.get('PreservedBaselineLedger') == 'evidence/t25/baseline/parity-ledger.csv',
            'Baseline reference preservation policy changed')
    require(set(parent_references) <= set(bindings), 'Accepted T23 reference membership missing')
    for name, row in parent_references.items():
        if name == 'docs/parity-ledger.csv':
            require(sha256(source_root/candidate['PreservedBaselineLedger']) == row['sha256'], 'Preserved T23 ledger differs')
        else:
            require(bindings[name] == row, 'Accepted T23 reference declaration changed: '+name)
    required.add(candidate['PreservedBaselineLedger'])
    require(required <= set(bindings), 'Required parent/native reference membership missing')
    for name, row in bindings.items():
        path = safe_path(source_root, name)
        require(path.is_file() and path.stat().st_size == row['bytes'] and sha256(path) == row['sha256'],
                'Reference bytes changed: '+name)
    t7.verify_reference_suite(source_root, json_object(source_root/'scenarios/benchmarks/catalog.json'))
    return bindings


def verify_preparation(source_root):
    source_root = Path(source_root).resolve()
    candidate = json_object(source_root/CANDIDATE)
    require(candidate.get('Schema') == 'csr-tranche-25-candidate-v1' and candidate.get('Tranche') == 25
            and candidate.get('SourceCommit') == multi.PIN and candidate.get('EngineCommit') == multi.ENGINE,
            'Candidate identity/source pin mismatch')
    source = candidate_snapshot(source_root)
    require(candidate.get('SourceFilesExcludedPaths') == [CANDIDATE] and
            t17.source_map(candidate.get('SourceFiles'), 'candidate sources') ==
            {name: digest for name, digest in source.items() if name != CANDIDATE}, 'Candidate sources changed/missing')
    files = sorted(path.relative_to(source_root).as_posix() for path in (source_root/'tests').glob('Test*.m'))
    names = selected_test_names(source_root, files)
    require(candidate.get('TestFiles') == files and candidate.get('ExpectedTestNames') == names, 'Full portable test selection mismatch')
    baseline = verify_baseline(source_root, candidate)
    references = verify_references(source_root, candidate)
    plan, campus = verify_plan(source_root, candidate)
    reused = verify_reused(source_root)
    native = {row['seed']: row['ns3'] for row in reused['cases']}
    build = multi.verify_native_suite(source_root)
    for seed in multi.FRESH_SEEDS:
        native[seed] = multi.normalize_native(multi.verify_native(source_root, seed, verified_build=build))
    return {'source': source, 'references': references, 'baseline': baseline, 'plan': plan, 'campus': campus,
            'planned_matlab_tests': len(names), 'planned_cases': 2, 'reused': reused,
            'native_application_reference': native, 'matlab_executed': False}


def verify_identity(root, metadata, source_root, candidate):
    require(metadata.get('Schema') == SCHEMA and metadata.get('Tranche') == 25 and
            metadata.get('Status') == 'completed-review-required', 'Return is not finalized complete T25 evidence')
    require(metadata.get('CandidateFile') == CANDIDATE and metadata.get('CandidateSHA256') == sha256(source_root/CANDIDATE)
            == sha256(root/'candidate.json') and sha256(root/'plan.json') == candidate['PlanSHA256'],
            'Returned candidate/plan binding mismatch')
    runtime = metadata.get('Runtime')
    require(isinstance(runtime, dict) and runtime.get('Runtime') == 'MATLAB' and runtime.get('DefaultBackend') == 'portable'
            and all(isinstance(runtime.get(key), str) and runtime[key] for key in ('Version', 'Release')),
            'Missing portable MATLAB runtime/release')
    required = {'SourceCommit': multi.PIN, 'MATLABExecuted': True, 'NativeExecuted': False,
        'FullAcceptanceGateExecuted': True, 'AcceptanceEstablished': False, 'NumericalParityEstablished': False,
        'CompletedCaseCount': 2, 'PlannedCaseCount': 2, 'CampusStructuralChecksPassed': True,
        'SimulatedSecondsCompleted': 12000, 'PlannedSimulatedSeconds': 12000,
        'ReusedCaseCount': 3, 'ReusedSeeds': list(multi.REUSED_SEEDS), 'ComparisonSeeds': list(multi.SEEDS),
        'SingleSeedScope': False, 'CommonRandomNumbersClaimed': False,
        'HistoricalRuntimeEqualityRequired': False, 'StatisticalEquivalenceClaimed': False,
        'ReusedCampusFile': REUSED, 'ReusedCampusSHA256': sha256(source_root/REUSED), 'ComparisonBandPercent': 10,
        'EvidenceArchive': 't25.zip'}
    require(all(metadata.get(key) == value for key, value in required.items()), 'Runtime/scope/full-gate claims mismatch')
    require(t17.timestamp(metadata.get('StartedUTC'), 'start') <= t17.timestamp(metadata.get('CompletedUTC'), 'completion'),
            'Completion precedes start')
    reused = json_object(source_root/REUSED)
    require(metadata.get('ReusedCases') == reused_report_rows(reused, runtime), 'Reused historical runtime/source/case claims differ')
    require(metadata.get('MatlabRuntimeHomogeneousAcrossSeeds') == all(row['runtime'] == runtime for row in reused['cases']),
            'Runtime homogeneity claim differs')
    return runtime


def verify_stage(root,phase,entry,metadata,source,references,runtime):
    require(entry.get('Phase') == phase and entry.get('File') == f'{phase}/receipt.json','Stage receipt path/phase mismatch')
    directory = root/phase; path = directory/'receipt.json'; digest = sha256(path)
    require(entry.get('SHA256') == digest == (directory/'receipt.sha256').read_text().strip(),'Stage receipt hash mismatch')
    receipt = json_object(path)
    require(receipt.get('schema') == 'csr-tranche25-stage-receipt-v1' and receipt.get('phase') == phase
            and receipt.get('status') == 'completed','Stage incomplete or wrong identity')
    identity = receipt.get('identity',{})
    require(isinstance(identity,dict) and identity.get('CandidateSHA256') == metadata['CandidateSHA256']
            and identity.get('SourceCommit') == t7.PIN and identity.get('Runtime') == runtime
            and t17.source_map(identity.get('SourceFiles'),'stage sources') == source
            and record_map(identity.get('ReferenceFiles'),'stage references',sizes=True) == references,
            'Stage source/reference/candidate/runtime mismatch')
    require(receipt.get('SourceFilesStableDuringRun') is True and receipt.get('ReferenceFilesStableDuringRun') is True
            and t17.source_map(receipt.get('SourceFilesFinal'),'stage final sources') == source
            and record_map(receipt.get('ReferenceFilesFinal'),'stage final references',sizes=True) == references,
            'Stage source/reference stability unproven')
    started = json_object(directory/'start.json')
    require(started.get('schema') == 'csr-tranche25-stage-start-v1' and started.get('phase') == phase
            and started.get('status') == 'started' and started.get('identity') == identity,
            'Stage start identity/status mismatch')
    require(t17.timestamp(started.get('started_utc'),'stage start') <= t17.timestamp(receipt.get('completed_utc'),'stage completion')
            <= t17.timestamp(metadata['CompletedUTC'],'finalize'),'Stage timing inconsistent')
    inventory(directory,receipt.get('artifacts'),phase+' artifacts',excluded=('receipt.json','receipt.sha256'),
              local=receipt.get('local_artifacts',[]))
    summary = json_object(directory/'summary.json')
    require(receipt.get('summary') == summary,'Stage receipt summary content mismatch')
    return summary


def verify_tests(root, metadata, source_root, candidate, summary):
    files, names = candidate['TestFiles'], candidate['ExpectedTestNames']
    require(summary.get('Schema') == 'csr-tranche25-portable-tests-summary-v1'
            and summary.get('TestResultsFile') == 'results.csv' and summary.get('TestFiles') == files
            and summary.get('ExpectedTestNames') == names, 'Portable tests summary selection mismatch')
    require(names == selected_test_names(source_root, files), 'Test source methods changed')
    require(metadata.get('TestResultsFile') == 'tests/results.csv' and metadata.get('TestFiles') == files
            and metadata.get('ExpectedTestNames') == names, 'Returned test selection differs')
    rows = csv_rows(root/'tests/results.csv', ('Name', 'Passed', 'Failed', 'Incomplete', 'DurationSeconds'))
    require(len(rows) == len(names) and {row['Name'] for row in rows} == set(names), 'Missing or duplicate portable MATLAB test identity')
    for row in rows:
        require(logical(row['Passed'], 'Passed') and not logical(row['Failed'], 'Failed') and not logical(row['Incomplete'], 'Incomplete'),
                'MATLAB test failed or incomplete')
        number(row['DurationSeconds'], 'test duration', minimum=0)
    for reported in (summary, metadata):
        require(reported.get('TestsExecuted') is True and reported.get('TestsPassed') is True and
                all(integer(reported.get(key), key) == value for key, value in
                    [('TestCount', len(names)), ('PassedTests', len(names)), ('FailedTests', 0), ('IncompleteTests', 0)]),
                'MATLAB test counters disagree with exact results')
    return {'status': 'passed', 'count': len(names), 'classes': len(files), 'names': names,
            'scope': 'All top-level portable Test*.m classes; native adapter tests excluded.'}


def verify_configuration(config,baseline,case,source_root):
    actual=copy.deepcopy(config)
    require(actual.get('Hop',{}).get('DataQueuedRetryPolicy') == case['policy'] == 'actual-tx','Default DATA policy changed')
    require(actual.get('Seed') == case['seed'] and baseline.get('Seed') == 128,'Case seed override mismatch')
    actual['Seed']=128
    result=retained.same_configuration(baseline,actual,source_root,case)
    result['seed_override']={'before':128,'after':case['seed']}
    return result


def verify_case(root,entry,case,summary,source_root,source,runtime,source_hash,baseline_config):
    key = case['case_id']; directory = root/key
    require(entry.get('CaseId') == key and entry.get('Directory') == key and
            entry.get('ManifestSHA256') == sha256(directory/'case.json') and summary.get('Case') == entry,
            'Case path/manifest/summary binding mismatch')
    manifest = json_object(directory/'case.json')
    require(manifest.get('schema') == 'csr-tranche25-ensemble-case-v1' and manifest.get('status') == 'completed'
            and manifest.get('case_id') == key and manifest.get('policy') == case['policy']
            and manifest.get('case') == case and manifest.get('original_case_id') == 'campus_multihop_6000',
            'Case manifest identity mismatch')
    require(manifest.get('opnet_same_seed_reference_available') is False and
        manifest.get('opnet_scope')=='archived-seed128-aggregate-context-only', 'Unsupported OPNET seed comparison')
    for field in ('scenario','scenario_sha256','seed','duration_s','bucket_width_s','reference_directory'):
        require(manifest.get(field) == case[field],'Case plan/manifest mismatch: '+field)
    require(manifest.get('runtime') == runtime and manifest.get('matlab_version') == runtime['Version']
            and manifest.get('matlab_release') == runtime['Release'] and manifest.get('ns3_source_commit') == t7.PIN
            and manifest.get('source_snapshot_sha256') == source_hash
            and t17.source_map(manifest.get('source_files'),'case sources') == source,'Case runtime/source binding mismatch')
    require(manifest.get('seed_override_after_import') is True and manifest.get('imported_seed') == 128, 'Seed override provenance missing')
    require(manifest.get('scheduler_stop_s') == 6000 and manifest.get('mode') == 'continuous'
            and all(manifest.get(k) is True for k in ('structural_checks_passed','admission_counts_complete','original_admission_trace_prefix'))
            and all(manifest.get(k) is False for k in ('observer_enabled','post_horizon_drain','numerical_parity_established')),
            'Case completion/observation scope mismatch')
    inventory(directory,manifest.get('files'),'case files',excluded=('start.json','case.json','summary.json','receipt.json','receipt.sha256'),
              local=manifest.get('local_files',[]))
    raw_manifest = json_object(directory/'raw/case_manifest.json')
    require(raw_manifest.get('schema') == 'csr-matlab-research-case-v1' and raw_manifest.get('status') == 'completed'
            and all(raw_manifest.get(k) is True for k in ('execution_completed','structural_checks_passed','source_files_stable'))
            and raw_manifest.get('ns3_source_commit') == t7.PIN and raw_manifest.get('matlab_version') == runtime['Version']
            and raw_manifest.get('matlab_release') == runtime['Release']
            and t17.source_map(raw_manifest.get('source_files'),'raw source') == source,'Raw case completion/source mismatch')
    require(raw_manifest.get('imported_seed')==128 and raw_manifest.get('seed_override_after_import') is True,
        'Raw seed override provenance missing')
    inventory(directory/'raw',raw_manifest.get('files'),'raw files',excluded=('case_manifest.json',),local=raw_manifest.get('local_files',[]))
    require(raw_manifest.get('scenario_sha256') == sha256(directory/'raw/scenario.csv') == case['scenario_sha256'],
            'Raw original scenario mismatch')
    raw = json_object(directory/'raw/summary.json'); config,stats,md = raw['Config'],raw['Statistics'],raw['Metadata']
    configuration = verify_configuration(config,baseline_config,case,source_root)
    require(md.get('Runtime') == 'MATLAB' and md.get('Version') == runtime['Version'] and md.get('Release') == runtime['Release']
            and md.get('SourceCommit') == t7.PIN and md.get('Backend') == 'portable' and md.get('ChannelModel') == 'csr-phy'
            and md.get('ModelStage') == 'tranche-3-autonomous-network-routing' and manifest.get('result_metadata') == md
            and not any(k in raw for k in ('TransportTiming','ServiceDiagnostics','LinkDiagnostics')),
            'Unexpected runtime/controlled or instrumented PHY/configuration')
    require(sha256(directory/'raw/trace.csv') == sha256(directory/'raw/protocol_trace.csv'),'Protocol trace copies disagree')
    require(all(integer(stats.get(k),k) == 0 for k in ('OmittedTraceRecords','OmittedPhyTraceRecords')),
            'Protocol or PHY trace truncated')
    legacy_config = copy.deepcopy(config)
    legacy_config['Hop'].pop('DataQueuedRetryPolicy')
    t7.verify_config(directory,legacy_config)
    counts = t7.count_balance(stats,key)
    performance_rows = list(metrics.rows(directory/'analysis/performance_summary.csv'))
    require(len(performance_rows) == 1,'Missing/duplicate performance summary')
    performance = performance_rows[0]
    parsed = sweep.metrics(performance)
    require(all(parsed[k] == counts[k] for k in t7.COUNTS),'Performance/raw outcome mismatch')
    admission = t7.verify_admission(directory,config,stats)
    require(admission['attempts'] == 1710000 and admission['trace_records'] == 100000
            and admission['omitted_trace_records'] == 1610000
            and integer(manifest.get('admission_trace_omitted_records'),'manifest omissions') == 1610000,
            'Historical admission-prefix exact accounting mismatch')
    expected_summary = {'Schema':'csr-tranche25-ensemble-summary-v1','CaseId':key,'Policy':case['policy'],
        'OriginalBenchmarkCaseId':'campus_multihop_6000','CompletedCaseCount':1,'DurationSeconds':6000,'SchedulerStopSeconds':6000,
        'Seed':case['seed'],'ImportedSeed':128,'SeedOverrideAfterImport':True,'RequestedPolicySameAsDefault':case['policy']=='actual-tx'}
    expected_summary.update(dict.fromkeys(('StructuralChecksPassed','DefaultContinuousTiming','RealPHY','AutonomousRouting','OriginalAdmissionTracePrefix'),True))
    expected_summary.update(dict.fromkeys(('ObserverEnabled','PostHorizonDrain','AcceptanceEstablished','NumericalParityEstablished','FiniteStopPendingIsFailure'),False))
    require(all(summary.get(k) == v for k,v in expected_summary.items()) and summary.get('ProtocolTraceOmissions') == 0
            and summary.get('PhyTraceOmissions') == 0,'Case stage summary completion/scope mismatch')
    number(summary.get('ElapsedWallSeconds'),'elapsed wall seconds',minimum=0)
    t17.verify_campus_summary(summary,performance,admission)
    benchmark = list(metrics.rows(directory/'benchmark_summary.csv',('CaseId','Policy',*t7.COUNTS,'Attempts','AdmissionBlocked')))
    require(len(benchmark) == 1 and benchmark[0]['CaseId'] == key and benchmark[0]['Policy'] == case['policy']
            and t7.count_balance(benchmark[0],key) == counts and integer(benchmark[0]['Attempts'],'attempts') == admission['attempts']
            and integer(benchmark[0]['AdmissionBlocked'],'blocked') == admission['blocked'],'Case benchmark summary mismatch')
    node_counts = t17.verify_node_metrics(directory,config,performance)
    physical = t17.verify_phy(directory,config,stats,performance)
    provenance = json_object(directory/'analysis/aggregate_provenance.json')
    require(provenance.get('source_snapshot_sha256') == source_hash and provenance.get('source_file') == 'raw/protocol_trace.csv'
            and provenance.get('source_file_sha256') == sha256(directory/'raw/protocol_trace.csv'),'Aggregate source/trace binding mismatch')
    observations = multi.analyze_case(directory,case)
    require(all(observations['totals'][field] == counts[counter] for field,counter in
                (('admitted','Generated'),('delivered','Received'),('dropped','Dropped'),('pending','Pending')))
            and observations['totals']['attempts'] == admission['attempts']
            and observations['totals']['blocked'] == admission['blocked'],
            'Reconstructed metrics disagree with complete raw accounting')
    return {'case_id':key,'policy':case['policy'],'counts':counts,'admission':admission,
        'configuration':configuration,'physical_trace':physical,'node_counts':node_counts,
        'elapsed_wall_seconds':float(summary['ElapsedWallSeconds']),'observations':observations}



def compare_seed_aggregates(directory,reference,campus,seed):
    """Validate each engine's real input hash, then align event-rate buckets."""
    observations={}; inputs={}
    for engine in ('matlab','ns3'):
        path=directory/'analysis/aggregates.csv' if engine=='matlab' else reference/'ns3-aggregates.csv'
        side=directory/'analysis/aggregate_provenance.json' if engine=='matlab' else reference/'ns3-benchmark.provenance.json'
        provenance=json_object(side)
        descriptor={k:campus[k] for k in ('scenario','scenario_sha256','profile_id','duration_s','bucket_width_s')}
        if engine=='ns3' and seed!=128:
            descriptor['scenario_sha256']=sha256(reference/'scenario.csv')
        trace_hash=aggregate._check_provenance(provenance,descriptor,engine,sha256(path),6000,60,100)
        observations[engine],excluded=aggregate.read_series(path,engine,campus['scenario'],trace_hash,60,100,provenance.get('excluded_extra_statistics',[]))
        inputs[engine]={'scenario_sha256':descriptor['scenario_sha256'],'aggregate_sha256':sha256(path),'provenance_sha256':sha256(side),'excluded':excluded}
        if engine=='matlab':
            require(trace_hash==sha256(directory/'raw/protocol_trace.csv'),'MATLAB aggregate trace hash mismatch')
        else:
            upstream=provenance.get('upstream_provenance',{})
            require(sha256(safe_path(reference,upstream.get('path')))==upstream.get('sha256'),'Native aggregate upstream mismatch')
    comparison,points=aggregate._compare_pair('matlab','ns3',observations,60,100)
    return {'seed':seed,'inputs':inputs,'comparison':comparison,'points':points,
        'scope':'Event-based aggregate rates and bucket means, separate from unique delivered application counts. Native seed-only input mapping verified independently.',
        'numeric_tolerance_gate_applied':False}


def review(evidence, source_root, output):
    evidence, source_root, output = t17.output_location(evidence, source_root, output)
    prepared = verify_preparation(source_root); candidate = json_object(source_root/CANDIDATE)
    with t17.evidence_directory(evidence) as root:
        require(evidence.is_dir() or not (root/'t25.zip').exists(), 'Unexpected nested return archive')
        metadata = json_object(root/'metadata.json'); runtime = verify_identity(root, metadata, source_root, candidate)
        inventory(root, metadata.get('Artifacts'), 'outer artifacts', excluded=('metadata.json', 't25.zip'), local=metadata.get('LocalArtifacts', []))
        source_report = verify_sources(root, metadata, source_root)
        references = t17.verify_references(root, metadata, prepared['references'])
        baseline = verify_baseline(source_root, candidate, metadata)
        entries = records(metadata.get('StageReceipts'), 'stage receipts')
        require(len(entries) == 3 and {entry.get('Phase') for entry in entries} == set(PHASES), 'Missing/duplicate stage receipts')
        summaries = {entry['Phase']: verify_stage(root, entry['Phase'], entry, metadata, prepared['source'], prepared['references'], runtime)
                     for entry in entries}
        tests = verify_tests(root, metadata, source_root, candidate, summaries['tests'])
        cases = records(metadata.get('Cases'), 'completed cases')
        require(len(cases) == 2 and {entry.get('CaseId') for entry in cases} == {'s131', 's132'}, 'Missing/duplicate fresh seed cases')
        cases = {entry['CaseId']: entry for entry in cases}
        with zipfile.ZipFile(source_root/'evidence/t19/owner.zip') as archive:
            baseline_config = json.loads(archive.read('a128/raw/summary.json'))['Config']
        observations, aggregate_comparisons = {}, {}
        for case in prepared['plan']['cases']:
            key = case['case_id']
            observations[key] = verify_case(root, cases[key], case, summaries[key], source_root, prepared['source'], runtime,
                                            sha256(root/'source.json'), baseline_config)
            aggregate_comparisons[case['seed']] = compare_seed_aggregates(root/key, source_root/case['reference_directory'], prepared['campus'], case['seed'])
        matlab = {row['seed']: row['matlab'] for row in prepared['reused']['cases']}
        matlab.update({seed: multi.normalize_matlab(observations[f's{seed}']['observations']) for seed in multi.FRESH_SEEDS})
        comparisons = multi.compare_seeds(matlab, prepared['native_application_reference'])
        runtimes = [{'seed': row['seed'], 'runtime': row['runtime'], 'fresh_execution': False} for row in prepared['reused']['cases']]
        runtimes += [{'seed': seed, 'runtime': runtime, 'fresh_execution': True} for seed in multi.FRESH_SEEDS]
        homogeneous = all(row['runtime'] == runtime for row in runtimes)
        limitations = list(LIMITATIONS)
        if not homogeneous:
            limitations.append('MATLAB releases/capability identities differ across reused and fresh runs; observed variability cannot isolate seed from runtime differences.')
        for seed in multi.FRESH_SEEDS:
            # Raw receipt/trace proof remains in the returned archive; avoid copying millions of ownership episode fields into the numerical report.
            observations[f's{seed}']['observations'] = matlab[seed]
        result = {'schema': REVIEW_SCHEMA, 'status': 'structural_review_completed', 'evidence_integrity_verified': True,
            'full_structural_gate_completed': True, 'acceptance_established': False, 'numerical_parity_established': False,
            'matlab_executed_by_reviewer': False, 'runtime': runtime, 'source': source_report, 'baseline': baseline,
            'references': references, 'tests': tests, 'cases': observations, 'reused_cases': prepared['reused']['cases'],
            'engine_ensemble': {'matlab_runs': runtimes, 'runtime_homogeneous': homogeneous,
                'historical_runtime_equality_required': False, 'ns3_source_commit': multi.PIN, 'ns3_engine_commit': multi.ENGINE},
            'native_application_reference': prepared['native_application_reference'], 'comparisons': comparisons,
            'aggregate_comparisons': aggregate_comparisons, 'metadata_sha256': sha256(root/'metadata.json'), 'limitations': limitations}
    output.mkdir(parents=True, exist_ok=True)
    (output/'review.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(argv)
    try:
        t17.output_location(args.evidence,args.source_root,args.output)
    except ValueError as exc:
        print('T25 review output rejected without modifying inputs: '+str(exc)); return 1
    try:
        result = review(args.evidence,args.source_root,args.output)
    except (ValueError,OSError,csv.Error,zipfile.BadZipFile,KeyError,TypeError,AttributeError,OverflowError,StopIteration) as exc:
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'review.json').write_text(json.dumps({'schema':REVIEW_SCHEMA,'status':'review_failed',
            'evidence_integrity_verified':False,'full_structural_gate_completed':False,'acceptance_established':False,
            'numerical_parity_established':False,'matlab_executed_by_reviewer':False,'error':str(exc)},indent=2)+'\n')
        print('T25 evidence rejected: '+str(exc)); return 1
    print(f"T25 review completed: {result['tests']['count']} portable tests, two fresh full-campus seeds and three archived seeds; numerical residuals descriptive.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
