#!/usr/bin/env python3
"""Verify saved aggregate arithmetic only. Does not run MATLAB or native models."""
from decimal import Decimal, localcontext
import json
from pathlib import Path


def verify(path):
    summary = json.loads(path.read_text(encoding='utf-8'))
    assert summary['schema'] == 'csr-current-policy-descriptive-summary-v1'
    assert summary['matlab_seeds'] == [135, 136, 137]
    assert summary['native_seeds'] == [135, 137, 140]
    assert summary['runs_per_engine'] == 3
    assert summary['interval_seconds'] == {
        'start': 0, 'start_inclusive': True, 'end': 6000, 'end_inclusive': False}
    assert [r['source_id'] for r in summary['rows']] == [2, 3, 4, 5, 7, 8]
    checked = 0
    with localcontext() as context:
        context.prec = 50
        for row in summary['rows']:
            matlab, native = row['matlab'], row['native']
            for cohort in (matlab, native):
                assert len(cohort['deliveries_by_run']) == summary['runs_per_engine']
                assert all(isinstance(v, int) and v >= 0 for v in cohort['deliveries_by_run'])
                assert sum(cohort['deliveries_by_run']) == cohort['first_deliveries']
                assert cohort['admitted'] - cohort['first_deliveries'] == cohort['undelivered_at_cutoff']
                assert cohort['undelivered_at_cutoff'] >= 0
                assert cohort['first_deliveries'] > 0
            ratios = {
                'admissions': Decimal(matlab['admitted']) / native['admitted'],
                'deliveries': Decimal(matlab['first_deliveries']) / native['first_deliveries'],
                'pooled_delivered_latency':
                    (Decimal(matlab['delivered_latency_sum_seconds']) / matlab['first_deliveries']) /
                    (Decimal(native['delivered_latency_sum_nanoseconds']) /
                     Decimal(10 ** 9) / native['first_deliveries']),
            }
            for metric, actual in ratios.items():
                assert actual == Decimal(row['matlab_over_native_ratios'][metric]), (row['source_id'], metric)
                within = Decimal('0.8') <= actual <= Decimal('1.2')
                assert row['point_estimate_within_20_percent'][metric] == within
                assert within
                checked += 1
        matlab_total = sum(r['matlab']['first_deliveries'] for r in summary['rows'])
        native_total = sum(r['native']['first_deliveries'] for r in summary['rows'])
        aggregate = summary['aggregate']
        assert matlab_total == aggregate['matlab_first_deliveries'] == 35678
        assert native_total == aggregate['native_first_deliveries'] == 35479
        assert Decimal(aggregate['delivery_ratio']) == Decimal(matlab_total) / native_total
        assert Decimal(aggregate['delivery_percent_difference']) == (Decimal(matlab_total) / native_total - 1) * 100
    assert checked == 18 and summary['all_18_source_metric_point_estimates_within_20_percent'] is True
    assert summary['formal_acceptance'] is False
    assert summary['causal_model_fix_established'] is False
    assert summary['repository_packaging']['simulation_executed_for_this_update'] is False
    assert summary['repository_packaging']['new_relocatable_adapter_executed'] is False
    return {'passed': True, 'source_metric_checks': checked,
            'scope': 'Saved summary arithmetic and explicit claim boundaries only; no simulator execution.'}


if __name__ == '__main__':
    print(json.dumps(verify(Path(__file__).with_name('SUMMARY.json')), indent=2))
