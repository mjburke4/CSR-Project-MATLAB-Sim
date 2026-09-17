"""Independent native diagnostic checks using authenticated derived evidence."""
import csv
import json
import math
from collections import Counter
from pathlib import Path
from audit_inputs import digest, WORKSPACE, BASE

def main():
    accepted = json.loads((WORKSPACE/'t20-return-review/analysis/review.json').read_text())
    summaries = []
    for seed in (128, 129, 130):
        path = BASE/f'native/s{seed}.json'
        native = json.loads(path.read_text())
        source = WORKSPACE/'csr20'/('evidence/tranche-7-ns3-reference/campus_multihop_6000' if seed == 128 else f'evidence/tranche-20-ns3-reference/s{seed}')
        assert digest(source/'manifest.json') == native['input']['manifest_sha256']
        assert digest(source/'ns3-trace.csv.gz') == native['input']['trace_gzip_sha256']
        proof = json.loads((source/'ns3-aggregates.provenance.json').read_text())
        assert proof['input']['sha256'] == native['input']['trace_raw_sha256']
        assert proof['input']['size_bytes'] == native['input']['trace_raw_bytes']
        assert native['input']['last_event_time_s'] < 6000
        for flow in native['flows']:
            reference = next(r for r in accepted['native_application_reference'][str(seed)]['flows'] if r['source'] == flow['source'])
            for field in ['admitted', 'unique_delivered', 'duplicate_delivery_events', 'unmatched_sends']:
                assert flow[field] == reference[field]
            assert flow['admitted'] == flow['unique_delivered'] + flow['unmatched_sends']
            assert flow['first_delivery_delay_s']['count'] == flow['unique_delivered']
        with (BASE/f'native/s{seed}-flow-timeline.csv').open(newline='') as stream:
            bins = list(csv.DictReader(stream))
        assert len(bins) == 120
        for flow in native['flows']:
            rows = [r for r in bins if int(r['source']) == flow['source']]
            assert len(rows) == 20
            for output, field in [('admitted','admitted'), ('unique_delivered','unique_delivered'), ('duplicate_events','duplicate_delivery_events')]:
                assert sum(int(r[output]) for r in rows) == flow[field]
        assert native['nsdp_snapshot_mismatch_count'] == 0
        assert native['queue_snapshot_mismatch_count'] == 0
        assert not native['unmatched_episode_events']
        if seed == 128:
            assert not native['nsdp_state'] and not native['residence'], 'Historical missing instrumentation is unavailable, not fabricated'
        else:
            enqueues = Counter((r['node'],r['source']) for r in native['pending_enqueues'])
            hops = Counter((r['node'],r['source']) for r in native['pending_hop'])
            for row in native['pending_enqueues']:
                assert row['enqueue_s'] >= 300
                assert math.isclose(row['age_at_stop_s'], 6000-row['enqueue_s'], abs_tol=1e-9)
            for row in native['pending_hop']:
                assert math.isclose(row['age_at_stop_s'], 6000-row['admission_s'], abs_tol=1e-9)
            for state in native['nsdp_state']:
                key = state['node'],state['source']
                assert state['last'] == enqueues[key]+hops[key]
                assert 0 <= state['time_weighted_mean_300_6000'] <= state['maximum']
                assert 0 <= state['seconds_at_or_above_16_300_6000'] <= 5700
            for queue in native['shared_nwk_queue']:
                assert queue['last'] == sum(v for (n,s),v in enqueues.items() if n == queue['node'])
            for population in native['residence']:
                key = population['node'],population['source']
                assert 'hop_residence_s' not in population, 'DACK feedback must not be called capacity release'
                queued = population['nwk_queue_wait_s']['count']
                completed = population['hop_admission_to_nsdp_release_completion_s']['count']
                assert queued == completed + hops[key]
                for field in ['nwk_queue_wait_s', 'hop_admission_to_nsdp_release_completion_s', 'enqueue_to_nsdp_release_completion_s']:
                    stat = population[field]
                    assert not stat['count'] or 0 <= stat['mean'] <= stat['max'] <= 6000
            with (BASE/f'native/s{seed}-gateway-routes.csv').open(newline='') as stream:
                routes = list(csv.DictReader(stream))
            late = [r for r in routes if float(r['time_s']) >= 300]
            assert not late
        summaries.append({'seed':seed,'application_flows_and_120_bins_match_accepted':True,'nsdp_and_queue_conservation_passed':True,
            'historical_telemetry_available':seed != 128,'last_raw_event_time_s':native['input']['last_event_time_s'],
            'native_node8_relay7_nsdp': next((r for r in native['nsdp_state'] if r['node']==8 and r['source']==7),None)})
    output = {'schema':'csr-tranche21-independent-native-diagnostic-review-v1','passed':True,'seeds':summaries,
        'review_method':'Independent recomputation of counts/conservation from derived full-trace output, authenticated against raw-gzip/provenance hashes and accepted T20 application counts. Large raw traces were not reparsed by this reviewer.',
        'metrics':'Native admission to NSDP release/completion ends at ACK/no_ack/DACK feedback; delayed DACK capacity release is a separate endpoint. Queue waits and delivery delays are completed-only populations.',
        'separate_capacity_review':'See native-capacity-review.json for actual-capacity-release and terminal-outcome join validation.',
        'source_files_sha256':{p.name:digest(p) for p in (BASE/'native').glob('*.py')},
        'output_json_sha256':{f's{s}.json':digest(BASE/f'native/s{s}.json') for s in (128,129,130)}}
    (Path(__file__).parent/'native-review.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(output,indent=2))

if __name__ == '__main__':
    main()
