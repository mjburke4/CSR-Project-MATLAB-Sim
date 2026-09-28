from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parents[1]/'kit/autocase'
files=[]
for p in sorted(root.rglob('*')):
 if p.is_file() and p.name!='FILES.json' and not any(x.startswith('out_auto_') for x in p.relative_to(root).parts):
  files.append({'path':p.relative_to(root).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
(root/'FILES.json').write_text(json.dumps({'schema':'csr-autonomous-issued-kit-v1','scope':'seed132 autonomous0to330 natural-prefix and common-input diagnostic','matlab_executed':False,'numerical_parity_established':False,'target_percent':15,'files':files},indent=2)+'\n')
print(json.dumps({'files':len(files),'bytes':sum(x['bytes'] for x in files),'manifest':str(root/'FILES.json')}))
