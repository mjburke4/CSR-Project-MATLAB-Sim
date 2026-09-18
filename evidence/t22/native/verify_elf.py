from pathlib import Path
import hashlib,json,subprocess
root=Path('t22-work/native/ns-3-dev-git-6b5cd24ea80713ce16d88575869aedd6f432bdae');out={}
for p in sorted((root/'build/lib').glob('libns3-dev-*-debug.so')):
 b=p.read_bytes();assert b[:4]==b'\x7fELF' and len(b)>100000,p
 headers=subprocess.check_output(['readelf','-h',str(p)],text=True);assert 'DYN (Shared object file)' in headers,p
 syms=subprocess.check_output(['nm','-D','--defined-only',str(p)],text=True);assert len(syms.splitlines())>10,p
 out[p.name]={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'elf_shared_object':True,'defined_dynamic_symbols':len(syms.splitlines())}
zeros=[str(p) for p in (root/'cmake-cache').rglob('*.o') if p.stat().st_size==0];assert not zeros,zeros
Path('t22-work/native/elf-verification.json').write_text(json.dumps({'passed':True,'zero_object_files':zeros,'libraries':out},indent=2)+'\n');print({p:x['bytes'] for p,x in out.items()})
