#!/usr/bin/env python3
"""Independent raw-return audit. Does not modify simulation or reuse aggregate counters."""
from pathlib import Path
import csv,gzip,json,hashlib,collections,statistics,math
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
inputs={}
def path(rel):
 p=ROOT/rel
 inputs[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
 return p
def rows(rel):
 p=path(rel)
 return csv.DictReader(gzip.open(p,'rt') if str(p).endswith('.gz') else p.open())
def js(rel):return json.loads(path(rel).read_text())
def mean(x):return statistics.mean(x) if x else None
report={}
all_contrib=[]
for seed in [131,132]:
 base=f'terminal6000_return/data/s{seed}/attempt_001'
 states={}; sources={}; gen={}; rec={}; late=set(); recoveries=[]; appdrops=[]; status_errors=[]; events=collections.Counter(); init=[]; txfirst={}; drop_at={}; drop_before_delivery=set(); delivery_late_status=[]
 max_t=0
 for r in rows(base+'/raw/protocol_trace.csv'):
  t=float(r['TimeSeconds']); max_t=max(max_t,t); e=r['Event']; pid=r['PacketId']; node=int(r['NodeId']); events[e]+=1
  if e=='app_generate':
   if pid in states:status_errors.append(['duplicate_generation',pid,t])
   states[pid]='pending';sources[pid]=node;gen[pid]=t
  elif e=='app_drop':
   if states.get(pid)!='pending':status_errors.append(['drop_non_pending',pid,t])
   states[pid]='dropped';appdrops.append(pid);drop_at[pid]=t
  elif e=='relay_accept':
   if states.get(pid)=='dropped':
    recoveries.append({'id':pid,'source':sources[pid],'time_s':t,'drop_time_s':drop_at[pid]});states[pid]='pending'
  elif e=='app_receive':
   if pid in rec:status_errors.append(['duplicate_delivery',pid,t])
   if states.get(pid)=='dropped':late.add(pid);delivery_late_status.append(t-gen[pid])
   if pid in drop_at:drop_before_delivery.add(pid)
   states[pid]='delivered';rec[pid]=t
  if e in ('neighbor_active','discovery_finished'):init.append(r)
  if e=='tx_start':txfirst.setdefault(node,t)
 stats=js(base+'/raw/summary.json')['Statistics']
 counts=collections.Counter(states.values())
 assertions={
  'unique_generated_matches':len(states)==stats['Generated'],
  'unique_delivered_matches':len(rec)==stats['Received'],
  'provisional_dropped_matches':counts['dropped']==stats['Dropped'],
  'pending_matches':counts['pending']==stats['Pending'],
  'late_deliveries_match':len(late)==stats['LateDeliveries'],
  'late_custody_recoveries_match':len(recoveries)==stats['LateCustodyRecoveries'],
  'unique_accounting_identity':len(states)==len(rec)+counts['dropped']+counts['pending'],
  'no_invalid_status_transitions':not status_errors,
  'no_post_cutoff_protocol':max_t<6000,
  'no_core_trace_omissions':stats['OmittedTraceRecords']==stats['OmittedPhyTraceRecords']==0,
 }
 # Check app-table reconstruction and exact latency expression against all raw deliveries.
 ledger=list(rows(base+'/analysis/applications.csv'));ledger_bad=[]
 for r in ledger:
  pid=r['PacketId'];state=states[pid]
  if r['Outcome']!=state:ledger_bad.append([pid,'outcome',r['Outcome'],state])
  if state=='delivered' and abs(float(r['LatencySeconds'])-(rec[pid]-gen[pid]))>1e-8:ledger_bad.append([pid,'latency'])
 assertions['all_application_rows_match_raw']=not ledger_bad and len(ledger)==len(states)
 # Scenario equality except run seed/duration comments requires exact source geometry/flows.
 scen=list(rows(base+'/raw/scenario.csv')); native_scen=list(rows(f'recovered/native_origin/evidence/tranche-25-ns3-reference/s{seed}/scenario.csv'))
 meaningful=lambda rs:[r for r in rs if r['record'] in ('node','flow')]
 assertions['scenario_nodes_and_flows_identical']=meaningful(scen)==meaningful(native_scen)
 # Native complete route history: extract first nonself route / route to gateway; trace itself has no discovery_finished event.
 native_routes={};native_first_gateway={};native_tx={};native_route_times=[];native_first_route={};native_startup_snmp=[]
 for r in rows(f'recovered/native_origin/evidence/tranche-25-ns3-reference/s{seed}/ns3-trace.csv.gz'):
  e=r['event'];t=float(r['time_s']);n=int(r['node']) if r['node'] else -1
  if e=='route_change':
   dst=int(r['dst']);native_routes[(n,dst)]=r
   if dst!=n:native_first_route.setdefault(n,t)
   if dst==1 and n!=1:native_first_gateway.setdefault(n,t)
   if t<200:native_route_times.append(r)
  if e=='tx_start':native_tx.setdefault(n,t)
  if e=='statistic_sample' and 'discov' in r['statistic'].lower():native_startup_snmp.append(r)
 routes=list(rows(base+'/raw/routes.csv'))
 native_nonself={f'{n}:{dst}':{'next_hop':int(r['next_hop']),'cost':float(r['route_cost'])} for (n,dst),r in native_routes.items() if n!=dst}
 matlab_nonself={f"{r['NodeId']}:{r['DestinationId']}":{'next_hop':int(r['NextHop']),'cost':float(r['Cost'])} for r in routes}
 # Natural random source: sample signatures are unpaired; check exact first MAC request contexts/values later against native first TX.
 rng=[]; rngcount=collections.Counter(); first_rng={}
 normal=[]
 for l in path(base+'/random_requests.jsonl').open():
  r=json.loads(l);purpose=r['purpose'];rngcount[purpose]+=1;first_rng.setdefault(f"{r['node']}:{purpose}",r)
  if purpose=='sync_threshold':normal.append(r['actual']['standard_normal'])
  if purpose=='mac_slot' and not (r['actual']['low']<=r['value']<=r['actual']['high']):rng.append(['range',r])
 assertions['natural_mac_draws_in_range']=not rng
 late_by_source=collections.Counter(sources[x] for x in late)
 anydrop_by_source=collections.Counter(sources[x] for x in drop_before_delivery)
 table=[]
 for src in (2,3,4,5,7,8):
  ids=[p for p in states if sources[p]==src]; ds=[p for p in ids if p in rec]
  lat=[rec[p]-gen[p] for p in ds]
  early_lat=[rec[p]-gen[p] for p in ds if p not in drop_before_delivery]
  late_lat=[rec[p]-gen[p] for p in ds if p in drop_before_delivery]
  table.append({'source':src,'admitted':len(ids),'delivered':len(ds),'unresolved':len(ids)-len(ds),'mean_s':mean(lat),'delivery_from_provisional_drop':late_by_source[src],'delivery_after_any_provisional_drop':anydrop_by_source[src],'mean_delivery_after_any_drop_s':mean(late_lat),'mean_no_prior_drop_s':mean(early_lat),'latency_sum_s':sum(lat),'latency_sum_after_any_drop_s':sum(late_lat)})
 result={'pass':all(assertions.values()),'checks':assertions,'raw_events':events,'maximum_trace_time_s':max_t,'states':counts,'app_drop_events':len(appdrops),'distinct_dropped_apps':len(set(appdrops)),'late_deliveries':len(late),'late_custody_recoveries':len(recoveries),'delivered_after_any_prior_drop':len(drop_before_delivery),'table':table,'status_errors':status_errors,'ledger_errors':ledger_bad,'matlab_startup_events':init,'matlab_first_tx':txfirst,'matlab_final_routes':matlab_nonself,'native_final_routes':native_nonself,'native_first_tx':native_tx,'native_first_nonself_route':native_first_route,'native_first_gateway_route':native_first_gateway,'native_route_events_before_200s':native_route_times,'native_discovery_statistics':native_startup_snmp,'random_counts':rngcount,'first_random_requests':first_rng,'normal_draw_mean':mean(normal),'normal_draw_sample_variance':statistics.variance(normal),'cutoff':js(base+'/cutoff_semantics.json')}
 report[str(seed)]=result
 with (OUT/f's{seed}_late_recoveries.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=['id','source','time_s','drop_time_s']);w.writeheader();w.writerows(recoveries)
 print(seed, 'PASS',result['pass'],'checks',assertions,'late',len(late),'recoveries',len(recoveries))
# Source weighting: hold native delivered source/seed weights fixed. Not a paired identity claim.
comparisons=[]
for seed in [131,132]:
 for r in rows(f'terminal6000_return/data/s{seed}/attempt_001/analysis/source_target_comparison.csv'):
  n=int(r['native_delivered']);m=int(r['matlab_delivered']);src=int(r['source'])
  mu=float(r['matlab_mean_delivered_latency_s']);nu=float(r['native_mean_delivered_latency_s'])
  if n:comparisons.append({'seed':seed,'source':src,'n':n,'m':m,'matlab_mean_s':mu,'native_mean_s':nu})
N=sum(x['n'] for x in comparisons)
for r in comparisons:r['native_weighted_mean_gap_contribution_s']=r['n']/N*(r['matlab_mean_s']-r['native_mean_s'])
report['native_weighted_contributions']=comparisons
report['pass']=all(report[str(s)]['pass'] for s in [131,132]);report['input_sha256']=inputs
(OUT/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
print('weightedcontributions',[(r['seed'],r['source'],round(r['native_weighted_mean_gap_contribution_s'],3)) for r in comparisons])
