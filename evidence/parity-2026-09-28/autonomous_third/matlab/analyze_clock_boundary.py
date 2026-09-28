from pathlib import Path
import csv,json,math,hashlib,collections
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
NATIVE=ROOT/'autonomous/native_capture/run/observations.tsv'
TX=ROOT/'autonomous/native_capture/fixture/tx_signatures.csv'
MAT=ROOT/'autonomous_third/data/B_common/first_divergence.json'
def bps(rate):return 4/{8:.000510,16:.000254,32:.000126,64:.000062,128:.000030,500:4/500000,1000:4/1000000}[int(rate)]
tx={int(r['tx_id']):r for r in csv.DictReader(TX.open())}
observations=list(csv.DictReader(NATIVE.open(),delimiter='\t'))
signals={};intervals={};samples=[]
for r in observations:
 d=json.loads(r['detail_json']);key=(r['node'],r['tx_id'])
 if r['event']=='rx_signal_arrival':signals[key]={'start':float(d['start_sec']),'end':float(d['end_sec']),'start_callback_ns':int(r['time_ns']),'preamble':int(d['preamble'])}
 elif r['event']=='rx_error_interval':intervals[key+(d['interval_ordinal'],)]={'row':r,'details':d}
 elif r['event']=='rx_binomial_draw':samples.append((r,d))
# Replay the pinned bit-allocation expressions over native observed intervals.
# This is arithmetic only: it does not recreate the autonomous event order.
results=[]
for mode in ['native_raw','native_ns_division','native_ns_multiplication']:
 previous_end={}
 modeled={}
 for r in observations:
  key=(r['node'],r['tx_id']);d=json.loads(r['detail_json'])
  if r['event']!='rx_error_interval':continue
  signal=signals[key];parent=tx[int(r['tx_id'])]
  if mode=='native_raw':start=float(d['interval_start_sec']);end=float(d['interval_end_sec'])
  else:
   conv=(lambda n:n/1e9) if mode=='native_ns_division' else (lambda n:n*1e-9)
   start=previous_end.get(key,conv(signal['start_callback_ns']))
   end=min(conv(int(r['time_ns'])),signal['end'])
  previous_end[key]=end
  preamble=7888 if signal['preamble'] else 104
  header_rate=bps(8);payload_rate=bps(parent['rate_kbps'])
  header_start=signal['start']+preamble/header_rate
  payload_start=signal['start']+(preamble+48)/header_rate
  packet_end=payload_start+(int(parent['total_wire_bytes'])*8+32)/payload_rate
  stop=min(end,packet_end)
  hb=max(start,header_start);he=min(stop,payload_start);pb=max(start,payload_start)
  hc=math.floor(max(0,he-hb)*header_rate);pc=math.floor(max(0,stop-pb)*payload_rate)
  modeled[key+(d['interval_ordinal'],)]={'header':hc,'payload':pc,'header_product':max(0,he-hb)*header_rate,'payload_product':max(0,stop-pb)*payload_rate,'interval_start_sec':start,'interval_end_sec':end,'header_begin_sec':hb,'header_end_sec':he,'payload_begin_sec':pb,'payload_end_sec':stop}
 for r,d in samples:
  v=modeled[(r['node'],r['tx_id'],d['interval_ordinal'])];actual=int(d['bits']);calculated=v[d['component']]
  results.append({'mode':mode,'node':int(r['node']),'tx_id':int(r['tx_id']),'time_ns':int(r['time_ns']),'ordinal':int(d['draw_ordinal']),'interval_ordinal':int(d['interval_ordinal']),'component':d['component'],'native_bits':actual,'calculated_bits':calculated,'delta':calculated-actual,'matched':actual==calculated,**v})
with (OUT/'clock_arithmetic_all_samples.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
summary={}
for mode in ['native_raw','native_ns_division','native_ns_multiplication']:
 rows=[r for r in results if r['mode']==mode];bad=[r for r in rows if not r['matched']]
 summary[mode]={'samples':len(rows),'matched':len(rows)-len(bad),'mismatched':len(bad),'first_mismatches':bad[:5]}
x=json.loads(MAT.read_text());signal=signals[('4','4294967297')];rate=bps(8);pb=signal['start']+(7888+48)/rate
first=[]
for label,end in [('matlab_continuous',signal['end']),('native_callback_raw',float(intervals[('4','4294967297','1')]['details']['interval_end_sec'])),('existing_transport_ns_division',int(x['expected']['time_ns'])/1e9),('ns_multiplication',int(x['expected']['time_ns'])*1e-9)]:
 product=(end-pb)*rate
 first.append({'mode':label,'physical_start_sec':signal['start'],'payload_start_sec':pb,'end_sec':end,'end_minus_physical_end_ps':(end-signal['end'])*1e12,'payload_product':product,'floor_bits':math.floor(product),'end_binary64_hex':end.hex()})
summary['first_divergence']=first
summary['scope']='Independent binary64 arithmetic reconstruction over existing native intervals, not MATLAB execution or a closed-loop transport test.'
summary['input_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [NATIVE,TX,MAT]}
(OUT/'clock_arithmetic_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:{a:v[a] for a in ['samples','matched','mismatched']} for k,v in summary.items() if isinstance(v,dict) and 'samples' in v},indent=2));print(json.dumps(first,indent=2))
