#!/usr/bin/env python3
"""Verify T22 preserves every accepted T20 source/reference binding."""
import argparse, hashlib, json
from pathlib import Path

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def audit(root):
    c=json.loads((root/'evidence/t20/candidate.json').read_text())
    checks={}
    for key in ['SourceFiles','ReferenceFileInventory']:
        rows=json.loads((root/'evidence/t20/source.json').read_text()) if key=='SourceFiles' else c[key]
        failures=[]
        for r in rows:
            p=root/r['path']
            if not p.is_file(): failures.append({'path':r['path'],'reason':'missing'})
            elif sha(p)!=r['sha256']:failures.append({'path':r['path'],'reason':'sha256_mismatch'})
        checks[key]={'count':len(rows),'matlab_files':sum(r['path'].endswith('.m') for r in rows),'unchanged':not failures,'failures':failures}
    return {'schema':'csr-t22-independent-baseline-v1','passed':all(x['unchanged'] for x in checks.values()),'candidate_sha256':sha(root/'evidence/t20/candidate.json'),'checks':checks,'new_matlab_execution_claimed':False}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-root',default='csr22');p.add_argument('--output',default='t22-work/review/baseline-review.json');a=p.parse_args();r=audit(Path(a.source_root));Path(a.output).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));raise SystemExit(0 if r['passed'] else 1)
