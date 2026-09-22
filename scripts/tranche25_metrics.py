"""Prespecified five-run campus screen; a run, never a packet, is a sample.

Seeds label matched configurations, not common random numbers. Whole run vectors
are resampled independently by engine. All uncertainty is exploratory at n=5;
these intervals and the practical +/-10% screen cannot establish equivalence.
"""
from __future__ import annotations

import math
from pathlib import Path
import random
import statistics

from analyze_tranche11_return import require, json_object, sha256, safe_path, record_map, all_files
import tranche20_metrics as previous
import tranche20_native_metrics as native_metrics

PIN = previous.PIN
ENGINE = previous.ENGINE
SEEDS = (128, 129, 130, 131, 132)
FRESH_SEEDS = (131, 132)
REUSED_SEEDS = (128, 129, 130)
SOURCES = (2, 3, 4, 5, 7, 8)
METRICS = ('admitted', 'unique_delivered', 'mean_delivered_delay_s')
METHOD = {
    'schema': 'csr-tranche25-five-seed-method-v1',
    'seeds': list(SEEDS),
    'sampling_unit': 'whole_engine_run',
    'engines_resampled_independently': True,
    'resample_whole_flow_vector': True,
    'bootstrap_draws': 20000,
    'bootstrap_rng_seed': 2500132,
    'bootstrap_rng': 'python-random-MT19937-randrange',
    'interval_percentiles': [2.5, 97.5],
    'percentile_interpolation': 'linear-type7',
    'count_estimand': 'ratio_of_unweighted_run_means_equals_ratio_of_sums',
    'delay_estimand': 'ratio_of_unweighted_run_conditional_delivered_delay_means',
    'packet_weighted_delay_role': 'separate_descriptive_only',
    'working_band_percent': 10,
    'historical_band_percent': 5,
    'paired_seed_bootstrap': False,
    'packet_bootstrap': False,
    'equivalence_acceptance_test': False,
    'scope': 'Exploratory five-run sample; no population equivalence or numerical acceptance claim.',
}


def finite_nonnegative(value, label):
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0, 'Invalid '+label)
    return float(value)


def count(value, label):
    number = finite_nonnegative(value, label)
    require(number.is_integer(), 'Noninteger '+label)
    return int(number)


def _normalized_row(row, *, native=False, latency=None):
    admitted = count(row['admitted'], 'admitted count')
    delivered = count(row.get('unique_delivered', row.get('delivered')), 'delivered count')
    require(delivered <= admitted, 'Delivered count exceeds admissions')
    latency = latency if latency is not None else row.get('first_delivery_delay_s' if native else 'delivered_latency')
    require(isinstance(latency, dict), 'Missing conditional delivered delay population')
    n = count(latency['count'], 'delay count')
    mean = latency.get('mean' if native else 'mean_s')
    require(n == delivered, 'Conditional delay count differs from unique deliveries')
    if n:
        mean = finite_nonnegative(mean, 'conditional delivered delay')
        total = finite_nonnegative(latency.get('sum_s', mean*n), 'delivered delay sum')
        require(math.isclose(total/n, mean, rel_tol=1e-12, abs_tol=1e-9), 'Delay sum and mean disagree')
    else:
        require(mean is None, 'Empty conditional delay population must have null mean')
        total = 0.0
    return {'admitted': admitted, 'unique_delivered': delivered,
            'delivered_delay_count': n, 'delivered_delay_sum_s': total,
            'mean_delivered_delay_s': mean}


def normalize_matlab(observations):
    flows = [dict(source=count(row['source'], 'source'), **_normalized_row(row))
             for row in observations['flows']]
    total_delay = math.fsum(row['delivered_delay_sum_s'] for row in flows)
    delivered = sum(row['unique_delivered'] for row in flows)
    result = {'totals': {'admitted': sum(row['admitted'] for row in flows),
              'unique_delivered': delivered, 'delivered_delay_count': delivered,
              'delivered_delay_sum_s': total_delay,
              'mean_delivered_delay_s': total_delay/delivered if delivered else None},
              'flows': flows}
    require(result['totals']['admitted'] == observations['totals']['admitted']
            and delivered == observations['totals']['delivered'], 'MATLAB flow/total accounting differs')
    validate_run(result)
    return result


def normalize_native(observations, *, delay_override=None):
    """Normalize native metrics; old seed128 needs independently recovered delays."""
    overrides = delay_override or {}
    flows = [dict(source=count(row['source'], 'source'),
                  **_normalized_row(row, native=True, latency=overrides.get(row['source'])))
             for row in observations['flows']]
    total_delay = math.fsum(row['delivered_delay_sum_s'] for row in flows)
    delivered = sum(row['unique_delivered'] for row in flows)
    result = {'totals': {'admitted': sum(row['admitted'] for row in flows),
              'unique_delivered': delivered, 'delivered_delay_count': delivered,
              'delivered_delay_sum_s': total_delay,
              'mean_delivered_delay_s': total_delay/delivered if delivered else None},
              'flows': flows}
    require(result['totals']['admitted'] == observations['totals']['admitted']
            and delivered == observations['totals']['delivered'], 'Native flow/total accounting differs')
    if 'first_delivery_delay_s' in observations:
        whole = observations['first_delivery_delay_s']
        require(whole['count'] == delivered and
                (whole['mean'] is None if not delivered else
                 math.isclose(whole['mean'], result['totals']['mean_delivered_delay_s'], rel_tol=1e-12, abs_tol=1e-9)),
                'Native whole-run delay differs from flow populations')
    validate_run(result)
    return result


def validate_run(run):
    require(isinstance(run, dict) and isinstance(run.get('totals'), dict)
            and isinstance(run.get('flows'), list), 'Missing run totals/flows')
    flows = run['flows']
    require(len(flows) == len(SOURCES) and {row.get('source') for row in flows} == set(SOURCES),
            'Flow populations differ or duplicate')
    for row in [run['totals'], *flows]:
        a, d, n = [count(row.get(key), key) for key in ('admitted', 'unique_delivered', 'delivered_delay_count')]
        require(d <= a and n == d, 'Run admission/delivery/delay accounting differs')
        total = finite_nonnegative(row.get('delivered_delay_sum_s'), 'delivered delay sum')
        mean = row.get('mean_delivered_delay_s')
        if n:
            finite_nonnegative(mean, 'conditional delivered delay')
            require(math.isclose(total/n, mean, rel_tol=1e-12, abs_tol=1e-9), 'Run delay sum/mean differs')
        else:
            require(mean is None and total == 0, 'Empty delay population must be null, never zero-filled')
    for key in ('admitted', 'unique_delivered', 'delivered_delay_count'):
        require(run['totals'][key] == sum(row[key] for row in flows), 'Run flow/total accounting differs: '+key)
    require(math.isclose(run['totals']['delivered_delay_sum_s'],
                        math.fsum(row['delivered_delay_sum_s'] for row in flows), rel_tol=1e-12, abs_tol=1e-8),
            'Run flow/total delay sum differs')
    return run


def describe(values):
    if any(value is None for value in values):
        return None
    return {'mean': statistics.fmean(values), 'minimum': min(values), 'maximum': max(values),
            'sample_standard_deviation': statistics.stdev(values)}


def residual(matlab, native):
    return 100*(matlab-native)/native if matlab is not None and native is not None and native > 0 else None


def percentile(sorted_values, percent):
    require(sorted_values and 0 <= percent <= 100, 'Invalid percentile input')
    pos = (len(sorted_values)-1)*percent/100
    lo = int(math.floor(pos)); hi = int(math.ceil(pos))
    return sorted_values[lo] + (sorted_values[hi]-sorted_values[lo])*(pos-lo)


def bootstrap_indices():
    rng = random.Random(METHOD['bootstrap_rng_seed'])
    # Each sampled index identifies an entire run: all flows travel together.
    return [(tuple(rng.randrange(5) for _ in SEEDS), tuple(rng.randrange(5) for _ in SEEDS))
            for _ in range(METHOD['bootstrap_draws'])]


def exploratory_interval(matlab, native, indices):
    missing = any(value is None for value in [*matlab, *native])
    base = {'method': 'independent-whole-run-percentile-bootstrap',
            'draws': METHOD['bootstrap_draws'], 'percentiles': METHOD['interval_percentiles'],
            'lower_residual_percent': None, 'upper_residual_percent': None,
            'valid_draws': 0, 'undefined_draws': METHOD['bootstrap_draws'],
            'degenerate_empirical_distribution': False, 'equivalence_established': False,
            'exploratory_only': True}
    if missing:
        return dict(base, status='undefined_missing_run_conditional_mean')
    values = []
    for mi, ni in indices:
        m = math.fsum(matlab[index] for index in mi)
        n = math.fsum(native[index] for index in ni)
        value = residual(m, n)
        if value is not None:
            values.append(value)
    base.update(valid_draws=len(values), undefined_draws=len(indices)-len(values))
    if len(values) != len(indices):
        return dict(base, status='undefined_zero_native_bootstrap_denominator')
    values.sort()
    return dict(base, status='exploratory_complete',
                lower_residual_percent=percentile(values, 2.5),
                upper_residual_percent=percentile(values, 97.5),
                degenerate_empirical_distribution=values[0] == values[-1])


def compare_seeds(matlab, native, band_percent=10):
    require(set(matlab) == set(native) == set(SEEDS), 'Exactly all five predefined seeds required')
    require(band_percent == METHOD['working_band_percent'], 'Prespecified descriptive band changed')
    for run in [*matlab.values(), *native.values()]:
        validate_run(run)
    maps = {name: {seed: {row['source']: row for row in data[seed]['flows']} for seed in SEEDS}
            for name, data in [('matlab', matlab), ('ns3', native)]}
    indices = bootstrap_indices()
    rows, summaries = [], []
    for source in [None, *SOURCES]:
        mr = [matlab[seed]['totals'] if source is None else maps['matlab'][seed][source] for seed in SEEDS]
        nr = [native[seed]['totals'] if source is None else maps['ns3'][seed][source] for seed in SEEDS]
        for metric in METRICS:
            ms = [row[metric] for row in mr]; ns = [row[metric] for row in nr]
            differences = [m-n if m is not None and n is not None else None for m, n in zip(ms, ns)]
            rs = [residual(m, n) for m, n in zip(ms, ns)]
            for index, seed in enumerate(SEEDS):
                rows.append({'seed': seed, 'source': source, 'metric': metric,
                    'matlab': ms[index], 'ns3': ns[index], 'delta': differences[index],
                    'residual_percent': rs[index],
                    'within_5_percent': abs(rs[index]) <= 5 if rs[index] is not None else None,
                    'within_10_percent': abs(rs[index]) <= 10 if rs[index] is not None else None,
                    'matlab_delivered_sample_size': mr[index]['unique_delivered'],
                    'ns3_delivered_sample_size': nr[index]['unique_delivered'],
                    'same_numbered_seed_is_common_rng_pair': False})
            complete = all(value is not None for value in [*ms, *ns])
            ensemble = residual(math.fsum(ms), math.fsum(ns)) if complete else None
            record = {'source': source, 'metric': metric, 'matlab': describe(ms), 'ns3': describe(ns),
                'delta': describe(differences), 'per_seed_residual_percent': describe(rs),
                'ratio_of_run_means_residual_percent': ensemble,
                'within_10_percent_of_ratio_of_run_means': abs(ensemble) <= 10 if ensemble is not None else None,
                'pooled_ratio_of_count_sums_residual_percent': ensemble if metric != 'mean_delivered_delay_s' else None,
                'seeds_within_5_percent': sum(value is not None and abs(value) <= 5 for value in rs),
                'seeds_within_10_percent': sum(value is not None and abs(value) <= 10 for value in rs),
                'undefined_seeds': [seed for seed, value in zip(SEEDS, rs) if value is None],
                'all_seeds_within_10_percent': all(value is not None and abs(value) <= 10 for value in rs),
                'signed_residual_consistency': 'undefined' if None in differences else
                    'positive_all' if all(value > 0 for value in differences) else
                    'negative_all' if all(value < 0 for value in differences) else
                    'zero_all' if all(value == 0 for value in differences) else 'mixed_or_zero',
                'exploratory_interval': exploratory_interval(ms, ns, indices)}
            if metric == 'mean_delivered_delay_s':
                dm = sum(row['delivered_delay_count'] for row in mr)
                dn = sum(row['delivered_delay_count'] for row in nr)
                pm = math.fsum(row['delivered_delay_sum_s'] for row in mr)/dm if dm else None
                pn = math.fsum(row['delivered_delay_sum_s'] for row in nr)/dn if dn else None
                record['packet_weighted_pooled_conditional_delay'] = {
                    'matlab_mean_s': pm, 'ns3_mean_s': pn,
                    'matlab_delivered_count': dm, 'ns3_delivered_count': dn,
                    'residual_percent': residual(pm, pn), 'descriptive_only': True,
                    'pending_and_dropped_packets_excluded': True}
            summaries.append(record)
    return {'schema': 'csr-tranche25-five-seed-comparison-v1', 'seeds': list(SEEDS),
            'method': METHOD.copy(), 'band_percent': band_percent, 'rows': rows, 'summaries': summaries,
            'band_is_acceptance_gate': False, 'statistical_equivalence_established': False,
            'numerical_parity_established': False,
            'limitations': ['Five runs per engine give fragile exploratory uncertainty, not an equivalence test.',
                'Seed labels identify configuration choices, not cross-engine packet pairing or common random numbers.',
                'Delay is conditional on first unique delivery by 6000 seconds; pending and dropped applications are excluded.',
                'Historical seeds were selected and inspected during diagnostics; intervals are not prospective confirmatory inference.',
                'A ratio interval inside the practical band does not itself establish numerical parity.']}


analyze_case = previous.analyze_case
verify_seed_derivation = previous.verify_seed_derivation


def verify_native_suite(source_root):
    root = Path(source_root)/'evidence/tranche-25-ns3-reference'
    suite = json_object(root/'manifest.json')
    require(suite.get('schema') == 'csr-tranche25-native-suite-v1' and suite.get('status') == 'completed'
            and suite.get('ns3_source_commit') == PIN and suite.get('engine_commit') == ENGINE
            and suite.get('seeds') == list(FRESH_SEEDS) and suite.get('control_seed') == 129
            and suite.get('observer_enabled') is False and suite.get('matlab_executed') is False
            and suite.get('production_source_unchanged') is True and suite.get('engine_source_unchanged') is True,
            'Native suite identity/completion differs')
    bindings = record_map(suite.get('files'), 'native suite files', sizes=True)
    require(set(bindings) == all_files(root)-{'manifest.json'}, 'Native suite file inventory incomplete')
    for name, row in bindings.items():
        path = safe_path(root, name)
        require(path.is_file() and path.stat().st_size == row['bytes'] and sha256(path) == row['sha256'],
                'Native suite artifact differs: '+name)
    build = json_object(root/'build.json')
    require(build.get('schema') == 'csr-tranche25-native-build-v1' and build.get('status') == 'passed'
            and build.get('ns3_source_commit') == PIN and build.get('engine_commit') == ENGINE
            and build.get('observer_enabled') is False and build.get('production_source_unchanged') is True
            and build.get('engine_source_unchanged') is True
            and build.get('source_tree') == 'b611b233fb369569b98f0914ece24d029ccc2f42'
            and build.get('engine_tree') == 'f30343185fb057e3a9cdd54f496cca0cef49ae23',
            'Native rebuilt source/engine provenance differs')
    control = json_object(root/'control-seed129.json')
    require(suite.get('control_sha256') == sha256(root/'control-seed129.json')
            and control.get('schema') == 'csr-tranche25-native-build-control-v1' and control.get('status') == 'passed'
            and control.get('seed') == 129 and control.get('duration_s') == 6000
            and all(control.get(key) is True for key in ('full_uncompressed_trace_identical',
                'admission_diagnostics_byte_identical', 'unique_application_metrics_identical', 'aggregate_values_identical')),
            'Native seed129 build-control gate did not pass')
    accepted = Path(source_root)/'evidence/tranche-20-ns3-reference/s129'
    fresh = root/'build-provenance/control-s129'
    require(control.get('accepted_manifest_sha256') == sha256(accepted/'manifest.json')
            and control.get('fresh_manifest_sha256') == sha256(fresh/'manifest.json')
            and control.get('accepted_trace_sha256') == sha256(accepted/'ns3-trace.csv.gz'),
            'Native seed129 control references differ')
    original = json_object(accepted/'ns3-aggregates.provenance.json')['input']
    restored = json_object(fresh/'ns3-aggregates.provenance.json')['input']
    strip = lambda value: {key: item for key, item in value.items() if key != 'path'}
    require(control.get('uncompressed_trace_identity') == strip(original) == strip(restored),
            'Native seed129 reconstructed trace identity differs')
    require(json_object(fresh/'native-applications.json') == json_object(accepted/'native-applications.json'),
            'Native seed129 control metrics differ')
    control_manifest = json_object(fresh/'manifest.json')
    require(control_manifest.get('build_sha256') == sha256(root/'build.json') and
            control_manifest.get('runner_sha256') == build.get('runner_sha256'), 'Control uses a different native build')
    control_bindings = record_map(control_manifest.get('files'), 'native control files', sizes=True)
    require(control_bindings['app-admission-diagnostics.csv']['sha256'] == sha256(accepted/'app-admission-diagnostics.csv'),
            'Native seed129 control admission bytes differ')
    return build


def verify_native(source_root, seed, *, verified_build=None):
    require(seed in FRESH_SEEDS, 'Wrong fresh native seed')
    source_root = Path(source_root); root = source_root/'evidence/tranche-25-ns3-reference'; directory = root/f's{seed}'
    build = verified_build if verified_build is not None else verify_native_suite(source_root)
    manifest = json_object(directory/'manifest.json')
    require(manifest.get('schema') == 'csr-tranche25-native-reference-v1' and manifest.get('status') == 'completed'
            and manifest.get('ns3_source_commit') == PIN and manifest.get('engine_commit') == ENGINE
            and manifest.get('observer_enabled') is False and manifest.get('build_sha256') == sha256(root/'build.json')
            and manifest.get('runner_sha256') == build.get('runner_sha256'), 'Native run/build identity mismatch')
    bindings = record_map(manifest.get('files'), 'native files', sizes=True)
    require(set(bindings) == all_files(directory)-{'manifest.json'}, 'Native case file inventory incomplete')
    for name, row in bindings.items():
        path = safe_path(directory, name)
        require(path.is_file() and path.stat().st_size == row['bytes'] and sha256(path) == row['sha256'],
                'Native artifact mismatch: '+name)
    for stage in ('run_ns3', 'aggregate_ns3'):
        require(manifest.get('stages', {}).get(stage, {}).get('exit_code') == 0, 'Native stage failed')
    require(manifest.get('stages') == json_object(directory/'execution-stages.json'), 'Native execution stage receipt differs')
    parent = source_root/'scenarios/benchmarks/campus_multihop_6000.csv'; derived = directory/'scenario.csv'
    changes = verify_seed_derivation(parent, derived, seed); recipe = json_object(directory/'seed-recipe.json')
    require(recipe == manifest.get('seed_recipe') and recipe.get('parent_sha256') == sha256(parent)
            and recipe.get('scenario_sha256') == sha256(derived) and recipe.get('field_changes') == changes
            and recipe.get('only_run_seed_changed') is True and recipe.get('seed') == seed, 'Native seed recipe binding mismatch')
    case = manifest.get('case', {})
    require(case.get('seed') == seed and case.get('case_id') == f's{seed}' and case.get('duration_s') == 6000
            and case.get('scenario') == 'blue_radio_campus-multihop' and case.get('bucket_width_s') == 60
            and case.get('scenario_sha256') == sha256(derived), 'Native case identity mismatch')
    result = native_metrics.native_applications(directory)
    require(result == json_object(directory/'native-applications.json'), 'Native application reconstruction mismatch')
    require(result['totals']['attempts'] == 1710000 and len(result['flows']) == len(SOURCES)
            and {flow['source'] for flow in result['flows']} == set(SOURCES), 'Native traffic population mismatch')
    result['input_provenance'] = {'original_sha256': sha256(parent), 'derived_sha256': sha256(derived),
                                 'seed': seed, 'field_changes': changes}
    return result
