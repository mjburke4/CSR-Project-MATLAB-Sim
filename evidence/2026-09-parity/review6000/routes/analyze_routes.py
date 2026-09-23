from pathlib import Path
import gzip,csv,collections,json,hashlib,zipfile,io,argparse
DEFAULT_ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description='Read-only native/MATLAB seed-131 startup route audit; no simulations.')
parser.add_argument('--root',type=Path,default=DEFAULT_ROOT,help='Root containing original_extracted (default: script grandparent)')
parser.add_argument('--native-trace',type=Path,help='Native ns3-trace.csv.gz override')
parser.add_argument('--matlab-archive',type=Path,help='MATLAB owner.zip override')
parser.add_argument('--output',type=Path,help='Derived-output directory override')
args=parser.parse_args()
ROOT=args.root.resolve(); OUT=(args.output or ROOT/'review6000/routes').resolve(); OUT.mkdir(parents=True,exist_ok=True)
native=(args.native_trace or ROOT/'original_extracted/t25up/evidence/tranche-25-ns3-reference/s131/ns3-trace.csv.gz').resolve()
owner=(args.matlab_archive or ROOT/'original_extracted/t25review/owner.zip').resolve()
counts=collections.Counter(); routes=[]; links=[]; boundary=[]; last_stats={};first_rx={};tx_counts=collections.Counter();rx_counts=collections.Counter();txfirst={};txlast={}
with gzip.open(native,'rt') as f:
 reader=csv.DictReader(f);fields=reader.fieldnames
 for r in reader:
  e=r['event'];n=r['node'];p=r['peer'];t=float(r['time_s']);kind=r['packet_type'];reason=r['reason'];
  if e=='route_change':routes.append(r)
  if e=='scenario_link':links.append(r)
  if e=='tx_start':
   k=(n,kind,p);tx_counts[k]+=1;txfirst.setdefault(k,r);txlast[k]=r
  if e in ('rx_accept','rx_drop'):
   k=(n,p,e,kind,reason);rx_counts[k]+=1;first_rx.setdefault(k,r)
  if e=='statistic_sample':last_stats[(n,r['statistic'])]=r
  if t<300 and (e in ('tx_start','rx_accept','rx_drop','route_change')):
   if ((n=='2' and p in ('4','')) or (n=='4' and p in ('2',''))):boundary.append(r)
for name,rows in [('native_all_routes',routes),('native_links',links),('native_startup_boundary2_4',boundary)]:
 with (OUT/(name+'.csv')).open('w') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
(OUT/'native_tx_counts.json').write_text(json.dumps([{'node':k[0],'kind':k[1],'peer':k[2],'count':v,'first_s':txfirst[k]['time_s'],'last_s':txlast[k]['time_s']} for k,v in tx_counts.items()],indent=2))
(OUT/'native_rx_counts.json').write_text(json.dumps([{'node':k[0],'peer':k[1],'event':k[2],'kind':k[3],'reason':k[4],'count':v,'first_s':first_rx[k]['time_s']} for k,v in rx_counts.items()],indent=2))
(OUT/'native_final_stats.json').write_text(json.dumps([{'node':k[0],'statistic':k[1],'value':v['value']} for k,v in last_stats.items()],indent=2))
z=zipfile.ZipFile(owner)
mat_events=collections.Counter();mat_selected=[];mat_start=[]
with z.open('s131/raw/protocol_trace.csv') as bf:
 reader=csv.DictReader(io.TextIOWrapper(bf));mat_fields=reader.fieldnames
 for r in reader:
  e=r['Event'];mat_events[e]+=1
  if any(x in e.lower() for x in ['route','neighbor','topology','discovery','security']):mat_selected.append(r)
  if float(r['TimeSeconds'])<300 and (r['NodeId'] in ['2','4']):mat_start.append(r)
for name,rows in [('matlab_route_related',mat_selected),('matlab_startup_nodes2_4',mat_start)]:
 with (OUT/(name+'.csv')).open('w') as f:
  w=csv.DictWriter(f,fieldnames=mat_fields);w.writeheader();w.writerows(rows)
(OUT/'matlab_events.json').write_text(json.dumps(mat_events,indent=2))
provenance={'inputs':{str(p):hashlib.file_digest(p.open('rb'),'sha256').hexdigest() for p in [native,owner]},'matlab_member':{'name':'s131/raw/protocol_trace.csv','sha256':hashlib.sha256(z.read('s131/raw/protocol_trace.csv')).hexdigest()},'native_counts':{'route_changes':len(routes),'startup_boundary_events':len(boundary)},'matlab_counts':{'route_related_events':len(mat_selected),'startup_nodes2_4_events':len(mat_start)}}
(OUT/'provenance.json').write_text(json.dumps(provenance,indent=2))
print(json.dumps(provenance,indent=2));print(mat_events)
