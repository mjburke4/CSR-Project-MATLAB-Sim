import hashlib,tarfile,json,pathlib

def obj(kind,data):return hashlib.sha1(kind.encode()+b' '+str(len(data)).encode()+b'\0'+data).digest()
def verify(path,expected):
 root={}
 with tarfile.open(path) as t:
  members=t.getmembers();prefix=members[0].name.split('/')[0]+'/'
  for m in members:
   if not (m.isfile() or m.issym()):continue
   name=m.name.removeprefix(prefix);parts=name.split('/');d=root
   for part in parts[:-1]:d=d.setdefault(part,{})
   b=m.linkname.encode() if m.issym() else t.extractfile(m).read();mode='120000' if m.issym() else '100755' if m.mode&0o111 else '100644'
   d[parts[-1]]=(mode,obj('blob',b))
 def tree(d):
  rows=[]
  for name,v in sorted(d.items(),key=lambda x:(x[0]+('/' if isinstance(x[1],dict) else '')).encode()):
   mode,sha=('40000',tree(v)) if isinstance(v,dict) else v
   rows.append(mode.encode()+b' '+name.encode()+b'\0'+sha)
  return obj('tree',b''.join(rows))
 actual=tree(root).hex();assert actual==expected,(actual,expected)
 p=pathlib.Path(path);return {'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'git_tree_sha':actual,'git_tree_verified':True}
if __name__=='__main__':
 out={'source':verify('t22-work/native/source.tar.gz','b611b233fb369569b98f0914ece24d029ccc2f42'),'engine':verify('t22-work/native-engine.tar.gz','f30343185fb057e3a9cdd54f496cca0cef49ae23')}
 pathlib.Path('t22-work/native/archive-verification.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
