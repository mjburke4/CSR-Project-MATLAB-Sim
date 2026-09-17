from pathlib import Path
from collections import defaultdict
import csv,gzip,io,zipfile,json,hashlib
root=Path(__file__).resolve().parents[2]
source=root/'csr18'
out=Path(__file__).resolve().parent
counts=defaultdict(int)
with zipfile.ZipFile(source/'evidence/t17/owner.zip') as z:
 with z.open('campus/c/analysis/applications.csv') as f:
  for r in csv.DictReader(io.TextIOWrapper(f,encoding='utf-8-sig')):
   src=int(r['SourceId']);t=float(r['GeneratedSeconds']);counts['matlab',src,'admitted',min(int(t//300),19)]+=1
   if r['Outcome']=='delivered':
    t=float(r['ReceivedSeconds']);counts['matlab',src,'delivered',min(int(t//300),19)]+=1
native=source/'evidence/tranche-7-ns3-reference/campus_multihop_6000/ns3-trace.csv.gz'
with gzip.open(native,'rt',encoding='utf-8-sig') as f:
 for r in csv.DictReader(f):
  if r['event'] not in ('app_send','nwk_delivery'):continue
  src=int(r['src']);t=float(r['time_s']);kind='admitted' if r['event']=='app_send' else 'delivered';counts['ns3',src,kind,min(int(t//300),19)]+=1
rows=[]
for src in [2,3,4,5,7,8]:
 cumulative=defaultdict(int)
 for b in range(20):
  r={'source':src,'start_s':b*300,'end_s':(b+1)*300}
  for kind in ['admitted','delivered']:
   for sim in ['matlab','ns3']:
    v=counts[sim,src,kind,b];cumulative[sim,kind]+=v;r[f'{sim}_{kind}']=v;r[f'{sim}_cumulative_{kind}']=cumulative[sim,kind]
   r[f'{kind}_difference']=r[f'matlab_{kind}']-r[f'ns3_{kind}'];r[f'cumulative_{kind}_difference']=cumulative['matlab',kind]-cumulative['ns3',kind]
  rows.append(r)
with (out/'t17_flow_timeline_300s.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps([r for r in rows if r['source']==5],indent=2))
meta={'schema':'csr-t18-existing-t17-timeline-v1','interval_convention':'[start,end), final includes endpoint 6000','inputs':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [source/'evidence/t17/owner.zip',native]},'scope':'Existing accepted full-campus traces only. Equal seed labels do not align cross-simulator random streams. Binned counts do not establish causal scheduler or retry-policy differences.'}
(out/'provenance.json').write_text(json.dumps(meta,indent=2)+'\n')
