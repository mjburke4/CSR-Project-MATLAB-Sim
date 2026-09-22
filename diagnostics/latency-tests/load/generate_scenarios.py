#!/usr/bin/env python3
"""Deterministic CSV derivation; no simulator execution."""
import csv, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    parent=ROOT/'scenarios/parent.csv'
    with parent.open(newline='') as f:
        r=csv.DictReader(f); fields=r.fieldnames; original=list(r)
    cases=[]
    for seed in (128,129,132):
        for load,interval in [('low',2.0),('full',0.02)]:
            key=f'{load}{seed}'; rows=[dict(r) for r in original]
            for r in rows:
                if r['record']=='run': r.update(duration_s='600',seed=str(seed),scenario='campus-'+key)
                if r['record']=='flow': r['flow_interval_s']=str(interval)
                if r['record']=='node': r['interarrival_s']=str(interval)
            out=ROOT/'scenarios'/f'{key}.csv'
            with out.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n'); w.writeheader(); w.writerows(rows)
            cases.append(dict(id=key,seed=seed,load=load,interval_s=interval,duration_s=600,scenario='scenarios/'+out.name,sha256=sha(out)))
    (ROOT/'plan.json').write_text(json.dumps(dict(schema='latency-load-v1',parent_sha256=sha(parent),traffic_start_s=300,cases=cases),indent=2)+'\n')
if __name__=='__main__': main()
