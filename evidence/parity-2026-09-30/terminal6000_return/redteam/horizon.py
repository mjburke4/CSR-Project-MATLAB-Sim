from pathlib import Path
import csv,json,hashlib
root=Path(__file__).resolve().parents[2];out=[];inputs={}
for s in [131,132]:
 for model in ['native','matlab']:
  if model=='native':p=root/f'recovered/issued/csr6000/reference/s{s}/applications.csv'
  else:p=root/f'terminal6000_return/data/s{s}/attempt_001/analysis/applications.csv'
  inputs[str(p.relative_to(root))]=hashlib.sha256(p.read_bytes()).hexdigest()
  rows=list(csv.DictReader(p.open()))
  for source in [2,7,8]:
   if model=='native':times=[int(r['first_delivery_time_ns'])/1e9 for r in rows if int(r['source'])==source and r['status']=='delivered']
   else:times=[float(r['ReceivedSeconds']) for r in rows if int(r['SourceId'])==source and r['Outcome']=='delivered']
   out.append(dict(seed=s,model=model,source=source,first_delivery_s=min(times) if times else None))
(Path(__file__).parent/'horizon.json').write_text(json.dumps(dict(first_deliveries=out,input_sha256=inputs),indent=2)+'\n')
