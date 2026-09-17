"""Independent validation of native application-outcome and capacity joins."""
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from audit_inputs import digest, BASE

def csvrows(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))

def identity(row):
    return tuple(int(row[k]) for k in ('node','peer','source','destination','sequence','hop_sequence'))

def main():
    summaries = []
    for seed in (129, 130):
        root = BASE/'native'
        data = json.loads((root/f's{seed}-outcome-joins.json').read_text())
        native = json.loads((root/f's{seed}.json').read_text())
        assert data['input_binding'] == native['input']
        assert not data['capacity_release_without_admission']
        episodes = csvrows(root/f's{seed}-capacity-episodes.csv')
        completions = csvrows(root/f's{seed}-completion-outcomes.csv')
        by_id = {identity(r):r for r in episodes}
        assert len(by_id) == len(episodes)
        pending = {identity(r):r for r in data['capacity_pending_at_stop']}
        assert len(pending) == len(data['capacity_pending_at_stop'])
        assert not (by_id.keys() & pending.keys())
        completed = Counter((int(r['node']),int(r['source'])) for r in episodes)
        pending_by_flow = Counter((int(r['node']),int(r['source'])) for r in pending.values())
        admitted = Counter()
        for row in data['threshold_histograms']:
            admitted[row['node'],row['source']] += row['admissions']
        assert admitted == completed + pending_by_flow
        for row in pending.values():
            assert math.isclose(row['age_at_stop_s'],6000-row['admission_s'],abs_tol=1e-8)
        for row in episodes:
            start, end = float(row['admission_s']),float(row['release_s'])
            assert 300 <= start <= end < 6000
            assert math.isclose(float(row['capacity_retention_s']),end-start,abs_tol=1e-8)
        delayed_dack = active_dack = 0
        outcome = Counter()
        for row in completions:
            ident = identity(row)
            received = row['unique_delivered_by_stop'] == 'True'
            outcome[int(row['node']),int(row['source']),row['reason'],received] += 1
            if received:
                assert row['first_delivery_s'] and 300 <= float(row['first_delivery_s']) < 6000
                assert (row['delivery_after_hop_completion']=='True') == (float(row['first_delivery_s'])>float(row['completion_s']))
            else:
                assert not row['first_delivery_s'] and not row['delivery_after_hop_completion']
            if row['reason']=='dack':
                assert row['capacity_released']=='0' and row['nsdp_released']=='1'
                if ident in by_id:
                    capacity=by_id[ident]
                    assert capacity['release_event']=='hop_capacity_release'
                    assert float(capacity['release_s'])>float(row['completion_s'])
                    delayed_dack += 1
                else:
                    assert ident in pending
                    active_dack += 1
            else:
                assert row['capacity_released']=='1'
                assert ident in by_id
                assert by_id[ident]['release_event']=='hop_completion'
                assert float(by_id[ident]['release_s'])==float(row['completion_s'])
        reported = Counter({(r['node'],r['source'],r['hop_completion_reason'],r['unique_delivered_by_stop']):r['count'] for r in data['source_node_outcome_counts']})
        assert reported == outcome
        durations = defaultdict(list)
        for row in episodes:
            durations[int(row['node']),int(row['source'])].append(float(row['capacity_retention_s']))
        for row in data['capacity_retention_completed']:
            values=durations[row['node'],row['source']]
            assert row['count']==len(values)
            assert math.isclose(row['mean'],sum(values)/len(values),rel_tol=1e-12)
            assert row['max']==max(values)
        summaries.append({'seed':seed,'completed_capacity_episodes_checked':len(episodes),
            'pending_capacity_episodes_checked':len(pending),'DACK_delayed_capacity_release_joins':delayed_dack,
            'DACK_still_held_at_stop':active_dack,
            'source4_node4_no_ack_with_delivery':outcome[4,4,'no_ack',True],
            'source4_node4_no_ack_without_delivery':outcome[4,4,'no_ack',False],
            'capacity_conservation_and_endpoint_semantics_passed':True})
    out={'schema':'csr-tranche21-independent-native-capacity-review-v1','passed':True,'seeds':summaries,
        'scope':'Within-run identities include node, peer, original source, destination, application sequence and hop sequence. DACK NSDP release is not equated with delayed capacity release; unreleased episodes are censored at 6000 seconds.',
        'review_method':'Reviewed raw-join implementation and independently checked generated CSV identities, cohort counts, durations, and pending/completed accounting; did not reparse raw multi-gigabyte trace.',
        'causal_limit':'A no_ack HOP completion is not automatically an application drop. A later or earlier unique gateway delivery takes precedence for application delivery outcome.',
        'reviewed_sha256':{p.name:digest(p) for p in (BASE/'native').glob('*') if p.is_file() and (p.name=='join_outcomes.py' or any(k in p.name for k in ['outcome-joins','completion-outcomes','capacity-episodes']))}}
    (Path(__file__).parent/'native-capacity-review.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))

if __name__=='__main__':
    main()
