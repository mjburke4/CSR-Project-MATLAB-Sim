#!/usr/bin/env python3
"""Independent within-engine custody-path phase reconstruction. No cross-engine ID pairing."""
import csv,gzip,json,hashlib,statistics,math
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal,ROUND_HALF_EVEN
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
CUTOFF=6000_000_000_000
SOURCES=[2,3,4,5,7,8]
def ns(x):return int((Decimal(x)*10**9).to_integral_value(rounding=ROUND_HALF_EVEN))
def detail(x):return dict(p.split('=',1) for p in x.split(';') if '=' in p)
def dump_csv(path,rows):
 if not rows:return
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read_model(seed):
 p=ROOT/f'terminal6000_return/data/s{seed}/attempt_001/raw/protocol_trace.csv';apps={};counts=Counter();ignored=[]
 events={'app_generate','network_enqueue','hop_admit','hop_sent','app_receive','app_drop','hop_retry','hop_failed'}
 for r in csv.DictReader(p.open()):
  e=r['Event'];counts[e]+=1
  if e not in events or r['FrameKind'] not in ('APP','DATA'):continue
  t=ns(r['TimeSeconds']); aid=int(r['PacketId']); node=int(r['NodeId'])
  if e=='app_generate':
   assert aid not in apps;apps[aid]={'id':aid,'source':node,'gen':t,'received':None,'hops':[],'drops':[],'receive_count':0}
   continue
  a=apps.get(aid)
  if a is None:ignored.append(r);continue
  if e=='network_enqueue':
   assert not any(h['node']==node for h in a['hops']), ('repeat_node',seed,aid,node)
   a['hops'].append({'node':node,'enqueue':t,'admit':None,'tx':[],'retries':[],'failures':[]})
  elif e=='app_receive':
   a['receive_count']+=1
   if a['received'] is None:a['received']=t
  elif e=='app_drop':a['drops'].append((t,node,r['Reason']))
  else:
   hh=[h for h in a['hops'] if h['node']==node];assert len(hh)==1,(e,aid,node)
   h=hh[0]
   if e=='hop_admit':assert h['admit'] is None;h['admit']=t;h['peer']=int(r['PeerId']);h['seq']=int(r['Sequence'])
   elif e=='hop_sent':h['tx'].append(t)
   elif e=='hop_retry':h['retries'].append(t)
   elif e=='hop_failed':h['failures'].append((t,r['Reason']))
 assert not ignored
 return apps,{'input':str(p.relative_to(ROOT)),'sha256':sha(p),'events':dict(counts),'tx_scope':'hop_sent is physical DATA sent indication while HOP owner exists; first TX coverage checked for every admitted delivered hop. Later orphan-copy TX can lack hop_sent, so retransmission counts are lower bounds.'}
def read_native(seed):
 p=ROOT/f'recovered/native_origin/evidence/tranche-25-ns3-reference/s{seed}/ns3-trace.csv.gz';apps={};counts=Counter();txmap={};unmatched=[];rx={};duplicate_enqueues=0
 want={'app_send','nwk_enqueue','hop_admission','nwk_delivery','tx_start','hop_completion','hop_feedback'}
 with gzip.open(p,'rt',newline='') as f:
  rd=csv.reader(f);header=next(rd);idx={s:i for i,s in enumerate(header)}
  for rr in rd:
   e=rr[idx['event']];counts[e]+=1
   if e not in want:continue
   r=dict(zip(header,rr))
   if r['packet_type']!='data':continue
   t=ns(r['time_s']);node=int(r['node'])
   if e=='tx_start':
    key=(node,int(r['sequence']))
    if key in txmap:txmap[key]['tx'].append(t)
    else:unmatched.append({'time_ns':t,'node':node,'seq':int(r['sequence'])})
    continue
   aid=int(r['sequence'])
   if e=='app_send':
    assert aid not in apps;apps[aid]={'id':aid,'source':int(r['src']),'gen':t,'received':None,'hops':[],'drops':[],'receive_count':0}
    continue
   a=apps[aid]
   if e=='nwk_enqueue':
    assert r['success']=='1'
    duplicate_enqueues+=int(any(h['node']==node for h in a['hops']))
    a['hops'].append({'node':node,'enqueue':t,'admit':None,'tx':[],'retries':[],'failures':[]})
   elif e=='nwk_delivery':
    a['receive_count']+=1
    if a['received'] is None:a['received']=t
   elif e=='hop_feedback':
    key=(aid,node,t);assert key not in rx
    rx[key]=(int(r['peer']),int(detail(r['detail'])['hop_sequence']))
   elif e=='hop_admission':
    if r['success']!='1':continue
    hh=[h for h in a['hops'] if h['node']==node and h['admit'] is None];assert hh,(e,aid,node)
    h=hh[0];h['admit']=t;h['peer']=int(r['peer']);h['seq']=int(detail(r['detail'])['hop_sequence'])
    key=(node,h['seq']);assert key not in txmap,('hopseq_reuse',seed,key);txmap[key]=h
   elif e=='hop_completion' and r['reason']=='no_ack':
    h=txmap[node,int(detail(r['detail'])['hop_sequence'])];h['failures'].append((t,r['reason']))
 assert not unmatched, unmatched[:5]
 for aid,a in apps.items():
  a['raw_hops']=a['hops']
  if a['received'] is not None:
   h=txmap[rx[aid,1,a['received']]]
  else:h=a['hops'][-1]
  path=[]
  while True:
   assert not any(h is old for old in path);path.append(h)
   if h['node']==a['source'] and h['enqueue']==a['gen']:break
   h=txmap[rx[aid,h['node'],h['enqueue']]]
  a['hops']=list(reversed(path))
 return apps,{'input':str(p.relative_to(ROOT)),'sha256':sha(p),'events':dict(counts),'unmatched_data_tx':unmatched,'duplicate_nwk_enqueues':duplicate_enqueues,'tx_scope':'tx_start DATA maps to installed HOP sequence at transmitting node; map retained after owner expiration; no HOP sequence reuse.'}
def phases(model,seed,apps):
 rows=[];hoprows=[];checks=Counter()
 refs={}
 if model=='native':
  rp=ROOT/f'recovered/issued/csr6000/reference/s{seed}/applications.csv';refs={int(r['native_app_id']):r for r in csv.DictReader(rp.open())}
 else:
  rp=ROOT/f'terminal6000_return/data/s{seed}/attempt_001/analysis/applications.csv';refs={int(r['PacketId']):r for r in csv.DictReader(rp.open())}
 assert set(refs)==set(apps)
 for aid,a in apps.items():
  end=a['received'] if a['received'] is not None else CUTOFF;delivered=a['received'] is not None
  hhs=[h for h in a['hops'] if h['enqueue']<=end];nw=mac=post=0;retry_events=0;txcounts=0;laststage=None
  assert hhs and hhs[0]['node']==a['source'] and hhs[0]['enqueue']==a['gen']
  for i,h in enumerate(hhs):
   hend=hhs[i+1]['enqueue'] if i+1<len(hhs) else end
   admit=h['admit'];admit=admit if admit is not None and admit<=hend else None
   tx=[t for t in h['tx'] if t<=hend];first=min(tx) if tx else None
   if admit is None:
    assert first is None;dn=hend-h['enqueue'];dm=dp=0;stage='NWK waiting'
   elif first is None:
    dn=admit-h['enqueue'];dm=hend-admit;dp=0;stage='awaiting first physical TX'
   else:
    dn=admit-h['enqueue'];dm=first-admit;dp=hend-first;stage='after first physical TX'
   assert min(dn,dm,dp)>=0,(model,seed,aid,i,dn,dm,dp)
   if delivered:assert admit is not None and first is not None,(model,seed,aid,i,'missing_first_tx')
   nw+=dn;mac+=dm;post+=dp;laststage=stage;retry_events+=sum(t<=hend for t in h['retries']);txcounts+=len(tx)
   hoprows.append({'model':model,'seed':seed,'app_id':aid,'source':a['source'],'delivered':int(delivered),'path_index':i,'custody_node':h['node'],'next_node':h.get('peer',''),'enqueue_ns':h['enqueue'],'hop_admit_ns':admit if admit is not None else '', 'first_tx_ns':first if first is not None else '','path_end_ns':hend,'nwk_wait_s':dn/1e9,'first_mac_wait_s':dm/1e9,'post_first_tx_s':dp/1e9,'data_sent_observations_before_path_end':len(tx),'hop_retry_events_before_path_end':sum(t<=hend for t in h['retries']),'owner_failures_before_path_end':sum(t<=hend for t,_ in h['failures'])})
  age=end-a['gen'];assert nw+mac+post==age
  q=refs[aid]
  if model=='native':
   assert a['source']==int(q['source']) and a['gen']==int(q['generated_time_ns'])
   assert delivered==(q['status']=='delivered')
   if delivered:
    assert a['received']==int(q['first_delivery_time_ns']);assert nw==int(q['total_nwk_wait_ns']),(seed,aid,nw,q['total_nwk_wait_ns'])
   rawstatus=q['status']
  else:
   assert a['source']==int(q['SourceId']) and abs(a['gen']-ns(q['GeneratedSeconds']))<2
   assert delivered==(q['Outcome']=='delivered')
   if delivered:assert abs(a['received']-ns(q['ReceivedSeconds']))<2
   rawstatus=q['Outcome']
  checks['admitted_apps']+=1;checks['delivered_apps']+=delivered;checks['delivered_hops']+=len(hhs) if delivered else 0
  rows.append({'model':model,'seed':seed,'source':a['source'],'app_id':aid,'generated_ns':a['gen'],'end_ns':end,'outcome':'delivered' if delivered else 'unresolved','raw_status':rawstatus,'latency_or_unresolved_age_s':age/1e9,'nwk_wait_s':nw/1e9,'first_mac_wait_s':mac/1e9,'post_first_tx_s':post/1e9,'last_recorded_custody_node':hhs[-1]['node'],'last_recorded_stage':laststage,'custody_hops':len(hhs),'data_sent_observations_before_end':txcounts,'hop_retry_events_before_end':retry_events,'provisional_drop_events_before_end':sum(t<=end for t,_,_ in a['drops']),'late_delivery_after_any_drop':int(delivered and any(t<a['received'] for t,_,_ in a['drops']))})
 dump_csv(OUT/f'{model}_s{seed}_applications.csv',rows);dump_csv(OUT/f'{model}_s{seed}_custody_phases.csv',hoprows)
 return rows,hoprows,dict(checks)
def summarize(rows):
 out=[]
 for model in ['native','matlab']:
  for seed in [131,132]:
   for src in SOURCES:
    a=[r for r in rows if (r['model'],r['seed'],r['source'])==(model,seed,src)];d=[r for r in a if r['outcome']=='delivered'];u=[r for r in a if r['outcome']=='unresolved']
    avg=lambda key:statistics.fmean(r[key] for r in d) if d else None
    out.append({'model':model,'seed':seed,'source':src,'admitted':len(a),'delivered':len(d),'unresolved':len(u),'mean_latency_s':avg('latency_or_unresolved_age_s'),'mean_nwk_wait_s':avg('nwk_wait_s'),'mean_first_mac_wait_s':avg('first_mac_wait_s'),'mean_post_first_tx_s':avg('post_first_tx_s'),'mean_custody_hops':avg('custody_hops'),'mean_data_sent_observations':avg('data_sent_observations_before_end'),'unresolved_last_NWK':sum(r['last_recorded_stage']=='NWK waiting' for r in u),'unresolved_last_preTX':sum(r['last_recorded_stage']=='awaiting first physical TX' for r in u),'unresolved_last_postTX':sum(r['last_recorded_stage']=='after first physical TX' for r in u)})
 return out
if __name__=='__main__':
 allrows=[];allhops=[];audits=[]
 for seed in [131,132]:
  for model,reader in [('matlab',read_model),('native',read_native)]:
   apps,receipt=reader(seed);rr,hh,checks=phases(model,seed,apps);allrows+=rr;allhops+=hh;audits.append({'model':model,'seed':seed,**receipt,'checks':checks});print('pass',model,seed,checks,flush=True)
 summary=summarize(allrows);dump_csv(OUT/'source_phases.csv',summary)
 indexed={(r['model'],r['seed'],r['source']):r for r in summary};nativeN=sum(r['delivered'] for r in summary if r['model']=='native');contrib=[]
 for seed in [131,132]:
  for src in SOURCES:
   n=indexed['native',seed,src];m=indexed['matlab',seed,src]
   if not n['delivered'] or not m['delivered']:continue
   w=n['delivered']/nativeN
   contrib.append({'seed':seed,'source':src,'native_weight':w,'native_delivered':n['delivered'],'matlab_delivered':m['delivered'],**{k+'_difference':m[k]-n[k] for k in ('mean_latency_s','mean_nwk_wait_s','mean_first_mac_wait_s','mean_post_first_tx_s')},**{k+'_weighted_contribution_s':w*(m[k]-n[k]) for k in ('mean_latency_s','mean_nwk_wait_s','mean_first_mac_wait_s','mean_post_first_tx_s')}})
 dump_csv(OUT/'source_weighted_contributions.csv',sorted(contrib,key=lambda r:-r['mean_latency_s_weighted_contribution_s']))
 custody=[]
 for model in ['native','matlab']:
  for seed in [131,132]:
   for src in SOURCES:
    d=indexed[model,seed,src]['delivered']
    for node in [2,3,4,5,7,8]:
     hh=[h for h in allhops if h['model']==model and h['seed']==seed and h['source']==src and h['custody_node']==node and h['delivered']]
     if hh:custody.append({'model':model,'seed':seed,'source':src,'custody_node':node,'delivered_hops':len(hh),'nwk_wait_per_delivered_app_s':sum(h['nwk_wait_s'] for h in hh)/d,'first_mac_wait_per_delivered_app_s':sum(h['first_mac_wait_s'] for h in hh)/d,'post_first_tx_per_delivered_app_s':sum(h['post_first_tx_s'] for h in hh)/d})
 dump_csv(OUT/'delivered_phases_by_custody_node.csv',custody)
 result={'status':'pass','audits':audits,'source_summary':summary,'native_delivery_weights_sum':sum(r['native_weight'] for r in contrib),'weighted_gap_components_s':{k:sum(r[k+'_weighted_contribution_s'] for r in contrib) for k in ('mean_latency_s','mean_nwk_wait_s','mean_first_mac_wait_s','mean_post_first_tx_s')},'scope':'Within-engine application IDs only. First unique delivery ends latency. NWK enqueue starts each custody hop; HOP admission separates NWK waiting; first observed physical DATA sent separates initial MAC waiting; remainder includes airtime, retries, feedback-related queueing, and receiver/relay admission. Owner expiry does not end or reset application clocks. Unfinished stages are last recorded custody stages, not all-copy liveness or proof of eventual loss. MATLAB post-first-TX physical TX counts are lower bounds because ownerless DATA sent indications omit hop_sent; first-TX coverage is complete for every delivered hop.'}
 (OUT/'audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result['weighted_gap_components_s'],indent=2))
