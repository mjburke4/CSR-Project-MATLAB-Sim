#!/usr/bin/env python3
"""Run the isolated light/drain fixture against the packaged fixed plan."""
import argparse,hashlib,json,subprocess,time,shutil
from pathlib import Path

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--runner',required=True,type=Path);p.add_argument('--fixture-receipt',required=True,type=Path);p.add_argument('--plan',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
 plan=json.loads(a.plan.read_text());receipt=json.loads(a.fixture_receipt.read_text());runner=a.runner.resolve();assert sha(runner)==receipt['runner_sha256'],'Fixture binary/receipt mismatch';assert receipt['source_commit']=='486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b';assert receipt['production_source_unchanged']
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);shutil.copy2(a.plan,out/'plan.json');status=dict(schema='light-drain-native-execution-v1',status='running',runner_sha256=sha(runner),fixture_receipt_sha256=sha(a.fixture_receipt),completed_cases=[])
 try:
  for c in plan['cases']:
   scenario=(a.plan.parent/c['scenario']).resolve();assert sha(scenario)==c['sha256'],'Scenario modified'
   dest=out/c['id'];dest.mkdir();cmd=[str(runner),f'--scenario={scenario}',f'--trace={dest/"ns3-trace.csv"}',f'--appDiagnostics={dest/"app-admission-diagnostics.csv"}',f'--stop={c["duration_s"]}',f'--trafficStop={c["traffic_stop_s"]}','--flowLimit=0','--dutyCycling=1','--opnetAlignedDutyCycle=1','--gatewayDiscovery=1','--opnetAppGating=1','--aggregateTraceOnly=0','--admissionTrace=1','--quietModelLogs=1','--stochasticSyncThreshold=1']
   record=dict(argv=cmd,scenario_sha256=sha(scenario),status='running');start=time.monotonic()
   with (dest/'run.log').open('wb') as f:result=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
   record.update(exit_code=result.returncode,wall_seconds=time.monotonic()-start,status='completed' if result.returncode==0 else 'failed');(dest/'run-status.json').write_text(json.dumps(record,indent=2)+'\n');(dest/'status.json').write_text(json.dumps(record,indent=2)+'\n');assert result.returncode==0,'Native run failed; preserve output'
   status['completed_cases'].append(c['id'])
  assert sha(runner)==status['runner_sha256'];status['status']='completed-review-required'
 except Exception as e:status.update(status='failed',error=str(e));raise
 finally:
  (out/'status.json').write_text(json.dumps(status,indent=2)+'\n');(out/'files.json').write_text(json.dumps({str(f.relative_to(out)):sha(f) for f in sorted(out.rglob('*')) if f.is_file() and f.name!='files.json'},indent=2)+'\n')
if __name__=='__main__':main()
