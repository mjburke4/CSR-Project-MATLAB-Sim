"""Independent source-4 diagnostic accounting and event-population review."""
import csv
import io
import json
import math
from collections import Counter
from pathlib import Path
from zipfile import ZipFile
from audit_inputs import digest, WORKSPACE, BASE

def main():
    result_path = BASE / 'source4/source4.json'
    report = json.loads(result_path.read_text())
    accepted = json.loads((WORKSPACE / 't20-return-review/analysis/review.json').read_text())
    checks = []
    for input_row in report['input_files']:
        assert digest(WORKSPACE / input_row['path']) == input_row['sha256']
    for row in report['seeds']:
        seed = row['seed']
        if seed == 128:
            with ZipFile(WORKSPACE / 'csr20/evidence/t19/owner.zip') as archive:
                applications = list(csv.DictReader(io.StringIO(archive.read('a128/analysis/applications.csv').decode('utf-8-sig'))))
            obs = accepted['reused_seed128']['observations']
        else:
            with (WORKSPACE / f't20-return-review/owner/s{seed}/analysis/applications.csv').open(newline='') as stream:
                applications = list(csv.DictReader(stream))
            obs = accepted['cases'][f's{seed}']['observations']
        source_apps = {int(a['PacketId']): a for a in applications if int(a['SourceId']) == 4}
        outcome = Counter(a['Outcome'] for a in source_apps.values())
        m, n, dec = row['matlab_source4'], row['native_source4'], row['decomposition']
        assert len(source_apps) == m['admitted']
        for key in ('delivered', 'dropped', 'pending'):
            assert outcome[key] == m[key]
        assert sum(outcome.values()) == m['admitted']
        assert dec['delivery_delta'] == m['delivered'] - n['unique_delivered']
        assert dec['admission_delta'] == m['admitted'] - n['admitted']
        assert dec['native_undelivered'] == n['admitted'] - n['unique_delivered']
        assert dec['matlab_undelivered'] == m['dropped'] + m['pending']
        assert dec['delivery_delta'] == dec['admission_delta'] - dec['undelivered_delta']
        assert dec['within_ten_percent_delivery_band'] == (10 * abs(dec['delivery_delta']) <= n['unique_delivered'])
        terminal = {pid: a for pid, a in source_apps.items() if a['Outcome'] == 'dropped'}
        hops = [e for e in obs['hop_episodes'] if e['source'] == 4]
        failures = [e for e in hops if e['release'] and e['release']['event'] == 'hop_failed']
        terminal_matches = [e for e in failures if e['packet_id'] in terminal and abs(float(terminal[e['packet_id']]['LastEventSeconds']) - e['release']['time_s']) <= 1e-8]
        assert {e['packet_id'] for e in terminal_matches} == set(terminal)
        assert len(terminal_matches) == len(terminal)
        episode_checks = 0
        for h in row['hops']:
            matching = [e for e in obs['hop_episodes'] if (e['node'], e['peer'], e['source']) == (h['node'], h['peer'], h['source'])]
            assert len(matching) == h['episodes'] == sum(h['completion_counts'].values())
            assert h['local_at_node'] == (h['node'] == h['source'])
            assert h['retry_requests'] == sum(h['retry_wait_completion_counts'].values())
            assert h['capacity_retention_completed']['n'] + h['capacity_retention_censored']['n'] == len(matching)
            for ep in matching:
                assert ep['admit']['time_s'] <= 6000
                end = ep['release']['time_s'] if ep['release'] else 6000
                assert end >= ep['admit']['time_s'] and end <= 6000 + 1e-8
                assert math.isclose(ep['capacity_retention_s'], end - ep['admit']['time_s'], abs_tol=1e-8)
                for request_wait in ep['retry_request_waits']:
                    assert request_wait['seconds'] >= -1e-8
                episode_checks += 1
        for custody in row['custody']:
            assert custody['released'] + custody['pending_at_stop'] == custody['episodes']
            assert custody['enqueue_to_first_submit']['n'] == custody['submitted']
            assert custody['enqueue_to_release']['n'] == custody['released']
            assert custody['censored_enqueue_to_stop']['n'] == custody['pending_at_stop']
            for field in ['enqueue_to_first_submit', 'enqueue_to_release', 'censored_enqueue_to_stop']:
                stats = custody[field]
                assert stats['n'] == 0 or 0 <= stats['mean_s'] <= stats['maximum_s'] <= 6000
        for population in row['ownership']:
            for key in ('hop_data_capacity', 'nwk_custody'):
                stats = population[key]
                assert 0 <= stats['mean_active_300_to_6000s'] <= stats['peak_count']
                assert 0 <= stats['mean_6000s'] <= stats['peak_count']
        checks.append({'seed': seed, 'source4_applications': len(source_apps), 'final_drop_identities_matched': len(terminal_matches),
            'all_source4_failure_episodes': len(failures), 'failure_episodes_with_other_final_outcome': len(failures) - len(terminal_matches),
            'hop_episode_capacity_intervals_checked': episode_checks, 'conservation_passed': True})
    out = {'schema': 'csr-tranche21-independent-source4-review-v1', 'passed': True, 'seeds': checks,
        'identity': 'Original application source independently matched to PacketId inventory; failed-hop callbacks not equated with terminal drops.',
        'censoring': 'Released and pending populations are separate; pending ages end at 6000 seconds. Retry waits explicitly pair to next observed hop_sent, not unique queued-retry lineage.',
        'scope': 'Native unmatched sends remain undelivered, not classified as losses. Arithmetic decompositions are descriptive and do not prove causality.',
        'matlab_executed_by_reviewer': False,
        'code_and_report_sha256': {f'source4/{p.name}': digest(p) for p in (BASE / 'source4').glob('*') if p.is_file()}}
    (Path(__file__).parent / 'source4-review.json').write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps(out, indent=2))

if __name__ == '__main__':
    main()
