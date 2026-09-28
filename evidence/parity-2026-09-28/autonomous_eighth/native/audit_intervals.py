#!/usr/bin/env python3
"""Fixed-native-history interval reconstruction and portable preflight inputs."""
import collections,csv,hashlib,json,math
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
OBS=ROOT/'autonomous/native_capture/run/observations.tsv'
TX=ROOT/'autonomous/native_capture/fixture/tx_signatures.csv'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save_csv(name,rows):
    with (OUT/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def bps(rate):return 4/{8:.000510,16:.000254,32:.000126,64:.000062,128:.000030,500:4/500000,1000:4/1000000}[int(rate)]
obs=list(csv.DictReader(OBS.open(),delimiter='\t'))
tx={r['tx_id']:r for r in csv.DictReader(TX.open())}
clocks={int(r['time_ns']):r for r in csv.DictReader((OUT/'clock_values.csv').open())}
seconds=lambda n:float(clocks[int(n)]['native_seconds'])
signals={};schedules={};acquisition=[];intervals={};sample_fixture=[]
for r in obs:
    d=json.loads(r['detail_json']);key=(r['node'],r['tx_id'])
    if r['event']=='rx_signal_arrival':
        signals[key]={'start':float(d['start_sec']),'end':float(d['end_sec']),
                      'start_callback_ns':int(r['time_ns']),'preamble':int(d['preamble'])}
    elif r['event']=='timer_lifecycle' and d.get('timer')=='m_acquisitionEvent' and d.get('action')=='schedule':
        origin=int(r['time_ns']);end=int(d['deadline_ns']);assert end-origin==6630000
        schedules[(r['node'],end)]=origin
        acquisition.append({'node':int(r['node']),'event_order':int(r['event_order']),
            'event_uid':int(d['event_uid']),'origin_ns':origin,'delay_ns':end-origin,
            'cause':d['cause'],'native_path':'ScheduleAcquisition -> AcquireSignal',
            'origin_seconds_raw':seconds(origin),'delay_seconds_raw':0.00663,
            'delay_seconds':0.00663,'deadline_ns':end,
            'origin_native_seconds':seconds(origin),'deadline_native_seconds':seconds(end),
            'deadline_ns_division_seconds':end/1e9,
            'floating_sum_seconds':seconds(origin)+0.00663,
            'division_origin_floating_sum_seconds':origin/1e9+0.00663})

def calculate(signal,parent,start,end):
    preamble=7888 if signal['preamble'] else 104
    rate=bps(parent['rate_kbps']);header_rate=bps(8)
    header_start=signal['start']+preamble/header_rate
    payload_start=signal['start']+(preamble+48)/header_rate
    packet_bits=preamble+48+int(parent['total_wire_bytes'])*8+32
    packet_end=payload_start+(packet_bits-preamble-48)/rate
    bounded=min(end,packet_end)
    hb=max(start,header_start);he=min(bounded,payload_start);pb=max(start,payload_start)
    hp=max(0,he-hb)*header_rate;pp=max(0,bounded-pb)*rate
    return {'expected_header_bits':math.floor(hp),'expected_payload_bits':math.floor(pp),
        'header_product':hp,'payload_product':pp,'component_header_start_sec':hb,
        'component_header_end_sec':he,'component_payload_start_sec':pb,
        'component_payload_end_sec':bounded,'packet_bits':packet_bits,
        'preamble_bits':preamble,'payload_rate_bps':rate}

methods=['native_raw','native_clock','ns_division','floating_acquisition_only','floating_acquisition_division_origin']
modeled={};all_rows=[]
for mode in methods:
    previous={}
    for r in obs:
        if r['event']!='rx_error_interval':continue
        d=json.loads(r['detail_json']);key=(r['node'],r['tx_id']);signal=signals[key];parent=tx[r['tx_id']]
        raw_start=float(d['interval_start_sec']);raw_end=float(d['interval_end_sec'])
        if mode=='native_raw':start=raw_start;end=raw_end
        else:
            conv=(lambda n:n/1e9) if mode in ('ns_division','floating_acquisition_division_origin') else seconds
            start=previous.get(key,conv(signal['start_callback_ns']))
            callback=conv(int(r['time_ns']))
            if mode in ('floating_acquisition_only','floating_acquisition_division_origin') and d['cause']=='CsrNetDevice::AcquireSignal':
                origin=schedules[(r['node'],int(r['time_ns']))]
                callback=conv(origin)+0.00663
            end=min(callback,signal['end'])
        previous[key]=end
        val=calculate(signal,parent,start,end)
        row={'mode':mode,'node':int(r['node']),'tx_id':int(r['tx_id']),
            'interval_ordinal':int(d['interval_ordinal']),'callback_ns':int(r['time_ns']),
            'cause':d['cause'],'interval_start_sec':start,'interval_end_sec':end,**val}
        modeled[(mode,*key,d['interval_ordinal'])]=row;all_rows.append(row)
        if mode=='native_raw':intervals[key+(d['interval_ordinal'],)]={'row':r,'detail':d,'value':val}

sample_modes=[]
for r in obs:
    if r['event']!='rx_binomial_draw':continue
    d=json.loads(r['detail_json']);key=(r['node'],r['tx_id']);signal=signals[key];parent=tx[r['tx_id']]
    iv=intervals[key+(d['interval_ordinal'],)];val=iv['value']
    count=val['expected_'+d['component']+'_bits'];assert count==int(d['bits'])
    sample_fixture.append({
        'node':int(r['node']),'tx_id':int(r['tx_id']),'draw_ordinal':int(d['draw_ordinal']),
        'interval_ordinal':int(d['interval_ordinal']),'component':d['component'],
        'callback_ns':int(r['time_ns']),'arrival_callback_ns':signal['start_callback_ns'],
        'signal_start_sec':signal['start'],'signal_end_sec':signal['end'],
        'rate_key':int(parent['rate_kbps']),'preamble_bits':val['preamble_bits'],'packet_bits':val['packet_bits'],
        'interval_start_sec':float(d['interval_start_sec']),'interval_end_sec':float(d['interval_end_sec']),
        'interval_start_ns':int(d['interval_start_ns']),'interval_end_ns':int(d['interval_end_ns']),
        'expected_header_bits':val['expected_header_bits'],'expected_payload_bits':val['expected_payload_bits'],
        'component_start_sec':float(d['component_start_sec']),'component_end_sec':float(d['component_end_sec']),
        'bits':int(d['bits']),'probability':float(d['probability']),'uniform':float(d['draw']),
        'cause':d['cause']})
    for mode in methods:
        row=modeled[(mode,*key,d['interval_ordinal'])]
        value=row['expected_'+d['component']+'_bits']
        sample_modes.append({'mode':mode,'node':int(r['node']),'tx_id':int(r['tx_id']),
            'draw_ordinal':int(d['draw_ordinal']),'component':d['component'],'native_bits':count,
            'calculated_bits':value,'difference':value-count,'callback_ns':int(r['time_ns']),
            'cause':d['cause'],'probability':float(d['probability']),'uniform':float(d['draw'])})
assert len(sample_fixture)==1542 and len(intervals)==4070
save_csv('phy_component_fixture.csv',sample_fixture)
save_csv('acquisition_schedule_fixture.csv',acquisition)
save_csv('all_interval_arithmetic.csv',all_rows)
save_csv('all_sample_arithmetic.csv',sample_modes)
summary={}
for mode in methods:
    samples=[r for r in sample_modes if r['mode']==mode];bad=[r for r in samples if r['difference']]
    changed=[]
    for r in all_rows:
        if r['mode']!=mode:continue
        raw=modeled[('native_raw',str(r['node']),str(r['tx_id']),str(r['interval_ordinal']))]
        if any(r[f]!=raw[f] for f in ('expected_header_bits','expected_payload_bits')):changed.append(r)
    summary[mode]={'samples':len(samples),'sample_mismatches':len(bad),'intervals':4070,
        'changed_intervals':len(changed),'first_sample_mismatches':bad[:15],
        'sample_mismatch_causes':dict(collections.Counter(r['cause']for r in bad))}
clock_bad=[r for r in clocks.values()if r['native_bits']!=r['division_bits']]
summary.update({'scope':'Fixed native traffic and event history; counterfactual arithmetic only, not a network continuation.',
    'acquisition_schedules':len(acquisition),
    'acquisition_floating_deadline_differences':sum(r['floating_sum_seconds']!=r['deadline_native_seconds']for r in acquisition),
    'acquisition_division_origin_floating_deadline_differences':sum(r['division_origin_floating_sum_seconds']!=r['deadline_ns_division_seconds']for r in acquisition),
    'clock_values':len(clocks),'native_getseconds_vs_division_differences':clock_bad,
    'input_sha256':{str(p.relative_to(ROOT)):sha(p)for p in (OBS,TX,OUT/'clock_values.csv')}})
(OUT/'arithmetic_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:{a:v[a]for a in ('samples','sample_mismatches','intervals','changed_intervals')}for k,v in summary.items()if k in methods},indent=2))
print('Acquisition schedules:',len(acquisition))
