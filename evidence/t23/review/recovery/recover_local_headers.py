"""Recover only independently hash-bound complete members from a truncated old ZIP."""
from pathlib import Path
import hashlib,json,struct,zlib
base=Path('/workspace/scratch/ab77b42f47ca');root=base/'t23-return-review/issued-overlay'
p=base/'t23-review-recovery/NS3 to MATLAB Network Simulation/csr14.zip'
c=json.loads((root/'evidence/tranche-23-candidate.json').read_text())
expected={x['path']:x for x in c['SourceFiles']+c['ReferenceFileInventory']}
recovered=[];complete=0;position=0;reason='end_of_file'
with p.open('rb') as f:
 while True:
  h=f.read(30)
  if len(h)<30:reason='incomplete_header';break
  sig,ver,flags,method,mt,md,crc,cs,us,nl,el=struct.unpack('<4s5H3I2H',h)
  if sig!=b'PK\x03\x04':reason='non_local_header';break
  name=f.read(nl).decode('utf-8' if flags&0x800 else 'cp437');f.read(el)
  if flags&0x9:reason='unsupported_flags';break
  if f.tell()+cs>p.stat().st_size:reason='incomplete_member:'+name;break
  needed=expected.get(name)
  if needed and not (root/name).is_file():
   compressed=f.read(cs)
   data=zlib.decompress(compressed,-15) if method==8 else compressed if method==0 else None
   assert data is not None and len(data)==us and zlib.crc32(data)&0xffffffff==crc,name
   if hashlib.sha256(data).hexdigest()==needed['sha256']:
    assert not Path(name).is_absolute() and '..' not in Path(name).parts
    dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    recovered.append({'path':name,'sha256':needed['sha256'],'offset':position,'bytes':len(data)})
  else:f.seek(cs,1)
  complete+=1;position=f.tell()
receipt={'schema':'csr-t23-hash-bound-historical-recovery-v1','archive':str(p),'archive_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'complete_local_members':complete,'stop_reason':reason,'recovered':recovered,'note':'Old archive has no ZIP directory; only complete members whose CRC and independently issued T23 SHA256 match are used. Owner T23 ZIP is separate and intact.'}
(base/'t23-return-review/historical-recovery.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'complete_local_members':complete,'stop_reason':reason,'recovered':len(recovered)}))
missing=[x for n,x in expected.items() if not (root/n).is_file()]
(base/'t23-return-review/missing-bound-files.json').write_text(json.dumps(missing,indent=2))
print('missing_bound_files',len(missing))
