#!/usr/bin/env python3
"""Independent identity/schema checks, including retained seed-130 source rows."""
import argparse,csv,gzip,hashlib,json,math
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def audit(root):
    directory=root/'scenarios/t22';c=json.loads((directory/'contract.json').read_text());p=json.loads((directory/'seed130-provenance.json').read_text());fail=[]
    for name,expected in c['input_hashes'].items():
        if sha(directory/name)!=expected:fail.append('hash:'+name)
    def rows(name):
        with (directory/name).open(newline='') as f:
            reader=csv.DictReader(f);return reader.fieldnames,list(reader)
    ch,cases=rows('cases.csv');ah,actions=rows('actions.csv')
    if ch!=c['configuration_columns'] or ah!=c['action_columns']:fail.append('columns')
    if len(cases)!=c['case_count'] or len(actions)!=c['action_count']:fail.append('counts')
    keys={}
    for case in cases:
        rs=[r for r in actions if r['case_id']==case['case_id']]
        if [int(r['step']) for r in rs]!=list(range(1,len(rs)+1)):fail.append('steps:'+case['case_id'])
        if any(float(b['time_s'])<float(a['time_s']) for a,b in zip(rs,rs[1:])):fail.append('time_order:'+case['case_id'])
        if case['policy']!='actual-tx':fail.append('policy:'+case['case_id'])
        for r in rs:keys[r['case_id'],int(r['step'])]=r
    for m in c['milestones']:
        if (m['case_id'],m['step']) not in keys:fail.append('milestone_key:'+str(m))
        if not set(m['equals']).issubset(c['state_columns']):fail.append('milestone_columns')
    raw=root/p['input_path']
    if sha(raw)!=p['input_gzip_sha256']:fail.append('seed130_hash')
    expected={r['event_index']:r for r in p['events']};found={}
    with gzip.open(raw,'rt',newline='') as f:
        for r in csv.DictReader(f):
            if r['event_index'] in expected:found[r['event_index']]={k:r[k] for k in expected[r['event_index']]} 
            if len(found)==len(expected):break
    for i,row in expected.items():
        if found.get(i)!=row:fail.append('seed130_row:'+i)
    return {'schema':'csr-t22-independent-contract-input-review-v1','passed':not fail,'remaining_blockers':fail,'cases':len(cases),'checkpoints':len(actions),'independent_milestone_assertions':sum(len(m['equals']) for m in c['milestones']),'seed130_original_rows_checked':len(expected),'seed130_original_rows_match':found==expected,'seed130_comparison_scope':'every retained original column; omitted raw columns contain unrelated radio/statistic fields','integer_tolerance':c['comparison']['integer_tolerance'],'time_absolute_tolerance_seconds':c['comparison']['time_absolute_tolerance_seconds'],'motif_scope':'transformed reduced input history, not full campus replay','bindings':{str((directory/n).relative_to(root)):sha(directory/n) for n in ['contract.json','cases.csv','actions.csv','seed130-provenance.json']}}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-root',default='csr22');p.add_argument('--output',default='t22-work/review/contract-input-review.json');a=p.parse_args();r=audit(Path(a.source_root));Path(a.output).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));raise SystemExit(0 if r['passed'] else 1)
