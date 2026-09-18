#!/usr/bin/env python3
"""Compile and execute T22 actual native HOP contracts on a pinned engine build.

No MATLAB execution or RF inference. A copied header adds only one friend
access declaration; all CSR behavior methods and engine sources are unchanged.
"""
from __future__ import annotations
import argparse,csv,difflib,hashlib,json,shutil,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
PIN='486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b'
ENGINE='6b5cd24ea80713ce16d88575869aedd6f432bdae'
MODULES=('csr','spectrum','buildings','propagation','mobility','antenna','network','stats','core')
HEADER_SHA='0a826930bab43db429a2a3bd905672b370774274f7de826abf180f002156f10b'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 with Path(p).open(newline='') as f:return list(csv.DictReader(f))
def writejson(p,d):Path(p).write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
def execute(cmd,log):
 start=time.monotonic()
 with log.open('wb') as f:p=subprocess.run(list(map(str,cmd)),stdout=f,stderr=subprocess.STDOUT)
 rec={'argv':list(map(str,cmd)),'exit_code':p.returncode,'wall_seconds':time.monotonic()-start,'log':log.name,'log_sha256':sha(log)}
 if p.returncode:raise RuntimeError(f'Command failed ({p.returncode}): {log}')
 return rec

def run(source,build,work,out,root,compiler):
 contract=json.loads((root/'scenarios/t22/contract.json').read_text());actions=read(root/'scenarios/t22/actions.csv');cases=read(root/'scenarios/t22/cases.csv')
 for name,d in contract['input_hashes'].items():
  if sha(root/'scenarios/t22'/name)!=d:raise ValueError('Contract input hash mismatch')
 if b'\"' in (root/'scenarios/t22/actions.csv').read_bytes():raise ValueError('Native frozen CSV does not support quoted fields')
 for c in cases:
  if [float(c[n]) for n in ('resend_seconds','max_resends','dack_seconds','tic_seconds','pending_threshold','flow_threshold_max')]!=[2.,2.,20.,1/36e6,16.,16.]:raise ValueError('Native defaults must match contract')
 if sha(source/'model/csr-hop-layer.h')!=HEADER_SHA:raise ValueError('Unexpected HOP source')
 baseline=json.loads((root/'evidence/tranche-14-native-build.json').read_text())
 model={str(p.relative_to(source)):sha(p) for p in sorted((source/'model').iterdir()) if p.is_file()}
 expected={r['path']:r['sha256'] for r in baseline['module_files']}
 for name,d in expected.items():
  if model.get(name)!=d:raise ValueError('Pinned model mismatch: '+name)
 for p in (work,out):p.mkdir(parents=True,exist_ok=True)
 provenance=json.loads((out/'build.json').read_text())
 if provenance['status']!='passed' or provenance['source_pin']!=PIN or provenance['engine_pin']!=ENGINE or not provenance['linked_libraries_verified_elf']:raise ValueError('Unverified native build provenance')
 for name in MODULES:
  p=build/'lib'/f'libns3-dev-{name}-debug.so'
  if sha(p)!=provenance['libraries'][p.name] or p.read_bytes()[:4]!=b'\x7fELF':raise ValueError('Native library changed or is not ELF')
 tracked_path=out/provenance['tracked_source_verification']
 if sha(tracked_path)!=provenance['tracked_source_verification_sha256']:raise ValueError('Tracked source verification changed')
 tracked=json.loads(tracked_path.read_text())
 for kind,folder in [('source',source),('engine',build.parent)]:
  for name,d in tracked[kind]['file_sha256'].items():
   p=folder/name
   actual=hashlib.sha256(str(p.readlink()).encode()).hexdigest() if p.is_symlink() else sha(p)
   if actual!=d:raise ValueError('Tracked build source changed: '+name)
 overlay=work/'overlay/ns3';overlay.mkdir(parents=True,exist_ok=True)
 for p in (source/'model').iterdir():
  if p.is_file():
   q=overlay/p.name
   if q.exists() or q.is_symlink():q.unlink()
   q.symlink_to(p.resolve())
 target=overlay/'csr-hop-layer.h';target.unlink();before=(source/'model/csr-hop-layer.h').read_text();needle='class CsrHopLayer : public Object\n{';replacement=needle+'\n  friend struct CsrTranche22Access; // T22 fixture-only observation and protected-feedback adapter.'
 if before.count(needle)!=1:raise ValueError('Unexpected friend access anchor')
 after=before.replace(needle,replacement,1);target.write_text(after)
 (out/'seams.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='pinned/csr-hop-layer.h',tofile='overlay/csr-hop-layer.h')))
 library=build/'lib';binary=work/'tranche22-window';cmd=[compiler,'-std=c++23','-g','-DNS3_ASSERT_ENABLE','-DNS3_BUILD_PROFILE_DEBUG','-DNS3_LOG_ENABLE','-DSTACKTRACE_LIBRARY_IS_LINKED=1','-D__LINUX__','-I'+str(overlay.parent),'-I'+str(build/'include'),str(root/'scripts/ns3/tranche22_window.cc'),'-L'+str(library),'-Wl,-rpath,'+str(library),'-Wl,--no-as-needed',*[f'-lns3-dev-{n}-debug' for n in MODULES],'-lstdc++exp','-o',str(binary)]
 commands=[execute(cmd,out/'compile.log'),execute([binary,root/'scenarios/t22/actions.csv',out/'raw'],out/'run.log')]
 checkpoints=[];counts={};rawbindings={}
 for c in cases:
  name=c['case_id'];folder=out/'raw'/name;states={int(r['step']):r for r in read(folder/'states.csv')};tally={'ack':0,'dack':0,'no_ack':0};retired_retry=0;expired=0;finished=set();seen=[]
  for event in read(folder/'trace.csv'):
   if event['event']=='hop_completion':
    reason=event['reason'];ident=(event['peer'],event['sequence'])
    if reason not in tally or ident in finished:raise ValueError('Duplicate/unknown native completion')
    finished.add(ident);tally[reason]+=1;detail=dict(x.split('=',1) for x in event['detail'].split(';') if '=' in x);retired_retry+=int(detail['resend_count'])
   elif event['event']=='hop_capacity_release':
    if event['reason']!='dack_expiry':raise ValueError('Unknown capacity release')
    expired+=1
   elif event['event']=='t22_checkpoint':
    step=int(event['sequence']);r=states[step];seen.append(step)
    x={k:r[k] for k in contract['state_columns'] if k in r};x.update(ack_total=str(tally['ack']),dack_total=str(tally['dack']),fail_total=str(tally['no_ack']),retry_total=str(retired_retry+int(r['live_retry_sum'])),dack_expired_total=str(expired))
    if int(x['nsdp_release_total'])!=sum(tally.values()) or tally['dack']-expired!=int(x['dack_holds']):raise ValueError('Native completion/capacity conservation failed')
    checkpoints.append(x)
  if seen!=list(states):raise ValueError('Checkpoint marker mismatch')
  counts[name]={'checkpoints':len(states),'ack':tally['ack'],'dack':tally['dack'],'failed':tally['no_ack'],'dack_expired':expired}
 if len(checkpoints)!=len(actions):raise ValueError('Action count mismatch')
 for r,a in zip(checkpoints,actions):
  for k in ('case_id','step','action','packet','peer'):
   if r[k]!=a[k]:raise ValueError('Action identity mismatch')
  if abs(float(r['time_s'])-float(a['time_s']))>0.51e-9:raise ValueError('Action clock mismatch')
 with (out/'checkpoints.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=contract['state_columns']);w.writeheader();w.writerows(checkpoints)
 milestones=contract.get('milestones',[])
 # Sparse independently specified rule checks augment the complete MATLAB comparison.
 failures=[];lookup={(r['case_id'],int(r['step'])):r for r in checkpoints}
 for m in milestones:
  row=lookup[(m['case_id'],int(m['step']))]
  for field,value in m['equals'].items():
   if int(row[field])!=value:failures.append({'case_id':m['case_id'],'step':m['step'],'field':field,'expected':value,'actual':int(row[field])})
 if failures:writejson(out/'milestone-failures.json',failures);raise ValueError('Native sparse milestones failed')
 if model!={str(p.relative_to(source)):sha(p) for p in sorted((source/'model').iterdir()) if p.is_file()}:raise ValueError('Source mutated')
 summary={'schema':'csr-tranche22-native-reference-v1','status':'passed','created_utc':datetime.now(timezone.utc).isoformat(),'source_pin':PIN,'engine_pin':ENGINE,'native_executed':True,'matlab_executed':False,'production_source_unchanged':True,'engine_source_unchanged':True,'case_count':len(cases),'checkpoint_count':len(checkpoints),'milestone_count':len(milestones),'cases':counts,'model_sources':model,'libraries':{n:sha(library/f'libns3-dev-{n}-debug.so') for n in MODULES},'input_bindings':{str(p.relative_to(root)):sha(p) for p in sorted((root/'scenarios/t22').iterdir()) if p.is_file()},'fixture_sources':{str(p.relative_to(root)):sha(p) for p in (root/'scripts/ns3/tranche22_window.cc',Path(__file__).resolve())},'commands':commands,'build_manifest':'build.json','build_manifest_sha256':sha(out/'build.json'),'binary_sha256':sha(binary),'overlay_header_sha256':sha(target),'seams_sha256':sha(out/'seams.patch'),'time_resolution_seconds':1e-9,'native_tic_seconds':28e-9,'scope':'Controlled HOP callbacks with production Pairwise16 feedback; no actual radio transmissions, PHY test, campus rerun, or numerical-parity claim. Existing queued-retry timestamp difference is not changed. MapScheduler observation subclass drains all existing callbacks through each input time.'}
 writejson(out/'summary.json',summary)
 writejson(out/'manifest.json',{'schema':'csr-tranche22-native-files-v1','files':{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json'}})
 return summary

def main():
 a=argparse.ArgumentParser(description=__doc__)
 for n in ('source','build','work','output'):a.add_argument('--'+n,type=Path,required=True)
 a.add_argument('--compiler',default='/usr/bin/g++');x=a.parse_args();root=Path(__file__).resolve().parents[1]
 result=run(x.source.resolve(),x.build.resolve(),x.work.resolve(),x.output.resolve(),root,x.compiler);print(json.dumps({k:result[k] for k in ('status','case_count','checkpoint_count','milestone_count')}))
if __name__=='__main__':main()
