#!/usr/bin/env python3
"""First unique delivery latency, with explicit right-censoring limitations."""
import argparse,csv,json,math,statistics
from pathlib import Path
from generate_scenarios import ROOT,sha
def rows(p):
 with Path(p).open(newline='',encoding='utf-8-sig') as f: return list(csv.DictReader(f))
def percentile(values,p):
 if not values: return None
 x=sorted(values); a=(len(x)-1)*p; lo=math.floor(a); hi=math.ceil(a)
 return x[lo]+(a-lo)*(x[hi]-x[lo])
def metrics(apps,attempts,native=False,duplicates=0):
 assert len({x['id'] for x in apps})==len(apps),'Duplicate application identity'
 counts={k:sum(x['outcome']==k for x in apps) for k in ('delivered','dropped','pending','unresolved')}
 assert sum(counts.values())==len(apps) and attempts>=len(apps),'Accounting mismatch'
 values=[x['latency_s'] for x in apps if x['outcome']=='delivered']
 assert all(v is not None and math.isfinite(v) and v>=0 for v in values),'Invalid latency'
 return dict(admitted=len(apps),attempts=attempts,admission_blocked=attempts-len(apps),delivered_unique=counts['delivered'],explicit_drops=None if native else counts['dropped'],pending=None if native else counts['pending'],unresolved=counts['unresolved'],delivery_ratio=counts['delivered']/len(apps) if apps else None,duplicate_delivery_events=duplicates,median_latency_s=percentile(values,.5),p95_latency_s=percentile(values,.95),mean_latency_s=statistics.fmean(values) if values else None)
def matlab(d):
 apps=[dict(id=r['PacketId'],source=r['SourceId'],destination=r['DestinationId'],generated_s=float(r['GeneratedSeconds']),outcome=r['Outcome'],latency_s=float(r['LatencySeconds']) if r['Outcome']=='delivered' else None) for r in rows(d/'applications.csv')]
 attempts=sum(int(r['Attempts']) for r in rows(d/'raw/application_admission_statistics.csv'))
 m=metrics(apps,attempts); nodes=rows(d/'node_statistics.csv'); m['node2_waiting_for_hop_at_stop']=next(int(r['WaitingForHop']) for r in nodes if int(r['Id'])==2)
 return apps,m
def native(d):
 sent={}; duplicates=0
 for r in rows(d/'ns3-trace.csv'):
  if r['event'] not in ('app_send','nwk_delivery'): continue
  key=(r['src'],r['dst'],r['sequence']); t=float(r['time_s']); assert math.isfinite(t) and 0<=t<600,'Invalid event time'
  if r['event']=='app_send':
   assert key not in sent,'Duplicate generation'
   sent[key]=dict(id=':'.join(key),source=key[0],destination=key[1],generated_s=t,outcome='unresolved',latency_s=None)
  else:
   assert key in sent,'Delivery without generation'; app=sent[key]
   if app['outcome']=='delivered': duplicates+=1
   else: app.update(outcome='delivered',latency_s=t-app['generated_s'])
 admission=rows(d/'app-admission-diagnostics.csv')
 assert sum(int(r['admitted']) for r in admission)==len(sent),'Incomplete native trace'
 for r in admission:
  assert int(r['admitted'])==sum(x['source']==r['source'] for x in sent.values()),'Per-flow admitted mismatch'
  assert int(r['attempts'])==int(r['admitted'])+sum(int(v) for k,v in r.items() if k.startswith('blocked_')),'Admission partition mismatch'
 apps=list(sent.values()); m=metrics(apps,sum(int(r['attempts']) for r in admission),True,duplicates); m['node2_waiting_for_hop_at_stop']=None
 return apps,m
def main():
 p=argparse.ArgumentParser(); p.add_argument('--matlab',type=Path,required=True); p.add_argument('--native',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=False)
 result={'status':'running','acceptance_established':False,'cases':[]}
 try:
  plan=json.loads((ROOT/'plan.json').read_text())
  for base in (a.matlab,a.native):
   assert json.loads((base/'plan.json').read_text())==plan,'Run scenario plan mismatch'
   assert json.loads((base/'status.json').read_text())['status']=='completed-review-required','Incomplete suite'
   inventory=json.loads((base/'files.json').read_text())
   entries=inventory.items() if isinstance(inventory,dict) else ((x['path'],x['sha256']) for x in inventory)
   for relative,want in entries:
    path=(base/relative).resolve(); path.relative_to(base.resolve()); assert sha(path)==want,'Evidence hash mismatch: '+relative
  for c in plan['cases']:
   for engine,base,reader in [('matlab',a.matlab,matlab),('native',a.native,native)]:
    d=base/c['id']; assert json.loads((d/'status.json').read_text())['status']=='completed','Incomplete case'
    apps,m=reader(d); m.update(case=c['id'],seed=c['seed'],load=c['load'],engine=engine); result['cases'].append(m)
    (a.output/f'{engine}-{c["id"]}-applications.json').write_text(json.dumps(apps,indent=2,allow_nan=False)+'\n')
  result['status']='completed-review-required'
 except Exception as e: result.update(status='failed',failure=str(e)); raise
 finally:
  (a.output/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
  (a.output/'files.json').write_text(json.dumps({f.name:sha(f) for f in sorted(a.output.iterdir()) if f.is_file() and f.name!='files.json'},indent=2)+'\n')
if __name__=='__main__': main()
