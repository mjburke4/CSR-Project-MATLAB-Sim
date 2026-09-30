#!/usr/bin/env python3
"""Reproduce the authorized +/-20% assessment from prior audited measurements."""
from pathlib import Path
import csv
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'node8_1200'
source = ROOT/'terminal6000_return/accounting/source_targets.csv'
accounting = ROOT/'terminal6000_return/accounting/audit.json'
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rows = list(csv.DictReader(source.open(newline='')))
assert len(rows) == 12
reference = json.loads((OUT/'milestone_20.json').read_text())
assert reference['target_percent'] == 20
by_key = {(r['seed'],r['source']):r for r in reference['rows']}
checks=[]
for row in rows:
    key = row['seed'],row['source']
    count = None if row['count_delta_percent']=='' else abs(float(row['count_delta_percent'])) <= 20
    latency = None if row['latency_delta_percent']=='' else abs(float(row['latency_delta_percent'])) <= 20
    both = None if count is None or latency is None else count and latency
    recorded = by_key[key]
    assert count == recorded['count_within_20']
    assert latency == recorded['latency_within_20']
    assert both == recorded['both_within_20']
    for name,value in row.items():
        assert recorded[name] == value, (key,name)
    checks.append({'seed':int(key[0]),'source':int(key[1]),'count_pass':count,'latency_pass':latency,'both_pass':both})
defined=sum(r['both_pass'] is not None for r in checks)
passed=sum(r['both_pass'] is True for r in checks)
assert (defined,passed)==(9,5)
receipt={'schema':'csr-target20-regrade-reproduction-v1','status':'pass','target_percent':20,
         'input_sha256':{str(p.relative_to(ROOT)):digest(p) for p in (source,accounting,OUT/'milestone_20.json')},
         'source_seed_cells':12,'defined_cells':defined,'cells_passing_both':passed,
         'full_network_target_met':False,'common_input_checks_relaxed':False,'rows':checks}
(OUT/'milestone_20_reproduction.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k!='rows'},indent=2))
