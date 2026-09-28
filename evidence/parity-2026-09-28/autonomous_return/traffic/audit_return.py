#!/usr/bin/env python3
"""Read-only audit of returned natural capture, traffic/custody and RNG context."""
import csv, gzip, hashlib, json
from pathlib import Path
from collections import Counter, defaultdict
from decimal import Decimal

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
DATA=ROOT/'autonomous_return/data'
A=DATA/'A_natural'
FIX=ROOT/'autonomous/kit/autocase/ref/native'
OLD=ROOT/'return6000/data/s132/attempt_001/raw'

def read(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))
def ns(s):return round(Decimal(str(s))*10**9)
def save(name,rows):
    if not rows:return
    with (OUT/name).open('w',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)

attempts=read(A/'application_admission_trace.csv')
service=read(A/'service_trace.csv')
random=[json.loads(s) for s in (A/'random_requests.jsonl').read_text().splitlines()]
native_random=read(FIX/'random_draws.csv')
native_prefix=ROOT/'next_feedback/short_kit/two_case_next/schema_review/native_s132_prefix_0_330.csv.gz'
with gzip.open(native_prefix,'rt',newline='') as f:native=list(csv.DictReader(f))

# Independently recheck exact natural CSV-prefix values, not just the returned pass flag.
prefix=[]
for name in ('protocol_trace.csv','phy_trace.csv','application_admission_trace.csv'):
    actual=read(A/name)
    with (OLD/name).open(newline='') as f:
        expected=[]
        for r in csv.DictReader(f):
            if Decimal(r['TimeSeconds'])>=330:break
            expected.append(r)
    assert actual==expected,name
    prefix.append({'file':name,'rows':len(actual),'exact_csv_cell_match':True})

# Replay only the application custody accounting from passive callback rows.
# No simulation state is modified. Application creation increments own NSDP;
# source-local custody release decrements it before the next observed attempt.
custody=Counter(); own=defaultdict(set); verified=Counter(); releases=Counter()
release_rows=[]; transition_rows=[]; gate_violations=[]
for r in service:
    if Decimal(r['TimeSeconds'])<300:continue
    node=int(r['NodeId']); d=json.loads(r['DetailsJSON'])
    if r['Event']=='application_attempt':
        source=int(d['SourceId']);observed=int(d['NsdpCount']);accepted=bool(d['Accepted'])
        assert source==node and not d['DiscoveryActive'] and d['TopologyKnown']
        assert observed==custody[source],(r['ObservationId'],source,observed,custody[source])
        assert accepted==(observed<16)
        verified[source]+=1
        assert ns(d['TimeSeconds'])==300_000_000_000+(int(d['AttemptIndex'])-1)*20_000_000
        if accepted:
            pid=int(d['PacketId']);assert pid not in own[source]
            own[source].add(pid);custody[source]+=1
            transition_rows.append({'observation_id':r['ObservationId'],'time_s':r['TimeSeconds'],
                'source':source,'event':'application_admitted','packet_id':pid,
                'nsdp_before':observed,'nsdp_after':custody[source]})
    elif r['Event']=='network_custody_release' and r['ApplicationSourceId']!='NaN' and int(r['ApplicationSourceId'])==node:
        pid=int(r['PacketId']);assert pid in own[node],(node,pid,r)
        own[node].remove(pid);before=custody[node];custody[node]-=1;releases[node]+=1
        row={'observation_id':r['ObservationId'],'time_s':r['TimeSeconds'],'source':node,
            'event':'source_custody_release','packet_id':pid,'nsdp_before':before,'nsdp_after':custody[node]}
        transition_rows.append(row);release_rows.append({**row,'reason':d['Reason']})
assert sum(verified.values())==9000
save('source_custody_transitions.csv',transition_rows)
save('source_custody_releases.csv',release_rows)

nr_admit={}
for r in native:
    if r['event']=='app_admission':
        d=dict(s.split('=',1) for s in r['detail'].split(';') if '=' in s)
        nr_admit[(int(r['node']),int(d['attempt_index']))]=(r,d)
paired=[]
for r in attempts:
    s=int(r['SourceId']);ix=int(r['AttemptIndex']);n,d=nr_admit[(s,ix)]
    assert ns(r['TimeSeconds'])==ns(n['time_s'])
    paired.append({'source':s,'attempt_index':ix,'time_s':r['TimeSeconds'],
        'matlab_admitted':bool(int(r['Accepted'])),'native_admitted':n['success']=='1',
        'matlab_nsdp':int(r['NsdpCount']),'native_nsdp':int(d['nsdp_count'])})
save('paired_attempt_decisions.csv',paired)
first={}
for r in paired:
    if r['matlab_admitted']!=r['native_admitted']:first.setdefault(r['source'],r)

# Pin specific event contexts by actual time, not mismatched per-node ordinals.
contexts=[]
for t,node in [(10.01,1),(300.001,7),(300.001,8)]:
    m=next(r for r in random if r['purpose']=='mac_slot' and r['node']==node and ns(r['time_s'])==ns(t))
    n=next(r for r in native_random if r['purpose']=='mac_slot' and int(r['node'])==node and int(r['time_ns'])==ns(t))
    fields=['profile','active_nodes','reservation_counter','reservation_slot','state','low','high']
    matches={k:str(m['actual'][k])==n[k] for k in fields}
    assert all(matches.values())
    contexts.append({'time_s':t,'node':node,'matlab_draw':m['value'],'native_draw':int(n['value']),
        'matlab_ordinal':m['ordinal'],'native_ordinal':int(n['ordinal']),
        'active_nodes':m['actual']['active_nodes'],'low':m['actual']['low'],'high':m['actual']['high'],
        'profile':m['actual']['profile'],'state':m['actual']['state'],
        'reservation_counter':m['actual']['reservation_counter'],'reservation_slot':m['actual']['reservation_slot'],
        'matlab_reported_nodes':m['actual']['reported_nodes'],'native_reported_nodes':int(n['reported_nodes']),
        'selected_request_context_matches':all(matches.values())})
save('matched_request_context_different_draws.csv',contexts)

counts=[]
for node in [1,2,3,4,5,7,8]:
    for purpose in ['mac_slot','sync_threshold','phy_binomial']:
        mr=[r for r in random if r['node']==node and r['purpose']==purpose]
        nr=[r for r in native_random if int(r['node'])==node and r['purpose']==purpose]
        counts.append({'node':node,'purpose':purpose,'matlab_0_300':sum(r['time_s']<300 for r in mr),
            'native_0_300':sum(int(r['time_ns'])<300_000_000_000 for r in nr),
            'matlab_0_330':len(mr),'native_0_330':len(nr)})
save('rng_draw_counts.csv',counts)

source_summary=[]
for source in [2,3,4,5,7,8]:
    generated=sum(int(r['Accepted']) for r in attempts if int(r['SourceId'])==source)
    source_summary.append({'source':source,'attempts':verified[source],'admitted':generated,
        'nsdp_blocked':verified[source]-generated,'own_custody_releases':releases[source],
        'source_owned_at_330':custody[source],
        'all_attempt_nsdp_values_match_admit_minus_release_history':True,
        'first_different_admission_time_s':first[source]['time_s']})
save('source_accounting_330.csv',source_summary)

chain=[]
for source,peer,mpid,npid in [(7,8,5,883),(8,2,6,884)]:
    ms=[r for r in service if int(r['NodeId'])==source and int(r['PacketId'])==mpid
        and r['ApplicationSourceId']==str(source) and Decimal(r['TimeSeconds'])>=300]
    first_sent=next(r for r in ms if r['Event']=='hop_sent' and r['FrameKind']=='DATA' and r['PeerId']==str(peer))
    first_released=next(r for r in ms if r['Event']=='network_custody_release')
    first_received=next(r for r in service if int(r['NodeId'])==peer and int(r['PacketId'])==mpid
        and r['Event']=='hop_receive' and r['FrameKind']=='DATA'
        and r['ApplicationSourceId']==str(source) and Decimal(r['TimeSeconds'])>=300)
    completion=next(r for r in native if r['event']=='hop_completion' and r['node']==str(source) and r['sequence']==str(npid))
    hop=next(r for r in native if r['event']=='hop_admission' and r['node']==str(source) and r['sequence']==str(npid))
    hd=dict(s.split('=',1) for s in hop['detail'].split(';') if '=' in s)
    tx=next(r for r in native if r['event']=='tx_start' and r['node']==str(source)
        and r['peer']==str(peer) and r['packet_type']=='data'
        and r['sequence']==hd['hop_sequence'] and Decimal(r['time_s'])>=300)
    rx=next(r for r in native if r['event']=='rx_accept' and r['node']==str(peer)
        and r['peer']==str(source) and r['packet_type']=='data'
        and r['sequence']==hd['hop_sequence'] and Decimal(r['time_s'])>=300)
    replacement=next(r for r in attempts if int(r['SourceId'])==source and int(r['Accepted']) and int(r['AttemptIndex'])>16)
    nat_replacement=next(r for r in paired if r['source']==source and r['attempt_index']>16 and r['native_admitted'])
    chain.append({'source':source,'peer':peer,'matlab_packet_id':mpid,'native_packet_id':npid,
        'matlab_first_data_tx_s':first_sent['TimeSeconds'],'native_first_data_tx_s':tx['time_s'],
        'matlab_first_data_rx_s':first_received['TimeSeconds'],'native_first_data_rx_s':rx['time_s'],
        'matlab_first_custody_release_s':first_released['TimeSeconds'],'native_first_custody_release_s':completion['time_s'],
        'matlab_first_replacement_admission_s':replacement['TimeSeconds'],'native_first_replacement_admission_s':nat_replacement['time_s']})
save('initial_source_transfer_chain.csv',chain)
assert chain[0]['matlab_first_data_tx_s']=='301.496'
assert chain[1]['matlab_first_data_tx_s']=='300.144'
assert ns(chain[0]['native_first_data_tx_s'])==300_092_000_000
assert ns(chain[1]['native_first_data_tx_s'])==316_719_000_000

# Independently validate those source transfers against actual ordered DATA
# children and native flow/attempt lineage, excluding other packet namespaces.
direct={}
with (A/'ordered_events.jsonl').open() as f:
    for line in f:
        if '"event":"mac_transmit"' not in line:continue
        r=json.loads(line)
        if r['time_s']<300 or r['node'] not in (7,8):continue
        frame=r['details']['frame'];children=frame.get('Segments') or [frame]
        for child in children:
            app=child.get('App') or {}
            if child['Kind']=='DATA' and app.get('SourceId')==r['node'] and app.get('FlowOrdinal')==1:
                assert app['GeneratedSeconds']==300
                direct.setdefault(r['node'],{'time_s':r['time_s'],'peer':child['DestinationId'],
                    'hop_sequence':child['Sequence'],'app_id':app['Id'],
                    'flow_index_0based':app['FlowIndex']-1,'attempt_index':app['FlowOrdinal'],
                    'app_generated_ns':ns(app['GeneratedSeconds'])})
        if len(direct)==2:break
signatures=read(FIX/'tx_signatures.csv')
lineage=[]
for item in chain:
    source=item['source'];m=direct[source]
    n=next(r for r in signatures if r['kind']=='0' and int(r['source'])==source
        and int(r['network_source'])==source and int(r['app_attempt_index'])==1)
    assert m['flow_index_0based']==int(n['app_flow_index'])
    assert m['app_generated_ns']==int(n['app_generated_time_ns'])==300_000_000_000
    assert m['peer']==int(n['hop_destination'])==item['peer']
    assert ns(m['time_s'])==ns(item['matlab_first_data_tx_s'])
    assert int(n['time_ns'])==ns(item['native_first_data_tx_s'])
    lineage.append({'source':source,'peer':m['peer'],'flow_index_0based':m['flow_index_0based'],
        'attempt_index':1,'generated_time_ns':300_000_000_000,
        'matlab_tx_time_s':m['time_s'],'native_tx_time_ns':int(n['time_ns']),
        'matlab_hop_sequence':m['hop_sequence'],'native_hop_sequence':int(n['hop_sequence']),
        'matlab_application_id':m['app_id'],'native_application_id':n['native_app_sequence'],
        'native_tx_id':n['tx_id']})
save('verified_initial_data_lineage.csv',lineage)

summary={'scope':'Actual returned natural capture; read-only traffic/custody and random-input evidence',
    'exact_prefix_independent_checks':prefix,'attempt_rows':len(attempts),
    'all_9000_attempt_nsdp_values_close_against_passive_admit_release_history':True,
    'all_9000_attempt_admission_decisions_match_nsdp_less_than_16':True,
    'different_paired_admission_decisions':sum(r['matlab_admitted']!=r['native_admitted'] for r in paired),
    'first_admission_differences':first,'source_summary':source_summary,'sampled_request_contexts':contexts,
    'initial_source_transfer_chain':chain,'verified_initial_data_lineage':lineage,
    'traffic_rng_draws':sum(r['purpose']=='traffic' for r in random),
    'case_B_error':json.loads((DATA/'B_common/error.json').read_text()),
    'case_B_random_request_rows':len((DATA/'B_common/random_requests.jsonl').read_text().splitlines()),
    'inference':'The new natural capture directly observes different MAC samples preceding the traffic/custody divergence. It does not test equal-input protocol equivalence because caseB failed in the harness before sample consumption.',
    'production_fix_supported':False,
    'limits':['Matching listed draw-request fields is not a complete network-state equality claim.',
              'Natural draw ordinals differ by300s; align by semantic event context, not equal ordinals.',
              'Natural sources7 and8 do not remain persistently advantaged by their first completion; full6000s attribution remains separate.']}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
paths=[A/'application_admission_trace.csv',A/'service_trace.csv',A/'random_requests.jsonl',
    A/'ordered_events.jsonl',A/'prefix_gate.json',FIX/'random_draws.csv',FIX/'tx_signatures.csv',native_prefix]
(OUT/'input_manifest.json').write_text(json.dumps([{'path':str(p.relative_to(ROOT)),
    'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest(),'bytes':p.stat().st_size} for p in paths],indent=2)+'\n')
print(json.dumps({'samples':contexts,'source_summary':source_summary,'chains':chain},indent=2))
