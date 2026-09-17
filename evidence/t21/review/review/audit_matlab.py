"""Independent population, censoring and endpoint review for T21 MATLAB diagnosis."""
import json
import math
from collections import Counter
from pathlib import Path
from audit_inputs import digest, WORKSPACE, BASE

def close(a, b):
    assert math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-6), (a, b)

def sweep(intervals, lo=300., hi=6000.):
    events = Counter()
    for start, stop in intervals:
        a, b = max(lo, start), min(hi, stop)
        if b > a:
            events[a] += 1
            events[b] -= 1
    integral = saturated = count = 0
    previous = lo
    for t, delta in sorted(events.items()):
        integral += count * (t-previous)
        saturated += (t-previous) if count >= 16 else 0
        count += delta
        assert count >= 0
        previous = t
    assert count == 0
    return integral, saturated

def main():
    report = json.loads((BASE / 'matlab/matlab_node8.json').read_text())
    accepted = json.loads((WORKSPACE / 't20-return-review/analysis/review.json').read_text())
    assert digest(WORKSPACE / 't20-return-review/analysis/review.json') == report['t20_review_sha256']
    assert digest(WORKSPACE / 't20-return-review/owner/metadata.json') == report['t20_metadata_sha256']
    assert digest(WORKSPACE / 'csr20/evidence/t19/owner.zip') == report['accepted_t19_owner_sha256']
    assert not report['matlab_executed'] and not report['native_executed'] and not report['simulation_source_modified']
    for path, sha in report['source_files_read_sha256'].items():
        assert digest(WORKSPACE / path) == sha
    checks = []
    for result in report['results']:
        seed = result['seed']
        obs = accepted['reused_seed128']['observations'] if seed == 128 else accepted['cases'][f's{seed}']['observations']
        for cohort in result['cohorts']:
            node, source = cohort['node'], cohort['source']
            hs = [e for e in obs['hop_episodes'] if (e['node'], e['source']) == (node, source)]
            cs = [e for e in obs['nwk_custody_episodes'] if (e['node'], e['source']) == (node, source)]
            assert cohort['local_at_node'] == (node == source)
            assert cohort['hop_admitted'] == len(hs)
            assert cohort['hop_acks'] + cohort['hop_failed'] + cohort['hop_dack_expired'] + cohort['hop_pending_at_stop'] == len(hs)
            assert cohort['nwk_enqueued'] == len(cs)
            assert cohort['nwk_released'] + cohort['nwk_pending_at_stop'] == len(cs)
            assert cohort['nwk_submitted'] + cohort['nwk_waiting_first_submit_at_stop'] == len(cs)
            assert all(e['enqueue']['time_s'] >= 300 for e in cs)
            assert all(e['submit'] or e['release'] is None for e in cs), 'Released unsubmitted custody would change pending wait interpretation'
            populations = {
                'nwk_custody_app_seconds': [(e['enqueue']['time_s'], e['release']['time_s'] if e['release'] else 6000) for e in cs],
                'nwk_pre_first_submit_app_seconds': [(e['enqueue']['time_s'], e['submit']['time_s'] if e['submit'] else 6000) for e in cs],
                'hop_capacity_app_seconds': [(e['admit']['time_s'], e['release']['time_s'] if e['release'] else 6000) for e in hs],
                'dack_hold_app_seconds': [(e['dack']['time_s'], e['release']['time_s'] if e['release'] else 6000) for e in hs if e['dack']],
            }
            for field, intervals in populations.items():
                area, high = sweep(intervals)
                close(area, cohort[field])
                if field == 'nwk_custody_app_seconds':
                    close(high, cohort['observed_nwk_custody_seconds_at_or_above_16'])
            close(cohort['nwk_custody_app_seconds'], cohort['nwk_completed_custody_app_seconds'] + cohort['nwk_censored_custody_elapsed_app_seconds'])
            close(cohort['nwk_pre_first_submit_app_seconds'], cohort['nwk_completed_first_submit_wait_app_seconds'] + cohort['nwk_censored_first_submit_elapsed_app_seconds'])
            close(cohort['hop_capacity_app_seconds'], cohort['hop_completed_capacity_app_seconds'] + cohort['hop_censored_capacity_elapsed_app_seconds'])
            for area_name, mean_name in [('nwk_custody_app_seconds','mean_nwk_custody_traffic_window'), ('nwk_pre_first_submit_app_seconds','mean_nwk_pre_first_submit_traffic_window'), ('hop_capacity_app_seconds','mean_hop_capacity_traffic_window'), ('dack_hold_app_seconds','mean_dack_capacity_traffic_window')]:
                close(cohort[area_name]/5700, cohort[mean_name])
            temporal = [x for x in result['timeline'] if (x['node'], x['source']) == (node, source)]
            assert len(temporal) == 20
            for field, dest in [('nwk_enqueued','nwk_enqueued'), ('nwk_submitted','nwk_submitted'), ('nwk_released','nwk_released'), ('hop_admitted','hop_admitted'), ('hop_sent_callbacks','hop_sent_callbacks')]:
                assert sum(t[field] for t in temporal) == cohort[dest]
            close(sum(t['mean_nwk_custody']*300 for t in temporal), cohort['nwk_custody_app_seconds'])
        prefix = result['admission_trace_prefix']
        assert prefix['rows'] == 100000 and prefix['omitted_attempt_rows'] == 1610000
        assert prefix['last_time_s'] < 634
        assert result['endpoint_counts_verified'] and not result['routing']['route_change_times_available']
        assert all(row['sent_indications_without_owned_confirmation'] == 0 for row in result['hop_callback_coverage'])
        checks.append({'seed': seed, 'cohort_populations_checked': len(result['cohorts']), 'protocol_callback_rows_verified_by_diagnostic': result['episode_callback_rows_verified'], 'independent_interval_sweep_matches': True, 'conservation_and_censoring_passed': True})
    output = {'schema': 'csr-tranche21-independent-matlab-review-v1', 'passed': True, 'seeds': checks,
        'units': 'Population integrals are application-seconds; time-weighted means are applications, not wait seconds. Completed wait distributions are seconds.',
        'scope': 'All accepted evidence reused. Full counters, generated-event counts and scheduled attempts support 300-second blocked totals; blocked-reason timing beyond the 100000-row prefix is unavailable.',
        'routing': 'Stable DATA peers are observed; absence of transient route changes is not claimed.',
        'matlab_executed_by_reviewer': False,
        'reviewed_sha256': {p.name:digest(p) for p in (BASE/'matlab').glob('*') if p.is_file()}}
    (Path(__file__).parent/'matlab-review.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(output,indent=2))

if __name__ == '__main__':
    main()
