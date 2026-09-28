#!/usr/bin/env python3
"""Offline checks of ns-3 clock conversion and existing transport plans."""
from pathlib import Path
import csv,hashlib,json,math,subprocess,collections

ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
NATIVE=ROOT/'autonomous/native_capture/run/observations.tsv'
SIG=ROOT/'autonomous/native_capture/fixture/tx_signatures.csv'
SCENARIO=ROOT/'autonomous/native_capture/fixture/scenario_s132.csv'
def read(p,delimiter=','):
    return list(csv.DictReader(p.open(),delimiter=delimiter))
def ns(x):return math.floor(x*1e9+.5)
def write(name,rows):
    with (OUT/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
obs=read(NATIVE,'\t')
ticks=sorted({int(r['time_ns']) for r in obs})
(OUT/'clock_ticks.txt').write_text(''.join(str(n)+'\n' for n in ticks))
with (OUT/'clock_ticks.txt').open() as src,(OUT/'clock_values.csv').open('w') as dst:
    subprocess.run([str(OUT/'arithmetic_probe'),'--clock-values'],stdin=src,stdout=dst,check=True)
clock=read(OUT/'clock_values.csv')
clockmap={int(r['time_ns']):float(r['native_seconds']) for r in clock}
summary={'clock_values':len(clock),'division_bit_mismatches':sum(r['native_bits']!=r['division_bits'] for r in clock),
         'multiplication_bit_mismatches':sum(r['native_bits']!=r['multiplication_bits'] for r in clock)}
tx={int(r['tx_id']):r for r in read(SIG)}
assert all(int(r['rate_kbps'])==8 for r in tx.values()),'This capture arithmetic audit is rate-8 specific.'
positions={int(r['node_id']):tuple(float(r[k]) for k in ['x_m','y_m','height_m']) for r in read(SCENARIO) if r['record']=='node'}
arrivals={};ends={};preambles={}
for r in obs:
    key=(int(r['node']),int(r['tx_id'])) if r['tx_id'] else None
    if r['event']=='rx_signal_arrival':arrivals[key]=(r,json.loads(r['detail_json']))
    elif r['event']=='rx_preamble_end':preambles[key]=int(r['time_ns'])
    elif r['event'] in ('rx_phy_decision','rx_prior_stage'):ends[key]=int(r['time_ns'])
rows=[]
for key,(r,d) in arrivals.items():
    recv,id=key;parent=tx[id];sender=int(parent['source']);t_ns=int(parent['time_ns']);t=t_ns/1e9
    distance=math.sqrt(sum((a-b)**2 for a,b in zip(positions[sender],positions[recv])))
    delay=distance/3e8
    rate=4/.00051;bits=7888 if d['preamble']=='1' else 104
    preamble=bits/4*.00051
    duration=(bits+48)/4*.00051+(int(parent['total_wire_bytes'])*8+32)/rate
    # Existing TransportTiming.plan('nanoseconds') components; physical
    # signal times are not quantized and are checked independently below.
    start=t_ns+ns(delay);pre=start+ns(preamble);end=start+ns(duration)
    rawstart=t+delay;rawend=rawstart+duration
    observed_start=int(r['time_ns']);arrival_seconds=clockmap[observed_start]
    native_pre=observed_start+ns(rawstart+preamble-arrival_seconds)
    native_end=observed_start+ns(rawend-arrival_seconds)
    rows.append(dict(node=recv,tx_id=id,source=sender,tx_ns=t_ns,
        raw_start_matches=float(d['start_sec'])==rawstart,raw_end_matches=float(d['end_sec'])==rawend,
        observed_start_ns=observed_start,transport_start_ns=start,start_match=start==observed_start,
        observed_preamble_ns=preambles.get(key,''),transport_preamble_ns=pre,
        preamble_match='' if key not in preambles else pre==preambles[key],
        observed_end_ns=ends.get(key,''),transport_end_ns=end,end_match='' if key not in ends else end==ends[key],
        native_relative_preamble_ns=native_pre,native_relative_end_ns=native_end,
        plans_agree_preamble=pre==native_pre,plans_agree_end=end==native_end))
write('callback_plan_comparison.csv',rows)
summary['callback_plans']={'signals':len(rows),
    'raw_physical_start_matches':sum(r['raw_start_matches'] for r in rows),
    'raw_physical_end_matches':sum(r['raw_end_matches'] for r in rows),
    'arrival_matches':sum(r['start_match'] for r in rows),
    'observed_preambles':len(preambles),'preamble_matches':sum(r['preamble_match'] is True for r in rows),
    'observed_ends':len(ends),'end_matches':sum(r['end_match'] is True for r in rows),
    'component_vs_native_relative_preamble_matches':sum(r['plans_agree_preamble'] for r in rows),
    'component_vs_native_relative_end_matches':sum(r['plans_agree_end'] for r in rows),
    'unfinished_signal_ends':len(rows)-len(ends),
    'first_disagreements':[r for r in rows if not r['start_match'] or r['end_match'] is False or r['preamble_match'] is False][:10]}
interval_rows=[];previous_end={}
for r in obs:
    if r['event']!='rx_error_interval':continue
    key=(int(r['node']),int(r['tx_id']));d=json.loads(r['detail_json']);arrival,signal=arrivals[key]
    rate=4/.00051;pre=7888 if signal['preamble']=='1' else 104
    start=float(signal['start_sec']);raw_end=float(signal['end_sec'])
    header_start=start+pre/rate;payload_start=start+(pre+48)/rate
    packet_end=payload_start+(int(tx[key[1]]['total_wire_bytes'])*8+32)/rate
    ns_start=previous_end.get(key,int(arrival['time_ns'])/1e9)
    ns_end=min(int(r['time_ns'])/1e9,raw_end);previous_end[key]=ns_end
    def counts(begin,end):
        end=min(end,packet_end)
        return (math.floor(max(0,min(end,payload_start)-max(begin,header_start))*rate),
                math.floor(max(0,end-max(begin,payload_start))*rate))
    a=counts(float(d['interval_start_sec']),float(d['interval_end_sec']))
    b=counts(ns_start,ns_end)
    interval_rows.append(dict(node=key[0],tx_id=key[1],interval_ordinal=d['interval_ordinal'],
        native_raw_header_bits=a[0],native_raw_payload_bits=a[1],division_header_bits=b[0],division_payload_bits=b[1],
        matched=a==b))
write('all_interval_arithmetic.csv',interval_rows)
summary['all_interval_arithmetic']={'intervals':len(interval_rows),
    'matching_header_and_payload_counts':sum(r['matched'] for r in interval_rows),
    'first_disagreements':[r for r in interval_rows if not r['matched']][:10],
    'scope':'Counts reconstructed with the pinned floor expressions for all 4070 native intervals; sampled counts independently observable for 1542 components only.'}
summary['scope']='Existing native traffic and geometry only. No MATLAB execution, no generated event order, and no network simulation. Callback-planning result does not validate other scheduler, HOP/MAC, acquisition or duty timers.'
summary['input_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [NATIVE,SIG,SCENARIO,OUT/'arithmetic_probe.cc']}
(OUT/'callback_timing_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
