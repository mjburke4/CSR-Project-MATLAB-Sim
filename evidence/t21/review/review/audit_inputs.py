"""Independent T21 source/evidence binding and descriptive-target audit."""
import csv
import hashlib
import json
import math
from collections import Counter
from decimal import Decimal
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
WORKSPACE = BASE.parent
SOURCE = WORKSPACE / 'csr20'
PACKAGE = WORKSPACE / 't20-return-review/package'
OWNER = WORKSPACE / 't20-return-review/owner'

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while data := stream.read(1024 * 1024):
            h.update(data)
    return h.hexdigest()

def read(path):
    return json.loads(path.read_text())

def main():
    acceptance = read(PACKAGE / 'acceptance.json')
    assert acceptance['accepted'] and acceptance['tests_passed'] == 716
    verified = {}
    for label, filename, key in [
        ('owner_archive', 'original-t20.zip', 'owner_archive_sha256'),
        ('candidate', 'candidate.json', 'candidate_sha256'),
        ('source_snapshot', 'source.json', 'source_snapshot_sha256'),
        ('reference_snapshot', 'references.json', 'reference_snapshot_sha256'),
    ]:
        observed = digest(PACKAGE / filename)
        assert observed == acceptance[key], (label, observed)
        verified[label] = observed
    assert digest(SOURCE / 'evidence/tranche-20-candidate.json') == acceptance['candidate_sha256']
    sources, refs = read(OWNER / 'source.json'), read(OWNER / 'references.json')
    for label, bindings in [('source', sources), ('reference', refs)]:
        assert len({b['path'] for b in bindings}) == len(bindings)
        for row in bindings:
            path = SOURCE / row['path']
            assert digest(path) == row['sha256'], (label, row['path'])
            if 'bytes' in row:
                assert path.stat().st_size == row['bytes']
    assert len(sources) == 376 and len(refs) == 98
    target = read(BASE / 'target/target-screen.json')
    for path, expected in target['input_sha256'].items():
        assert digest(PACKAGE / path) == expected
    assert target['target_percent'] == 10
    assert not target['band_is_structural_gate']
    assert not target['statistical_equivalence_established']
    with (PACKAGE / 'independent-findings/comparisons.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 21
    target_rows = {(r['seed'],r['source'],r['metric']): r for r in target['comparisons']}
    counts = Counter()
    exclusions = []
    for row in rows:
        for metric, mkey, nkey in [
            ('admitted','matlab_admitted','ns3_admitted'),
            ('unique_delivered','matlab_delivered','ns3_unique_delivered'),
            ('mean_delivered_delay_s','matlab_mean_delivered_latency_s','ns3_mean_first_delivery_latency_s'),
        ]:
            m, n = Decimal(row[mkey]), Decimal(row[nkey])
            percent = Decimal(100) * (m / n - 1)
            observed = target_rows[int(row['seed']), row['source'], metric]
            assert math.isclose(observed['difference_percent'], float(percent), rel_tol=1e-12, abs_tol=1e-12)
            assert observed['within_10_percent'] == (abs(m-n) <= n/Decimal(10))
            assert observed['within_5_percent'] == (abs(m-n) <= n/Decimal(20))
            group = 'whole_network' if row['source'] == 'total' else 'individual_flows'
            counts[metric, group, 'total'] += 1
            counts[metric, group, 'within10'] += observed['within_10_percent']
            counts[metric, group, 'within5'] += observed['within_5_percent']
            if metric == 'unique_delivered' and group == 'individual_flows' and not observed['within_10_percent']:
                exclusions.append({'seed': int(row['seed']), 'source': int(row['source']), 'difference_percent': float(percent)})
    for row in target['summaries']:
        key = row['metric'], row['group']
        assert row['comparisons'] == counts[*key, 'total']
        assert row['within_10_percent'] == counts[*key, 'within10']
        assert row['within_5_percent'] == counts[*key, 'within5']
    for row in target['pooled_counts']:
        metric = row['metric']; source = row['source']
        values = [r for r in target_rows.values() if r['source'] == source and r['metric'] == metric]
        m, n = sum(r['matlab'] for r in values), sum(r['ns3'] for r in values)
        assert row['matlab_sum'] == m and row['ns3_sum'] == n
        assert math.isclose(row['ratio_of_sums_percent'], 100 * (m-n)/n, abs_tol=1e-12)
        assert math.isclose(row['mean_per_seed_difference_percent'], sum(r['difference_percent'] for r in values)/3, abs_tol=1e-12)
        assert row['all_seeds_within_10_percent'] == all(r['within_10_percent'] for r in values)
    result = {
        'schema': 'csr-tranche21-independent-input-target-review-v1',
        'passed': True,
        'source_bindings_unchanged': len(sources),
        'reference_bindings_unchanged': len(refs),
        'matlab_sources_unchanged': sum(r['path'].endswith('.m') for r in sources),
        'accepted_t20_inputs_verified': verified,
        'target_math_comparisons_verified': len(target_rows),
        'scope': 'Existing accepted evidence; T21 descriptive target revised to ±10%. No MATLAB or native simulator execution by reviewer.',
        'summary': target['summaries'],
        'flow_deliveries_outside_10_percent': exclusions,
        'assessment': [
            '13 of 18 individual flow delivery comparisons meet ±10%; all three whole-network delivery comparisons meet the target.',
            'Source 4 pooled delivery residual is within ±10% but seed 128 remains outside; do not claim every seed meets the target.',
            'Seeds 128 and 129 source 7 and 8 delivery comparisons are within ±10%; seed 130 remains substantially outside in opposing directions.',
            'Three seeds are a descriptive sample and do not establish statistical equivalence.',
            'Mean delivered delay is conditional on different delivered populations, and its agreement should not be inferred from delivery-count agreement.',
        ],
        'checked_code_sha256': {'compare_target.py': digest(BASE / 'compare_target.py'), 'review/audit_inputs.py': digest(Path(__file__))},
        'remaining_gate': 'Review conservation, event identities, bounded observation windows, and causal wording in forthcoming diagnostic outputs.'
    }
    (Path(__file__).parent / 'input-target-review.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['accepted_t20_inputs_verified','assessment','checked_code_sha256']} ,indent=2))

if __name__ == '__main__':
    main()
