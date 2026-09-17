#!/usr/bin/env python3
"""Verify a fresh pristine full trace reproduces accepted seed-128 event content.

Historical T7 used compact aggregate trace. The projection selects precisely
its event types/columns, removing only trace indices which count different rows.
"""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import tranche19_metrics as metrics

EVENTS={'app_send','nwk_enqueue','nwk_forward','nwk_delivery','hop_feedback','route_change','rx_drop','statistic_sample'}
FIELDS=['schema','time_s','event','src','dst','sequence','size_bytes','reason','node','statistic','value','peer','next_hop','route_cost','detail']

def projection(path):
    h=hashlib.sha256(); count=0
    with gzip.open(path,'rt',newline='') as stream:
        for row in csv.DictReader(stream):
            if row['event'] not in EVENTS: continue
            if row['event']=='nwk_enqueue': row['detail']=''  # admission-mode-only detail, pinned NWK source
            h.update((json.dumps([row[k] for k in FIELDS],ensure_ascii=True,separators=(',',':'))+'\n').encode())
            count+=1
    return {'rows':count,'sha256':h.hexdigest()}

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--accepted',type=Path,required=True);ap.add_argument('--fresh',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    old,new=args.accepted,args.fresh
    a,b=projection(old/'ns3-trace.csv.gz'),projection(new/'ns3-trace.csv.gz')
    assert a == b, f'Historical trace event projection differs: {a} vs {b}'
    assert (old/'app-admission-diagnostics.csv').read_bytes() == (new/'app-admission-diagnostics.csv').read_bytes()
    assert metrics.native_applications(old) == metrics.native_applications(new)
    # All statistics equal; source trace SHA and filename are provenance, not numbers.
    def aggregates(path):
        with path.open(newline='') as stream:
            return [{k:v for k,v in row.items() if k not in ('source_file','source_file_sha256')} for row in csv.DictReader(stream)]
    assert aggregates(old/'ns3-aggregates.csv') == aggregates(new/'ns3-aggregates.csv')
    report={'schema':'csr-tranche20-native-baseline-reproduction-v1','status':'passed',
            'seed':128,'duration_s':6000,'fresh_manifest_sha256':digest(new/'manifest.json'),
            'accepted_trace_sha256':digest(old/'ns3-trace.csv.gz'),'fresh_trace_sha256':digest(new/'ns3-trace.csv.gz'),
            'projection_fields':FIELDS,'excluded_admission_only_detail_event':'nwk_enqueue','projection_events':sorted(EVENTS),'accepted_projection':a,'fresh_projection':b,
            'admission_diagnostics_byte_identical':True,'application_metrics_identical':True,
            'aggregate_statistics_identical':True,'scope':'Native executable/provenance gate only; no new MATLAB seed128 run.'}
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
