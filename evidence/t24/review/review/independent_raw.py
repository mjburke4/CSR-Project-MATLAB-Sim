#!/usr/bin/env python3
"""Independent raw audit: no census implementation imports or output reuse."""
import argparse,csv,gzip,json,hashlib
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'t23-return-review/issued-overlay/evidence/tranche-20-ns3-reference'
OUT=ROOT/'t24/review'

def details(x):
    return dict(p.split('=',1) for p in x.split(';') if '=' in p)

def scan(seed):
    p=BASE/f's{seed}/ns3-trace.csv.gz'
    counts=Counter(); identities=defaultdict(Counter); target=Counter()
    custody=Counter(); custody_area=Counter(); last={}; peak=Counter()
    repeated_rows=[]; feedback_same_hop={}; replay=Counter(); pending_feedback={}
    target_rows=[]; errors=[]; event_max=0
    with gzip.open(p,'rt',newline='') as f:
      reader=csv.reader(f); h=next(reader); ix={k:h.index(k) for k in h}
      for row in reader:
        event_max+=1
        event=row[ix['event']]
        if event not in {'nwk_enqueue','nwk_nsdp_release','hop_completion','hop_feedback','hop_admission','nwk_forward','hop_capacity_release'}: continue
        node=row[ix['node']]; src=row[ix['src']]; dst=row[ix['dst']]; app=row[ix['sequence']]
        flow=(node,src,dst); identity=(*flow,app)
        counts[event]+=1
        t=float(row[ix['time_s']]); eid=int(row[ix['event_index']]); detail=details(row[ix['detail']])
        is_target=node=='8' and src=='7' and dst=='1'
        if is_target:
          target[event]+=1
          target_rows.append(dict(zip(h,row)))
        if event in {'nwk_enqueue','nwk_nsdp_release'}:
          if flow in last:
            custody_area[flow]+=custody[flow]*(max(300,min(t,6000))-max(300,min(last[flow],6000)))
          last[flow]=t
          before=custody[flow]
          custody[flow]+=1 if event=='nwk_enqueue' else -1
          peak[flow]=max(peak[flow],custody[flow])
          expected=int(detail['nsdp_count'] if event=='nwk_enqueue' else detail['count_after'])
          if custody[flow]!=expected: errors.append([eid,event,'custody_snapshot',custody[flow],expected])
          if event=='nwk_nsdp_release' and before!=int(detail['count_before']):errors.append([eid,event,'before',before,detail['count_before']])
          if custody[flow]<0: errors.append([eid,event,'negative_custody'])
        if event=='nwk_enqueue':
          prior=identities[flow][app]; identities[flow][app]+=1
          if prior:
            repeated_rows.append({'event_index':eid,'time_s':t,'node':int(node),'src':int(src),'dst':int(dst),'sequence':int(app),'owner_ordinal':prior+1,'peer':row[ix['peer']]})
          if row[ix['reason']]=='relay':
            fk=(node,row[ix['peer']],src,dst,app,t)
            if fk in pending_feedback: errors.append([eid,'overlapping_enqueue_feedback_key'])
            pending_feedback[fk]=(eid,prior>0)
        elif event=='hop_feedback' and detail.get('first_reception')=='1' and detail.get('nsdp_state_valid')=='1':
          fk=(node,row[ix['peer']],src,dst,app,t)
          enq=pending_feedback.pop(fk,None)
          if enq is None:
            if int(detail['nsdp_count_after'])>int(detail['nsdp_count_before']):errors.append([eid,'feedback_increment_without_enqueue'])
            continue
          if int(detail['nsdp_count_after'])-int(detail['nsdp_count_before'])!=1:errors.append([eid,'enqueue_feedback_wrong_increment'])
          hk=(node,row[ix['peer']],detail['hop_sequence'],src,dst,app)
          prev=feedback_same_hop.get(hk)
          if enq[1]:
            replay[('same_hop_dack' if prev and prev['reason']=='dack' else 'other_repeat')]+=1
            if is_target:replay[('target_same_hop_dack' if prev and prev['reason']=='dack' else 'target_other_repeat')]+=1
            for rr in reversed(repeated_rows):
              if rr['event_index']==enq[0]:
                rr.update(feedback_index=eid,hop_sequence=int(detail['hop_sequence']),reason=row[ix['reason']],prior_same_hop_feedback=prev)
                break
          feedback_same_hop[hk]={'event_index':eid,'reason':row[ix['reason']],'time_s':t}
    for flow,now in last.items(): custody_area[flow]+=custody[flow]*(6000-max(300,min(now,6000)))
    flows=[]
    for flow in sorted(identities,key=lambda f:tuple(map(int,f))):
      pop=identities[flow]
      flows.append({'node':int(flow[0]),'src':int(flow[1]),'dst':int(flow[2]),'enqueues':sum(pop.values()),'unique_applications':len(pop),'repeated_enqueues':sum(pop.values())-len(pop),'applications_repeated':sum(n>1 for n in pop.values()),'max_enqueues_per_app':max(pop.values()),'nsdp_owners_at_stop':custody[flow],'peak_nsdp':peak[flow],'nsdp_owner_seconds_300_6000':custody_area[flow],'mean_nsdp_300_6000':custody_area[flow]/5700})
    if pending_feedback: errors.append(['unmatched_relay_enqueue_count',len(pending_feedback)])
    (OUT/f's{seed}-node8-source7-raw-events.json').write_text(json.dumps(target_rows,indent=2)+'\n')
    (OUT/f's{seed}-repeated-enqueues.json').write_text(json.dumps(repeated_rows,indent=2)+'\n')
    return {'seed':seed,'trace_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'rows':event_max,'event_counts':dict(counts),'node8_source7_event_counts':dict(target),'repeat_origin_counts':dict(replay),'flows':flows,'errors':errors}

def main():
  global BASE,OUT
  parser=argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--native-reference-root',type=Path,default=BASE)
  parser.add_argument('--output',type=Path,default=OUT)
  args=parser.parse_args();BASE=args.native_reference_root.resolve();OUT=args.output.resolve();OUT.mkdir(parents=True,exist_ok=True)
  results=[]
  for seed in (129,130):
    result=scan(seed);results.append(result)
    print(json.dumps({k:result[k] for k in ['seed','rows','node8_source7_event_counts','repeat_origin_counts','errors']}),flush=True)
  (OUT/'independent-raw.json').write_text(json.dumps({'schema':'csr-t24-independent-raw-audit-v1','results':results},indent=2)+'\n')
if __name__=='__main__':main()
