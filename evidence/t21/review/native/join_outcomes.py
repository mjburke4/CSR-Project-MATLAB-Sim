#!/usr/bin/env python3
"""Join native HOP completion to final application outcome; retain DACK capacity hold.
Read-only extra pass over accepted seed129/130 trace; identities are within-run.
"""
import csv,gzip,json,hashlib,argparse
from pathlib import Path
from collections import Counter,defaultdict
from analyze_native import HashedLines,fields,stats,csvout,sha

def run(source,out,seed):
 trace=source/f'evidence/tranche-20-ns3-reference/s{seed}/ns3-trace.csv.gz'
 baseline=json.loads((out/f's{seed}.json').read_text());assert sha(trace)==baseline['input']['trace_gzip_sha256']
 delivered={};records=[];active={};capacity=[];unmatched=[];thresholds=Counter();completions=Counter()
 with gzip.open(trace,'rb') as f:
  lines=HashedLines(f);r=csv.reader(lines);h=next(r);ix={k:i for i,k in enumerate(h)}
  for row in r:
   ev=row[ix['event']]
   if ev not in ('nwk_delivery','hop_admission','hop_completion','hop_capacity_release'):continue
   src=int(row[ix['src']]) if row[ix['src']] else None
   if src not in (4,7,8):continue
   dst=int(row[ix['dst']]);seq=int(row[ix['sequence']]);t=float(row[ix['time_s']]);key=(src,dst,seq)
   if ev=='nwk_delivery':delivered.setdefault(key,t);continue
   node=int(row[ix['node']]);peer=int(row[ix['peer']])
   if node not in (4,7,8):continue
   d=fields(row[ix['detail']]);hs=int(d['hop_sequence']);ident=(node,peer,src,dst,seq,hs);reason=row[ix['reason']]
   if ev=='hop_admission':
    assert ident not in active
    active[ident]={'seed':seed,'node':node,'peer':peer,'source':src,'destination':dst,'sequence':seq,'hop_sequence':hs,'admission_s':t,'admission_event_index':int(row[ix['event_index']]),'threshold_at_admission':int(d['threshold'])}
    thresholds[node,src,int(d['threshold'])]+=1
   if ev=='hop_completion':
    rec={'seed':seed,'node':node,'peer':peer,'source':src,'destination':dst,'sequence':seq,'hop_sequence':hs,'completion_s':t,'reason':reason,'resend_count':int(d['resend_count']),'capacity_released':int(d['capacity_released']),'nsdp_released':int(d['nsdp_released']),'event_index':int(row[ix['event_index']])};records.append(rec)
   if ev in ('hop_completion','hop_capacity_release') and d.get('capacity_released')=='1':
    start=active.pop(ident,None)
    if start is None:unmatched.append({'identity':ident,'event':ev,'time_s':t,'reason':reason})
    else:
     capacity.append({**start,'release_s':t,'release_reason':reason,'release_event':ev,'capacity_retention_s':t-start['admission_s']})
 assert lines.h.hexdigest()==baseline['input']['trace_raw_sha256'] and lines.n==baseline['input']['trace_raw_bytes']
 for r in records:
  key=(r['source'],r['destination'],r['sequence']);received=delivered.get(key);r['unique_delivered_by_stop']=received is not None;r['first_delivery_s']=received;r['delivery_after_hop_completion']=None if received is None else received>r['completion_s']
  completions[r['node'],r['source'],r['reason'],received is not None]+=1
 caps=defaultdict(list)
 for r in capacity:caps[r['node'],r['source']].append(r['capacity_retention_s'])
 result={'seed':seed,'input_binding':baseline['input'],'source_node_outcome_counts':[{'node':n,'source':s,'hop_completion_reason':reason,'unique_delivered_by_stop':yes,'count':v} for (n,s,reason,yes),v in sorted(completions.items())],'capacity_retention_completed':[{'node':n,'source':s,**stats(v)} for (n,s),v in sorted(caps.items())],'capacity_pending_at_stop':[{**v,'age_at_stop_s':6000-v['admission_s']} for v in active.values()],'capacity_release_without_admission':unmatched,'threshold_histograms':[{'node':n,'source':s,'threshold':th,'admissions':v} for (n,s,th),v in sorted(thresholds.items())],'limits':['HOP no_ack can coexist with an end-to-end delivery when feedback is lost; this is not automatically an application drop.','Capacity retention ends at actual capacity_released=1; DACK hold is included, unlike NSDP-release completion residence.','Native event sequences identify within-run applications only; source sequence counters differ between simulators.']}
 (out/f's{seed}-outcome-joins.json').write_text(json.dumps(result,indent=2));csvout(out/f's{seed}-completion-outcomes.csv',records);csvout(out/f's{seed}-capacity-episodes.csv',capacity)
 print(json.dumps({'seed':seed,'unmatched_capacity':len(unmatched),'counts':result['source_node_outcome_counts'],'capacity_pending':len(active)}),flush=True)
if __name__=='__main__':
 base=Path(__file__).resolve().parents[2];p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,default=base/'csr20');p.add_argument('--out',type=Path,default=Path(__file__).resolve().parent);p.add_argument('--seeds',nargs='+',type=int,default=[129,130]);a=p.parse_args()
 for seed in a.seeds:run(a.source_root,a.out,seed)
