#!/usr/bin/env python3
"""Independent audit limited to identities flagged by raw repeat counting."""
import argparse,csv,gzip,json
from collections import Counter,defaultdict,deque
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'t24/review'
BASE=ROOT/'t23-return-review/issued-overlay/evidence/tranche-20-ns3-reference'
EVENTS={'nwk_enqueue','nwk_forward','hop_admission','hop_completion','hop_capacity_release','hop_feedback','nwk_delivery','app_send'}
def detail(s):return dict(x.split('=',1) for x in s.split(';') if '=' in x)
def audit(seed):
    repeats=json.loads((OUT/f's{seed}-repeated-enqueues.json').read_text())
    keys={(str(r['src']),str(r['dst']),str(r['sequence'])) for r in repeats}
    rows=[]
    with gzip.open(BASE/f's{seed}/ns3-trace.csv.gz','rt',newline='') as f:
      reader=csv.reader(f);h=next(reader);ix={k:h.index(k) for k in h}
      for r in reader:
        if r[ix['event']] in EVENTS and (r[ix['src']],r[ix['dst']],r[ix['sequence']]) in keys:
          rows.append(dict(zip(h,r)))
    (OUT/f's{seed}-repeat-app-lineage.json').write_text(json.dumps(rows,indent=2)+'\n')
    queue=defaultdict(deque);forward={};hop={};hold={};active=Counter();ordinal=Counter();eps=[];errors=[]
    def need(ok,*err):
      if not ok:errors.append(err)
      return ok
    for r in rows:
      node=r['node'];key=(node,r['src'],r['dst'],r['sequence']);t=float(r['time_s']);ev=r['event'];d=detail(r['detail']);eid=int(r['event_index'])
      if ev=='nwk_enqueue':
        ordinal[key]+=1
        ep={'node':int(node),'source':int(r['src']),'destination':int(r['dst']),'application_sequence':int(r['sequence']),'ordinal':ordinal[key],'enqueue_event':eid,'enqueue_s':t,'other_owners_at_enqueue':active[key],'forward_s':None,'admission_s':None,'completion_s':None,'capacity_release_s':None}
        queue[key].append(ep);active[key]+=1;eps.append(ep)
      elif ev=='nwk_forward':
        if not need(bool(queue[key]),eid,'missing_enqueue'):continue
        ep=queue[key].popleft();ep['forward_s']=t;ep['forward_event']=eid
        need(key not in forward,eid,'forward_collision');forward[key]=ep
      elif ev=='hop_admission':
        if not need(key in forward,eid,'missing_forward'):continue
        ep=forward.pop(key);need(ep['forward_s']==t,eid,'forward_time_mismatch')
        hkey=(key,r['peer'],d['hop_sequence']);need(hkey not in hop,eid,'hop_collision');hop[hkey]=ep
        ep['admission_s']=t;ep['admission_event']=eid;ep['peer']=int(r['peer']);ep['hop_sequence']=int(d['hop_sequence'])
      elif ev=='hop_completion':
        hkey=(key,r['peer'],d['hop_sequence'])
        if not need(hkey in hop,eid,'missing_hop'):continue
        ep=hop.pop(hkey);ep['completion_s']=t;ep['completion_event']=eid;ep['completion_reason']=r['reason'];active[key]-=1
        need(d['nsdp_released']=='1',eid,'nsdp_unreleased')
        if r['reason']=='dack':
          need(d['capacity_released']=='0',eid,'dack_capacity');need(hkey not in hold,eid,'hold_collision');hold[hkey]=ep
        else:
          need(d['capacity_released']=='1',eid,'missing_capacity_release');ep['capacity_release_s']=t
      elif ev=='hop_capacity_release':
        hkey=(key,r['peer'],d['hop_sequence'])
        if not need(hkey in hold,eid,'missing_hold'):continue
        ep=hold.pop(hkey);ep['capacity_release_s']=t;ep['capacity_release_event']=eid
    repeated=[]
    for ep in eps:
      if ep['ordinal']<2:continue
      ep['custody_owner_seconds']=min(6000,ep['completion_s'] or 6000)-max(300,ep['enqueue_s'])
      ep['waiting_owner_seconds']=min(6000,ep['admission_s'] or 6000)-max(300,ep['enqueue_s'])
      ep['hop_capacity_seconds']=0 if ep['admission_s'] is None else min(6000,ep['capacity_release_s'] or 6000)-max(300,ep['admission_s'])
      repeated.append(ep)
    need(len(repeated)==len(repeats),'repeat_count',len(repeated),len(repeats))
    result={'seed':seed,'selected_application_identities':len(keys),'raw_selected_rows':len(rows),'repeated_instances':repeated,'errors':errors,'repeated_totals':{'count':len(repeated),'overlap_at_enqueue':sum(e['other_owners_at_enqueue']>0 for e in repeated),'forwarded':sum(e['admission_s'] is not None for e in repeated),'completed':sum(e['completion_s'] is not None for e in repeated),'capacity_released':sum(e['capacity_release_s'] is not None for e in repeated),'custody_owner_seconds':sum(e['custody_owner_seconds'] for e in repeated),'waiting_owner_seconds':sum(e['waiting_owner_seconds'] for e in repeated),'hop_capacity_seconds':sum(e['hop_capacity_seconds'] for e in repeated)}}
    print(json.dumps({'seed':seed,'errors':errors,'totals':result['repeated_totals']}),flush=True)
    return result
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--native-reference-root',type=Path,default=BASE)
 parser.add_argument('--output',type=Path,default=OUT,help='Independent raw audit directory (input and output).')
 args=parser.parse_args();BASE=args.native_reference_root.resolve();OUT=args.output.resolve();OUT.mkdir(parents=True,exist_ok=True)
 r={'schema':'csr-t24-independent-repeat-lifetime-audit-v1','results':[audit(s) for s in (129,130)]}
 (OUT/'repeat-lifetime-audit.json').write_text(json.dumps(r,indent=2)+'\n')
