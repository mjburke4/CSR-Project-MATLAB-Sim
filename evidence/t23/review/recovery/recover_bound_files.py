from pathlib import Path
import json,hashlib,zipfile,sys
base=Path('/workspace/scratch/ab77b42f47ca');root=base/'t23-return-review/issued-overlay'
c=json.loads((root/'evidence/tranche-23-candidate.json').read_text())
rows={x['path']:x for x in c['SourceFiles']+c['ReferenceFileInventory']}
rows['evidence/tranche-23-candidate.json']={'path':'evidence/tranche-23-candidate.json','sha256':'b40afd3755ceb47576ea2c9854b4af15a14cebcf87024331e67bf53e069f0818'}
for p in sys.argv[1:]:
 count=0
 with zipfile.ZipFile(p) as z:
  for n in rows:
   if (root/n).is_file():continue
   matches=[x for x in z.namelist() if x==n or x.endswith('/'+n)]
   for src in matches:
    data=z.read(src)
    if hashlib.sha256(data).hexdigest()!=rows[n]['sha256']:continue
    assert 'bytes' not in rows[n] or len(data)==rows[n]['bytes']
    dest=root/n;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);count+=1;break
 print(Path(p).name,'bound_files_recovered',count)
missing=[x for n,x in rows.items() if not (root/n).is_file()]
(base/'t23-return-review/missing-bound-files.json').write_text(json.dumps(missing,indent=2))
print('remaining_references',len(missing),'bytes',sum(x.get('bytes',0) for x in missing))
