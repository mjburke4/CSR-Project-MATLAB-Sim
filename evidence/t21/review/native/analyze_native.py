#!/usr/bin/env python3
"""Read-only T21 native trace diagnosis. No simulation and no model changes.
All event bins use [start,end), unique delivery identity=(src,dst,sequence).
NSDP state is per source/destination at a relay; NWK queue is shared.
Queue residence matches the oldest outstanding enqueue of an identity.
"""
import argparse,csv,gzip,hashlib,json,math,time
from pathlib import Path
from collections import Counter,defaultdict,deque
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
SOURCE=ROOT/'csr20'
DURATION=6000;WIDTH=300
CANDIDATE_SHA256='ba4cedf3551a0bc1fe31385108e1f33011d1c97211bba993b6061a2de31389c1'

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def fields(s):return dict(x.split('=',1) for x in s.split(';') if '=' in x)
def number(v):return int(v) if v not in ('',None) else None
def stats(v):
 if not v:return {'count':0,'mean':None,'p50':None,'p90':None,'max':None}
 v=sorted(v);return {'count':len(v),'mean':sum(v)/len(v),'p50':v[(len(v)-1)//2],'p90':v[math.ceil(.9*len(v))-1],'max':v[-1]}
def csvout(p,rows):
 if not rows:
  p.unlink(missing_ok=True);return
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
class HashedLines:
 def __init__(self,f):self.f=f;self.h=hashlib.sha256();self.n=0
 def __iter__(self):return self
 def __next__(self):
  b=next(self.f);self.h.update(b);self.n+=len(b);return b.decode('utf-8-sig')
class State:
 def __init__(self):self.value=0;self.t=0.;self.integral=0.;self.high=0.;self.maximum=0;self.samples=0;self.bins=defaultdict(lambda:[0.,0.])
 def move(self,t,v):
  if t<self.t-1e-8:raise ValueError('state time reversed')
  lo=max(self.t,300.);hi=min(t,DURATION)
  while lo<hi:
   bi=int(lo//WIDTH);end=min(hi,(bi+1)*WIDTH);dt=end-lo
   self.integral+=dt*self.value;self.high+=dt*(self.value>=16)
   self.bins[bi][0]+=dt*self.value;self.bins[bi][1]+=dt*(self.value>=16);lo=end
  self.t=t;self.value=v;self.maximum=max(self.maximum,v);self.samples+=1
 def result(self):
  self.move(DURATION,self.value)
  return {'last':self.value,'maximum':self.maximum,'time_weighted_mean_300_6000':self.integral/5700,'seconds_at_or_above_16_300_6000':self.high,'observations':self.samples-1}

def analyze(seed):
 path=SOURCE/('evidence/tranche-7-ns3-reference/campus_multihop_6000' if seed==128 else f'evidence/tranche-20-ns3-reference/s{seed}')
 trace=path/'ns3-trace.csv.gz';m=json.loads((path/'manifest.json').read_text());prov=json.loads((path/'ns3-aggregates.provenance.json').read_text())
 mh=sha(path/'manifest.json');gzsha=sha(trace)
 candidate_path=SOURCE/'evidence/tranche-20-candidate.json'
 assert sha(candidate_path)==CANDIDATE_SHA256, 'Not the accepted T20 candidate'
 refmap={v['path']:v for v in json.loads(candidate_path.read_text())['ReferenceFileInventory']}
 for pth,digest in ((path/'manifest.json',mh),(trace,gzsha),(path/'ns3-aggregates.provenance.json',sha(path/'ns3-aggregates.provenance.json'))):
  assert refmap[pth.relative_to(SOURCE).as_posix()]['sha256']==digest, 'Native input not bound by accepted T20 candidate'
 bound=[x for x in m.get('files',[]) if x['path']=='ns3-trace.csv.gz']
 if not bound:bound=[x for x in m.get('compressed_artifacts',[]) if x['path']=='ns3-trace.csv.gz']
 assert bound and bound[0]['sha256']==gzsha,'trace gzip differs from manifest'
 counts=Counter();countsnode=Counter();bins=defaultdict(Counter);nodebins=defaultdict(Counter);sent={};received=set();delays=defaultdict(list);delaybins=defaultdict(list)
 reasons=Counter();route=[];nodes=(4,8);nsdp=defaultdict(State);queues=defaultdict(State);nsdp_mismatch=[];queue_mismatch=[]
 enqueue=defaultdict(deque);waits=defaultdict(list);hop=defaultdict(deque);hoptimes=defaultdict(list);custody=defaultdict(list);unmatched=Counter()
 episodes=[];hopcounts=Counter();feedback=Counter();firstlast={};snapreason=defaultdict(Counter);maxnsdp=Counter();attempts=Counter();duplicate=Counter();sourceepisodes=[]
 examples=defaultdict(list);lineno=-1;start=time.time();lasttime=0.
 with gzip.open(trace,'rb') as f:
  lines=HashedLines(f);r=csv.reader(lines);header=next(r);idx={k:i for i,k in enumerate(header)}
  for vals in r:
   lineno+=1
   ev=vals[idx['event']];counts[ev]+=1;t=float(vals[idx['time_s']]);lasttime=max(lasttime,t);bi=min(int(t//WIDTH),19)
   node=number(vals[idx['node']]);src=number(vals[idx['src']]);dst=number(vals[idx['dst']]);seq=number(vals[idx['sequence']]);reason=vals[idx['reason']];peer=number(vals[idx['peer']]);key=(src,dst,seq)
   countsnode[node,ev]+=1
   if ev=='app_send':
    assert key not in sent,'duplicate app generation';sent[key]=t;bins[src,bi]['admitted']+=1
   elif ev=='nwk_delivery':
    assert key in sent and t>=sent[key],'delivery lineage';bins[src,bi]['delivery_events']+=1
    if key in received:bins[src,bi]['duplicate_events']+=1;duplicate[src]+=1
    else:
     received.add(key);delay=t-sent[key];delays[src].append(delay);delaybins[src,bi].append(delay);bins[src,bi]['unique_delivered']+=1
   if ev=='route_change' and node in (2,4,5,7,8) and dst==1:
    route.append({'seed':seed,'time_s':t,'event_index':vals[idx['event_index']],'node':node,'destination':dst,'next_hop':vals[idx['next_hop']],'cost':vals[idx['route_cost']],'reason':reason,'detail':vals[idx['detail']]})
   if node not in (2,4,7,8):continue
   if ev=='app_admission':
    attempts[node,reason]+=1
    if node in (7,8):nodebins[node,src,bi]['app_'+reason]+=1
   if node not in nodes and ev!='hop_feedback':continue
   if ev not in {'nwk_enqueue','nwk_admission','nwk_forward','nwk_nsdp_release','hop_admission','hop_completion','hop_capacity_release','hop_feedback','nwk_drop','hop_drop'}:continue
   d=fields(vals[idx['detail']]);c=nodebins[node,src,bi];c[ev+':'+reason]+=1;reasons[node,src,ev,reason]+=1
   if len(examples[node,ev,reason])<2:examples[node,ev,reason].append({k:vals[i] for k,i in idx.items() if vals[i]})
   if ev=='hop_feedback':
    feedback[node,peer,src,reason]+=1
    if node in nodes and 'nsdp_count_before' in d:
     snapreason[node,src,reason][int(d['nsdp_count_before'])]+=1
    continue
   if node not in nodes:continue
   if seed==128:continue  # Historical reduced trace lacks full queue/HOP transitions.
   # Independent NSDP snapshots are flow-specific, not total relay custody.
   if ev in ('nwk_enqueue','nwk_nsdp_release'):
    new=int(d.get('nsdp_count',d.get('count_after',-1)));state=nsdp[node,src,dst]
    if new>=0:
     if ev=='nwk_enqueue' and new!=state.value+1:nsdp_mismatch.append([t,node,src,ev,state.value,new])
     if ev=='nwk_nsdp_release' and int(d.get('count_before',state.value))!=state.value:nsdp_mismatch.append([t,node,src,ev,state.value,new])
     state.move(t,new)
   if ev=='nwk_enqueue':
    enqueue[node,key].append((t,int(vals[idx['event_index']])));q=int(d.get('queue_after',-1))
    if q>=0:
     if q!=queues[node].value+1:queue_mismatch.append([t,node,ev,queues[node].value,q])
     queues[node].move(t,q)
   elif ev=='nwk_admission':
    for field in ('queue_before','nsdp_count','pending','outstanding','threshold','neighbor_spad'):
     if field in d:maxnsdp[node,field]=max(maxnsdp[node,field],int(d[field]))
    if 'nsdp_count' in d and int(d['nsdp_count'])!=nsdp[node,src,dst].value:nsdp_mismatch.append([t,node,src,ev,nsdp[node,src,dst].value,int(d['nsdp_count'])])
    if 'queue_before' in d and int(d['queue_before'])!=queues[node].value:queue_mismatch.append([t,node,ev,queues[node].value,int(d['queue_before'])])
    if 'queue_after' in d:queues[node].move(t,int(d['queue_after']))
    if reason=='admitted':
     if not enqueue[node,key]:unmatched[node,src,'admission_without_enqueue']+=1;enqt=None
     else:enqt,ei=enqueue[node,key].popleft();waits[node,src].append(t-enqt)
     hop[node,key].append({'enqueue_s':enqt,'admission_s':t,'admission_event_index':int(vals[idx['event_index']])})
     c['queue_wait_sum_s']+=0 if enqt is None else t-enqt;c['queue_wait_count']+=int(enqt is not None)
   elif ev=='hop_completion':
    hopcounts[node,src,reason]+=1;c['resend_count_sum']+=int(d.get('resend_count',0));c['completion_count']+=1
    ep={'seed':seed,'node':node,'source':src,'destination':dst,'sequence':seq,'peer':peer,'time_s':t,'reason':reason,'resend_count':int(d.get('resend_count',0)),'event_index':int(vals[idx['event_index']])}
    if hop[node,key]:
     began=hop[node,key].popleft();ep.update(began);dt=t-began['admission_s'];hoptimes[node,src].append(dt);ep['hop_admission_to_nsdp_release_completion_s']=dt
     if began['enqueue_s'] is not None:custody[node,src].append(t-began['enqueue_s']);ep['enqueue_to_nsdp_release_completion_s']=t-began['enqueue_s']
    else:unmatched[node,src,'completion_without_admission']+=1
    episodes.append(ep)
 rawsha=lines.h.hexdigest();rawbytes=lines.n
 assert lasttime<DURATION, 'Trace event at or beyond exclusive stop boundary'
 assert rawsha==prov['input']['sha256'] and rawbytes==prov['input']['size_bytes'],'uncompressed trace differs from pinned aggregate input'
 flows=[]
 for source in sorted({k[0] for k in sent}):
  admitted=sum(k[0]==source for k in sent);delivered=sum(k[0]==source for k in received)
  flows.append({'source':source,'admitted':admitted,'unique_delivered':delivered,'duplicate_delivery_events':duplicate[source],'unmatched_sends':admitted-delivered,'first_delivery_delay_s':stats(delays[source])})
 diagnostic=list(csv.DictReader((path/'app-admission-diagnostics.csv').open()))
 assert all(int(x['admitted'])==next(v['admitted'] for v in flows if v['source']==int(x['source'])) for x in diagnostic)
 flowbins=[{'seed':seed,'source':src,'start_s':bi*WIDTH,'end_s':(bi+1)*WIDTH,**{k:bins[src,bi][k] for k in ('admitted','unique_delivered','delivery_events','duplicate_events')},'delivery_mean_delay_s':stats(delaybins[src,bi])['mean']} for src in sorted({k[0] for k in sent}) for bi in range(20)]
 # CSV long-form event counts preserves event denominators (failed polls are not distinct packets).
 events=[{'seed':seed,'node':node,'source':src,'start_s':bi*WIDTH,'end_s':(bi+1)*WIDTH,'metric':metric,'value':value} for (node,src,bi),vs in sorted(nodebins.items(),key=str) for metric,value in sorted(vs.items())]
 nsdp_rows=[{'node':n,'source':s,'destination':d,**state.result()} for (n,s,d),state in sorted(nsdp.items())]
 queue_rows=[{'node':n,**state.result()} for n,state in sorted(queues.items())]
 statebins=[]
 for (node,src,dst),state in sorted(nsdp.items()):
  for bi in range(1,20):statebins.append({'seed':seed,'node':node,'source':src,'start_s':bi*WIDTH,'end_s':(bi+1)*WIDTH,'mean_nsdp':state.bins[bi][0]/WIDTH,'nsdp_at_least16_seconds':state.bins[bi][1]})
 for n,state in sorted(queues.items()):
  for bi in range(1,20):statebins.append({'seed':seed,'node':n,'source':'shared_NWK_queue','start_s':bi*WIDTH,'end_s':(bi+1)*WIDTH,'mean_nsdp':state.bins[bi][0]/WIDTH,'nsdp_at_least16_seconds':state.bins[bi][1]})
 result={'schema':'csr-t21-native-diagnosis-v1','seed':seed,'duration_s':DURATION,'full_custody_telemetry_available':seed!=128,'input':{'manifest_sha256':mh,'trace_gzip_sha256':gzsha,'trace_raw_sha256':rawsha,'trace_raw_bytes':rawbytes,'rows':lineno+1,'last_event_time_s':lasttime},'flows':flows,'event_counts':dict(counts),'counts_by_node':[{'node':n,'event':e,'count':v} for (n,e),v in sorted(countsnode.items(),key=str)],'node_source_event_reasons':[{'node':n,'source':s,'event':e,'reason':re,'count':v} for (n,s,e,re),v in sorted(reasons.items(),key=str)],'app_attempt_reasons':[{'node':n,'reason':re,'count':v} for (n,re),v in sorted(attempts.items())],'feedback':[{'node':n,'peer':p,'source':s,'reason':re,'count':v} for (n,p,s,re),v in sorted(feedback.items(),key=str)],'feedback_before_nsdp_histogram':[{'node':n,'source':s,'reason':re,'histogram':dict(c)} for (n,s,re),c in sorted(snapreason.items(),key=str)],'nsdp_state':nsdp_rows,'shared_nwk_queue':queue_rows,'residence':[{'node':n,'source':s,'nwk_queue_wait_s':stats(waits[n,s]),'hop_admission_to_nsdp_release_completion_s':stats(hoptimes[n,s]),'enqueue_to_nsdp_release_completion_s':stats(custody[n,s])} for n,s in sorted(set(waits)|set(hoptimes))],'unmatched_episode_events':[[*k,v] for k,v in unmatched.items()],'nsdp_snapshot_mismatch_count':len(nsdp_mismatch),'nsdp_snapshot_mismatch_examples':nsdp_mismatch[:20],'queue_snapshot_mismatch_count':len(queue_mismatch),'queue_snapshot_mismatch_examples':queue_mismatch[:20],'pending_enqueues':[{'node':n,'source':k[0],'destination':k[1],'sequence':k[2],'enqueue_s':t,'event_index':ei,'age_at_stop_s':DURATION-t} for (n,k),q in enqueue.items() for t,ei in q],'pending_hop':[{'node':n,'source':k[0],'destination':k[1],'sequence':k[2],**x,'age_at_stop_s':DURATION-x['admission_s']} for (n,k),q in hop.items() for x in q],'processing_seconds':time.time()-start,'limits':['Historical seed128 trace omits admission/custody/HOP observation events; missing observations are unavailable, not zero.','Failed nwk_admission counts are retry/pump observations, not unique blocked packets.','Delivery delay includes only applications delivered by stop; unmatched native sends cannot alone distinguish drops and pending.','NSDP is per original source/destination; shared NWK queue occupancy must not be called shared NSDP.','HOP admission-to-completion ends at NSDP release; a DACK can retain HOP capacity until a later expiry. This is not total HOP capacity residence.','All causal interpretation is observational; no policy counterfactual was executed.']}
 (OUT/f's{seed}.json').write_text(json.dumps(result,indent=2));(OUT/f's{seed}-event-examples.json').write_text(json.dumps([{'node':k[0],'event':k[1],'reason':k[2],'examples':v} for k,v in examples.items()],indent=2))
 csvout(OUT/f's{seed}-flow-timeline.csv',flowbins);csvout(OUT/f's{seed}-events.csv',events);csvout(OUT/f's{seed}-state-timeline.csv',statebins);csvout(OUT/f's{seed}-gateway-routes.csv',route)
 # Union field names because historical traces may omit episode fields.
 if episodes:
  keys=list(dict.fromkeys(k for x in episodes for k in x));csvout(OUT/f's{seed}-hop-episodes.csv',[{k:x.get(k,'') for k in keys} for x in episodes])
 print(json.dumps({'seed':seed,'flows':flows,'rows':lineno+1,'nsdp_mismatches':len(nsdp_mismatch),'queue_mismatches':len(queue_mismatch),'elapsed_s':time.time()-start}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--seeds',nargs='+',type=int,default=[128,129,130]);p.add_argument('--source-root',type=Path,default=SOURCE);p.add_argument('--out',type=Path,default=OUT);a=p.parse_args()
 SOURCE=a.source_root.resolve();OUT=a.out.resolve();OUT.mkdir(parents=True,exist_ok=True)
 for seed in a.seeds:analyze(seed)
