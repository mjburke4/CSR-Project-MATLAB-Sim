#!/usr/bin/env python3
"""Calibration runs of one fixed campus traffic schedule across three seeds."""
from pathlib import Path
import argparse,csv,hashlib,json,subprocess,time,collections,statistics
ROOT=Path(__file__).resolve().parent; WORK=ROOT.parent
NODES=[2,3,4,5,7,8]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(cmd,dest):
 dest.mkdir(parents=True,exist_ok=False);start=time.monotonic()
 with (dest/'run.log').open('wb') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
 record=dict(argv=cmd,exit_code=r.returncode,wall_seconds=time.monotonic()-start)
 (dest/'run-status.json').write_text(json.dumps(record,indent=2)+'\n'); assert r.returncode==0,record
 return record
def analyze(dest,trafficstop,simstop):
 apps={};delivered=set();attempts=[];queues=collections.defaultdict(lambda:dict(peak=0,last=0));final_events={}
 with (dest/'ns3-trace.csv').open() as f:
  for r in csv.DictReader(f):
   ev=r['event'];t=float(r['time_s']);key=(r['src'],r['dst'],r['sequence'])
   if ev=='app_admission':
    assert t<trafficstop
    attempts.append((int(r['src']),t))
   if ev=='app_send':assert t<trafficstop;apps[key]=t
   if ev=='nwk_delivery':delivered.add(key)
   if ev=='statistic_sample' and r['statistic']=='NWK.Network Queue Size (packets)':
    q=queues[r['node']];q['last']=int(float(r['value']));q['peak']=max(q['peak'],q['last'])
   final_events[r['node']]=(t,ev)
 with (dest/'app-admission-diagnostics.csv').open() as f:admissions=list(csv.DictReader(f))
 sources={}
 for s in NODES:
  subset={k for k in apps if k[0]==str(s)};done=subset&delivered;sources[str(s)]=dict(admitted=len(subset),delivered=len(done),unresolved=len(subset-done))
 return dict(apps=len(apps),delivered=len(delivered),unresolved=len(set(apps)-delivered),queues=queues,sources=sources,admissions=admissions,latest_app_send=max(apps.values()),latest_attempt=max(t for _,t in attempts) if attempts else None,attempt_schedule=attempts,final_events=final_events)
def main():
 p=argparse.ArgumentParser();p.add_argument('--interval',type=int,default=30);p.add_argument('--count',type=int,default=20);p.add_argument('--drain',type=int,default=600);p.add_argument('--name',required=True);p.add_argument('--seeds',type=int,nargs='+',default=[128,129,132]);a=p.parse_args()
 out=ROOT/a.name;out.mkdir(exist_ok=False)
 cutoff=300+a.interval*a.count;end=cutoff+a.drain
 parent=WORK/'latency-tests/load/scenarios/parent.csv'
 with parent.open(newline='') as f:r=csv.DictReader(f);fields=r.fieldnames;original=list(r)
 cases=[]
 for seed in a.seeds:
  key=f'drain{seed}';rows=[dict(r) for r in original];starts={str(s):300+i*a.interval/6 for i,s in enumerate(NODES)}
  for r in rows:
   if r['record']=='run':r.update(duration_s=str(end),seed=str(seed),scenario='campus-light-'+key)
   if r['record']=='node':r['interarrival_s']=str(a.interval);r['start_s']=str(starts.get(r['node_id'],300))
   if r['record']=='flow':r['flow_interval_s']=str(a.interval);r['flow_start_s']=str(starts[r['flow_src']])
  scenario=out/(key+'.csv')
  with scenario.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
  dest=out/key
  cmd=[str(ROOT/'drain-scenario-runner'),f'--scenario={scenario}',f'--trace={dest/"ns3-trace.csv"}',f'--appDiagnostics={dest/"app-admission-diagnostics.csv"}',f'--stop={end}',f'--trafficStop={cutoff}','--flowLimit=0','--dutyCycling=1','--opnetAlignedDutyCycle=1','--gatewayDiscovery=1','--opnetAppGating=1','--aggregateTraceOnly=0','--admissionTrace=1','--quietModelLogs=1','--stochasticSyncThreshold=1']
  execution=run(cmd,dest);review=analyze(dest,cutoff,end)
  case=dict(id=key,seed=seed,scenario=scenario.name,scenario_sha256=sha(scenario),interval_s=a.interval,traffic_start_s=300,traffic_stop_s=cutoff,duration_s=end,drain_s=a.drain,flow_limit=0,attempts_per_source=a.count,source_starts=starts,native=review,execution=execution)
  (dest/'review.json').write_text(json.dumps(case,indent=2)+'\n');cases.append(case)
  print(key,json.dumps(review),flush=True)
 (out/'calibration.json').write_text(json.dumps(dict(parent_sha256=sha(parent),cases=cases),indent=2)+'\n')
 (out/'files.json').write_text(json.dumps({str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='files.json'},indent=2)+'\n')
if __name__=='__main__':main()
