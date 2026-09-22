"""Numerical-meaning and corruption tests; no simulation execution."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tranche25_metrics as m


def run(admitted=100, delivered=90, delay=10):
    flows = [{'source': source, 'admitted': admitted, 'unique_delivered': delivered,
              'delivered_delay_count': delivered, 'delivered_delay_sum_s': delivered*delay,
              'mean_delivered_delay_s': delay if delivered else None} for source in m.SOURCES]
    return {'flows': flows, 'totals': {'admitted': admitted*6, 'unique_delivered': delivered*6,
            'delivered_delay_count': delivered*6, 'delivered_delay_sum_s': delivered*delay*6,
            'mean_delivered_delay_s': delay if delivered else None}}


def ensemble():
    return {seed: run() for seed in m.SEEDS}


class MetricsMeaningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.identical = m.compare_seeds(ensemble(), ensemble())

    def test_population_is_all_five_runs_all_six_flows_and_network(self):
        self.assertEqual(len(self.identical['rows']), 105)
        self.assertEqual(len(self.identical['summaries']), 21)
        self.assertEqual({row['seed'] for row in self.identical['rows']}, set(m.SEEDS))
        self.assertEqual({row['source'] for row in self.identical['rows']}, {None, *m.SOURCES})

    def test_matching_results_cannot_establish_acceptance_or_equivalence(self):
        self.assertFalse(self.identical['statistical_equivalence_established'])
        self.assertFalse(self.identical['numerical_parity_established'])
        self.assertFalse(self.identical['band_is_acceptance_gate'])
        self.assertTrue(all(row['exploratory_interval']['exploratory_only'] for row in self.identical['summaries']))
        self.assertTrue(all(row['exploratory_interval']['degenerate_empirical_distribution'] for row in self.identical['summaries']))

    def test_actual_count_ratio_not_mean_percentage(self):
        matlab = ensemble(); native = ensemble()
        matlab[128] = run(200, 180); native[128] = run(100, 90)
        native[129] = run(1000, 900); matlab[129] = run(1000, 900)
        result = m.compare_seeds(matlab, native)
        row = next(row for row in result['summaries'] if row['source'] is None and row['metric'] == 'admitted')
        self.assertAlmostEqual(row['pooled_ratio_of_count_sums_residual_percent'], 100*100/1400)
        self.assertAlmostEqual(row['per_seed_residual_percent']['mean'], 20)
        self.assertNotAlmostEqual(row['pooled_ratio_of_count_sums_residual_percent'], row['per_seed_residual_percent']['mean'])

    def test_delay_run_mean_differs_from_packet_weighted_mean(self):
        matlab = {seed: run(1000, 10 if seed == 128 else 1000, 100 if seed == 128 else 1) for seed in m.SEEDS}
        native = {seed: run(1000, 1000, 10) for seed in m.SEEDS}
        row = next(row for row in m.compare_seeds(matlab, native)['summaries']
                   if row['source'] == 2 and row['metric'] == 'mean_delivered_delay_s')
        self.assertAlmostEqual(row['matlab']['mean'], 20.8)
        self.assertAlmostEqual(row['ratio_of_run_means_residual_percent'], 108)
        self.assertAlmostEqual(row['packet_weighted_pooled_conditional_delay']['matlab_mean_s'], 5000/4010)
        self.assertIsNone(row['pooled_ratio_of_count_sums_residual_percent'])

    def test_independent_bootstrap_not_paired_equal_seed_labels(self):
        varied = {seed: run(admitted=(index+1)*100, delivered=(index+1)*90) for index, seed in enumerate(m.SEEDS)}
        result = m.compare_seeds(varied, varied)
        row = next(row for row in result['summaries'] if row['source'] is None and row['metric'] == 'admitted')
        interval = row['exploratory_interval']
        self.assertEqual(row['ratio_of_run_means_residual_percent'], 0)
        self.assertLess(interval['lower_residual_percent'], 0)
        self.assertGreater(interval['upper_residual_percent'], 0)

    def test_original_five_percent_flags_preserved_with_ten_percent_target(self):
        matlab = {seed: run(108, 97) for seed in m.SEEDS}
        result = m.compare_seeds(matlab, ensemble())
        row = next(row for row in result['rows'] if row['source'] == 2 and row['metric'] == 'admitted')
        self.assertFalse(row['within_5_percent']); self.assertTrue(row['within_10_percent'])

    def test_undefined_native_count_denominator_not_zero_residual(self):
        native = {seed: run(0, 0) for seed in m.SEEDS}
        result = m.compare_seeds(ensemble(), native)
        row = next(row for row in result['summaries'] if row['source'] == 2 and row['metric'] == 'admitted')
        self.assertIsNone(row['ratio_of_run_means_residual_percent'])
        self.assertIsNone(row['exploratory_interval']['lower_residual_percent'])
        self.assertEqual(row['exploratory_interval']['undefined_draws'], 20000)

    def test_missing_delivery_population_does_not_drop_run_from_uncertainty(self):
        matlab = ensemble(); matlab[128] = run(100, 0)
        result = m.compare_seeds(matlab, ensemble())
        row = next(row for row in result['summaries'] if row['source'] == 2 and row['metric'] == 'mean_delivered_delay_s')
        self.assertIsNone(row['ratio_of_run_means_residual_percent'])
        self.assertIsNone(row['exploratory_interval']['lower_residual_percent'])
        self.assertEqual(row['undefined_seeds'], [128])
        self.assertIsNotNone(row['packet_weighted_pooled_conditional_delay']['matlab_mean_s'])

    def test_partial_zero_bootstrap_denominator_makes_interval_undefined(self):
        native = {seed: run(0, 0) if seed != 132 else run() for seed in m.SEEDS}
        result = m.compare_seeds(ensemble(), native)
        row = next(row for row in result['summaries'] if row['source'] == 2 and row['metric'] == 'admitted')
        self.assertIsNotNone(row['ratio_of_run_means_residual_percent'])
        self.assertIsNone(row['exploratory_interval']['lower_residual_percent'])
        self.assertGreater(row['exploratory_interval']['undefined_draws'], 0)
        self.assertGreater(row['exploratory_interval']['valid_draws'], 0)

    def test_bootstrap_is_reproducible_and_uses_whole_run_indices(self):
        indices = m.bootstrap_indices()
        self.assertEqual(indices, m.bootstrap_indices())
        self.assertEqual(len(indices), 20000)
        self.assertTrue(all(len(a) == len(b) == 5 and all(0 <= index < 5 for index in a+b) for a, b in indices))
        self.assertTrue(any(a != b for a, b in indices))

    def test_type7_percentile_interpolation_is_recorded(self):
        self.assertEqual(m.percentile([0, 10, 20, 30], 25), 7.5)
        self.assertEqual(m.METHOD['percentile_interpolation'], 'linear-type7')

    def test_missing_or_unplanned_seed_rejected(self):
        data = ensemble(); data[133] = data.pop(128)
        with self.assertRaisesRegex(ValueError, 'five predefined'): m.compare_seeds(data, ensemble())

    def test_duplicate_flow_not_hidden_by_dictionary(self):
        data = ensemble(); data[128]['flows'][-1] = copy.deepcopy(data[128]['flows'][0])
        with self.assertRaisesRegex(ValueError, 'Flow populations'): m.compare_seeds(data, ensemble())

    def test_changed_practical_target_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Prespecified'): m.compare_seeds(ensemble(), ensemble(), 5)

    def test_inconsistent_flow_total_rejected(self):
        data = ensemble(); data[128]['totals']['admitted'] += 1
        with self.assertRaisesRegex(ValueError, 'flow/total'): m.compare_seeds(data, ensemble())

    def test_fractional_application_counts_rejected(self):
        data = run(); data['flows'][0]['admitted'] = 100.5
        with self.assertRaisesRegex(ValueError, 'Noninteger'): m.validate_run(data)

    def test_nonfinite_or_boolean_counts_rejected(self):
        for value in (True, float('inf'), float('nan'), -1):
            data = run(); data['flows'][0]['admitted'] = value
            with self.subTest(value=value), self.assertRaises(ValueError): m.validate_run(data)

    def test_delay_sample_count_must_equal_unique_delivery_count(self):
        data = run(); data['flows'][0]['delivered_delay_count'] -= 1
        with self.assertRaisesRegex(ValueError, 'accounting'): m.validate_run(data)

    def test_delay_population_cannot_be_zero_filled_when_empty(self):
        data = run(100, 0); data['flows'][0]['mean_delivered_delay_s'] = 0
        with self.assertRaisesRegex(ValueError, 'null'): m.validate_run(data)

    def test_delay_sum_corruption_rejected(self):
        data = run(); data['flows'][0]['delivered_delay_sum_s'] += 1
        with self.assertRaisesRegex(ValueError, 'sum/mean'): m.validate_run(data)

    def test_deliveries_cannot_exceed_admissions(self):
        with self.assertRaises(ValueError): m.validate_run(run(10, 20))

    def test_native_normalization_requires_delay_population(self):
        with self.assertRaisesRegex(ValueError, 'Missing conditional'): m.normalize_native({'flows': [{'source': 2, 'admitted': 10, 'delivered': 9}]})

    def test_matlab_normalization_does_not_accept_mismatched_whole_totals(self):
        obs = {'totals': {'admitted': 100, 'delivered': 90}, 'flows': [
            {'source': source, 'admitted': 10, 'delivered': 9, 'delivered_latency': {'count': 9, 'mean_s': 10}}
            for source in m.SOURCES]}
        with self.assertRaisesRegex(ValueError, 'flow/total'): m.normalize_matlab(obs)


if __name__ == '__main__': unittest.main()
