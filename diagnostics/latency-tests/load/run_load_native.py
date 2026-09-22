#!/usr/bin/env python3
"""Execute an already built accepted pristine csr-opnet-scenario-runner."""
import argparse,json,subprocess,time
from pathlib import Path
from generate_scenarios import ROOT,sha
PIN='486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b'
def main():
 p=argparse.ArgumentParser(); p.add_argument('--runner',type=Path,required=True); p.add_argument('--build-receipt',type=Path,required=True); p.add_argument('--output',type=Path,required=True); p.add_argument('--cases',nargs='+'); a=p.parse_args()
 out=a.output.resolve(); out.mkdir(parents=True,exist_ok=False)
 status={'status':'running','native_executed':False,'acceptance_established':False,'completed_cases':[]}
 try:
  # Receipt is supplied by the existing accepted build workflow, not fabricated here.
  receipt=json.loads(a.build_receipt.read_text()); runner=a.runner.resolve()
  assert receipt['source_commit']==PIN and receipt['runner_sha256']==sha(runner),'Build receipt mismatch'
  status.update(build_receipt=receipt,build_receipt_sha256=sha(a.build_receipt),runner_sha256=sha(runner),binary_provenance_scope='External receipt asserted; this wrapper does not rebuild or independently attest library bindings')
  plan=json.loads((ROOT/'plan.json').read_text()); ids=[c['id'] for c in plan['cases']]
  chosen=a.cases or ids; assert len(set(chosen))==len(chosen) and set(chosen)<=set(ids),'Unknown or duplicate cases'
  (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
  for c in plan['cases']:
   if c['id'] not in chosen: continue
   dest=out/c['id']; dest.mkdir(); scenario=ROOT/c['scenario']; assert sha(scenario)==c['sha256'],'Scenario changed'
   cmd=[str(runner),f'--scenario={scenario}',f'--trace={dest / "ns3-trace.csv"}',f'--appDiagnostics={dest / "app-admission-diagnostics.csv"}','--stop=600','--flowLimit=0','--dutyCycling=1','--opnetAlignedDutyCycle=1','--gatewayDiscovery=1','--opnetAppGating=1','--aggregateTraceOnly=0','--admissionTrace=1','--quietModelLogs=1','--stochasticSyncThreshold=1']
   record={'status':'running','argv':cmd,'scenario_sha256':sha(scenario)}; (dest/'status.json').write_text(json.dumps(record,indent=2))
   start=time.monotonic(); status['native_executed']=True
   with (dest/'run.log').open('wb') as log: result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
   record.update(status='completed' if result.returncode==0 else 'failed',exit_code=result.returncode,wall_seconds=time.monotonic()-start)
   (dest/'status.json').write_text(json.dumps(record,indent=2)); assert result.returncode==0,'Native run failed; inspect '+str(dest/'run.log')
   status['completed_cases'].append(c['id'])
  assert sha(runner)==status['runner_sha256'],'Binary changed'
  status['status']='completed-review-required'
 except Exception as e:
  status.update(status='failed',failure=str(e)); raise
 finally:
  (out/'status.json').write_text(json.dumps(status,indent=2)+'\n')
  (out/'files.json').write_text(json.dumps({str(f.relative_to(out)):sha(f) for f in sorted(out.rglob('*')) if f.is_file() and f.name!='files.json'},indent=2)+'\n')
if __name__=='__main__': main()
