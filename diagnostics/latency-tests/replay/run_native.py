#!/usr/bin/env python3
"""Build the public-API HOP replay without changing pinned production source."""
import argparse,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'mac'))
import native_build_support as B
from compare_hop_replay import inspect
import csv

def main():
 p=argparse.ArgumentParser();p.add_argument('--ns3-source',type=Path,required=True);p.add_argument('--ns3-build',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--compiler',default='g++');a=p.parse_args()
 source=a.ns3_source.resolve();build=a.ns3_build.resolve();out=a.output.resolve()
 B.check_source(source,build);out.mkdir(parents=True,exist_ok=False)
 before=B.input_snapshot(source,build);status={'status':'running','native_executed':False,'matlab_executed':False,'source_commit':B.PIN,'source_inputs':before}
 try:
  binary=out/'hop-tests';cmd=B.compile_runner(source,build,binary,a.compiler)
  cmd[cmd.index(str(source/'csr-opnet-scenario-runner.cc'))]=str(HERE/'hop_replay.cc');status['compile_command']=cmd
  with (out/'compile.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
  status['binary_sha256']=B.digest(binary)
  with (out/'run.log').open('w') as f:
   status['native_executed']=True
   subprocess.run([str(binary),str(HERE/'inputs.csv'),str(out/'hop.csv')],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
  with (HERE/'inputs.csv').open(newline='') as f:cases=list(csv.DictReader(f))
  result=inspect(out/'hop.csv',cases);status['checks']={k:v['checks'] for k,v in result.items()}
  status['structural_passed']=all(all(v['checks'].values()) for v in result.values())
  B.check_source(source,build)
  if before!=B.input_snapshot(source,build):raise ValueError('Native source/build changed')
  status['status']='completed'
 except Exception as e:status.update(status='failed',error=str(e));raise
 finally:
  status['fixture_hashes']={p.name:B.digest(p) for p in HERE.iterdir() if p.is_file()}
  (out/'metadata.json').write_text(json.dumps(status,indent=2)+'\n')
 if not status['structural_passed']:raise SystemExit(1)
if __name__=='__main__':main()
