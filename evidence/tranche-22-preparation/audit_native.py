#!/usr/bin/env python3
"""Independent native artifact/fixture/lifecycle readiness audit."""
import csv,hashlib,json
from pathlib import Path
ROOT=Path('csr22');OUT=ROOT/'evidence/t22/native';SOURCE=Path('t22-work/native/CSR-Project-NS3-part2-486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b');BUILD=Path('t22-work/native/ns-3-dev-git-6b5cd24ea80713ce16d88575869aedd6f432bdae/build')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
 with p.open(newline='') as f:return list(csv.DictReader(f))
def main():
 s=json.loads((OUT/'summary.json').read_text());build_receipt=json.loads((OUT/'build.json').read_text());c=json.loads((ROOT/'scenarios/t22/contract.json').read_text());fail=[]
 if build_receipt['libraries']!={f'libns3-dev-{k}-debug.so':v for k,v in s['libraries'].items()}:fail.append('build_execution_library_mismatch')
 for record in [build_receipt['configure'],*build_receipt['build_attempts']]:
  if sha(OUT/record['log'])!=record['log_sha256']:fail.append('build_log_binding')
 if build_receipt['build_attempts'][-1]['exit_code']!=0 or not build_receipt['linked_libraries_verified_elf']:fail.append('final_build_not_complete')
 binary=Path(s['commands'][1]['argv'][0]);libs={k:BUILD/'lib'/f'libns3-dev-{k}-debug.so' for k in s['libraries']}
 for name,p in {'binary':binary,**libs}.items():
  if p.read_bytes()[:4]!=b'\x7fELF':fail.append('not_elf:'+name)
  expected=s['binary_sha256'] if name=='binary' else s['libraries'][name]
  if sha(p)!=expected:fail.append('elf_hash:'+name)
 original=(SOURCE/'model/csr-hop-layer.h').read_text();overlay=Path('t22-work/native/final/overlay/ns3/csr-hop-layer.h').read_text();seam='\n  friend struct CsrTranche22Access; // T22 fixture-only observation and protected-feedback adapter.'
 if overlay.count(seam)!=1 or overlay.replace(seam,'',1)!=original:fail.append('non_observational_header_change')
 for name,digest in s['model_sources'].items():
  if sha(SOURCE/name)!=digest:fail.append('model_hash:'+name)
 for command in s['commands']:
  if command['exit_code']!=0 or sha(OUT/command['log'])!=command['log_sha256']:fail.append('command_receipt')
 rows=read(OUT/'checkpoints.csv');lookup={(r['case_id'],int(r['step'])):r for r in rows};milestones=0
 for m in c['milestones']:
  for field,expected in m['equals'].items():
   milestones+=1
   if int(lookup[m['case_id'],m['step']][field])!=expected:fail.append(f'milestone:{m["case_id"]}:{m["step"]}:{field}')
 cases={};total_events=0
 for folder in sorted((OUT/'raw').iterdir()):
  if not folder.is_dir():continue
  completed={};dack={};released={};checkpoints=0
  for r in read(folder/'trace.csv'):
   total_events+=1;k=(r['peer'],r['sequence'])
   if r['event']=='tx_start':fail.append('uncontrolled_tx:'+folder.name)
   if r['event']=='hop_completion':
    if k in completed:fail.append('duplicate_completion:'+folder.name)
    completed[k]=r
    if r['reason']=='dack':dack[k]=r
   elif r['event']=='hop_capacity_release':
    if k in released or k not in dack:fail.append('unowned_or_duplicate_dack_release:'+folder.name)
    released[k]=r
    if k in dack:
     dd=dict(x.split('=',1) for x in dack[k]['detail'].split(';') if '=' in x)
     expected=40 if int(dd['resend_count'])>=2 else 20
     elapsed=float(r['time_s'])-float(dack[k]['time_s'])
     if not expected<=elapsed<=expected+1e-6:fail.append('dack_hold_duration:'+folder.name)
   elif r['event']=='t22_checkpoint':checkpoints+=1
  selected=[r for r in rows if r['case_id']==folder.name];offered=0
  for r in selected:
   p={k:int(r[k]) for k in ['accepted','global_pending','resend','dack_holds','ack_total','dack_total','fail_total','nsdp_release_total','dack_expired_total']}
   offered+=p['accepted']==1;terminal=p['ack_total']+p['dack_total']+p['fail_total']
   if p['global_pending']!=p['resend']+p['dack_holds'] or offered!=terminal+p['resend'] or p['nsdp_release_total']!=terminal:fail.append('ownership_conservation:'+folder.name)
  if checkpoints!=len(selected):fail.append('checkpoint_membership:'+folder.name)
  cases[folder.name]={'checkpoints':checkpoints,'terminal_identities':len(completed),'dack_identities':len(dack),'dack_capacity_identities_released':len(released)}
 result={'schema':'csr-t22-independent-native-review-v1','passed':not fail,'remaining_blockers':fail,'native_executed':s['native_executed'],'matlab_executed':False,'case_count':len(cases),'checkpoint_count':len(rows),'individual_milestone_assertions':milestones,'raw_trace_events':total_events,'actual_elf_artifacts_verified':len(libs)+1,'build_and_execution_library_hashes_match':True,'build_attempts_retained':len(build_receipt['build_attempts']),'single_friend_seam_only':overlay.replace(seam,'',1)==original,'cases':cases,'bindings':{str(p.relative_to(ROOT)):sha(p) for p in [OUT/'build.json',OUT/'manifest.json',OUT/'summary.json',OUT/'checkpoints.csv',OUT/'seams.patch',ROOT/'scripts/ns3/tranche22_window.cc',ROOT/'scripts/run_tranche22_ns3_reference.py']},'scope':'Preparation gate; actual native fixture execution, all inherited MATLAB behavior unchanged; MATLAB cross-engine execution pending.'}
 Path('t22-work/review/native-review.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(bool(fail))
if __name__=='__main__':main()
