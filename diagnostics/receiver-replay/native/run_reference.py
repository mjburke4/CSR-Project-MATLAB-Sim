#!/usr/bin/env python3
"""Build and replay the bundled fixture against an existing pinned ns-3 build."""
import argparse,pathlib,subprocess,sys,time,json
p=argparse.ArgumentParser();p.add_argument('--engine-build',type=pathlib.Path,required=True);a=p.parse_args();N=pathlib.Path(__file__).resolve().parent
subprocess.run([sys.executable,str(N/'build_replay.py'),'--engine-build',str(a.engine_build)],check=True)
start=time.monotonic()
with (N/'run-replay.log').open('w') as f:subprocess.run([str(N/'receiver-replay'),str(N.parent/'inputs'),str(N/'replay-output.log')],stdout=f,stderr=subprocess.STDOUT,check=True)
subprocess.run([sys.executable,str(N/'validate_native.py')],check=True)
(N/'run-receipt.json').write_text(json.dumps(dict(exit_code=0,elapsed_s=time.monotonic()-start,simulation_start_s=620,simulation_stop_s=669,comparison_start_s=657,comparison_stop_s=669,matlab_executed=False),indent=2)+'\n')
