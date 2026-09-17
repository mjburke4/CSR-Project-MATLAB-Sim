"""Native unique-application metrics with pinned source-exact duplicate proof.

The byte-identical upstream aggregator is run against decompressed trace bytes
through a streaming path adapter. It revalidates DACK/enqueue source ordering,
NSDP transitions, payload-size identity, and delivery timing before counting
unique applications. Delivery events and retry duplicates remain explicit.
"""
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tranche19_metrics as base

PINNED_HELPER_SHA256 = 'fac6ceb6c5b7d95d41567a2f1018194b59d03366b581bdeb6415674d51985f2e'
_HELPER = Path(__file__).parent/'ns3/tranche20-aggregate-upstream.py'
assert hashlib.sha256(_HELPER.read_bytes()).hexdigest() == PINNED_HELPER_SHA256
_spec=importlib.util.spec_from_file_location('tranche20_upstream_aggregate',_HELPER)
upstream=importlib.util.module_from_spec(_spec); _spec.loader.exec_module(upstream)

class GzipTracePath:
    """Read-only path protocol for the unchanged upstream streaming reader."""
    name='ns3-trace.csv'
    def __init__(self,path,size): self.path,self.size=Path(path),size
    def open(self,mode='r',**kwargs):
        return gzip.open(self.path,mode if 'b' in mode else mode+'t',**kwargs)
    def resolve(self): return self.path.with_suffix('').resolve()
    def stat(self): return SimpleNamespace(st_size=self.size)


def native_applications(directory,duration_s=6000,bin_width_s=300):
    directory=Path(directory)
    expected=json.loads((directory/'ns3-aggregates.provenance.json').read_text())
    raw=GzipTracePath(directory/'ns3-trace.csv.gz',expected['input']['size_bytes'])
    series,provenance=upstream.derive_series(raw,'blue_radio_campus-multihop',60,duration_s,0)
    for key,value in provenance.items():
        if key=='input':
            base.require({k:v for k,v in value.items() if k!='path'} == {k:v for k,v in expected[key].items() if k!='path'},'Native uncompressed input identity/content mismatch')
        elif key=='output': base.require(value['row_count']==expected[key]['row_count'],'Native upstream output row count mismatch')
        else: base.require(value == expected[key],f'Native upstream proof mismatch: {key}')
    with (directory/'ns3-aggregates.csv').open(newline='') as stream:
        base.require(series == list(csv.DictReader(stream)),'Native aggregate series differs from fresh derivation')
    match=provenance['delay_matching']
    base.require(match['unmatched_delivery_count']==0,'Native delivery without exact source lineage')
    base.require(provenance['matched_packet_size_integrity']['mismatch_count']==0,'Native delivery size mismatch')
    sent={}; delivered=set(); events=Counter(); bins=defaultdict(Counter); duplicate_counts=Counter(); delays=defaultdict(list)
    with gzip.open(directory/'ns3-trace.csv.gz','rt',encoding='utf-8-sig',newline='') as stream:
        for row in csv.DictReader(stream):
            if row['event'] not in ('app_send','nwk_delivery'):continue
            when=base.finite(row['time_s'],'native time')
            base.require(0<=when<duration_s,'Native application event outside horizon')
            source=base.integer(row['src'],'source');key=(source,base.integer(row['sequence'],'sequence'))
            bi=base.bucket(when,duration_s,bin_width_s)
            if row['event']=='app_send':
                base.require(key not in sent,'Repeated native generation identity')
                sent[key]=when; bins[source,bi]['admitted']+=1
            else:
                base.require(key in sent and when>=sent[key],'Native delivery without preceding send')
                events[source]+=1;bins[source,bi]['delivery_events']+=1
                if key in delivered: duplicate_counts[source]+=1;bins[source,bi]['duplicate_delivery_events']+=1
                else:
                    delivered.add(key);bins[source,bi]['delivered']+=1;delays[source].append(when-sent[key])
    proof=provenance['source_exact_dack_retry_duplicates']
    base.require(sum(duplicate_counts.values())==proof['matched_duplicate_delivery_count'],'Native duplicate event/proof mismatch')
    flows=[]
    for row in base.rows(directory/'app-admission-diagnostics.csv',('source','attempts','admitted')):
        source=base.integer(row['source'],'source');admitted=sum(k[0]==source for k in sent);received=sum(k[0]==source for k in delivered)
        base.require(admitted==base.integer(row['admitted'],'admitted'),'Native admitted diagnostic mismatch')
        attempts=base.integer(row['attempts'],'attempts');base.require(attempts>=admitted,'Native attempt count below admission')
        flows.append({'source':source,'attempts':attempts,'admitted':admitted,'blocked':attempts-admitted,'delivered':received,
                      'unique_delivered':received,'delivery_events':events[source],'duplicate_delivery_events':duplicate_counts[source],
                      'unmatched_sends':admitted-received,
                      'first_delivery_delay_s':{'count':len(delays[source]),'mean':sum(delays[source])/len(delays[source]) if delays[source] else None,'min':min(delays[source]) if delays[source] else None,'max':max(delays[source]) if delays[source] else None}})
    base.require(len(flows)==len({f['source'] for f in flows}) and {k[0] for k in sent}<={f['source'] for f in flows},'Native source coverage mismatch')
    all_delays=[v for values in delays.values() for v in values]
    keys=('attempts','admitted','blocked','delivered','unique_delivered','delivery_events','duplicate_delivery_events','unmatched_sends')
    return {'schema':'csr-tranche20-native-app-metrics-v1','flows':flows,'totals':{k:sum(f[k] for f in flows) for k in keys},
            'flow_timeline':[{'source':f['source'],'start_s':i*bin_width_s,'end_s':(i+1)*bin_width_s,
                             **{k:bins[f['source'],i][k] for k in ('admitted','delivered','delivery_events','duplicate_delivery_events')}}
                            for f in flows for i in range(int(duration_s/bin_width_s))],
            'first_delivery_delay_s':{'count':len(all_delays),'mean':sum(all_delays)/len(all_delays) if all_delays else None,'min':min(all_delays) if all_delays else None,'max':max(all_delays) if all_delays else None},
            'duplicate_proof':proof,'upstream_helper_sha256':PINNED_HELPER_SHA256,
            'scope':'Delivered counts unique native applications; delivery events include source-proven DACK retry duplicates. Unmatched sends do not separate drops from pending.'}
