#!/usr/bin/env python3
"""Bind unchanged core, seal the batch, and create the short-path MATLAB ZIP."""
import argparse,hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def entry(p):return {'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 base=json.loads((ROOT/'baseline_binding.json').read_text())
 for r in base['matlab_baseline_files']:
  assert sha(ROOT/'core'/r['path'])==r['sha256'],r['path']
 runtime={ROOT/'run_mac_batch.m',ROOT/'baseline_binding.json'}
 for folder in ['core','matlab','inputs','reference']:
  runtime.update(x for x in (ROOT/folder).rglob('*') if x.is_file() and x.suffix in {'.m','.json','.csv'})
 for folder in ['diagnostics/rules','diagnostics/node4','diagnostics/grouped']:
  runtime.update(x for x in (ROOT/folder).rglob('*') if x.is_file() and x.suffix in {'.m','.json','.csv'})
 write(ROOT/'RUN_FILES.json',{'schema':'csr.mac-batch-run.v1','files':[entry(x) for x in sorted(runtime)]})
 excluded={'PACKAGE_FILES.json'}
 suffixes={'.py','.m','.csv','.json','.md','.h','.cc','.patch','.log','.gz','.txt'}
 included=[x for x in sorted(ROOT.rglob('*')) if x.is_file() and x.suffix in suffixes and x.name not in excluded and '__pycache__' not in x.parts and not any(y.startswith('out_mac_') for y in x.parts)]
 write(ROOT/'PACKAGE_FILES.json',{'schema':'csr.mac-batch-package.v1','files':[entry(x) for x in included]})
 included.append(ROOT/'PACKAGE_FILES.json');a.output.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(a.output,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for x in included:z.write(x,'macbatch/'+x.relative_to(ROOT).as_posix())
 with zipfile.ZipFile(a.output) as z:assert z.testzip() is None
 print(json.dumps({'file':str(a.output.resolve()),'files':len(included),'runtime_bound_files':len(runtime),'accepted_core_files':len(base['matlab_baseline_files']),'bytes':a.output.stat().st_size,'sha256':sha(a.output),'longest_relative_path':max(len('macbatch/'+x.relative_to(ROOT).as_posix()) for x in included)},indent=2))
if __name__=='__main__':main()
