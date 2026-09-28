#!/usr/bin/env python3
"""Stream original ns-3 seed132 trace; audit receiver decisions and sender feedback.
No simulation or model mutation. CSV row identities refer to original event_index.
"""
import csv,gzip,json,hashlib,collections,decimal,math
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
TRACE=BASE/'native_archive/evidence/tranche-25-ns3-reference/s132/ns3-trace.csv.gz'
OUT=Path(__file__).resolve().parent
EXPECTED_SHA='3da17e3397756f8890964d571932a44f7c94573b4d38eac9387342588883a4ef'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def ds(s):return dict(x.split('=',1) for x in s.split(';') if '=' in x)
def save(name,rows):
 if not rows:return
 with (OUT/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def ns(s):return int((decimal.Decimal(s)*10**9).to_integral_value(rounding=decimal.ROUND_HALF_EVEN))
def stats(a):
 a=sorted(a)
 return dict(n=len(a),mean=math.fsum(a)/len(a) if a else None,p50=a[(len(a)-1)//2] if a else None,max=max(a) if a else None)
assert sha(TRACE)==EXPECTED_SHA
counts=collections.Counter();kept=[];receipts=[];admissions=[];completions=[];state=collections.Counter();errors=[];changes=[];area=collections.Counter();abovearea=collections.Counter();lasttime=collections.defaultdict(lambda:300.);physical=[];late=[];gaps=[]
logical={'hop_feedback','hop_completion','hop_admission','hop_capacity_release','nwk_enqueue','nwk_forward','nwk_nsdp_release','hop_drop','nwk_drop'}
prev=-1
with gzip.open(TRACE,'rt',newline='') as f:
 rd=csv.reader(f);header=next(rd)
 for raw in rd:
  i=int(raw[1]);assert i==prev+1,(prev,i);prev=i
  ev,node=raw[3],raw[4];counts[ev]+=1
  if node not in ('2','8'):continue
  phys=(ev in ('tx_start','rx_accept','rx_drop') and ((raw[6] in ('ack','dack') and ((node=='2' and raw[8]=='8') or (node=='8' and raw[5]=='2'))) or (raw[6]=='data' and ((node=='8' and raw[8]=='2') or(node=='2' and raw[5]=='8')))))
  if ev not in logical and not phys:continue
  r=dict(zip(header,raw));kept.append(r)
  if phys:physical.append(r)
  if raw[6]!='data':continue
  d=ds(raw[27]);src=int(raw[7]) if raw[7] else 0;t=float(raw[2]);key=(int(node),src,int(raw[8] or 0));seq=int(raw[9]) if raw[9] else None
  if ev in ('nwk_enqueue','nwk_nsdp_release'):
   before=state[key];after=int(d['nsdp_count'] if ev=='nwk_enqueue' else d['count_after'])
   expected=before+1 if ev=='nwk_enqueue' else before-1
   if ev=='nwk_nsdp_release' and before!=int(d['count_before']):errors.append({'kind':'release_before','event_index':i,'state':before,'trace':d['count_before']})
   if expected!=after:errors.append({'kind':'nsdp_delta','event_index':i,'before':before,'after':after,'expected':expected})
   dt=max(0,min(t,6000)-lasttime[key]);area[key]+=dt*before;abovearea[key]+=dt*(before>=16);lasttime[key]=t;state[key]=after
   changes.append(dict(event_index=i,time_s=raw[2],node=node,source=src,destination=raw[8],event=ev,application_sequence=seq,count_before=before,count_after=after))
  if ev=='hop_feedback' and node=='2' and raw[5]=='8':
   before=int(d['nsdp_count_before']);after=int(d['nsdp_count_after']);first=int(d['first_reception']);local=raw[8]==node;ackable=int(d['ackable']);pred='dack' if ackable and first and not local and before>=int(d['nsdp_limit']) else 'ack'
   if d['nsdp_state_valid']!='1' or after!=state[key]:errors.append({'kind':'feedback_state','event_index':i,'state':state[key],'before':before,'after':after,'details':d})
   if pred!=raw[13]:errors.append({'kind':'decision_rule','event_index':i,'predicted':pred,'observed':raw[13]})
   receipts.append(dict(event_index=i,time_s=raw[2],time_ns=ns(raw[2]),source=src,destination=int(raw[8]),application_sequence=seq,incoming_hop_sequence=int(d['hop_sequence']),first_reception=first,nsdp_before=before,nsdp_after=after,nsdp_limit=int(d['nsdp_limit']),predicted_kind=pred,emitted_kind=raw[13],total_custody_after=sum(v for k,v in state.items() if k[0]==2)))
  if node=='8' and raw[5]=='2' and ev in ('hop_admission','hop_completion'):
   rr=dict(event_index=i,time_s=raw[2],time_ns=ns(raw[2]),source=src,destination=int(raw[8]),application_sequence=seq,incoming_hop_sequence=int(d['hop_sequence']),kind=raw[13],resend_count=int(d.get('resend_count','0')))
   (admissions if ev=='hop_admission' else completions).append(rr)
for key,value in state.items():
 dt=max(0,6000-lasttime[key]);area[key]+=dt*value;abovearea[key]+=dt*(value>=16)
save('filtered_native_events.csv',kept);save('receiver_decisions.csv',receipts);save('nsdp_state_changes.csv',changes);save('edge_physical_front_events.csv',physical)
keyfn=lambda r:(r['source'],r['destination'],r['application_sequence'],r['incoming_hop_sequence'])
admitby={keyfn(r):r for r in admissions};assert len(admitby)==len(admissions)
compby=collections.defaultdict(list);rxby=collections.defaultdict(list)
for r in completions:compby[keyfn(r)].append(r)
for r in receipts:rxby[keyfn(r)].append(r)
outcomes=[]
for k,a in admitby.items():
 rs=rxby[k];cs=compby[k];assert len(cs)<=1;first=rs[0] if rs else None;c=cs[0] if cs else None
 outcomes.append(dict(source=a['source'],destination=a['destination'],application_sequence=a['application_sequence'],incoming_hop_sequence=a['incoming_hop_sequence'],admission_event_index=a['event_index'],admission_time_s=a['time_s'],receiver_event_count=len(rs),first_receipt_event_index=first['event_index'] if first else '',first_receipt_time_s=first['time_s'] if first else '',first_receipt_kind=first['emitted_kind'] if first else '',first_nsdp_before=first['nsdp_before'] if first else '',completion_event_index=c['event_index'] if c else '',completion_time_s=c['time_s'] if c else '',completion_kind=c['kind'] if c else 'unresolved',completion_resend_count=c['resend_count'] if c else '',first_receipt_to_completion_s=(c['time_ns']-first['time_ns'])/1e9 if c and first else '',feedback_kind_differs_from_first=(c['kind']!=first['emitted_kind']) if c and first else ''))
for k in set(rxby)|set(compby):
 if k not in admitby:errors.append({'kind':'missing_admission','identity':k})
save('link_8_2_application_outcomes.csv',outcomes)
cohorts=[]
for source in (7,8):
 for start,end in [(0,6000),(300,330),(300,600),(600,1200),(1200,1800),(1800,2400),(2400,3000),(3000,3600),(3600,4200),(4200,4800),(4800,5400),(5400,6000)]:
  rx=[r for r in receipts if r['source']==source and start<=float(r['time_s'])<end];aa=[r for r in admissions if r['source']==source and start<=float(r['time_s'])<end];cc=[r for r in completions if r['source']==source and start<=float(r['time_s'])<end]
  cohorts.append(dict(source=source,start_s=start,end_s=end,admissions=len(aa),receiver_events=len(rx),first_receipts=sum(r['first_reception'] for r in rx),duplicate_receipts=sum(not r['first_reception'] for r in rx),receiver_ack=sum(r['emitted_kind']=='ack' for r in rx),receiver_dack=sum(r['emitted_kind']=='dack' for r in rx),completed_ack=sum(r['kind']=='ack' for r in cc),completed_dack=sum(r['kind']=='dack' for r in cc),completed_other=sum(r['kind'] not in ('ack','dack') for r in cc),mean_nsdp_before=math.fsum(r['nsdp_before'] for r in rx)/len(rx) if rx else None))
save('source_time_cohorts.csv',cohorts)
occupancy=[dict(node=k[0],source=k[1],destination=k[2],mean_custody=area[k]/5700,seconds_at_or_above16=abovearea[k],fraction_at_or_above16=abovearea[k]/5700,last_custody=state[k]) for k in sorted(state)]
save('flow_custody_occupancy.csv',occupancy)
summary=dict(schema='csr-native-receiver-feedback-audit-v1',seed=132,input=str(TRACE),input_sha256=EXPECTED_SHA,total_raw_rows=prev+1,kept_raw_rows=len(kept),event_counts=dict(counts),receiver_decision_counts=dict(collections.Counter(r['emitted_kind'] for r in receipts)),receiver_first_counts=dict(collections.Counter(r['first_reception'] for r in receipts)),completion_counts=dict(collections.Counter(r['kind'] for r in completions)),admissions=len(admissions),no_receive_count=sum(not r['receiver_event_count'] for r in outcomes),kind_mismatch_count=sum(r['feedback_kind_differs_from_first'] is True for r in outcomes),decision_and_nsdp_errors=errors,first_dacks={str(s):next((r for r in receipts if r['source']==s and r['emitted_kind']=='dack'),None) for s in (7,8)},feedback_delay_seconds={kind:stats([r['first_receipt_to_completion_s'] for r in outcomes if r['completion_kind']==kind and r['first_receipt_to_completion_s']!='']) for kind in ('ack','dack')},limitations=['Native PHY tx/rx exposes aggregate-front identity only; control children/bitmap membership are not fully exposed by this longrun schema.','Logical HOP completion is recorded per original application and hop sequence; its completion time supports end-to-end feedback age without asserting which physical control child acknowledged it.','Different autonomous engines/seeds are not packet-paired.','NSDP is tracked per original (source,destination), not per ingress neighbor; receiver decision occupancy is before this reception.'])
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ('event_counts','decision_and_nsdp_errors')},indent=2));print('errors',len(errors))
