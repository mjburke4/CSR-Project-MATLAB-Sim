#!/usr/bin/env python3
"""Compile T23 receiver fixture against reverified, retained accepted T22 libraries.

Production CSR/engine files are unchanged. The native fixture uses real NWK
ownership and HOP feedback, with explicitly controlled post-security ingress,
MAC transmit notices and downstream feedback. No RF or MATLAB execution claim.
"""
from __future__ import annotations
import argparse,csv,difflib,hashlib,json,shutil,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
PIN='486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b'
ENGINE='6b5cd24ea80713ce16d88575869aedd6f432bdae'
MODULES=('csr','spectrum','buildings','propagation','mobility','antenna','network','stats','core')
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
 contract=json.loads((root/'scenarios/t23/contract.json').read_text());actions=read(root/'scenarios/t23/actions.csv');cases=read(root/'scenarios/t23/cases.csv')
 for name,digest in contract['input_hashes'].items():
  if sha(root/'scenarios/t23'/name)!=digest:raise ValueError('Contract input hash mismatch')
 if b'"' in (root/'scenarios/t23/actions.csv').read_bytes():raise ValueError('Frozen native input does not support quoted CSV')
 for c in cases:
  if [float(c[n]) for n in ('resend_seconds','max_resends','dack_seconds','tic_seconds','pending_threshold','flow_threshold_max')]!=[2.,2.,20.,1/36e6,16.,16.] or c['policy']!='actual-tx':raise ValueError('Unexpected fixture configuration')
 for p in (work,out):p.mkdir(parents=True,exist_ok=True)
 inherited=root/'evidence/t22/native';receipt=json.loads((inherited/'build.json').read_text())
 if receipt['status']!='passed' or receipt['source_pin']!=PIN or receipt['engine_pin']!=ENGINE or not receipt['linked_libraries_verified_elf']:raise ValueError('Unverified inherited native build receipt')
 tracked_path=inherited/receipt['tracked_source_verification']
 if sha(tracked_path)!=receipt['tracked_source_verification_sha256']:raise ValueError('Inherited tracked-source manifest mismatch')
 tracked=json.loads(tracked_path.read_text());verified={}
 for kind,folder in [('source',source),('engine',build.parent)]:
  count=0
  for name,digest in tracked[kind]['file_sha256'].items():
   p=folder/name;actual=hashlib.sha256(str(p.readlink()).encode()).hexdigest() if p.is_symlink() else sha(p)
   if actual!=digest:raise ValueError('Tracked build source changed: '+name)
   count+=1
  verified[kind]=count
 library=build/'lib';libraries={}
 for name in MODULES:
  p=library/f'libns3-dev-{name}-debug.so'
  if sha(p)!=receipt['libraries'][p.name] or p.read_bytes()[:4]!=b'\x7fELF':raise ValueError('Retained library changed or is not ELF: '+p.name)
  libraries[p.name]=sha(p)
 model={str(p.relative_to(source)):sha(p) for p in sorted((source/'model').iterdir()) if p.is_file()}
 inherited_copy=out/'build-provenance';inherited_copy.mkdir(exist_ok=True)
 shutil.copy2(inherited/'build.json',inherited_copy/'t22-build.json');shutil.copy2(inherited/'summary.json',inherited_copy/'t22-summary.json');shutil.copy2(tracked_path,inherited_copy/'tracked-source-verification.json')
 # Preserve the verifier and original build logs referenced by the accepted receipt.
 for n in ('verify_archive_trees.py','verify_elf.py','configure.log','build.log','build-resume.log','build-repair.log','build-final.log','csr-rebuild.log','elf-verification.json','archive-verification.json'):
  if (inherited/n).is_file():shutil.copy2(inherited/n,inherited_copy/n)
 build_record={'schema':'csr-tranche23-retained-native-build-v1','status':'passed','source_pin':PIN,'engine_pin':ENGINE,'source_tree':receipt['source_tree'],'engine_tree':receipt['engine_tree'],'engine_rebuilt_for_t23':False,'reused_accepted_t22_libraries':True,'fresh_fixture_compile':True,'production_source_unchanged':True,'engine_source_unchanged':True,'libraries':libraries,'linked_libraries_verified_elf':True,'tracked_source_verification':'build-provenance/tracked-source-verification.json','tracked_source_verification_sha256':sha(tracked_path),'tracked_files_reverified':verified,'accepted_t22_build':'build-provenance/t22-build.json','accepted_t22_build_sha256':sha(inherited/'build.json'),'accepted_t22_summary':'build-provenance/t22-summary.json','accepted_t22_summary_sha256':sha(inherited/'summary.json'),'compiler':{'path':str(Path(compiler).resolve()),'sha256':sha(Path(compiler).resolve())},'created_utc':datetime.now(timezone.utc).isoformat()}
 writejson(out/'build.json',build_record)
 overlay=work/'overlay/ns3';overlay.mkdir(parents=True,exist_ok=True)
 for p in (source/'model').iterdir():
  if p.is_file():
   q=overlay/p.name
   if q.exists() or q.is_symlink():q.unlink()
   q.symlink_to(p.resolve())
 patches=[];overlay_hashes={}
 for name,anchor in [('csr-hop-layer.h','class CsrHopLayer : public Object\n{'),('csr-mac-core.h','class CsrMacCore\n{')]:
  target=overlay/name;target.unlink();before=(source/'model'/name).read_text()
  if before.count(anchor)!=1:raise ValueError('Unexpected friend anchor: '+name)
  after=before.replace(anchor,anchor+'\n  friend struct CsrTranche23Access; // Fixture-only decoded ingress / read-only observation.',1);target.write_text(after)
  patches.extend(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='pinned/'+name,tofile='overlay/'+name));overlay_hashes[name]=sha(target)
 (out/'seams.patch').write_text(''.join(patches))
 binary=work/'tranche23-receiver';cmd=[compiler,'-std=c++23','-g','-DNS3_ASSERT_ENABLE','-DNS3_BUILD_PROFILE_DEBUG','-DNS3_LOG_ENABLE','-DSTACKTRACE_LIBRARY_IS_LINKED=1','-D__LINUX__','-I'+str(overlay.parent),'-I'+str(build/'include'),str(root/'scripts/ns3/tranche23_receiver.cc'),'-L'+str(library),'-Wl,-rpath,'+str(library),'-Wl,--no-as-needed',*[f'-lns3-dev-{n}-debug' for n in MODULES],'-lstdc++exp','-o',str(binary)]
 commands=[execute(cmd,out/'compile.log')]
 for mode in ('trace_on','trace_off'):commands.append(execute([binary,root/'scenarios/t23/actions.csv',out/mode,mode],out/(mode+'.log')))
 checkpoints=[];feedback=[];counts={}
 for c in cases:
  name=c['case_id'];on=out/'trace_on'/name;off=out/'trace_off'/name
  for leaf in ('states.csv','feedback.csv'):
   if (on/leaf).read_bytes()!=(off/leaf).read_bytes():raise ValueError('Observer-on/off changed fixture output: '+name+'/'+leaf)
  states=read(on/'states.csv');emitted=read(on/'feedback.csv');trace=read(on/'trace.csv')
  if list(states[0])!=contract['state_columns']:raise ValueError('Native state columns differ from contract')
  if emitted and list(emitted[0])!=contract['feedback_columns']:raise ValueError('Native feedback columns differ from contract')
  ca=[r for r in actions if r['case_id']==name]
  if len(states)!=len(ca):raise ValueError('Action/checkpoint count mismatch')
  for r,a in zip(states,ca):
   for k in ('case_id','step','action','packet'):
    if r[k]!=a[k]:raise ValueError('Action identity mismatch')
   if abs(float(r['time_s'])-float(a['observe_s']))>0.51e-9:raise ValueError('Observation clock mismatch')
   if int(r['nwk_owned'])!=int(r['nsdp_relay'])+int(r['nsdp_local']) or int(r['nwk_owned'])!=int(r['nwk_waiting'])+int(r['hop_resend']):raise ValueError('Native ownership conservation failed')
  marks=[r for r in trace if r['event']=='t23_checkpoint']
  if [r['sequence'] for r in marks]!=[r['step'] for r in states]:raise ValueError('Trace checkpoint markers mismatch')
  if any(r['event']=='tx_start' for r in trace):raise ValueError('Unexpected actual native radio transmission')
  tally={'ack':0,'dack':0};releases=0;expired=0
  snapshots={r['step']:r for r in states}
  for e in trace:
   if e['event']=='hop_completion':
    if e['reason'] not in tally:raise ValueError('Unplanned native completion: '+e['reason'])
    tally[e['reason']]+=1
   elif e['event']=='nwk_nsdp_release':releases+=1
   elif e['event']=='hop_capacity_release':
    if e['reason']!='dack_expiry':raise ValueError('Unexpected capacity release')
    expired+=1
   elif e['event']=='t23_checkpoint':
    s=snapshots[e['sequence']]
    if [int(s[n]) for n in ('ack_completed','dack_completed','nsdp_releases','dack_expired')]!=[tally['ack'],tally['dack'],releases,expired]:raise ValueError('Native counters disagree with independent trace')
  native_feedback=[e for e in trace if e['event']=='hop_feedback']
  if len(native_feedback)!=len(emitted):raise ValueError('Native feedback capture/trace mismatch')
  for e,f in zip(native_feedback,emitted):
   if e['reason'].upper()!=f['kind'] or abs(float(e['time_s'])-float(f['time_s']))>1e-9:raise ValueError('Native feedback capture differs from production trace')
  checkpoints+=states;feedback+=emitted;counts[name]={'checkpoints':len(states),'feedback_frames':len(emitted),'ack_completed':tally['ack'],'dack_completed':tally['dack'],'nsdp_releases':releases,'dack_expired':expired,'actual_mac_transmissions':0}
 for leaf,rows,columns in [('checkpoints.csv',checkpoints,contract['state_columns']),('feedback.csv',feedback,contract['feedback_columns'])]:
  with (out/leaf).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows(rows)
 failures=[];lookup={(r['case_id'],int(r['step'])):r for r in checkpoints}
 milestones=contract.get('milestones',[])+contract.get('native_milestones',[])
 for m in milestones:
  row=lookup[(m['case_id'],int(m['step']))]
  for field,value in m['equals'].items():
   if int(row[field])!=value:failures.append({'case_id':m['case_id'],'step':m['step'],'field':field,'expected':value,'actual':int(row[field])})
 if failures:writejson(out/'milestone-failures.json',failures);raise ValueError('Native sparse milestones failed')
 if model!={str(p.relative_to(source)):sha(p) for p in sorted((source/'model').iterdir()) if p.is_file()}:raise ValueError('Production source mutated')
 summary={'schema':'csr-tranche23-native-reference-v1','status':'passed','created_utc':datetime.now(timezone.utc).isoformat(),'source_pin':PIN,'engine_pin':ENGINE,'native_executed':True,'matlab_executed':False,'production_source_unchanged':True,'engine_source_unchanged':True,'engine_rebuilt_for_t23':False,'reused_accepted_t22_libraries':True,'fresh_fixture_compile':True,'observer_on_off_identical':True,'actual_mac_transmissions':0,'case_count':len(cases),'checkpoint_count':len(checkpoints),'feedback_count':len(feedback),'milestone_count':len(milestones),'cases':counts,'model_sources':model,'libraries':libraries,'input_bindings':{str(p.relative_to(root)):sha(p) for p in sorted((root/'scenarios/t23').iterdir()) if p.is_file()},'fixture_sources':{str(p.relative_to(root)):sha(p) for p in (root/'scripts/ns3/tranche23_receiver.cc',Path(__file__).resolve())},'commands':commands,'build_manifest':'build.json','build_manifest_sha256':sha(out/'build.json'),'binary_sha256':sha(binary),'overlay_headers':overlay_hashes,'seams_sha256':sha(out/'seams.patch'),'time_resolution_seconds':1e-9,'native_tic_seconds':28e-9,'scope':'Controlled post-security decoded ingress, real NWK ownership, production receiver feedback generation and Pairwise16 downstream feedback. No actual RF, security-ingress or campus execution claim. Settled states observed one microsecond after inputs; no same-tick wake-order equivalence claim.'}
 writejson(out/'summary.json',summary)
 writejson(out/'manifest.json',{'schema':'csr-tranche23-native-files-v1','files':{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json'}})
 return summary

def main():
 a=argparse.ArgumentParser(description=__doc__)
 for n in ('source','build','work','output'):a.add_argument('--'+n,type=Path,required=True)
 a.add_argument('--compiler',default='/usr/bin/g++');x=a.parse_args();root=Path(__file__).resolve().parents[1]
 result=run(x.source.resolve(),x.build.resolve(),x.work.resolve(),x.output.resolve(),root,x.compiler);print(json.dumps({k:result[k] for k in ('status','case_count','checkpoint_count','feedback_count','milestone_count')}))
if __name__=='__main__':main()
